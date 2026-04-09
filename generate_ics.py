import os
import json
import hashlib
import time
from datetime import datetime, timedelta, date

import pytz
from bs4 import BeautifulSoup
from icalendar import Calendar, Event, Alarm

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from webdriver_manager.chrome import ChromeDriverManager


# -------------------- Configurações Globais --------------------
CALENDAR_FILENAME = "calendar.ics"
STATE_FILE = "state.json"

BR_TZ = pytz.timezone("America/Sao_Paulo")

FUTURE_LIMIT_DAYS = 4
DELETE_OLDER_THAN_DAYS = 7

PAGE_LOAD_TIMEOUT_SECONDS = 20
JSONLD_WAIT_SECONDS = 15

SOURCE_MARKER = "X-SETT-SOURCE:TIPSGG"
TIPS_URL_HINT = "https://tips.gg/matches/"


# -------------------- Jogos / Times --------------------
def normalize_team(name: str) -> str:
    return (name or "").lower().strip()


GAMES = {
    "CS2": {
        "prefix": "[CS2] ",
        "base_path": "https://tips.gg/csgo/matches/",
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
        "teams": {"LOUD", "FURIA", "MIBR"},
        "exclusions": set(),
    },
    "RL": {
        "prefix": "[RL] ",
        "base_path": "https://tips.gg/rl/matches/",
        "teams": {"FURIA", "Team Secret"},
        "exclusions": set(),
    },
    "LOL": {
        "prefix": "[LOL] ",
        "base_path": "https://tips.gg/lol/matches/",
        "teams": {"paiN Gaming", "LOUD", "Vivo Keyd Stars", "RED Canids"},
        "exclusions": set(),
    },
}

for k, cfg in GAMES.items():
    cfg["teams_norm"] = {normalize_team(t) for t in cfg["teams"]}
    cfg["exclusions_norm"] = {normalize_team(t) for t in cfg["exclusions"]}


# -------------------- Helpers --------------------
def log(msg: str):
    now = datetime.now(BR_TZ).strftime("%H:%M:%S")
    print(f"[{now}] {msg}")


def build_url_for_day(base_path: str, target_date: date) -> str:
    return f"{base_path}{target_date.strftime('%d-%m-%Y')}/"


def match_url_absolute(url: str) -> str:
    if url.startswith("http"):
        return url
    return f"https://tips.gg{url}" if url.startswith("/") else url


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
    return dt.astimezone(pytz.utc).replace(microsecond=0, second=0)


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


# -------------------- Estado --------------------
def load_cursor(today: date, future_limit: date) -> date:
    if not os.path.exists(STATE_FILE):
        return today
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        d = date.fromisoformat(data.get("cursor_date", ""))
        if today <= d <= future_limit:
            return d
    except Exception:
        pass
    return today


def save_cursor(d: date):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"cursor_date": d.isoformat()}, f, ensure_ascii=False)


# -------------------- Deduplicação --------------------
def extract_match_url_from_description(desc: str) -> str:
    for line in (desc or "").splitlines():
        line = line.strip()
        if line.startswith("https://tips.gg/matches/"):
            return line
        if line.startswith("🌐"):
            return line.replace("🌐", "").strip()
    return ""


def event_key(component) -> tuple:
    name = str(component.get('summary', '')).strip().lower()
    begin_iso = ""
    try:
        dt = component.get('dtstart').dt
        if isinstance(dt, datetime):
            begin_iso = normalize_event_datetime_utc(dt).isoformat()
    except Exception:
        pass
    desc = str(component.get('description', ''))
    url = extract_match_url_from_description(desc)
    return (name, begin_iso, url)


def dedupe_calendar_events(cal: Calendar) -> int:
    seen = set()
    to_remove = []
    for component in cal.walk('VEVENT'):
        if not is_ours(component):
            continue
        key = event_key(component)
        if key in seen:
            to_remove.append(component)
        else:
            seen.add(key)
    for comp in to_remove:
        cal.subcomponents.remove(comp)
    return len(to_remove)


def dedupe_by_url_keep_latest(cal: Calendar) -> int:
    url_to_components: dict[str, list] = {}
    for component in cal.walk('VEVENT'):
        if not is_ours(component):
            continue
        desc = str(component.get('description', ''))
        url = extract_match_url_from_description(desc)
        if not url:
            continue
        url_to_components.setdefault(url, []).append(component)

    to_remove = []
    for url, comps in url_to_components.items():
        if len(comps) <= 1:
            continue
        def get_dtstamp(c):
            try:
                ds = c.get('dtstamp')
                if ds:
                    dt = ds.dt if hasattr(ds, 'dt') else ds
                    if isinstance(dt, datetime):
                        return dt
            except Exception:
                pass
            return datetime.min.replace(tzinfo=pytz.utc)
        comps_sorted = sorted(comps, key=get_dtstamp, reverse=True)
        to_remove.extend(comps_sorted[1:])

    for comp in to_remove:
        try:
            cal.subcomponents.remove(comp)
        except ValueError:
            pass
    return len(to_remove)


# -------------------- Selenium --------------------
def setup_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280,900")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT_SECONDS)
    return driver


# -------------------- UID --------------------
def build_stable_uid(game_key, summary, match_time_utc, tournament, organizer, match_url) -> str:
    raw = f"{game_key}|{summary}|{match_time_utc.isoformat()}|{tournament}|{organizer}|{match_url}"
    return hashlib.md5(raw.encode()).hexdigest() + "@tipsgg"


# -------------------- Parse JSON-LD --------------------
def parse_jsonld_scripts(soup: BeautifulSoup) -> list[dict]:
    events = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, dict) and data.get("@type") == "SportsEvent":
                events.append(data)
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("@type") == "SportsEvent":
                        events.append(item)
        except Exception:
            pass
    return events


def process_jsonld_events(
    events: list[dict],
    game_key: str,
    game_cfg: dict,
    existing_uids: set,
    now_utc: datetime,
    stats: dict,
) -> list[Event]:
    prefix = game_cfg["prefix"]
    teams_norm = game_cfg["teams_norm"]
    exclusions_norm = game_cfg["exclusions_norm"]
    new_events = []

    stats["sports_events"] += len(events)

    for event_data in events:
        start_date_str = event_data.get("startDate", "")
        if not start_date_str:
            stats["skipped_bad_date"] += 1
            continue

        description = event_data.get("description", "")
        organizer_name = (event_data.get("organizer") or {}).get("name", "")
        match_url = match_url_absolute(event_data.get("url", "") or "")

        competitors = event_data.get("competitor", []) or []
        if len(competitors) < 2:
            stats["skipped_no_competitors"] += 1
            continue

        team1_raw = competitors[0].get("name", "TBD")
        team2_raw = competitors[1].get("name", "TBD")

        if team1_raw == "TBD" or team2_raw == "TBD":
            stats["skipped_tbd"] += 1
            continue

        # Parse da data — o site usa -0300, fromisoformat lida bem com isso
        try:
            match_time = datetime.fromisoformat(start_date_str)
            if match_time.tzinfo is None:
                match_time = BR_TZ.localize(match_time)
            match_time_utc = match_time.astimezone(pytz.utc)
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
            summary=event_summary,
            match_time_utc=match_time_utc,
            tournament=description,
            organizer=organizer_name,
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

    return new_events


# -------------------- Scrape principal --------------------
def scrape_one_day_for_game(
    driver: webdriver.Chrome,
    game_key: str,
    game_cfg: dict,
    target_day: date,
    existing_uids: set,
) -> tuple[list[Event], dict]:
    stats = {
        "game": game_key,
        "date": target_day.strftime("%d/%m/%Y"),
        "scripts_total": 0,
        "sports_events": 0,
        "added": 0,
        "skipped_tbd": 0,
        "skipped_past": 0,
        "skipped_no_competitors": 0,
        "skipped_not_allowed": 0,
        "skipped_bad_date": 0,
        "json_decode_errors": 0,
        "timeouts_load": 0,
        "timeouts_jsonld": 0,
    }

    url = build_url_for_day(game_cfg["base_path"], target_day)

    try:
        driver.get(url)
    except TimeoutException:
        stats["timeouts_load"] += 1
        try:
            driver.execute_script("window.stop();")
        except Exception:
            pass

    # Aguarda qualquer JSON-LD de SportsEvent aparecer
    try:
        WebDriverWait(driver, JSONLD_WAIT_SECONDS).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, 'script[type="application/ld+json"]')
            )
        )
    except TimeoutException:
        stats["timeouts_jsonld"] += 1
        log(f"  ↳ Timeout aguardando JSON-LD em {game_key}")

    soup = BeautifulSoup(driver.page_source, "html.parser")
    now_utc = datetime.now(pytz.utc)

    all_scripts = soup.find_all("script", type="application/ld+json")
    stats["scripts_total"] = len(all_scripts)

    jsonld_events = parse_jsonld_scripts(soup)

    if jsonld_events:
        log(f"  ↳ JSON-LD: {len(jsonld_events)} eventos encontrados")
        new_events = process_jsonld_events(
            jsonld_events, game_key, game_cfg, existing_uids, now_utc, stats
        )
    else:
        log(f"  ↳ Nenhum JSON-LD de SportsEvent encontrado")
        new_events = []

    return new_events, stats


# -------------------- Execução --------------------
log("🔄 Iniciando execução (cursor rotativo)...")

cal = load_calendar(CALENDAR_FILENAME)

deduped_initial = dedupe_calendar_events(cal)
if deduped_initial:
    log(f"🧼 Deduplicação inicial: removidos {deduped_initial} eventos duplicados.")

deduped_by_url_initial = dedupe_by_url_keep_latest(cal)
if deduped_by_url_initial:
    log(f"🧼 Dedup por URL (inicial): removidos {deduped_by_url_initial} eventos.")

existing_uids = get_existing_uids(cal)

today = datetime.now(BR_TZ).date()
future_limit = today + timedelta(days=FUTURE_LIMIT_DAYS)

cutoff = today - timedelta(days=DELETE_OLDER_THAN_DAYS)
removed = prune_older_than(cal, cutoff)
log(f"🧹 Limpeza: removidos {removed} eventos com data < {cutoff.strftime('%d/%m/%Y')}")

target_day = today
log(f"📌 Cursor atual: {target_day.strftime('%d/%m/%Y')} "
    f"(range: {today.strftime('%d/%m/%Y')}..{future_limit.strftime('%d/%m/%Y')})")

driver = None
total_added = 0
ran_ok = False

try:
    driver = setup_driver()
    log("⚙️ Selenium iniciado.")

    for game_key, cfg in GAMES.items():
        url = build_url_for_day(cfg["base_path"], target_day)
        log(f"🌐 Raspando {game_key} em {target_day.strftime('%d/%m/%Y')} -> {url}")

        new_events, stats = scrape_one_day_for_game(
            driver, game_key, cfg, target_day, existing_uids
        )

        for ev in new_events:
            cal.add_component(ev)

        total_added += stats["added"]

        log(f"🧾 RESUMO {game_key} - {stats['date']}")
        log(f"  scripts={stats['scripts_total']} sports={stats['sports_events']} added={stats['added']}")
        log(f"  skipped: tbd={stats['skipped_tbd']} past={stats['skipped_past']} "
            f"not_allowed={stats['skipped_not_allowed']} bad_date={stats['skipped_bad_date']}")
        log(f"  timeouts: load={stats['timeouts_load']} jsonld={stats['timeouts_jsonld']} "
            f"json_err={stats['json_decode_errors']}")

        time.sleep(2)

    deduped_final = dedupe_calendar_events(cal)
    if deduped_final:
        log(f"🧼 Deduplicação final: removidos {deduped_final} eventos duplicados.")

    deduped_by_url_final = dedupe_by_url_keep_latest(cal)
    if deduped_by_url_final:
        log(f"🧼 Dedup por URL (final): removidos {deduped_by_url_final} eventos.")

    existing_uids = get_existing_uids(cal)
    ran_ok = True

except WebDriverException as e:
    log(f"❌ WebDriverException: {e}")
except Exception as e:
    log(f"❌ Erro geral: {e}")
finally:
    if driver:
        try:
            driver.quit()
        except Exception:
            pass
        log("⚙️ Selenium fechado.")

log(f"💾 Salvando arquivo: {CALENDAR_FILENAME}")
try:
    save_calendar(cal, CALENDAR_FILENAME)
    log(f"✅ Salvo. Total adicionados nesta execução: {total_added}")
except Exception as e:
    log(f"❌ Erro ao salvar {CALENDAR_FILENAME}: {e}")

if ran_ok:
    next_day = target_day + timedelta(days=1)
    if next_day > future_limit:
        next_day = today
    save_cursor(next_day)
    log(f"🔁 Cursor atualizado: próximo alvo {next_day.strftime('%d/%m/%Y')}")
else:
    log("⏸️ Cursor NÃO avançou porque a execução falhou.")
