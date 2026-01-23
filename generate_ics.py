import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
from ics import Calendar, Event
from ics.alarm import DisplayAlarm
import hashlib
import json
import re
import time # Importar a biblioteca time para usar time.sleep

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

TIPSGG_BASE_URL = "https://tips.gg/csgo/matches/" # URL base sem a data
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
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    # Inicializa o ChromeDriver usando webdriver_manager
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    # Loop para os próximos 5 dias
    for i in range(2):
        target_date = datetime.now(BR_TZ) + timedelta(days=i)
        date_str = target_date.strftime('%d-%m-%Y')
        current_url = f"{TIPSGG_BASE_URL}{date_str}/"

        print(f"⚙️ Processando URL: {current_url}")

        try:
            driver.get(current_url)

            # Espera até que os elementos JSON-LD estejam presentes na página
            WebDriverWait(driver, 30).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'script[type="application/ld+json"]'))
            )

            soup = BeautifulSoup(driver.page_source, 'html.parser')

            # Encontra todos os blocos de script JSON-LD
            json_ld_scripts = soup.find_all('script', type='application/ld+json')

            for script in json_ld_scripts:
                try:
                    event_data = json.loads(script.string)

                    # Verificar se é um SportsEvent válido
                    if event_data.get("@type") != "SportsEvent":
                        continue

                    # Extrair informações do JSON-LD
                    event_name = event_data.get("name", "Desconhecido")
                    start_date_str = event_data.get("startDate")
                    organizer_name = event_data.get("organizer", {}).get("name", "Desconhecido")
                    description_raw = event_data.get("description", "")
                    match_url_raw = event_data.get("url", "")

                    # Extrair nomes dos times
                    team1_raw = "TBD"
                    team2_raw = "TBD"
                    if "performer" in event_data and isinstance(event_data["performer"], list):
                        if len(event_data["performer"]) > 0:
                            team1_raw = event_data["performer"][0].get("name", "TBD")
                        if len(event_data["performer"]) > 1:
                            team2_raw = event_data["performer"][1].get("name", "TBD")

                    # Converter data/hora para UTC e verificar se a partida já ocorreu
                    if not start_date_str:
                        continue # Ignora se não houver data de início

                    match_time_utc = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))

                    # Ignorar partidas TBD ou que já ocorreram
                    if team1_raw == "TBD" or team2_raw == "TBD":
                        continue
                    if match_time_utc < datetime.now(pytz.utc):
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

            # Pausa de 1 minuto ANTES de ir para a próxima data, se não for a última iteração
            if i < 4: # Se não for o último dia (0 a 4, total de 5 dias)
                print(f"😴 Pausando por 1 minuto antes de processar a próxima data...")
                time.sleep(60) # Pausa de 60 segundos

        except TimeoutException:
            print(f"❌ Tempo limite excedido ao carregar a página {current_url} ou aguardar elementos. Continuando para a próxima data.")
        except WebDriverException as we:
            print(f"❌ Erro do WebDriver ao acessar {current_url}: {we}. Continuando para a próxima data.")
        except Exception as e_page:
            print(f"❌ Erro inesperado ao processar a página {current_url}: {e_page}. Continuando para a próxima data.")

except requests.exceptions.RequestException as e:
    print(f"❌ Falha na requisição HTTP - {e}")
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
