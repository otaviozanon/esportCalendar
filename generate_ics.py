import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
from ics import Calendar, Event
from ics.alarm import DisplayAlarm
import hashlib
import re

# -------------------- Configurações Globais --------------------
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo",
                   "RED Canids", "Legacy", "ODDIK"]

# Nomes de times a serem explicitamente excluídos (versões que podem aparecer no HTML)
BRAZILIAN_TEAMS_EXCLUSIONS = ["Imperial.A", "Imperial Fe", "MIBR.A", "paiN.A", "ODDIK.A", "Imperial Academy", "Imperial.Acd", "Imperial Female"]

URL_LIQUIPEDIA = "https://liquipedia.net/counterstrike/Liquipedia:Matches"
BR_TZ = pytz.timezone("America/Sao_Paulo")

cal = Calendar()
added_count = 0
unique_matches = set()

# --- Funções de Normalização e Extração ---
def normalize_team(name):
    """Normaliza o nome de um time para facilitar a comparação."""
    if not name:
        return ""
    name = name.lower().strip()
    # Remove termos comuns que não afetam a identificação do time principal
    name = name.replace("esports", "").replace("e-sports", "").replace("gaming", "").replace("team", "")
    # Padroniza variações de academias e times femininos
    name = name.replace("academy", "acd").replace(".a", ".acd")
    name = name.replace("women", "fe").replace("female", "fe")
    # Remove caracteres não alfanuméricos, mas mantém espaços para processamento inicial
    name = re.sub(r'[^a-z0-9\s]', '', name)
    # Remove todos os espaços para a comparação final
    name = re.sub(r'\s+', '', name)
    return name

def get_team_name_from_block(team_opponent_div):
    """Extrai o nome do time de um bloco de oponente, lidando com TBD e links."""
    if not team_opponent_div:
        return None

    name_span = team_opponent_div.find('span', class_='name')
    if name_span:
        name_link = name_span.find('a')
        # Verifica se é um link para uma página existente e não um 'redlink'
        if name_link and 'title' in name_link.attrs and 'page does not exist' not in name_link['title'].lower():
            return name_link.get_text(strip=True)
        # Se o texto do span é 'TBD' ou se o link é um 'redlink' (página não existe)
        elif name_span.get_text(strip=True).lower() == 'tbd' or (name_link and 'class' in name_link.attrs and 'new' in name_link['class']):
            return 'TBD'
        # Fallback para pegar o texto direto do span se não for link ou for link inválido
        elif name_span.get_text(strip=True):
            return name_span.get_text(strip=True)

    # Fallback para ícone de TBD se não houver span.name ou ele estiver vazio
    tbd_icon = team_opponent_div.find('i', class_='far fa-users')
    if tbd_icon:
        return 'TBD'

    return None # Retorna None se não encontrar nada

print(f"🔍 Buscando partidas em {URL_LIQUIPEDIA}...")

try:
    response = requests.get(URL_LIQUIPEDIA, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'lxml')

    match_blocks = soup.find_all('div', class_='match-info')

    print(f"✅ Encontrados {len(match_blocks)} blocos de partidas individuais com a classe 'match-info'.")

    if not match_blocks:
        print("⚠️ Nenhum bloco de partida encontrado. Verifique se a classe 'match-info' mudou ou se o conteúdo não está mais no HTML inicial.")
        exit()

    # Pré-normaliza as listas de times para comparação eficiente
    NORMALIZED_BRAZILIAN_TEAMS = [normalize_team(team) for team in BRAZILIAN_TEAMS]
    NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS = [normalize_team(team) for team in BRAZILIAN_TEAMS_EXCLUSIONS]

    for match_idx, match_block in enumerate(match_blocks, 1):
        team1_raw, team2_raw, event_name, match_url = 'N/A', 'N/A', 'N/A', URL_LIQUIPEDIA
        match_format = 'Partida'
        match_time_br = None # Inicializa match_time_br aqui

        try:
            # Extraindo o horário
            time_tag = match_block.find('span', class_='timer-object')
            if not time_tag or 'data-timestamp' not in time_tag.attrs:
                print(f"--- DEBUG: Bloco {match_idx} ignorado: Sem timestamp válido.")
                continue

            time_unix_timestamp = int(time_tag['data-timestamp'])
            match_time_utc = datetime.fromtimestamp(time_unix_timestamp, tz=pytz.utc)
            match_time_br = match_time_utc.astimezone(BR_TZ) # Define match_time_br aqui

            # Extrair os times corretamente (independente da ordem)
            all_opponent_divs = match_block.find_all('div', class_='match-info-header-opponent')

            if len(all_opponent_divs) < 2:
                print(f"--- DEBUG: Bloco {match_idx} ignorado: Não foram encontrados dois oponentes válidos.")
                continue

            team1_opponent_div = all_opponent_divs[0]
            team2_opponent_div = all_opponent_divs[1]

            team1_raw = get_team_name_from_block(team1_opponent_div)
            team2_raw = get_team_name_from_block(team2_opponent_div)

            if team1_raw is None or team2_raw is None:
                print(f"--- DEBUG: Bloco {match_idx} ignorado: Não foi possível extrair nomes de ambos os times.")
                continue

            if team1_raw == 'TBD' or team2_raw == 'TBD':
                print(f"--- DEBUG: Bloco {match_idx} ignorado: Um ou ambos os times são 'TBD'.")
                continue

            # Extraindo o formato da partida
            format_tag = match_block.find('span', class_='match-info-header-scoreholder-lower')
            if format_tag:
                match_format = format_tag.get_text(strip=True).replace('(', '').replace(')', '')

            # Extraindo o nome do evento e URL
            event_name_tag = match_block.find('span', class_='match-info-tournament-name')
            if event_name_tag and event_name_tag.find('span') and event_name_tag.find('span').get_text(strip=True):
                event_name = event_name_tag.find('span').get_text(strip=True)
                match_url = f"https://liquipedia.net{event_name_tag.find('a')['href']}" if event_name_tag.find('a') and 'href' in event_name_tag.find('a').attrs else URL_LIQUIPEDIA
            else:
                event_name = "Evento Desconhecido"
                match_url = URL_LIQUIPEDIA

            # --- Lógica de Filtragem Aprimorada (com debug) ---
            normalized_team1 = normalize_team(team1_raw)
            normalized_team2 = normalize_team(team2_raw)

            # DEBUG: Imprime os nomes normalizados para cada partida
            print(f"--- DEBUG: Processando bloco {match_idx}: Times '{team1_raw}' (norm: '{normalized_team1}') vs '{team2_raw}' (norm: '{normalized_team2}')")
            print(f"--- DEBUG: Normalized BR Teams: {NORMALIZED_BRAZILIAN_TEAMS}")
            print(f"--- DEBUG: Normalized Exclusions: {NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS}")


            is_br_team_involved = (normalized_team1 in NORMALIZED_BRAZILIAN_TEAMS) or \
                                  (normalized_team2 in NORMALIZED_BRAZILIAN_TEAMS)

            is_excluded_team_involved = (normalized_team1 in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS) or \
                                        (normalized_team2 in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS)

            if not is_br_team_involved:
                print(f"--- DEBUG: Bloco {match_idx} ignorado: Nenhum time BR envolvido.")
                continue

            if is_excluded_team_involved:
                print(f"--- DEBUG: Bloco {match_idx} ignorado: Time envolvido está na lista de exclusão.")
                continue

            # Criação do evento ICS
            format_map = {
                'Bo1': 'Best of 1 (Bo1)',
                'Bo2': 'Best of 2 (Bo2)',
                'Bo3': 'Best of 3 (Bo3)',
                'Bo5': 'Best of 5 (Bo5)',
                'Partida': 'Partida Simples'
            }
            full_match_format = format_map.get(match_format, match_format)

            e = Event()
            e.name = f"{team1_raw} vs {team2_raw}" # Usa os nomes raw para o nome do evento
            e.begin = match_time_utc.astimezone(pytz.utc)
            e.end = e.begin + timedelta(hours=2)
            e.description = (
                f"🎮 Format: {full_match_format}\n"
                f"📅 Event: {event_name}"
            )
            e.url = match_url

            alarm = DisplayAlarm(trigger=timedelta(minutes=0), display_text=f"{team1_raw} vs {team2_raw}")
            e.alarms.append(alarm)

            uid_base = f"{team1_raw}_{team2_raw}_{event_name}_{e.begin.isoformat()}".encode("utf-8")
            stable_uid = hashlib.md5(uid_base).hexdigest()[:8]
            e.uid = f"{stable_uid}@cs2calendar"

            sorted_teams = tuple(sorted([normalized_team1, normalized_team2]))
            match_key = (sorted_teams, e.begin.isoformat(), normalize_team(event_name))

            if match_key in unique_matches:
                print(f"--- DEBUG: Bloco {match_idx} ignorado: Partida '{e.name}' em '{event_name}' às '{e.begin.isoformat()}' já adicionada (duplicada).")
                continue

            unique_matches.add(match_key)
            cal.events.add(e)
            added_count += 1

            print(f"      ✅ Adicionado: {e.name} ({match_time_br.strftime('%d/%m %H:%M')}) | {full_match_format} | Evento: {event_name}")

        except Exception as e_inner:
            print(f"      ❌ Erro ao processar bloco {match_idx}: {e_inner} | Dados parciais: Team1='{team1_raw}', Team2='{team2_raw}', Evento='{event_name}'")

except requests.exceptions.RequestException as e:
    print(f"❌ Falha na requisição HTTP - {e}")
except Exception as e:
    print(f"❌ Erro inesperado - {e}")

try:
    with open("calendar.ics", "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())
    print(f"\n📌 {added_count} partidas BR salvas em calendar.ics (com alarmes no horário do jogo)")
except Exception as e:
    print(f"❌ Erro ao salvar calendar.ics: {e}")
