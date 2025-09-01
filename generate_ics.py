import requests
from bs4 import BeautifulSoup
from ics import Calendar, Event
from datetime import datetime, timedelta

# Lista de times brasileiros
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial"]

# URL do Draft5 próximas partidas
URL = "https://draft5.gg/proximas-partidas"

def fetch_games():
    response = requests.get(URL)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    games = []
    for row in soup.select(".match-row"):  # exemplo de classe
        team1 = row.select_one(".team1").text.strip()
        team2 = row.select_one(".team2").text.strip()
        date_str = row.select_one(".date").text.strip()
        time_str = row.select_one(".time").text.strip()
        tournament = row.select_one(".tournament").text.strip()

        # Ignora partidas com TBD
        if "TBD" in team1 or "TBD" in team2:
            continue

        # Filtra apenas times brasileiros
        if not any(t in BRAZILIAN_TEAMS for t in [team1, team2]):
            continue

        # Combina data e hora em datetime
        dt = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M")
        games.append({
            "team1": team1,
            "team2": team2,
            "tournament": tournament,
            "datetime": dt
        })
    return games

def generate_ics(games, filename="calendar.ics"):
    cal = Calendar()
    for game in games:
        e = Event()
        e.name = f"{game['team1']} vs {game['team2']} ({game['tournament']})"
        e.begin = game['datetime']
        e.duration = timedelta(hours=2)  # duração padrão
        cal.events.add(e)

    with open(filename, "w", encoding="utf-8") as f:
        f.writelines(cal)
    print(f"{filename} gerado com {len(games)} jogos.")

if __name__ == "__main__":
    games = fetch_games()
    generate_ics(games)
