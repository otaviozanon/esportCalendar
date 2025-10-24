import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
from ics import Calendar, Event

# -------------------- Configurações Globais --------------------
# Lista de times brasileiros cujas partidas serão incluídas no calendário.
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo",
                   "RED Canids", "Legacy", "ODDIK"]

# Lista de exclusão para sub-equipes
BRAZILIAN_TEAMS_EXCLUSIONS = ["Imperial.A", "Imperial Fe", "MIBR.A", "MIBR Fe"] 

URL_LIQUIPEDIA = "https://liquipedia.net/counterstrike/Liquipedia:Matches"
BR_TZ = pytz.timezone("America/Sao_Paulo") # Fuso horário de Brasília
cal = Calendar()
added_count = 0

print(f"🔍 Buscando partidas em {URL_LIQUIPEDIA}...")

# -------------------- Coleta de partidas (Liquipedia) --------------------
try:
    # 1. Realiza a requisição HTTP para a página de partidas da Liquipedia.
    response = requests.get(URL_LIQUIPEDIA, timeout=10)
    response.raise_for_status() # Lança exceção para erros HTTP (4xx ou 5xx)

    # 2. Faz o parsing do conteúdo HTML usando BeautifulSoup.
    soup = BeautifulSoup(response.text, 'lxml')
    
    # ------------------------------------------------------------------
    # --- Identifica os blocos de partidas na página ---
    # Foca em todas as tabelas de partidas futuras (usando a classe CSS específica).
    MATCH_TABLE_CLASS = 'wikitable wikitable-striped infobox_matches_content'
    match_tables = soup.find_all('table', class_=MATCH_TABLE_CLASS)
    
    print(f"✅ Encontrados {len(match_tables)} blocos de partidas individuais com a classe '{MATCH_TABLE_CLASS}'.")

    if not match_tables:
        print("⚠️ Nenhum bloco de partida encontrado. Verifique se a classe da tabela mudou.")
        exit()
    # ------------------------------------------------------------------


    # 3. Itera sobre cada tabela de partida encontrada.
    for match_idx, match_table in enumerate(match_tables, 1):
        team1, team2, event_name, match_url = 'N/A', 'N/A', 'N/A', URL_LIQUIPEDIA
        match_format = 'Partida' # Variável para o formato (Bo1, Bo3, etc.)
        
        try:
            # Uma tabela de partida geralmente tem 2 linhas (TRs) com informações: 
            # TR[0]: Nomes dos times e formato (vs)
            # TR[1]: Data, Evento e Streams
            rows = match_table.find_all('tr') 
            
            if len(rows) < 2:
                # Ignora tabelas incompletas.
                continue

            # --- Extração da TR[0] (Times e Formato) ---
            # As colunas da TR[0] são: [0] Time 1, [1] vs (formato), [2] Time 2
            team_cols = rows[0].find_all('td', recursive=False)
            
            # Times: Extrai o nome do time usando a classe 'team-template-text' ou o texto da coluna.
            team1_tag = team_cols[0].find('span', class_='team-template-text')
            team2_tag = team_cols[2].find('span', class_='team-template-text')
            
            team1 = team1_tag.text.strip() if team1_tag else team_cols[0].text.strip()
            team2 = team2_tag.text.strip() if team2_tag else team_cols[2].text.strip()

            # Formato (BoX)
            if len(team_cols) > 1:
                versus_col = team_cols[1]
                # Busca pela tag <abbr> (que contém o formato Bo1/Bo3) dentro da coluna 'versus'.
                format_abbr = versus_col.find('abbr')
                if format_abbr and format_abbr.text:
                    match_format = format_abbr.text.strip()
            
            # --- Extração da TR[1] (Data/Evento) ---
            # Encontra a tag que contém o timestamp UNIX (data-timestamp).
            time_tag = rows[1].find('span', class_='timer-object')
            
            # 1. Data/Hora
            if not time_tag or 'data-timestamp' not in time_tag.attrs:
                # Ignora a partida se não houver um timestamp válido (TBD/adiamento).
                continue

            try:
                # Converte o timestamp UNIX (em segundos) para um objeto datetime UTC.
                time_unix_timestamp = int(time_tag['data-timestamp'])
                match_time_utc = datetime.fromtimestamp(time_unix_timestamp, tz=pytz.utc)
            except ValueError:
                print(f"      ❌ Partida {match_idx} ({team1} vs {team2}): Falha ao converter timestamp para inteiro. Pulando.")
                continue
            
            # 2. Evento (Busca o link de texto do evento dentro da classe 'text-nowrap')
            event_name_tag = rows[1].find('div', class_='text-nowrap')
            event_link = event_name_tag.find('a') if event_name_tag else None

            if event_link and event_link.text.strip():
                event_name = event_link.text.strip()
                # Constrói a URL completa para a página do evento.
                match_url = f"https://liquipedia.net{event_link['href']}" if 'href' in event_link.attrs else URL_LIQUIPEDIA
            else:
                event_name = "Evento Desconhecido"
                match_url = URL_LIQUIPEDIA
            
            # 3. Lógica de Filtragem (INCLUSÃO e EXCLUSÃO)
            
            # Checa se o Time 1 OU o Time 2 corresponde a algum time da lista de inclusão BR.
            is_team_br = any(br.lower() in team1.lower() or br.lower() in team2.lower() for br in BRAZILIAN_TEAMS)

            # Checa se o Time 1 OU o Time 2 corresponde a algum time da lista de exclusão (sub-equipes).
            is_excluded = any(ex.lower() in team1.lower() or ex.lower() in team2.lower() for ex in BRAZILIAN_TEAMS_EXCLUSIONS)

            # A partida só é adicionada se for um time BR E não for um time da lista de exclusão.
            if not is_team_br or is_excluded:
                # Partida ignorada devido à exclusão ou falta de time BR.
                continue

            # ----------------- Criação do Evento ICS -----------------
            # Converte o horário para o fuso horário de São Paulo (BR_TZ) para exibição no log.
            match_time_br = match_time_utc.astimezone(BR_TZ)
            
            # Mapeamento do formato (BoX) para descrição completa.
            format_map = {
                'Bo1': 'Best of 1 (Bo1)',
                'Bo3': 'Best of 3 (Bo3)',
                'Bo5': 'Best of 5 (Bo5)',
                'Partida': 'Partida Simples' # Retorno padrão
            }
            full_match_format = format_map.get(match_format, match_format)

            e = Event()
            # SUMMARY (Título do Evento): Nome dos times no formato Time A vs Time B
            e.name = f"{team1} vs {team2}" 
            # BEGIN e END devem ser definidos em UTC para compatibilidade com o padrão ICS.
            e.begin = match_time_utc.astimezone(pytz.utc) 
            e.end = e.begin + timedelta(hours=2) # Duração padrão de 2 horas
            
            # DESCRIPTION: Conteúdo detalhado no corpo do evento do calendário.
            e.description = (
                f"🎮 Format: {full_match_format}\n"
                f"📅 Event: {event_name}"
            )
            e.url = match_url # Link para a página da partida/evento
            
            cal.events.add(e)
            added_count += 1
            print(f"      ✅ Adicionado: {e.name} ({match_time_br.strftime('%d/%m %H:%M')}) | Formato: {full_match_format} | Evento: {event_name}")

        except Exception as e:
            # Captura exceções específicas ao processar uma única partida e continua com as demais.
            print(f"      ❌ Erro ao processar bloco de partida {match_idx} ({team1} vs {team2}): {e}")

except requests.exceptions.RequestException as e:
    # Tratamento de erro para falhas na requisição HTTP (ex: sem internet).
    print(f"❌ Erro ao acessar {URL_LIQUIPEDIA}: Falha na requisição HTTP - {e}")
except Exception as e:
    # Tratamento de erro para exceções inesperadas.
    print(f"❌ Erro inesperado durante o scraping: {e}")

# -------------------- Finalizar e Salvar --------------------
# Salva o calendário gerado no formato .ics
try:
    with open("calendar.ics", "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())
    print(f"\n📌 {added_count} partidas BR salvas em calendar.ics")
except Exception as e:
    print(f"❌ Erro ao salvar calendar.ics: {e}")
