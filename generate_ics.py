import requests # Ainda útil para outras requisições, mas não para a principal
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

# -------------------- Configurações Globais --------------------
# Lista de times brasileiros principais (nomes como aparecem no HTML, mas serão normalizados para comparação)
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo",
                   "RED Canids", "Legacy", "ODDIK", "Imperial Esports"]

# Lista de exclusões (nomes como aparecem no HTML, mas serão normalizados para comparação)
BRAZILIAN_TEAMS_EXCLUSIONS = [
    "Imperial.A", "Imperial Fe", "MIBR.A", "paiN.A", "ODDIK.A",
    "Imperial Academy", "Imperial.Acd", "Imperial Female",
    "Furia Academy", "Furia.A", "Pain Academy", "Mibr Academy",
    "Legacy Academy", "ODDIK Academy", "RED Canids Academy",
    "Fluxo Academy"
]

TIPSGG_URL = "https://tips.gg/csgo/matches/"
CALENDAR_FILENAME = "calendar.ics"
BR_TZ = pytz.timezone('America/Sao_Paulo') # Fuso horário de Brasília

# -------------------- Funções Auxiliares --------------------
def normalize_team(name):
    """
    Normaliza o nome do time para comparação, convertendo para minúsculas e removendo espaços extras.
    Mantém caracteres especiais e espaços internos para comparações literais.
    """
    if not name:
        return ""
    return name.lower().strip()

# Pré-normaliza as listas de times para otimizar as comparações
NORMALIZED_BRAZILIAN_TEAMS = {normalize_team(team) for team in BRAZILIAN_TEAMS}
NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS = {normalize_team(team) for team in BRAZILIAN_TEAMS_EXCLUSIONS}

# -------------------- Lógica Principal --------------------
cal = Calendar()
added_count = 0

print(f"🔍 Abrindo navegador para {TIPSGG_URL} com Selenium...")

# Configurações do Selenium
chrome_options = Options()
chrome_options.add_argument("--headless")  # Roda o navegador em segundo plano (sem interface gráfica)
chrome_options.add_argument("--disable-gpu") # Necessário para headless em alguns sistemas
chrome_options.add_argument("--no-sandbox") # Necessário para headless em alguns ambientes (ex: Docker)
chrome_options.add_argument("--window-size=1920,1080") # Define um tamanho de janela para evitar problemas de layout
chrome_options.add_argument(f"user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36") # User-Agent

# O caminho para o chromedriver. Se estiver no PATH do sistema, pode ser apenas 'chromedriver'
# Se não, especifique o caminho completo, por exemplo: service = Service('/caminho/para/seu/chromedriver')
service = Service('chromedriver') # Assumindo que 'chromedriver' está no PATH ou no mesmo diretório

driver = None # Inicializa driver como None para o bloco finally

try:
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.get(TIPSGG_URL)

    # Espera até que os elementos de script JSON-LD estejam presentes na página
    # Isso é crucial, pois o conteúdo pode ser carregado dinamicamente
    print("⏳ Esperando o conteúdo da página carregar...")
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'script[type="application/ld+json"]'))
    )
    print("✅ Conteúdo carregado!")

    # Agora que a página está carregada (e o JS executado), pegamos o HTML completo
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    script_blocks = soup.find_all('script', type='application/ld+json')
    print(f"✅ Encontrados {len(script_blocks)} blocos de script JSON-LD.")

    current_time_br = datetime.now(BR_TZ)
    print(f"⏰ Horário atual em BRT: {current_time_br.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")

    for script_idx, script_tag in enumerate(script_blocks, 1):
        json_content = script_tag.string
        if not json_content:
            # print(f"  ⚠️ Script {script_idx} vazio, ignorando.")
            continue

        # print(f"\n--- Processando script {script_idx} ---")
        # print("  Conteúdo JSON-LD bruto:", json_content[:200], "...") # Log parcial para não poluir muito

        try:
            data = json.loads(json_content)

            # Verifica se é um SportsEvent e se tem os campos necessários
            if data.get('@type') == 'SportsEvent' and \
               data.get('name') and \
               data.get('startDate') and \
               data.get('competitor') and \
               len(data['competitor']) >= 2 and \
               data.get('organizer') and \
               data['organizer'].get('name') and \
               data.get('url'):

                team1_raw = data['competitor'][0]['name']
                team2_raw = data['competitor'][1]['name']
                start_raw = data['startDate']
                organizer_name = data['organizer']['name']
                match_url_raw = "https://tips.gg" + data['url'] # O URL no JSON é relativo
                description_raw = data.get('description', '') # A descrição pode conter o formato da partida

                # print(f"  Partida: {team1_raw} vs {team2_raw}")
                # print(f"  Início: {start_raw}")
                # print(f"  Evento: {organizer_name}")
                # print(f"  URL: {match_url_raw}")

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
                    # print(f"  🚫 Ignorando: Nenhum time BR principal (não excluído) envolvido. ({team1_raw}, {team2_raw})")
                    continue

                # Converter data/hora para o fuso horário de Brasília
                try:
                    # O formato do startDate é ISO 8601 com offset de fuso horário (-0300)
                    match_time_utc_aware = datetime.fromisoformat(start_raw)
                    match_time_br = match_time_utc_aware.astimezone(BR_TZ)
                except ValueError:
                    print(f"  ❌ Erro ao parsear data/hora '{start_raw}', ignorando.")
                    continue

                # Filtrar partidas que já aconteceram (considerando uma duração de 2 horas)
                # O usuário prefere considerar somente partidas futuras.
                if match_time_br + timedelta(hours=2) < current_time_br:
                    # print(f"  🚫 Ignorando: Partida já ocorreu ou está em andamento. ({match_time_br} < {current_time_br})")
                    continue

                # Extrair formato da partida (Bo1, Bo3, etc.) da descrição
                match_format_match = re.search(r'(BO\d+)\sMatch', description_raw)
                match_format = match_format_match.group(1) if match_format_match else "BoX"

                # Novo formato para o nome do evento (summary)
                event_summary = f"{team1_raw} vs {team2_raw}"

                # Novo formato para a descrição do evento
                event_description = (
                    f"🏆- {match_format}\n"
                    f"📍{organizer_name}\n"
                    f"🌐{match_url_raw}"
                )

                # Gerar UID único para o evento
                event_uid = hashlib.sha1(
                    (event_summary + start_raw).encode("utf-8")
                ).hexdigest()

                # print("🆔 UID:", event_uid)

                e = Event()
                e.name = event_summary
                e.begin = match_time_br # O objeto `ics` lida bem com datetimes timezone-aware
                e.duration = timedelta(hours=2) # Duração padrão de 2 horas
                e.description = event_description
                e.uid = event_uid

                # Adiciona alarme 15 minutos antes
                alarm = DisplayAlarm(trigger=timedelta(minutes=-15))
                e.alarms.append(alarm)

                cal.events.add(e)
                added_count += 1

                print(f"✅ Adicionado ao calendário: {event_summary} em {match_time_br.strftime('%H:%M')}")

            else:
                # print(f"  ⚠️ Script {script_idx} não é um SportsEvent válido ou está incompleto, ignorando.")
                pass

        except json.JSONDecodeError as je:
            print(f"❌ Erro ao decodificar JSON no script {script_idx}: {je}")
        except ValueError as ve:
            print(f"❌ Erro de dados no script {script_idx}: {ve}")
        except Exception as e_inner:
            print(f"❌ Erro inesperado ao processar script {script_idx}: {e_inner}")

except TimeoutException:
    print("❌ Tempo limite excedido ao carregar a página. O site pode estar demorando muito ou bloqueando.")
except WebDriverException as we:
    print(f"❌ Erro do WebDriver (verifique se o chromedriver está no PATH e é compatível com seu Chrome): {we}")
except Exception as e:
    print(f"❌ Erro geral durante a execução do Selenium: {e}")
finally:
    if driver:
        driver.quit() # Garante que o navegador seja fechado, mesmo em caso de erro

print(f"\n💾 Salvando arquivo: {CALENDAR_FILENAME}")
try:
    with open(CALENDAR_FILENAME, "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())
    print(f"📌 Total de partidas adicionadas: {added_count}")
except Exception as e:
    print(f"❌ Erro ao salvar {CALENDAR_FILENAME}: {e}")
