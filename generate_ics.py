import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
from ics import Calendar, Event
from ics.alarm import DisplayAlarm
import hashlib
import json

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from webdriver_manager.chrome import ChromeDriverManager

# -------------------- Configurações Globais --------------------
BRAZILIAN_TEAMS = [
    "FURIA", "paiN", "MIBR", "Imperial", "Fluxo",
    "RED Canids", "Legacy", "ODDIK", "Imperial Esports"
]

BRAZILIAN_TEAMS_EXCLUSIONS = [
    "Imperial.A", "Imperial Fe", "MIBR.A", "paiN.A", "ODDIK.A",
    "Imperial Academy", "Imperial.Acd", "Imperial Female",
    "Furia Academy", "Furia.A", "Pain Academy", "Mibr Academy",
    "Legacy Academy", "ODDIK Academy", "RED Canids Academy", "Fluxo Academy"
]

CALENDAR_FILENAME = "calendar.ics"
BR_TZ = pytz.timezone("America/Sao_Paulo")

def normalize_team(name):
    return name.lower().strip() if name else ""

NORMALIZED_BRAZILIAN_TEAMS = {normalize_team(t) for t in BRAZILIAN_TEAMS}
NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS = {normalize_team(t) for t in BRAZILIAN_TEAMS_EXCLUSIONS}

# -------------------- Lógica Principal --------------------
cal = Calendar()
added_count = 0

today = datetime.now(BR_TZ)
date_str = today.strftime("%d-%m-%Y")
TIPSGG_URL = f"https://tips.gg/csgo/matches/{date_str}/"

driver = None

try:
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--log-level=3")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.get(TIPSGG_URL)

    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'script[type="application/ld+json"]'))
    )

    soup = BeautifulSoup(driver.page_source, "html.parser")
    scripts = soup.find_all("script", type="application/ld+json")

    for script in scripts:
        try:
            event_data = json.loads(script.string)

            if event_data.get("@type") != "SportsEvent":
                continue

            competitors = event_data.get("competitor", [])
            if len(competitors) < 2:
                continue

            team1 = competitors[0].get("name")
            team2 = competitors[1].get("name")

            if not team1 or not team2 or team1 == "TBD" or team2 == "TBD":
                continue

            start_date_str = event_data.get("startDate")
            if not start_date_str:
                continue

            match_time_utc = datetime.fromisoformat(
                start_date_str.replace("Z", "+00:00")
            )

            if match_time_utc < datetime.now(pytz.utc):
                continue

            t1 = normalize_team(team1)
            t2 = normalize_team(team2)

            is_br = (
                (t1 in NORMALIZED_BRAZILIAN_TEAMS and t1 not in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS)
                or
                (t2 in NORMALIZED_BRAZILIAN_TEAMS and t2 not in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS)
            )

            if not is_br:
                continue

            match_url = event_data.get("url", "")
            if match_url and not match_url.startswith("http"):
                match_url = f"https://tips.gg{match_url}"

            description = event_data.get("description", "")
            organizer = event_data.get("organizer", {}).get("name", "")

            uid = hashlib.sha1(
                f"{team1}{team2}{start_date_str}".encode("utf-8")
            ).hexdigest()

            e = Event()
            e.name = f"{team1} vs {team2}"
            e.begin = match_time_utc
            e.duration = timedelta(hours=2)
            e.uid = uid
            e.description = f"{description}\n{organizer}\n{match_url}"

            e.alarms.append(DisplayAlarm(trigger=timedelta(minutes=-15)))

            cal.events.add(e)
            added_count += 1

        except json.JSONDecodeError as e:
            print(f"❌ Erro ao decodificar JSON: {e}")
        except Exception as e:
            print(f"❌ Erro ao processar partida: {e}")

except TimeoutException:
    print("❌ Timeout ao carregar a página.")
except WebDriverException as e:
    print(f"❌ Erro do WebDriver: {e}")
except Exception as e:
    print(f"❌ Erro geral: {e}")
finally:
    if driver:
        driver.quit()

# -------------------- Salvamento --------------------
print(f"💾 Salvando arquivo: {CALENDAR_FILENAME}")
try:
    with open(CALENDAR_FILENAME, "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())
    print(f"📌 Total de partidas adicionadas: {added_count}")
except Exception as e:
    print(f"❌ Erro ao salvar o arquivo: {e}")
