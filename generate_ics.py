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

# --- Buscar partidas ---
print(f"🔍 Buscando partidas em {API_BASE}/matches ...")
try:
    resp = requests.get(f"{API_BASE}/matches", timeout=20)
    resp.raise_for_status()
    matches = resp.json()
    print(f"📦 {len(matches)} partidas recebidas")
except Exception as e:
    print(f"⚠️ Erro ao buscar partidas: {e}")
    matches = []

added_count = 0

for idx, match in enumerate(matches, start=1):
    try:
        match_id = match.get("id")
        team1 = match.get("team1", {}).get("name", "TBD")
        team2 = match.get("team2", {}).get("name", "TBD")
        event_name = match.get("event", {}).get("name", "Unknown Event")
        time_str = match.get("date")  # ISO ou timestamp
        url = match.get("url", f"https://www.hltv.org/matches/{match_id}")

        # Converter data/hora
        match_time = None
        if time_str:
            try:
                match_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            except Exception:
                try:
                    match_time = datetime.fromtimestamp(int(time_str) / 1000, tz=timezone.utc)
                except Exception:
                    continue
        if not match_time or match_time < cutoff_time:
            continue

        # Filtrar apenas partidas com times BR
        teams_lower = [team1.lower(), team2.lower()]
        has_br_team = any(br.lower() in t for br in BRAZILIAN_TEAMS for t in teams_lower)

        if not has_br_team:
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
        # Log apenas partidas BR adicionadas
        print(f"✅ Adicionado: {e.name} ({e.begin}) | URL: {e.url}")

    except Exception as e:
        print(f"⚠️ Erro ao processar partida {match.get('id')}: {e}")

# --- Salvar calendar.ics ---
try:
    with open("calendar.ics", "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())
    print(f"\n📌 {added_count} partidas BR salvas em calendar.ics")
except Exception as e:
    print(f"❌ Erro ao salvar calendar.ics: {e}")
