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
driver = None # Inicializa driver como None para o bloco finally

print(f"🔍 Abrindo navegador para {TIPSGG_URL} com Selenium...")

try:
    # Configurações do Chrome para rodar em modo headless no GitHub Actions
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox") # Necessário para ambientes Linux como GitHub Actions
    chrome_options.add_argument("--disable-dev-shm-usage") # Necessário para ambientes Linux
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    chrome_options.add_argument("--window-size=1920,1080") # Garante uma resolução padrão

    print("⚙️ Baixando e configurando ChromeDriver com webdriver_manager...")
    service = Service(ChromeDriverManager().install())
    print("⚙️ ChromeDriver configurado com sucesso.")

    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.get(TIPSGG_URL)
    print(f"⚙️ Página {TIPSGG_URL} carregada com sucesso pelo Selenium.")

    # Espera até que os scripts JSON-LD estejam presentes
    print("⚙️ Aguardando elementos JSON-LD na página...")
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'script[type="application/ld+json"]'))
    )
    print("✅ Elementos JSON-LD encontrados na página.")

    soup = BeautifulSoup(driver.page_source, 'html.parser')

    # Encontra todos os blocos de script JSON-LD
    json_ld_scripts = soup.find_all('script', type='application/ld+json')
    print(f"📦 Encontrados {len(json_ld_scripts)} blocos JSON-LD na página.")

    current_time_br = datetime.now(BR_TZ) # Pega o horário atual em BRT para comparar com os jogos

    for script_idx, script in enumerate(json_ld_scripts, 1):
        try:
            data = json.loads(script.string)

            # Verifica se é um SportsEvent e se tem os campos necessários
            if data.get('@type') == 'SportsEvent' and data.get('name') and data.get('startDate') and data.get('competitor'):
                event_name_full = data['name']
                start_date_str = data['startDate']
                competitors = data['competitor']
                match_url_raw = data.get('url')
                organizer_name = data.get('organizer', {}).get('name', 'Desconhecido')
                description_raw = data.get('description', '') # A descrição pode conter o formato (BO1, BO3)

                # Extrair formato da partida (BO1, BO3, etc.) da descrição
                match_format_match = re.search(r'(BO\d+)', description_raw, re.IGNORECASE)
                match_format = match_format_match.group(1).upper() if match_format_match else "BoX"

                # Extrair nomes dos times
                team1_raw = competitors[0]['name'] if len(competitors) > 0 else "TBD"
                team2_raw = competitors[1]['name'] if len(competitors) > 1 else "TBD"

                # Converte a data/hora para o fuso horário de Brasília
                # O formato de startDate é ISO 8601, ex: "2026-01-23T12:00:00-0300"
                match_time_utc = datetime.fromisoformat(start_date_str).astimezone(pytz.utc)
                match_time_br = match_time_utc.astimezone(BR_TZ)

                # --- Lógica de Filtragem ---
                print(f"\n--- Processando Partida {script_idx}: {team1_raw} vs {team2_raw} ({match_time_br.strftime('%d/%m %H:%M')}) ---")

                # 1. Ignorar partidas com TBD
                if team1_raw == "TBD" or team2_raw == "TBD":
                    print(f"🚫 Ignorando: Times TBD ({team1_raw} vs {team2_raw})")
                    continue

                # 2. Ignorar partidas que já aconteceram (apenas futuras)
                if match_time_br < current_time_br:
                    print(f"🚫 Ignorando: Partida já ocorreu ({match_time_br.strftime('%d/%m %H:%M')})")
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

                print(f"  Time 1: '{team1_raw}' (Normalizado: '{normalized_team1}') - É BR: {is_br_team1}, Excluído: {is_excluded_team1}")
                print(f"  Time 2: '{team2_raw}' (Normalizado: '{normalized_team2}') - É BR: {is_br_team2}, Excluído: {is_excluded_team2}")

                if not is_br_team_involved:
                    print("🚫 Ignorando: Nenhum time BR principal (não excluído) envolvido.")
                    continue # Ignora se nenhum time BR principal (não excluído) estiver envolvido

                print("✅ Partida atende aos critérios de time BR.")

                # Construir o resumo e a descrição do evento
                event_summary = f"{team1_raw} vs {team2_raw}"
                event_description = (
                    f"🏆 {match_format}\n"
                    f"📍 {organizer_name}\n"
                    f"🌐 https://tips.gg{match_url_raw}" # tips.gg retorna URL relativa, precisa do domínio
                )

                # Gerar UID único para o evento
                event_uid = hashlib.sha1(event_summary.encode('utf-8') + str(match_time_utc.timestamp()).encode('utf-8')).hexdigest()

                e = Event()
                e.name = event_summary
                e.begin = match_time_utc # O calendário lida bem com datetimes timezone-aware
                e.duration = timedelta(hours=2) # Duração padrão de 2 horas
                e.description = event_description
                e.uid = event_uid

                # Adiciona alarme 15 minutos antes
                alarm = DisplayAlarm(trigger=timedelta(minutes=-15))
                e.alarms.append(alarm)

                cal.events.add(e)
                added_count += 1
                print(f"🎉 Adicionado ao calendário: '{event_summary}'")

            else:
                print(f"⚠️ Script {script_idx}: JSON-LD não é um SportsEvent válido ou faltam campos essenciais.")

        except json.JSONDecodeError as je:
            print(f"❌ Erro ao decodificar JSON no script {script_idx}: {je}")
        except ValueError as ve:
            print(f"❌ Erro de dados no script {script_idx}: {ve}")
        except Exception as e_inner:
            print(f"❌ Erro inesperado ao processar script {script_idx}: {e_inner}")

except requests.exceptions.RequestException as e:
    print(f"❌ Falha na requisição HTTP - {e}")
except TimeoutException:
    print("❌ Tempo limite excedido ao carregar a página ou aguardar elementos.")
except WebDriverException as e:
    print(f"❌ Erro do WebDriver (verifique se o chromedriver está no PATH e é compatível com seu Chrome): {e}")
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
