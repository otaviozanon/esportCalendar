from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from ics import Calendar, Event
from datetime import datetime, timedelta

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

    # Espera até pelo menos um card aparecer
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "div.MatchCardSimple__Match-sc-wcmxha-8"))
    )

    html = driver.page_source
finally:
    driver.quit()

soup = BeautifulSoup(html, "html.parser")

# Seleciona todos os cards de partidas
cards = soup.find_all("div", class_=lambda c: c and "MatchCardSimple__Match" in c)

calendar = Calendar()
total_found = 0

for card in cards:
    try:
        # Pega os dois times
        teams_divs = card.find_all("div", class_=lambda c: c and "MatchCardSimple__MatchTeam" in c)
        if len(teams_divs) != 2:
            continue

        team1 = teams_divs[0].find("span").text.strip()
        team2 = teams_divs[1].find("span").text.strip()

        # Filtra apenas se houver um time brasileiro
        if not any(team in [team1, team2] for team in BRAZILIAN_TEAMS):
            continue

        # Pega horário
        time_small = card.find("small", class_=lambda c: c and "MatchCardSimple__MatchTime" in c)
        if not time_small:
            print(f"⚠️ Horário não encontrado para o jogo: {team1} vs {team2}")
            continue
        hour_min = time_small.find("span").text.strip()

        # Usa data de hoje como referência
        today_str = datetime.now().strftime("%d/%m/%Y")
        event_time = datetime.strptime(f"{today_str} {hour_min}", "%d/%m/%Y %H:%M")

        # Cria evento
        e = Event()
        e.name = f"{team1} vs {team2}"
        e.begin = event_time
        e.duration = timedelta(hours=1)
        calendar.events.add(e)
        total_found += 1
        print(f"✅ Jogo adicionado: {e.name} - {e.begin}")

    except Exception as ex:
        print(f"⚠️ Erro ao processar card: {ex}")

with open("calendar.ics", "w", encoding="utf-8") as f:
    f.writelines(calendar)

print(f"🔹 calendar.ics gerado com sucesso! Total de jogos adicionados: {total_found}")
