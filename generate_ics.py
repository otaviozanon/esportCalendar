import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
from ics import Calendar, Event

# -------------------- Configurações --------------------
URL_LIQUIPEDIA = "https://liquipedia.net/counterstrike/Liquipedia:Matches"
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo",
                   "Sharks", "RED Canids", "Legacy", "ODDIK"]
BR_TZ = pytz.timezone("America/Sao_Paulo")
cal = Calendar()
added_count = 0

# -------------------- Coleta de partidas (Liquipedia) --------------------
print(f"🔍 Buscando partidas em {URL_LIQUIPEDIA}...")

try:
    # 1. Requisição HTTP
    response = requests.get(URL_LIQUIPEDIA)
    response.raise_for_status() # Lança exceção para status codes de erro (4xx ou 5xx)

    # 2. Parsing do HTML
    soup = BeautifulSoup(response.text, 'lxml')
    
    # A Liquipedia usa classes como 'wikitable' para tabelas de partidas
    # Procure pela tabela principal de "Upcoming Matches"
    match_table = soup.find('table', class_='wikitable')
    
    if not match_table:
        print("⚠️ Tabela de partidas não encontrada. Verifique a estrutura da página.")
        exit()

    # 3. Iterar pelas linhas (TRs) da tabela, pulando o cabeçalho
    # O seletor 'tr[data-url]' pode ajudar a focar nas linhas de partidas
    rows = match_table.find_all('tr', recursive=False)[1:] # [1:] para pular o cabeçalho
    print(f"📦 {len(rows)} linhas de partidas encontradas")

    for row_idx, row in enumerate(rows, 1):
        try:
            # Colunas da tabela: Data (0), Time 1 (1), vs (2), Time 2 (3), Evento (4), Stream (5)
            cols = row.find_all('td', recursive=False)
            
            if len(cols) < 5: # Garante que temos as colunas básicas
                continue

            # Data/Hora: A primeira coluna (index 0) tem o timestamp em UTC
            # O link dentro do <td> (seletor 'span.timer-object') contém o timestamp UTC
            time_tag = cols[0].find('span', class_='timer-object')
            
            if not time_tag or 'data-timestamp' not in time_tag.attrs:
                 # Pode ser um placeholder como 'TBD', 'Aguardando Data', etc.
                continue

            # O formato do timestamp é ISO 8601 (YYYY-MM-DDTHH:MM:SSZ)
            time_utc_str = time_tag['data-timestamp']
            
            # Converte para objeto datetime, garantindo que seja UTC
            match_time_utc = datetime.fromisoformat(time_utc_str.replace('Z', '+00:00'))
            
            # Time 1 e Time 2 (index 1 e 3)
            # Os nomes dos times estão em links (<a>)
            team1_tag = cols[1].find('a')
            team2_tag = cols[3].find('a')
            
            # Se não encontrar o link (<a>), tenta pegar o texto direto
            team1 = team1_tag.text.strip() if team1_tag else cols[1].text.strip()
            team2 = team2_tag.text.strip() if team2_tag else cols[3].text.strip()

            # Evento (index 4)
            event_name_tag = cols[4].find('a')
            event_name = event_name_tag.text.strip() if event_name_tag else cols[4].text.strip()
            
            # URL da partida (link para o evento geralmente)
            # Usando a URL do evento como referência
            match_url = f"https://liquipedia.net{event_name_tag['href']}" if event_name_tag and 'href' in event_name_tag.attrs else URL_LIQUIPEDIA
            
            # Verifica se é time brasileiro
            if not any(br.lower() in team1.lower() or br.lower() in team2.lower() for br in BRAZILIAN_TEAMS):
                # print(f"      ⚠️ Partida {row_idx}: Nenhum time BR ({team1} vs {team2})")
                continue

            # Converte para o fuso horário do Brasil para exibição no calendário, 
            # mantendo a referência UTC no ICS (o que é o ideal).
            match_time_br = match_time_utc.astimezone(BR_TZ)

            # Criar evento ICS
            e = Event()
            e.name = f"{team1} vs {team2} - {event_name}"
            # O ICS armazena em UTC, mesmo que o objeto datetime esteja localizado
            e.begin = match_time_utc.astimezone(pytz.utc) 
            e.end = e.begin + timedelta(hours=2) # Duração estimada de 2h
            e.description = f"Partida entre {team1} e {team2} no evento {event_name}"
            e.url = match_url

            cal.events.add(e)
            added_count += 1
            print(f"      ✅ Adicionado: {e.name} ({match_time_br.strftime('%d/%m %H:%M')}) | URL: {e.url}")

        except Exception as e:
            print(f"      ⚠️ Erro ao processar linha {row_idx}: {e}")

except requests.exceptions.RequestException as e:
    print(f"❌ Erro ao acessar {URL_LIQUIPEDIA}: {e}")
except Exception as e:
    print(f"❌ Erro inesperado: {e}")

# -------------------- Finalizar --------------------
# Salvar calendar.ics
try:
    with open("calendar.ics", "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())
    print(f"\n📌 {added_count} partidas BR salvas em calendar.ics")
except Exception as e:
    print(f"❌ Erro ao salvar calendar.ics: {e}")
