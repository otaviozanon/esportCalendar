from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from ics import Calendar, Event
from datetime import datetime, timedelta
import time

BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial"]
URL = "https://draft5.gg/proximas-partidas"

# Configuração do Selenium usando webdriver_manager
options = Options()
options.add_argument("--headless")
options.add_argument("--disable-gpu")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def fetch_games():
    driver.get(URL)
    time.sleep(5)  # esperar JS carregar
    
    games = []
    match_cards = driver.find_elements("css selector", "div.MatchCardSimple__Match-sc-wcmxha-8")
    
    for card in match_cards:
        try:
            teams = card.find_elements("css selector", "div.MatchCardSimple__TeamNameAndLogo-sc-wcmxha-40 span")
            if len(teams) != 2:
                continue
            team1, team2 = teams[0].text.strip(), teams[1].text.strip()
            if "TBD" in team1 or "TBD" in team2:
                continue
            if not any(t in BRAZILIAN_TEAMS for t in [team1, team2]):
                continue

            datetime_str = card.find_element("css selector", "div.MatchCardSimple__MatchDate-sc-wcmxha-37").text.strip()
            dt = datetime.strptime(datetime_str, "%d/%m/%Y %H:%M")  # ajuste conforme HTML real
            tournament = card.find_element("css selector", "div.MatchCardSimple__TournamentName-sc-wcmxha-42").text.strip()

            games.append({
                "team1": team1,
                "team2": team2,
                "tournament": tournament,
                "datetime": dt
            })
        except:
            continue
    return games

def generate_ics(games, filename="calendar.ics"):
    cal = Calendar()
    for game in games:
        e = Event()
        e.name = f"{game['team1']} vs {game['team2']} ({game['tournament']})"
        e.begin = game['datetime']
        e.duration = timedelta(hours=2)
        cal.events.add(e)
    with open(filename, "w", encoding="utf-8") as f:
        f.writelines(cal)
    print(f"{filename} gerado com {len(games)} jogos.")

if __name__ == "__main__":
    games = fetch_games()
    generate_ics(games)
    driver.quit()
