"""
Esport Calendar Scraper - Raspa eventos de tips.gg e gera calendario ICS.
Suporta CS2, Valorant, Rocket League, League of Legends.

Ponto de entrada principal. Delega orquestracao para os modulos especializados.
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta, date
from typing import List, Tuple

import pytz

from config import (
    CALENDAR_FILENAME,
    DELETE_OLDER_THAN_DAYS,
    CS2_TEAMS,
    CS2_EXCLUSIONS,
    VALORANT_TEAMS,
    ROCKET_LEAGUE_TEAMS,
    LOL_TEAMS,
    BR_TZ_NAME,
    STATE_FILE,
    CS2_RUN_INTERVAL_MINUTES_BRIGHTDATA,
    VAL_RL_LOL_RUN_HOURS_BRIGHTDATA,
    CS2_RUN_HOURS_SCRAPEDO,
    VAL_RL_LOL_RUN_HOURS_SCRAPEDO,
    GameConfig,
    GameKey,
)
from logger import setup_logger
from calendar_manager import (
    load_calendar,
    save_calendar,
    get_existing_uids,
    dedupe_by_uid,
    dedupe_by_url,
    prune_older_than,
)
from scraper import scrape_days_for_game, get_active_api, ScraperAPI
from healthcheck import save_healthcheck


BR_TZ = pytz.timezone(BR_TZ_NAME)

GAMES_CONFIG = {
    GameKey.CS2: GameConfig(
        prefix="[CS2] ",
        base_path="https://tips.gg/csgo/matches/",
        days_to_scrape=3,
        once_per_day=False,
        run_at_hour=0,
        teams=CS2_TEAMS,
        exclusions=CS2_EXCLUSIONS,
    ),
    GameKey.VAL: GameConfig(
        prefix="[V] ",
        base_path="https://tips.gg/valorant/matches/",
        days_to_scrape=1,
        once_per_day=True,
        run_at_hour=6,
        teams=VALORANT_TEAMS,
        exclusions=set(),
    ),
    GameKey.RL: GameConfig(
        prefix="[RL] ",
        base_path="https://tips.gg/rl/matches/",
        days_to_scrape=1,
        once_per_day=True,
        run_at_hour=6,
        teams=ROCKET_LEAGUE_TEAMS,
        exclusions=set(),
    ),
    GameKey.LOL: GameConfig(
        prefix="[LOL] ",
        base_path="https://tips.gg/lol/matches/",
        days_to_scrape=1,
        once_per_day=True,
        run_at_hour=6,
        teams=LOL_TEAMS,
        exclusions=set(),
    ),
}


# ==================== GERENCIAMENTO DE ESTADO ====================

_state_cache: dict = None

def load_state() -> dict:
    """Carrega estado do arquivo state.json. Retorna dict vazio se inexistente. Com cache em memoria."""
    global _state_cache

    if _state_cache is not None:
        return _state_cache

    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                _state_cache = json.load(f)
                return _state_cache
        except (FileNotFoundError, json.JSONDecodeError, PermissionError) as e:
            logger = setup_logger("state")
            logger.warning(f"Falha ao carregar state.json: {e}")

    _state_cache = {"last_run": {}, "cs2_day_offset": 0}
    return _state_cache


def save_state(state: dict) -> None:
    """Persiste estado em state.json. Atualiza cache."""
    global _state_cache

    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        _state_cache = state
    except (IOError, PermissionError) as e:
        raise IOError(f"Erro ao salvar state.json: {e}")


def get_run_config():
    """Retorna configuracao de frequencia baseada na API ativa."""
    active_api = get_active_api()

    if active_api == ScraperAPI.BRIGHT_DATA:
        return {
            "cs2_mode": "interval",  # A cada X minutos
            "cs2_interval_min": CS2_RUN_INTERVAL_MINUTES_BRIGHTDATA,
            "val_rl_lol_hours": VAL_RL_LOL_RUN_HOURS_BRIGHTDATA,
        }
    else:  # SCRAPE_DO
        return {
            "cs2_mode": "fixed_hours",  # Horarios fixos
            "cs2_hours": CS2_RUN_HOURS_SCRAPEDO,
            "val_rl_lol_hours": VAL_RL_LOL_RUN_HOURS_SCRAPEDO,
        }


def should_run_game(game_key: GameKey, once_per_day: bool, run_at_hour: int) -> bool:
    """Verifica se jogo deve rodar agora baseado na API ativa."""
    now = datetime.now(BR_TZ)
    config = get_run_config()
    state = load_state()

    # CS2: logica dinamica baseada na API
    if game_key == GameKey.CS2:
        last_run_str = state.get("last_run", {}).get(game_key)

        if not last_run_str:
            return True

        try:
            last_run = datetime.fromisoformat(last_run_str)

            # Bright Data: a cada X minutos
            if config["cs2_mode"] == "interval":
                minutes_since = (now - last_run).total_seconds() / 60
                return minutes_since >= config["cs2_interval_min"]

            # Scrape.do: horarios fixos
            else:
                cs2_hours = config["cs2_hours"]
                if now.hour not in cs2_hours:
                    return False
                return last_run.hour != now.hour or last_run.date() != now.date()

        except (ValueError, TypeError):
            return True

    # VAL/RL/LOL: horarios fixos baseados na API
    allowed_hours = config["val_rl_lol_hours"]

    if now.hour not in allowed_hours:
        return False

    last_run_str = state.get("last_run", {}).get(game_key)
    if not last_run_str:
        return True

    try:
        last_run = datetime.fromisoformat(last_run_str)
        # Permite se for horario diferente ou dia diferente
        return last_run.hour != now.hour or last_run.date() != now.date()
    except (ValueError, TypeError):
        return True


def mark_game_as_run(game_key: GameKey) -> None:
    """Marca jogo como executado. CS2 usa timestamp completo, outros jogos apenas data."""
    state = load_state()
    state.setdefault("last_run", {})

    now = datetime.now(BR_TZ)

    # CS2: salva timestamp completo (ISO) para controle de 4h
    if game_key == GameKey.CS2:
        state["last_run"][game_key] = now.isoformat()
    else:
        # Outros jogos: apenas data (controle diario)
        state["last_run"][game_key] = now.strftime("%Y-%m-%d")

    save_state(state)


def get_cs2_target_days(today: date) -> List[date]:
    """Retorna dias-alvo para CS2 baseado no offset rotativo (0, 1, 2)."""
    state = load_state()
    offset = state.get("cs2_day_offset", 0)
    return [today + timedelta(days=offset)]


def advance_cs2_offset() -> Tuple[int, int]:
    """Avança offset rotativo do CS2: (0→1, 1→2, 2→0). Retorna (antigo, novo)."""
    state = load_state()
    current = state.get("cs2_day_offset", 0)
    next_offset = (current + 1) % 3
    state["cs2_day_offset"] = next_offset
    save_state(state)
    return current, next_offset


def main() -> bool:
    """Orquestrador principal. Carrega calendario, raspa partidas, gera eventos ICS e salva. Retorna True se sucesso."""
    logger = setup_logger("generate_ics")
    start_time = time.time()
    errors = []
    games_stats = {}

    logger.info("=" * 60)
    logger.info("\U0001f680 INICIANDO GERACAO DE CALENDARIO")
    active_api = get_active_api()
    api_name = "Bright Data (5k/mês)" if active_api == ScraperAPI.BRIGHT_DATA else "Scrape.do (1k/mês)"
    logger.info(f"🌐 API ativa: {api_name}")
    logger.info("=" * 60)

    cal = load_calendar()
    state = load_state()
    now = datetime.now(BR_TZ)
    today = now.date()

    deduped = dedupe_by_uid(cal)
    if deduped > 0:
        logger.info(f"\U0001f5d1\ufe0f  Removidos {deduped} eventos duplicados (UID)")

    deduped_url = dedupe_by_url(cal)
    if deduped_url > 0:
        logger.info(f"\U0001f5d1\ufe0f  Removidos {deduped_url} eventos duplicados (URL)")

    existing_uids = get_existing_uids(cal)

    cutoff = today - timedelta(days=DELETE_OLDER_THAN_DAYS)
    removed = prune_older_than(cal, cutoff)
    if removed > 0:
        logger.info(f"\U0001f5d1\ufe0f  Removidos {removed} eventos anteriores a {cutoff.strftime('%d/%m/%Y')}")

    total_added = 0

    try:
        for game_key, cfg in GAMES_CONFIG.items():
            if not should_run_game(game_key, cfg.once_per_day, cfg.run_at_hour):
                config = get_run_config()

                # CS2: mostra proximo horario baseado na API
                if game_key == GameKey.CS2:
                    state = load_state()
                    last_run_str = state.get("last_run", {}).get(game_key)

                    if config["cs2_mode"] == "interval":
                        # Bright Data: mostra minutos restantes
                        if last_run_str:
                            try:
                                last_run = datetime.fromisoformat(last_run_str)
                                minutes_since = (now - last_run).total_seconds() / 60
                                minutes_remaining = max(0, config["cs2_interval_min"] - minutes_since)
                                logger.info(
                                    f"\u23ed\ufe0f  CS2 proxima execucao em {minutes_remaining:.0f} min "
                                    f"(a cada {config['cs2_interval_min']} min)"
                                )
                            except (ValueError, TypeError):
                                pass
                    else:
                        # Scrape.do: mostra proximo horario fixo
                        cs2_hours = config["cs2_hours"]
                        next_hours = [h for h in cs2_hours if h > now.hour]
                        if next_hours:
                            next_hour = next_hours[0]
                            next_run_date = today
                        else:
                            next_hour = cs2_hours[0]
                            next_run_date = today + timedelta(days=1)

                        logger.info(
                            f"\u23ed\ufe0f  CS2 proxima execucao: "
                            f"{next_hour:02d}:00 ({next_run_date.strftime('%d/%m/%Y')}) "
                            f"(horarios: {', '.join([f'{h:02d}:00' for h in cs2_hours])})"
                        )
                else:
                    # VAL/RL/LOL: mostra proximo horario
                    allowed_hours = config["val_rl_lol_hours"]
                    next_hours = [h for h in allowed_hours if h > now.hour]
                    if next_hours:
                        next_hour = next_hours[0]
                        next_run_date = today
                    else:
                        next_hour = allowed_hours[0]
                        next_run_date = today + timedelta(days=1)

                    logger.info(
                        f"\u23ed\ufe0f  {game_key.value} proxima execucao: "
                        f"{next_hour:02d}:00 ({next_run_date.strftime('%d/%m/%Y')}) "
                        f"(horarios: {', '.join([f'{h:02d}:00' for h in allowed_hours])})"
                    )
                continue

            if game_key == GameKey.CS2:
                current_offset = state.get("cs2_day_offset", 0)
                target_days = get_cs2_target_days(today)
                next_offset = (current_offset + 1) % 3
                logger.info(
                    f"\U0001f4c5 {game_key.value} offset {current_offset}\u2192{next_offset} "
                    f"| LIMPANDO {target_days[0].strftime('%d/%m/%Y')}"
                )
            else:
                target_days = [today]
                logger.info(f"\U0001f4c5 {game_key.value} | LIMPANDO {today.strftime('%d/%m/%Y')}")

            new_events, stats = scrape_days_for_game(game_key, cfg, target_days, existing_uids)

            for ev in new_events:
                cal.add_component(ev)

            total_added += stats.added

            # Coleta stats por jogo para healthcheck
            games_stats[game_key.value] = {
                "added": stats.added,
                "scraped": stats.scripts_total,
                "filtered": stats.skipped_not_allowed,
                "skipped_tbd": stats.skipped_tbd,
                "skipped_past": stats.skipped_past
            }

            logger.info(
                f"- ENCONTRADOS ( {stats.scripts_total} ) "
                f"| NAO PERMITIDOS ( {stats.skipped_not_allowed} ) "
                f"| ADICIONADOS ( {stats.added} )"
            )

            if stats.matches:
                matches_str = " | ".join(
                    [f"{m.teams} - {m.time}" for m in stats.matches]
                )
                logger.info(
                    f"- JOGOS {target_days[0].strftime('%d/%m/%Y')} | {matches_str}"
                )

            logger.info("-" * 60)

            # Marca execucao (CS2 sempre marca timestamp, outros so se once_per_day)
            if game_key == GameKey.CS2 or cfg.once_per_day:
                mark_game_as_run(game_key)

            if game_key == GameKey.CS2:
                current, next_offset = advance_cs2_offset()
                next_day = today + timedelta(days=next_offset)
                logger.info(f"CS2 proximo offset: {next_offset} ({next_day.strftime('%d/%m/%Y')})")
                logger.info("-" * 60)

        deduped_final = dedupe_by_uid(cal)
        if deduped_final > 0:
            logger.info(f"\U0001f5d1\ufe0f  Removidos {deduped_final} eventos duplicados (final)")

    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        errors.append(error_msg)
        logger.error(f"\u274c ERRO GERAL: {error_msg}")
        import traceback
        logger.error(f"Stack trace:\n{traceback.format_exc()}")

        # Salva healthcheck mesmo com erro
        execution_time = time.time() - start_time
        save_healthcheck(
            success=False,
            total_added=total_added,
            errors=errors,
            execution_time_seconds=execution_time,
            games_processed=games_stats
        )
        return False

    logger.info(f"\U0001f4be Salvando {CALENDAR_FILENAME}...")
    try:
        save_calendar(cal)
    except IOError as e:
        logger.error(str(e))
        return False

    logger.info(f"\u2705 Concluido | Total adicionados: {total_added}")

    # Salva healthcheck com sucesso
    execution_time = time.time() - start_time
    total_scraped = sum(g.get("scraped", 0) for g in games_stats.values())

    save_healthcheck(
        success=True,
        total_added=total_added,
        total_scraped=total_scraped,
        errors=errors,
        execution_time_seconds=execution_time,
        games_processed=games_stats
    )

    logger.info(f"\u23f1\ufe0f  Tempo de execucao: {execution_time:.2f}s")
    logger.info("=" * 60)
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
