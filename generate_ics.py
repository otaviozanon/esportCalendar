from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from ics import Calendar, Event
from datetime import datetime, timedelta
import pytz

# -------------------- Configurações --------------------
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo",
                   "Sharks", "RED Canids", "Legacy", "ODDIK"]
BR_TZ = pytz.timezone("America/Sao_Paulo")
cal = Calendar()
added_count = 0

# Datas: hoje até 5 dias à frente
today = datetime.utcnow()
dates = [today + timedelta(days=i) for i in range(6)]
print(f"🕒 Agora (UTC): {today}")

# -------------------- Configurar Selenium --------------------
options = Options()
options.add_argument("--headless")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1920,1080")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
wait = WebDriverWait(driver, 15)  # espera máxima de 15s por elementos

# -------------------- Coleta de partidas --------------------
for date in dates:
    date_str = date.strftime('%Y-%m-%d')
    url = f"https://www.hltv.org/matches?selectedDate={date_str}"
    print(f"\n🔍 Buscando partidas para {date_str} em {url}...")

    try:
        driver.get(url)
        
        # Espera pelo carregamento de qualquer bloco de partida
        try:
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "match-zone-wrapper")))
            print("✅ Blocos de partidas carregados")
        except:
            print("⚠️ Nenhum bloco de partidas carregado após espera")

        zones = driver.find_elements(By.CLASS_NAME, "match-zone-wrapper")
        print(f"📦 {len(zones)} blocos de partidas encontrados na página")

        for zone_idx, zone in enumerate(zones, 1):
            match_blocks = zone.find_elements(By.CLASS_NAME, "match-wrapper")
            print(f"   🔹 Zona {zone_idx}: {len(match_blocks)} partidas")

            for match_idx, match in enumerate(match_blocks, 1):
                try:
                    team1 = match.find_element(By.CSS_SELECTOR, "div.match-team.team1 > div.match-teamname").text.strip()
                    team2 = match.find_element(By.CSS_SELECTOR, "div.match-team.team2 > div.match-teamname").text.strip()

                    if not any(br.lower() in team1.lower() or br.lower() in team2.lower() for br in BRAZILIAN_TEAMS):
                        print(f"      ⚠️ Partida {match_idx}: Nenhum time BR ({team1} vs {team2})")
                        continue

                    event_name = match.find_element(By.CLASS_NAME, "match-event").text.strip()
                    time_str = match.find_element(By.CLASS_NAME, "match-time").text.strip()
                    match_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                    match_time = BR_TZ.localize(match_time)

                    match_url_tag = match.find_element(By.CSS_SELECTOR, "a.match-info")
                    match_url = match_url_tag.get_attribute("href")

                    # Criar evento ICS
                    e = Event()
                    e.name = f"{team1} vs {team2} - {event_name}"
                    e.begin = match_time
                    e.end = e.begin + timedelta(hours=2)
                    e.description = f"Partida entre {team1} e {team2} no evento {event_name}"
                    e.url = match_url

                    cal.events.add(e)
                    added_count += 1
                    print(f"      ✅ Adicionado: {e.name} ({e.begin}) | URL: {e.url}")

                except Exception as e:
                    print(f"      ⚠️ Erro ao processar partida {match_idx} na zona {zone_idx}: {e}")

    except Exception as e:
        print(f"⚠️ Erro ao acessar {url}: {e}")

# -------------------- Finalizar --------------------
driver.quit()

# Salvar calendar.ics
try:
    with open("calendar.ics", "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())
    print(f"\n📌 {added_count} partidas BR salvas em calendar.ics")
except Exception as e:
    print(f"❌ Erro ao salvar calendar.ics: {e}")
