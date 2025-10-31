import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
from ics import Calendar, Event
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# -------------------- Configurações Globais --------------------
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo",
                   "RED Canids", "Legacy", "ODDIK"]

BRAZILIAN_TEAMS_EXCLUSIONS = ["Imperial.A", "Imperial Fe", "MIBR.A"]

URL_HLTV = "https://www.hltv.org/matches"
URL_LIQUIPEDIA = "https://liquipedia.net/counterstrike/Liquipedia:Matches"
BR_TZ = pytz.timezone("America/Sao_Paulo")

cal = Calendar()
added_count = 0
unique_matches = set()


# -------------------- Função para scraping do HLTV com Selenium --------------------
def scrape_hltv_selenium():
    """Busca partidas do HLTV usando Selenium"""
    print("=" * 60)
    print(f"🔍 Tentando buscar partidas do HLTV ({URL_HLTV})...")
    print("=" * 60)
    
    driver = None
    try:
        # Configurações do Chrome para rodar em headless (sem interface gráfica)
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Instala e configura o ChromeDriver automaticamente
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        print("🌐 Carregando página do HLTV...")
        driver.get(URL_HLTV)
        
        # Aguarda a página carregar completamente
        time.sleep(5)
        
        # Aguarda os elementos de partida aparecerem
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, "upcomingMatch"))
        )
        
        print("✅ Página carregada com sucesso!")
        
        # Pega o HTML renderizado
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'lxml')
        
        # Busca todas as partidas
        matches = soup.find_all('div', class_='upcomingMatch')
        
        if not matches:
            print("⚠️ Nenhuma partida encontrada no HLTV")
            return False
        
        print(f"✅ Encontradas {len(matches)} partidas no HLTV\n")
        
        global added_count
        
        for match in matches:
            try:
                # Extrai os times
                team_divs = match.find_all('div', class_='matchTeamName')
                if len(team_divs) < 2:
                    continue
                
                team1 = team_divs[0].text.strip()
                team2 = team_divs[1].text.strip()
                
                # Verifica se é time BR
                is_team_br = any(br.lower() in team1.lower() or br.lower() in team2.lower() 
                               for br in BRAZILIAN_TEAMS)
                is_excluded = any(ex.lower() in team1.lower() or ex.lower() in team2.lower() 
                                for ex in BRAZILIAN_TEAMS_EXCLUSIONS)
                
                if not is_team_br or is_excluded:
                    continue
                
                # Extrai o horário (timestamp Unix em milissegundos)
                time_div = match.find('div', class_='matchTime')
                if not time_div or 'data-unix' not in time_div.attrs:
                    continue
                
                time_unix = int(time_div['data-unix']) / 1000  # Converte de ms para segundos
                match_time_utc = datetime.fromtimestamp(time_unix, tz=pytz.utc)
                
                # Extrai o nome do evento
                event_div = match.find('div', class_='matchEventName')
                event_name = event_div.text.strip() if event_div else "Evento Desconhecido"
                
                # Extrai o formato (Bo1, Bo3, etc)
                format_div = match.find('div', class_='bestOf')
                match_format = format_div.text.strip() if format_div else "Partida"
                
                # Extrai a URL da partida
                match_link = match.find('a', class_='match')
                match_url = f"https://www.hltv.org{match_link['href']}" if match_link and 'href' in match_link.attrs else URL_HLTV
                
                # Mapeia o formato
                format_map = {
                    'Bo1': 'Best of 1 (Bo1)',
                    'Bo3': 'Best of 3 (Bo3)',
                    'Bo5': 'Best of 5 (Bo5)',
                }
                full_match_format = format_map.get(match_format, match_format)
                
                # Cria o evento
                e = Event()
                e.name = f"{team1} vs {team2}"
                e.begin = match_time_utc
                e.end = e.begin + timedelta(hours=2)
                e.description = (
                    f"🎮 Format: {full_match_format}\n"
                    f"📅 Event: {event_name}\n"
                    f"🌐 Source: HLTV"
                )
                e.url = match_url
                
                # Evita duplicatas
                sorted_teams = tuple(sorted([team1.lower().strip(), team2.lower().strip()]))
                match_key = (sorted_teams, e.begin.isoformat(), event_name.lower().strip())
                
                if match_key in unique_matches:
                    continue
                
                unique_matches.add(match_key)
                cal.events.add(e)
                added_count += 1
                
                match_time_br = match_time_utc.astimezone(BR_TZ)
                print(f"   ✅ [HLTV] {e.name} ({match_time_br.strftime('%d/%m %H:%M')}) | {full_match_format} | {event_name}")
                
            except Exception as e:
                print(f"   ⚠️ Erro ao processar partida: {e}")
                continue
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao acessar HLTV com Selenium: {e}")
        return False
    
    finally:
        if driver:
            driver.quit()
            print("\n🔒 Navegador fechado")


# -------------------- Função para scraping do Liquipedia (fallback) --------------------
def scrape_liquipedia():
    """Busca partidas do Liquipedia como fallback"""
    print("\n" + "=" * 60)
    print(f"🔄 Usando Liquipedia como fallback ({URL_LIQUIPEDIA})...")
    print("=" * 60)
    
    try:
        response = requests.get(URL_LIQUIPEDIA, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')

        MATCH_TABLE_CLASS = 'wikitable wikitable-striped infobox_matches_content'
        match_tables = soup.find_all('table', class_=MATCH_TABLE_CLASS)

        print(f"✅ Encontrados {len(match_tables)} blocos de partidas no Liquipedia\n")

        if not match_tables:
            print("⚠️ Nenhum bloco de partida encontrado no Liquipedia")
            return False

        global added_count

        for match_idx, match_table in enumerate(match_tables, 1):
            team1, team2, event_name, match_url = 'N/A', 'N/A', 'N/A', URL_LIQUIPEDIA
            match_format = 'Partida'

            try:
                rows = match_table.find_all('tr')
                if len(rows) < 2:
                    continue

                team_cols = rows[0].find_all('td', recursive=False)
                team1_tag = team_cols[0].find('span', class_='team-template-text')
                team2_tag = team_cols[2].find('span', class_='team-template-text')

                team1 = team1_tag.text.strip() if team1_tag else team_cols[0].text.strip()
                team2 = team2_tag.text.strip() if team2_tag else team_cols[2].text.strip()

                if len(team_cols) > 1:
                    versus_col = team_cols[1]
                    format_abbr = versus_col.find('abbr')
                    if format_abbr and format_abbr.text:
                        match_format = format_abbr.text.strip()

                time_tag = rows[1].find('span', class_='timer-object')

                if not time_tag or 'data-timestamp' not in time_tag.attrs:
                    continue

                try:
                    time_unix_timestamp = int(time_tag['data-timestamp'])
                    match_time_utc = datetime.fromtimestamp(time_unix_timestamp, tz=pytz.utc)
                except ValueError:
                    continue

                event_name_tag = rows[1].find('div', class_='text-nowrap')
                event_link = event_name_tag.find('a') if event_name_tag else None

                if event_link and event_link.text.strip():
                    event_name = event_link.text.strip()
                    match_url = f"https://liquipedia.net{event_link['href']}" if 'href' in event_link.attrs else URL_LIQUIPEDIA
                else:
                    event_name = "Evento Desconhecido"
                    match_url = URL_LIQUIPEDIA

                is_team_br = any(br.lower() in team1.lower() or br.lower() in team2.lower() for br in BRAZILIAN_TEAMS)
                is_excluded = any(ex.lower() in team1.lower() or ex.lower() in team2.lower() for ex in BRAZILIAN_TEAMS_EXCLUSIONS)

                if not is_team_br or is_excluded:
                    continue

                format_map = {
                    'Bo1': 'Best of 1 (Bo1)',
                    'Bo3': 'Best of 3 (Bo3)',
                    'Bo5': 'Best of 5 (Bo5)',
                    'Partida': 'Partida Simples'
                }
                full_match_format = format_map.get(match_format, match_format)

                e = Event()
                e.name = f"{team1} vs {team2}"
                e.begin = match_time_utc
                e.end = e.begin + timedelta(hours=2)
                e.description = (
                    f"🎮 Format: {full_match_format}\n"
                    f"📅 Event: {event_name}\n"
                    f"🌐 Source: Liquipedia"
                )
                e.url = match_url

                sorted_teams = tuple(sorted([team1.lower().strip(), team2.lower().strip()]))
                match_key = (sorted_teams, e.begin.isoformat(), event_name.lower().strip())

                if match_key in unique_matches:
                    continue

                unique_matches.add(match_key)
                cal.events.add(e)
                added_count += 1
                
                match_time_br = match_time_utc.astimezone(BR_TZ)
                print(f"   ✅ [Liquipedia] {e.name} ({match_time_br.strftime('%d/%m %H:%M')}) | {full_match_format} | {event_name}")

            except Exception as e:
                print(f"   ⚠️ Erro ao processar bloco {match_idx}: {e}")
        
        return True

    except requests.exceptions.RequestException as e:
        print(f"❌ Falha na requisição ao Liquipedia: {e}")
        return False
    except Exception as e:
        print(f"❌ Erro inesperado no Liquipedia: {e}")
        return False


# -------------------- Execução Principal --------------------
def main():
    print("\n" + "🎮" * 30)
    print("   CS2 Calendar Generator - HLTV (Selenium) + Liquipedia")
    print("🎮" * 30 + "\n")
    
    # Tenta HLTV com Selenium primeiro
    hltv_success = scrape_hltv_selenium()
    
    # Se HLTV falhar ou não retornar partidas BR, usa Liquipedia
    if not hltv_success or added_count == 0:
        if added_count == 0:
            print("\n⚠️ HLTV não retornou partidas de times BR. Tentando Liquipedia...")
        else:
            print("\n⚠️ HLTV falhou. Tentando Liquipedia...")
        
        time.sleep(2)
        liquipedia_success = scrape_liquipedia()
        
        if not liquipedia_success and added_count == 0:
            print("\n❌ Ambas as fontes falharam. Nenhuma partida foi adicionada.")
    
    # Salva o calendário
    print("\n" + "=" * 60)
    try:
        with open("calendar.ics", "w", encoding="utf-8") as f:
            f.writelines(cal.serialize_iter())
        print(f"✅ {added_count} partidas BR salvas em calendar.ics")
    except Exception as e:
        print(f"❌ Erro ao salvar calendar.ics: {e}")
    
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
