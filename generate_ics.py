import requests
from bs4 import BeautifulSoup
from ics import Calendar, Event
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Lista de times brasileiros que queremos acompanhar
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
    url = f"https://www.hltv.org/matches?selectedDate={d.strftime('%Y-%m-%d')}"
    print(f"🔹 Acessando {url}")

    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except Exception as e:
        print(f"⚠️ Erro ao acessar {url}: {e}")
        continue

    soup = BeautifulSoup(resp.text, "html.parser")
    matches = soup.select(".upcomingMatch")

    for match in matches:
        teams = [t.get_text(strip=True) for t in match.select(".team")]
        if len(teams) < 2:
            continue
        team1, team2 = teams[:2]

        # Filtra só jogos com times brasileiros
        if not any(team in BRAZILIAN_TEAMS for team in [team1, team2]):
            continue

        # Extrair horário do atributo data-unix (epoch em ms)
        time_elem = match.select_one(".matchTime")
        if not time_elem or not time_elem.has_attr("data-unix"):
            print(f"⚠️ Horário não encontrado para {team1} vs {team2}")
            continue

        timestamp = int(time_elem["data-unix"]) / 1000
        dt = datetime.fromtimestamp(timestamp, tz=ZoneInfo("UTC")).astimezone(tz_brazil)

        # Extrair nome do campeonato
        event_elem = match.select_one(".matchEventName")
        event_name = event_elem.get_text(strip=True) if event_elem else "Desconhecido"

        # Criar evento ICS
        event = Event()
        event.name = f"{team1} vs {team2}"
        event.begin = dt
        event.end = dt + timedelta(hours=2)  # duração estimada
        event.description = f"Campeonato: {event_name}"
        event.location = "HLTV.org"

        calendar.events.add(event)
        total_games += 1
        print(f"✅ Jogo adicionado: {team1} vs {team2} - {dt}")

# Salvar arquivo ICS
with open("calendar.ics", "w", encoding="utf-8") as f:
    f.writelines(calendar.serialize_iter())

print(f"🔹 calendar.ics gerado com sucesso! Total de jogos adicionados: {total_games}")
