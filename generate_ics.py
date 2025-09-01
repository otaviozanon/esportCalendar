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
import re

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
        EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='MatchCard']"))
    )

    html = driver.page_source
finally:
    driver.quit()

soup = BeautifulSoup(html, "html.parser")

# Seleciona todos os cards de partida
cards = soup.find_all("div", class_=re.compile("MatchCard"))

calendar = Calendar()
total_found = 0

for card in cards:
    try:
        text = card.get_text(" ", strip=True)

        # Extrai times (simplesmente os nomes antes do primeiro e segundo "0")
        match_teams = re.findall(r"([A-Za-z0-9\s]+?)\s0\s([A-Za-z0-9\s]+?)\s0", text)
        if not match_teams:
            continue
        team1, team2 = match_teams[0]
        team1 = team1.strip()
        team2 = team2.strip()

        # Filtra apenas se tiver pelo menos um time brasileiro
        if not any(team in [team1, team2] for team in BRAZILIAN_TEAMS):
            continue

        # Extrai horário (ex.: "02/09/2025 17:00" ou "02/09 17:00")
        match_time = re.search(r"(\d{2}/\d{2}(?:/\d{4})?)\s(\d{2}:\d{2})", text)
        if not match_time:
            print(f"⚠️ Horário não encontrado para o jogo: {team1} vs {team2}")
            continue

        date_str, time_str = match_time.groups()

        # Adiciona ano atual se não vier
        if len(date_str.split("/")) == 2:
            year = datetime.now().year
            date_str += f"/{year}"

        event_time = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M")

        # Cria evento
        e = Event()
        e.name = f"{team1} vs {team2}"
        e.begin = event_time
        e.duration = timedelta(hours=1)
        calendar.events.add(e)
        total_found += 1
        print(f"✅ Jogo adicionado: {e.name} - {e.begin}")

    except Exception as ex:
        print(f"⚠️ Erro ao processar card: {text}\n{ex}")

with open("calendar.ics", "w", encoding="utf-8") as f:
    f.writelines(calendar)

print(f"🔹 calendar.ics gerado com sucesso! Total de jogos adicionados: {total_found}")
