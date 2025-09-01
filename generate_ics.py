from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from ics import Calendar, Event
from datetime import datetime, timedelta
import re

BRAZILIAN_TEAMS = ["FURIA", "paiN", "LOUD", "MIBR", "INTZ", "VIVO KEYD"]

options = Options()
options.add_argument("--headless")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

try:
    url = "https://draft5.gg/proximas-partidas"
    print(f"🔹 Acessando URL: {url}")
    driver.get(url)
    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    html = driver.page_source
finally:
    driver.quit()

# Extrai apenas o texto visível da página
text = html.replace("\n", " ").replace("\r", " ")

# Regex para encontrar partidas: TIME1 vs TIME2 + horário
# Exemplo de padrão: "FURIA 0 MOUZ 0 02/09 - 17:00"
pattern = r"([A-Za-z0-9\s]+?)\s0\s([A-Za-z0-9\s]+?)\s0\s(\d{2}/\d{2})\s[-–]\s(\d{2}:\d{2})"

matches = re.findall(pattern, text)
print(f"🔹 Total de jogos encontrados: {len(matches)}")

calendar = Calendar()

for m in matches:
    team1, team2, date_str, time_str = m
    # Verifica se algum time é brasileiro
    if not any(team in [team1.strip(), team2.strip()] for team in BRAZILIAN_TEAMS):
        continue

    event_time = datetime.strptime(f"{date_str} {time_str}", "%d/%m %H:%M")
    e = Event()
    e.name = f"{team1.strip()} vs {team2.strip()}"
    e.begin = event_time
    e.duration = timedelta(hours=1)
    calendar.events.add(e)
    print(f"✅ Jogo adicionado: {e.name} - {e.begin}")

with open("calendar.ics", "w", encoding="utf-8") as f:
    f.writelines(calendar)

print("🔹 calendar.ics gerado com sucesso!")
