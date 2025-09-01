import requests
from ics import Calendar
import re
from datetime import datetime, timezone

# --- Configurações ---
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo", "O PLANO", "Sharks", "RED Canids"]

# Função para remover emojis e caracteres especiais
def remove_emojis(text: str) -> str:
    return re.sub(r'[^\x00-\x7F]+', '', text)

# Data/hora atual em UTC
now_utc = datetime.now(timezone.utc)

# Baixar ICS oficial do HLTV.Events
url = "https://calendar.hltv.events/events.ics"
print(f"🔹 Baixando ICS oficial do HLTV.Events: {url}")
response = requests.get(url)
response.raise_for_status()
print(f"🔹 Status code da requisição: {response.status_code}")

source_calendar = Calendar(response.text)
my_calendar = Calendar()

# Filtrar eventos de times brasileiros **futuros**
for event in source_calendar.events:
    if any(team in event.name for team in BRAZILIAN_TEAMS) and event.begin > now_utc:
        my_calendar.events.add(event)
        print(f"✅ Adicionado: {remove_emojis(event.name)} em {event.begin}")

# Salvar ICS filtrado sem emojis
with open("calendar.ics", "w", encoding="utf-8") as f:
    for line in my_calendar.serialize_iter():
        f.write(remove_emojis(line) + "\n")

print("🔹 calendar.ics gerado com sucesso!")
