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
        EC.presence_of_element_located((By.CSS_SELECTOR, "div"))
    )
    print("🔹 Cards carregados no site.")

    html = driver.page_source
finally:
    driver.quit()

soup = BeautifulSoup(html, "html.parser")

# Lista para armazenar os cards relevantes
cards = []

# Procura todos os divs e verifica se contêm algum time brasileiro
for div in soup.find_all("div"):
    text = div.get_text(" ", strip=True)
    if any(team in text for team in BRAZILIAN_TEAMS):
        cards.append(div)

print(f"🔹 Total de cards encontrados com times brasileiros: {len(cards)}")

calendar = Calendar()

for card in cards:
    try:
        # Extrai todos os times no texto do card
        teams_in_card = []
        for team in BRAZILIAN_TEAMS:
            if team in card.get_text():
                teams_in_card.append(team)
        
        # Extrai horário do jogo usando regex (HH:MM - DD/MM/YYYY)
        text = card.get_text(" ", strip=True)
        match = re.search(r"(\d{2}:\d{2})\s*[-–]\s*(\d{2}/\d{2}/\d{4})", text)
        if not match:
            print(f"⚠️ Horário não encontrado no card: {text}")
            continue
        time_str, date_str = match.groups()
        event_time = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M")

        # Cria evento
        e = Event()
        e.name = " vs ".join(teams_in_card)
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
