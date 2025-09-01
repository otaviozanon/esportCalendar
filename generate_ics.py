import requests
from ics import Calendar, Event

# --- Configurações ---
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo", "O PLANO", "Sharks", "RED Canids"]

# Baixar ICS oficial do HLTV.Events
url = "https://calendar.hltv.events/events.ics"
response = requests.get(url)
response.raise_for_status()

source_calendar = Calendar(response.text)
my_calendar = Calendar()

# Filtrar eventos de times brasileiros
for event in source_calendar.events:
    if any(team in event.name for team in BRAZILIAN_TEAMS):
        my_calendar.events.add(event)
        print(f"✅ Adicionado: {event.name} em {event.begin}")

# Salvar ICS filtrado
with open("calendar.ics", "w", encoding="utf-8") as f:
    f.writelines(my_calendar.serialize_iter())

print("🔹 calendar.ics gerado com sucesso!")
