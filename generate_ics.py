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
search_data = fetch_json(f"{API_BASE}/events/search/all")
events = search_data.get("results", []) if search_data else []
print(f"📦 {len(events)} eventos encontrados")

added_count = 0

for event_summary in events:
    try:
        event_id = event_summary.get("id")
        event_name = event_summary.get("name", "Unknown Event")
        event_url = event_summary.get("eventMatchesUrl", "#")
        print(f"\n🔹 Processando evento: {event_name} (ID: {event_id}) | URL: {event_url}")

        profile_data = fetch_json(f"{API_BASE}/events/{event_id}/profile")
        if not profile_data:
            continue

        event_profile = profile_data.get("eventProfile", {})
        teams = event_profile.get("teams", [])
        evps = event_profile.get("evps", [])

        # Mapear nomes de times
        event_team_names = [team.get("names", [team.get("name", "")])[0] for team in teams]

        # Filtrar times BR no evento
        br_teams_in_event = [t for t in event_team_names if any(br.lower() in t.lower() for br in BRAZILIAN_TEAMS)]
        if not br_teams_in_event:
            print(f"⏭️ Nenhum time BR neste evento")
            continue

        # Criar evento ICS por partida/evp
        for evp in evps:
            try:
                match_id = evp.get("id")
                match_name = evp.get("nickname", f"Partida {match_id}")
                match_time_str = evp.get("eventStats")  # Pode precisar ajustar se houver datetime real
                match_url = evp.get("eventStats", event_url)  # fallback

                # Tentar converter data/hora se disponível
                try:
                    match_time = datetime.fromisoformat(match_time_str.replace("Z", "+00:00"))
                except Exception:
                    match_time = now_utc  # fallback: agora

                if match_time < cutoff_time:
                    print(f"⏭️ Ignorado: {match_name} - partida antiga ({match_time})")
                    continue

                # Criar evento ICS
                e = Event()
                e.name = f"{match_name} - {event_name}"
                e.begin = match_time.astimezone(BR_TZ)
                e.end = e.begin + timedelta(hours=2)
                e.description = f"Evento {event_name} | Times BR: {', '.join(br_teams_in_event)}"
                e.url = match_url

                cal.events.add(e)
                added_count += 1
                print(f"✅ Adicionado: {e.name} ({e.begin}) | URL: {e.url}")

            except Exception as e:
                print(f"⚠️ Erro ao processar partida/evp: {e}")

    except Exception as e:
        print(f"⚠️ Erro ao processar evento {event_summary}: {e}")

# --- Salvar calendar.ics ---
try:
    with open("calendar.ics", "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())
    print(f"\n📌 {added_count} partidas BR salvas em calendar.ics")
except Exception as e:
    print(f"❌ Erro ao salvar calendar.ics: {e}")
