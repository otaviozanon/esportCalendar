import requests
from ics import Calendar

# --- Configurações ---
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo", "O PLANO", "Sharks", "RED Canids"]

# Baixar ICS oficial do HLTV.Events
url = "https://calendar.hltv.events/events.ics"
print(f"🔹 Baixando ICS oficial do HLTV.Events: {url}")
response = requests.get(url)
response.raise_for_status()
print(f"🔹 Status code da requisição: {response.status_code}")

source_calendar = Calendar(response.text)
my_calendar = Calendar()

# Filtrar eventos de times brasileiros
for event in source_calendar.events:
    if any(team in event.name for team in BRAZILIAN_TEAMS):
        my_calendar.events.add(event)
        # Forçar log em UTF-8
        print("✅ Adicionado: {}".format(event.name.encode("utf-8", errors="ignore").decode("utf-8")), 
              "em", event.begin)

# Salvar ICS filtrado com UTF-8 explícito
with open("calendar.ics", "w", encoding="utf-8") as f:
    f.writelines(my_calendar.serialize_iter())

print("🔹 calendar.ics gerado com sucesso!")
