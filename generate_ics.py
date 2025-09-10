import os
import requests
from ics import Calendar, Event
from datetime import datetime, timezone, timedelta
import pytz

# --- Configurações ---
API_BASE = "https://hltv-json-api.fly.dev"
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo", "Sharks", "RED Canids", "Legacy", "ODDIK"]
BR_TZ = pytz.timezone('America/Sao_Paulo')
MAX_AGE_DAYS = 30  # Jogos com mais de 30 dias serão removidos

# --- Inicializa calendário ---
cal = Calendar()

# --- Buscar eventos (campeonatos) ---
resp = requests.get(f"{API_BASE}/events")
resp.raise_for_status()
events = resp.json()

now_utc = datetime.now(timezone.utc)
cutoff_time = now_utc - timedelta(days=MAX_AGE_DAYS)

added_count = 0

for ev in events:
    event_id = ev["id"]

    # Baixa o perfil completo do evento
    profile_resp = requests.get(f"{API_BASE}/events/{event_id}/profile")
    profile_resp.raise_for_status()
    details = profile_resp.json()["eventProfile"]

    # Converte datas
    start = datetime.fromisoformat(details["startDate"])
    end = datetime.fromisoformat(details["endDate"])

    # Ignorar eventos antigos
    if start < cutoff_time:
        continue

    # Checar se há time BR
    teams = [t["name"].lower() for t in details.get("teams", [])]
    if not any(br.lower() in teams for br in BRAZILIAN_TEAMS):
        continue

    # Criar evento ICS
    e = Event()
    e.name = details["name"]
    e.begin = start.astimezone(BR_TZ)
    e.end = end.astimezone(BR_TZ)
    e.description = f"{details['name']} - {details.get('prizePool', 'N/A')} em {details.get('location', 'Online')}"
    e.url = details.get("url", f"https://www.hltv.org/events/{event_id}")

    cal.events.add(e)
    added_count += 1
    print(f"✅ Adicionado: {e.name} ({e.begin})")

# --- Salvar calendar.ics ---
with open("calendar.ics", "w", encoding="utf-8") as f:
    f.writelines(cal.serialize_iter())

print(f"📌 {added_count} eventos salvos no calendar.ics")
