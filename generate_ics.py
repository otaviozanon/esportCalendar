import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from ics import Calendar, Event

BRAZILIAN_TEAMS = {"FURIA", "paiN", "MIBR", "LOUD", "Imperial", "Vivo Keyd", "INTZ"}

# Data de hoje
today = datetime.today().strftime("%Y-%m-%d")
url = f"https://www.hltv.org/matches?selectedDate={today}"

print(f"🔹 Buscando jogos em: {url}")
resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
soup = BeautifulSoup(resp.text, "html.parser")

calendar = Calendar()
total = 0

for match in soup.select(".upcomingMatch"):
    teams = [t.get_text(strip=True) for t in match.select(".team")]
    if len(teams) < 2:
        continue

    # filtro: só times brasileiros
    if not any(team in BRAZILIAN_TEAMS for team in teams):
        continue

    time_str = match.select_one(".time")
    if not time_str:
        continue

    # converte hora HLTV -> datetime UTC
    hour = time_str.get_text(strip=True)
    try:
        dt = datetime.strptime(f"{today} {hour}", "%Y-%m-%d %H:%M")
    except:
        continue

    # cria evento ICS
    e = Event()
    e.name = f"{teams[0]} vs {teams[1]}"
    e.begin = dt
    e.duration = timedelta(hours=2)
    calendar.events.add(e)
    total += 1
    print(f"✅ Adicionado: {e.name} às {hour}")

with open("calendar.ics", "w", encoding="utf-8") as f:
    f.writelines(calendar)

print(f"🗓️ Arquivo calendar.ics gerado com {total} jogos de times brasileiros para {today}")
