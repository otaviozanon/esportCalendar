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

REQUEST_TIMEOUT = 30 # Mantido para referência, não usado diretamente pelo Selenium
REQUEST_DELAY = 2    # Mantido para referência, não usado diretamente pelo Selenium
PAGE_LOAD_TIMEOUT_SECONDS = 30 # Aumentado para dar mais tempo
MATCH_WAIT_SECONDS = 20 # Tempo para esperar por elementos de partida (JSON-LD ou DOM)

SOURCE_MARKER = "X-SETT-SOURCE:TIPSGG"
TIPS_URL_HINT = "https://tips.gg/matches/"

# User-Agents comuns para tentar evitar detecção
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
    # Adiciona um User-Agent comum para tentar evitar detecção
    options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
    # Remove flags que podem ser detectadas como automação
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT_SECONDS)
    return driver


# -------------------- Calendar Event Creation --------------------
def create_calendar_event(
    summary: str,
    description: str,
    start_time: datetime,
    end_time: datetime,
    url: str,
    uid_base: str,
) -> Event:
    event = Event()
    event.add("summary", summary)
    event.add("description", description)
    event.add("dtstart", start_time)
    event.add("dtend", end_time)
    event.add("url", url)
    event.add("uid", hashlib.md5(f"{uid_base}-{url}".encode()).hexdigest())
    event.add("dtstamp", datetime.now(pytz.utc))

    alarm = Alarm()
    alarm.add("action", "DISPLAY")
    alarm.add("description", summary)
    alarm.add("trigger", timedelta(minutes=-30))
    event.add_component(alarm)
    return event


# -------------------- Data Extraction --------------------
def extract_jsonld_via_js(driver) -> list:
    json_ld_scripts = driver.execute_script(
        """
        const scripts = document.querySelectorAll('script');
        const results = [];
        scripts.forEach(script => {
            const text = script.textContent;
            if (text.includes('"@type":"SportsEvent"') && text.startsWith('{')) {
                try {
                    results.push(JSON.parse(text));
                } catch (e) {
                    console.error("Erro ao parsear JSON-LD:", e);
                }
            }
        });
        return results;
        """
    )
    return json_ld_scripts


def parse_jsonld_event(json_data: dict, game_key: str, cfg: dict, target_date: date) -> dict:
    try:
        if json_data.get("@type") != "SportsEvent":
            return None

        start_dt_str = json_data.get("startDate")
        if not start_dt_str:
            return None

        # Parsear com timezone, ex: "2026-04-09T04:00:00-0300"
        start_dt_local = datetime.fromisoformat(start_dt_str)
        start_dt_utc = start_dt_local.astimezone(pytz.utc)

        # Verificar se a data do evento corresponde ao target_date
        if start_dt_utc.date() != target_date:
            return {"skipped_bad_date": 1}

        team1_name = json_data["competitor"][0]["name"]
        team2_name = json_data["competitor"][1]["name"]
        tournament_name = json_data["organizer"]["name"]
        match_url = "https://tips.gg" + json_data["url"]

        # Filtrar times
        norm_team1 = normalize_team(team1_name)
        norm_team2 = normalize_team(team2_name)

        is_our_team = (norm_team1 in cfg["teams_norm"] and norm_team1 not in cfg["exclusions_norm"]) or \
                      (norm_team2 in cfg["teams_norm"] and norm_team2 not in cfg["exclusions_norm"])

        if not is_our_team:
            return {"skipped_not_allowed": 1}

        # Verificar se a partida já passou (usando UTC para comparação)
        if start_dt_utc < datetime.now(pytz.utc):
            return {"skipped_past": 1}

        summary = f"{cfg['prefix']}{team1_name} vs {team2_name} ({tournament_name})"
        description = f"Torneio: {tournament_name}\nURL: {match_url}"

        # Estimar end_time (3 horas para BO3, 1 hora para BO1/BO2, etc.)
        # O JSON-LD fornece endDate, vamos usá-lo se disponível
        end_dt_str = json_data.get("endDate")
        if end_dt_str:
            end_dt_local = datetime.fromisoformat(end_dt_str)
            end_dt_utc = end_dt_local.astimezone(pytz.utc)
        else:
            end_dt_utc = start_dt_utc + timedelta(hours=3) # Estimativa padrão

        return {
            "event": create_calendar_event(
                summary, description, start_dt_utc, end_dt_utc, match_url, game_key
            ),
            "added": 1,
        }
    except Exception as e:
        log(f"❌ Erro ao processar JSON-LD: {e} - Dados: {json_data}")
        return {"json_decode_errors": 1}


def parse_dom_matches(soup: BeautifulSoup, game_key: str, cfg: dict, target_date: date) -> list:
    events = []
    stats = {"dom_matches_found": 0, "skipped_tbd": 0, "skipped_past": 0, "skipped_not_allowed": 0, "skipped_bad_date": 0}

    match_elements = soup.select("div.element.match.upcoming")
    stats["dom_matches_found"] = len(match_elements)

    for match_el in match_elements:
        try:
            team_names = [name.get_text(strip=True) for name in match_el.select(".teams .team .name")]
            if len(team_names) != 2:
                continue
            team1_name, team2_name = team_names

            time_str = match_el.select_one(".info .time").get_text(strip=True)
            match_url_suffix = match_el.select_one("a.match-link")["href"]
            match_url = f"https://tips.gg{match_url_suffix}"

            # Extrair nome do torneio do link do torneio
            tournament_link_el = match_el.find_previous(class_="header").select_one(".tournament-link.title h2")
            tournament_name = tournament_link_el.get_text(strip=True) if tournament_link_el else "Desconhecido"

            # Combinar data e hora. O site exibe a hora no fuso horário do usuário (BR_TZ)
            # Precisamos parsear como BR_TZ e depois converter para UTC
            try:
                # O HTML mostra "04:00" para 04:00-0300, então precisamos combinar com a data alvo
                start_dt_local = BR_TZ.localize(datetime.combine(target_date, datetime.strptime(time_str, "%H:%M").time()))
                start_dt_utc = start_dt_local.astimezone(pytz.utc)
            except ValueError:
                stats["skipped_bad_date"] += 1
                continue

            # Filtrar times
            norm_team1 = normalize_team(team1_name)
            norm_team2 = normalize_team(team2_name)

            is_our_team = (norm_team1 in cfg["teams_norm"] and norm_team1 not in cfg["exclusions_norm"]) or \
                          (norm_team2 in cfg["teams_norm"] and norm_team2 not in cfg["exclusions_norm"])

            if not is_our_team:
                stats["skipped_not_allowed"] += 1
                continue

            # Verificar se a partida já passou (usando UTC para comparação)
            if start_dt_utc < datetime.now(pytz.utc):
                stats["skipped_past"] += 1
                continue

            summary = f"{cfg['prefix']}{team1_name} vs {team2_name} ({tournament_name})"
            description = f"Torneio: {tournament_name}\nURL: {match_url}"
            end_dt_utc = start_dt_utc + timedelta(hours=3) # Estimativa padrão

            events.append(
                create_calendar_event(
                    summary, description, start_dt_utc, end_dt_utc, match_url, game_key
                )
            )
        except Exception as e:
            log(f"❌ Erro ao parsear DOM de partida: {e} - Elemento: {match_el.prettify()}")
            stats["json_decode_errors"] = stats.get("json_decode_errors", 0) + 1 # Reutilizando json_decode_errors para erros de parse DOM

    return events, stats


def scrape_one_day_for_game(driver, game_key: str, cfg: dict, target_date: date, existing_uids: set) -> tuple:
    url = build_url_for_day(cfg["base_path"], target_date)
    stats = {
        "date": target_date.strftime("%d/%m/%Y"),
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

    try:
        driver.get(url)
        # Espera por qualquer um dos seletores de conteúdo ou por um bloco de conteúdo geral
        WebDriverWait(driver, MATCH_WAIT_SECONDS).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "script[type*='json'], div.element.match.upcoming, .content-block.matches"))
        )
        time.sleep(2) # Dar um tempo extra para o Rocket Loader processar

        # Tentar extrair via JSON-LD primeiro
        json_ld_data = extract_jsonld_via_js(driver)
        stats["scripts_total"] = len(json_ld_data)

        if json_ld_data:
            stats["method"] = "JSON-LD"
            for item in json_ld_data:
                result = parse_jsonld_event(item, game_key, cfg, target_date)
                if "event" in result:
                    event = result["event"]
                    if event["uid"] not in existing_uids:
                        new_events.append(event)
                        stats["added"] += 1
                else:
                    for k, v in result.items():
                        stats[k] = stats.get(k, 0) + v
            stats["sports_events"] = len(new_events) # Contagem de eventos válidos do JSON-LD

        # Se JSON-LD não encontrou nada ou falhou, tentar via DOM
        if not new_events:
            stats["method"] = "DOM"
            soup = BeautifulSoup(driver.page_source, "html.parser")
            dom_events, dom_stats = parse_dom_matches(soup, game_key, cfg, target_date)
            for event in dom_events:
                if event["uid"] not in existing_uids:
                    new_events.append(event)
                    stats["added"] += 1
            stats["dom_matches_found"] = dom_stats["dom_matches_found"]
            stats["skipped_tbd"] += dom_stats["skipped_tbd"]
            stats["skipped_past"] += dom_stats["skipped_past"]
            stats["skipped_not_allowed"] += dom_stats["skipped_not_allowed"]
            stats["skipped_bad_date"] += dom_stats["skipped_bad_date"]
            stats["json_decode_errors"] += dom_stats.get("json_decode_errors", 0) # Reutilizando para erros de parse DOM

    except TimeoutException:
        log(f"  ↳ Timeout ao carregar a página ou aguardar elementos em {game_key}")
        stats["timeouts_load"] = 1
    except Exception as e:
        log(f"  ↳ Erro inesperado durante a raspagem de {game_key}: {e}")
        stats["json_decode_errors"] = stats.get("json_decode_errors", 0) + 1 # Contar erros gerais aqui

    return new_events, stats


# -------------------- Calendar Management --------------------
def load_calendar(filename: str) -> Calendar:
    cal = Calendar()
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            cal = Calendar.from_ical(f.read())
    return cal


def save_calendar(cal: Calendar, filename: str):
    with open(filename, "wb") as f:
        f.write(cal.to_ical())


def get_existing_uids(cal: Calendar) -> set:
    return {str(event["uid"]) for event in cal.subcomponents if event.name == "VEVENT"}


def is_ours(event) -> bool:
    description = str(event.get("description", ""))
    return SOURCE_MARKER in description


def dedupe_calendar_events(cal: Calendar) -> int:
    unique_events = {}
    to_remove = []
    for event in cal.subcomponents:
        if event.name == "VEVENT" and is_ours(event):
            summary = str(event.get("summary"))
            start_time = event.get("dtstart").dt
            # Usar uma chave de dedup que inclua summary e data para evitar duplicatas
            key = (summary, start_time.date())
            if key in unique_events:
                to_remove.append(event)
            else:
                unique_events[key] = event
    for comp in to_remove:
        cal.subcomponents.remove(comp)
    return len(to_remove)


def dedupe_by_url_keep_latest(cal: Calendar) -> int:
    unique_events = {}
    to_remove = []
    for event in cal.subcomponents:
        if event.name == "VEVENT" and is_ours(event):
            url = str(event.get("url", ""))
            if TIPS_URL_HINT in url:
                if url in unique_events:
                    existing_event = unique_events[url]
                    # Manter o evento mais recente (pelo DTSTAMP)
                    if event.get("dtstamp").dt > existing_event.get("dtstamp").dt:
                        to_remove.append(existing_event)
                        unique_events[url] = event
                    else:
                        to_remove.append(event)
                else:
                    unique_events[url] = event
    for comp in to_remove:
        cal.subcomponents.remove(comp)
    return len(to_remove)


def prune_older_than(cal: Calendar, cutoff: date) -> int:
    to_remove = []
    for event in cal.subcomponents:
        if event.name == "VEVENT" and is_ours(event):
            event_date = event.get("dtstart").dt.date()
            if event_date < cutoff:
                to_remove.append(event)
    for comp in to_remove:
        cal.subcomponents.remove(comp)
    return len(to_remove)


# -------------------- State --------------------
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


# -------------------- Main Execution --------------------
if __name__ == "__main__":
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
