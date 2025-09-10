import requests
from bs4 import BeautifulSoup
from ics import Calendar, Event
from datetime import datetime, timedelta
import pytz
import time

HLTV_MATCHES_URL = "https://www.hltv.org/matches"
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo",
                   "Sharks", "RED Canids", "Legacy", "ODDIK"]
BR_TZ = pytz.timezone("America/Sao_Paulo")
MAX_AGE_DAYS = 30

cal = Calendar()
now_utc = datetime.utcnow()
cutoff_time = now_utc - timedelta(days=MAX_AGE_DAYS)

print(f"🕒 Agora (UTC): {now_utc}")
print(f"🗑️ Ignorando partidas com início antes de {cutoff_time}")

def fetch_html(url, retries=3, delay=2):
    headers = {"User-Agent": "Mozilla/5.0"}
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "lxml")
        except Exception as e:
            print(f"⚠️ Tentativa {attempt+1} falhou para {url}: {e}")
            time.sleep(delay)
    return None

def extract_matches(soup):
    matches_list = []
    # Tenta encontrar blocos de partidas usando padrões genéricos
    match_containers = soup.find_all("a", href=True)
    for a_tag in match_containers:
        href = a_tag['href']
        if "/matches/" in href:
            match_url = "https://www.hltv.org" + href
            match_soup = fetch_html(match_url)
            if not match_soup:
                continue
            # Procurar times dentro do link do evento
            teams = match_soup.find_all("div", class_="teamName")
            if len(teams) < 2:
                continue
            team1 = teams[0].get_text(strip=True)
            team2 = teams[1].get_text(strip=True)
            # Horário
            time_tag = match_soup.find("div", class_="matchTime")
            if time_tag and time_tag.has_attr("data-unix"):
                match_time = datetime.utcfromtimestamp(int(time_tag["data-unix"])/1000)
            else:
                match_time = datetime.utcnow()  # fallback
            # Evento
            event_tag = match_soup.find("div", class_="event")
            event_name = event_tag.get_text(strip=True) if event_tag else "Unknown Event"

            matches_list.append({
                "team1": team1,
                "team2": team2,
                "time": match_time,
                "event": event_name,
                "url": match_url
            })
    return matches_list

# --- Buscar HTML principal ---
soup_main = fetch_html(HLTV_MATCHES_URL)
all_matches = []

if soup_main:
    all_matches.extend(extract_matches(soup_main))

# --- Filtrar partidas BR e adicionar ao calendar ---
added_count = 0
added_set = set()

for m in all_matches:
    team1 = m["team1"]
    team2 = m["team2"]
    match_time = m["time"]
    event_name = m["event"]
    url = m["url"]

    # Filtrar apenas times BR
    if not any(br.lower() in team1.lower() or br.lower() in team2.lower() for br in BRAZILIAN_TEAMS):
        print(f"⏭️ Ignorado: {team1} vs {team2} - nenhum time BR")
        continue

    # Ignorar partidas antigas
    if match_time < cutoff_time:
        print(f"⏭️ Ignorado: {team1} vs {team2} - partida antiga ({match_time})")
        continue

    # Evitar duplicatas
    key = f"{team1}-{team2}-{match_time.isoformat()}"
    if key in added_set:
        continue
    added_set.add(key)

    # Criar evento ICS
    e = Event()
    e.name = f"{team1} vs {team2} - {event_name}"
    e.begin = pytz.utc.localize(match_time).astimezone(BR_TZ)
    e.end = e.begin + timedelta(hours=2)
    e.description = f"Partida entre {team1} e {team2} no evento {event_name}"
    e.url = url

    cal.events.add(e)
    added_count += 1
    print(f"✅ Adicionado: {e.name} ({e.begin}) | URL: {e.url}")

# --- Salvar calendar.ics ---
try:
    with open("calendar.ics", "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())
    print(f"\n📌 {added_count} partidas BR salvas em calendar.ics")
except Exception as e:
    print(f"❌ Erro ao salvar calendar.ics: {e}")
