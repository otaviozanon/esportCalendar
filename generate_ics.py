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
        EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='MatchCard']"))
    )

    html = driver.page_source
finally:
    driver.quit()

soup = BeautifulSoup(html, "html.parser")

# Seleciona todos os cards de partida
cards = soup.find_all("div", class_=lambda c: c and "MatchCard" in c)

calendar = Calendar()
total_found = 0

for card in cards:
    try:
        # Procura os spans dentro do card
        spans = card.find_all("span")
        team1 = team2 = None
        event_time = None

        for span in spans:
            text = span.get_text(" ", strip=True)
            # Procura times brasileiros
            for team in BRAZILIAN_TEAMS:
                if team in text:
                    if not team1:
                        team1 = team
                    elif not team2 and team != team1:
                        team2 = team
            # Procura horário no formato HH:MM
            if ':' in text and any(char.isdigit() for char in text):
                event_time = text

        if not team1 or not team2 or not event_time:
            continue

        # Tenta extrair hora e data, assumindo data atual se não estiver
        import re
        time_match = re.search(r"(\d{2}:\d{2})", event_time)
        if not time_match:
            continue
        hour_min = time_match.group(1)
        # Usa data de hoje como referência
        today_str = datetime.now().strftime("%d/%m/%Y")
        dt = datetime.strptime(f"{today_str} {hour_min}", "%d/%m/%Y %H:%M")

        e = Event()
        e.name = f"{team1} vs {team2}"
        e.begin = dt
        e.duration = timedelta(hours=1)
        calendar.events.add(e)
        total_found += 1
        print(f"✅ Jogo adicionado: {e.name} - {e.begin}")

    except Exception as ex:
        print(f"⚠️ Erro ao processar card: {ex}")

with open("calendar.ics", "w", encoding="utf-8") as f:
    f.writelines(calendar)

print(f"🔹 calendar.ics gerado com sucesso! Total de jogos adicionados: {total_found}")
