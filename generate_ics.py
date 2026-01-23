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

TIPSGG_URL = "https://tips.gg/csgo/matches/"
CALENDAR_FILENAME = "calendar.ics"
BR_TZ = pytz.timezone('America/Sao_Paulo')

# -------------------- Funções Auxiliares --------------------
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

print(f"🔍 Abrindo navegador para {TIPSGG_URL} com Selenium...")

try:
    # Configurações do Chrome para rodar em ambiente headless (GitHub Actions)
    chrome_options = Options()
    chrome_options.add_argument("--headless") # Roda o navegador em segundo plano
    chrome_options.add_argument("--no-sandbox") # Necessário para ambientes Linux como GitHub Actions
    chrome_options.add_argument("--disable-dev-shm-usage") # Necessário para ambientes Linux
    chrome_options.add_argument("--window-size=1920,1080") # Define um tamanho de janela para evitar problemas de renderização
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    chrome_options.add_argument("--log-level=3") # Suprime logs desnecessários do Chrome

    # Usa ChromeDriverManager para gerenciar o chromedriver automaticamente
    # Isso baixa o chromedriver compatível e o configura no PATH temporariamente
    print("⚙️ Baixando e configurando ChromeDriver com webdriver_manager...")
    driver_path = ChromeDriverManager().install()
    service = Service(driver_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    print("⚙️ ChromeDriver configurado com sucesso.")

    driver.get(TIPSGG_URL)
    print(f"⚙️ Página {TIPSGG_URL} carregada com sucesso pelo Selenium.")

    # Espera até que os scripts JSON-LD estejam presentes
    # Aumentei o tempo de espera para 30 segundos, caso a página demore mais
    print("⚙️ Aguardando elementos JSON-LD na página...")
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'script[type="application/ld+json"]'))
    )
    print("✅ Elementos JSON-LD encontrados na página.")

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    # print("HTML da página (primeiros 500 caracteres):", driver.page_source[:500]) # Log para debug

    # Encontrar todos os blocos de script JSON-LD
    json_ld_scripts = soup.find_all('script', type='application/ld+json')
    print(f"📦 Encontrados {len(json_ld_scripts)} blocos JSON-LD na página.")

    for script_idx, script in enumerate(json_ld_scripts):
        try:
            data = json.loads(script.string)
            # print(f"JSON-LD {script_idx} decodificado: {data.get('name', 'N/A')}") # Log para debug

            if data.get('@type') == 'SportsEvent':
                event_name_raw = data.get('name', 'Desconhecido')
                event_description_raw = data.get('description', '')
                start_date_str = data.get('startDate')
                end_date_str = data.get('endDate') # Para calcular a duração
                match_url_raw = data.get('url')
                organizer_name = data.get('organizer', {}).get('name', 'Desconhecido')

                # Extrair times
                competitors = data.get('competitor', [])
                team1_raw = competitors[0].get('name') if len(competitors) > 0 else "TBD"
                team2_raw = competitors[1].get('name') if len(competitors) > 1 else "TBD"

                if team1_raw == "TBD" or team2_raw == "TBD":
                    # print(f"ℹ️ Ignorando partida {event_name_raw} devido a TBD.")
                    continue

                # Normaliza os nomes para a lógica de filtragem
                normalized_team1 = normalize_team(team1_raw)
                normalized_team2 = normalize_team(team2_raw)

                is_br_team1 = normalized_team1 in NORMALIZED_BRAZILIAN_TEAMS
                is_br_team2 = normalized_team2 in NORMALIZED_BRAZILIAN_TEAMS

                is_excluded_team1 = normalized_team1 in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS
                is_excluded_team2 = normalized_team2 in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS

                is_br_team_involved = (is_br_team1 and not is_excluded_team1) or \
                                      (is_br_team2 and not is_excluded_team2)

                if not is_br_team_involved:
                    # print(f"ℹ️ Ignorando partida {team1_raw} vs {team2_raw} (não é time BR principal).")
                    continue

                # Processar datas e fusos horários
                if not start_date_str:
                    # print(f"❌ Data de início não encontrada para {event_name_raw}.")
                    continue

                # O formato do tips.gg é ISO 8601 com offset de fuso horário (ex: 2026-01-23T12:00:00-0300)
                # datetime.fromisoformat() lida com isso automaticamente
                match_time_utc = datetime.fromisoformat(start_date_str).astimezone(pytz.utc)
                match_time_br = match_time_utc.astimezone(BR_TZ)

                # Filtrar partidas passadas (apenas futuras)
                if match_time_utc < datetime.now(pytz.utc) - timedelta(minutes=5): # Pequena margem para partidas que acabaram de começar
                    # print(f"ℹ️ Ignorando partida {team1_raw} vs {team2_raw} (já passou).")
                    continue

                # Calcular duração do evento
                event_duration = timedelta(hours=2) # Duração padrão
                if end_date_str:
                    try:
                        end_time_utc = datetime.fromisoformat(end_date_str).astimezone(pytz.utc)
                        event_duration = end_time_utc - match_time_utc
                        if event_duration.total_seconds() <= 0: # Garante que a duração seja positiva
                            event_duration = timedelta(hours=2)
                    except ValueError:
                        pass # Usa a duração padrão se houver erro na data final

                # Extrair formato da partida (BO1, BO3, etc.) da descrição
                match_format_match = re.search(r'(BO\d+)', event_description_raw, re.IGNORECASE)
                match_format = match_format_match.group(1).upper() if match_format_match else "BoX"

                # Extrair fase do torneio (Playoffs, Group D, etc.)
                # A fase está na descrição, ex: "BO3 Match. Playoffs. Malta. CS2 (CS:GO) Premier."
                stage_match = re.search(r'\.(.*?)\.', event_description_raw)
                stage = stage_match.group(1).strip() if stage_match else "Fase Desconhecida"
                # Remove "Match" e "BOx" da fase se estiverem presentes
                stage = stage.replace("Match", "").replace(match_format, "").strip()
                if stage.endswith('.'): stage = stage[:-1] # Remove ponto final se houver

                # Novo formato para o nome do evento (summary)
                event_summary = f"{team1_raw} vs {team2_raw} ({match_format})"

                # Novo formato para a descrição do evento
                event_description = (
                    f"🏆 Torneio: {organizer_name}\n"
                    f"⚔️ Formato: {match_format}\n"
                    f"📍 Fase: {stage}\n"
                    f"🌐 Link: https://tips.gg{match_url_raw}" # O URL do JSON-LD é relativo, precisa do domínio
                )

                event_uid = hashlib.sha1(event_summary.encode('utf-8') + str(match_time_utc).encode('utf-8')).hexdigest()

                e = Event()
                e.name = event_summary
                e.begin = match_time_utc # Armazena em UTC, o calendário lida com a conversão
                e.duration = event_duration
                e.description = event_description
                e.uid = event_uid

                # Adiciona alarme 15 minutos antes
                alarm = DisplayAlarm(trigger=timedelta(minutes=-15))
                e.alarms.append(alarm)

                cal.events.add(e)
                added_count += 1

                print(f"✅ Adicionado: {event_summary} em {match_time_br.strftime('%d/%m %H:%M')} BRT ({organizer_name})")

        except json.JSONDecodeError as je:
            print(f"❌ Erro ao decodificar JSON no script {script_idx}: {je}")
        except ValueError as ve:
            print(f"❌ Erro de dados no script {script_idx}: {ve}")
        except Exception as e_inner:
            print(f"❌ Erro inesperado ao processar script {script_idx}: {e_inner}")

except TimeoutException:
    print(f"❌ Erro: Tempo limite excedido ao carregar a página {TIPSGG_URL} ou encontrar elementos.")
except WebDriverException as we:
    print(f"❌ Erro do WebDriver (verifique se o chromedriver está no PATH e é compatível com seu Chrome): {we}")
    print("Dica: No GitHub Actions, certifique-se de usar 'browser-actions/setup-chrome@v1' para instalar o Chrome.")
except Exception as e:
    print(f"❌ Erro geral durante a execução do Selenium: {e}")
finally:
    if driver:
        print("⚙️ Fechando navegador Selenium.")
        driver.quit() # Garante que o navegador seja fechado, mesmo em caso de erro

print(f"\n💾 Salvando arquivo: {CALENDAR_FILENAME}")
try:
    with open(CALENDAR_FILENAME, "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())
    print(f"📌 Total de partidas adicionadas: {added_count}")
except Exception as e:
    print(f"❌ Erro ao salvar {CALENDAR_FILENAME}: {e}")
