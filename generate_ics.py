from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from ics import Calendar, Event
from datetime import datetime, timedelta
import pytz
import time

# Configurações
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo", "O PLANO", "Sharks", "RED Canids"]
tz_brazil = pytz.timezone("America/Sao_Paulo")

# Datas
today = datetime.now(tz_brazil).date()
dates = [(today + timedelta(days=i)) for i in range(8)]  # Hoje + próximos 7 dias

calendar = Calendar()
total_games = 0

# Configura Selenium (headless)
options = Options()
options.headless = True
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(service=Service(), options=options)

for d in dates:
    url = f"https://www.hltv.org/matches?selectedDate={d.strftime('%Y-%m-%d')}"
    print(f"🔹 Acessando {url}")
    driver.get(url)

    try:
        # Espera carregar os matches
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.match-day"))
        )
    except:
        print(f"⚠️ Erro: página não carregou ou bloqueada para {url}")
        continue

    match_days = driver.find_elements(By.CSS_SELECTOR, "div.match-day")
    for day in match_days:
        matches = day.find_elements(By.CSS_SELECTOR, "div.match")
        for match in matches:
            try:
                team1 = match.find_element(By.CSS_SELECTOR, "div.matchTeam .matchTeamName").text
                team2 = match.find_element(By.CSS_SELECTOR, "div.matchTeam:nth-child(2) .matchTeamName").text
                time_str = match.find_element(By.CSS_SELECTOR, "div.matchTime").text  # ex: "12:00"

                if not any(team in BRAZILIAN_TEAMS for team in [team1, team2]):
                    continue

                # Converte para datetime
                hour, minute = map(int, time_str.split(":"))
                match_dt = datetime(d.year, d.month, d.day, hour, minute, tzinfo=tz_brazil)

                event = Event()
                event.name = f"{team1} vs {team2}"
                event.begin = match_dt
                event.end = match_dt + timedelta(hours=2)
                event.location = "HLTV.org"
                calendar.events.add(event)
                total_games += 1
                print(f"✅ Jogo adicionado: {team1} vs {team2} - {match_dt}")
            except Exception as e:
                print(f"⚠️ Erro ao processar match: {e}")

driver.quit()

# Salva o calendar
with open("calendar.ics", "w", encoding="utf-8") as f:
    f.writelines(calendar.serialize_iter())

print(f"🔹 calendar.ics gerado com sucesso! Total de jogos adicionados: {total_games}")
