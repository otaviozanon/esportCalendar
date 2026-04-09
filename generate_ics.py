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

# Removido: from webdriver_manager.chrome import ChromeDriverManager


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

    # A linha abaixo foi removida, pois undetected_chromedriver já lida com isso
    # options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False) # Outra opção anti-detecção

    # undetected_chromedriver já gerencia o Chromedriver, não precisa de Service
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
    return {str(event["UID"]) for event in cal.walk("VEVENT")}


def prune_older_than(cal: Calendar, cutoff_date: date) -> int:
    events_to_keep = []
    removed_count = 0
    for component in cal.walk():
        if component.name == "VEVENT":
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

    # Reconstroi o calendário com os eventos a serem mantidos
    new_cal = Calendar()
    for prop in cal.property_items():
        if prop[0] != "VEVENT": # Copia todas as propriedades que não são eventos
            new_cal.add(prop[0], prop[1])
    for event in events_to_keep:
        if event.name == "VEVENT":
            new_cal.add_component(event)
    cal.clear()
    for component in new_cal.walk():
        cal.add_component(component)
    return removed_count


def dedupe_calendar_events(cal: Calendar) -> int:
    unique_events = {}
    removed_count = 0
    for event in cal.walk("VEVENT"):
        uid = str(event["UID"])
        if uid in unique_events:
            removed_count += 1
        else:
            unique_events[uid] = event

    # Reconstroi o calendário com eventos únicos
    new_cal = Calendar()
    for prop in cal.property_items():
        if prop[0] != "VEVENT":
            new_cal.add(prop[0], prop[1])
    for event in unique_events.values():
        new_cal.add_component(event)
    cal.clear()
    for component in new_cal.walk():
        cal.add_component(component)
    return removed_count


def dedupe_by_url_keep_latest(cal: Calendar) -> int:
    events_by_url = {}
    removed_count = 0

    for event in cal.walk("VEVENT"):
        url = str(event.get("URL", ""))
        if not url:
            continue

        dtstart = event.get("dtstart").dt
        if isinstance(dtstart, date) and not isinstance(dtstart, datetime):
            # Converte date para datetime para comparação
            dtstart = datetime.combine(dtstart, datetime.min.time(), tzinfo=BR_TZ)
        elif isinstance(dtstart, datetime) and dtstart.tzinfo is None:
            # Assume BR_TZ se não tiver timezone
            dtstart = BR_TZ.localize(dtstart)
        elif isinstance(dtstart, datetime) and dtstart.tzinfo is not None:
            # Converte para BR_TZ para comparação consistente
            dtstart = dtstart.astimezone(BR_TZ)

        if url not in events_by_url or dtstart > events_by_url[url].get("dtstart").dt.astimezone(BR_TZ):
            if url in events_by_url:
                removed_count += 1
            events_by_url[url] = event
        else:
            removed_count += 1

    new_cal = Calendar()
    for prop in cal.property_items():
        if prop[0] != "VEVENT":
            new_cal.add(prop[0], prop[1])
    for event in events_by_url.values():
        new_cal.add_component(event)
    cal.clear()
    for component in new_cal.walk():
        cal.add_component(component)
    return removed_count


def load_cursor(today: date, future_limit: date) -> date:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
            cursor_str = state.get("cursor_date")
            if cursor_str:
                cursor_date = datetime.strptime(cursor_str, "%Y-%m-%d").date()
                if today <= cursor_date <= future_limit:
                    return cursor_date
    return today


def save_cursor(date_to_save: date):
    with open(STATE_FILE, "w") as f:
        json.dump({"cursor_date": date_to_save.strftime("%Y-%m-%d")}, f)


# -------------------- Scraping Logic --------------------
def build_url_for_day(base_path: str, target_date: date) -> str:
    if target_date == datetime.now(BR_TZ).date():
        return base_path # URL para "hoje" não tem data
    return f"{base_path}{target_date.strftime('%d-%m-%Y')}/"


def extract_jsonld_via_js(driver) -> list:
    # Busca por scripts que contenham "@type":"SportsEvent"
    # Isso contorna a modificação do 'type' pelo Cloudflare Rocket Loader
    script_contents = driver.execute_script("""
        return Array.from(document.querySelectorAll('script'))
            .map(s => s.textContent)
            .filter(text => text.includes('"@type":"SportsEvent"') && text.startsWith('{'));
    """)

    json_ld_data_list = []
    for content in script_contents:
        try:
            data = json.loads(content)
            if data.get("@type") == "SportsEvent":
                json_ld_data_list.append(data)
        except json.JSONDecodeError:
            pass
    return json_ld_data_list


def parse_jsonld_event(json_data: dict, game_key: str, cfg: dict, target_day: date, existing_uids: set, stats: dict) -> Event | None:
    try:
        event_name = json_data.get("name")
        description = json_data.get("description")
        url = json_data.get("url")
        start_date_str = json_data.get("startDate")
        organizer_name = json_data.get("organizer", {}).get("name")

        if not event_name or not start_date_str or not url:
            stats["skipped_bad_date"] += 1
            return None

        # Parse startDate com offset de timezone
        dt_start_br = datetime.fromisoformat(start_date_str)
        dt_start_utc = dt_start_br.astimezone(pytz.utc)

        # Verificar se a partida já passou (usando UTC para consistência)
        if dt_start_utc < datetime.now(pytz.utc):
            stats["skipped_past"] += 1
            return None

        # Verificar se a partida é para o dia alvo
        if dt_start_br.date() != target_day:
            stats["skipped_bad_date"] += 1
            return None

        team1_name = json_data.get("competitor", [{}])[0].get("name")
        team2_name = json_data.get("competitor", [{}, {}])[1].get("name")

        if not team1_name or not team2_name:
            stats["skipped_tbd"] += 1
            return None

        norm_team1 = normalize_team(team1_name)
        norm_team2 = normalize_team(team2_name)

        # Verificar exclusões
        if norm_team1 in cfg["exclusions_norm"] or norm_team2 in cfg["exclusions_norm"]:
            stats["skipped_not_allowed"] += 1
            return None

        # Verificar se algum dos times é de interesse
        if not (norm_team1 in cfg["teams_norm"] or norm_team2 in cfg["teams_norm"]):
            stats["skipped_not_allowed"] += 1
            return None

        # Extrair torneio da URL se não estiver no organizer
        tournament_name = organizer_name
        if not tournament_name and url:
            parts = url.split('/')
            if len(parts) >= 3 and parts[-3] != "matches": # Ex: /matches/counter-strike/09-04-2026/mibr-vs-3dmax/08-00/
                tournament_name = parts[-3].replace('-', ' ').title() # Tenta pegar o torneio da URL

        summary = f"{cfg['prefix']}{team1_name} vs {team2_name}"
        if tournament_name:
            summary += f" ({tournament_name})"

        event_uid = hashlib.sha1(url.encode()).hexdigest()
        if event_uid in existing_uids:
            return None # Já existe, pular

        event = Event()
        event.add("summary", summary)
        event.add("dtstart", dt_start_utc)
        event.add("dtend", dt_start_utc + timedelta(hours=3)) # Duração padrão de 3 horas
        event.add("description", description or "Partida de E-sports")
        event.add("location", "Online")
        event.add("url", f"https://tips.gg{url}")
        event.add("uid", event_uid)
        event.add("dtstamp", datetime.now(pytz.utc))
        event.add("categories", [game_key])
        event.add("x-alt-desc", f"Partida de {game_key}: {team1_name} vs {team2_name}. Torneio: {tournament_name or 'N/A'}. Veja mais em: https://tips.gg{url}")
        event.add("X-SETT-SOURCE", SOURCE_MARKER) # Marcador para identificar nossos eventos

        # Adicionar alarme 30 minutos antes
        alarm = Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add("description", f"Lembrete: {summary}")
        alarm.add("trigger", timedelta(minutes=-30))
        event.add_component(alarm)

        stats["added"] += 1
        stats["sports_events"] += 1
        return event

    except Exception as e:
        log(f"  ↳ Erro ao parsear JSON-LD: {e} - Data: {json_data}")
        stats["json_decode_errors"] += 1
        return None


def parse_dom_matches(soup: BeautifulSoup, game_key: str, cfg: dict, target_day: date, existing_uids: set, stats: dict) -> list:
    events = []
    match_elements = soup.select("div.element.match.upcoming")
    stats["dom_matches_found"] = len(match_elements)

    for match_el in match_elements:
        try:
            match_link_el = match_el.select_one("a.match-link")
            if not match_link_el:
                continue

            url_suffix = match_link_el["href"]
            full_url = f"https://tips.gg{url_suffix}"

            # Extrair times
            team_names_els = match_el.select(".teams .team .name")
            if len(team_names_els) < 2:
                continue
            team1_name = team_names_els[0].get_text(strip=True)
            team2_name = team_names_els[1].get_text(strip=True)

            # Extrair horário
            time_str = match_el.select_one(".info .time").get_text(strip=True)
            # O HTML indica que o horário é local (BR_TZ), mas o JSON-LD usa -0300.
            # Vamos assumir que o horário no DOM é o mesmo do JSON-LD (BR_TZ)
            match_datetime_str = f"{target_day.strftime('%Y-%m-%d')} {time_str}"
            dt_start_br = BR_TZ.localize(datetime.strptime(match_datetime_str, "%Y-%m-%d %H:%M"))
            dt_start_utc = dt_start_br.astimezone(pytz.utc)

            # Verificar se a partida já passou (usando UTC para consistência)
            if dt_start_utc < datetime.now(pytz.utc):
                stats["skipped_past"] += 1
                continue

            norm_team1 = normalize_team(team1_name)
            norm_team2 = normalize_team(team2_name)

            # Verificar exclusões
            if norm_team1 in cfg["exclusions_norm"] or norm_team2 in cfg["exclusions_norm"]:
                stats["skipped_not_allowed"] += 1
                continue

            # Verificar se algum dos times é de interesse
            if not (norm_team1 in cfg["teams_norm"] or norm_team2 in cfg["teams_norm"]):
                stats["skipped_not_allowed"] += 1
                continue

            # Extrair torneio
            tournament_el = match_el.find_previous_sibling("div", class_="header").select_one(".tournament-link.title h2")
            tournament_name = tournament_el.get_text(strip=True) if tournament_el else "N/A"

            summary = f"{cfg['prefix']}{team1_name} vs {team2_name}"
            if tournament_name:
                summary += f" ({tournament_name})"

            event_uid = hashlib.sha1(full_url.encode()).hexdigest()
            if event_uid in existing_uids:
                continue # Já existe, pular

            event = Event()
            event.add("summary", summary)
            event.add("dtstart", dt_start_utc)
            event.add("dtend", dt_start_utc + timedelta(hours=3)) # Duração padrão de 3 horas
            event.add("description", f"Partida de {game_key}: {team1_name} vs {team2_name}. Torneio: {tournament_name}.")
            event.add("location", "Online")
            event.add("url", full_url)
            event.add("uid", event_uid)
            event.add("dtstamp", datetime.now(pytz.utc))
            event.add("categories", [game_key])
            event.add("x-alt-desc", f"Partida de {game_key}: {team1_name} vs {team2_name}. Torneio: {tournament_name}. Veja mais em: {full_url}")
            event.add("X-SETT-SOURCE", SOURCE_MARKER) # Marcador para identificar nossos eventos

            # Adicionar alarme 30 minutos antes
            alarm = Alarm()
            alarm.add("action", "DISPLAY")
            alarm.add("description", f"Lembrete: {summary}")
            alarm.add("trigger", timedelta(minutes=-30))
            event.add_component(alarm)

            stats["added"] += 1
            stats["dom_matches_found"] += 1 # Contar como dom_matches_found aqui também
            events.append(event)

        except Exception as e:
            log(f"  ↳ Erro ao parsear DOM para uma partida: {e} - Elemento: {match_el.prettify()[:200]}...")
            stats["json_decode_errors"] += 1 # Usar este contador para erros de parse de DOM também
            continue
    return events


def scrape_one_day_for_game(driver, game_key: str, cfg: dict, target_day: date, existing_uids: set) -> tuple[list, dict]:
    all_new_events = []
    stats = {
        "date": target_day.strftime("%Y-%m-%d"),
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

    try:
        url = build_url_for_day(cfg["base_path"], target_day)
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
