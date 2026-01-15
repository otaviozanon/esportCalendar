import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
from ics import Calendar, Event
from ics.alarm import DisplayAlarm
import hashlib
import re

# -------------------- Configurações Globais --------------------
# Lista de times brasileiros principais (nomes como aparecem no HTML, mas serão normalizados para comparação)
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo",
                   "RED Canids", "Legacy", "ODDIK", "Imperial Esports"] # Adicionei "Imperial Esports" para garantir a captura

# Lista de exclusões (nomes como aparecem no HTML, mas serão normalizados para comparação)
BRAZILIAN_TEAMS_EXCLUSIONS = [
    "Imperial.A", "Imperial Fe", "MIBR.A", "paiN.A", "ODDIK.A",
    "Imperial Academy", "Imperial.Acd", "Imperial Female",
    "Furia Academy", "Furia.A", "Pain Academy", "Mibr Academy", "Legacy Academy", "ODDIK Academy",
    "RED Canids Academy", "Fluxo Academy"
]

URL_LIQUIPEDIA_MATCHES = "https://liquipedia.net/counterstrike/Liquipedia:Matches"
BR_TZ = pytz.timezone('America/Sao_Paulo') # Fuso horário de Brasília
CALENDAR_FILENAME = "calendar.ics"

# -------------------- Funções Auxiliares --------------------

def normalize_team(name):
    """
    Normaliza o nome do time para comparação, convertendo para minúsculas e removendo espaços extras.
    Mantém caracteres especiais e espaços internos para comparações literais.
    """
    if not name:
        return ""
    return name.lower().strip()

# Pré-normaliza as listas de times para comparações eficientes
NORMALIZED_BRAZILIAN_TEAMS = {normalize_team(team) for team in BRAZILIAN_TEAMS}
NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS = {normalize_team(team) for team in BRAZILIAN_TEAMS_EXCLUSIONS}

print(f"--- DEBUG: Normalized BR Teams (set): {NORMALIZED_BRAZILIAN_TEAMS}")
print(f"--- DEBUG: Normalized Exclusions (set): {NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS}")

def get_match_data(match_block):
    """Extrai dados de uma partida de um bloco HTML."""
    match_time_element = match_block.find('span', class_='timer-object')
    if not match_time_element:
        raise ValueError("Elemento de tempo da partida não encontrado.")

    timestamp_str = match_time_element.get('data-timestamp')
    if not timestamp_str:
        raise ValueError("Timestamp da partida não encontrado.")

    match_time_utc = datetime.fromtimestamp(int(timestamp_str), tz=pytz.utc)
    match_time_br = match_time_utc.astimezone(BR_TZ)

    # Extrai nomes dos times
    all_opponent_divs = match_block.find_all('div', class_='match-info-header-opponent')

    if len(all_opponent_divs) < 2:
        raise ValueError("Não foi possível encontrar dois oponentes para a partida.")

    team1_opponent_div = all_opponent_divs[0]
    team2_opponent_div = all_opponent_divs[1]

    team1_element = team1_opponent_div.find('span', class_='name')
    team2_element = team2_opponent_div.find('span', class_='name')

    team1_raw = team1_element.get_text(strip=True) if team1_element else "TBD"
    team2_raw = team2_element.get_text(strip=True) if team2_element else "TBD"

    # Extrai nome do evento
    event_name_element = match_block.find('span', class_='match-info-tournament-name')
    event_name = event_name_element.get_text(strip=True) if event_name_element else "Evento Desconhecido"

    # Extrai formato da partida (Bo1, Bo3, etc.)
    match_format_element = match_block.find('span', class_='match-info-header-scoreholder-lower')
    match_format = match_format_element.get_text(strip=True) if match_format_element else "Formato Desconhecido"

    # Extrai URL da partida
    match_url_element = match_block.find('div', class_='match-info-links')
    match_url = ""
    if match_url_element:
        # Tenta encontrar o primeiro link que não seja de stream
        link = match_url_element.find('a', href=True, string=lambda text: text and "VOD" not in text and "Stream" not in text)
        if link:
            match_url = "https://liquipedia.net" + link['href']
        else:
            # Se não encontrar um link específico, pega o primeiro link disponível
            first_link = match_url_element.find('a', href=True)
            if first_link:
                match_url = "https://liquipedia.net" + first_link['href']

    return team1_raw, team2_raw, event_name, match_format, match_time_utc, match_time_br, match_url

# -------------------- Lógica Principal --------------------
cal = Calendar()
added_count = 0

print(f"🔍 Buscando partidas em {URL_LIQUIPEDIA_MATCHES}...")

try:
    response = requests.get(URL_LIQUIPEDIA_MATCHES)
    response.raise_for_status() # Levanta um erro para códigos de status HTTP ruins (4xx ou 5xx)

    soup = BeautifulSoup(response.text, 'html.parser')

    match_blocks = soup.find_all('div', class_='match-info')
    print(f"✅ Encontrados {len(match_blocks)} blocos de partidas individuais com a classe 'match-info'.")

    for match_idx, match_block in enumerate(match_blocks, 1):
        team1_raw, team2_raw, event_name, match_format, match_time_utc, match_time_br, match_url = [None] * 7 # Inicializa para evitar NameError
        try:
            team1_raw, team2_raw, event_name, match_format, match_time_utc, match_time_br, match_url = get_match_data(match_block)

            # Normaliza os nomes dos times para comparação
            normalized_team1 = normalize_team(team1_raw)
            normalized_team2 = normalize_team(team2_raw)

            # Ignora partidas com "TBD" (To Be Determined)
            if normalized_team1 == "tbd" or normalized_team2 == "tbd":
                print(f"--- DEBUG: Bloco {match_idx} ignorado: Um ou ambos os times são 'TBD'.")
                continue

            # Verifica se algum dos times é brasileiro (principal)
            is_br_team1 = normalized_team1 in NORMALIZED_BRAZILIAN_TEAMS
            is_br_team2 = normalized_team2 in NORMALIZED_BRAZILIAN_TEAMS
            is_br_team_involved = is_br_team1 or is_br_team2

            # Verifica se algum dos times é uma exclusão (academia/feminino)
            is_excluded_team1 = normalized_team1 in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS
            is_excluded_team2 = normalized_team2 in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS
            is_excluded_team_involved = is_excluded_team1 or is_excluded_team2

            print(f"--- DEBUG: Processando bloco {match_idx}: Times '{team1_raw}' (norm: '{normalized_team1}') vs '{team2_raw}' (norm: '{normalized_team2}')")
            print(f"      is_br_team1: {is_br_team1}, is_br_team2: {is_br_team2}")
            print(f"      is_excluded_team1: {is_excluded_team1}, is_excluded_team2: {is_excluded_team2}")

            # Lógica de filtragem:
            # Inclui se houver um time BR principal E NENHUM time envolvido for uma exclusão.
            # Isso significa que "Imperial" vs "Sharks" entra.
            # "Imperial.A" vs "Outro" não entra.
            # "Imperial" vs "Imperial.A" não entra (pois Imperial.A é exclusão).
            if not is_br_team_involved:
                print(f"--- DEBUG: Bloco {match_idx} ignorado: Nenhum time BR principal envolvido.")
                continue

            if is_excluded_team_involved:
                print(f"--- DEBUG: Bloco {match_idx} ignorado: Um ou ambos os times são times de exclusão (academia/feminino).")
                continue

            # Se chegou até aqui, a partida é válida para ser adicionada
            event_uid = hashlib.sha1(f"{team1_raw}{team2_raw}{match_time_utc}".encode()).hexdigest()

            e = Event()
            e.name = f"{team1_raw} vs {team2_raw} | {match_format}"
            e.begin = match_time_utc
            e.duration = timedelta(hours=2) # Duração padrão de 2 horas
            e.description = f"Evento: {event_name}\nLink: {match_url}"
            e.uid = event_uid

            # Adiciona alarme 15 minutos antes
            alarm = DisplayAlarm(trigger=timedelta(minutes=-15))
            e.alarms.append(alarm)

            cal.events.add(e)
            added_count += 1
            print(f"      ✅ Adicionado: {team1_raw} vs {team2_raw} ({match_time_br.strftime('%d/%m %H:%M')}) | {match_format} | Evento: {event_name}")

        except ValueError as ve:
            print(f"      ❌ Erro de dados no bloco {match_idx}: {ve}")
        except Exception as e_inner:
            print(f"      ❌ Erro ao processar bloco {match_idx}: {e_inner} | Dados parciais: Team1='{team1_raw}', Team2='{team2_raw}', Evento='{event_name}'")

except requests.exceptions.RequestException as e:
    print(f"❌ Falha na requisição HTTP - {e}")
except Exception as e:
    print(f"❌ Erro inesperado - {e}")

try:
    with open(CALENDAR_FILENAME, "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())
    print(f"\n📌 {added_count} partidas BR salvas em {CALENDAR_FILENAME} (com alarmes no horário do jogo)")
except Exception as e:
    print(f"❌ Erro ao salvar {CALENDAR_FILENAME}: {e}")
