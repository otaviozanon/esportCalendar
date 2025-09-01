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
import time

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

    # Pega o HTML completo
    html = driver.page_source
finally:
    driver.quit()

# Parse com BeautifulSoup
soup = BeautifulSoup(html, "html.parser")

# Seleciona todos os cards que contenham pelo menos um time brasileiro
cards = []
for div in soup.find_all("div"):
    text = div.get_text(strip=True)
    if any(team in text for team in BRAZILIAN_TEAMS):
        cards.append(div)

print(f"🔹 Total de cards encontrados com times brasileiros: {len(cards)}")

# Cria calendário
calendar = Calendar()

for card in cards:
    text = card.get_text(" ", strip=True)
    try:
        # Aqui você pode ajustar como extrair times e horário
        # Exemplo simplificado:
        times = [team for team in BRAZILIAN_TEAMS if team in text]
        event_time = datetime.now() + timedelta(days=1)  # ajuste conforme data real do card
        e = Event()
        e.name = " vs ".join(times)
        e.begin = event_time
        e.duration = timedelta(hours=1)
        calendar.events.add(e)
        print(f"✅ Jogo adicionado: {e.name} - {e.begin}")
    except Exception as ex:
        print(f"⚠️ Erro ao processar card: {text}\n{ex}")

# Salva o .ics
with open("calendar.ics", "w", encoding="utf-8") as f:
    f.writelines(calendar)
print("🔹 calendar.ics gerado com sucesso!")
