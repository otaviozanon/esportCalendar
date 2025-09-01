from hltv import HLTV
from ics import Calendar, Event
from datetime import datetime, timedelta
import pytz

# --- Configurações ---
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo", "O PLANO", "Sharks", "RED Canids"]
tz_brazil = pytz.timezone("America/Sao_Paulo")
today = datetime.now(tz_brazil).date()
date_range = [(today + timedelta(days=i)) for i in range(8)]  # hoje + 7 dias
calendar = Calendar()
total_games = 0

print(f"🔹 Buscando jogos de {date_range[0]} até {date_range[-1]}")

# --- Buscar partidas ---
hltv = HLTV()

for d in date_range:
    try:
        matches = hltv.matches_on_date(d)  # pega todos os jogos do dia
        print(f"🔹 {len(matches)} matches encontrados em {d}")
    except Exception as e:
        print(f"⚠️ Erro ao buscar partidas em {d}: {repr(e)}")
        continue

    for match in matches:
        try:
            team1 = match['team1']['name']
            team2 = match['team2']['name']

            if not any(t in BRAZILIAN_TEAMS for t in [team1, team2]):
                continue

            dt_utc = match['time']  # já vem como datetime em UTC
            dt_brazil = dt_utc.astimezone(tz_brazil)

            event = Event()
            event.name = f"{team1} vs {team2}"
            event.begin = dt_brazil
            event.end = dt_brazil + timedelta(hours=2)
            event.location = "HLTV.org"

            calendar.events.add(event)
            total_games += 1
            print(f"✅ Jogo adicionado: {team1} vs {team2} às {dt_brazil.strftime('%H:%M')}")
        except Exception as e:
            print(f"⚠️ Erro ao processar partida: {repr(e)}")

# Salvar ICS
with open("calendar.ics", "w", encoding="utf-8") as f:
    f.writelines(calendar.serialize_iter())

print(f"\n🔹 calendar.ics gerado com sucesso! Total de jogos adicionados: {total_games}")
