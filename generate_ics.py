import requests
from bs4 import BeautifulSoup
from ics import Calendar, Event
from datetime import datetime, timedelta
import pytz

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

def fetch_hltv_html(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        print(f"❌ Erro ao acessar HLTV: {e}")
        return None

def extract_matches(soup):
    matches_list = []

    # Encontrar blocos de partidas
    matches_divs = soup.find_all("div", class_="upcomingMatch")
    print(f"📦 Encontrados {len(matches_divs)} blocos de partidas no HTML")
    
    for idx, match_div in enumerate(matches_divs, start=1):
        try:
            # Extrair times
            team1_tag = match_div.find(lambda tag: tag.name == "div" and "team1" in tag.get("class", []))
            team2_tag = match_div.find(lambda tag: tag.name == "div" and "team2" in tag.get("class", []))
            if not team1_tag or not team2_tag:
                print(f"⚠️ Bloco {idx}: times não encontrados")
                continue
            team1 = team1_tag.get_text(strip=True)
            team2 = team2_tag.get_text(strip=True)

            # Timestamp
            time_tag = match_div.find(lambda tag: tag.name == "div" and "matchTime" in tag.get("class", []))
            if not time_tag or not time_tag.has_attr("data-unix"):
                print(f"⚠️ Bloco {idx}: horário não encontrado")
                continue
            match_time = datetime.utcfromtimestamp(int(time_tag["data-unix"])/1000)

            # Evento
            event_tag = match_div.find(lambda tag: tag.name == "div" and "event" in tag.get("class", []))
            event_name = event_tag.get_text(strip=True) if event_tag else "Unknown Event"

            # URL
            url_tag = match_div.find("a", href=True)
            url = "https://www.hltv.org" + url_tag["href"] if url_tag else ""

            matches_list.append({
                "team1": team1,
                "team2": team2,
                "time": match_time,
                "event": event_name,
                "url": url
            })
            print(f"🔍 Bloco {idx}: {team1} vs {team2} - {event_name} | {match_time} | URL: {url}")

        except Exception as e:
            print(f"⚠️ Erro ao processar bloco {idx}: {e}")

    return matches_list

# --- Buscar HTML principal ---
soup = fetch_hltv_html(HLTV_MATCHES_URL)
all_matches = extract_matches(soup) if soup else []

# --- Adicionar partidas BR ao calendar ---
added_count = 0
added_set = set()  # evita duplicatas

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
