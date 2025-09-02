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
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo", "O PLANO", "Sharks", "RED Canids"]
BR_TZ = pytz.timezone('America/Sao_Paulo')  # Fuso horário de Curitiba
MAX_AGE_DAYS = 15  # ⚡ Agora removemos eventos com mais de 15 dias
SOURCE_ICS_URL = "https://calendar.hltv.events/events.ics"
OUTPUT_ICS_FILE = "calendar.ics"

# --- Função para remover emojis e caracteres estranhos ---
def remove_emojis(text: str) -> str:
    return re.sub(r'[^\x00-\x7F]+', '', text)

# --- Datas de corte ---
now_utc = datetime.now(timezone.utc)
cutoff_time = now_utc - timedelta(days=MAX_AGE_DAYS)
print(f"🕒 Agora (UTC): {now_utc}")
print(f"🗑️ Jogos anteriores a {cutoff_time} serão removidos.")

# --- Baixar ICS oficial ---
print(f"🔹 Baixando ICS oficial do HLTV.Events: {SOURCE_ICS_URL}")
response = requests.get(SOURCE_ICS_URL)
response.raise_for_status()
source_calendar = Calendar(response.text)

# --- Carregar calendar.ics antigo, se existir ---
my_calendar = Calendar()
if os.path.exists(OUTPUT_ICS_FILE):
    with open(OUTPUT_ICS_FILE, "r", encoding="utf-8") as f:
        try:
            cleaned_lines = [line for line in f.readlines() if not line.startswith(";")]
            calendars = Calendar.parse_multiple("".join(cleaned_lines))
            for cal in calendars:
                my_calendar.events.update(cal.events)
            print("🔹 calendar.ics antigo carregado (mantendo eventos anteriores).")
        except Exception as e:
            print(f"⚠️ Não foi possível carregar o calendário antigo: {e}")

# --- Limpar eventos antigos (>15 dias) ---
old_count = len(my_calendar.events)
my_calendar.events = {
    ev for ev in my_calendar.events
    if ev.begin and ev.begin > cutoff_time
}
print(f"🧹 Removidos {old_count - len(my_calendar.events)} eventos antigos.")

# --- Adicionar novos eventos (somente equipes brasileiras + TBD) ---
added_count = 0
for event in source_calendar.events:
    event_name_clean = remove_emojis(event.name).lower()
    event_time = event.begin

    if event_time.tzinfo is None:
        event_time = event_time.replace(tzinfo=timezone.utc)

    # Verifica equipe brasileira
    has_brazilian_team = any(team.lower() in event_name_clean for team in BRAZILIAN_TEAMS)
    
    # Verifica se é TBD
    is_tbd = "tbd" in event_name_clean or "winner" in event_name_clean or "?" in event_name_clean

    if has_brazilian_team and is_tbd:
        # Evita duplicados pelo UID
        if not any(ev.uid == event.uid for ev in my_calendar.events):
            my_calendar.events.add(event)
            event_time_br = event_time.astimezone(BR_TZ)
            print(f"✅ Adicionado (TBD): {event.name} em {event_time_br}")
            added_count += 1

print(f"📌 {added_count} novos eventos TBD adicionados.")

# --- Salvar calendar.ics atualizado ---
with open(OUTPUT_ICS_FILE, "w", encoding="utf-8") as f:
    for line in my_calendar.serialize_iter():
        f.write(remove_emojis(line) + "\n")
    f.write(f"X-GENERATED-TIME:{datetime.now(timezone.utc).isoformat()}\n")

print("🔹 calendar.ics atualizado com eventos novos e antigos!")
