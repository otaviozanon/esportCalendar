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
MATCH_WAIT_SECONDS = 12

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
            begin_iso = normalize_event_datetime_utc(dt).isoformat()
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
        cur_has_marker = SOURCE_MARKER in str(current_best.get('description', ''))
        new_has_marker = SOURCE_MARKER in str(component.get('description', ''))
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
                b = normalize_event_datetime_utc(dt) if isinstance(dt, datetime) else pytz.utc.localize(datetime.min)
            except Exception:
                b = pytz.utc.localize(datetime.min)
            has_marker = 1 if SOURCE_MARKER in str(comp.get('description', '')) else 0
            return (b, has_marker)

        keep = max(comps, key=score)
        for comp in comps:
            if comp is keep:
                continue
            cal.subcomponents.remove(comp)
            removed += 1
    return removed


# -------------------- Selenium --------------------
def setup_driver() -> webdriver.Chrome:
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT_SECONDS)
    return driver


# -------------------- Build de eventos --------------------
def build_stable_uid(
    game_key: str,
    event_summary: str,
    match_time_utc: datetime,
    tournament_desc: str,
    organizer_name: str,
    match_url: str,
) -> str:
    dt_norm = normalize_event_datetime_utc(match_time_utc)
    payload = "|".join([
        (game_key or "").strip().lower(),
        (event_summary or "").strip().lower(),
        dt_norm.isoformat(),
        (tournament_desc or "").strip().lower(),
        (organizer_name or "").strip().lower(),
        (match_url or "").strip().lower(),
    ])
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def match_url_absolute(match_url: str) -> str:
    match_url = match_url or ""
    if match_url and not match_url.startswith("http"):
        return f"https://tips.gg{match_url}"
    return match_url


def build_event(
    game_key: str,
    prefix: str,
    team1_raw: str,
    team2_raw: str,
    match_time_utc: datetime,
    description: str,
    organizer_name: str,
    match_url: str,
    existing_uids: set,
) -> Event | None:
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
        return None

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

    existing_uids.add(event_uid)
    return e


# -------------------- soup_has_sports_events --------------------
def soup_has_sports_events(soup: BeautifulSoup) -> bool:
    for script in soup.find_all("script", type="application/ld+json"):
        raw = (script.string or "").strip()
        try:
            d = json.loads(raw)
            if d.get("@type") == "SportsEvent":
                return True
        except Exception:
            pass
    return False


# -------------------- Parse JSON-LD --------------------
def parse_jsonld(
    soup: BeautifulSoup,
    game_key: str,
    game_cfg: dict,
    existing_uids: set,
    now_utc: datetime,
    stats: dict,
) -> list[Event]:
    scripts = soup.find_all("script", type="application/ld+json")
    stats["scripts_total"] = len(scripts)
    new_events = []

    teams_norm = game_cfg["teams_norm"]
    exclusions_norm = game_cfg["exclusions_norm"]
    prefix = game_cfg["prefix"]

    for script in scripts:
        raw = (script.string or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            stats["json_decode_errors"] += 1
            continue

        if data.get("@type") != "SportsEvent":
            continue

        stats["sports_events"] += 1

        start_date_str = data.get("startDate", "") or ""
        description = data.get("description", "") or ""
        organizer_name = (data.get("organizer") or {}).get("name", "Desconhecido")
        match_url = match_url_absolute(data.get("url", "") or "")

        competitors = data.get("competitor", []) or []
        if len(competitors) < 2:
            stats["skipped_no_competitors"] += 1
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

        ev = build_event(
            game_key, prefix, team1_raw, team2_raw,
            match_time_utc, description, organizer_name, match_url,
            existing_uids,
        )
        if ev:
            new_events.append(ev)
            stats["added"] += 1

    return new_events


# -------------------- Parse DOM --------------------
def parse_dom(
    soup: BeautifulSoup,
    game_key: str,
    game_cfg: dict,
    existing_uids: set,
    now_utc: datetime,
    target_day: date,
    stats: dict,
) -> list[Event]:
    """
    Fallback para quando não há JSON-LD.
    Estrutura atual do tips.gg:
      - times:   .team .name
      - horário: .time  (ex: "04:00") — exibido em UTC pelo servidor
      - link:    a.match-link[href]   (ex: /matches/counter-strike/09-04-2026/mibr-vs-3dmax/08-00/)
    """
    match_elements = soup.select('.element.match')
    stats["dom_matches_found"] = len(match_elements)
    new_events = []

    teams_norm = game_cfg["teams_norm"]
    exclusions_norm = game_cfg["exclusions_norm"]
    prefix = game_cfg["prefix"]

    for el in match_elements:
        team_tags = el.select('.team .name')
        if len(team_tags) < 2:
            stats["skipped_no_competitors"] += 1
            continue

        team1_raw = team_tags[0].get_text(strip=True)
        team2_raw = team_tags[1].get_text(strip=True)

        if not team1_raw or not team2_raw:
            stats["skipped_no_competitors"] += 1
            continue

        if team1_raw == "TBD" or team2_raw == "TBD":
            stats["skipped_tbd"] += 1
            continue

        t1 = normalize_team(team1_raw)
        t2 = normalize_team(team2_raw)
        allowed_t1 = (t1 in teams_norm) and (t1 not in exclusions_norm)
        allowed_t2 = (t2 in teams_norm) and (t2 not in exclusions_norm)
        if not (allowed_t1 or allowed_t2):
            stats["skipped_not_allowed"] += 1
            continue

        # Horário exibido pelo site é UTC
        time_tag = el.select_one('.time')
        time_str = time_tag.get_text(strip=True) if time_tag else "00:00"
        try:
            hour, minute = [int(x) for x in time_str.split(":")]
            match_time_utc = datetime(
                target_day.year, target_day.month, target_day.day,
                hour, minute, tzinfo=pytz.utc
            )
        except Exception:
            stats["skipped_bad_date"] += 1
            continue

        if match_time_utc < now_utc:
            stats["skipped_past"] += 1
            continue

        # Link da partida — agora no formato /matches/counter-strike/...
        link_tag = el.select_one('a.match-link[href]')
        match_url = link_tag['href'] if link_tag else ""
        match_url = match_url_absolute(match_url)

        # Torneio: tenta extrair do slug da URL
        # ex: /matches/counter-strike/09-04-2026/mibr-vs-3dmax/08-00/
        # parts[-2] após rstrip("/") = "08-00", parts[-3] = slug da partida
        tournament_desc = ""
        try:
            parts = match_url.rstrip("/").split("/")
            # estrutura: ['https:', '', 'tips.gg', 'matches', 'counter-strike', 'DD-MM-YYYY', 'slug-partida', 'HH-MM']
            if len(parts) >= 7:
                tournament_desc = parts[-3]  # ex: "mibr-vs-3dmax"
        except Exception:
            pass

        ev = build_event(
            game_key, prefix, team1_raw, team2_raw,
            match_time_utc, tournament_desc, "tips.gg", match_url,
            existing_uids,
        )
        if ev:
            new_events.append(ev)
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
        "url": build_url_for_day(game_cfg["base_path"], target_day),
        "method": "none",
        "scripts_total": 0,
        "sports_events": 0,
        "dom_matches_found": 0,
        "added": 0,
        "skipped_tbd": 0,
        "skipped_past": 0,
        "skipped_no_competitors": 0,
        "skipped_not_allowed": 0,
        "skipped_bad_date": 0,
        "json_decode_errors": 0,
        "timeouts_load": 0,
        "timeouts_wait": 0,
    }

    url = stats["url"]

    try:
        driver.get(url)
    except TimeoutException:
        stats["timeouts_load"] += 1
        try:
            driver.execute_script("window.stop();")
        except Exception:
            pass

    # Espera JSON-LD primeiro; se não aparecer espera pelo DOM
    try:
        WebDriverWait(driver, MATCH_WAIT_SECONDS).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, 'script[type="application/ld+json"]')
            )
        )
    except TimeoutException:
        try:
            WebDriverWait(driver, MATCH_WAIT_SECONDS).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, '.element.match')
                )
            )
        except TimeoutException:
            stats["timeouts_wait"] += 1

    soup = BeautifulSoup(driver.page_source, "html.parser")
    now_utc = datetime.now(pytz.utc)

    if soup_has_sports_events(soup):
        stats["method"] = "jsonld"
        log(f"  ↳ Usando JSON-LD")
        new_events = parse_jsonld(soup, game_key, game_cfg, existing_uids, now_utc, stats)
    elif soup.select('.element.match'):
        stats["method"] = "dom"
        log(f"  ↳ JSON-LD ausente, usando DOM")
        new_events = parse_dom(soup, game_key, game_cfg, existing_uids, now_utc, target_day, stats)
    else:
        stats["method"] = "none"
        log(f"  ↳ Nenhum conteúdo útil encontrado")
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

target_day = load_cursor(today, future_limit)
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

        new_events, stats = scrape_one_day_for_game(driver, game_key, cfg, target_day, existing_uids)

        for ev in new_events:
            cal.add_component(ev)

        total_added += stats["added"]

        log(f"🧾 RESUMO {game_key} - {stats['date']} [método: {stats['method']}]")
        log(f"  scripts={stats['scripts_total']} sports={stats['sports_events']} "
            f"dom_matches={stats['dom_matches_found']} added={stats['added']}")
        log(f"  skipped: tbd={stats['skipped_tbd']} past={stats['skipped_past']} "
            f"not_allowed={stats['skipped_not_allowed']} bad_date={stats['skipped_bad_date']}")
        log(f"  timeouts: load={stats['timeouts_load']} wait={stats['timeouts_wait']} "
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
