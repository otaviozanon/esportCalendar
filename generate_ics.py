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

# Gerar URL apenas para hoje
today = datetime.now(BR_TZ)
date_str = today.strftime('%d-%m-%Y')
TIPSGG_URL = f"https://tips.gg/csgo/matches/{date_str}/"

print(f"🔍 Abrindo navegador para {TIPSGG_URL} com Selenium...")

driver = None

try:
    # Configurar opções do Chrome
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    print("⚙️ Baixando e configurando ChromeDriver com webdriver_manager...")
    service = Service(ChromeDriverManager().install())
    print("⚙️ ChromeDriver configurado com sucesso.")

    driver = webdriver.Chrome(service=service, options=chrome_options)

    print(f"⚙️ Página {TIPSGG_URL} carregada com sucesso pelo Selenium.")
    driver.get(TIPSGG_URL)

    print("⚙️ Aguardando elementos JSON-LD na página...")
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'script[type="application/ld+json"]'))
    )
    print("✅ Elementos JSON-LD encontrados na página.")

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    scripts = soup.find_all('script', type='application/ld+json')
    print(f"📦 Encontrados {len(scripts)} blocos JSON-LD na página.")

    for script_idx, script in enumerate(scripts, 1):
        try:
            event_data = json.loads(script.string)

            # Verificar se é um SportsEvent válido
            if event_data.get("@type") != "SportsEvent":
                continue

            # Extrair informações do JSON-LD
            event_name = event_data.get("name", "Desconhecido")
            start_date_str = event_data.get("startDate", "")
            description = event_data.get("description", "")
            organizer_name = event_data.get("organizer", {}).get("name", "Desconhecido")
            match_url = event_data.get("url", "")

            # Construir URL completa se for relativa
            if match_url and not match_url.startswith("http"):
                match_url = f"https://tips.gg{match_url}"

            # Extrair times
            competitors = event_data.get("competitor", [])
            if len(competitors) < 2:
                continue

            team1_raw = competitors[0].get("name", "TBD")
            team2_raw = competitors[1].get("name", "TBD")

            # Ignorar partidas com TBD
            if team1_raw == "TBD" or team2_raw == "TBD":
                continue

            # Converter startDate para datetime
            try:
                match_time_utc = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
            except:
                continue

            # Verificar se a partida já ocorreu
            if match_time_utc < datetime.now(pytz.utc):
                print(f"--- Processando Partida {script_idx}: {team1_raw} vs {team2_raw} ({match_time_utc.strftime('%d/%m %H:%M')}) ---")
                print(f"🚫 Ignorando: Partida já ocorreu ({match_time_utc.strftime('%d/%m %H:%M')})")
                continue

            # Normalizar nomes dos times
            normalized_team1 = normalize_team(team1_raw)
            normalized_team2 = normalize_team(team2_raw)

            # Lógica de filtragem: verifica se algum time BR principal está envolvido E não é uma exclusão
            is_br_team1 = normalized_team1 in NORMALIZED_BRAZILIAN_TEAMS
            is_br_team2 = normalized_team2 in NORMALIZED_BRAZILIAN_TEAMS

            is_excluded_team1 = normalized_team1 in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS
            is_excluded_team2 = normalized_team2 in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS

            is_br_team_involved = (is_br_team1 and not is_excluded_team1) or \
                                  (is_br_team2 and not is_excluded_team2)

            print(f"--- Processando Partida {script_idx}: {team1_raw} vs {team2_raw} ({match_time_utc.strftime('%d/%m %H:%M')}) ---")
            print(f"   Time 1: {team1_raw} (normalizado: {normalized_team1}) - É BR: {is_br_team1}, Excluído: {is_excluded_team1}")
            print(f"   Time 2: {team2_raw} (normalizado: {normalized_team2}) - É BR: {is_br_team2}, Excluído: {is_excluded_team2}")
            print(f"   Time BR envolvido: {is_br_team_involved}")

            if not is_br_team_involved:
                print(f"🚫 Ignorando: Nenhum time BR principal (não excluído) envolvido")
                continue

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
            print(f"🎉 Adicionado ao calendário: '{event_summary}'")

        except json.JSONDecodeError as je:
            print(f"❌ Erro ao decodificar JSON no script {script_idx}: {je}")
        except Exception as e_inner:
            print(f"❌ Erro inesperado ao processar script {script_idx}: {e_inner}")

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
        print("⚙️ Fechando navegador Selenium.")
        driver.quit()

print(f"\n💾 Salvando arquivo: {CALENDAR_FILENAME}")
try:
    with open(CALENDAR_FILENAME, "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())
    print(f"📌 Total de partidas adicionadas: {added_count}")
except Exception as e:
    print(f"❌ Erro ao salvar {CALENDAR_FILENAME}: {e}")
