from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from ics import Calendar, Event
from datetime import datetime, timedelta
import pytz
import time

# Configurações
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo",
                   "Sharks", "RED Canids", "Legacy", "ODDIK"]
BR_TZ = pytz.timezone("America/Sao_Paulo")
cal = Calendar()
added_count = 0

# Datas: hoje até 5 dias à frente
today = datetime.utcnow()
dates = [today + timedelta(days=i) for i in range(6)]

print(f"🕒 Agora (UTC): {today}")

# Configurar Selenium headless
options = Options()
options.add_argument("--headless")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
driver = webdriver.Chrome(options=options)

for date in dates:
    date_str = date.strftime('%Y-%m-%d')
    url = f"https://www.hltv.org/matches?selectedDate={date_str}"
    print(f"\n🔍 Buscando partidas para {date_str} em {url}...")

    try:
        driver.get(url)
        time.sleep(2)  # espera carregar JS
        soup = BeautifulSoup(driver.page_source, "lxml")

        match_blocks = soup.find_all("a", class_="a-reset")
        print(f"📦 {len(match_blocks)} partidas encontradas na página")

        for match in match_blocks:
            try:
                teams = match.find_all("div", class_="matchTeamName")
                if len(teams) < 2:
                    continue
                team1 = teams[0].text.strip()
                team2 = teams[1].text.strip()

                # Filtrar times BR
                if not any(br.lower() in team1.lower() or br.lower() in team2.lower() for br in BRAZILIAN_TEAMS):
                    continue

                event_name_tag = match.find("div", class_="matchEventName")
                event_name = event_name_tag.text.strip() if event_name_tag else "Unknown Event"

                time_tag = match.find("div", class_="matchTime")
                time_str = time_tag.text.strip() if time_tag else "00:00"
                match_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                match_time = BR_TZ.localize(match_time)

                match_url = "https://www.hltv.org" + match['href']

                e = Event()
                e.name = f"{team1} vs {team2} - {event_name}"
                e.begin = match_time
                e.end = e.begin + timedelta(hours=2)  # duração estimada
                e.description = f"Partida entre {team1} e {team2} no evento {event_name}"
                e.url = match_url

                cal.events.add(e)
                added_count += 1
                print(f"✅ Adicionado: {e.name} ({e.begin}) | URL: {e.url}")

            except Exception as e:
                print(f"⚠️ Erro ao processar partida: {e}")

    except Exception as e:
        print(f"⚠️ Erro ao acessar {url}: {e}")

# Fechar driver
driver.quit()

# --- Salvar calendar.ics ---
try:
    with open("calendar.ics", "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())
    print(f"\n📌 {added_count} partidas BR salvas em calendar.ics")
except Exception as e:
    print(f"❌ Erro ao salvar calendar.ics: {e}")
