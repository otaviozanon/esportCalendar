import os
import json
import hashlib
import time
from datetime import datetime, timedelta, date

import pytz
from bs4 import BeautifulSoup
from icalendar import Calendar, Event, Alarm

# Importar undetected_chromedriver em vez de selenium.webdriver
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
    uids = set()
    for component in cal.subcomponents:
        if isinstance(component, Event) and SOURCE_MARKER in component.get("X-SETT-SOURCE", ""):
            uids.add(str(component["uid"]))
    return uids


def dedupe_calendar_events(cal: Calendar) -> int:
    unique_events = {}
    to_remove = []
    removed_count = 0

    for event in cal.subcomponents:
        if isinstance(event, Event) and SOURCE_MARKER in event.get("X-SETT-SOURCE", ""):
            # Usar uma combinação de summary e data/hora de início para identificar duplicatas
            # Normalizar o summary para ignorar pequenas variações
            summary_norm = normalize_team(event.get("summary", ""))
            start_dt = event.get("dtstart").dt.isoformat()

            key = (summary_norm, start_dt)

            if key in unique_events:
                to_remove.append(event)
                removed_count += 1
            else:
                unique_events[key] = event

    for event in to_remove:
        cal.subcomponents.remove(event)
    return removed_count


def dedupe_by_url_keep_latest(cal: Calendar) -> int:
    events_by_url = {}
    to_remove = []
    removed_count = 0

    for event in cal.subcomponents:
        if isinstance(event, Event) and SOURCE_MARKER in event.get("X-SETT-SOURCE", ""):
            url = event.get("url")
            if url:
                if url not in events_by_url:
                    events_by_url[url] = event
                else:
                    # Se houver duplicata, mantém o evento com o DTSTAMP mais recente
                    existing_event = events_by_url[url]
                    if event.get("dtstamp").dt > existing_event.get("dtstamp").dt:
                        to_remove.append(existing_event)
                        events_by_url[url] = event
                    else:
                        to_remove.append(event)

    for event in to_remove:
        if event in cal.subcomponents: # Verifica se o evento ainda está na lista antes de remover
            cal.subcomponents.remove(event)
            removed_count += 1
    return removed_count


def prune_older_than(cal: Calendar, cutoff: date) -> int:
    to_remove = []
    for event in cal.subcomponents:
        if isinstance(event, Event) and SOURCE_MARKER in event.get("X-SETT-SOURCE", ""):
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


# -------------------- Scraper Logic --------------------
def build_url_for_day(base_path: str, target_day: date) -> str:
    # O site tips.gg usa o formato https://tips.gg/csgo/matches/DD-MM-YYYY/
    # Para o dia atual, ele pode usar apenas https://tips.gg/csgo/matches/
    if target_day == datetime.now(BR_TZ).date():
        return base_path
    return f"{base_path}{target_day.strftime('%d-%m-%Y')}/"


def extract_jsonld_via_js(driver) -> list:
    """Extrai todos os objetos JSON-LD de SportsEvent da página via JavaScript."""
    json_ld_scripts = driver.execute_script(
        """
        let results = [];
        document.querySelectorAll('script').forEach(script => {
            if (script.textContent.includes('"@type":"SportsEvent"') && script.textContent.startsWith('{')) {
                try {
                    results.push(JSON.parse(script.textContent));
                } catch (e) {
                    console.error("Erro ao parsear JSON-LD:", e);
                }
            }
        });
        return results;
        """
    )
    return json_ld_scripts


def parse_jsonld_event(json_data: dict, game_key: str, cfg: dict, target_day: date, existing_uids: set, stats: dict) -> Event | None:
    """Processa um único objeto JSON-LD e cria um evento iCalendar."""
    try:
        if json_data.get("@type") != "SportsEvent":
            return None

        name = json_data.get("name", "Evento Desconhecido")
        url = json_data.get("url")
        if not url:
            url = json_data.get("location", {}).get("url")
        if not url:
            url = TIPS_URL_HINT # Fallback para URL genérica se não encontrar

        # O startDate vem com o offset de timezone (ex: -0300), fromisoformat lida com isso
        start_dt_str = json_data.get("startDate")
        if not start_dt_str:
            log(f"    ↳ Pulando evento '{name}': Sem startDate.")
            stats["skipped_bad_date"] += 1
            return None

        start_dt_local = datetime.fromisoformat(start_dt_str)
        start_dt_utc = start_dt_local.astimezone(pytz.utc)

        # Verificar se a data do evento corresponde ao target_day
        if start_dt_utc.date() != target_day:
            log(f"    ↳ Pulando evento '{name}': Data ({start_dt_utc.date()}) não corresponde ao alvo ({target_day}).")
            stats["skipped_bad_date"] += 1
            return None

        # Verificar se o evento já passou (em relação ao BR_TZ)
        now_br = datetime.now(BR_TZ)
        if start_dt_local < now_br - timedelta(minutes=10): # Margem de 10 minutos
            log(f"    ↳ Pulando evento '{name}': Já passou ({start_dt_local.strftime('%H:%M')}).")
            stats["skipped_past"] += 1
            return None

        team1_name = json_data.get("competitor", [{}, {}])[0].get("name")
        team2_name = json_data.get("competitor", [{}, {}])[1].get("name")
        tournament_name = json_data.get("organizer", {}).get("name")

        if not team1_name or not team2_name:
            log(f"    ↳ Pulando evento '{name}': Times não encontrados.")
            stats["skipped_tbd"] += 1
            return None

        # Normalizar nomes dos times para comparação
        norm_team1 = normalize_team(team1_name)
        norm_team2 = normalize_team(team2_name)

        # Verificar exclusões
        if norm_team1 in cfg["exclusions_norm"] or norm_team2 in cfg["exclusions_norm"]:
            log(f"    ↳ Pulando evento '{name}': Time excluído encontrado.")
            stats["skipped_not_allowed"] += 1
            return None

        # Verificar se algum dos times é de interesse
        is_relevant = False
        if cfg["teams_norm"]: # Se a lista de times de interesse não estiver vazia
            if norm_team1 in cfg["teams_norm"] or norm_team2 in cfg["teams_norm"]:
                is_relevant = True
        else: # Se a lista de times de interesse estiver vazia, todos são relevantes
            is_relevant = True

        if not is_relevant:
            log(f"    ↳ Pulando evento '{name}': Nenhum time de interesse encontrado.")
            stats["skipped_not_allowed"] += 1
            return None

        summary = f"{cfg['prefix']}{team1_name} vs {team2_name}"
        description = f"Torneio: {tournament_name}\nURL: {url}"

        # Gerar UID consistente
        unique_string = f"{summary}-{start_dt_utc.isoformat()}-{url}"
        uid = hashlib.sha1(unique_string.encode()).hexdigest() + "@tips.gg"

        if uid in existing_uids:
            log(f"    ↳ Pulando evento '{summary}': Já existe (UID: {uid}).")
            return None

        event = Event()
        event.add("summary", summary)
        event.add("dtstart", start_dt_utc)
        event.add("dtend", start_dt_utc + timedelta(hours=3)) # Duração padrão de 3 horas
        event.add("description", description)
        event.add("uid", uid)
        event.add("url", url)
        event.add("dtstamp", datetime.now(pytz.utc))
        event.add("X-SETT-SOURCE", SOURCE_MARKER)

        # Adicionar alarme 30 minutos antes
        alarm = Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add("description", f"Partida de {game_key} começando!")
        alarm.add("trigger", timedelta(minutes=-30))
        event.add_component(alarm)

        log(f"    ✅ Evento JSON-LD adicionado: {summary} em {start_dt_local.strftime('%d/%m/%Y %H:%M')}")
        stats["added"] += 1
        stats["sports_events"] += 1
        return event

    except Exception as e:
        log(f"    ❌ Erro ao processar JSON-LD para '{json_data.get('name', 'N/A')}': {e}")
        stats["json_decode_errors"] += 1
        return None


def parse_dom_matches(soup: BeautifulSoup, game_key: str, cfg: dict, target_day: date, existing_uids: set, stats: dict) -> list:
    """
    Extrai eventos de partidas da estrutura DOM (div.element.match).
    """
    events = []
    matches = soup.select("div.element.match.upcoming")
    stats["dom_matches_found"] += len(matches)

    for match_element in matches:
        try:
            team_names = [
                name.get_text(strip=True)
                for name in match_element.select(".teams .team .name")
            ]
            if len(team_names) < 2:
                log("    ↳ Pulando evento DOM: Não foi possível encontrar 2 times.")
                stats["skipped_tbd"] += 1
                continue

            team1_name = team_names[0]
            team2_name = team_names[1]

            time_str = match_element.select_one(".info .time").get_text(strip=True)
            match_link_element = match_element.select_one("a.match-link")
            url = match_link_element["href"] if match_link_element else TIPS_URL_HINT

            # O torneio pode ser extraído do cabeçalho acima do grupo de partidas
            tournament_element = match_element.find_previous(class_="header").select_one(".tournament-link.title h2")
            tournament_name = tournament_element.get_text(strip=True) if tournament_element else "Torneio Desconhecido"

            # Combinar data do target_day com o horário da string
            # O horário no DOM é local (BR_TZ)
            try:
                match_time_local = datetime.strptime(time_str, "%H:%M").time()
                start_dt_local = BR_TZ.localize(datetime.combine(target_day, match_time_local))
                start_dt_utc = start_dt_local.astimezone(pytz.utc)
            except ValueError:
                log(f"    ↳ Pulando evento DOM '{team1_name} vs {team2_name}': Formato de hora inválido '{time_str}'.")
                stats["skipped_bad_date"] += 1
                continue

            # Verificar se o evento já passou (em relação ao BR_TZ)
            now_br = datetime.now(BR_TZ)
            if start_dt_local < now_br - timedelta(minutes=10): # Margem de 10 minutos
                log(f"    ↳ Pulando evento DOM '{team1_name} vs {team2_name}': Já passou ({start_dt_local.strftime('%H:%M')}).")
                stats["skipped_past"] += 1
                continue

            # Normalizar nomes dos times para comparação
            norm_team1 = normalize_team(team1_name)
            norm_team2 = normalize_team(team2_name)

            # Verificar exclusões
            if norm_team1 in cfg["exclusions_norm"] or norm_team2 in cfg["exclusions_norm"]:
                log(f"    ↳ Pulando evento DOM '{team1_name} vs {team2_name}': Time excluído encontrado.")
                stats["skipped_not_allowed"] += 1
                continue

            # Verificar se algum dos times é de interesse
            is_relevant = False
            if cfg["teams_norm"]: # Se a lista de times de interesse não estiver vazia
                if norm_team1 in cfg["teams_norm"] or norm_team2 in cfg["teams_norm"]:
                    is_relevant = True
            else: # Se a lista de times de interesse estiver vazia, todos são relevantes
                is_relevant = True

            if not is_relevant:
                log(f"    ↳ Pulando evento DOM '{team1_name} vs {team2_name}': Nenhum time de interesse encontrado.")
                stats["skipped_not_allowed"] += 1
                continue

            summary = f"{cfg['prefix']}{team1_name} vs {team2_name}"
            description = f"Torneio: {tournament_name}\nURL: {url}"

            # Gerar UID consistente
            unique_string = f"{summary}-{start_dt_utc.isoformat()}-{url}"
            uid = hashlib.sha1(unique_string.encode()).hexdigest() + "@tips.gg"

            if uid in existing_uids:
                log(f"    ↳ Pulando evento DOM '{summary}': Já existe (UID: {uid}).")
                continue

            event = Event()
            event.add("summary", summary)
            event.add("dtstart", start_dt_utc)
            event.add("dtend", start_dt_utc + timedelta(hours=3)) # Duração padrão de 3 horas
            event.add("description", description)
            event.add("uid", uid)
            event.add("url", url)
            event.add("dtstamp", datetime.now(pytz.utc))
            event.add("X-SETT-SOURCE", SOURCE_MARKER)

            # Adicionar alarme 30 minutos antes
            alarm = Alarm()
            alarm.add("action", "DISPLAY")
            alarm.add("description", f"Partida de {game_key} começando!")
            alarm.add("trigger", timedelta(minutes=-30))
            event.add_component(alarm)

            events.append(event)
            log(f"    ✅ Evento DOM adicionado: {summary} em {start_dt_local.strftime('%d/%m/%Y %H:%M')}")
            stats["added"] += 1

        except Exception as e:
            log(f"    ❌ Erro ao processar elemento DOM de partida: {e}")
            stats["json_decode_errors"] += 1 # Reutilizando para erros de parse

    return events


def scrape_one_day_for_game(driver, game_key: str, cfg: dict, target_day: date, existing_uids: set) -> tuple[list, dict]:
    """
    Navega para a URL do dia e tenta raspar eventos usando JSON-LD e, se falhar, DOM.
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
