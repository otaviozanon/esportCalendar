from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from ics import Calendar, Event
from datetime import datetime, timedelta
import pytz
import time

# --- Configurações ---
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo", "O PLANO", "Sharks", "RED Canids"]
tz_brazil = pytz.timezone("America/Sao_Paulo")
today = datetime.now(tz_brazil).date()
date_range = [(today + timedelta(days=i)) for i in range(8)]  # hoje + 7 dias
calendar = Calendar()

# --- Configurar Selenium headless ---
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
)
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

total_games = 0
print(f"🔹 Buscando jogos de {date_range[0]} até {date_range[-1]}")

for d in date_range:
    url = f"https://www.hltv.org/matches?selectedDate={d.strftime('%Y-%m-%d')}"
    print(f"🔹 Acessando {url}")
    
    try:
        driver.get(url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.match-day"))
        )
        time.sleep(1)  # espera extra para garantir carregamento
        matches = driver.find_elements(By.CSS_SELECTOR, "div.match-day div.upcomingMatch")
    except Exception as e:
        print(f"⚠️ Erro ao acessar {url}: {e}")
        continue

    for m in matches:
        try:
            teams = m.find_elements(By.CSS_SELECTOR, "div.matchTeamName span")
            if len(teams) < 2:
                continue
            team1 = teams[0].text.strip()
            team2 = teams[1].text.strip()

            # Filtra só times brasileiros
            if not any(team in BRAZILIAN_TEAMS for team in [team1, team2]):
                continue

            # Captura horário
            time_element = m.find_element(By.CSS_SELECTOR, "div.matchTime")
            match_time_text = time_element.text.strip()  # exemplo: "12:00"
            if not match_time_text:
                print(f"⚠️ Horário não encontrado para {team1} vs {team2}")
                continue

            # Converte para datetime no fuso de Brasil
            hour, minute = map(int, match_time_text.split(":"))
            dt = datetime.combine(d, datetime.min.time(), tzinfo=tz_brazil)
            dt = dt.replace(hour=hour, minute=minute)

            # Evento
            event = Event()
            event.name = f"{team1} vs {team2}"
            event.begin = dt
            event.end = dt + timedelta(hours=2)
            event.location = "HLTV.org"

            calendar.events.add(event)
            total_games += 1
            print(f"✅ Jogo adicionado: {team1} vs {team2} às {dt.strftime('%H:%M')}")
        except Exception as e:
            print(f"⚠️ Erro ao processar card: {e}")

driver.quit()

# Salvar arquivo .ics
with open("calendar.ics", "w", encoding="utf-8") as f:
    f.writelines(calendar.serialize_iter())

print(f"🔹 calendar.ics gerado com sucesso! Total de jogos adicionados: {total_games}")
