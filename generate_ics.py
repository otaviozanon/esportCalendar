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
        
        try:
            # Uma tabela de partida tem 2 linhas (TRs): 
            # TR[0]: Times/vs
            # TR[1]: Filler (Data/Evento/Streams)
            rows = match_table.find_all('tr', recursive=False)
            
            if len(rows) < 2:
                print(f"      ⚠️ Partida {match_idx}: Tabela incompleta (menos de 2 linhas). Pulando.")
                continue

            # --- Extração da TR[0] (Times) ---
            team_cols = rows[0].find_all('td', recursive=False)
            # Colunas são: [0] Time 1, [1] vs, [2] Time 2
            
            # Seletores mais robustos para nomes de times (dentro de team-template-text)
            team1_tag = team_cols[0].find('span', class_='team-template-text')
            team2_tag = team_cols[2].find('span', class_='team-template-text')
            
            team1 = team1_tag.text.strip() if team1_tag else team_cols[0].text.strip()
            team2 = team2_tag.text.strip() if team2_tag else team_cols[2].text.strip()

            # --- Extração da TR[1] (Data/Evento) ---
            # O filler/data está na primeira e única TD da segunda linha (TR[1])
            time_tag = rows[1].find('span', class_='timer-object')
            event_tag = rows[1].find('a') # O link do evento (que é o nome do evento)
            
            # 1. Data/Hora
            if not time_tag or 'data-timestamp' not in time_tag.attrs:
                print(f"      ⚠️ Partida {match_idx} ({team1} vs {team2}): Sem timestamp válido (TBD/Adiamento).")
                continue

            time_utc_str = time_tag['data-timestamp']
            match_time_utc = datetime.fromisoformat(time_utc_str.replace('Z', '+00:00'))
            
            # 2. Evento
            event_name = event_tag.text.strip() if event_tag else "Evento Desconhecido"
            match_url = f"https://liquipedia.net{event_tag['href']}" if event_tag and 'href' in event_tag.attrs else URL_LIQUIPEDIA
            
            # 3. Verifica BR
            if not any(br.lower() in team1.lower() or br.lower() in team2.lower() for br in BRAZILIAN_TEAMS):
                print(f"      ➡️ Partida {match_idx}: Nenhum time BR ({team1} vs {team2}). Ignorando.")
                continue

            # ----------------- Criação do Evento ICS -----------------
            match_time_br = match_time_utc.astimezone(BR_TZ)

            e = Event()
            e.name = f"{team1} vs {team2} - {event_name}"
            e.begin = match_time_utc.astimezone(pytz.utc) 
            e.end = e.begin + timedelta(hours=2)
            e.description = f"Partida entre {team1} e {team2} no evento {event_name} (Horário de Brasília)"
            e.url = match_url

            cal.events.add(e)
            added_count += 1
            print(f"      ✅ Adicionado: {e.name} ({match_time_br.strftime('%d/%m %H:%M')}) | URL: {e.url}")

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
