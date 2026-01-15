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
# Adicionei mais variações para garantir a exclusão
BRAZILIAN_TEAMS_EXCLUSIONS = [
    "Imperial.A", "Imperial Fe", "MIBR.A", "paiN.A", "ODDIK.A",
    "Imperial Academy", "Imperial.Acd", "Imperial Female",
    "Furia Academy", "Furia.A", "Pain Academy", "Mibr Academy", "Legacy Academy", "ODDIK Academy",
    "RED Canids Academy", "Fluxo Academy"
]

URL_LIQUIPEDIA = "https://liquipedia.net/counterstrike/Liquipedia:Matches"
BR_TZ = pytz.timezone("America/Sao_Paulo")

cal = Calendar()
added_count = 0
unique_matches = set()

# --- Funções de Normalização e Extração ---
def normalize_team(name):
    """
    Normaliza o nome de um time para facilitar a comparação,
    mantendo a distinção entre time principal e academias/femininos.
    """
    if not name:
        return ""

    original_name = name.lower().strip()
    normalized_name = original_name

    # Primeiro, verifica e padroniza termos de exclusão específicos
    if "academy" in normalized_name:
        normalized_name = normalized_name.replace("academy", "acd")
    if ".a" in normalized_name:
        normalized_name = normalized_name.replace(".a", ".acd")
    if "female" in normalized_name:
        normalized_name = normalized_name.replace("female", "fe")
    if "fe" in normalized_name and "female" not in original_name: # Evita "fe" de "fenix" virar "fenixfe"
        normalized_name = normalized_name.replace("fe", "fe") # Mantém "fe" se já estiver lá

    # Remove termos comuns que não afetam a identificação do time principal
    # Faça isso APÓS a verificação de academy/female para não remover "esports" de "Imperial Esports" antes de decidir se é principal
    normalized_name = normalized_name.replace("esports", "").replace("e-sports", "").replace("gaming", "").replace("team", "")

    # Remove caracteres não alfanuméricos e espaços para a comparação final
    normalized_name = re.sub(r'[^a-z0-9]', '', normalized_name)

    return normalized_name

def get_team_name_from_block(team_div):
    """Extrai o nome do time de um bloco de oponente, lidando com TBD e links."""
    if not team_div:
        return "N/A" # Caso o div do time não seja encontrado

    # Primeiro, tenta pegar o texto do link 'a' dentro do span com class 'name'
    name_span = team_div.find('span', class_='name')
    if name_span:
        link_tag = name_span.find('a')
        if link_tag and link_tag.text.strip():
            return link_tag.text.strip()
        elif name_span.text.strip(): # Se não tem link, pega o texto direto do span (ex: TBD)
            return name_span.text.strip()

    # Fallback para o ícone de TBD, se o nome não for encontrado
    if team_div.find('i', class_='fa-users'):
        return "TBD"

    return "N/A" # Se nada for encontrado

# Pré-normaliza as listas de times para comparação eficiente
NORMALIZED_BRAZILIAN_TEAMS = {normalize_team(team) for team in BRAZILIAN_TEAMS}
NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS = {normalize_team(team) for team in BRAZILIAN_TEAMS_EXCLUSIONS}

print(f"🔍 Buscando partidas em {URL_LIQUIPEDIA}...")
print(f"--- DEBUG: Normalized BR Teams (set): {NORMALIZED_BRAZILIAN_TEAMS}")
print(f"--- DEBUG: Normalized Exclusions (set): {NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS}")

try:
    response = requests.get(URL_LIQUIPEDIA, timeout=10)
    response.raise_for_status() # Isso vai levantar um erro para status 4xx/5xx
    soup = BeautifulSoup(response.text, 'lxml')

    match_blocks = soup.find_all('div', class_='match-info')
    print(f"✅ Encontrados {len(match_blocks)} blocos de partidas individuais com a classe 'match-info'.")

    for match_idx, match_block in enumerate(match_blocks, 1):
        match_time_br = None # Inicializa para garantir que sempre exista

        try:
            # Extrair timestamp
            timer_object = match_block.find('span', class_='timer-object')
            if not timer_object or 'data-timestamp' not in timer_object.attrs:
                print(f"--- DEBUG: Bloco {match_idx} ignorado: Não foi possível encontrar o timestamp.")
                continue

            timestamp_utc = int(timer_object['data-timestamp'])
            match_time_utc = datetime.fromtimestamp(timestamp_utc, tz=pytz.utc)
            match_time_br = match_time_utc.astimezone(BR_TZ)

            # Extrair os times corretamente, lidando com casos bugados
            all_opponent_divs = match_block.find_all('div', class_='match-info-header-opponent')

            if len(all_opponent_divs) < 2:
                print(f"--- DEBUG: Bloco {match_idx} ignorado: Não foram encontrados dois oponentes claros.")
                continue 

            team1_opponent_div = all_opponent_divs[0]
            team2_opponent_div = all_opponent_divs[1]

            team1_raw = get_team_name_from_block(team1_opponent_div)
            team2_raw = get_team_name_from_block(team2_opponent_div)

            # Ignorar partidas com TBD
            if team1_raw == "TBD" or team2_raw == "TBD":
                print(f"--- DEBUG: Bloco {match_idx} ignorado: Um ou ambos os times são 'TBD'.")
                continue

            # Normaliza os nomes para a lógica de filtragem
            normalized_team1 = normalize_team(team1_raw)
            normalized_team2 = normalize_team(team2_raw)

            print(f"--- DEBUG: Processando bloco {match_idx}: Times '{team1_raw}' (norm: '{normalized_team1}') vs '{team2_raw}' (norm: '{normalized_team2}')")

            # Lógica de filtragem: pelo menos um time BR e nenhum time excluído
            is_br_team_involved = (normalized_team1 in NORMALIZED_BRAZILIAN_TEAMS) or \
                                  (normalized_team2 in NORMALIZED_BRAZILIAN_TEAMS)

            is_excluded_team_involved = (normalized_team1 in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS) or \
                                        (normalized_team2 in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS)

            if not is_br_team_involved:
                print(f"--- DEBUG: Bloco {match_idx} ignorado: Nenhum time BR envolvido.")
                continue

            if is_excluded_team_involved:
                print(f"--- DEBUG: Bloco {match_idx} ignorado: Time '{team1_raw}' ou '{team2_raw}' está na lista de exclusão.")
                continue

            # Extrair formato da partida
            match_format_span = match_block.find('span', class_='match-info-header-scoreholder-lower')
            full_match_format = match_format_span.get_text(strip=True).replace('(', '').replace(')', '') if match_format_span else "N/A"

            # Extrair nome do evento e URL
            event_name_span = match_block.find('span', class_='match-info-tournament-name')
            event_name = event_name_span.find('span').get_text(strip=True) if event_name_span and event_name_span.find('span') else "N/A"
            event_url_tag = event_name_span.find('a') if event_name_span else None
            event_url = "https://liquipedia.net" + event_url_tag['href'] if event_url_tag and 'href' in event_url_tag.attrs else URL_LIQUIPEDIA

            # Criar evento ICS
            e = Event()
            e.name = f"{team1_raw} vs {team2_raw}"
            e.begin = match_time_utc
            e.duration = timedelta(hours=2) # Duração padrão de 2 horas
            e.description = f"Formato: {full_match_format}\nEvento: {event_name}\nLink: {event_url}"

            # Adicionar alarme para o início do jogo
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
