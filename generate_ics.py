from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from ics import Calendar, Event
from datetime import datetime
import time
import re

# Lista de times brasileiros
BRAZILIAN_TEAMS = ["FURIA", "paiN", "LOUD", "MIBR", "INTZ", "VIVO KEYD"]

# Configurações do Chrome
options = Options()
options.add_argument("--headless")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

try:
    url = "https://draft5.gg/proximas-partidas"
    print(f"🔹 Acessando URL: {url}")
    driver.get(url)

    # Espera até 15s pelo carregamento do primeiro card
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='MatchCard']"))
    )
    print("🔹 Cards carregados no site.")

    html = driver.page_source
finally:
    driver.quit()

soup = BeautifulSoup(html, "html.parser")

# Seleciona todos os cards que contenham pelo menos um time brasileiro
cards = []
for div in soup.find_all("div", class_=re.compile("MatchCard")):
    text = div.get_text(" ", strip=True)
    if any(team in text for team in BRAZILIAN_TEAMS):
        cards.append(div)

print(f"🔹 Total de cards encontrados com times brasileiros: {len(cards)}")

calendar = Calendar()

for card in cards:
    try:
        # Extrai os times do jogo
        teams = [t.get_text(strip=True) for t in card.find_all("span", class_=re.compile("team-name"))]
        if not any(team in teams for team in BRAZILIAN_TEAMS):
            continue  # ignora se nenhum time brasileiro estiver

        # Extrai horário do jogo
        time_div = card.find("div", class_=re.compile("match-time"))
        if not time_div:
            print(f"⚠️ Não foi possível encontrar horário no card: {' '.join(teams)}")
            continue

        time_text = time_div.get_text(strip=True)

        # Formato esperado: "02:00 - 02/09/2025" ou similar
        match = re.search(r"(\d{2}:\d{2})\s*-\s*(\d{2}/\d{2}/\d{4})", time_text)
        if not match:
            print(f"⚠️ Formato de horário inesperado: {time_text}")
            continue

        time_str, date_str = match.groups()
        event_time = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M")

        e = Event()
        e.name = " vs ".join(teams)
        e.begin = event_time
        e.duration = timedelta(hours=1)
        calendar.events.add(e)
        print(f"✅ Jogo adicionado: {e.name} - {e.begin}")

    except Exception as ex:
        print(f"⚠️ Erro ao processar card: {card.get_text(' ', strip=True)}\n{ex}")

# Salva o .ics
with open("calendar.ics", "w", encoding="utf-8") as f:
    f.writelines(calendar)

print("🔹 calendar.ics gerado com sucesso!")
