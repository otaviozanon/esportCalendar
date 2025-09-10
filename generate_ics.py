import requests
from ics import Calendar, Event
from datetime import datetime, timezone, timedelta
import pytz

API_BASE = "https://hltv-json-api.fly.dev"
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo",
                   "Sharks", "RED Canids", "Legacy", "ODDIK"]
BR_TZ = pytz.timezone("America/Sao_Paulo")
MAX_AGE_DAYS = 30

cal = Calendar()
now_utc = datetime.now(timezone.utc)
cutoff_time = now_utc - timedelta(days=MAX_AGE_DAYS)

print(f"🕒 Agora (UTC): {now_utc}")
print(f"🗑️ Ignorando partidas com início antes de {cutoff_time}")

def fetch_json(url):
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"❌ Erro ao acessar {url}: {e}")
        return None

# --- Buscar eventos ---
print(f"🔍 Buscando eventos...")
events = fetch_json(f"{API_BASE}/events/search/all")  # "all" para pegar todos
if not events:
    events = []

print(f"📦 {len(events)} eventos encontrados")

added_count = 0

for event in events:
    try:
        event_id = event.get("id")
        event_name = event.get("name", "Unknown Event")
        print(f"\n🔹 Processando evento: {event_name} (ID: {event_id})")

        event_profile = fetch_json(f"{API_BASE}/events/{event_id}/profile")
        if not event_profile:
            continue

        matches = event_profile.get("matches", [])
        print(f"📦 {len(matches)} partidas encontradas no evento {event_name}")

        for match in matches:
            try:
                team1 = match.get("team1", {}).get("name", "TBD")
                team2 = match.get("team2", {}).get("name", "TBD")
                time_str = match.get("date")
                url = match.get("url", f"https://www.hltv.org/matches/{match.get('id')}")

                # Converter data/hora
                try:
                    match_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                except Exception:
                    match_time = datetime.fromtimestamp(int(time_str) / 1000, tz=timezone.utc)

                if match_time < cutoff_time:
                    print(f"⏭️ Ignorado: {team1} vs {team2} - partida antiga ({match_time})")
                    continue

                # Filtrar times BR
                teams_lower = [team1.lower(), team2.lower()]
                if not any(br.lower() in t for br in BRAZILIAN_TEAMS for t in teams_lower):
                    print(f"⏭️ Ignorado: {team1} vs {team2} - nenhum time BR")
                    continue

                # Criar evento ICS
                e = Event()
                e.name = f"{team1} vs {team2} - {event_name}"
                e.begin = match_time.astimezone(BR_TZ)
                e.end = e.begin + timedelta(hours=2)
                e.description = f"Partida entre {team1} e {team2} no evento {event_name}"
                e.url = url

                cal.events.add(e)
                added_count += 1
                print(f"✅ Adicionado: {e.name} ({e.begin}) | URL: {e.url}")

            except Exception as e:
                print(f"⚠️ Erro ao processar partida: {e}")

    except Exception as e:
        print(f"⚠️ Erro ao processar evento {event.get('id')}: {e}")

# --- Salvar calendar.ics ---
try:
    with open("calendar.ics", "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())
    print(f"\n📌 {added_count} partidas BR salvas em calendar.ics")
except Exception as e:
    print(f"❌ Erro ao salvar calendar.ics: {e}")
