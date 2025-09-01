import requests
from ics import Calendar
import re
from datetime import datetime, timezone
import pytz

# --- Configurações ---
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo", "O PLANO", "Sharks", "RED Canids"]
BR_TZ = pytz.timezone('America/Sao_Paulo')  # Fuso horário de Curitiba

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
    event_name_clean = remove_emojis(event.name).lower()
    print(f"🔸 Evento encontrado: {event_name_clean} - {event.begin}")

    # Garantir que begin tenha timezone
    event_time = event.begin
    if event_time.tzinfo is None:
        event_time = event_time.replace(tzinfo=timezone.utc)

    # Comparar no mesmo fuso (UTC)
    if any(team.lower() in event_name_clean for team in BRAZILIAN_TEAMS) and event_time > now_utc:
        # Adicionar o evento
        my_calendar.events.add(event)
        # Mostrar o horário convertido para horário de Brasília (Curitiba)
        event_time_br = event_time.astimezone(BR_TZ)
        print(f"✅ Adicionado: {event_name_clean} em {event_time_br}")
        event_count += 1

if event_count == 0:
    print("⚠️ Nenhum evento futuro de times brasileiros encontrado!")

with open("calendar.ics", "w", encoding="utf-8") as f:
    for line in my_calendar.serialize_iter():
        f.write(remove_emojis(line) + "\n")
    # Adiciona timestamp para forçar mudança no arquivo
    f.write(f"; Gerado em {datetime.now(timezone.utc).isoformat()}\n")

print("🔹 calendar.ics gerado com sucesso!")
