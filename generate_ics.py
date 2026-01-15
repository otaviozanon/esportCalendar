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

# -------------------- Funções Auxiliares --------------------
# A função normalize_team DEVE ser definida antes de ser usada.
def normalize_team(name):
    """
    Normaliza o nome do time para comparação, convertendo para minúsculas e removendo espaços extras.
    Mantém caracteres especiais e espaços internos.
    """
    if not name:
        return ""
    return name.lower().strip()

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

BR_TZ = pytz.timezone('America/Sao_Paulo') # Fuso horário de Brasília (UTC-3)

# Pré-normaliza as listas para comparações eficientes
NORMALIZED_BRAZILIAN_TEAMS = {normalize_team(team) for team in BRAZILIAN_TEAMS}
NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS = {normalize_team(team) for team in BRAZILIAN_TEAMS_EXCLUSIONS}

# -------------------- Inicialização do Calendário --------------------
cal = Calendar()
added_count = 0

# -------------------- Configuração do Selenium --------------------
chrome_options = Options()
chrome_options.add_argument("--headless")  # Executa em modo headless (sem interface gráfica)
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080") # Garante uma resolução padrão
chrome_options.add_argument("--disable-gpu") # Necessário para alguns ambientes headless
chrome_options.add_argument("--log-level=3") # Suprime logs do Chrome/WebDriver

# Tenta usar o chromedriver do PATH ou especifica um caminho (ajuste se necessário)
# service = Service('/caminho/para/seu/chromedriver') # Descomente e ajuste se o chromedriver não estiver no PATH
driver = None

# -------------------- Processamento Principal --------------------
print(f"🔍 Iniciando Selenium para buscar partidas em {LIQUIPEDIA_URL}...")
try:
    # Inicializa o WebDriver
    # Se você especificou um caminho para o chromedriver, use:
    # driver = webdriver.Chrome(service=service, options=chrome_options)
    # Caso contrário, o Selenium tentará encontrá-lo no PATH:
    driver = webdriver.Chrome(options=chrome_options)

    driver.get(LIQUIPEDIA_URL)

    # Espera a página carregar e os elementos de partida aparecerem
    WebDriverWait(driver, 20).until(
        EC.presence_of_all_elements_located((By.CLASS_NAME, 'match-info'))
    )
    print("✅ Página carregada e elementos de partida detectados.")

    # Tenta clicar no filtro "Upcoming"
    try:
        # Localiza o botão "Upcoming" pelo seu atributo data-switch-value
        upcoming_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, '.switch-pill-option[data-switch-value="upcoming"]'))
        )
        if 'switch-pill-active' not in upcoming_button.get_attribute('class'):
            print("--- DEBUG: Clicando no filtro 'Upcoming'...")
            upcoming_button.click()
            # Espera que o conteúdo da página seja atualizado após o clique
            # Uma forma de fazer isso é esperar que o número de blocos de partida mude ou que um spinner desapareça.
            # Por enquanto, vamos esperar por um pequeno período para a página se renderizar.
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, 'match-info'))
            )
            print("--- DEBUG: Filtro 'Upcoming' aplicado com sucesso.")
        else:
            print("--- DEBUG: Filtro 'Upcoming' já está ativo. Prosseguindo.")
    except TimeoutException:
        print("--- DEBUG: Botão 'Upcoming' não encontrado ou não clicável. Prosseguindo sem aplicar o filtro.")
    except Exception as e:
        print(f"--- DEBUG: Erro ao tentar clicar no filtro 'Upcoming': {e}. Prosseguindo.")

    # Pega o HTML atualizado da página
    html_content = driver.page_source
    soup = BeautifulSoup(html_content, 'html.parser')

    # Encontra todos os blocos de partidas
    match_blocks = soup.find_all('div', class_='match-info')
    print(f"✅ Encontrados {len(match_blocks)} blocos de partidas individuais com a classe 'match-info'.")
    print(f"--- DEBUG: Normalized BR Teams (set): {NORMALIZED_BRAZILIAN_TEAMS}")
    print(f"--- DEBUG: Normalized Exclusions (set): {NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS}")

    for match_idx, block in enumerate(match_blocks, 1):
        try:
            # Extrair nomes dos times
            team_names = block.find_all('span', class_='name')
            team1_raw = team_names[0].get_text(strip=True) if len(team_names) > 0 else "N/A"
            team2_raw = team_names[1].get_text(strip=True) if len(team_names) > 1 else "N/A"

            normalized_team1 = normalize_team(team1_raw)
            normalized_team2 = normalize_team(team2_raw)

            # Verificar se algum dos times é brasileiro e não está na lista de exclusão
            is_team1_br = normalized_team1 in NORMALIZED_BRAZILIAN_TEAMS and normalized_team1 not in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS
            is_team2_br = normalized_team2 in NORMALIZED_BRAZILIAN_TEAMS and normalized_team2 not in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS

            if not (is_team1_br or is_team2_br):
                print(f"--- DEBUG: Bloco {match_idx} ignorado: Nenhum time BR envolvido ou time excluído. Times '{team1_raw}' (norm: '{normalized_team1}') vs '{team2_raw}' (norm: '{normalized_team2}')")
                continue

            # Extrair data e hora
            timer_object = block.find('span', class_='timer-object')
            if not timer_object:
                raise ValueError("Elemento 'timer-object' não encontrado.")

            timestamp_str = timer_object.get('data-timestamp')
            if not timestamp_str:
                raise ValueError("Atributo 'data-timestamp' não encontrado.")

            timestamp = int(timestamp_str)
            match_datetime_utc = datetime.fromtimestamp(timestamp, tz=pytz.utc)
            match_datetime = match_datetime_utc.astimezone(BR_TZ)

            # Extrair formato (BoX)
            best_of_element = block.find('span', class_='match-info-header-scoreholder-lower')
            best_of = best_of_element.get_text(strip=True) if best_of_element else "N/A"

            # Extrair nome do evento/torneio
            event_name_element = block.find('span', class_='match-info-tournament-name')
            event_name = event_name_element.get_text(strip=True) if event_name_element else "N/A"

            # Gerar UID para o evento (garante unicidade)
            event_uid = hashlib.sha1(f"{team1_raw}{team2_raw}{timestamp}".encode()).hexdigest()
            event = Event()
            event.name = f"{team1_raw} vs {team2_raw}"
            event.begin = match_datetime
            event.end = match_datetime + timedelta(hours=3) # Duração padrão de 3 horas
            event.description = f"Evento: {event_name} | Formato: {best_of}"
            event.uid = event_uid

            # Adicionar alarme
            alarm = DisplayAlarm(trigger=timedelta(minutes=0)) # Alarme no horário do jogo
            event.alarms.append(alarm)

            cal.events.add(event)
            added_count += 1

            print(f"   ✅ Adicionado: {team1_raw} vs {team2_raw} ({match_datetime.strftime('%d/%m %H:%M')}) | {best_of} | Evento: {event_name}\n")

        except ValueError as ve:
            print(f"   ❌ Erro de dados no bloco {match_idx}: {ve}\n")
        except Exception as e_inner:
            print(f"   ❌ Erro ao processar bloco {match_idx}: {e_inner}\n")

except TimeoutException:
    print("❌ Tempo limite excedido ao carregar a página ou encontrar elementos com Selenium.")
except WebDriverException as e:
    print(f"❌ Erro do WebDriver: {e}")
except requests.exceptions.RequestException as e:
    print(f"❌ Falha na requisição HTTP - {e}")
except Exception as e:
    print(f"❌ Erro inesperado - {e}")
finally:
    if driver:
        driver.quit() # Garante que o navegador seja fechado

# -------------------- Salvar Calendário --------------------
try:
    with open(CALENDAR_FILENAME, "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())
    print(f"\n📌 {added_count} partidas BR salvas em {CALENDAR_FILENAME} (com alarmes no horário do jogo)")
except Exception as e:
    print(f"❌ Erro ao salvar {CALENDAR_FILENAME}: {e}")
