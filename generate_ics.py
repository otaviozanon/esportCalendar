import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
from ics import Calendar, Event
from ics.alarm import DisplayAlarm
import hashlib
import re # Importa o módulo de expressões regulares

# -------------------- Configurações Globais --------------------
# Nomes dos times brasileiros (versões principais, serão normalizadas)
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo",
                   "RED Canids", "Legacy", "ODDIK"] # Removido "Imperial Esports" daqui, pois "Imperial" já cobre.

# Nomes de times a serem explicitamente excluídos (versões que podem aparecer no HTML)
BRAZILIAN_TEAMS_EXCLUSIONS = ["Imperial.A", "Imperial Fe", "MIBR.A", "paiN.A", "ODDIK.A", "Imperial Academy", "Imperial.Acd"]

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
    name = name.replace("esports", "").replace("e-sports", "").replace("gaming", "").replace("team", "")
    name = name.replace("academy", "acd").replace(".a", ".acd") # Padroniza academias
    name = name.replace("women", "fe").replace("female", "fe") # Padroniza times femininos
    name = re.sub(r'[^a-z0-9]', '', name) # Remove caracteres não alfanuméricos
    return name

def get_team_name_from_block(team_opponent_div):
    """Extrai o nome do time de um bloco de oponente, lidando com TBD e links."""
    if not team_opponent_div:
        return None

    # Tenta encontrar o span com a classe 'name' primeiro
    name_span = team_opponent_div.find('span', class_='name')
    if name_span:
        # Verifica se é um link para uma página existente ou um 'new' link (TBD)
        name_link = name_span.find('a')
        if name_link and 'title' in name_link.attrs and 'page does not exist' not in name_link['title'].lower():
            return name_link.get_text(strip=True)
        elif name_span.get_text(strip=True).lower() == 'tbd':
            return 'TBD' # Retorna 'TBD' explicitamente
        elif name_span.get_text(strip=True):
            return name_span.get_text(strip=True) # Caso seja um span.name sem link, mas com texto

    # Caso não encontre span.name ou seja TBD, verifica se há um 'i' para TBD genérico
    tbd_icon = team_opponent_div.find('i', class_='far fa-users')
    if tbd_icon:
        return 'TBD'

    return None # Retorna None se não encontrar um nome válido

# Pré-normaliza as listas de times para comparações eficientes
NORMALIZED_BRAZILIAN_TEAMS = [normalize_team(team) for team in BRAZILIAN_TEAMS]
NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS = [normalize_team(team) for team in BRAZILIAN_TEAMS_EXCLUSIONS]

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

    for match_idx, match_block in enumerate(match_blocks, 1):
        team1_raw, team2_raw, event_name, match_url = 'N/A', 'N/A', 'N/A', URL_LIQUIPEDIA
        match_format = 'Partida'

        try:
            # --- Extração do Horário ---
            time_tag = match_block.find('span', class_='timer-object')
            if not time_tag or 'data-timestamp' not in time_tag.attrs:
                # print(f"      ❌ Erro: Bloco {match_idx} sem timestamp. Ignorando.")
                continue

            timestamp = int(time_tag['data-timestamp'])
            match_time_utc = datetime.fromtimestamp(timestamp, tz=pytz.utc)

            # --- Extração dos Nomes dos Times ---
            team1_opponent_div = match_block.find('div', class_='match-info-header-opponent-left')
            team2_opponent_div = match_block.find('div', class_='match-info-header-opponent', class_=lambda x: x != 'match-info-header-opponent-left') # Pega o segundo 'match-info-header-opponent'

            team1_raw = get_team_name_from_block(team1_opponent_div)
            team2_raw = get_team_name_from_block(team2_opponent_div)

            # Ignora partidas com TBD ou nomes de times inválidos
            if not team1_raw or not team2_raw or team1_raw == 'TBD' or team2_raw == 'TBD':
                # print(f"      ❌ Erro: Bloco {match_idx} com times TBD ou inválidos ('{team1_raw}' vs '{team2_raw}'). Ignorando.")
                continue

            # --- Extração do Formato da Partida ---
            format_tag = match_block.find('span', class_='match-info-header-scoreholder-lower')
            if format_tag:
                match_format = format_tag.get_text(strip=True).replace('(', '').replace(')', '')

            # --- Extração do Nome e URL do Evento ---
            event_tournament_div = match_block.find('div', class_='match-info-tournament')
            event_name_tag = event_tournament_div.find('span', class_='match-info-tournament-name') if event_tournament_div else None
            event_link = event_name_tag.find('a') if event_name_tag else None

            if event_link and event_link.text.strip():
                event_name = event_link.text.strip()
                match_url = f"https://liquipedia.net{event_link['href']}" if 'href' in event_link.attrs else URL_LIQUIPEDIA
            else:
                event_name = "Evento Desconhecido"
                match_url = URL_LIQUIPEDIA

            # --- Lógica de Filtragem de Times BR (AGORA MAIS ROBUSTA) ---
            normalized_team1 = normalize_team(team1_raw)
            normalized_team2 = normalize_team(team2_raw)

            # Verifica se algum dos times é brasileiro (usando nomes normalizados)
            is_br_team_involved = (normalized_team1 in NORMALIZED_BRAZILIAN_TEAMS) or \
                                  (normalized_team2 in NORMALIZED_BRAZILIAN_TEAMS)

            # Verifica se algum dos times está na lista de exclusão (usando nomes normalizados)
            is_excluded_team_involved = (normalized_team1 in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS) or \
                                        (normalized_team2 in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS)

            # Se não houver time BR envolvido OU se algum time for de exclusão, ignora
            if not is_br_team_involved or is_excluded_team_involved:
                continue

            # Se chegou aqui, a partida é válida e envolve um time BR principal
            team1 = team1_raw # Usa o nome original para o evento
            team2 = team2_raw # Usa o nome original para o evento

            match_time_br = match_time_utc.astimezone(BR_TZ)

            format_map = {
                'Bo1': 'Best of 1 (Bo1)',
                'Bo3': 'Best of 3 (Bo3)',
                'Bo5': 'Best of 5 (Bo5)',
                'Partida': 'Partida Simples'
            }
            full_match_format = format_map.get(match_format, match_format)

            e = Event()
            e.name = f"{team1} vs {team2}"
            e.begin = match_time_utc.astimezone(pytz.utc)
            e.end = e.begin + timedelta(hours=2) # Duração padrão de 2 horas
            e.description = (
                f"🎮 Format: {full_match_format}\n"
                f"📅 Event: {event_name}"
            )
            e.url = match_url

            alarm = DisplayAlarm(trigger=timedelta(minutes=0), display_text=f"{team1} vs {team2}")
            e.alarms.append(alarm)

            uid_base = f"{team1}_{team2}_{event_name}_{e.begin.isoformat()}".encode("utf-8")
            stable_uid = hashlib.md5(uid_base).hexdigest()[:8]
            e.uid = f"{stable_uid}@cs2calendar"

            sorted_teams = tuple(sorted([normalized_team1, normalized_team2])) # Usa nomes normalizados para a chave de unicidade
            match_key = (sorted_teams, e.begin.isoformat(), normalize_team(event_name))

            if match_key in unique_matches:
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

