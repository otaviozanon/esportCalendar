import requests
from ics import Calendar
import unicodedata

# --- Configurações ---
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo", "O PLANO", "Sharks", "RED Canids"]

# Função para normalizar texto, removendo caracteres problemáticos do terminal
def clean_text(text: str) -> str:
    # Normaliza Unicode (NFC) e ignora caracteres inválidos
    return unicodedata.normalize("NFC", text)

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
        print(f"✅ Adicionado: {clean_text(event.name)} em {event.begin}")

# Salvar ICS filtrado com UTF-8 explícito
with open("calendar.ics", "w", encoding="utf-8") as f:
    for line in my_calendar.serialize_iter():
        f.write(clean_text(line) + "\n")

print("🔹 calendar.ics gerado com sucesso!")
