import os
import json
import hashlib
import time
from datetime import datetime, timedelta, date

import pytz
from bs4 import BeautifulSoup
from icalendar import Calendar, Event, Alarm

# Importar undetected_chromedriver
import undetected_chromedriver as uc
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException


# -------------------- Configurações Globais --------------------
CALENDAR_FILENAME = "calendar.ics"
STATE_FILE = "state.json"

BR_TZ = pytz.timezone("America/Sao_Paulo")

FUTURE_LIMIT_DAYS = 4
DELETE_OLDER_THAN_DAYS = 7

PAGE_LOAD_TIMEOUT_SECONDS = 60  # Aumentado para dar bastante tempo
MATCH_WAIT_SECONDS = 45         # Aumentado para dar bastante tempo para o JS carregar

SOURCE_MARKER = "X-SETT-SOURCE:TIPSGG"
TIPS_URL_HINT = "https://tips.gg/matches/"

# User-Agents comuns para tentar evitar detecção (undetected_chromedriver já gerencia isso, mas é bom ter um fallback)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


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
    options.add_argument("--log-level=3") # Suprime logs desnecessários do Chrome
    options.add_argument(f"user-agent={USER_AGENTS[0]}") # Define um user-agent

    driver = uc.Chrome(options=options, use_subprocess=True)
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT_SECONDS)
    return driver


# -------------------- Calendar Functions --------------------
def load_calendar(filename: str) -> Calendar:
    if os.path.exists(filename):
        with open(filename, "rb") as f:
            return Calendar.from_ical(f.read())
    return Calendar()


def save_calendar(cal: Calendar, filename: str):
    with open(filename, "wb") as f:
        f.write(cal.to_ical())


def get_existing_uids(cal: Calendar) -> set:
    # Adiciona uma verificação para 'UID' antes de tentar acessá-lo
    return {str(event["UID"]) for event in cal.walk("VEVENT") if "UID" in event}


def prune_older_than(cal: Calendar, cutoff_date: date) -> int:
    events_to_keep = []
    removed_count = 0
    for component in cal.walk():
        if component.name == "VEVENT":
            # Adiciona uma verificação para 'UID' aqui também, para consistência
            if "UID" not in component:
                log(f"⚠️ Evento sem UID encontrado durante a limpeza: {component.get('SUMMARY', 'Sem Sumário')}. Será mantido.")
                events_to_keep.append(component)
                continue

            event_dt_start = component.get("dtstart").dt
            if isinstance(event_dt_start, datetime):
                event_date = event_dt_start.date()
            elif isinstance(event_dt_start, date):
                event_date = event_dt_start
            else:
                event_date = None

            if event_date and event_date < cutoff_date:
                removed_count += 1
            else:
                events_to_keep.append(component)
        else:
            events_to_keep.append(component)

    cal.clear()
    for event in events_to_keep:
        cal.add_component(event)
    return removed_count


def dedupe_calendar_events(cal: Calendar) -> int:
    unique_events = {}
    removed_count = 0
    for component in cal.walk("VEVENT"):
        # Adiciona uma verificação para 'UID' antes de tentar acessá-lo
        if "UID" not in component:
            log(f"⚠️ Evento sem UID encontrado durante a dedup: {component.get('SUMMARY', 'Sem Sumário')}. Será ignorado na dedup.")
            continue # Ignora eventos sem UID para a dedup por UID

        uid = str(component["UID"])
        if uid in unique_events:
            removed_count += 1
        else:
            unique_events[uid] = component

    # Reconstroi o calendário com eventos únicos
    cal.clear()
    for event in unique_events.values():
        cal.add_component(event)
    return removed_count


def dedupe_by_url_keep_latest(cal: Calendar) -> int:
    events_by_url = {}
    removed_count = 0
    for component in cal.walk("VEVENT"):
        # Adiciona uma verificação para 'UID' e 'URL'
        if "UID" not in component or "URL" not in component:
            log(f"⚠️ Evento sem UID ou URL encontrado durante a dedup por URL: {component.get('SUMMARY', 'Sem Sumário')}. Será ignorado na dedup.")
            continue

        url = str(component["URL"])
        dtstamp = component.get("DTSTAMP").dt if "DTSTAMP" in component else datetime.min.replace(tzinfo=pytz.utc)

        if url not in events_by_url or dtstamp > events_by_url[url].get("DTSTAMP").dt:
            events_by_url[url] = component
        else:
            removed_count += 1

    cal.clear()
    for event in events_by_url.values():
        cal.add_component(event)
    return removed_count


# -------------------- Cursor Management --------------------
def load_cursor(default_day: date, future_limit: date) -> date:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
            cursor_str = state.get("last_scraped_day")
            if cursor_str:
                cursor_date = datetime.strptime(cursor_str, "%Y-%m-%d").date()
                # Garante que o cursor não avance para além do limite futuro
                if cursor_date <= future_limit:
                    return cursor_date
    return default_day


def save_cursor(day: date):
    with open(STATE_FILE, "w") as f:
        json.dump({"last_scraped_day": day.strftime("%Y-%m-%d")}, f)


# -------------------- URL Building --------------------
def build_url_for_day(base_path: str, target_day: date) -> str:
    today = datetime.now(BR_TZ).date()
    if target_day == today:
        return base_path # Para hoje, a URL não tem data
    else:
        return f"{base_path}{target_day.strftime('%d-%m-%Y')}/"


# -------------------- Event Parsing --------------------
def parse_jsonld_event(json_data: dict, game_key: str, cfg: dict, target_day: date, existing_uids: set, stats: dict) -> Event | None:
    try:
        if json_data.get("@type") != "SportsEvent":
            return None

        event_name = json_data.get("name")
        start_date_str = json_data.get("startDate")
        end_date_str = json_data.get("endDate")
        url_suffix = json_data.get("url")
        organizer_name = json_data.get("organizer", {}).get("name")
        competitors = json_data.get("competitor", [])

        if not event_name or not start_date_str or not url_suffix:
            log(f"  ⚠️ JSON-LD incompleto (nome, data ou URL ausente): {json_data.get('name', 'N/A')}")
            stats["skipped_bad_date"] += 1
            return None

        # Parsear datas com offset de timezone
        start_dt = datetime.fromisoformat(start_date_str)
        end_dt = datetime.fromisoformat(end_date_str) if end_date_str else start_dt + timedelta(hours=3) # Estima 3h se não houver end_date

        # Converter para UTC
        start_dt_utc = start_dt.astimezone(pytz.utc)
        end_dt_utc = end_dt.astimezone(pytz.utc)

        # Verificar se a partida já passou
        if start_dt_utc < datetime.now(pytz.utc):
            stats["skipped_past"] += 1
            return None

        # Verificar se é TBD
        if "TBD" in event_name.upper() or any("TBD" in comp.get("name", "").upper() for comp in competitors):
            stats["skipped_tbd"] += 1
            return None

        # Verificar times permitidos e excluídos
        team_names = [comp.get("name") for comp in competitors if comp.get("name")]
        normalized_team_names = {normalize_team(t) for t in team_names}

        if not (normalized_team_names & cfg["teams_norm"]):
            stats["skipped_not_allowed"] += 1
            return None

        if normalized_team_names & cfg["exclusions_norm"]:
            stats["skipped_not_allowed"] += 1
            return None

        # Construir URL completa
        full_url = f"https://tips.gg{url_suffix}"

        # Gerar UID
        uid_hash = hashlib.sha1(full_url.encode()).hexdigest()
        uid = f"{game_key}-{uid_hash}"

        if uid in existing_uids:
            return None # Já existe, não adiciona

        event = Event()
        event.add("SUMMARY", f"{cfg['prefix']}{event_name}")
        event.add("DTSTART", start_dt_utc)
        event.add("DTEND", end_dt_utc)
        event.add("DTSTAMP", datetime.now(pytz.utc))
        event.add("UID", uid)
        event.add("URL", full_url)
        event.add("DESCRIPTION", f"Torneio: {organizer_name or 'N/A'}\nLink: {full_url}")
        event.add("CATEGORIES", game_key)
        event.add("X-SETT-SOURCE", SOURCE_MARKER)

        # Adicionar alarme 15 minutos antes
        alarm = Alarm()
        alarm.add("ACTION", "DISPLAY")
        alarm.add("DESCRIPTION", f"Lembrete: {cfg['prefix']}{event_name}")
        alarm.add("TRIGGER", timedelta(minutes=-15))
        event.add_component(alarm)

        stats["sports_events"] += 1
        stats["added"] += 1
        return event

    except Exception as e:
        log(f"  ❌ Erro ao parsear JSON-LD: {e} - Dados: {json_data.get('name', 'N/A')}")
        stats["json_decode_errors"] += 1
        return None


def parse_dom_matches(soup: BeautifulSoup, game_key: str, cfg: dict, target_day: date, existing_uids: set, stats: dict) -> list[Event]:
    events = []
    matches = soup.select("div.element.match.upcoming")
    stats["dom_matches_found"] = len(matches)

    for match in matches:
        try:
            team_elements = match.select("div.team span.name")
            if len(team_elements) < 2:
                continue

            team1_name = team_elements[0].get_text(strip=True)
            team2_name = team_elements[1].get_text(strip=True)

            # Verificar times permitidos e excluídos
            normalized_team_names = {normalize_team(team1_name), normalize_team(team2_name)}

            if not (normalized_team_names & cfg["teams_norm"]):
                stats["skipped_not_allowed"] += 1
                continue

            if normalized_team_names & cfg["exclusions_norm"]:
                stats["skipped_not_allowed"] += 1
                continue

            match_time_str = match.select_one("span.time").get_text(strip=True)
            match_link_suffix = match.select_one("a.match-link")["href"]

            # A URL do torneio está no header acima do bloco de partidas
            tournament_element = match.find_previous("div", class_="header").select_one("a.tournament-link h2")
            tournament_name = tournament_element.get_text(strip=True) if tournament_element else "N/A"

            # A data já é a target_day
            # O horário do site é exibido no fuso horário do usuário (BR_TZ)
            try:
                match_datetime_local = BR_TZ.localize(datetime.strptime(f"{target_day} {match_time_str}", "%Y-%m-%d %H:%M"))
                start_dt_utc = match_datetime_local.astimezone(pytz.utc)
                end_dt_utc = start_dt_utc + timedelta(hours=3) # Estima 3h de duração
            except ValueError:
                stats["skipped_bad_date"] += 1
                continue

            # Verificar se a partida já passou
            if start_dt_utc < datetime.now(pytz.utc):
                stats["skipped_past"] += 1
                continue

            event_name = f"{team1_name} vs {team2_name}"
            full_url = f"https://tips.gg{match_link_suffix}"

            # Gerar UID
            uid_hash = hashlib.sha1(full_url.encode()).hexdigest()
            uid = f"{game_key}-{uid_hash}"

            if uid in existing_uids:
                continue # Já existe, não adiciona

            event = Event()
            event.add("SUMMARY", f"{cfg['prefix']}{event_name}")
            event.add("DTSTART", start_dt_utc)
            event.add("DTEND", end_dt_utc)
            event.add("DTSTAMP", datetime.now(pytz.utc))
            event.add("UID", uid)
            event.add("URL", full_url)
            event.add("DESCRIPTION", f"Torneio: {tournament_name}\nLink: {full_url}")
            event.add("CATEGORIES", game_key)
            event.add("X-SETT-SOURCE", SOURCE_MARKER)

            # Adicionar alarme 15 minutos antes
            alarm = Alarm()
            alarm.add("ACTION", "DISPLAY")
            alarm.add("DESCRIPTION", f"Lembrete: {cfg['prefix']}{event_name}")
            alarm.add("TRIGGER", timedelta(minutes=-15))
            event.add_component(alarm)

            events.append(event)
            stats["added"] += 1

        except Exception as e:
            log(f"  ❌ Erro ao parsear partida DOM: {e} - HTML: {match.prettify()[:200]}...")
            stats["json_decode_errors"] += 1 # Reutilizando para erros de parse DOM
            continue
    return events


def extract_jsonld_via_js(driver) -> list[dict]:
    # Executa JavaScript para encontrar todos os scripts com conteúdo JSON-LD
    # e retorna seus textContents
    script = """
    let jsonLdScripts = [];
    document.querySelectorAll('script').forEach(s => {
        if (s.textContent.includes('"@type":"SportsEvent"') && s.textContent.startsWith('{')) {
            jsonLdScripts.push(s.textContent);
        }
    });
    return jsonLdScripts;
    """
    json_ld_strings = driver.execute_script(script)

    parsed_data = []
    for s in json_ld_strings:
        try:
            data = json.loads(s)
            parsed_data.append(data)
        except json.JSONDecodeError as e:
            log(f"  ❌ Erro ao decodificar JSON-LD via JS: {e} - String: {s[:100]}...")
            # stats["json_decode_errors"] += 1 # Não temos acesso a stats aqui
    return parsed_data


def scrape_one_day_for_game(driver, game_key: str, cfg: dict, target_day: date, existing_uids: set) -> tuple[list[Event], dict]:
    all_new_events = []
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

    url = build_url_for_day(cfg["base_path"], target_day)

    try:
        driver.get(url)

        # Esperar por um elemento principal de matches ou o body
        WebDriverWait(driver, PAGE_LOAD_TIMEOUT_SECONDS).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.content-block.matches"))
        )
        log(f"  Página carregada e elemento principal encontrado em {game_key}.")
        time.sleep(5) # Dar um tempo extra para o JS do site renderizar tudo

        # Tentar extrair JSON-LD primeiro
        log("  Tentando extrair JSON-LD via JavaScript...")
        json_ld_data_list = extract_jsonld_via_js(driver)
        stats["scripts_total"] = len(json_ld_data_list)

        if json_ld_data_list:
            log(f"  {len(json_ld_data_list)} scripts JSON-LD encontrados.")
            for json_data in json_ld_data_list:
                event = parse_jsonld_event(json_data, game_key, cfg, target_day, existing_uids, stats)
                if event:
                    all_new_events.append(event)

            if all_new_events:
                stats["method"] = "JSON-LD"
                log(f"  {len(all_new_events)} eventos adicionados via JSON-LD.")
                return all_new_events, stats
        else:
            log("  Nenhum JSON-LD de SportsEvent encontrado ou parseado.")
            stats["timeouts_jsonld"] += 1 # Conta como timeout se não encontrar JSON-LD

        # Fallback para parse do DOM se JSON-LD não funcionar
        log("  Tentando parsear via DOM (fallback)...")
        # Esperar por pelo menos um elemento de partida no DOM antes de parsear
        WebDriverWait(driver, MATCH_WAIT_SECONDS).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.element.match.upcoming"))
        )
        soup = BeautifulSoup(driver.page_source, "html.parser")
        dom_events = parse_dom_matches(soup, game_key, cfg, target_day, existing_uids, stats)
        all_new_events.extend(dom_events)

        if dom_events:
            stats["method"] = "DOM"
            log(f"  {len(dom_events)} eventos adicionados via DOM.")
        else:
            log(f"  Nenhuma partida encontrada em {game_key} para {target_day.strftime('%d/%m/%Y')}")

    except TimeoutException:
        log(f"  ↳ Timeout ao carregar a página ou aguardar elementos em {game_key}.")
        stats["timeouts_load"] += 1
    except Exception as e:
        log(f"  ↳ Erro durante a raspagem de {game_key}: {e}")

    return all_new_events, stats


# -------------------- Main Execution --------------------
if __name__ == "__main__":
    log("🔄 Iniciando execução (cursor rotativo)...")

    cal = load_calendar(CALENDAR_FILENAME)
    existing_uids = get_existing_uids(cal)

    deduped_initial = dedupe_calendar_events(cal)
    if deduped_initial:
        log(f"🧼 Deduplicação inicial: removidos {deduped_initial} eventos duplicados.")

    deduped_by_url_initial = dedupe_by_url_keep_latest(cal)
    if deduped_by_url_initial:
        log(f"🧼 Dedup por URL (inicial): removidos {deduped_by_url_initial} eventos.")

    today = datetime.now(BR_TZ).date()
    future_limit = today + timedelta(days=FUTURE_LIMIT_DAYS)

    cutoff = today - timedelta(days=DELETE_OLDER_THAN_DAYS)
    removed = prune_older_than(cal, cutoff)
    log(f"🧹 Limpeza: removidos {removed} eventos com data < {cutoff.strftime('%d/%m/%Y')}")

    target_day = today # Usar load_cursor para manter a persistência
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
