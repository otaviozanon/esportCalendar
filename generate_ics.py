from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from ics import Calendar, Event
from datetime import datetime, timedelta
import time

# Lista de times brasileiros
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial"]

# URL do Draft5 próximas partidas
URL = "https://draft5.gg/proximas-partidas"

# Configuração do Selenium (Chrome headless)
options = Options()
options.add_argument("--headless")
options.add_argument("--disable-gpu")
driver = webdriver.Chrome(options=options)

def fetch_games():
    driver.get(URL)
    time.sleep(5)  # esperar a página carregar JS
    
    games = []
    
    # Cada card de partida
    match_cards = driver.find_elements(By.CSS_SELECTOR, "div.MatchCardSimple__Match-sc-wcmxha-8")  # ajuste conforme HTML
    
    for card in match_cards:
        try:
            teams = card.find_elements(By.CSS_SELECTOR, "div.MatchCardSimple__TeamNameAndLogo-sc-wcmxha-40 span")
            if len(teams) != 2:
                continue
            team1 = teams[0].text.strip()
            team2 = teams[1].text.strip()

            # Ignorar partidas com TBD
            if "TBD" in team1 or "TBD" in team2:
                continue

            # Filtrar apenas times brasileiros
            if not any(t in BRAZILIAN_TEAMS for t in [team1, team2]):
                continue

            # Pegar data e hora
            datetime_str = card.find_element(By.CSS_SELECTOR, "div.MatchCardSimple__MatchDate-sc-wcmxha-37").text.strip()
            # Exemplo: "31/08/2025 12:00" -> ajustar conforme formato real
            dt = datetime.strptime(datetime_str, "%d/%m/%Y %H:%M")
            
            # Pegar torneio
            tournament = card.find_element(By.CSS_SELECTOR, "div.MatchCardSimple__TournamentName-sc-wcmxha-42").text.strip()

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
