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
                   "RED Canids", "Legacy", "ODDIK", "Imperial Esports"]

# Lista de exclusões (nomes como aparecem no HTML, mas serão normalizados para comparação)
BRAZILIAN_TEAMS_EXCLUSIONS = [
    "Imperial.A", "Imperial Fe", "MIBR.A", "paiN.A", "ODDIK.A",
    "Imperial Academy", "Imperial.Acd", "Imperial Female",
    "Furia Academy", "Furia.A", "Pain Academy", "Mibr Academy", "Legacy Academy", "ODDIK Academy",
    "RED Canids Academy", "Fluxo Academy"
]

LIQUIPEDIA_URL = "https://liquipedia.net/counterstrike/Liquipedia:Matches"
CALENDAR_FILENAME = "calendar.ics"
BR_TZ = pytz.timezone('America/Sao_Paulo') # Fuso horário de Brasília

# -------------------- Funções Auxiliares --------------------
def normalize_team(name):
    """
    Normaliza o nome do time para comparação, convertendo para minúsculas e removendo espaços extras.
    Mantém caracteres especiais e espaços internos para comparações literais.
    """
    if not name:
        return ""
    return name.lower().strip()

# Pré-normaliza as listas de times para otimizar as comparações
NORMALIZED_BRAZILIAN_TEAMS = {normalize_team(team) for team in BRAZILIAN_TEAMS}
NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS = {normalize_team(team) for team in BRAZILIAN_TEAMS_EXCLUSIONS}

# -------------------- Lógica Principal --------------------
cal = Calendar()
added_count = 0

print(f"🔍 Buscando partidas em {LIQUIPEDIA_URL}...")

try:
    response = requests.get(LIQUIPEDIA_URL, timeout=10)
    response.raise_for_status() # Levanta um erro para códigos de status HTTP ruins (4xx ou 5xx)
    soup = BeautifulSoup(response.text, 'html.parser')

    match_blocks = soup.find_all('div', class_='match-info')
    print(f"✅ Encontrados {len(match_blocks)} blocos de partidas individuais com a classe 'match-info'.")

    for match_idx, match_block in enumerate(match_blocks, 1):
        team1_raw = "TBD"
        team2_raw = "TBD"
        event_name = "Desconhecido"
        match_url = LIQUIPEDIA_URL # Fallback para a URL principal
        match_format = "BoX"
        match_time_br = None # Inicializa para garantir que exista no escopo

        try:
            # Extrair timestamp e converter para BRT
            timer_object = match_block.find('span', class_='timer-object')
            if not timer_object or 'data-timestamp' not in timer_object.attrs:
                continue # Ignora blocos sem timestamp válido

            timestamp_utc = int(timer_object['data-timestamp'])
            match_time_utc = datetime.fromtimestamp(timestamp_utc, tz=pytz.utc)
            match_time_br = match_time_utc.astimezone(BR_TZ)

            # Extrair nomes dos times
            all_opponent_divs = match_block.find_all('div', class_='match-info-header-opponent')

            if len(all_opponent_divs) < 2:
                continue # Ignora se não houver dois oponentes claros

            team1_opponent_div = all_opponent_divs[0]
            team2_opponent_div = all_opponent_divs[1]

            team1_name_span = team1_opponent_div.find('span', class_='name')
            team2_name_span = team2_opponent_div.find('span', class_='name')

            if team1_name_span and team1_name_span.a:
                team1_raw = team1_name_span.a.get_text(strip=True)
            elif team1_name_span:
                team1_raw = team1_name_span.get_text(strip=True)

            if team2_name_span and team2_name_span.a:
                team2_raw = team2_name_span.a.get_text(strip=True)
            elif team2_name_span:
                team2_raw = team2_name_span.get_text(strip=True)

            # Ignorar partidas com TBD
            if team1_raw == "TBD" or team2_raw == "TBD":
                continue

            # Normaliza os nomes para a lógica de filtragem
            normalized_team1 = normalize_team(team1_raw)
            normalized_team2 = normalize_team(team2_raw)

            # Lógica de filtragem: verifica se algum time BR principal está envolvido E não é uma exclusão
            is_br_team1 = normalized_team1 in NORMALIZED_BRAZILIAN_TEAMS
            is_br_team2 = normalized_team2 in NORMALIZED_BRAZILIAN_TEAMS

            is_excluded_team1 = normalized_team1 in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS
            is_excluded_team2 = normalized_team2 in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS

            is_br_team_involved = (is_br_team1 and not is_excluded_team1) or \
                                  (is_br_team2 and not is_excluded_team2)

            if not is_br_team_involved:
                continue # Ignora se nenhum time BR principal (não excluído) estiver envolvido

            # Extrair nome do evento
            tournament_name_span = match_block.find('span', class_='match-info-tournament-name')
            if tournament_name_span and tournament_name_span.a and tournament_name_span.a.span:
                event_name = tournament_name_span.a.span.get_text(strip=True)
            elif tournament_name_span and tournament_name_span.a:
                event_name = tournament_name_span.a.get_text(strip=True)

            # Extrair URL do evento (se disponível)
            event_link_a = match_block.find('span', class_='match-info-tournament-name')
            if event_link_a and event_link_a.a and 'href' in event_link_a.a.attrs:
                match_url = "https://liquipedia.net" + event_link_a.a['href']

            # Extrair formato da partida (Bo1, Bo3, etc.)
            scoreholder_lower_span = match_block.find('span', class_='match-info-header-scoreholder-lower')
            if scoreholder_lower_span:
                match_format = scoreholder_lower_span.get_text(strip=True)

            # --- INÍCIO DAS MUDANÇAS SOLICITADAS ---
            # Novo formato para o nome do evento (summary)
            event_summary = f"{team1_raw} vs {team2_raw}"

            # Novo formato para a descrição do evento
            event_description = (
                f"🏆- {match_format}\n"
                f"📍{event_name}\n"
                f"🌐{match_url}"
            )
            # --- FIM DAS MUDANÇAS SOLICITADAS ---

            event_uid = hashlib.sha1(event_summary.encode('utf-8') + str(timestamp_utc).encode('utf-8')).hexdigest()

            e = Event()
            e.name = event_summary
            e.begin = match_time_utc
            e.duration = timedelta(hours=2) # Duração padrão de 2 horas
            e.description = event_description # Usando a nova descrição formatada
            e.uid = event_uid

            # Adiciona alarme 15 minutos antes
            alarm = DisplayAlarm(trigger=timedelta(minutes=-15))
            e.alarms.append(alarm)

            cal.events.add(e)
            added_count += 1

        except ValueError as ve:
            print(f"❌ Erro de dados no bloco {match_idx}: {ve}")
        except Exception as e_inner:
            print(f"❌ Erro inesperado ao processar bloco {match_idx}: {e_inner}")

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
