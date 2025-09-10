import requests
from requests.exceptions import RequestException
from ics import Calendar, Event
from datetime import datetime, timezone, timedelta
import pytz
import time

API_BASE = "https://hltv-json-api.fly.dev"
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo",
                   "Sharks", "RED Canids", "Legacy", "ODDIK"]
BR_TZ = pytz.timezone("America/Sao_Paulo")
MAX_AGE_DAYS = 30
RETRIES = 3
RETRY_DELAY = 5  # segundos

cal = Calendar()
now_utc = datetime.now(timezone.utc)
cutoff_time = now_utc - timedelta(days=MAX_AGE_DAYS)

print(f"🕒 Agora (UTC): {now_utc}")
print(f"🗑️ Ignorando partidas com início antes de {cutoff_time}")

def get_json_with_retries(url):
    for attempt in range(1, RETRIES + 1):
        try:
            resp = requests.get(url, timeout=20)
            resp.raise_for_status()
            return resp.json()
        except RequestException as e:
            print(f"⚠️ Tentativa {attempt} falhou para {url}: {e}")
            if attempt < RETRIES:
                print(f"   ⏳ Aguardando {RETRY_DELAY}s antes da próxima tentativa...")
                time.sleep(RETRY_DELAY)
            else:
                print(f"❌ Falha definitiva ao acessar {url}")
    return None

# --- Buscar eventos ---
events_data = get_json_with_retries(f"{API_BASE}/matches")
events = events_data.get("results", []) if events_data else []
print(f"📦 {len(events)} eventos recebidos")

added_count = 0

for idx, event in enumerate(events, start=1):
    event_name = event.get("name", "Unknown Event")
    matches_url = event.get("eventMatchesUrl")
    print(f"\n🔹 Evento #{idx}: {event_name}")
    if not matches_url:
        print(f"   ⚠️ Sem matches_url, ignorando evento")
        continue

    matches_data = get_json_with_retries(matches_url)
    matches = matches_data.get("results", []) if matches_data else []
    if not matches:
        print(f"   ⚠️ Nenhuma partida encontrada para {event_name}")
        continue

    for match_idx, match in enumerate(matches, start=1):
        try:
            match_id = match.get("id")
            team1 = match.get("team1", {}).get("name", "TBD")
            team2 = match.get("team2", {}).get("name", "TBD")
            time_str = match.get("date")
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
                        print(f"   ⚠️ Não foi possível converter data da partida {match_id}")
            if not match_time:
                print(f"   ⏭️ Ignorando partida {match_id}: data inválida")
                continue

            if match_time < cutoff_time:
                print(f"   ⏭️ Ignorando partida antiga {team1} vs {team2} ({match_time})")
                continue

            # Filtrar apenas partidas BR
            teams_lower = [team1.lower(), team2.lower()]
            has_br_team = any(br.lower() in t for br in BRAZILIAN_TEAMS for t in teams_lower)
            if not has_br_team:
                print(f"   ⏭️ Ignorando partida {team1} vs {team2}: nenhum time BR")
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
            print(f"⚠️ Erro ao processar partida {match.get('id')}: {e}")

# --- Salvar calendar.ics ---
try:
    with open("calendar.ics", "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())
    print(f"\n📌 {added_count} partidas BR salvas em calendar.ics")
except Exception as e:
    print(f"❌ Erro ao salvar calendar.ics: {e}")
