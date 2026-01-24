import os
import json
import hashlib
from datetime import datetime, timedelta, date
from typing import Optional, Tuple, List, Dict

import pytz
from bs4 import BeautifulSoup
from ics import Calendar, Event
from ics.alarm import DisplayAlarm

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from webdriver_manager.chrome import ChromeDriverManager


# -------------------- Configurações Globais --------------------
BRAZILIAN_TEAMS = [
    "FURIA", "paiN", "MIBR", "Imperial", "Fluxo",
    "RED Canids", "Legacy", "ODDIK", "Imperial Esports"
]

BRAZILIAN_TEAMS_EXCLUSIONS = [
    "Imperial.A", "Imperial Fe", "MIBR.A", "paiN.A", "ODDIK.A",
    "Imperial Academy", "Imperial.Acd", "Imperial Female",
    "Furia Academy", "Furia.A", "Pain Academy", "Mibr Academy", "Legacy Academy", "ODDIK Academy",
    "RED Canids Academy", "Fluxo Academy"
]

CALENDAR_FILENAME = "calendar.ics"
BR_TZ = pytz.timezone("America/Sao_Paulo")

# Janela fixa: hoje..hoje+4 (5 dias)
FUTURE_LIMIT_DAYS = 4

# Limpeza: remove eventos do script com mais de 7 dias atrás
DELETE_OLDER_THAN_DAYS = 7

# Timeouts
PAGE_LOAD_TIMEOUT_SECONDS = 15
JSONLD_WAIT_SECONDS = 8

# Marcador para identificar eventos do script
SOURCE_MARKER = "X-RANALLI-SOURCE:TIPSGG"

# Âncora para identificar eventos antigos gerados sem marcador (mas do tips.gg)
TIPS_URL_HINT = "https://tips.gg/matches/"


# -------------------- Helpers --------------------
def log(msg: str):
    now = datetime.now(BR_TZ).strftime("%H:%M:%S")
    print(f"[{now}] {msg}")


def normalize_team(name: str) -> str:
    return (name or "").lower().strip()


NORMALIZED_BRAZILIAN_TEAMS = {normalize_team(t) for t in BRAZILIAN_TEAMS}
NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS = {normalize_team(t) for t in BRAZILIAN_TEAMS_EXCLUSIONS}


def build_url_for_day(target_date: date) -> str:
    date_str = target_date.strftime("%d-%m-%Y")
    return f"https://tips.gg/csgo/matches/{date_str}/"


def load_calendar(path: str) -> Calendar:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return Calendar(f.read())
        except Exception as e:
            log(f"⚠️ Falha ao ler {path}: {e}. Criando calendário novo.")
    return Calendar()


def save_calendar(cal: Calendar, path: str):
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())


def normalize_event_datetime_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    return dt.astimezone(pytz.utc).replace(microsecond=0, second=0)


def is_ours(ev: Event) -> bool:
    desc = (getattr(ev, "description", "") or "")
    return (SOURCE_MARKER in desc) or (TIPS_URL_HINT in desc)


def event_start_date_local(ev: Event) -> Optional[date]:
    try:
        dt = ev.begin.datetime
        if dt.tzinfo is None:
            dt = pytz.utc.localize(dt)
        return dt.astimezone(BR_TZ).date()
    except Exception:
        return None


def prune_older_than(cal: Calendar, cutoff_date: date) -> int:
    to_remove = []
    for ev in list(cal.events):
        if not is_ours(ev):
            continue
        d = event_start_date_local(ev)
        if d and d < cutoff_date:
            to_remove.append(ev)

    for ev in to_remove:
        cal.events.discard(ev)

    return len(to_remove)


# -------------------- URL / Torneio --------------------
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


def extract_match_url_from_event(ev: Event) -> str:
    desc = (getattr(ev, "description", "") or "")
    return extract_match_url_from_description(desc).strip().lower()


def index_events_by_url(cal: Calendar) -> Dict[str, Event]:
    by_url: Dict[str, Event] = {}
    for ev in cal.events:
        if not is_ours(ev):
            continue
        url = extract_match_url_from_event(ev)
        if url:
            by_url[url] = ev
    return by_url


def build_uid_from_url(match_url: str) -> str:
    return hashlib.sha1((match_url or "").strip().lower().encode("utf-8")).hexdigest()


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
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT_SECONDS)
    return driver


def safe_get(driver: webdriver.Chrome, url: str) -> None:
    try:
        driver.get(url)
    except TimeoutException:
        try:
            driver.execute_script("window.stop();")
        except Exception:
            pass


def wait_for_dom(driver: webdriver.Chrome, css: str, timeout_s: int) -> bool:
    try:
        WebDriverWait(driver, timeout_s).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, css))
        )
        return True
    except TimeoutException:
        return False


def collect_match_urls_from_day_html(page_source: str) -> List[str]:
    """
    Coleta URLs reais dos cards do dia pelo HTML (não pelo JSON-LD).
    Isso evita pegar match “velho” quando o JSON-LD fica desatualizado.
    """
    soup = BeautifulSoup(page_source, "html.parser")
    urls = set()

    for a in soup.select('a.match-link[href]'):
        href = (a.get("href") or "").strip()
        if not href:
            continue
        if href.startswith("/"):
            href = "https://tips.gg" + href
        if href.startswith("https://tips.gg/matches/"):
            # remove sufixos tipo /streams /predictions
            href = href.split("/streams/")[0].split("/predictions/")[0]
            urls.add(href.rstrip("/"))

    return sorted(urls)


def parse_sportsevent_from_jsonld(raw_json: str) -> Optional[dict]:
    """
    A página pode ter:
      - um dict
      - uma lista
      - um @graph
    Retorna o primeiro SportsEvent que achar.
    """
    try:
        data = json.loads(raw_json)
    except Exception:
        return None

    candidates = []
    if isinstance(data, dict):
        if data.get("@type") == "SportsEvent":
            candidates.append(data)
        if "@graph" in data and isinstance(data["@graph"], list):
            candidates.extend([x for x in data["@graph"] if isinstance(x, dict)])
    elif isinstance(data, list):
        candidates.extend([x for x in data if isinstance(x, dict)])

    for item in candidates:
        if item.get("@type") == "SportsEvent":
            return item
    return None


def scrape_match_page_sportsevent(driver: webdriver.Chrome, match_url: str) -> Optional[dict]:
    """
    Abre a página do match e extrai o SportsEvent do JSON-LD dela.
    """
    safe_get(driver, match_url)
    wait_for_dom(driver, 'script[type="application/ld+json"]', JSONLD_WAIT_SECONDS)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    scripts = soup.find_all("script", type="application/ld+json")
    for s in scripts:
        raw = (s.string or "").strip()
        if not raw:
            continue
        se = parse_sportsevent_from_jsonld(raw)
        if se:
            return se
    return None


def find_fallback_event_to_replace(
    cal: Calendar,
    day: date,
    tournament_desc: str,
    organizer_name: str,
    team_anchor: str,
    begin_norm_utc: datetime,
) -> Optional[Event]:
    """
    Fallback quando a URL mudou:
    tenta achar um evento do script no mesmo dia, mesmo campeonato/organizer,
    contendo o time âncora (ex: FURIA) e com horário próximo.
    """
    team_anchor = (team_anchor or "").strip().lower()
    tournament_desc = (tournament_desc or "").strip().lower()
    organizer_name = (organizer_name or "").strip().lower()

    best = None
    best_delta = None

    for ev in cal.events:
        if not is_ours(ev):
            continue
        d = event_start_date_local(ev)
        if d != day:
            continue

        desc = (getattr(ev, "description", "") or "").lower()
        if tournament_desc and (f"🏆 {tournament_desc}" not in desc):
            continue
        if organizer_name and (f"📍 {organizer_name}" not in desc):
            continue
        if team_anchor and (team_anchor not in (getattr(ev, "name", "") or "").lower()):
            continue

        try:
            old_begin = normalize_event_datetime_utc(ev.begin.datetime)
        except Exception:
            continue

        delta = abs(int((old_begin - begin_norm_utc).total_seconds()))
        # tolerância: até 8 horas
        if delta > 8 * 3600:
            continue

        if best is None or delta < best_delta:
            best = ev
            best_delta = delta

    return best


def upsert_event_by_url_or_fallback(
    cal: Calendar,
    by_url: Dict[str, Event],
    match_url: str,
    event_summary: str,
    begin_norm: datetime,
    tournament_desc: str,
    organizer_name: str,
    team_anchor_for_fallback: str,
) -> Tuple[bool, bool]:
    """
    Retorna (added, updated)
    """
    match_url_norm = (match_url or "").strip().lower()
    if not match_url_norm:
        return (False, False)

    event_description = (
        f"🏆 {tournament_desc}\n"
        f"📍 {organizer_name}\n"
        f"🌐 {match_url}\n"
        f"{SOURCE_MARKER}"
    )

    existing_ev = by_url.get(match_url_norm)

    # 1) update direto por URL
    if existing_ev:
        changed = False

        if (getattr(existing_ev, "name", "") or "") != event_summary:
            existing_ev.name = event_summary
            changed = True

        try:
            old_begin = normalize_event_datetime_utc(existing_ev.begin.datetime)
        except Exception:
            old_begin = None

        if old_begin != begin_norm:
            existing_ev.begin = begin_norm
            changed = True

        if (getattr(existing_ev, "description", "") or "") != event_description:
            existing_ev.description = event_description
            changed = True

        existing_ev.duration = timedelta(hours=2)
        if not getattr(existing_ev, "alarms", None):
            existing_ev.alarms = []
        if not existing_ev.alarms:
            existing_ev.alarms.append(DisplayAlarm(trigger=timedelta(minutes=-15)))

        new_uid = build_uid_from_url(match_url_norm)
        if getattr(existing_ev, "uid", "") != new_uid:
            existing_ev.uid = new_uid
            changed = True

        return (False, changed)

    # 2) fallback (URL mudou): substitui evento “antigo equivalente”
    day_local = begin_norm.astimezone(BR_TZ).date()
    fallback_ev = find_fallback_event_to_replace(
        cal=cal,
        day=day_local,
        tournament_desc=tournament_desc,
        organizer_name=organizer_name,
        team_anchor=team_anchor_for_fallback,
        begin_norm_utc=begin_norm,
    )

    if fallback_ev:
        # remove índice antigo
        old_url = extract_match_url_from_event(fallback_ev)
        if old_url and old_url in by_url and by_url[old_url] is fallback_ev:
            del by_url[old_url]

        # atualiza o evento existente
        fallback_ev.name = event_summary
        fallback_ev.begin = begin_norm
        fallback_ev.duration = timedelta(hours=2)
        fallback_ev.description = event_description
        fallback_ev.uid = build_uid_from_url(match_url_norm)
        if not getattr(fallback_ev, "alarms", None):
            fallback_ev.alarms = []
        if not fallback_ev.alarms:
            fallback_ev.alarms.append(DisplayAlarm(trigger=timedelta(minutes=-15)))

        by_url[match_url_norm] = fallback_ev
        return (False, True)

    # 3) insert novo
    e = Event()
    e.name = event_summary
    e.begin = begin_norm
    e.duration = timedelta(hours=2)
    e.description = event_description
    e.uid = build_uid_from_url(match_url_norm)
    e.alarms.append(DisplayAlarm(trigger=timedelta(minutes=-15)))

    cal.events.add(e)
    by_url[match_url_norm] = e
    return (True, False)


def is_brazilian_team_involved(team1: str, team2: str) -> bool:
    n1 = normalize_team(team1)
    n2 = normalize_team(team2)

    is_br1 = n1 in NORMALIZED_BRAZILIAN_TEAMS and n1 not in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS
    is_br2 = n2 in NORMALIZED_BRAZILIAN_TEAMS and n2 not in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS
    return is_br1 or is_br2


def scrape_one_day(driver: webdriver.Chrome, day: date, cal: Calendar, by_url: Dict[str, Event]) -> dict:
    """
    1) abre página do dia
    2) coleta URLs reais via HTML
    3) abre cada match e extrai SportsEvent do JSON-LD do match
    4) upsert (URL ou fallback)
    """
    stats = {
        "date": day.strftime("%d/%m/%Y"),
        "day_url": build_url_for_day(day),
        "match_urls": 0,
        "match_pages_ok": 0,
        "match_pages_fail": 0,
        "added": 0,
        "updated": 0,
        "skipped_not_br": 0,
        "skipped_tbd": 0,
        "skipped_past": 0,
        "skipped_bad_date": 0,
    }

    safe_get(driver, stats["day_url"])
    wait_for_dom(driver, "a.match-link", JSONLD_WAIT_SECONDS)

    match_urls = collect_match_urls_from_day_html(driver.page_source)
    stats["match_urls"] = len(match_urls)

    now_utc = datetime.now(pytz.utc)

    for match_url in match_urls:
        se = scrape_match_page_sportsevent(driver, match_url)
        if not se:
            stats["match_pages_fail"] += 1
            continue

        stats["match_pages_ok"] += 1

        # pega dados
        start_date_str = se.get("startDate", "") or ""
        description = se.get("description", "") or ""
        organizer_name = (se.get("organizer") or {}).get("name", "Desconhecido")

        competitors = se.get("competitor", []) or []
        if len(competitors) < 2:
            continue

        team1_raw = competitors[0].get("name", "TBD")
        team2_raw = competitors[1].get("name", "TBD")

        if team1_raw == "TBD" or team2_raw == "TBD":
            stats["skipped_tbd"] += 1
            continue

        if not is_brazilian_team_involved(team1_raw, team2_raw):
            stats["skipped_not_br"] += 1
            continue

        # horário
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

        begin_norm = normalize_event_datetime_utc(match_time_utc)
        event_summary = f"{team1_raw} vs {team2_raw}"

        # usa o match_url da própria página (mais estável), mas se quiser pode preferir se["url"]
        final_match_url = match_url

        added, updated = upsert_event_by_url_or_fallback(
            cal=cal,
            by_url=by_url,
            match_url=final_match_url,
            event_summary=event_summary,
            begin_norm=begin_norm,
            tournament_desc=description,
            organizer_name=organizer_name,
            team_anchor_for_fallback="FURIA",  # âncora para trocar URL quando mudar
        )

        if added:
            stats["added"] += 1
        if updated:
            stats["updated"] += 1

    return stats


# -------------------- Execução --------------------
log("🔄 Iniciando execução (HTML do dia -> página do match -> upsert)...")

cal = load_calendar(CALENDAR_FILENAME)

# Limpeza
today = datetime.now(BR_TZ).date()
cutoff = today - timedelta(days=DELETE_OLDER_THAN_DAYS)
removed = prune_older_than(cal, cutoff)
log(f"🧹 Limpeza: removidos {removed} eventos do script com data < {cutoff.strftime('%d/%m/%Y')}")

# Index por URL
by_url = index_events_by_url(cal)

driver = None
total_added = 0
total_updated = 0

try:
    driver = setup_driver()

    for offset in range(0, FUTURE_LIMIT_DAYS + 1):
        day = today + timedelta(days=offset)
        log(f"📅 Processando dia {day.strftime('%d/%m/%Y')}")

        stats = scrape_one_day(driver, day, cal, by_url)

        total_added += stats["added"]
        total_updated += stats["updated"]

        log(
            f"🧾 {stats['date']} | matches={stats['match_urls']} ok={stats['match_pages_ok']} fail={stats['match_pages_fail']} "
            f"added={stats['added']} updated={stats['updated']} "
            f"skipped(not_br={stats['skipped_not_br']}, tbd={stats['skipped_tbd']}, past={stats['skipped_past']}, bad_date={stats['skipped_bad_date']})"
        )

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

# Salva
log(f"💾 Salvando arquivo: {CALENDAR_FILENAME}")
try:
    save_calendar(cal, CALENDAR_FILENAME)
    log(f"✅ Salvo. Total: added={total_added} updated={total_updated}")
except Exception as e:
    log(f"❌ Erro ao salvar {CALENDAR_FILENAME}: {e}")
