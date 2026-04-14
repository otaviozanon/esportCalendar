import os
import json
import hashlib
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
def normalize_team(name: str) -&gt; str:
    return (name or "").lower().strip()


GAMES = {
    "CS2": {
        "prefix": "[CS2] ",
        "base_path": "https://tips.gg/csgo/matches/",
        "days_to_scrape": 3,
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
        "run_at_hour": 0,
        "teams": {"LOUD", "FURIA", "MIBR"},
        "exclusions": set(),
    },
    "RL": {
        "prefix": "[RL] ",
        "base_path": "https://tips.gg/rl/matches/",
        "days_to_scrape": 1,
        "once_per_day": True,
        "run_at_hour": 0,
        "teams": {"FURIA", "Team Secret"},
        "exclusions": set(),
    },
    "LOL": {
        "prefix": "[LOL] ",
        "base_path": "https://tips.gg/lol/matches/",
        "days_to_scrape": 1,
        "once_per_day": True,
        "run_at_hour": 0,
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


def build_url_for_day(base_path: str, target_date: date) -&gt; str:
    date_str = target_date.strftime("%d-%m-%Y")
    return f"{base_path}{date_str}/"


def load_calendar(path: str) -&gt; Calendar:
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


def get_existing_uids(cal: Calendar) -&gt; set:
    uids = set()
    for component in cal.walk('VEVENT'):
        uid = component.get('uid')
        if uid:
            uids.add(str(uid))
    return uids


def normalize_event_datetime_utc(dt: datetime) -&gt; datetime:
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    dt = dt.astimezone(pytz.utc).replace(microsecond=0, second=0)
    return dt


def is_ours(component) -&gt; bool:
    desc = str(component.get('description', ''))
    return (SOURCE_MARKER in desc) or (TIPS_URL_HINT in desc)


def event_start_date_local(component) -&gt; date | None:
    try:
        dt = component.get('dtstart').dt
        if isinstance(dt, datetime):
            if dt.tzinfo is None:
                dt = pytz.utc.localize(dt)
            return dt.astimezone(BR_TZ).date()
        elif isinstance(dt, date):
            return dt
    except:
        pass
    return None


def prune_older_than(cal: Calendar, cutoff_date: date) -&gt; int:
    to_remove = []
    for component in list(cal.walk('VEVENT')):
        if not is_ours(component):
            continue
        event_date = event_start_date_local(component)
        if event_date and event_date &lt; cutoff_date:
            to_remove.append(component)
    for comp in to_remove:
        cal.subcomponents.remove(comp)
    return len(to_remove)


def load_state() -&gt; dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"games_run_today": {}, "cs2_day_offset": 0}


def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def should_run_game(game_key: str, cfg: dict, now: datetime, state: dict) -&gt; bool:
    """Verifica se o jogo deve rodar agora"""

    # CS2 sempre roda
    if game_key == "CS2":
        return True

    # VAL, LOL, RL: rodam apenas se chegou a hora
    run_at_hour = cfg.get("run_at_hour", 0)
    today = now.date()

    games_run = state.get("games_run_today", {})
    last_run = games_run.get(game_key)

    # Se já rodou hoje, não roda de novo
    if last_run:
        try:
            last_run_date = datetime.fromisoformat(last_run).date()
            if last_run_date == today:
                return False
        except:
            pass

    # Se ainda não chegou a hora, não roda
    if now.hour &lt; run_at_hour:
        return False

    return True


def mark_game_as_run(game_key: str, state: dict):
    if "games_run_today" not in state:
        state["games_run_today"] = {}
    state["games_run_today"][game_key] = datetime.now(BR_TZ).isoformat()
    save_state(state)


def get_cs2_target_days(today: date, state: dict) -&gt; list:
    """Retorna lista com o dia alvo do CS2 baseado no offset"""
    offset = state.get("cs2_day_offset", 0)
    target_day = today + timedelta(days=offset)
    return [target_day]


def advance_cs2_offset(state: dict):
    """Avança o offset do CS2 (0 -&gt; 1 -&gt; 2 -&gt; 3 -&gt; 0)"""
    offset = state.get("cs2_day_offset", 0)
    state["cs2_day_offset"] = (offset + 1) % 4
    save_state(state)


def dedupe_calendar_events(cal: Calendar) -&gt; int:
    """Remove eventos duplicados (mesmo UID)"""
    seen_uids = set()
    to_remove = []

    for component in list(cal.walk('VEVENT')):
        if not is_ours(component):
            continue
        uid = str(component.get('uid', ''))
        if uid in seen_uids:
            to_remove.append(component)
        else:
            seen_uids.add(uid)

    for comp in to_remove:
        cal.subcomponents.remove(comp)

    return len(to_remove)


def dedupe_by_url_keep_latest(cal: Calendar) -&gt; int:
    """Remove eventos com mesma URL, mantendo o mais recente"""
    url_map = {}

    for component in list(cal.walk('VEVENT')):
        if not is_ours(component):
            continue

        desc = str(component.get('description', ''))
        url = None
        for line in desc.split('\n'):
            if line.startswith('🌐 '):
                url = line.replace('🌐 ', '').strip()
                break

        if not url:
            continue

        if url not in url_map:
            url_map[url] = component
        else:
            existing = url_map[url]
            existing_time = existing.get('dtstart').dt
            new_time = component.get('dtstart').dt

            if new_time &gt; existing_time:
                url_map[url] = component

    to_remove = []
    for component in list(cal.walk('VEVENT')):
        if not is_ours(component):
            continue

        desc = str(component.get('description', ''))
        url = None
        for line in desc.split('\n'):
            if line.startswith('🌐 '):
                url = line.replace('🌐 ', '').strip()
                break

        if url and url_map.get(url) != component:
            to_remove.append(component)

    for comp in to_remove:
        cal.subcomponents.remove(comp)

    return len(to_remove)


def build_stable_uid(game_key: str, event_summary: str, match_time_utc: datetime, tournament_desc: str, organizer_name: str, match_url: str) -&gt; str:
    """Cria UID estável baseado em dados do evento"""
    data = f"{game_key}|{event_summary}|{match_time_utc.isoformat()}|{tournament_desc}|{organizer_name}|{match_url}"
    hash_obj = hashlib.sha256(data.encode())
    return f"{hash_obj.hexdigest()}@tips.gg"


def fetch_page_scrape_do(url: str) -> str:
    """Busca página usando Scrape.do"""
    if not SCRAPE_DO_API_KEY:
        log(f"  ⚠️ Scrape.do não configurado")
        return ""

    try:
        params = {
            "apikey": SCRAPE_DO_API_KEY,
            "url": url,
            "render": "false"
        }

        response = requests.get(SCRAPE_DO_URL, params=params, timeout=30)
        response.raise_for_status()

        return response.text

    except Exception as e:
        log(f"  ❌ Erro Scrape.do: {str(e)[:100]}")
        return ""


def scrape_days_for_game(game_key: str, cfg: dict, today: date, target_days: list, existing_uids: set) -&gt; tuple:
    """Raspa múltiplos dias para um jogo"""
    new_events = []
    total_stats = {
        "days_scraped": 0,
        "scripts_total": 0,
        "sports_events": 0,
        "added": 0,
        "skipped_tbd": 0,
        "skipped_past": 0,
        "skipped_not_allowed": 0,
    }

    prefix = cfg.get("prefix", "")
    base_path = cfg.get("base_path", "")
    teams_norm = cfg.get("teams_norm", set())
    exclusions_norm = cfg.get("exclusions_norm", set())

    for target_day in target_days:
        url = build_url_for_day(base_path, target_day)
        html = fetch_page_scrape_do(url)

        if not html:
            log(f"  ⚠️ Falha ao buscar {target_day.strftime('%d/%m/%Y')}")
            continue

        soup = BeautifulSoup(html, 'html.parser')
        scripts = soup.find_all('script', {'type': 'application/ld+json'})

        total_stats["days_scraped"] += 1
        total_stats["scripts_total"] += len(scripts)

        now_utc = datetime.now(pytz.utc)

        for script in scripts:
            try:
                data = json.loads(script.string)
            except json.JSONDecodeError:
                continue

            if not isinstance(data, dict):
                continue

            events = data.get("@graph", [])
            if not events:
                events = [data]

            total_stats["sports_events"] += len(events)

            for event in events:
                try:
                    if event.get("@type") != "SportsEvent":
                        continue

                    team1_raw = event.get("competitor", [{}])[0].get("name", "")
                    team2_raw = event.get("competitor", [{}])[1].get("name", "") if len(event.get("competitor", [])) &gt; 1 else ""

                    if not team1_raw or not team2_raw:
                        continue

                    description = event.get("name", "")
                    organizer_name = event.get("organizer", {}).get("name", "")

                    if "TBD" in team1_raw or "TBD" in team2_raw:
                        total_stats["skipped_tbd"] += 1
                        continue

                    match_url = event.get("url", "")

                    try:
                        match_time_str = event.get("startDate", "")
                        match_time_utc = datetime.fromisoformat(match_time_str.replace("Z", "+00:00"))
                        if match_time_utc.tzinfo is None:
                            match_time_utc = pytz.utc.localize(match_time_utc)
                        match_time_utc = match_time_utc.astimezone(pytz.utc)
                    except Exception:
                        continue

                    if match_time_utc &lt; now_utc:
                        total_stats["skipped_past"] += 1
                        continue

                    t1 = normalize_team(team1_raw)
                    t2 = normalize_team(team2_raw)

                    allowed_t1 = (t1 in teams_norm) and (t1 not in exclusions_norm)
                    allowed_t2 = (t2 in teams_norm) and (t2 not in exclusions_norm)

                    if not (allowed_t1 or allowed_t2):
                        total_stats["skipped_not_allowed"] += 1
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
                    total_stats["added"] += 1
                    log(f"      ✅ ADICIONADO: {event_summary}")

                except Exception:
                    continue

    return new_events, total_stats


# -------------------- Execução --------------------
log("🔄 Iniciando execução...")

if SCRAPE_DO_API_KEY:
    log("✅ Scrape.do configurado")
else:
    log("⚠️ Scrape.do não configurado")

cal = load_calendar(CALENDAR_FILENAME)
state = load_state()
now = datetime.now(BR_TZ)
today = now.date()

deduped_initial = dedupe_calendar_events(cal)
if deduped_initial:
    log(f"🧼 Deduplicação inicial: removidos {deduped_initial} eventos duplicados.")

deduped_by_url_initial = dedupe_by_url_keep_latest(cal)
if deduped_by_url_initial:
    log(f"🧼 Dedup por URL (inicial): removidos {deduped_by_url_initial} eventos.")

existing_uids = get_existing_uids(cal)

cutoff = today - timedelta(days=DELETE_OLDER_THAN_DAYS)
removed = prune_older_than(cal, cutoff)
log(f"🧹 Limpeza: removidos {removed} eventos com data &lt; {cutoff.strftime('%d/%m/%Y')}")

total_added = 0

try:
    for game_key, cfg in GAMES.items():
        if not should_run_game(game_key, cfg, now, state):
            run_at = cfg.get("run_at_hour", 0)
            log(f"⏭️  {game_key} aguardando {run_at:02d}:00 (agora são {now.hour:02d}:{now.minute:02d})")
            continue

        if game_key == "CS2":
            target_days = [today]
            log(f"🌐 Raspando {game_key} (offset={state.get('cs2_day_offset', 0)}) -&gt; {target_days[0].strftime('%d/%m/%Y')}")
        else:
            target_days = [today]
            log(f"🌐 Raspando {game_key} (dia atual) -&gt; {today.strftime('%d/%m/%Y')}")

        new_events, stats = scrape_days_for_game(game_key, cfg, today, target_days, existing_uids)

        for ev in new_events:
            cal.add_component(ev)

        total_added += stats["added"]

        log(f"🧾 RESUMO {game_key}")
        log(f"  dias={stats['days_scraped']} scripts={stats['scripts_total']} sports={stats['sports_events']} added={stats['added']}")
        log(f"  skipped: tbd={stats['skipped_tbd']} past={stats['skipped_past']} not_allowed={stats['skipped_not_allowed']}")

        if cfg.get("once_per_day", False):
            mark_game_as_run(game_key, state)

        if game_key == "CS2":
            advance_cs2_offset(state)

    deduped_final = dedupe_calendar_events(cal)
    if deduped_final:
        log(f"🧼 Deduplicação final: removidos {deduped_final} eventos.")

    deduped_by_url_final = dedupe_by_url_keep_latest(cal)
    if deduped_by_url_final:
        log(f"🧼 Dedup por URL (final): removidos {deduped_by_url_final} eventos.")

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

consegue arrumar para mim? Lmebrando que só funciona utilizando a proxy!
