from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
from ics import Calendar, Event
from ics.alarm import DisplayAlarm
import hashlib
import re
import time # Para adicionar pausas

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
CALENDAR_FILENAME = "calendar_selenium.ics" # Nome diferente para não sobrescrever

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

# -------------------- Lógica Principal com Selenium --------------------
cal = Calendar()
added_count = 0

print(f"🔍 Iniciando Selenium para buscar partidas em {LIQUIPEDIA_URL}...")

# Configurações do Selenium (usando Chrome, você pode mudar para Firefox, Edge, etc.)
# Certifique-se de que o chromedriver está no seu PATH ou especifique o caminho completo
options = webdriver.ChromeOptions()
options.add_argument('--headless') # Executa o navegador em modo headless (sem interface gráfica)
options.add_argument('--disable-gpu') # Necessário para headless em alguns sistemas
options.add_argument('--no-sandbox') # Necessário para ambientes Linux sem privilégios
options.add_argument('--window-size=1920,1080') # Define um tamanho de janela para renderização

driver = None # Inicializa driver como None
try:
    driver = webdriver.Chrome(options=options)
    driver.get(LIQUIPEDIA_URL)

    # Espera até que o conteúdo principal das partidas esteja visível
    # A classe 'match-info' é um bom indicador
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CLASS_NAME, 'match-info'))
    )
    print("✅ Página carregada e elementos de partida detectados.")

    # Opcional: Clicar em "All" e "Incoming" se não for o padrão
    # Na Liquipedia, "Incoming" geralmente é o padrão para "All", mas podemos simular o clique para garantir.
    try:
        # Tenta encontrar e clicar no filtro "All"
        all_filter = driver.find_element(By.XPATH, "//div[@class='filter-box' and contains(., 'All')]")
        if 'active' not in all_filter.get_attribute('class'):
            print("--- DEBUG: Clicando no filtro 'All'...")
            all_filter.click()
            time.sleep(1) # Pequena pausa para a UI reagir
        else:
            print("--- DEBUG: Filtro 'All' já está ativo.")

        # Tenta encontrar e clicar no filtro "Incoming" (geralmente dentro de "All")
        incoming_filter = driver.find_element(By.XPATH, "//div[@class='filter-box' and contains(., 'Incoming')]")
        if 'active' not in incoming_filter.get_attribute('class'):
            print("--- DEBUG: Clicando no filtro 'Incoming'...")
            incoming_filter.click()
            time.sleep(2) # Pausa maior para o conteúdo carregar após a filtragem
        else:
            print("--- DEBUG: Filtro 'Incoming' já está ativo.")

        # Espera novamente para garantir que as partidas foram atualizadas após o clique
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'match-info'))
        )
        print("✅ Filtros aplicados e conteúdo atualizado.")

    except NoSuchElementException:
        print("--- DEBUG: Filtros 'All' ou 'Incoming' não encontrados ou já ativos. Prosseguindo.")
    except TimeoutException:
        print("--- DEBUG: Tempo esgotado esperando pelos filtros. Prosseguindo.")


    # Pega o HTML da página após todas as interações
    page_source = driver.page_source
    soup = BeautifulSoup(page_source, 'html.parser')

    match_blocks = soup.find_all('div', class_='match-info')
    print(f"✅ Encontrados {len(match_blocks)} blocos de partidas individuais com a classe 'match-info'.")
    print(f"--- DEBUG: Normalized BR Teams (set): {NORMALIZED_BRAZILIAN_TEAMS}")
    print(f"--- DEBUG: Normalized Exclusions (set): {NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS}")

    for match_idx, match_block in enumerate(match_blocks, 1):
        team1_raw = "TBD"
        team2_raw = "TBD"
        event_name = "Desconhecido"
        match_url = LIQUIPEDIA_URL # Fallback para a URL principal
        match_format = "BoX"
        match_time_br = None # Inicializa para garantir que exista

        try:
            # Extrair timestamp e converter para BRT
            timestamp_str = match_block.find('span', class_='timer-object')['data-timestamp']
            match_time_utc = datetime.fromtimestamp(int(timestamp_str), tz=pytz.utc)
            match_time_br = match_time_utc.astimezone(BR_TZ)

            # Extrair nomes dos times
            all_opponent_divs = match_block.find_all('div', class_='match-info-header-opponent')

            if len(all_opponent_divs) < 2:
                print(f"--- DEBUG: Bloco {match_idx} ignorado: Não foi possível encontrar dois oponentes claros.")
                continue # Ignora se não houver dois oponentes claros

            team1_opponent_div = all_opponent_divs[0]
            team2_opponent_div = all_opponent_divs[1]

            team1_name_tag = team1_opponent_div.find('span', class_='name')
            team2_name_tag = team2_opponent_div.find('span', class_='name')

            if team1_name_tag and team1_name_tag.a:
                team1_raw = team1_name_tag.a.get_text(strip=True)
            elif team1_name_tag: # Caso não tenha link, mas tenha o span (ex: TBD)
                team1_raw = team1_name_tag.get_text(strip=True)

            if team2_name_tag and team2_name_tag.a:
                team2_raw = team2_name_tag.a.get_text(strip=True)
            elif team2_name_tag: # Caso não tenha link, mas tenha o span (ex: TBD)
                team2_raw = team2_name_tag.get_text(strip=True)

            # Ignorar partidas com TBD
            if team1_raw == "TBD" or team2_raw == "TBD":
                print(f"--- DEBUG: Bloco {match_idx} ignorado: Um ou ambos os times são 'TBD'.")
                continue

            # Normaliza os nomes para a lógica de filtragem
            normalized_team1 = normalize_team(team1_raw)
            normalized_team2 = normalize_team(team2_raw)

            # Verifica se algum dos times é brasileiro
            is_br_team_involved = (normalized_team1 in NORMALIZED_BRAZILIAN_TEAMS or
                                   normalized_team2 in NORMALIZED_BRAZILIAN_TEAMS)

            # Verifica se algum dos times é uma exclusão
            is_excluded_team_involved = (normalized_team1 in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS or
                                         normalized_team2 in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS)

            # Lógica de filtragem: Inclui se tiver time BR E não for uma exclusão
            if not is_br_team_involved or is_excluded_team_involved:
                print(f"--- DEBUG: Bloco {match_idx} ignorado: Nenhum time BR envolvido ou time excluído. Times '{team1_raw}' (norm: '{normalized_team1}') vs '{team2_raw}' (norm: '{normalized_team2}')")
                continue

            # Extrair nome do evento
            tournament_name_tag = match_block.find('span', class_='match-info-tournament-name')
            if tournament_name_tag and tournament_name_tag.a and tournament_name_tag.a.span:
                event_name = tournament_name_tag.a.span.get_text(strip=True)

            # Extrair formato da partida (Bo1, Bo3, etc.)
            match_format_tag = match_block.find('span', class_='match-info-header-scoreholder-lower')
            if match_format_tag:
                match_format = match_format_tag.get_text(strip=True).replace('(', '').replace(')', '')

            # Extrair URL da partida
            match_link_tag = match_block.find('div', class_='match-info-links')
            if match_link_tag and match_link_tag.a:
                match_url = "https://liquipedia.net" + match_link_tag.a['href']
            else: # Tenta pegar o link do torneio se não houver link específico da partida
                if tournament_name_tag and tournament_name_tag.a:
                    match_url = "https://liquipedia.net" + tournament_name_tag.a['href']

            # Gerar UID único para o evento
            event_uid_data = f"{team1_raw}-{team2_raw}-{event_name}-{match_time_utc.isoformat()}"
            event_uid = hashlib.sha1(event_uid_data.encode('utf-8')).hexdigest() + '@liquipedia.net'

            # Adicionar evento ao calendário
            e = Event()
            e.name = f"{team1_raw} vs {team2_raw} | {event_name} ({match_format})"
            e.begin = match_time_br
            e.duration = timedelta(hours=2) # Duração padrão de 2 horas
            e.description = f"Evento: {event_name}\nLink: {match_url}"
            e.uid = event_uid

            # Adiciona alarme 15 minutos antes
            alarm = DisplayAlarm(trigger=timedelta(minutes=-15))
            e.alarms.append(alarm)

            cal.events.add(e)
            added_count += 1
            print(f"      ✅ Adicionado: {team1_raw} vs {team2_raw} ({match_time_br.strftime('%d/%m %H:%M')}) | {match_format} | Evento: {event_name}")

        except ValueError as ve:
            print(f"      ❌ Erro de dados no bloco {match_idx}: {ve}")
        except Exception as e_inner:
            print(f"      ❌ Erro ao processar bloco {match_idx}: {e_inner} | Dados parciais: Team1='{team1_raw}', Team2='{team2_raw}', Evento='{event_name}'")

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
