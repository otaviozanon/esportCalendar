import requests
from ics import Calendar
import re
from datetime import datetime, timezone

# --- Configurações ---
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo", "O PLANO", "Sharks", "RED Canids"]

def remove_emojis(text: str) -> str:
    return re.sub(r'[^\x00-\x7F]+', '', text)

now_utc = datetime.now(timezone.utc)
print(f"🕒 Agora (UTC): {now_utc}")

url = "https://calendar.hltv.events/events.ics"
print(f"🔹 Baixando ICS oficial do HLTV.Events: {url}")
response = requests.get(url)
response.raise_for_status()
print(f"🔹 Status code da requisição: {response.status_code}")

source_calendar = Calendar(response.text)
my_calendar = Calendar()

event_count = 0

for event in source_calendar.events:
    print(f"🔸 Evento encontrado: {remove_emojis(event.name)} - {event.begin}")

    # Garantir que begin tenha timezone
    event_time = event.begin
    if event_time.tzinfo is None:
        event_time = event_time.replace(tzinfo=timezone.utc)

    if any(team in event.name for team in BRAZILIAN_TEAMS) and event_time > now_utc:
        my_calendar.events.add(event)
        print(f"✅ Adicionado: {remove_emojis(event.name)} em {event_time}")
        event_count += 1

if event_count == 0:
    print("⚠️ Nenhum evento futuro de times brasileiros encontrado!")

with open("calendar.ics", "w", encoding="utf-8") as f:
    for line in my_calendar.serialize_iter():
        f.write(remove_emojis(line) + "\n")

print("🔹 calendar.ics gerado com sucesso!")
