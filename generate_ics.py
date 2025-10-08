import os
import re
import pytz
import warnings
from datetime import datetime, timezone, timedelta
from ics import Calendar, Event
import time
import random

# Selenium
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# --- Suprimir FutureWarning específico do ics ---
warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    message=r"Behaviour of str\(Component\) will change in version 0.9.*"
)

# --- Configurações ---
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo", "Sharks", 
                   "RED Canids", "Legacy", "ODDIK"]
BR_TZ = pytz.timezone("America/Sao_Paulo")
MAX_AGE_DAYS = 30
LIQUIPEDIA_URL = "https://liquipedia.net/counterstrike/Liquipedia:Matches"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0"
]

def remove_emojis(text: str) -> str:
    return re.sub(r"[^\x00-\x7F]+", "", text)

def carregar_html_liquipedia(url: str):
    """Carrega o HTML renderizado da Liquipedia usando Selenium."""
    print(f"🌐 Acessando {url} via Selenium...")
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
    options.add_argument("--window-size=1920,1080")

    # 🔹 Aponta para o Chromium do Ubuntu Actions
    options.binary_location = "/usr/bin/chromium-browser"

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    try:
        driver.get(url)
        time.sleep(7)  # espera o JS carregar
        html = driver.page_source
        print(f"✅ Página carregada ({len(html)} caracteres).")
        return html
    finally:
        driver.quit()

# --- Tempo e corte ---
now_utc = datetime.now(timezone.utc)
cutoff_time = now_utc - timedelta(days=MAX_AGE_DAYS)
print(f"🕒 Agora (UTC): {now_utc}")
print(f"🗑️ Jogos anteriores a {cutoff_time} serão removidos.")

# --- Carregar calendário existente ---
my_calendar = Calendar()
if os.path.exists("calendar.ics"):
    with open("calendar.ics", "r", encoding="utf-8") as f:
        try:
            cleaned_lines = [line for line in f.readlines() if not line.startswith(";")]
            calendars = Calendar.parse_multiple("".join(cleaned_lines))
            for cal in calendars:
                my_calendar.events.update(cal.events)
            print("🔹 calendar.ics antigo carregado.")
        except Exception as e:
            print(f"⚠️ Erro ao carregar o calendário antigo: {e}")

# --- Limpar eventos antigos ---
old_count = len(my_calendar.events)
my_calendar.events = {ev for ev in my_calendar.events if ev.begin and ev.begin > cutoff_time}
print(f"🧹 Removidos {old_count - len(my_calendar.events)} eventos antigos.")

# --- Scraping via Selenium ---
html = carregar_html_liquipedia(LIQUIPEDIA_URL)
soup = BeautifulSoup(html, "html.parser")
matches = soup.select("div.match-card")

added_count = 0

for match in matches:
    teams = [t.get_text(strip=True) for t in match.select(".team")]
    time_elem = match.select_one(".match-countdown")
    event_elem = match.select_one(".match-meta .event")

    if not teams or not time_elem:
        continue

    timestamp = time_elem.get("data-timestamp")
    if not timestamp:
        continue
    try:
        event_time_utc = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
    except Exception:
        continue

    event_name = f"{teams[0]} vs {teams[1]}"
    if not any(team.lower() in event_name.lower() for team in BRAZILIAN_TEAMS):
        continue

    ev = Event()
    ev.name = remove_emojis(event_name)
    ev.begin = event_time_utc
    ev.uid = f"{event_time_utc.timestamp()}_{teams[0]}_{teams[1]}"
    ev.description = f"Torneio: {event_elem.get_text(strip=True) if event_elem else 'Desconhecido'}"
    ev.location = "Liquipedia.net"
    ev.created = now_utc

    if not any(e.uid == ev.uid for e in my_calendar.events):
        my_calendar.events.add(ev)
        added_count += 1
        event_time_br = event_time_utc.astimezone(BR_TZ)
        print(f"✅ Adicionado: {ev.name} em {event_time_br}")

print(f"📌 {added_count} novos eventos adicionados.")

# --- Salvar calendar.ics ---
with open("calendar.ics", "w", encoding="utf-8") as f:
    for line in my_calendar.serialize_iter():
        f.write(remove_emojis(line) + "\n")
    f.write(f"X-GENERATED-TIME:{datetime.now(timezone.utc).isoformat()}\n")

print("🔹 calendar.ics atualizado com jogos da Liquipedia!")
