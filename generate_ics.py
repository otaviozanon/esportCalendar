import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
from ics import Calendar, Event

# -------------------- Configurações --------------------
# Lista de times brasileiros
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo",
                   "Sharks", "RED Canids", "Legacy", "ODDIK", "Keyd"]
URL_LIQUIPEDIA = "https://liquipedia.net/counterstrike/Liquipedia:Matches"
BR_TZ = pytz.timezone("America/Sao_Paulo")
cal = Calendar()
added_count = 0

print(f"🔍 Buscando partidas em {URL_LIQUIPEDIA}...")

# -------------------- Coleta de partidas (Liquipedia) --------------------
try:
    # 1. Requisição HTTP
    response = requests.get(URL_LIQUIPEDIA, timeout=10)
    response.raise_for_status() # Lança exceção para status codes de erro (4xx ou 5xx)

    # 2. Parsing do HTML
    soup = BeautifulSoup(response.text, 'lxml')
    
    # ------------------------------------------------------------------
    # --- NOVO: Focar em todas as tabelas individuais de partidas ---
    # Usando o seletor completo que contém a classe identificada pelo usuário.
    MATCH_TABLE_CLASS = 'wikitable wikitable-striped infobox_matches_content'
    match_tables = soup.find_all('table', class_=MATCH_TABLE_CLASS)
    
    print(f"✅ Encontrados {len(match_tables)} blocos de partidas individuais com a classe '{MATCH_TABLE_CLASS}'.")

    if not match_tables:
        print("⚠️ Nenhum bloco de partida encontrado. Verifique se a classe da tabela mudou.")
        exit()
    # ------------------------------------------------------------------


    # 3. Iterar pelas tabelas individuais de partidas
    for match_idx, match_table in enumerate(match_tables, 1):
        team1, team2, event_name, match_url = 'N/A', 'N/A', 'N/A', URL_LIQUIPEDIA
        match_format = 'Partida' # Variável para o formato (Bo1, Bo3, etc.)
        
        try:
            # Uma tabela de partida tem 2 linhas (TRs): 
            # TR[0]: Times/vs
            # TR[1]: Filler (Data/Evento/Streams)
            rows = match_table.find_all('tr') 
            
            if len(rows) < 2:
                print(f"      ⚠️ Partida {match_idx}: Tabela incompleta (menos de 2 linhas). Pulando.")
                continue

            # --- Extração da TR[0] (Times e Formato) ---
            # Colunas são: [0] Time 1, [1] vs (formato), [2] Time 2
            team_cols = rows[0].find_all('td', recursive=False)
            
            # Times
            team1_tag = team_cols[0].find('span', class_='team-template-text')
            team2_tag = team_cols[2].find('span', class_='team-template-text')
            
            team1 = team1_tag.text.strip() if team1_tag else team_cols[0].text.strip()
            team2 = team2_tag.text.strip() if team2_tag else team_cols[2].text.strip()

            # Formato (BoX)
            if len(team_cols) > 1:
                versus_col = team_cols[1]
                # Busca pela tag <abbr> dentro da coluna 'versus'
                format_abbr = versus_col.find('abbr')
                if format_abbr and format_abbr.text:
                    match_format = format_abbr.text.strip()
            
            # --- Extração da TR[1] (Data/Evento) ---
            time_tag = rows[1].find('span', class_='timer-object')
            
            # 1. Data/Hora
            if not time_tag or 'data-timestamp' not in time_tag.attrs:
                print(f"      ⚠️ Partida {match_idx} ({team1} vs {team2}): Sem timestamp válido (TBD/Adiamento).")
                continue

            try:
                time_unix_timestamp = int(time_tag['data-timestamp'])
                match_time_utc = datetime.fromtimestamp(time_unix_timestamp, tz=pytz.utc)
            except ValueError:
                print(f"      ❌ Partida {match_idx} ({team1} vs {team2}): Falha ao converter timestamp para inteiro.")
                continue
            
            # 2. Evento (Busca o link de texto do evento dentro da classe 'text-nowrap')
            event_name_tag = rows[1].find('div', class_='text-nowrap')
            event_link = event_name_tag.find('a') if event_name_tag else None

            if event_link and event_link.text.strip():
                event_name = event_link.text.strip()
                match_url = f"https://liquipedia.net{event_link['href']}" if 'href' in event_link.attrs else URL_LIQUIPEDIA
            else:
                event_name = "Evento Desconhecido"
                match_url = URL_LIQUIPEDIA
            
            # 3. Verifica BR
            if not any(br.lower() in team1.lower() or br.lower() in team2.lower() for br in BRAZILIAN_TEAMS):
                continue

            # ----------------- Criação do Evento ICS -----------------
            match_time_br = match_time_utc.astimezone(BR_TZ)
            
            # Mapeamento do formato (BoX) para descrição completa
            format_map = {
                'Bo1': 'Best of 1 (Bo1)',
                'Bo3': 'Best of 3 (Bo3)',
                'Bo5': 'Best of 5 (Bo5)',
                'Partida': 'Partida Simples' # Default fallback
            }
            full_match_format = format_map.get(match_format, match_format)

            e = Event()
            # SUMMARY (Título): Apenas Times (Ex: Falcons vs Natus Vincere)
            e.name = f"{team1} vs {team2}" 
            e.begin = match_time_utc.astimezone(pytz.utc) 
            e.end = e.begin + timedelta(hours=2)
            
            # DESCRIPTION: Padrão Solicitado
            e.description = (
                f"Horário de Brasília\n\n"
                f"🎮 Format: {full_match_format}\n"
                f"📅 Event: {event_name} ⭐"
            )
            e.url = match_url

            cal.events.add(e)
            added_count += 1
            print(f"      ✅ Adicionado: {e.name} ({match_time_br.strftime('%d/%m %H:%M')}) | Formato: {full_match_format} | Evento: {event_name}")

        except Exception as e:
            # Loga o erro específico para ajudar na depuração
            print(f"      ❌ Erro ao processar bloco de partida {match_idx} ({team1} vs {team2}): {e}")

except requests.exceptions.RequestException as e:
    print(f"❌ Erro ao acessar {URL_LIQUIPEDIA}: Falha na requisição HTTP - {e}")
except Exception as e:
    print(f"❌ Erro inesperado durante o scraping: {e}")

# -------------------- Finalizar --------------------
# Salvar calendar.ics
try:
    with open("calendar.ics", "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())
    print(f"\n📌 {added_count} partidas BR salvas em calendar.ics")
except Exception as e:
    print(f"❌ Erro ao salvar calendar.ics: {e}")
