import requests
import json
from datetime import datetime, timedelta
import pytz
from ics import Calendar, Event
from ics.alarm import DisplayAlarm
import hashlib
# import os # Não é mais necessário para o controle de requisições

# -------------------- Configurações Globais --------------------
BRAZILIAN_TEAMS = ["FURIA", "paiN Gaming", "MIBR", "Imperial Esports", "Fluxo",
                   "RED Canids", "Legacy", "ODDIK", "INTZ", "Paquetá", "ARCTIC", "O PLANO"]

BRAZILIAN_TEAMS_EXCLUSIONS = [
    "Imperial Academy", "Imperial Female", "MIBR Academy", "paiN Academy", "ODDIK Academy",
    "Furia Academy", "Furia.A", "Pain Academy", "Mibr Academy", "Legacy Academy", "ODDIK Academy",
    "RED Canids Academy", "Fluxo Academy", "Spirit Academy"
]

CALENDAR_FILENAME = "calendar.ics"
BR_TZ = pytz.timezone('America/Sao_Paulo')

RAPIDAPI_HOST = "csgo-matches-and-tournaments.p.rapidapi.com"
RAPIDAPI_KEY = "11309a30bemsh349cbd9a170c61ep159a03jsnbd9e27efbe00"
RAPIDAPI_URL = f"https://{RAPIDAPI_HOST}/matches"

# As variáveis REQUEST_COUNT_FILE e MAX_DAILY_REQUESTS foram removidas daqui.

# -------------------- Funções Auxiliares --------------------
def normalize_team(name):
    if not name:
        return ""
    return name.lower().strip()

NORMALIZED_BRAZILIAN_TEAMS = {normalize_team(team) for team in BRAZILIAN_TEAMS}
NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS = {normalize_team(team) for team in BRAZILIAN_TEAMS_EXCLUSIONS}

# As funções get_request_count() e save_request_count() foram removidas daqui.

# -------------------- Lógica Principal --------------------
cal = Calendar()
added_count = 0

# A verificação de limite de requisições foi removida daqui.
headers = {
    'x-rapidapi-key': RAPIDAPI_KEY,
    'x-rapidapi-host': RAPIDAPI_HOST,
    'Content-Type': "application/json"
}

try:
    response = requests.get(RAPIDAPI_URL, headers=headers, timeout=10)
    response.raise_for_status()
    full_response_data = response.json()

    matches_data = full_response_data.get('data', [])

    if not matches_data:
        # print("ℹ️ Nenhuma partida encontrada na resposta da API.")
        pass

    now_utc = datetime.now(pytz.utc) # Definido uma vez para todas as comparações

    for match_idx, match in enumerate(matches_data, 1):
        team1_raw = "TBD"
        team2_raw = "TBD"
        event_name = "Desconhecido"
        match_url = RAPIDAPI_URL
        match_format = "BoX"
        match_time_utc = None

        try:
            played_at_str = match.get('played_at')
            if not played_at_str:
                continue

            match_time_utc = datetime.strptime(played_at_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=pytz.utc)

            # Filtrar apenas "upcoming matches"
            if match_time_utc < now_utc - timedelta(minutes=5):
                continue

            team_won_info = match.get('team_won', {})
            team_lose_info = match.get('team_lose', {})

            team1_raw = team_won_info.get('title', 'TBD')
            team2_raw = team_lose_info.get('title', 'TBD')

            if team1_raw == "TBD" and team2_raw == "TBD":
                continue
            elif team1_raw == "TBD":
                team1_raw = team_lose_info.get('title', 'TBD')
                team2_raw = "TBD"
            elif team2_raw == "TBD":
                team2_raw = team_won_info.get('title', 'TBD')
                team1_raw = "TBD"

            if team1_raw == "TBD" or team2_raw == "TBD":
                continue

            normalized_team1 = normalize_team(team1_raw)
            normalized_team2 = normalize_team(team2_raw)

            is_br_team1 = normalized_team1 in NORMALIZED_BRAZILIAN_TEAMS
            is_br_team2 = normalized_team2 in NORMALIZED_BRAZILIAN_TEAMS

            is_excluded_team1 = normalized_team1 in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS
            is_excluded_team2 = normalized_team2 in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS

            is_br_team_involved = (is_br_team1 and not is_excluded_team1) or \
                                  (is_br_team2 and not is_excluded_team2)

            if not is_br_team_involved:
                continue

            event_info = match.get('event', {})
            event_name = event_info.get('title', 'Desconhecido')

            match_url = RAPIDAPI_URL

            match_kind_info = match.get('match_kind', {})
            match_format = match_kind_info.get('title', 'BoX').upper()

            event_summary = f"{team1_raw} vs {team2_raw}"
            event_description = (
                f"🏆- {match_format}\n"
                f"📍{event_name}\n"
                f"🌐{match_url}"
            )

            event_uid = hashlib.sha1(
                (event_summary + played_at_str).encode('utf-8')
            ).hexdigest()

            e = Event()
            e.name = event_summary
            e.begin = match_time_utc
            e.duration = timedelta(hours=2)
            e.description = event_description
            e.uid = event_uid
            e.alarms.append(DisplayAlarm(trigger=timedelta(minutes=-15)))
            cal.events.add(e)
            added_count += 1

        except Exception as e_inner:
            # print(f"❌ Erro inesperado ao processar bloco {match_idx}: {e_inner}")
            pass

except Exception as e:
    # print(f"❌ Erro ao acessar a API: {e}")
    pass

try:
    with open(CALENDAR_FILENAME, "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())
    # print(f"\n📌 {added_count} partidas BR salvas em {CALENDAR_FILENAME} (com alarmes no horário do jogo)")
except Exception as e:
    # print(f"❌ Erro ao salvar {CALENDAR_FILENAME}: {e}")
    pass
