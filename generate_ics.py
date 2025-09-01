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
    print("🔹 Iniciando Selenium headless...")
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    print(f"🔹 Acessando URL: {URL}")
    driver.get(URL)
    time.sleep(5)  # esperar JS carregar

    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")
    games = []

    match_cards = soup.select("div.MatchCardSimple__Match-sc-wcmxha-8")
    print(f"🔹 Total de cards encontrados: {len(match_cards)}")

    for i, card in enumerate(match_cards, start=1):
        try:
            print(f"\n🔹 Processando card {i}...")
            teams = [span.text.strip() for span in card.select("div.MatchCardSimple__TeamNameAndLogo-sc-wcmxha-40 span")]
            if len(teams) != 2:
                print("⚠️ Card ignorado: número de times diferente de 2")
                continue
            team1, team2 = teams
            print(f"Times detectados: {team1} x {team2}")

            if "TBD" in team1 or "TBD" in team2:
                print("⚠️ Card ignorado: time TBD")
                continue

            if not any(t in BRAZILIAN_TEAMS for t in [team1, team2]):
                print("⚠️ Card ignorado: nenhum time brasileiro")
                continue

            datetime_el = card.select_one("div.MatchCardSimple__MatchDate-sc-wcmxha-37")
            if not datetime_el:
                print("⚠️ Card ignorado: data/hora não encontrada")
                continue
            datetime_str = datetime_el.text.strip()
            try:
                dt = datetime.strptime(datetime_str, "%d/%m/%Y %H:%M")
            except ValueError:
                print(f"⚠️ Formato de data inesperado: {datetime_str}")
                continue
            print(f"Data/hora: {dt}")

            tournament_el = card.select_one("div.MatchCardSimple__TournamentName-sc-wcmxha-42")
            tournament = tournament_el.text.strip() if tournament_el else "Torneio desconhecido"
            print(f"Torneio: {tournament}")

            games.append({
                "team1": team1,
                "team2": team2,
                "tournament": tournament,
                "datetime": dt
            })
            print("✅ Card adicionado à lista de jogos")

        except Exception as e:
            print(f"⚠️ Erro processando o card: {e}")
            continue

    driver.quit()
    print(f"\n🔹 Total de jogos capturados: {len(games)}")
    return games

def generate_ics(games, filename="calendar.ics"):
    print(f"🔹 Gerando arquivo {filename}...")
    cal = Calendar()
    for game in games:
        e = Event()
        e.name = f"{game['team1']} vs {game['team2']} ({game['tournament']})"
        e.begin = game['datetime']
        e.duration = timedelta(hours=2)
        cal.events.add(e)
        print(f"✅ Evento adicionado: {e.name} - {e.begin}")

    with open(filename, "w", encoding="utf-8") as f:
        f.writelines(cal)
    print(f"✅ {filename} gerado com {len(games)} jogos.")

if __name__ == "__main__":
    print("🔹 Iniciando script de captura de jogos")
    games = fetch_games()
    if not games:
        print("⚠️ Nenhum jogo encontrado.")
    generate_ics(games)
    print("🔹 Script finalizado")
