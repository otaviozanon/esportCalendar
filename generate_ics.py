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
MATCH_WAIT_SECONDS = 15 # Tempo para esperar por elementos de partida (JSON-LD ou DOM)

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
    print(f"[{now}] {msg}")


# -------------------- Selenium Setup --------------------
def setup_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--disable-blink-features=AutomationControlled") # Ajuda a evitar detecção
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    # Adiciona um User-Agent mais comum para evitar detecção
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT_SECONDS)
    return driver


# -------------------- Calendar Operations --------------------
def load_calendar(filename: str) -> Calendar:
    if os.path.exists(filename):
        with open(filename, "rb") as f:
            return Calendar.from_ical(f.read())
    return Calendar()


def save_calendar(cal: Calendar, filename: str):
    with open(filename, "wb") as f:
        f.write(cal.to_ical())


def get_existing_uids(cal: Calendar) -> set:
    return {str(event["UID"]) for event in cal.walk("VEVENT")}


def prune_older_than(cal: Calendar, cutoff_dt: datetime) -> int:
    to_remove = []
    for event in cal.walk("VEVENT"):
        dtstart = event.get("DTSTART")
        if dtstart and dtstart.dt < cutoff_dt:
            to_remove.append(event)
    for comp in to_remove:
        cal.subcomponents.remove(comp)
    return len(to_remove)


def dedupe_calendar_events(cal: Calendar) -> int:
    unique_events = {}
    for event in cal.walk("VEVENT"):
        summary = str(event.get("SUMMARY"))
        dtstart = event.get("DTSTART").dt
        # Cria uma chave única baseada no resumo e na data (sem segundos para flexibilidade)
        key = (summary, dtstart.date(), dtstart.hour, dtstart.minute)
        if key not in unique_events:
            unique_events[key] = event

    # Substitui os eventos no calendário pelos únicos
    cal.subcomponents = [event for event in unique_events.values()]
    return len(cal.walk("VEVENT")) - len(unique_events) # Retorna quantos foram removidos


def dedupe_by_url_keep_latest(cal: Calendar) -> int:
    events_by_url = {}
    for event in cal.walk("VEVENT"):
        url = str(event.get("URL"))
        if url:
            if url not in events_by_url:
                events_by_url[url] = event
            else:
                # Se já existe, mantém o mais recente (maior DTSTAMP)
                if event.get("DTSTAMP").dt > events_by_url[url].get("DTSTAMP").dt:
                    events_by_url[url] = event

    # Substitui os eventos no calendário pelos únicos por URL
    cal.subcomponents = [event for event in events_by_url.values()]
    return len(cal.walk("VEVENT")) - len(events_by_url)


# -------------------- State Management --------------------
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


# -------------------- Scraper Logic --------------------
def build_url_for_day(base_path: str, target_day: date) -> str:
    # O site usa o formato base_path/DD-MM-YYYY/ ou apenas base_path/ para o dia atual
    if target_day == date.today():
        return base_path
    return f"{base_path}{target_day.strftime('%d-%m-%Y')}/"


def extract_jsonld_via_js(driver) -> list:
    """
    Executa JavaScript para extrair todos os scripts JSON-LD,
    contornando a modificação de tipo do Cloudflare Rocket Loader.
    """
    script = """
    let jsonLdData = [];
    document.querySelectorAll('script').forEach(script => {
        try {
            if (script.textContent.includes('"@type":"SportsEvent"')) {
                const data = JSON.parse(script.textContent);
                if (data['@type'] === 'SportsEvent') {
                    jsonLdData.push(data);
                }
            }
        } catch (e) {
            // Ignora erros de parse de JSON para scripts que não são JSON-LD válidos
        }
    });
    return jsonLdData;
    """
    return driver.execute_script(script)


def parse_dom_matches(soup: BeautifulSoup, game_key: str, cfg: dict, target_day: date, existing_uids: set, stats: dict) -> list:
    new_events = []
    matches = soup.select("div.element.match.upcoming")
    stats["dom_matches_found"] = len(matches)

    for match_div in matches:
        try:
            team1_name = match_div.select_one("div.teams div.team:nth-of-type(1) span.name").text.strip()
            team2_name = match_div.select_one("div.teams div.team:nth-of-type(2) span.name").text.strip()

            # O horário está no formato "HH:MM" e é local (BR_TZ)
            time_str = match_div.select_one("span.time").text.strip()

            # A URL da partida agora é relativa, precisamos da base
            relative_url = match_div.select_one("a.match-link")["href"]
            full_url = f"https://tips.gg{relative_url}"

            # O torneio pode ser extraído do link do torneio ou da URL da partida
            tournament_link = match_div.select_one("a.tournament-link.title")
            tournament_name = tournament_link.select_one("h2").text.strip() if tournament_link else "Unknown Tournament"

            # Normaliza os nomes dos times para verificação
            norm_team1 = normalize_team(team1_name)
            norm_team2 = normalize_team(team2_name)

            # Verifica se algum dos times é de interesse e não está na lista de exclusão
            is_relevant = (
                (norm_team1 in cfg["teams_norm"] and norm_team1 not in cfg["exclusions_norm"]) or
                (norm_team2 in cfg["teams_norm"] and norm_team2 not in cfg["exclusions_norm"])
            )

            if not is_relevant:
                stats["skipped_not_allowed"] += 1
                continue

            # Combina a data do cursor com o horário da partida
            match_datetime_str = f"{target_day.isoformat()}T{time_str}:00"
            match_dt_local = datetime.fromisoformat(match_datetime_str).replace(tzinfo=BR_TZ)
            match_dt_utc = match_dt_local.astimezone(pytz.utc)

            if match_dt_utc < datetime.now(pytz.utc) - timedelta(minutes=10): # Margem de 10 minutos
                stats["skipped_past"] += 1
                continue

            # Cria um UID consistente
            uid_data = f"{full_url}-{match_dt_utc.isoformat()}"
            uid = hashlib.sha1(uid_data.encode()).hexdigest() + "@tips.gg"

            if uid in existing_uids:
                continue # Já existe, pula

            event = Event()
            event.add("SUMMARY", f"{cfg['prefix']}{team1_name} vs {team2_name} ({tournament_name})")
            event.add("DTSTART", match_dt_utc)
            event.add("DTEND", match_dt_utc + timedelta(hours=3)) # Duração estimada de 3 horas
            event.add("DESCRIPTION", f"Partida de {game_key} no torneio {tournament_name}. Mais detalhes: {full_url}")
            event.add("LOCATION", "Online")
            event.add("URL", full_url)
            event.add("UID", uid)
            event.add("DTSTAMP", datetime.now(pytz.utc))
            event.add("CATEGORIES", game_key)
            event.add("X-SETT-SOURCE", SOURCE_MARKER)

            # Adiciona um alarme 30 minutos antes
            alarm = Alarm()
            alarm.add("ACTION", "DISPLAY")
            alarm.add("DESCRIPTION", f"Lembrete: {cfg['prefix']}{team1_name} vs {team2_name} começa em 30 minutos!")
            alarm.add("TRIGGER", timedelta(minutes=-30))
            event.add_component(alarm)

            new_events.append(event)
            stats["added"] += 1

        except Exception as e:
            log(f"⚠️ Erro ao processar partida do DOM: {e} na URL {driver.current_url}")
            # Não incrementa stats['json_decode_errors'] pois não é JSON
            continue
    return new_events


def scrape_one_day_for_game(driver, game_key: str, cfg: dict, target_day: date, existing_uids: set) -> tuple[list, dict]:
    stats = {
        "date": target_day.strftime("%d/%m/%Y"),
        "scripts_total": 0,
        "sports_events": 0,
        "dom_matches_found": 0,
        "added": 0,
        "skipped_tbd": 0,
        "skipped_past": 0,
        "skipped_not_allowed": 0,
        "skipped_bad_date": 0,
        "timeouts_load": 0,
        "timeouts_jsonld": 0,
        "json_decode_errors": 0,
        "method": "N/A"
    }
    new_events = []
    url = build_url_for_day(cfg["base_path"], target_day)

    try:
        driver.get(url)
        # Espera por algum conteúdo de partida, seja JSON-LD ou DOM
        WebDriverWait(driver, MATCH_WAIT_SECONDS).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "script[type*='json'], div.element.match.upcoming"))
        )
        time.sleep(2) # Dá um tempo extra para o Rocket Loader e renderização

        # Tenta extrair JSON-LD primeiro
        json_ld_events = extract_jsonld_via_js(driver)
        stats["scripts_total"] = len(json_ld_events)

        if json_ld_events:
            stats["method"] = "JSON-LD"
            for data in json_ld_events:
                stats["sports_events"] += 1
                try:
                    # Verifica se o evento é um SportsEvent
                    if data.get("@type") != "SportsEvent":
                        continue

                    event_name = data.get("name", "N/A")
                    start_date_str = data.get("startDate")
                    event_url = data.get("url")
                    organizer_name = data.get("organizer", {}).get("name", "N/A")

                    if not start_date_str or not event_url:
                        stats["skipped_tbd"] += 1
                        continue

                    # O site envia com offset, fromisoformat() lida com isso
                    match_dt_local = datetime.fromisoformat(start_date_str)
                    match_dt_utc = match_dt_local.astimezone(pytz.utc)

                    # Verifica se a partida já passou (com uma margem de 10 minutos)
                    if match_dt_utc < datetime.now(pytz.utc) - timedelta(minutes=10):
                        stats["skipped_past"] += 1
                        continue

                    # Extrai nomes dos times do "name" ou "competitor"
                    team_names = []
                    if " vs " in event_name:
                        team_names = [t.strip() for t in event_name.split(" vs ")[:2]]
                    elif data.get("competitor"):
                        team_names = [comp.get("name") for comp in data["competitor"] if comp.get("name")]

                    if len(team_names) < 2:
                        stats["skipped_tbd"] += 1 # Não conseguiu identificar os times
                        continue

                    team1_name = team_names[0]
                    team2_name = team_names[1]

                    norm_team1 = normalize_team(team1_name)
                    norm_team2 = normalize_team(team2_name)

                    is_relevant = (
                        (norm_team1 in cfg["teams_norm"] and norm_team1 not in cfg["exclusions_norm"]) or
                        (norm_team2 in cfg["teams_norm"] and norm_team2 not in cfg["exclusions_norm"])
                    )

                    if not is_relevant:
                        stats["skipped_not_allowed"] += 1
                        continue

                    # Cria um UID consistente
                    full_event_url = f"https://tips.gg{event_url}" if event_url.startswith('/') else event_url
                    uid_data = f"{full_event_url}-{match_dt_utc.isoformat()}"
                    uid = hashlib.sha1(uid_data.encode()).hexdigest() + "@tips.gg"

                    if uid in existing_uids:
                        continue # Já existe, pula

                    event = Event()
                    event.add("SUMMARY", f"{cfg['prefix']}{team1_name} vs {team2_name} ({organizer_name})")
                    event.add("DTSTART", match_dt_utc)
                    event.add("DTEND", match_dt_utc + timedelta(hours=3)) # Duração estimada de 3 horas
                    event.add("DESCRIPTION", f"Partida de {game_key} no torneio {organizer_name}. Mais detalhes: {full_event_url}")
                    event.add("LOCATION", "Online")
                    event.add("URL", full_event_url)
                    event.add("UID", uid)
                    event.add("DTSTAMP", datetime.now(pytz.utc))
                    event.add("CATEGORIES", game_key)
                    event.add("X-SETT-SOURCE", SOURCE_MARKER)

                    # Adiciona um alarme 30 minutos antes
                    alarm = Alarm()
                    alarm.add("ACTION", "DISPLAY")
                    alarm.add("DESCRIPTION", f"Lembrete: {cfg['prefix']}{team1_name} vs {team2_name} começa em 30 minutos!")
                    alarm.add("TRIGGER", timedelta(minutes=-30))
                    event.add_component(alarm)

                    new_events.append(event)
                    stats["added"] += 1

                except json.JSONDecodeError:
                    stats["json_decode_errors"] += 1
                    log(f"❌ Erro de decodificação JSON para um script em {url}")
                except Exception as e:
                    log(f"⚠️ Erro ao processar evento JSON-LD: {e} na URL {url}")
                    continue
        else:
            log(f"  ↳ Nenhum JSON-LD de SportsEvent encontrado. Tentando parsear DOM.")
            stats["method"] = "DOM"
            soup = BeautifulSoup(driver.page_source, "html.parser")
            new_events.extend(parse_dom_matches(soup, game_key, cfg, target_day, existing_uids, stats))

    except TimeoutException:
        stats["timeouts_load"] += 1
        log(f"  ↳ Timeout ao carregar a página ou aguardar elementos em {game_key}")
    except Exception as e:
        log(f"❌ Erro ao raspar {game_key} em {url}: {e}")

    return new_events, stats


# -------------------- Main Execution --------------------
if __name__ == "__main__":
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
            log(f"  scripts={stats['scripts_total']} sports={stats['sports_events']} "
                f"dom_matches={stats['dom_matches_found']} added={stats['added']}")
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
