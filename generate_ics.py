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
# Lista de times brasileiros principais (nomes como aparecem no HTML, mas serão normalizados para comparação)
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo",
                   "RED Canids", "Legacy", "ODDIK", "Imperial Esports"]

# Lista de exclusões (nomes como aparecem no HTML, mas serão normalizados para comparação)
BRAZILIAN_TEAMS_EXCLUSIONS = [
    "Imperial.A", "Imperial Fe", "MIBR.A", "paiN.A", "ODDIK.A",
    "Imperial Academy", "Imperial.Acd", "Imperial Female",
    "Furia Academy", "Furia.A", "Pain Academy", "Mibr Academy", "Legacy Academy", "ODDIK Academy",
    "RED Canids Academy", "Fluxo Academy"
]

# URL da Liquipedia Counter-Strike para partidas
LIQUIPEDIA_URL = "https://liquipedia.net/counterstrike/Liquipedia:Matches"
CALENDAR_FILENAME = "calendar.ics"

# Configuração de fuso horário
BR_TZ = pytz.timezone('America/Sao_Paulo') # Fuso horário de Brasília (UTC-3)

# -------------------- Funções Auxiliares --------------------
def normalize_team(name):
    """
    Normaliza o nome do time para comparação, convertendo para minúsculas e removendo espaços extras.
    Mantém caracteres especiais e espaços internos.
    """
    if not name:
        return ""
    return name.lower().strip()

# Pré-normaliza as listas para comparações eficientes
NORMALIZED_BRAZILIAN_TEAMS = {normalize_team(team) for team in BRAZILIAN_TEAMS}
NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS = {normalize_team(team) for team in BRAZILIAN_TEAMS_EXCLUSIONS}

# -------------------- Lógica Principal --------------------
cal = Calendar()
added_count = 0
driver = None # Inicializa driver como None

try:
    # Configurações do Chrome para rodar em modo headless (sem interface gráfica)
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080") # Garante que a página seja renderizada em um tamanho razoável

    # Inicializa o WebDriver (certifique-se de que o chromedriver está no PATH ou especifique o caminho)
    # Exemplo: service = Service('/caminho/para/chromedriver')
    # driver = webdriver.Chrome(service=service, options=chrome_options)
    driver = webdriver.Chrome(options=chrome_options) # Assumindo que chromedriver está no PATH

    driver.get(LIQUIPEDIA_URL)

    # Espera até que o botão "Upcoming" esteja visível e clicável
    # O botão "Upcoming" está dentro de um div com a classe "switch-pill-option" e data-switch-value="upcoming"
    upcoming_button_selector = (By.CSS_SELECTOR, 'div.switch-pill-option[data-switch-value="upcoming"]')
    WebDriverWait(driver, 20).until(EC.element_to_be_clickable(upcoming_button_selector))

    # Clica no botão "Upcoming"
    upcoming_button = driver.find_element(*upcoming_button_selector)
    if "switch-pill-active" not in upcoming_button.get_attribute("class"):
        upcoming_button.click()
        # Espera que o conteúdo da página seja atualizado após o clique
        # Podemos esperar que os blocos de partida sejam recarregados ou que um spinner desapareça
        # Para ser mais robusto, esperamos que o número de blocos de partida se estabilize ou mude
        WebDriverWait(driver, 20).until(
            lambda d: len(d.find_elements(By.CLASS_NAME, 'match-info')) > 0
        )

    # Agora que a página está no estado "Upcoming", pegamos o HTML
    html_content = driver.page_source
    soup = BeautifulSoup(html_content, 'html.parser')

    match_blocks = soup.find_all('div', class_='match-info')

    for match_idx, match_block in enumerate(match_blocks, 1):
        try:
            # Extração dos nomes dos times
            team_names_elements = match_block.select('.block-team .name a')
            if len(team_names_elements) < 2:
                continue # Ignora blocos sem dois times

            team1_raw = team_names_elements[0].get_text(strip=True)
            team2_raw = team_names_elements[1].get_text(strip=True)

            # Normaliza os nomes para comparação
            normalized_team1 = normalize_team(team1_raw)
            normalized_team2 = normalize_team(team2_raw)

            # Verifica se algum dos times é brasileiro e não está na lista de exclusão
            is_br_team_involved = (normalized_team1 in NORMALIZED_BRAZILIAN_TEAMS and normalized_team1 not in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS) or \
                                  (normalized_team2 in NORMALIZED_BRAZILIAN_TEAMS and normalized_team2 not in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS)

            # Verifica se ambos os times são brasileiros e não estão na lista de exclusão
            is_both_br_teams = (normalized_team1 in NORMALIZED_BRAZILIAN_TEAMS and normalized_team1 not in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS) and \
                               (normalized_team2 in NORMALIZED_BRAZILIAN_TEAMS and normalized_team2 not in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS)

            # Se nenhum time BR estiver envolvido (ou ambos forem excluídos), ignora
            if not is_br_team_involved and not is_both_br_teams:
                continue

            # Extração do timestamp
            timer_object = match_block.find('span', class_='timer-object')
            if not timer_object:
                continue
            timestamp_str = timer_object.get('data-timestamp')
            if not timestamp_str:
                continue
            match_timestamp = int(timestamp_str)
            match_time_utc = datetime.fromtimestamp(match_timestamp, tz=pytz.utc)
            match_time_br = match_time_utc.astimezone(BR_TZ)

            # Extração do formato (Bo1, Bo3, etc.)
            match_format_element = match_block.find('span', class_='match-info-header-scoreholder-lower')
            match_format = match_format_element.get_text(strip=True) if match_format_element else "N/A"

            # Extração do nome do evento
            event_name_element = match_block.find('span', class_='match-info-tournament-name')
            event_name = event_name_element.get_text(strip=True) if event_name_element else "Evento Desconhecido"

            # Criação do evento no calendário
            event_summary = f"{team1_raw} vs {team2_raw}"
            event_description = f"Formato: {match_format}\nEvento: {event_name}\nLink: {LIQUIPEDIA_URL}"

            # Gerar um UID único e consistente para o evento
            event_uid_data = f"{event_summary}-{match_time_utc.isoformat()}-{event_name}"
            event_uid = hashlib.sha1(event_uid_data.encode('utf-8')).hexdigest()

            event = Event(
                name=event_summary,
                begin=match_time_br,
                end=match_time_br + timedelta(hours=3), # Duração estimada de 3 horas
                description=event_description,
                uid=event_uid
            )
            event.alarms.append(DisplayAlarm(trigger=timedelta(minutes=-30))) # Alarme 30 minutos antes
            cal.add_event(event)
            added_count += 1

        except ValueError as ve:
            # Não imprime logs de depuração, apenas erros críticos
            pass
        except Exception as e_inner:
            # Não imprime logs de depuração, apenas erros críticos
            pass

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

try:
    with open(CALENDAR_FILENAME, "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())
    print(f"\n📌 {added_count} partidas BR salvas em {CALENDAR_FILENAME} (com alarmes no horário do jogo)")
except Exception as e:
    print(f"❌ Erro ao salvar {CALENDAR_FILENAME}: {e}")
