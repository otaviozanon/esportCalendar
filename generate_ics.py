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
MATCH_WAIT_SECONDS = 15

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


# -------------------- Logging --------------------
def log(msg: str):
    now = datetime.now(BR_TZ).strftime("%H:%M:%S")
    print(f"[{now}] {msg}", flush=True)


# -------------------- Calendário --------------------
def load_calendar(filename: str) -> Calendar:
    if os.path.exists(filename):
        try:
            with open(filename, "rb") as f:
                return Calendar.from_ical(f.read())
        except Exception:
            pass
    cal = Calendar()
    cal.add("prodid", "-//Sett Tips.GG Scraper//EN")
    cal.add("version", "2.0")
    return cal


def save_calendar(cal: Calendar, filename: str):
    with open(filename, "wb") as f:
        f.write(cal.to_ical())


def get_existing_uids(cal: Calendar) -> set:
    uids = set()
    for component in cal.walk():
        if component.name == "VEVENT":
            uid = str(component.get("uid", ""))
            if uid:
                uids.add(uid)
    return uids


def is_ours(component) -> bool:
    for line in component.content_lines():
        if SOURCE_MARKER in line:
            return True
    url = str(component.get("url", ""))
    return TIPS_URL_HINT in url


def prune_older_than(cal: Calendar, cutoff: datetime) -> int:
    to_remove = []
    for component in cal.walk():
        if component.name != "VEVENT":
            continue
        if not is_ours(component):
            continue
        dtstart = component.get("dtstart")
        if dtstart is None:
            continue
        dt = dtstart.dt
        if isinstance(dt, date) and not isinstance(dt, datetime):
            dt = datetime(dt.year, dt.month, dt.day, tzinfo=BR_TZ)
        if dt.tzinfo is None:
            dt = BR_TZ.localize(dt)
        else:
            dt = dt.astimezone(BR_TZ)
        if dt < cutoff:
            to_remove.append(component)
    for c in to_remove:
        cal.subcomponents.remove(c)
    return len(to_remove)


def dedupe_calendar_events(cal: Calendar) -> int:
    seen = {}
    to_remove = []
    for component in cal.walk():
        if component.name != "VEVENT":
            continue
        uid = str(component.get("uid", ""))
        if not uid:
            continue
        if uid in seen:
            to_remove.append(component)
        else:
            seen[uid] = component
    for c in to_remove:
        cal.subcomponents.remove(c)
    return len(to_remove)


def dedupe_by_url_keep_latest(cal: Calendar) -> int:
    url_map = {}
    for component in cal.walk():
        if component.name != "VEVENT":
            continue
        if not is_ours(component):
            continue
        url = str(component.get("url", ""))
        if not url:
            continue
        dtstart = component.get("dtstart")
        if dtstart is None:
            continue
        dt = dtstart.dt
        if isinstance(dt, date) and not isinstance(dt, datetime):
            dt = datetime(dt.year, dt.month, dt.day, tzinfo=BR_TZ)
        if dt.tzinfo is None:
            dt = BR_TZ.localize(dt)
        if url not in url_map:
            url_map[url] = component
        else:
            existing_dt = url_map[url].get("dtstart").dt
            if isinstance(existing_dt, date) and not isinstance(existing_dt, datetime):
                existing_dt = datetime(existing_dt.year, existing_dt.month, existing_dt.day, tzinfo=BR_TZ)
            if existing_dt.tzinfo is None:
                existing_dt = BR_TZ.localize(existing_dt)
            if dt > existing_dt:
                url_map[url] = component

    to_keep = set(id(c) for c in url_map.values())
    to_remove = []
    for component in cal.walk():
        if component.name != "VEVENT":
            continue
        if not is_ours(component):
            continue
        url = str(component.get("url", ""))
        if url and id(component) not in to_keep:
            to_remove.append(component)
    for c in to_remove:
        cal.subcomponents.remove(c)
    return len(to_remove)


# -------------------- Estado (cursor rotativo) --------------------
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
        json.dump({"cursor_date": d.isoformat()}, f)


# -------------------- Selenium --------------------
def setup_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=en-US")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT_SECONDS)
    return driver


# -------------------- URL --------------------
def build_url_for_day(base_path: str, target_day: date) -> str:
    if target_day == date.today():
        return base_path
    return f"{base_path}{target_day.strftime('%d-%m-%Y')}/"


# -------------------- Parse JSON-LD via JavaScript --------------------
def extract_jsonld_via_js(driver) -> list:
    """
    Usa JavaScript para extrair todos os JSON-LDs da página,
    contornando o Cloudflare Rocket Loader que modifica o type dos scripts.
    """
    js = """
    var results = [];
    var scripts = document.querySelectorAll('script');
    for (var i = 0; i < scripts.length; i++) {
        var s = scripts[i];
        var t = s.getAttribute('type') || '';
        var txt = s.textContent || s.innerText || '';
        if (t === 'application/ld+json' || txt.indexOf('"@type"') !== -1) {
            if (txt.trim().startsWith('{') || txt.trim().startsWith('[')) {
                results.push(txt);
            }
        }
    }
    return results;
    """
    try:
        return driver.execute_script(js) or []
    except Exception:
        return []


# -------------------- Scrape --------------------
def make_uid(game_key: str, team1: str, team2: str, start_dt: datetime) -> str:
    raw = f"{game_key}|{normalize_team(team1)}|{normalize_team(team2)}|{start_dt.isoformat()}"
    return hashlib.md5(raw.encode()).hexdigest() + "@tipsgg"


def scrape_one_day_for_game(
    driver, game_key: str, cfg: dict, target_day: date, existing_uids: set
) -> tuple:
    stats = {
        "date": target_day.strftime("%d/%m/%Y"),
        "scripts_total": 0,
        "sports_events": 0,
        "added": 0,
        "skipped_tbd": 0,
        "skipped_past": 0,
        "skipped_not_allowed": 0,
        "skipped_bad_date": 0,
        "timeouts_load": 0,
        "timeouts_jsonld": 0,
        "json_decode_errors": 0,
    }
    new_events = []
    url = build_url_for_day(cfg["base_path"], target_day)
    now_br = datetime.now(BR_TZ)

    # Carrega a página
    try:
        driver.get(url)
    except TimeoutException:
        stats["timeouts_load"] += 1
        log(f"  ↳ Timeout carregando página {game_key}")
        return new_events, stats

    # Aguarda pelo elemento .element.match aparecer no DOM
    try:
        WebDriverWait(driver, MATCH_WAIT_SECONDS).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".element.match"))
        )
    except TimeoutException:
        # Pode não ter partidas no dia — não é necessariamente erro
        log(f"  ↳ Nenhuma partida encontrada em {game_key} para {target_day.strftime('%d/%m/%Y')}")
        stats["timeouts_jsonld"] += 1
        return new_events, stats

    # Pequena pausa para o Rocket Loader processar
    time.sleep(2)

    # Extrai JSON-LDs via JavaScript (contorna o Rocket Loader)
    raw_scripts = extract_jsonld_via_js(driver)
    stats["scripts_total"] = len(raw_scripts)

    for raw in raw_scripts:
        try:
            data = json.loads(raw.strip())
        except json.JSONDecodeError:
            stats["json_decode_errors"] += 1
            continue

        if not isinstance(data, dict):
            continue
        if data.get("@type") != "SportsEvent":
            continue

        stats["sports_events"] += 1

        # Extrai dados
        name = data.get("name", "")
        start_raw = data.get("startDate", "")
        event_url = data.get("url", "")
        organizer = data.get("organizer", {})
        tournament = organizer.get("name", "") if isinstance(organizer, dict) else ""
        competitors = data.get("competitor", [])

        if len(competitors) < 2:
            continue

        team1 = competitors[0].get("name", "")
        team2 = competitors[1].get("name", "")

        # Verifica TBD
        if not team1 or not team2 or "tbd" in normalize_team(team1) or "tbd" in normalize_team(team2):
            stats["skipped_tbd"] += 1
            continue

        # Verifica exclusões
        t1n = normalize_team(team1)
        t2n = normalize_team(team2)
        excl = cfg["exclusions_norm"]
        if t1n in excl or t2n in excl:
            stats["skipped_not_allowed"] += 1
            continue

        # Verifica se algum time é da lista permitida
        allowed = cfg["teams_norm"]
        if t1n not in allowed and t2n not in allowed:
            stats["skipped_not_allowed"] += 1
            continue

        # Parse da data — o site usa offset -0300 (horário de Brasília)
        try:
            start_dt = datetime.fromisoformat(start_raw)
            if start_dt.tzinfo is None:
                start_dt = BR_TZ.localize(start_dt)
            else:
                start_dt = start_dt.astimezone(BR_TZ)
        except Exception:
            stats["skipped_bad_date"] += 1
            continue

        # Verifica se é do dia certo
        if start_dt.date() != target_day:
            stats["skipped_bad_date"] += 1
            continue

        # Verifica se já passou
        if start_dt < now_br:
            stats["skipped_past"] += 1
            continue

        # Monta URL completa
        if event_url and not event_url.startswith("http"):
            event_url = "https://tips.gg" + event_url

        # Gera UID e verifica duplicata
        uid = make_uid(game_key, team1, team2, start_dt)
        if uid in existing_uids:
            continue

        # Cria evento
        prefix = cfg["prefix"]
        summary = f"{prefix}{team1} vs {team2}"
        if tournament:
            summary += f" — {tournament}"

        ev = Event()
        ev.add("summary", summary)
        ev.add("dtstart", start_dt)
        ev.add("dtend", start_dt + timedelta(hours=3))
        ev.add("uid", uid)
        if event_url:
            ev.add("url", event_url)
        ev.add("description", f"{name}\n{event_url}")
        ev["X-SETT-SOURCE"] = "TIPSGG"

        alarm = Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add("description", f"Em breve: {summary}")
        alarm.add("trigger", timedelta(minutes=-30))
        ev.add_component(alarm)

        new_events.append(ev)
        existing_uids.add(uid)
        stats["added"] += 1
        log(f"  ✅ {summary} às {start_dt.strftime('%H:%M')} (BR)")

    return new_events, stats


# -------------------- Main --------------------
log("🔄 Iniciando execução (cursor rotativo)...")

cal = load_calendar(CALENDAR_FILENAME)
existing_uids = get_existing_uids(cal)

today = date.today()
future_limit = today + timedelta(days=FUTURE_LIMIT_DAYS)
cutoff = datetime.now(BR_TZ) - timedelta(days=DELETE_OLDER_THAN_DAYS)

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
