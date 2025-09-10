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
print(f"🗑️ Ignorando eventos com início antes de {cutoff_time}")

# --- Buscar eventos por palavra ---
query = "iem"  # pode trocar depois para algo genérico como "cs"
print(f"🔍 Buscando eventos com query='{query}'...")

try:
    resp = requests.get(f"{API_BASE}/events/search/{query}", timeout=15)
    resp.raise_for_status()
    data = resp.json()
    print(f"📦 {len(data.get('results', []))} eventos encontrados")
except Exception as e:
    print(f"❌ Erro ao buscar eventos: {e}")
    exit(1)

added_count = 0

for ev in data.get("results", []):
    event_id = ev.get("id")
    event_name = ev.get("name")
    print(f"\n➡️ Processando evento {event_name} (id={event_id})")

    # --- Buscar perfil detalhado ---
    try:
        profile_resp = requests.get(f"{API_BASE}/events/{event_id}/profile", timeout=15)
        profile_resp.raise_for_status()
        details = profile_resp.json().get("eventProfile", {})
        print(f"   ✅ Perfil carregado: {details.get('name')}")
    except Exception as e:
        print(f"   ❌ Erro ao buscar perfil do evento {event_id}: {e}")
        continue

    # --- Validar datas ---
    try:
        start = datetime.fromisoformat(details["startDate"])
        end = datetime.fromisoformat(details["endDate"])
        print(f"   📅 Datas: {start} → {end}")
    except Exception as e:
        print(f"   ⚠️ Erro ao converter datas do evento {event_id}: {e}")
        continue

    if start < cutoff_time:
        print("   ⏭️ Evento antigo, ignorado")
        continue

    # --- Verificar times brasileiros ---
    teams = [t["name"].lower() for t in details.get("teams", [])]
    if any(br.lower() in teams for br in BRAZILIAN_TEAMS):
        print(f"   🇧🇷 Time BR encontrado! {teams}")
    else:
        print("   ❌ Nenhum time BR, ignorando")
        continue

    # --- Criar evento ICS ---
    try:
        e = Event()
        e.name = details["name"]
        e.begin = start.astimezone(BR_TZ)
        e.end = end.astimezone(BR_TZ)
        e.description = f"{details['name']} - {details.get('prizePool', 'N/A')} em {details.get('location', 'Online')}"
        e.url = details.get("url", ev.get("url"))

        cal.events.add(e)
        added_count += 1
        print(f"   🎉 Adicionado ao calendário: {e.name} ({e.begin})")
    except Exception as e:
        print(f"   ⚠️ Erro ao criar evento ICS para {event_id}: {e}")

# --- Salvar calendar.ics ---
try:
    with open("calendar.ics", "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())
    print(f"\n📌 {added_count} eventos salvos em calendar.ics")
except Exception as e:
    print(f"❌ Erro ao salvar calendar.ics: {e}")
