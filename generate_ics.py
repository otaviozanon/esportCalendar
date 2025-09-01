import os
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

source_calendar = Calendar(response.text)

# --- Carregar calendar.ics antigo, se existir ---
my_calendar = Calendar()
if os.path.exists("calendar.ics"):
    with open("calendar.ics", "r", encoding="utf-8") as f:
        try:
            my_calendar = Calendar(f.read())
            print("🔹 calendar.ics antigo carregado (mantendo eventos anteriores).")
        except Exception as e:
            print(f"⚠️ Não foi possível carregar o calendário antigo: {e}")

event_count = 0

for event in source_calendar.events:
    event_name_clean = remove_emojis(event.name).lower()
    event_time = event.begin

    if event_time.tzinfo is None:
        event_time = event_time.replace(tzinfo=timezone.utc)

    if any(team.lower() in event_name_clean for team in BRAZILIAN_TEAMS):
        # ✅ Sempre mantém os jogos dos BRs (passados e futuros)
        if event not in my_calendar.events:
            my_calendar.events.add(event)
            event_time_br = event_time.astimezone(BR_TZ)
            print(f"✅ Adicionado: {event_name_clean} em {event_time_br}")
            event_count += 1

if event_count == 0:
    print("⚠️ Nenhum evento novo encontrado (mas jogos antigos foram mantidos).")

with open("calendar.ics", "w", encoding="utf-8") as f:
    for line in my_calendar.serialize_iter():
        f.write(remove_emojis(line) + "\n")
    f.write(f"; Gerado em {datetime.now(timezone.utc).isoformat()}\n")

print("🔹 calendar.ics atualizado com eventos antigos + novos!")
