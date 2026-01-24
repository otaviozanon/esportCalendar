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
    """
    Normaliza datetime para UTC, sem microsegundos e com segundo=0.
    """
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    return dt.astimezone(pytz.utc).replace(microsecond=0, second=0)


def is_ours(ev: Event) -> bool:
    """
    Evento gerado pelo script:
    - tem SOURCE_MARKER, OU
    - tem link do tips.gg no description (casos antigos sem marcador)
    """
    desc = (getattr(ev, "description", "") or "")
    return (SOURCE_MARKER in desc) or (TIPS_URL_HINT in desc)


def event_start_date_local(ev: Event) -> Optional[date]:
    """
    Converte o begin do evento para data local.
    """
    try:
        dt = ev.begin.datetime
        if dt.tzinfo is None:
            dt = pytz.utc.localize(dt)
        return dt.astimezone(BR_TZ).date()
    except Exception:
        return None


def prune_older_than(cal: Calendar, cutoff_date: date) -> int:
    """
    Remove eventos DO SCRIPT com data < cutoff_date.
    Considera também eventos antigos do tips.gg sem marker.
    """
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


# -------------------- Descrição/URL do evento --------------------
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
    """
    Indexa eventos do script por URL do match. Isso é a chave para atualizar.
    """
    by_url: Dict[str, Event] = {}
    for ev in cal.events:
        if not is_ours(ev):
            continue
        url = extract_match_url_from_event(ev)
        if url:
            by_url[url] = ev
    return by_url


# -------------------- Deduplicação (cinto de segurança) --------------------
def event_key(ev: Event) -> tuple:
    """
    Chave lógica antiga (mantida só pra limpeza extra):
    (nome, horário UTC normalizado, campeonato, url)
    """
    name = (getattr(ev, "name", "") or "").strip().lower()

    begin_iso = ""
    try:
        dtd = normalize_event_datetime_utc(ev.begin.datetime)
        begin_iso = dtd.isoformat()
    except Exception:
        begin_iso = ""

    desc = (getattr(ev, "description", "") or "")
    tournament = extract_tournament_from_description(desc).lower()
    url = extract_match_url_from_event(ev).lower()

    return (name, begin_iso, tournament, url)


def dedupe_calendar_events(cal: Calendar) -> int:
    """
    Remove duplicados do tips.gg (mesma chave lógica).
    Regra:
      - se existir versão com SOURCE_MARKER, ela vence
      - senão, mantém o primeiro
    """
    best_by_key: Dict[tuple, Event] = {}
    to_remove: List[Event] = []

    for ev in list(cal.events):
        if not is_ours(ev):
            continue

        k = event_key(ev)
        if k not in best_by_key:
            best_by_key[k] = ev
            continue

        current_best = best_by_key[k]

        cur_desc = (getattr(current_best, "description", "") or "")
        new_desc = (getattr(ev, "description", "") or "")

        cur_has_marker = SOURCE_MARKER in cur_desc
        new_has_marker = SOURCE_MARKER in new_desc

        if new_has_marker and not cur_has_marker:
            to_remove.append(current_best)
            best_by_key[k] = ev
        else:
            to_remove.append(ev)

    for ev in to_remove:
        cal.events.discard(ev)

    return len(to_remove)


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


def build_uid_from_url(match_url: str) -> str:
    """
    UID determinístico pela URL do match.
    Isso faz o mesmo jogo ser o mesmo evento, mesmo se horário/time mudarem.
    """
    return hashlib.sha1((match_url or "").strip().lower().encode("utf-8")).hexdigest()


def scrape_one_day(
    driver: webdriver.Chrome,
    target_day: date,
    cal: Calendar,
    by_url: Dict[str, Event],
) -> Tuple[List[Event], dict]:
    stats = {
        "date": target_day.strftime("%d/%m/%Y"),
        "url": build_url_for_day(target_day),
        "scripts_total": 0,
        "sports_events": 0,
        "added": 0,
        "updated": 0,
        "skipped_tbd": 0,
        "skipped_past": 0,
        "skipped_no_competitors": 0,
        "skipped_not_br": 0,
        "skipped_bad_date": 0,
        "json_decode_errors": 0,
        "timeouts_load": 0,
        "timeouts_jsonld": 0,
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

    try:
        WebDriverWait(driver, JSONLD_WAIT_SECONDS).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'script[type="application/ld+json"]'))
        )
    except TimeoutException:
        stats["timeouts_jsonld"] += 1

    soup = BeautifulSoup(driver.page_source, "html.parser")
    scripts = soup.find_all("script", type="application/ld+json")
    stats["scripts_total"] = len(scripts)

    now_utc = datetime.now(pytz.utc)
    new_events: List[Event] = []

    for script in scripts:
        raw = (script.string or "").strip()
        if not raw:
            continue

        try:
            event_data = json.loads(raw)
        except json.JSONDecodeError:
            stats["json_decode_errors"] += 1
            continue

        if event_data.get("@type") != "SportsEvent":
            continue

        stats["sports_events"] += 1

        start_date_str = event_data.get("startDate", "") or ""
        description = event_data.get("description", "") or ""
        organizer_name = (event_data.get("organizer") or {}).get("name", "Desconhecido")
        match_url = event_data.get("url", "") or ""

        if match_url and not match_url.startswith("http"):
            match_url = f"https://tips.gg{match_url}"

        competitors = event_data.get("competitor", []) or []
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

        normalized_team1 = normalize_team(team1_raw)
        normalized_team2 = normalize_team(team2_raw)

        is_br_team1 = normalized_team1 in NORMALIZED_BRAZILIAN_TEAMS
        is_br_team2 = normalized_team2 in NORMALIZED_BRAZILIAN_TEAMS

        is_excluded_team1 = normalized_team1 in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS
        is_excluded_team2 = normalized_team2 in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS

        is_br_team_involved = (is_br_team1 and not is_excluded_team1) or (is_br_team2 and not is_excluded_team2)
        if not is_br_team_involved:
            stats["skipped_not_br"] += 1
            continue

        event_summary = f"{team1_raw} vs {team2_raw}"

        event_description = (
            f"🏆 {description}\n"
            f"📍 {organizer_name}\n"
            f"🌐 {match_url}\n"
            f"{SOURCE_MARKER}"
        )

        begin_norm = normalize_event_datetime_utc(match_time_utc)
        match_url_norm = (match_url or "").strip().lower()

        if not match_url_norm:
            # Sem URL não dá pra atualizar direito, então ignora para não bagunçar calendário
            continue

        existing_ev = by_url.get(match_url_norm)

        if existing_ev:
            # -------- UPDATE: corrige adversário e/ou horário --------
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

            # opcional: padroniza duração e alarmes
            existing_ev.duration = timedelta(hours=2)
            if not getattr(existing_ev, "alarms", None):
                existing_ev.alarms = []
            if not existing_ev.alarms:
                existing_ev.alarms.append(DisplayAlarm(trigger=timedelta(minutes=-15)))

            # garante UID estável pela URL (se era evento antigo)
            new_uid = build_uid_from_url(match_url_norm)
            if getattr(existing_ev, "uid", "") != new_uid:
                existing_ev.uid = new_uid
                changed = True

            if changed:
                stats["updated"] += 1

            continue

        # -------- INSERT: evento novo --------
        e = Event()
        e.name = event_summary
        e.begin = begin_norm
        e.duration = timedelta(hours=2)
        e.description = event_description
        e.uid = build_uid_from_url(match_url_norm)

        alarm = DisplayAlarm(trigger=timedelta(minutes=-15))
        e.alarms.append(alarm)

        new_events.append(e)
        by_url[match_url_norm] = e
        stats["added"] += 1

    return new_events, stats


# -------------------- Execução --------------------
log("🔄 Iniciando execução (janela fixa + upsert por URL)...")

cal = load_calendar(CALENDAR_FILENAME)

# Dedup inicial (se o arquivo estiver sujo)
deduped_initial = dedupe_calendar_events(cal)
if deduped_initial:
    log(f"🧼 Deduplicação inicial: removidos {deduped_initial} eventos duplicados (tips.gg).")

# Limpeza: remove eventos antigos do script
today = datetime.now(BR_TZ).date()
cutoff = today - timedelta(days=DELETE_OLDER_THAN_DAYS)
removed = prune_older_than(cal, cutoff)
log(f"🧹 Limpeza: removidos {removed} eventos do script com data < {cutoff.strftime('%d/%m/%Y')}")

# Index por URL (para atualizar)
by_url = index_events_by_url(cal)

driver = None
total_added = 0
total_updated = 0

try:
    driver = setup_driver()

    for offset in range(0, FUTURE_LIMIT_DAYS + 1):
        day = today + timedelta(days=offset)
        url = build_url_for_day(day)
        log(f"🌐 Raspando: {day.strftime('%d/%m/%Y')} -> {url}")

        new_events, stats = scrape_one_day(driver, day, cal, by_url)

        for ev in new_events:
            cal.events.add(ev)

        total_added += stats.get("added", 0)
        total_updated += stats.get("updated", 0)

        log(f"🧾 RESUMO {stats['date']}: scripts={stats['scripts_total']} sports={stats['sports_events']} "
            f"added={stats['added']} updated={stats['updated']} "
            f"skipped(tbd={stats['skipped_tbd']}, past={stats['skipped_past']}, not_br={stats['skipped_not_br']}, bad_date={stats['skipped_bad_date']}) "
            f"timeouts(load={stats['timeouts_load']}, jsonld={stats['timeouts_jsonld']}), json_err={stats['json_decode_errors']}")

    # Dedup final (segurança)
    deduped_final = dedupe_calendar_events(cal)
    if deduped_final:
        log(f"🧼 Deduplicação final: removidos {deduped_final} eventos duplicados (tips.gg).")

    log(f"✅ Janela revisada (hoje..hoje+{FUTURE_LIMIT_DAYS}): added={total_added} updated={total_updated}")

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
