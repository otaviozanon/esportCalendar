import os
import json
import hashlib
from datetime import datetime, timedelta, date
from typing import Dict, Set, Tuple, List

import pytz
from bs4 import BeautifulSoup
from icalendar import Calendar, Event, Alarm
import requests


# ================== CONFIGURAÇÕES GLOBAIS ==================
CALENDAR_FILENAME = "calendar.ics"
STATE_FILE = "state.json"

BR_TZ = pytz.timezone("America/Sao_Paulo")
UTC_TZ = pytz.utc

DELETE_OLDER_THAN_DAYS = 7
REQUEST_TIMEOUT = 30

SOURCE_MARKER = "X-SETT-SOURCE:TIPSGG"
TIPS_URL_HINT = "https://tips.gg/matches/"

SCRAPE_DO_API_KEY = os.getenv("SCRAPE_DO_API_KEY", "")
SCRAPE_DO_URL = "https://api.scrape.do"


# ================== CONFIGURAÇÃO DE JOGOS ==================
def normalize_team(name: str) -> str:
    """Normaliza nome do time para comparação (minúsculas e sem espaços)"""
    return (name or "").lower().strip()


GAMES: Dict = {
    "CS2": {
        "prefix": "[CS2] ",
        "base_path": "https://tips.gg/csgo/matches/",
        "days_to_scrape": 1,
        "once_per_day": False,
        "teams": {
            "FURIA", "paiN Gaming", "MIBR", "Imperial", "Fluxo", 
            "RED Canids", "Legacy", "ODDIK", "Imperial Esports", "Gaimin Gladiators"
        },
        "exclusions": {
            "Imperial.A", "Imperial Fe", "MIBR.A", "paiN.A", "ODDIK.A",
            "Imperial Academy", "Imperial.Acd", "Imperial Female",
            "Furia Academy", "Furia.A", "Pain Academy", "Mibr Academy", 
            "Legacy Academy", "ODDIK Academy", "RED Canids Academy", "Fluxo Academy"
        },
    },
    "VAL": {
        "prefix": "[V] ",
        "base_path": "https://tips.gg/valorant/matches/",
        "days_to_scrape": 1,
        "once_per_day": True,
        "teams": {"LOUD", "FURIA", "MIBR"},
        "exclusions": set(),
    },
    "RL": {
        "prefix": "[RL] ",
        "base_path": "https://tips.gg/rl/matches/",
        "days_to_scrape": 1,
        "once_per_day": True,
        "teams": {"FURIA", "Team Secret"},
        "exclusions": set(),
    },
    "LOL": {
        "prefix": "[LOL] ",
        "base_path": "https://tips.gg/lol/matches/",
        "days_to_scrape": 1,
        "once_per_day": True,
        "teams": {"paiN Gaming", "LOUD", "Vivo Keyd Stars", "RED Canids"},
        "exclusions": set(),
    },
}

# Pre-normaliza times para comparação rápida
for cfg in GAMES.values():
    cfg["teams_norm"] = {normalize_team(t) for t in cfg["teams"]}
    cfg["exclusions_norm"] = {normalize_team(t) for t in cfg["exclusions"]}


# ================== LOGGING ==================
def log(msg: str) -> None:
    """Exibe mensagem com timestamp em horário de São Paulo"""
    now = datetime.now(BR_TZ).strftime("%H:%M:%S")
    print(f"[{now}] {msg}")


# ================== CALENDÁRIO ==================
def load_calendar(path: str) -> Calendar:
    """Carrega calendário ICS existente ou cria um novo"""
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                return Calendar.from_ical(f.read())
        except Exception as e:
            log(f"⚠️ Falha ao ler {path}: {e}. Criando calendário novo.")

    cal = Calendar()
    cal.add('prodid', '-//Esport Calendar BR//tips.gg//')
    cal.add('version', '2.0')
    return cal


def save_calendar(cal: Calendar, path: str) -> None:
    """Salva calendário em arquivo ICS"""
    with open(path, "wb") as f:
        f.write(cal.to_ical())


def get_existing_uids(cal: Calendar) -> Set[str]:
    """Retorna conjunto de UIDs já existentes no calendário"""
    return {str(c.get('uid')) for c in cal.walk('VEVENT') if c.get('uid')}


def normalize_event_datetime_utc(dt: datetime) -> datetime:
    """Normaliza datetime para UTC sem microsegundos"""
    if dt.tzinfo is None:
        dt = UTC_TZ.localize(dt)
    return dt.astimezone(UTC_TZ).replace(microsecond=0, second=0)


def is_ours(component) -> bool:
    """Verifica se o evento foi criado por este script"""
    desc = str(component.get('description', ''))
    return SOURCE_MARKER in desc or TIPS_URL_HINT in desc


def event_start_date_local(component) -> date | None:
    """Extrai data do evento em horário local (São Paulo)"""
    try:
        dt = component.get('dtstart').dt
        if isinstance(dt, datetime):
            if dt.tzinfo is None:
                dt = UTC_TZ.localize(dt)
            return dt.astimezone(BR_TZ).date()
        elif isinstance(dt, date):
            return dt
    except Exception:
        pass
    return None


def prune_older_than(cal: Calendar, cutoff_date: date) -> int:
    """Remove eventos antigos do calendário (mais de 7 dias)"""
    to_remove = [
        c for c in cal.walk('VEVENT')
        if is_ours(c) and (d := event_start_date_local(c)) and d < cutoff_date
    ]

    for comp in to_remove:
        cal.subcomponents.remove(comp)

    return len(to_remove)


# ================== ESTADO (EXECUÇÃO DIÁRIA) ==================
def load_state() -> Dict:
    """Carrega estado de execução (qual jogo já rodou hoje)"""
    if not os.path.exists(STATE_FILE):
        return {"last_run_date": None, "games_run_today": {}}

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
            state.setdefault("games_run_today", {})
            return state
    except Exception:
        return {"last_run_date": None, "games_run_today": {}}


def save_state(state: Dict) -> None:
    """Salva estado de execução em JSON"""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def should_run_game(game_key: str, cfg: Dict, today: date, state: Dict) -> bool:
    """Verifica se o jogo deve rodar nesta execução

    - CS2: sempre roda (once_per_day=False)
    - LOL/RL/VAL: apenas 1x por dia (once_per_day=True)
    """
    if not cfg.get("once_per_day", False):
        return True

    last_run_date = state.get("last_run_date")
    games_run_today = state.get("games_run_today", {})

    if last_run_date != today.isoformat():
        return True

    return not games_run_today.get(game_key, False)


def mark_game_as_run(game_key: str, today: date, state: Dict) -> None:
    """Marca um jogo como executado hoje"""
    state["last_run_date"] = today.isoformat()
    state["games_run_today"][game_key] = True
    save_state(state)


# ================== DEDUPLICAÇÃO ==================
def extract_match_url_from_description(desc: str) -> str:
    """Extrai URL do match da descrição do evento"""
    if not desc:
        return ""
    for line in desc.splitlines():
        line = line.strip()
        if line.startswith(("http://", "https://")):
            return line
        if line.startswith("🌐"):
            return line.replace("🌐", "").strip()
    return ""


def extract_tournament_from_description(desc: str) -> str:
    """Extrai nome do torneio da descrição do evento"""
    if not desc:
        return ""
    for line in desc.splitlines():
        line = line.strip()
        if line.startswith("🏆"):
            return line.replace("🏆", "").strip()
    return ""


def event_key(component) -> Tuple[str, str, str, str]:
    """Cria chave única para deduplicação de eventos"""
    name = str(component.get('summary', '')).strip().lower()

    begin_iso = ""
    try:
        dt = component.get('dtstart').dt
        if isinstance(dt, datetime):
            begin_iso = normalize_event_datetime_utc(dt).isoformat()
    except Exception:
        pass

    desc = str(component.get('description', ''))
    tournament = extract_tournament_from_description(desc).lower()
    url = extract_match_url_from_description(desc).lower()

    return (name, begin_iso, tournament, url)


def dedupe_calendar_events(cal: Calendar) -> int:
    """Remove eventos duplicados, mantendo o com SOURCE_MARKER"""
    best_by_key: Dict = {}
    to_remove: List = []

    for component in list(cal.walk('VEVENT')):
        if not is_ours(component):
            continue

        k = event_key(component)
        if k not in best_by_key:
            best_by_key[k] = component
            continue

        current_best = best_by_key[k]
        cur_desc = str(current_best.get('description', ''))
        new_desc = str(component.get('description', ''))

        cur_has_marker = SOURCE_MARKER in cur_desc
        new_has_marker = SOURCE_MARKER in new_desc

        if new_has_marker and not cur_has_marker:
            to_remove.append(current_best)
            best_by_key[k] = component
        elif not new_has_marker or cur_has_marker:
            to_remove.append(component)

    for comp in to_remove:
        cal.subcomponents.remove(comp)

    return len(to_remove)


def dedupe_by_url_keep_latest(cal: Calendar) -> int:
    """Remove duplicatas por URL, mantendo a mais recente"""
    url_to_components: Dict = {}

    for component in list(cal.walk('VEVENT')):
        if not is_ours(component):
            continue

        desc = str(component.get('description', ''))
        url = extract_match_url_from_description(desc).strip().lower()

        if not url:
            continue

        url_to_components.setdefault(url, []).append(component)

    removed = 0
    for url, comps in url_to_components.items():
        if len(comps) <= 1:
            continue

        def score(comp):
            try:
                dt = comp.get('dtstart').dt
                b = normalize_event_datetime_utc(dt) if isinstance(dt, datetime) else UTC_TZ.localize(datetime.min)
            except Exception:
                b = UTC_TZ.localize(datetime.min)

            desc = str(comp.get('description', ''))
            has_marker = 1 if SOURCE_MARKER in desc else 0
            return (b, has_marker)

        keep = max(comps, key=score)

        for comp in comps:
            if comp is not keep:
                cal.subcomponents.remove(comp)
                removed += 1

    return removed


# ================== SCRAPING ==================
def fetch_page_scrape_do(url: str) -> str:
    """Busca página usando Scrape.do com renderização JavaScript"""
    log(f"  📡 GET {url}")

    if not SCRAPE_DO_API_KEY:
        log(f"  ⚠️ Scrape.do não configurado")
        return ""

    try:
        params = {
            "url": url,
            "token": SCRAPE_DO_API_KEY,
            "render": "true",
            "returnJSON": "true",
        }

        response = requests.get(SCRAPE_DO_URL, params=params, timeout=REQUEST_TIMEOUT)

        if response.status_code == 200:
            try:
                data = response.json()
                status_code = data.get("statusCode", 0)

                if status_code == 200:
                    content = data.get("content", "")
                    log(f"  ✅ Sucesso!")
                    return content
                else:
                    log(f"  ⚠️ Status {status_code}")
                    return ""
            except json.JSONDecodeError:
                log(f"  ⚠️ Erro ao decodificar JSON")
                return ""
        else:
            log(f"  ⚠️ Status HTTP {response.status_code}")
            return ""

    except Exception as e:
        log(f"  ❌ Erro: {str(e)[:80]}")
        return ""


def build_stable_uid(game_key: str, event_summary: str, match_time_utc: datetime,
                     tournament_desc: str, organizer_name: str, match_url: str) -> str:
    """Cria UID estável baseado no conteúdo do evento"""
    parts = f"{game_key}|{event_summary}|{match_time_utc.isoformat()}|{tournament_desc}|{organizer_name}|{match_url}"
    return hashlib.sha256(parts.encode()).hexdigest()


def match_url_absolute(rel_url: str) -> str:
    """Converte URL relativa para absoluta"""
    if not rel_url or rel_url.startswith("http"):
        return rel_url
    return f"https://tips.gg{rel_url if rel_url.startswith('/') else '/' + rel_url}"


def build_url_for_day(base_path: str, target_date: date) -> str:
    """Constrói URL para um dia específico no formato tips.gg"""
    date_str = target_date.strftime("%d-%m-%Y")
    return f"{base_path}{date_str}/"


def scrape_days_for_game(game_key: str, cfg: Dict, start_date: date,
                         num_days: int, existing_uids: Set[str]) -> Tuple[List[Event], Dict]:
    """Raspa eventos de um jogo para múltiplos dias"""
    prefix = cfg["prefix"]
    base_path = cfg["base_path"]
    teams_norm = cfg["teams_norm"]
    exclusions_norm = cfg["exclusions_norm"]

    stats = {
        "days_scraped": 0,
        "scripts_total": 0,
        "sports_events": 0,
        "skipped_tbd": 0,
        "skipped_past": 0,
        "skipped_not_allowed": 0,
        "added": 0,
    }

    new_events: List[Event] = []
    now_utc = datetime.now(UTC_TZ)

    for day_offset in range(num_days):
        target_date = start_date + timedelta(days=day_offset)
        url = build_url_for_day(base_path, target_date)
        html = fetch_page_scrape_do(url)

        if not html:
            continue

        stats["days_scraped"] += 1

        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception as e:
            log(f"      ❌ Erro ao parsear HTML: {e}")
            continue

        for script_tag in soup.find_all("script", {"type": "application/ld+json"}):
            stats["scripts_total"] += 1

            try:
                data = json.loads(script_tag.string)
            except json.JSONDecodeError:
                continue

            events = data.get("@graph", []) if isinstance(data, dict) else []

            for event_data in events:
                if not isinstance(event_data, dict) or event_data.get("@type") != "SportsEvent":
                    continue

                stats["sports_events"] += 1

                # Extrai dados
                start_date_str = event_data.get("startDate", "") or ""
                description = event_data.get("description", "") or ""
                organizer_name = (event_data.get("organizer") or {}).get("name", "Desconhecido")
                match_url = match_url_absolute(event_data.get("url", "") or "")

                competitors = event_data.get("competitor", []) or []
                if len(competitors) < 2:
                    continue

                team1_raw = competitors[0].get("name", "TBD")
                team2_raw = competitors[1].get("name", "TBD")

                if team1_raw == "TBD" or team2_raw == "TBD":
                    stats["skipped_tbd"] += 1
                    continue

                # Converte para datetime UTC
                try:
                    match_time_utc = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
                    if match_time_utc.tzinfo is None:
                        match_time_utc = UTC_TZ.localize(match_time_utc)
                    match_time_utc = match_time_utc.astimezone(UTC_TZ)
                except Exception:
                    continue

                if match_time_utc < now_utc:
                    stats["skipped_past"] += 1
                    continue

                # Verifica times
                t1 = normalize_team(team1_raw)
                t2 = normalize_team(team2_raw)

                allowed_t1 = t1 in teams_norm and t1 not in exclusions_norm
                allowed_t2 = t2 in teams_norm and t2 not in exclusions_norm

                if not (allowed_t1 or allowed_t2):
                    stats["skipped_not_allowed"] += 1
                    continue

                # Cria evento
                event_summary = f"{prefix}{team1_raw} vs {team2_raw}"
                event_uid = build_stable_uid(game_key, event_summary, match_time_utc,
                                            description, organizer_name, match_url)

                if event_uid in existing_uids:
                    continue

                event_description = (
                    f"🏆 {description}\n"
                    f"📍 {organizer_name}\n"
                    f"🌐 {match_url}\n"
                    f"{SOURCE_MARKER}"
                )

                e = Event()
                e.add('summary', event_summary)
                e.add('dtstart', normalize_event_datetime_utc(match_time_utc))
                e.add('dtend', normalize_event_datetime_utc(match_time_utc) + timedelta(hours=2))
                e.add('description', event_description)
                e.add('uid', event_uid)
                e.add('dtstamp', datetime.now(UTC_TZ))

                alarm = Alarm()
                alarm.add('action', 'DISPLAY')
                alarm.add('trigger', timedelta(minutes=-15))
                alarm.add('description', f'Lembrete: {event_summary}')
                e.add_component(alarm)

                new_events.append(e)
                existing_uids.add(event_uid)
                stats["added"] += 1
                log(f"      ✅ ADICIONADO: {event_summary}")

    return new_events, stats


# ================== EXECUÇÃO PRINCIPAL ==================
def main() -> None:
    """Função principal de execução"""
    log("🔄 Iniciando execução...")
    log("✅ Scrape.do configurado" if SCRAPE_DO_API_KEY else "⚠️ Scrape.do não configurado")

    # Carrega dados
    cal = load_calendar(CALENDAR_FILENAME)
    state = load_state()
    today = datetime.now(BR_TZ).date()

    # Deduplicação inicial
    deduped = dedupe_calendar_events(cal)
    if deduped:
        log(f"🧼 Deduplicação inicial: removidos {deduped} eventos duplicados.")

    deduped_url = dedupe_by_url_keep_latest(cal)
    if deduped_url:
        log(f"🧼 Dedup por URL (inicial): removidos {deduped_url} eventos.")

    existing_uids = get_existing_uids(cal)

    # Limpeza
    cutoff = today - timedelta(days=DELETE_OLDER_THAN_DAYS)
    removed = prune_older_than(cal, cutoff)
    log(f"🧹 Limpeza: removidos {removed} eventos com data < {cutoff.strftime('%d/%m/%Y')}")

    total_added = 0

    try:
        # Raspa cada jogo
        for game_key, cfg in GAMES.items():
            if not should_run_game(game_key, cfg, today, state):
                log(f"⏭️  {game_key} já foi executado hoje, pulando...")
                continue

            days_to_scrape = cfg.get("days_to_scrape", 1)
            log(f"🌐 Raspando {game_key} (próximos {days_to_scrape} dias)")

            new_events, stats = scrape_days_for_game(game_key, cfg, today, days_to_scrape, existing_uids)

            for ev in new_events:
                cal.add_component(ev)

            total_added += stats["added"]

            log(f"🧾 RESUMO {game_key}")
            log(f"  dias={stats['days_scraped']} scripts={stats['scripts_total']} sports={stats['sports_events']} added={stats['added']}")
            log(f"  skipped: tbd={stats['skipped_tbd']} past={stats['skipped_past']} not_allowed={stats['skipped_not_allowed']}")

            if cfg.get("once_per_day"):
                mark_game_as_run(game_key, today, state)

        # Deduplicação final
        deduped_final = dedupe_calendar_events(cal)
        if deduped_final:
            log(f"🧼 Deduplicação final: removidos {deduped_final} eventos.")

        deduped_url_final = dedupe_by_url_keep_latest(cal)
        if deduped_url_final:
            log(f"🧼 Dedup por URL (final): removidos {deduped_url_final} eventos.")

    except Exception as e:
        log(f"❌ Erro geral: {e}")
        import traceback
        log(f"📋 Traceback: {traceback.format_exc()}")

    # Salva
    log(f"💾 Salvando arquivo: {CALENDAR_FILENAME}")
    try:
        save_calendar(cal, CALENDAR_FILENAME)
        log(f"✅ Salvo. Total adicionados: {total_added}")
    except Exception as e:
        log(f"❌ Erro ao salvar: {e}")

    log("✅ Execução concluída!")


if __name__ == "__main__":
    main()
