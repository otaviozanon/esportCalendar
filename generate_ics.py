from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from ics import Calendar, Event
from datetime import datetime, timedelta
import time

# Lista de times brasileiros
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial"]

# URL Draft5 próximas partidas
URL = "https://draft5.gg/proximas-partidas"

def fetch_games():
    # Configuração Selenium headless
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get(URL)
    time.sleep(5)  # esperar JS carregar

    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")
    games = []

    # Seleciona todos os cards de partidas
    match_cards = soup.select("div.MatchCardSimple__Match-sc-wcmxha-8")  # ajuste se necessário

    for card in match_cards:
        try:
            teams = [span.text.strip() for span in card.select("div.MatchCardSimple__TeamNameAndLogo-sc-wcmxha-40 span")]
            if len(teams) != 2:
                continue
            team1, team2 = teams

            # Ignora partidas com TBD
            if "TBD" in team1 or "TBD" in team2:
                continue

            # Filtra apenas times brasileiros
            if not any(t in BRAZILIAN_TEAMS for t in [team1, team2]):
                continue

            # Pega data e hora
            datetime_str = card.select_one("div.MatchCardSimple__MatchDate-sc-wcmxha-37").text.strip()
            dt = datetime.strptime(datetime_str, "%d/%m/%Y %H:%M")  # ajuste se necessário

            # Torneio
            tournament = card.select_one("div.MatchCardSimple__TournamentName-sc-wcmxha-42").text.strip()

            games.append({
                "team1": team1,
                "team2": team2,
                "tournament": tournament,
                "datetime": dt
            })
        except Exception as e:
            print(f"⚠️ Erro processando um card: {e}")
            continue

    driver.quit()
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
