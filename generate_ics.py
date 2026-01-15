import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
from ics import Calendar, Event
from ics.alarm import DisplayAlarm
import hashlib
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# -------------------- Configurações Globais --------------------
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo",
                   "RED Canids", "Legacy", "ODDIK", "Imperial Esports"]

BRAZILIAN_TEAMS_EXCLUSIONS = [
    "Imperial.A", "Imperial Fe", "MIBR.A", "paiN.A", "ODDIK.A",
    "Imperial Academy", "Imperial.Acd", "Imperial Female",
    "Furia Academy", "Furia.A", "Pain Academy", "Mibr Academy", "Legacy Academy", "ODDIK Academy",
    "RED Canids Academy", "Fluxo Academy"
]

LIQUIPEDIA_URL = "https://liquipedia.net/counterstrike/Liquipedia:Matches"
CALENDAR_FILENAME = "calendar.ics"
BR_TZ = pytz.timezone('America/Sao_Paulo')

# Normalizar listas para comparação
NORMALIZED_BRAZILIAN_TEAMS = {normalize_team(team) for team in BRAZILIAN_TEAMS}
NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS = {normalize_team(team) for team in BRAZILIAN_TEAMS_EXCLUSIONS}

print(f"--- DEBUG: Normalized BR Teams (set): {NORMALIZED_BRAZILIAN_TEAMS}")
print(f"--- DEBUG: Normalized Exclusions (set): {NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS}\n")

# -------------------- Funções Auxiliares --------------------
def normalize_team(name):
    """Normaliza o nome do time para comparação (minúsculas, espaços extras removidos)."""
    if not name:
        return ""
    return " ".join(name.lower().split())

def extract_team_name(team_element):
    """Extrai o nome do time do elemento HTML."""
    if not team_element:
        return None
    name_span = team_element.find("span", class_="name")
    if name_span:
        link = name_span.find("a")
        if link:
            return link.get_text(strip=True)
    return None

def is_brazilian_team(team_name):
    """Verifica se o time é brasileiro e não está na lista de exclusões."""
    if not team_name:
        return False
    normalized = normalize_team(team_name)
    print(f"      --- DEBUG: Checking team '{team_name}' (norm: '{normalized}')")

    # Verifica se está na lista de exclusões
    if normalized in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS:
        print(f"         → Excluído (está em EXCLUSIONS)")
        return False

    # Verifica se está na lista de times brasileiros
    if normalized in NORMALIZED_BRAZILIAN_TEAMS:
        print(f"         → ✅ É time BR!")
        return True

    print(f"         → Não é time BR")
    return False

def extract_timestamp(timer_element):
    """Extrai o timestamp do elemento timer."""
    if timer_element:
        data_timestamp = timer_element.get("data-timestamp")
        if data_timestamp:
            try:
                return int(data_timestamp)
            except ValueError:
                pass
    return None

def extract_event_name(match_info):
    """Extrai o nome do evento/torneio."""
    tournament_name_elem = match_info.find("span", class_="match-info-tournament-name")
    if tournament_name_elem:
        span = tournament_name_elem.find("span")
        if span:
            return span.get_text(strip=True)
    return "Evento Desconhecido"

def extract_best_of(match_info):
    """Extrai o formato (Bo1, Bo3, etc)."""
    scoreholder = match_info.find("span", class_="match-info-header-scoreholder-lower")
    if scoreholder:
        return scoreholder.get_text(strip=True)
    return "Unknown"

# -------------------- Selenium Setup --------------------
print("🔍 Iniciando Selenium para buscar partidas em " + LIQUIPEDIA_URL + "...\n")

chrome_options = Options()
chrome_options.add_argument("--start-maximized")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option('useAutomationExtension', False)

driver = None
try:
    driver = webdriver.Chrome(options=chrome_options)
    driver.get(LIQUIPEDIA_URL)

    # Aguardar o carregamento inicial dos elementos
    print("⏳ Aguardando carregamento da página...\n")
    WebDriverWait(driver, 10).until(
        EC.presence_of_all_elements_located((By.CLASS_NAME, "match-info"))
    )
    print("✅ Página carregada e elementos de partida detectados.\n")

    # Tentar clicar no botão "Upcoming" se existir
    try:
        print("🔍 Procurando pelo filtro 'Upcoming'...\n")
        upcoming_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//div[@data-switch-value='upcoming']"))
        )
        print("✅ Botão 'Upcoming' encontrado. Clicando...\n")
        upcoming_button.click()

        # Aguardar o conteúdo dinâmico carregar após o clique
        print("⏳ Aguardando conteúdo dinâmico...\n")
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, "match-info"))
        )
        print("✅ Conteúdo dinâmico carregado.\n")
    except TimeoutException:
        print("⚠️  Filtro 'Upcoming' não encontrado ou já ativo. Prosseguindo com conteúdo atual.\n")

    # Extrair HTML após Selenium
    html_content = driver.page_source

except TimeoutException:
    print("❌ Tempo limite excedido ao carregar a página ou encontrar elementos com Selenium.")
    exit(1)
except WebDriverException as e:
    print(f"❌ Erro do WebDriver: {e}")
    exit(1)
except Exception as e:
    print(f"❌ Erro inesperado: {e}")
    exit(1)
finally:
    if driver:
        driver.quit()

# -------------------- Processar HTML com BeautifulSoup --------------------
soup = BeautifulSoup(html_content, "html.parser")
match_blocks = soup.find_all("div", class_="match-info")

print(f"✅ Encontrados {len(match_blocks)} blocos de partidas individuais com a classe 'match-info'.\n")

cal = Calendar()
added_count = 0

for match_idx, match_info in enumerate(match_blocks, 1):
    try:
        print(f"--- DEBUG: Processando bloco {match_idx}:")

        # Extrair times
        opponent_divs = match_info.find_all("div", class_="match-info-header-opponent")
        if len(opponent_divs) < 2:
            print(f"   ❌ Bloco {match_idx} ignorado: Estrutura HTML incompleta.\n")
            continue

        team1_raw = extract_team_name(opponent_divs[0])
        team2_raw = extract_team_name(opponent_divs[1])

        print(f"   Times encontrados: '{team1_raw}' vs '{team2_raw}'")

        if not team1_raw or not team2_raw:
            print(f"   ❌ Bloco {match_idx} ignorado: Um ou ambos os nomes de times não foram extraídos.\n")
            continue

        # Verificar se algum time é brasileiro
        is_team1_br = is_brazilian_team(team1_raw)
        is_team2_br = is_brazilian_team(team2_raw)

        if not (is_team1_br or is_team2_br):
            print(f"   ❌ Bloco {match_idx} ignorado: Nenhum time BR envolvido.\n")
            continue

        # Extrair timestamp
        timer_element = match_info.find("span", class_="timer-object")
        timestamp = extract_timestamp(timer_element)

        if not timestamp:
            print(f"   ❌ Bloco {match_idx} ignorado: Timestamp não encontrado.\n")
            continue

        # Converter timestamp para datetime
        match_datetime = datetime.fromtimestamp(timestamp, tz=pytz.UTC).astimezone(BR_TZ)

        # Extrair informações adicionais
        event_name = extract_event_name(match_info)
        best_of = extract_best_of(match_info)

        # Criar evento do calendário
        event_uid = hashlib.md5(f"{team1_raw}{team2_raw}{timestamp}".encode()).hexdigest()
        event = Event()
        event.name = f"{team1_raw} vs {team2_raw}"
        event.begin = match_datetime
        event.end = match_datetime + timedelta(hours=3)
        event.description = f"Evento: {event_name} | Formato: {best_of}"
        event.uid = event_uid

        # Adicionar alarme
        alarm = DisplayAlarm(trigger=timedelta(minutes=0))
        event.alarms.append(alarm)

        cal.events.add(event)
        added_count += 1

        print(f"   ✅ Adicionado: {team1_raw} vs {team2_raw} ({match_datetime.strftime('%d/%m %H:%M')}) | {best_of} | Evento: {event_name}\n")

    except Exception as e_inner:
        print(f"   ❌ Erro ao processar bloco {match_idx}: {e_inner}\n")

# -------------------- Salvar Calendário --------------------
try:
    with open(CALENDAR_FILENAME, "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())
    print(f"\n📌 {added_count} partidas BR salvas em {CALENDAR_FILENAME} (com alarmes no horário do jogo)")
except Exception as e:
    print(f"❌ Erro ao salvar {CALENDAR_FILENAME}: {e}")
