import os
import json
import hashlib
import time
from datetime import datetime, timedelta, date

import pytz
from bs4 import BeautifulSoup
from icalendar import Calendar, Event, Alarm
import requests


# -------------------- Configurações Globais --------------------
CALENDAR_FILENAME = "calendar.ics"
STATE_FILE = "state.json"

BR_TZ = pytz.timezone("America/Sao_Paulo")

DELETE_OLDER_THAN_DAYS = 7

SOURCE_MARKER = "X-SETT-SOURCE:TIPSGG"
TIPS_URL_HINT = "https://tips.gg/matches/"

# Scrape.do API
SCRAPE_DO_API_KEY = os.getenv("SCRAPE_DO_API_KEY", "")
SCRAPE_DO_URL = "https://api.scrape.do"


# -------------------- Jogos / Times --------------------
def normalize_team(name: str) -> str:
    return (name or "").lower().strip()


GAMES = {
    "CS2": {
        "prefix": "[CS2] ",
        "base_path": "https://tips.gg/csgo/matches/",
        "days_to_scrape": 1,
        "once_per_day": False,
        "teams": {"FURIA", "paiN Gaming", "MIBR", "Imperial", "Fluxo", "RED Canids", "Legacy", "ODDIK", "Imperial Esports", "Gaimin Gladiators"},
        "exclusions": {
            "Imperial.A", "Imperial Fe", "MIBR.A", "paiN.A", "ODDIK.A",
            "Imperial Academy", "Imperial.Acd", "Imperial Female",
            "Furia Academy", "Furia.A", "Pain Academy", "Mibr Academy", "Legacy Academy", "ODDIK Academy",
            "RED Canids Academy", "Fluxo Academy"
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

# Pre-normaliza
for k, cfg in GAMES.items():
    cfg["teams_norm"] = {normalize_team(t) for t in cfg["teams"]}
    cfg["exclusions_norm"] = {normalize_team(t) for t in cfg["exclusions"]}


# -------------------- Helpers --------------------
def log(msg: str):
    now = datetime.now(BR_TZ).strftime("%H:%M:%S")
    print(f"[{now}] {msg}")


def build_url_for_day(base_path: str, target_date: date) -> str:
    date_str = target_date.strftime("%d-%m-%Y")
    return f"{base_path}{date_str}/"


def load_calendar(path: str) -> Calendar:
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


def save_calendar(cal: Calendar, path: str):
    with open(path, "wb") as f:
        f.write(cal.to_ical())


def get_existing_uids(cal: Calendar) -> set:
    uids = set()
    for component in cal.walk('VEVENT'):
        uid = component.get('uid')
        if uid:
            uids.add(str(uid))
    return uids


def normalize_event_datetime_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    dt = dt.astimezone(pytz.utc).replace(microsecond=0, second=0)
    return dt


def is_ours(component) -> bool:
    desc = str(component.get('description', ''))
    return (SOURCE_MARKER in desc) or (TIPS_URL_HINT in desc)


def event_start_date_local(component) -> date | None:
    try:
        dt = component.get('dtstart').dt
        if isinstance(dt, datetime):
            if dt.tzinfo is None:
                dt = pytz.utc.localize(dt)
            return dt.astimezone(BR_TZ).date()
        elif isinstance(dt, date):
            return dt
    except Exception:
        pass
    return None


def prune_older_than(cal: Calendar, cutoff_date: date) -> int:
    to_remove = []
    for component in cal.walk('VEVENT'):
        if not is_ours(component):
            continue
        d = event_start_date_local(component)
        if d and d < cutoff_date:
            to_remove.append(component)

    for comp in to_remove:
        cal.subcomponents.remove(comp)

    return len(to_remove)


# -------------------- Estado (Controle de execução diária) --------------------
def load_state() -> dict:
    """Carrega estado de execução"""
    if not os.path.exists(STATE_FILE):
        return {
            "last_run_date": None,
            "games_run_today": {}
        }

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
            # Garante que games_run_today existe
            if "games_run_today" not in state:
                state["games_run_today"] = {}
            return state
    except Exception:
        return {
            "last_run_date": None,
            "games_run_today": {}
        }


def save_state(state: dict):
    """Salva estado de execução"""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def should_run_game(game_key: str, cfg: dict, today: date, state: dict) -> bool:
    """Verifica se o jogo deve rodar hoje"""

    # CS2 sempre roda
    if not cfg.get("once_per_day", False):
        return True

    # Para LOL, RL, VAL: verifica se já rodou hoje
    last_run_date = state.get("last_run_date")
    games_run_today = state.get("games_run_today", {})

    # Se a data mudou, reseta o controle
    if last_run_date != today.isoformat():
        return True

    # Se já rodou hoje, não roda novamente
    if games_run_today.get(game_key, False):
        return False

    return True


def mark_game_as_run(game_key: str, today: date, state: dict):
    """Marca jogo como executado hoje"""
    state["last_run_date"] = today.isoformat()

    # Garante que games_run_today existe
    if "games_run_today" not in state:
        state["games_run_today"] = {}

    state["games_run_today"][game_key] = True
    save_state(state)


# -------------------- Deduplicação --------------------
def extract_match_url_from_description(desc: str) -> str:
    if not desc:
        return ""
    for line in desc.splitlines():
        line = line.strip()
        if line.startswith("http://") or line.startswith("https://"):
            return line
        if line.startswith("🌐"):
            return line.replace("🌐", "").strip()
    return ""


def extract_tournament_from_description(desc: str) -> str:
    if not desc:
        return ""
    for line in desc.splitlines():
        line = line.strip()
        if line.startswith("🏆"):
            return line.replace("🏆", "").strip()
    return ""


def event_key(component) -> tuple:
    name = str(component.get('summary', '')).strip().lower()

    begin_iso = ""
    try:
        dt = component.get('dtstart').dt
        if isinstance(dt, datetime):
            dtd = normalize_event_datetime_utc(dt)
            begin_iso = dtd.isoformat()
    except Exception:
        pass

    desc = str(component.get('description', ''))
    tournament = extract_tournament_from_description(desc).lower()
    url = extract_match_url_from_description(desc).lower()

    return (name, begin_iso, tournament, url)


def dedupe_calendar_events(cal: Calendar) -> int:
    best_by_key = {}
    to_remove = []

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
        else:
            to_remove.append(component)

    for comp in to_remove:
        cal.subcomponents.remove(comp)

    return len(to_remove)


def dedupe_by_url_keep_latest(cal: Calendar) -> int:
    groups = {}
    removed = 0

    for component in list(cal.walk('VEVENT')):
        if not is_ours(component):
            continue

        desc = str(component.get('description', ''))
        url = extract_match_url_from_description(desc).strip().lower()

        if not url:
            continue

        groups.setdefault(url, []).append(component)

    for url, comps in groups.items():
        if len(comps) <= 1:
            continue

        def score(comp):
            try:
                dt = comp.get('dtstart').dt
                if isinstance(dt, datetime):
                    b = normalize_event_datetime_utc(dt)
                else:
                    b = pytz.utc.localize(datetime.min)
            except Exception:
                b = pytz.utc.localize(datetime.min)

            desc = str(comp.get('description', ''))
            has_marker = 1 if SOURCE_MARKER in desc else 0
            return (b, has_marker)

        keep = max(comps, key=score)

        for comp in comps:
            if comp is keep:
                continue
            cal.subcomponents.remove(comp)
            removed += 1

    return removed


# -------------------- HTTP com Scrape.do --------------------
def fetch_page_scrape_do(url: str) -> str:
    """Usa Scrape.do para contornar Cloudflare"""
    log(f"  📡 GET {url}")

    if not SCRAPE_DO_API_KEY:
        log(f"  ⚠️ Scrape.do não configurado")
        return ""

    try:
        params = {
            "apikey": SCRAPE_DO_API_KEY,
            "url": url,
            "render": "true",
        }

        response = requests.get(SCRAPE_DO_URL, params=params, timeout=30)

        if response.status_code == 200:
            log(f"  ✅ Sucesso!")
            return response.text
        else:
            log(f"  ⚠️ Status {response.status_code}")
            return ""

    except Exception as e:
        log(f"  ❌ Erro: {str(e)[:80]}")
        return ""


def build_stable_uid(
    game_key: str,
    event_summary: str,
    match_time_utc: datetime,
    tournament_desc: str,
    organizer_name: str,
    match_url: str,
) -> str:
    parts = f"{game_key}|{event_summary}|{match_time_utc.isoformat()}|{tournament_desc}|{organizer_name}|{match_url}"
    return hashlib.sha256(parts.encode()).hexdigest()


def match_url_absolute(rel_url: str) -> str:
    if not rel_url:
        return ""
    if rel_url.startswith("http"):
        return rel_url
    if rel_url.startswith("/"):
        return f"https://tips.gg{rel_url}"
    return f"https://tips.gg/{rel_url}"


def scrape_days_for_game(game_key: str, cfg: dict, start_date: date, num_days: int, existing_uids: set) -> tuple:
    prefix = cfg["prefix"]
    base_path = cfg["base_path"]
    teams_norm = cfg["teams_norm"]
    exclusions_norm = cfg["exclusions_norm"]

    stats = {
        "game": game_key,
        "days_scraped": 0,
        "scripts_total": 0,
        "sports_events": 0,
        "skipped_tbd": 0,
        "skipped_past": 0,
        "skipped_not_allowed": 0,
        "skipped_bad_date": 0,
        "json_decode_errors": 0,
        "added": 0,
    }

    new_events = []
    now_utc = datetime.now(pytz.utc)

    # Raspa múltiplos dias
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
                stats["json_decode_errors"] += 1
                continue

            events = data.get("@graph", []) if isinstance(data, dict) else []

            for event_data in events:
                if not isinstance(event_data, dict):
                    continue

                if event_data.get("@type") != "SportsEvent":
                    continue

                stats["sports_events"] += 1

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

                try:
                    match_time_utc = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
                    if match_time_utc.tzinfo is None:
                        match_time_utc = pytz.utc.localize(match_time_utc)
                    match_time_utc = match_time_utc.astimezone(pytz.utc)
                except Exception:
                    stats["skipped_bad_date"] += 1
                    continue

                if match_time_utc < now_utc:
                    stats["skipped_past"] += 1
                    continue

                t1 = normalize_team(team1_raw)
                t2 = normalize_team(team2_raw)

                allowed_t1 = (t1 in teams_norm) and (t1 not in exclusions_norm)
                allowed_t2 = (t2 in teams_norm) and (t2 not in exclusions_norm)

                if not (allowed_t1 or allowed_t2):
                    stats["skipped_not_allowed"] += 1
                    continue

                event_summary = f"{prefix}{team1_raw} vs {team2_raw}"

                event_uid = build_stable_uid(
                    game_key=game_key,
                    event_summary=event_summary,
                    match_time_utc=match_time_utc,
                    tournament_desc=description,
                    organizer_name=organizer_name,
                    match_url=match_url,
                )

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
                e.add('dtstamp', datetime.now(pytz.utc))

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


# -------------------- Execução --------------------
log("🔄 Iniciando execução...")

if SCRAPE_DO_API_KEY:
    log("✅ Scrape.do configurado")
else:
    log("⚠️ Scrape.do não configurado")

cal = load_calendar(CALENDAR_FILENAME)
state = load_state()
today = datetime.now(BR_TZ).date()

deduped_initial = dedupe_calendar_events(cal)
if deduped_initial:
    log(f"🧼 Deduplicação inicial: removidos {deduped_initial} eventos duplicados.")

deduped_by_url_initial = dedupe_by_url_keep_latest(cal)
if deduped_by_url_initial:
    log(f"🧼 Dedup por URL (inicial): removidos {deduped_by_url_initial} eventos.")

existing_uids = get_existing_uids(cal)

cutoff = today - timedelta(days=DELETE_OLDER_THAN_DAYS)
removed = prune_older_than(cal, cutoff)
log(f"🧹 Limpeza: removidos {removed} eventos com data < {cutoff.strftime('%d/%m/%Y')}")

total_added = 0
ran_ok = False

try:
    for game_key, cfg in GAMES.items():
        # Verifica se deve rodar este jogo
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

        # Marca como executado (para LOL, RL, VAL)
        if cfg.get("once_per_day", False):
            mark_game_as_run(game_key, today, state)

    deduped_final = dedupe_calendar_events(cal)
    if deduped_final:
        log(f"🧼 Deduplicação final: removidos {deduped_final} eventos.")

    deduped_by_url_final = dedupe_by_url_keep_latest(cal)
    if deduped_by_url_final:
        log(f"🧼 Dedup por URL (final): removidos {deduped_by_url_final} eventos.")

    existing_uids = get_existing_uids(cal)
    ran_ok = True

except Exception as e:
    log(f"❌ Erro geral: {e}")
    import traceback
    log(f"📋 Traceback: {traceback.format_exc()}")

log(f"💾 Salvando arquivo: {CALENDAR_FILENAME}")
try:
    save_calendar(cal, CALENDAR_FILENAME)
    log(f"✅ Salvo. Total adicionados: {total_added}")
except Exception as e:
    log(f"❌ Erro ao salvar: {e}")

log("✅ Execução concluída!")
