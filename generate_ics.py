import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
from ics import Calendar, Event

# -------------------- Configurações --------------------
# Lista de times brasileiros (mantenha como está)
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

    # 2. Parsing do HTML usando lxml (mais rápido)
    soup = BeautifulSoup(response.text, 'lxml')
    
    # --- Lógica de Seleção Robusta da Tabela ---
    match_table = None
    # Liquipedia usa 'wikitable' para várias tabelas. Vamos encontrar a principal
    all_wikitables = soup.find_all('table', class_='wikitable')

    # Tentativa 1: Encontrar a tabela que contém o cabeçalho 'vs' (indicador de partidas)
    for table in all_wikitables:
        if table.find('th', string='vs'):
            match_table = table
            print("✅ Tabela de partidas encontrada pelo cabeçalho 'vs'.")
            break
    
    # Tentativa 2: Se não encontrar, assume a primeira tabela grande (pode ser a correta)
    if not match_table and all_wikitables:
         match_table = all_wikitables[0]
         print("✅ Tabela de partidas encontrada como a primeira 'wikitable'.")


    if not match_table:
        print("⚠️ Tabela de partidas principal não encontrada no HTML.")
        exit()
    # ---------------------------------------------

    # 3. Iterar pelas linhas (TRs) da tabela, pulando o cabeçalho
    # O seletor 'tr[data-url]' pode ajudar a focar nas linhas de partidas
    rows = match_table.find_all('tr', recursive=False)[1:] # [1:] para pular o cabeçalho
    print(f"📦 {len(rows)} linhas de partidas encontradas para processamento.")

    for row_idx, row in enumerate(rows, 1):
        try:
            # Ignora linhas que são separadores de data/título (geralmente não têm <td>)
            if not row.find('td'):
                continue
                
            # Colunas da tabela
            cols = row.find_all('td', recursive=False)
            
            if len(cols) < 5: 
                continue

            # --- Extração de Data/Hora (UTC) ---
            time_tag = cols[0].find('span', class_='timer-object')
            
            if not time_tag or 'data-timestamp' not in time_tag.attrs:
                # Partida TBD ou Aguardando Data
                continue

            time_utc_str = time_tag['data-timestamp']
            
            # Converte para objeto datetime, garantindo que seja UTC
            match_time_utc = datetime.fromisoformat(time_utc_str.replace('Z', '+00:00'))
            
            
            # --- Extração dos Times e Evento ---
            # Time 1 e Time 2 (índice 1 e 3)
            # Os nomes dos times estão em um <a> dentro do <td>.
            # Usando .find('a') ou .find('span', class_='team-template-text')
            
            team1_tag = cols[1].find(['a', 'span'], class_='team-template-text')
            team2_tag = cols[3].find(['a', 'span'], class_='team-template-text')
            
            team1 = team1_tag.text.strip() if team1_tag else cols[1].text.strip()
            team2 = team2_tag.text.strip() if team2_tag else cols[3].text.strip()

            # Evento (índice 4)
            event_tag = cols[4].find('a')
            event_name = event_tag.text.strip() if event_tag else cols[4].text.strip()
            
            # URL da partida (link para o evento geralmente)
            match_url = f"https://liquipedia.net{event_tag['href']}" if event_tag and 'href' in event_tag.attrs else URL_LIQUIPEDIA
            
            # Verifica se é time brasileiro
            if not any(br.lower() in team1.lower() or br.lower() in team2.lower() for br in BRAZILIAN_TEAMS):
                # print(f"      ⚠️ Partida {row_idx}: Nenhum time BR ({team1} vs {team2})")
                continue

            # ----------------- Criação do Evento ICS -----------------
            # Converte para o fuso horário do Brasil para logs, mas usa UTC no ICS
            match_time_br = match_time_utc.astimezone(BR_TZ)

            e = Event()
            e.name = f"{team1} vs {team2} - {event_name}"
            # O ICS armazena em UTC (ideal para calendários)
            e.begin = match_time_utc.astimezone(pytz.utc) 
            e.end = e.begin + timedelta(hours=2) # Duração estimada
            e.description = f"Partida entre {team1} e {team2} no evento {event_name} (Horário de Brasília)"
            e.url = match_url

            cal.events.add(e)
            added_count += 1
            print(f"      ✅ Adicionado: {e.name} ({match_time_br.strftime('%d/%m %H:%M')}) | URL: {e.url}")

        except Exception as e:
            # Loga o erro específico para ajudar na depuração
            print(f"      ⚠️ Erro ao processar linha {row_idx} ({team1 or 'Time 1 Desconhecido'} vs {team2 or 'Time 2 Desconhecido'}): {e}")

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
