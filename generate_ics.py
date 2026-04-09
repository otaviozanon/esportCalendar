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

    # A linha abaixo foi removida, pois undetected_chromedriver já lida com isso
    # options.add_experimental_option('useAutomationExtension', False)

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

    cal.clear()
    for event in events_to_keep:
        cal.add_component(event)
    return removed_count


def dedupe_calendar_events(cal: Calendar) -> int:
    unique_events = {}
    removed_count = 0
    for component in cal.walk():
        if component.name == "VEVENT":
            uid = str(component["UID"])
            if uid in unique_events:
                removed_count += 1
            else:
                unique_events[uid] = component
        else:
            # Keep non-event components as is
            pass

    cal.clear()
    for event in unique_events.values():
        cal.add_component(event)
    return removed_count


def dedupe_by_url_keep_latest(cal: Calendar) -> int:
    events_by_url = {}
    removed_count = 0

    for component in cal.walk():
        if component.name == "VEVENT":
            description = str(component.get("DESCRIPTION", ""))
            if SOURCE_MARKER in description:
                # Extract URL from description
                start_idx = description.find(TIPS_URL_HINT)
                if start_idx != -1:
                    end_idx = description.find("\n", start_idx)
                    if end_idx == -1:
                        end_idx = len(description)
                    url = description[start_idx:end_idx].strip()

                    if url:
                        current_event = events_by_url.get(url)
                        if current_event:
                            # Compare DTSTAMP to keep the latest
                            current_dtstamp = current_event.get("DTSTAMP").dt
                            new_dtstamp = component.get("DTSTAMP").dt
                            if new_dtstamp > current_dtstamp:
                                events_by_url[url] = component
                                removed_count += 1 # Replaced an older event
                            else:
                                removed_count += 1 # Discarded the new (older) event
                        else:
                            events_by_url[url] = component
                    else:
                        # No URL found, treat as unique by UID
                        uid = str(component["UID"])
                        if uid not in events_by_url: # Avoids adding if a URL-based event already used this UID
                            events_by_url[uid] = component
                        else:
                            removed_count += 1
                else:
                    # No TIPS_URL_HINT, treat as unique by UID
                    uid = str(component["UID"])
                    if uid not in events_by_url:
                        events_by_url[uid] = component
                    else:
                        removed_count += 1
            else:
                # Not our event, treat as unique by UID
                uid = str(component["UID"])
                if uid not in events_by_url:
                    events_by_url[uid] = component
                else:
                    removed_count += 1
        else:
            # Keep non-event components as is
            pass

    cal.clear()
    for event in events_by_url.values():
        cal.add_component(event)
    return removed_count


def save_cursor(day: date):
    with open(STATE_FILE, "w") as f:
        json.dump({"last_scraped_date": day.isoformat()}, f)


def load_cursor(today: date, future_limit: date) -> date:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
            last_date_str = state.get("last_scraped_date")
            if last_date_str:
                last_date = date.fromisoformat(last_date_str)
                if last_date < future_limit:
                    return last_date
    return today


# -------------------- Parsing Functions --------------------
def parse_jsonld_event(json_data: dict, game_key: str, cfg: dict, target_day: date, existing_uids: set, stats: dict) -> Event | None:
    try:
        if json_data.get("@type") != "SportsEvent":
            return None

        name = json_data.get("name", "")
        description = json_data.get("description", "")
        url = json_data.get("url", "")
        start_date_str = json_data.get("startDate")
        end_date_str = json_data.get("endDate")
        organizer_name = json_data.get("organizer", {}).get("name", "N/A")

        if not start_date_str:
            stats["skipped_bad_date"] += 1
            return None

        # datetime.fromisoformat() pode lidar com offsets de timezone como -0300
        start_dt_local = datetime.fromisoformat(start_date_str)
        start_dt_utc = start_dt_local.astimezone(pytz.utc)

        # Verificar se a partida já passou
        if start_dt_utc < datetime.now(pytz.utc) - timedelta(minutes=30): # 30 minutos de margem
            stats["skipped_past"] += 1
            return None

        # Verificar se a partida é para o dia alvo
        if start_dt_local.date() != target_day:
            stats["skipped_bad_date"] += 1
            return None

        teams = [comp.get("name") for comp in json_data.get("competitor", []) if comp.get("name")]
        team1_name = teams[0] if len(teams) > 0 else "TBD"
        team2_name = teams[1] if len(teams) > 1 else "TBD"

        if team1_name == "TBD" or team2_name == "TBD":
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

        summary = f"{cfg['prefix']}{team1_name} vs {team2_name} ({organizer_name})"
        full_description = (
            f"{description}\n"
            f"Tournament: {organizer_name}\n"
            f"Teams: {team1_name} vs {team2_name}\n"
            f"URL: {TIPS_URL_HINT.rstrip('/')}{url}\n"
            f"{SOURCE_MARKER}"
        )

        # Gerar UID consistente
        event_uid_data = f"{url}-{start_dt_utc.isoformat()}"
        uid = hashlib.sha1(event_uid_data.encode()).hexdigest() + "@tips.gg"

        if uid in existing_uids:
            return None # Já existe, não adicionar

        event = Event()
        event.add("SUMMARY", summary)
        event.add("DTSTART", start_dt_utc)
        if end_date_str:
            end_dt_local = datetime.fromisoformat(end_date_str)
            end_dt_utc = end_dt_local.astimezone(pytz.utc)
            event.add("DTEND", end_dt_utc)
        else:
            # Se não houver DTEND, estimar 3 horas de duração
            event.add("DTEND", start_dt_utc + timedelta(hours=3))

        event.add("DESCRIPTION", full_description)
        event.add("LOCATION", "Online")
        event.add("UID", uid)
        event.add("DTSTAMP", datetime.now(pytz.utc)) # Timestamp de quando o evento foi adicionado/modificado

        # Adicionar alarme 30 minutos antes
        alarm = Alarm()
        alarm.add("ACTION", "DISPLAY")
        alarm.add("DESCRIPTION", summary)
        alarm.add("TRIGGER", timedelta(minutes=-30))
        event.add_component(alarm)

        stats["sports_events"] += 1
        stats["added"] += 1
        return event

    except Exception as e:
        log(f"  ↳ Erro ao parsear JSON-LD: {e} - Data: {json_data}")
        stats["json_decode_errors"] += 1
        return None


def parse_dom_matches(soup: BeautifulSoup, game_key: str, cfg: dict, target_day: date, existing_uids: set, stats: dict) -> list[Event]:
    dom_events = []
    match_elements = soup.select("div.element.match.upcoming")
    stats["dom_matches_found"] = len(match_elements)

    for match_el in match_elements:
        try:
            link_el = match_el.select_one("a.match-link")
            if not link_el:
                continue

            relative_url = link_el["href"]
            full_url = f"https://tips.gg{relative_url}"

            # Extrair times
            team_names = [name_el.get_text(strip=True) for name_el in match_el.select("div.team span.name")]
            if len(team_names) < 2:
                continue
            team1_name = team_names[0]
            team2_name = team_names[1]

            if team1_name == "TBD" or team2_name == "TBD":
                stats["skipped_tbd"] += 1
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

            # Extrair horário (o site mostra em horário local, mas precisamos converter para UTC)
            time_str = match_el.select_one("span.time").get_text(strip=True)
            # O HTML que você forneceu mostra 04:00, 07:00, 10:00, etc. para 09/04/2026.
            # O JSON-LD indica que esses horários já estão no fuso -0300.
            # Então, vamos combinar a data alvo com o horário e assumir o fuso BR_TZ.
            start_time = datetime.strptime(time_str, "%H:%M").time()
            start_dt_local = BR_TZ.localize(datetime.combine(target_day, start_time))
            start_dt_utc = start_dt_local.astimezone(pytz.utc)

            # Verificar se a partida já passou
            if start_dt_utc < datetime.now(pytz.utc) - timedelta(minutes=30):
                stats["skipped_past"] += 1
                continue

            # Extrair torneio
            tournament_el = match_el.find_previous(class_="header").select_one(".tournament-link.title h2")
            organizer_name = tournament_el.get_text(strip=True) if tournament_el else "N/A"

            summary = f"{cfg['prefix']}{team1_name} vs {team2_name} ({organizer_name})"
            full_description = (
                f"Tournament: {organizer_name}\n"
                f"Teams: {team1_name} vs {team2_name}\n"
                f"URL: {full_url}\n"
                f"{SOURCE_MARKER}"
            )

            # Gerar UID consistente
            event_uid_data = f"{full_url}-{start_dt_utc.isoformat()}"
            uid = hashlib.sha1(event_uid_data.encode()).hexdigest() + "@tips.gg"

            if uid in existing_uids:
                continue # Já existe, não adicionar

            event = Event()
            event.add("SUMMARY", summary)
            event.add("DTSTART", start_dt_utc)
            event.add("DTEND", start_dt_utc + timedelta(hours=3)) # Estimar 3 horas de duração
            event.add("DESCRIPTION", full_description)
            event.add("LOCATION", "Online")
            event.add("UID", uid)
            event.add("DTSTAMP", datetime.now(pytz.utc))

            # Adicionar alarme 30 minutos antes
            alarm = Alarm()
            alarm.add("ACTION", "DISPLAY")
            alarm.add("DESCRIPTION", summary)
            alarm.add("TRIGGER", timedelta(minutes=-30))
            event.add_component(alarm)

            dom_events.append(event)
            stats["added"] += 1

        except Exception as e:
            log(f"  ↳ Erro ao parsear DOM para uma partida: {e} - Elemento: {match_el.prettify()[:200]}...")
            stats["json_decode_errors"] += 1 # Reutilizando para erros de parse DOM

    return dom_events


def extract_jsonld_via_js(driver) -> list[dict]:
    # Este script JavaScript busca todos os elementos <script> na página
    # e tenta parsear seu textContent como JSON, filtrando por SportsEvent.
    js_script = """
    let jsonLdData = [];
    document.querySelectorAll('script').forEach(script => {
        const text = script.textContent.trim();
        if (text.startsWith('{') && text.includes('"@type":"SportsEvent"')) {
            try {
                const data = JSON.parse(text);
                jsonLdData.push(data);
            } catch (e) {
                // console.error("Failed to parse JSON-LD:", e);
            }
        }
    });
    return jsonLdData;
    """
    return driver.execute_script(js_script)


# -------------------- Scrape Logic --------------------
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
