"""
Esport Calendar Scraper - Raspa eventos de tips.gg e gera calendario ICS.
Suporta CS2, Valorant, Rocket League, League of Legends.

Ponto de entrada principal. Delega orquestracao para os modulos especializados.
"""

import json
import os
import sys
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
from scraper import scrape_days_for_game


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

def load_state() -> dict:
    """Carrega estado do arquivo state.json. Retorna dict vazio se inexistente."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_run": {}, "cs2_day_offset": 0}


def save_state(state: dict) -> None:
    """Persiste estado em state.json."""
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        raise IOError(f"Erro ao salvar state.json: {e}")


def should_run_game(game_key: str, once_per_day: bool, run_at_hour: int) -> bool:
    """Verifica se jogo deve rodar agora: controle de hora + execucao unica por dia."""
    if not once_per_day:
        return True

    now = datetime.now(BR_TZ)
    if now.hour < run_at_hour:
        return False

    state = load_state()
    last = state.get("last_run", {}).get(game_key)
    return last != now.strftime("%Y-%m-%d")


def mark_game_as_run(game_key: str) -> None:
    """Marca jogo como executado hoje no estado."""
    state = load_state()
    state.setdefault("last_run", {})
    state["last_run"][game_key] = datetime.now(BR_TZ).strftime("%Y-%m-%d")
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

    logger.info("=" * 60)
    logger.info("\U0001f680 INICIANDO GERACAO DE CALENDARIO")
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
                next_run_date = today if now.hour < cfg.run_at_hour else today + timedelta(days=1)
                logger.info(
                    f"\u23ed\ufe0f  {game_key.value} proxima execucao: "
                    f"{cfg.run_at_hour:02d}:00 ({next_run_date.strftime('%d/%m/%Y')})"
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

            if cfg.once_per_day:
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
        logger.error(f"\u274c ERRO GERAL: {type(e).__name__}: {e}")
        import traceback
        logger.error(f"Stack trace:\n{traceback.format_exc()}")
        return False

    logger.info(f"\U0001f4be Salvando {CALENDAR_FILENAME}...")
    try:
        save_calendar(cal)
    except IOError as e:
        logger.error(str(e))
        return False

    logger.info(f"\u2705 Concluido | Total adicionados: {total_added}")
    logger.info("=" * 60)
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
