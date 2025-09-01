import requests
from bs4 import BeautifulSoup
from ics import Calendar, Event
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# --- Configurações ---
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo", "O PLANO", "Sharks", "RED Canids"]
tz_brazil = ZoneInfo("America/Sao_Paulo")
today_brazil = datetime.now(tz_brazil).date()
date_range = [(today_brazil + timedelta(days=i)) for i in range(8)]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/139.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
}

calendar = Calendar()
total_games = 0

print(f"🔹 Buscando jogos de {date_range[0]} até {date_range[-1]}")

for d in date_range:
    url = f"https://www.hltv.org/matches?selectedDate={d.strftime('%Y-%m-%d')}"
    print(f"🔹 Acessando {url}")

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
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

        if not any(team in BRAZILIAN_TEAMS for team in [team1, team2]):
            continue

        time_elem = match.select_one(".matchTime")
        if not time_elem or not time_elem.has_attr("data-unix"):
            print(f"⚠️ Horário não encontrado para {team1} vs {team2}")
            continue

        timestamp = int(time_elem["data-unix"]) / 1000
        dt = datetime.fromtimestamp(timestamp, tz=ZoneInfo("UTC")).astimezone(tz_brazil)

        event_elem = match.select_one(".matchEventName")
        event_name = event_elem.get_text(strip=True) if event_elem else "Desconhecido"

        event = Event()
        event.name = f"{team1} vs {team2}"
        event.begin = dt
        event.end = dt + timedelta(hours=2)
        event.description = f"Campeonato: {event_name}"
        event.location = "HLTV.org"

        calendar.events.add(event)
        total_games += 1
        print(f"✅ Jogo adicionado: {team1} vs {team2} - {dt}")

with open("calendar.ics", "w", encoding="utf-8") as f:
    f.writelines(calendar.serialize_iter())

print(f"🔹 calendar.ics gerado com sucesso! Total de jogos adicionados: {total_games}")
