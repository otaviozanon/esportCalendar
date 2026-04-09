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

    # Adicionando mais argumentos para tentar evitar detecção
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--disable-extensions")
    options.add_argument("--start-maximized") # Pode ajudar na renderização

    # Usar undetected_chromedriver
    # Ele gerencia o Chromedriver automaticamente e aplica patches anti-detecção
    # Removido: driver_executable_path=ChromeDriverManager().install()
    driver = uc.Chrome(options=options) 
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


def create_event(
    summary: str,
    dtstart: datetime,
    dtend: datetime,
    url: str,
    description: str,
    uid: str,
) -> Event:
    event = Event()
    event.add("SUMMARY", summary)
    event.add("DTSTART", dtstart)
    event.add("DTEND", dtend)
    event.add("URL", url)
    event.add("DESCRIPTION", description)
    event.add("UID", uid)
    event.add("DTSTAMP", datetime.now(pytz.utc)) # Usar UTC para DTSTAMP

    # Adicionar alarme 15 minutos antes
    alarm = Alarm()
    alarm.add("ACTION", "DISPLAY")
    alarm.add("DESCRIPTION", summary)
    alarm.add("TRIGGER", timedelta(minutes=-15))
    event.add_component(alarm)

    return event


def generate_uid(url: str, start_time: datetime) -> str:
    # Gerar um UID único baseado na URL e no horário de início
    hash_input = f"{url}-{start_time.isoformat()}"
    return hashlib.md5(hash_input.encode("utf-8")).hexdigest() + "@tips.gg"


def prune_older_than(cal: Calendar, cutoff_date: date) -> int:
    to_remove = []
    for component in cal.walk("VEVENT"):
        if "DTSTART" in component:
            event_date = component["DTSTART"].dt.date()
            if event_date < cutoff_date:
                to_remove.append(component)
    for comp in to_remove:
        cal.subcomponents.remove(comp)
    return len(to_remove)


def dedupe_calendar_events(cal: Calendar) -> int:
    unique_events = {}
    removed_count = 0
    for event in cal.walk("VEVENT"):
        uid = str(event["UID"])
        if uid in unique_events:
            removed_count += 1
        else:
            unique_events[uid] = event
    cal.subcomponents = list(unique_events.values())
    return removed_count


def dedupe_by_url_keep_latest(cal: Calendar) -> int:
    events_by_url = {}
    for event in cal.walk("VEVENT"):
        url = str(event.get("URL"))
        if url:
            # Manter o evento mais recente para a mesma URL
            if url not in events_by_url or event["DTSTAMP"].dt > events_by_url[url]["DTSTAMP"].dt:
                events_by_url[url] = event

    original_count = len(list(cal.walk("VEVENT")))
    cal.subcomponents = list(events_by_url.values())
    return original_count - len(cal.subcomponents)


# -------------------- Scraping Logic --------------------
def build_url_for_day(base_path: str, target_day: date) -> str:
    # O site tips.gg usa o formato base_path/DD-MM-YYYY/ ou apenas base_path/ para o dia atual
    if target_day == datetime.now(BR_TZ).date():
        return base_path
    return f"{base_path}{target_day.strftime('%d-%m-%Y')}/"


def is_team_allowed(team_name: str, game_cfg: dict) -> bool:
    norm_name = normalize_team(team_name)
    if norm_name in game_cfg["teams_norm"]:
        return True
    if norm_name in game_cfg["exclusions_norm"]:
        return False
    return False # Por padrão, não permitir se não estiver na lista de times


def extract_jsonld_via_js(driver) -> list:
    """
    Extrai todos os scripts JSON-LD de SportsEvent da página usando JavaScript.
    Isso contorna a modificação do 'type' pelo Cloudflare Rocket Loader.
    """
    script = """
    let jsonLdScripts = [];
    document.querySelectorAll('script').forEach(s => {
        try {
            if (s.textContent.includes('"@type":"SportsEvent"') && s.textContent.startsWith('{')) {
                jsonLdScripts.push(JSON.parse(s.textContent));
            }
        } catch (e) {
            // console.error("Erro ao parsear JSON-LD:", e);
        }
    });
    return jsonLdScripts;
    """
    return driver.execute_script(script)


def parse_jsonld_event(
    json_data: dict, game_key: str, cfg: dict, target_day: date, existing_uids: set, stats: dict
) -> Event | None:
    if json_data.get("@type") != "SportsEvent":
        return None

    try:
        event_name = json_data.get("name", "N/A")
        start_date_str = json_data.get("startDate")
        event_url = json_data.get("url")
        organizer_name = json_data.get("organizer", {}).get("name", "N/A")

        if not start_date_str or not event_url:
            stats["skipped_bad_date"] += 1
            return None

        # Parsear a data com o offset de timezone (ex: 2026-04-09T04:00:00-0300)
        dt_start_br = datetime.fromisoformat(start_date_str)
        dt_start_utc = dt_start_br.astimezone(pytz.utc)

        # Verificar se a partida é para o dia alvo
        if dt_start_utc.date() != target_day:
            stats["skipped_bad_date"] += 1
            return None

        # Verificar se a partida já passou (considerando o horário atual em BR_TZ)
        now_br = datetime.now(BR_TZ)
        if dt_start_br < now_br - timedelta(minutes=15): # Dar uma margem de 15 minutos
            stats["skipped_past"] += 1
            return None

        # Extrair times
        competitors = json_data.get("competitor", [])
        team1_name = competitors[0].get("name") if len(competitors) > 0 else "TBD"
        team2_name = competitors[1].get("name") if len(competitors) > 1 else "TBD"

        if team1_name == "TBD" or team2_name == "TBD":
            stats["skipped_tbd"] += 1
            return None

        # Verificar se algum dos times é de interesse
        if not (is_team_allowed(team1_name, cfg) or is_team_allowed(team2_name, cfg)):
            stats["skipped_not_allowed"] += 1
            return None

        # Formatar summary e description
        summary = f"{cfg['prefix']}{team1_name} vs {team2_name} ({organizer_name})"
        description = f"Torneio: {organizer_name}\nURL: {event_url}\n"

        # O site retorna URL relativa, precisa da base
        full_event_url = f"https://tips.gg{event_url}" if event_url.startswith('/') else event_url

        # Calcular dt_end (assumindo 3 horas de duração para BO3, ou 1 hora para BO1/BO2)
        # O JSON-LD também pode ter endDate, vamos preferir ele se existir
        end_date_str = json_data.get("endDate")
        if end_date_str:
            dt_end_br = datetime.fromisoformat(end_date_str)
            dt_end_utc = dt_end_br.astimezone(pytz.utc)
        else:
            # Fallback: estimar duração
            description_text = json_data.get("description", "").lower()
            if "bo1" in description_text:
                dt_end_utc = dt_start_utc + timedelta(hours=1)
            elif "bo2" in description_text:
                dt_end_utc = dt_start_utc + timedelta(hours=2)
            else: # Padrão para BO3 ou desconhecido
                dt_end_utc = dt_start_utc + timedelta(hours=3)


        uid = generate_uid(full_event_url, dt_start_utc)
        if uid in existing_uids:
            return None # Já existe, pular

        stats["sports_events"] += 1
        stats["added"] += 1
        return create_event(summary, dt_start_utc, dt_end_utc, full_event_url, description, uid)

    except Exception as e:
        log(f"  ↳ Erro ao parsear JSON-LD de SportsEvent: {e} - Data: {json_data}")
        stats["json_decode_errors"] += 1
        return None


def parse_dom_matches(
    soup: BeautifulSoup, game_key: str, cfg: dict, target_day: date, existing_uids: set, stats: dict
) -> list[Event]:
    """
    Parses match data from the DOM structure if JSON-LD is not available.
    """
    events = []
    matches = soup.select("div.element.match.upcoming")
    stats["dom_matches_found"] = len(matches)

    for match_element in matches:
        try:
            # Extrair URL
            link_element = match_element.select_one("a.match-link")
            if not link_element:
                continue
            relative_url = link_element["href"]
            full_event_url = f"https://tips.gg{relative_url}" if relative_url.startswith('/') else relative_url

            # Extrair times
            team_names = [
                name_elem.get_text(strip=True)
                for name_elem in match_element.select("div.team span.name")
            ]
            if len(team_names) < 2:
                continue
            team1_name = team_names[0]
            team2_name = team_names[1]

            if team1_name == "TBD" or team2_name == "TBD":
                stats["skipped_tbd"] += 1
                continue

            if not (is_team_allowed(team1_name, cfg) or is_team_allowed(team2_name, cfg)):
                stats["skipped_not_allowed"] += 1
                continue

            # Extrair horário
            time_str = match_element.select_one("span.time").get_text(strip=True)

            # O site mostra o horário local (BR_TZ), então combinamos com a data alvo
            # e depois convertemos para UTC
            dt_start_br_naive = datetime.strptime(f"{target_day} {time_str}", "%Y-%m-%d %H:%M")
            dt_start_br = BR_TZ.localize(dt_start_br_naive)
            dt_start_utc = dt_start_br.astimezone(pytz.utc)

            # Verificar se a partida já passou (considerando o horário atual em BR_TZ)
            now_br = datetime.now(BR_TZ)
            if dt_start_br < now_br - timedelta(minutes=15): # Dar uma margem de 15 minutos
                stats["skipped_past"] += 1
                continue

            # Extrair torneio (do header ou da URL)
            tournament_title_element = match_element.find_previous(
                "div", class_="header"
            ).select_one("h2")
            organizer_name = (
                tournament_title_element.get_text(strip=True)
                if tournament_title_element
                else "Desconhecido"
            )

            # Tentar extrair o stage (Playoffs, Regular Season, etc.)
            stage_element = match_element.find_previous("div", class_="toggle-content").find_previous_sibling("div", class_="header").find_next_sibling("div", class_="performer")
            stage = stage_element.select_one("div.name").get_text(strip=True) if stage_element and stage_element.select_one("div.name") else ""

            if stage:
                organizer_name = f"{organizer_name} {stage}"

            summary = f"{cfg['prefix']}{team1_name} vs {team2_name} ({organizer_name})"
            description = f"Torneio: {organizer_name}\nURL: {full_event_url}\n"

            # Estimar duração (padrão 3 horas para BO3, 1 hora para BO1)
            # Sem JSON-LD, é mais difícil saber o formato (BO1, BO3, etc.)
            # Podemos tentar inferir da URL ou da descrição se houver
            dt_end_utc = dt_start_utc + timedelta(hours=3) # Padrão para 3 horas

            uid = generate_uid(full_event_url, dt_start_utc)
            if uid in existing_uids:
                continue

            stats["added"] += 1
            events.append(create_event(summary, dt_start_utc, dt_end_utc, full_event_url, description, uid))

        except Exception as e:
            log(f"  ↳ Erro ao parsear partida DOM: {e} - Elemento: {match_element}")
            stats["json_decode_errors"] += 1 # Reutilizando para erros de parse DOM

    return events


def scrape_one_day_for_game(
    driver, game_key: str, cfg: dict, target_day: date, existing_uids: set
) -> tuple[list[Event], dict]:
    """
    Navega para a página de um jogo para um dia específico e raspa eventos usando JSON-LD e, se falhar, DOM.
    """
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

    try:
        driver.get(build_url_for_day(cfg["base_path"], target_day))

        # Esperar por um elemento que indica que a página principal carregou e o Cloudflare passou
        # Pode ser o container principal de matches ou o body
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

    target_day = today# Usar load_cursor para manter a persistência
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
