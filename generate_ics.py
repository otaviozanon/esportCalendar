from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from ics import Calendar, Event
from datetime import datetime, timedelta
import time

# Lista de times brasileiros
BRAZILIAN_TEAMS = ["FURIA", "paiN", "LOUD", "MIBR", "INTZ", "VIVO KEYD"]

# Configuração do Chrome headless
options = Options()
options.add_argument("--headless")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

try:
    url = "https://draft5.gg/proximas-partidas"
    print(f"🔹 Acessando URL: {url}")
    driver.get(url)

    # Loop de espera simples: até 15s procurando por cards
    cards_elements = []
    for _ in range(15):
        cards_elements = driver.find_elements("css selector", "div[class*='MatchCardSimple__Match']")
        if cards_elements:
            break
        time.sleep(1)
    else:
        print("⚠️ Nenhum card encontrado após 15 segundos")

    html = driver.page_source
finally:
    driver.quit()

soup = BeautifulSoup(html, "html.parser")
cards = soup.find_all("div", class_=lambda c: c and "MatchCardSimple__Match" in c)

calendar = Calendar()
total_found = 0

for card in cards:
    try:
        # Captura os times
        teams_divs = card.find_all("div", class_=lambda c: c and "MatchCardSimple__MatchTeam" in c)
        if len(teams_divs) != 2:
            continue

        team1 = teams_divs[0].find("span").text.strip()
        team2 = teams_divs[1].find("span").text.strip()

        # Filtra apenas jogos com times brasileiros
        if not any(team in [team1, team2] for team in BRAZILIAN_TEAMS):
            continue

        # Captura o horário corretamente usando CSS selector recursivo
        time_small = card.select_one("small[class*='MatchCardSimple__MatchTime'] span")
        if not time_small:
            print(f"⚠️ Horário não encontrado para o jogo: {team1} vs {team2}")
            continue
        hour_min = time_small.get_text(strip=True)

        # Usa data atual como referência
        today_str = datetime.now().strftime("%d/%m/%Y")
        event_time = datetime.strptime(f"{today_str} {hour_min}", "%d/%m/%Y %H:%M")

        # Cria evento no calendário
        e = Event()
        e.name = f"{team1} vs {team2}"
        e.begin = event_time
        e.duration = timedelta(hours=1)
        calendar.events.add(e)
        total_found += 1
        print(f"✅ Jogo adicionado: {e.name} - {e.begin}")

    except Exception as ex:
        print(f"⚠️ Erro ao processar card: {ex}")

# Gera arquivo ICS
with open("calendar.ics", "w", encoding="utf-8") as f:
    f.writelines(calendar)

print(f"🔹 calendar.ics gerado com sucesso! Total de jogos adicionados: {total_found}")
