import os
import requests
from ics import Calendar
import re
from datetime import datetime, timezone, timedelta
import pytz
import warnings

# --- Suprimir FutureWarning específico do ics ---
warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    message=r"Behaviour of str\(Component\) will change in version 0.9.*"
)

# --- Configurações ---
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo", "Sharks", "RED Canids", "Legacy", "ODDIK"]
BR_TZ = pytz.timezone('America/Sao_Paulo')  # Fuso horário de Curitiba
MAX_AGE_DAYS = 30  # Jogos com mais de 30 dias serão removidos

def remove_emojis(text: str) -> str:
    return re.sub(r'[^\x00-\x7F]+', '', text)

now_utc = datetime.now(timezone.utc)
cutoff_time = now_utc - timedelta(days=MAX_AGE_DAYS)

print(f"🕒 Agora (UTC): {now_utc}")
print(f"🗑️ Jogos anteriores a {cutoff_time} serão removidos.")

# --- Baixar ICS oficial ---
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
            # 🔹 Remove linhas inválidas (comentários) antes de parsear
            cleaned_lines = [line for line in f.readlines() if not line.startswith(";")]
            
            # 🔹 Suporta múltiplos calendários
            calendars = Calendar.parse_multiple("".join(cleaned_lines))
            for cal in calendars:
                my_calendar.events.update(cal.events)

            print("🔹 calendar.ics antigo carregado (mantendo eventos anteriores).")
        except Exception as e:
            print(f"⚠️ Não foi possível carregar o calendário antigo: {e}")

# --- Limpar eventos antigos (>30 dias) ---
old_count = len(my_calendar.events)
my_calendar.events = {
    ev for ev in my_calendar.events
    if ev.begin and ev.begin > cutoff_time
}
print(f"🧹 Removidos {old_count - len(my_calendar.events)} eventos antigos.")

# --- Adicionar novos eventos ---
added_count = 0
for event in source_calendar.events:
    event_name_clean = remove_emojis(event.name).lower()
    event_time = event.begin

    if event_time.tzinfo is None:
        event_time = event_time.replace(tzinfo=timezone.utc)

    if any(team.lower() in event_name_clean for team in BRAZILIAN_TEAMS):
        # Evita duplicação pelo UID
        if not any(ev.uid == event.uid for ev in my_calendar.events):
            my_calendar.events.add(event)
            event_time_br = event_time.astimezone(BR_TZ)
            print(f"✅ Adicionado: {event_name_clean} em {event_time_br}")
            added_count += 1

print(f"📌 {added_count} novos eventos adicionados.")

# --- Salvar calendar.ics atualizado ---
with open("calendar.ics", "w", encoding="utf-8") as f:
    for line in my_calendar.serialize_iter():
        f.write(remove_emojis(line) + "\n")
    f.write(f"X-GENERATED-TIME:{datetime.now(timezone.utc).isoformat()}\n")

print("🔹 calendar.ics atualizado com eventos novos e antigos!")
