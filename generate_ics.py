import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
from ics import Calendar, Event
from ics.alarm import DisplayAlarm
import hashlib
import json
import re

# Importar Selenium
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# Importar webdriver_manager
from webdriver_manager.chrome import ChromeDriverManager

# -------------------- Configurações Globais --------------------
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo",
                   "RED Canids", "Legacy", "ODDIK", "Imperial Esports"]

BRAZILIAN_TEAMS_EXCLUSIONS = [
    "Imperial.A", "Imperial Fe", "MIBR.A", "paiN.A", "ODDIK.A",
    "Imperial Academy", "Imperial.Acd", "Imperial Female",
    "Furia Academy", "Furia.A", "Pain Academy", "Mibr Academy", "Legacy Academy", "ODDIK Academy",
    "RED Canids Academy", "Fluxo Academy"
]

CALENDAR_FILENAME = "calendar.ics"
BR_TZ = pytz.timezone('America/Sao_Paulo')

# Pré-normaliza as listas de times para otimizar as comparações
def normalize_team(name):
    if not name:
        return ""
    return name.lower().strip()

NORMALIZED_BRAZILIAN_TEAMS = {normalize_team(team) for team in BRAZILIAN_TEAMS}
NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS = {normalize_team(team) for team in BRAZILIAN_TEAMS_EXCLUSIONS}

# -------------------- Lógica Principal --------------------
cal = Calendar()
added_count = 0
driver = None # Inicializa driver como None para o bloco finally

print("🔍 Iniciando o processo de busca de partidas...")

try:
    # Configurações do Selenium
    chrome_options = Options()
    chrome_options.add_argument("--headless") # Executa em modo headless (sem interface gráfica)
    chrome_options.add_argument("--no-sandbox") # Necessário para ambientes Linux como GitHub Actions
    chrome_options.add_argument("--disable-dev-shm-usage") # Otimização para ambientes Docker/CI
    chrome_options.add_argument("--window-size=1920,1080") # Define um tamanho de janela
    chrome_options.add_argument("--log-level=3") # Reduz a verbosidade dos logs do Chrome

    # Inicializa o ChromeDriver usando webdriver_manager
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    # Constrói a URL para o dia atual
    today = datetime.now(BR_TZ)
    date_str = today.strftime('%d-%m-%Y')
    current_url = f"https://tips.gg/csgo/matches/{date_str}/"

    driver.get(current_url)

    # Espera até que os elementos JSON-LD estejam presentes na página
    WebDriverWait(driver, 30).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'script[type="application/ld+json"]'))
    )

    soup = BeautifulSoup(driver.page_source, 'html.parser')

    # Encontra todos os blocos de script JSON-LD
    json_ld_scripts = soup.find_all('script', type='application/ld+json')

    for script_idx, script in enumerate(json_ld_scripts, 1):
        try:
            data = json.loads(script.string)

            # Verifica se é um SportsEvent e se tem os campos necessários
            if data.get('@type') != 'SportsEvent' or not all(k in data for k in ['name', 'startDate', 'competitor', 'organizer', 'description', 'url']):
                continue # Ignora se não for um SportsEvent válido ou faltam campos essenciais

            # Extrair informações
            event_name_full = data.get('name', 'Nome do Evento Desconhecido')
            start_date_str = data.get('startDate')
            competitors = data.get('competitor', [])
            organizer_name = data.get('organizer', {}).get('name', 'Torneio Desconhecido')
            description_raw = data.get('description', '')
            match_url_raw = data.get('url', '')

            # Converte a data/hora para UTC e depois para o fuso horário de Brasília para comparação
            # O formato do tips.gg é ISO 8601 com offset, e datetime.fromisoformat lida com isso
            match_time_utc = datetime.fromisoformat(start_date_str).astimezone(pytz.utc)

            # Ignorar partidas que já ocorreram
            if match_time_utc < datetime.now(pytz.utc):
                continue

            team1_raw = competitors[0].get('name', 'TBD') if len(competitors) > 0 else 'TBD'
            team2_raw = competitors[1].get('name', 'TBD') if len(competitors) > 1 else 'TBD'

            # Ignorar partidas com TBD
            if team1_raw == "TBD" or team2_raw == "TBD":
                continue

            # Normaliza os nomes para a lógica de filtragem
            normalized_team1 = normalize_team(team1_raw)
            normalized_team2 = normalize_team(team2_raw)

            # Lógica de filtragem: verifica se algum time BR principal está envolvido E não é uma exclusão
            is_br_team1 = normalized_team1 in NORMALIZED_BRAZILIAN_TEAMS
            is_br_team2 = normalized_team2 in NORMALIZED_BRAZILIAN_TEAMS

            is_excluded_team1 = normalized_team1 in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS
            is_excluded_team2 = normalized_team2 in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS

            is_br_team_involved = (is_br_team1 and not is_excluded_team1) or \
                                  (is_br_team2 and not is_excluded_team2)

            if not is_br_team_involved:
                continue

            # Extrair formato da partida (Bo1, Bo3, etc.) e fase do torneio (Group D, Playoffs)
            match_format_match = re.search(r'(BO\d+ Match)', description_raw, re.IGNORECASE)
            match_format = match_format_match.group(1) if match_format_match else "BoX"

            match_phase_match = re.search(r'(Group [A-D]|Playoffs|Regular Season|Grand Final|Semi-Final|Quarter-Final)', description_raw, re.IGNORECASE)
            match_phase = match_phase_match.group(1) if match_phase_match else "Fase Desconhecida"

            description = f"{match_format} - {match_phase}"
            match_url = f"https://tips.gg{match_url_raw}" if match_url_raw.startswith('/') else match_url_raw

            # Criar evento
            event_summary = f"{team1_raw} vs {team2_raw}"
            event_description = (
                f"🏆 {description}\n"
                f"📍 {organizer_name}\n"
                f"🌐 {match_url}"
            )

            event_uid = hashlib.sha1(event_summary.encode('utf-8') + str(start_date_str).encode('utf-8')).hexdigest()

            e = Event()
            e.name = event_summary
            e.begin = match_time_utc
            e.duration = timedelta(hours=2)
            e.description = event_description
            e.uid = event_uid

            # Adiciona alarme 15 minutos antes
            alarm = DisplayAlarm(trigger=timedelta(minutes=-15))
            e.alarms.append(alarm)

            cal.events.add(e)
            added_count += 1

        except json.JSONDecodeError:
            pass # Não exibir logs no console
        except Exception:
            pass # Não exibir logs no console

except requests.exceptions.RequestException as e:
    print(f"❌ Falha na requisição HTTP - {e}")
except TimeoutException:
    print("❌ Tempo limite excedido ao carregar a página ou aguardar elementos.")
except WebDriverException as e:
    print(f"❌ Erro do WebDriver: {e}")
except Exception as e:
    print(f"❌ Erro geral durante a execução do Selenium: {e}")
finally:
    if driver:
        driver.quit()

print(f"\n💾 Salvando arquivo: {CALENDAR_FILENAME}")
try:
    with open(CALENDAR_FILENAME, "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())
    print(f"📌 Total de partidas adicionadas: {added_count}")
except Exception as e:
    print(f"❌ Erro ao salvar {CALENDAR_FILENAME}: {e}")
