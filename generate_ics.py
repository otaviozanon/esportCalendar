import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from ics import Calendar, Event

# Lista de times brasileiros
BRAZILIAN_TEAMS = {"FURIA", "paiN", "MIBR", "LOUD", "Imperial", "Vivo Keyd", "INTZ"}

calendar = Calendar()
total = 0

# Loop de hoje até 7 dias à frente
today = datetime.today()
for i in range(8):
    day = today + timedelta(days=i)
    date_str = day.strftime("%Y-%m-%d")
    url = f"https://www.hltv.org/matches?selectedDate={date_str}"

    print(f"🔹 Buscando jogos em: {url}")
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(resp.text, "html.parser")

    for match in soup.select(".upcomingMatch"):
        teams = [t.get_text(strip=True) for t in match.select(".team")]
        if len(teams) < 2:
            continue

        # Filtro: só times brasileiros
        if not any(team in BRAZILIAN_TEAMS for team in teams):
            continue

        time_str = match.select_one(".time")
        if not time_str:
            continue

        hour = time_str.get_text(strip=True)

        try:
            dt = datetime.strptime(f"{date_str} {hour}", "%Y-%m-%d %H:%M")
        except:
            print(f"⚠️ Não consegui converter horário: {hour}")
            continue

        event_name = match.select_one(".event-name")
        event_label = event_name.get_text(strip=True) if event_name else "Partida HLTV"

        # Criar evento ICS
        e = Event()
        e.name = f"{teams[0]} vs {teams[1]} ({event_label})"
        e.begin = dt
        e.duration = timedelta(hours=2)
        calendar.events.add(e)
        total += 1
        print(f"✅ Adicionado: {e.name} em {date_str} às {hour}")

# Salvar arquivo ICS
with open("calendar.ics", "w", encoding="utf-8") as f:
    f.writelines(calendar)

print(f"🗓️ Arquivo calendar.ics gerado com {total} jogos de times brasileiros (próximos 7 dias).")
