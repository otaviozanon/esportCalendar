from ics import Calendar, Event
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests

# Times brasileiros que queremos acompanhar
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo", "O PLANO", "Sharks", "RED Canids"]

# Timezone Brasil
tz_brazil = ZoneInfo("America/Sao_Paulo")

# Data inicial = hoje no Brasil
today_brazil = datetime.now(tz_brazil).date()

# Próximos 7 dias (total 8 dias incluindo hoje)
date_range = [(today_brazil + timedelta(days=i)) for i in range(8)]

calendar = Calendar()
total_games = 0

print(f"🔹 Buscando jogos de {date_range[0]} até {date_range[-1]}")

for d in date_range:
    url = f"https://hltv-api.vercel.app/api/matches?date={d.strftime('%Y-%m-%d')}"
    print(f"🔹 Acessando: {url}")

    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        matches = resp.json()
    except Exception as e:
        print(f"⚠️ Erro ao acessar {url}: {e}")
        continue

    for match in matches:
        team1 = match.get("team1", {}).get("name", "")
        team2 = match.get("team2", {}).get("name", "")

        # Filtra só times brasileiros
        if not any(team in BRAZILIAN_TEAMS for team in [team1, team2]):
            continue

        timestamp = match.get("time")  # já vem em ms (epoch)
        if not timestamp:
            print(f"⚠️ Horário não encontrado para {team1} vs {team2}")
            continue

        # Converte para datetime no fuso do Brasil
        dt = datetime.fromtimestamp(timestamp / 1000, tz=ZoneInfo("UTC")).astimezone(tz_brazil)

        event = Event()
        event.name = f"{team1} vs {team2}"
        event.begin = dt
        event.end = dt + timedelta(hours=2)  # duração estimada
        event.description = f"Campeonato: {match.get('event', {}).get('name', 'Desconhecido')}"
        event.location = "HLTV.org"

        calendar.events.add(event)
        total_games += 1

# Salva o calendário
with open("calendar.ics", "w", encoding="utf-8") as f:
    f.writelines(calendar.serialize_iter())

print(f"🔹 calendar.ics gerado com sucesso! Total de jogos adicionados: {total_games}")
