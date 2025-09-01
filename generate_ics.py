import asyncio
from hltv_async_api import Hltv
from ics import Calendar, Event
from datetime import datetime, timedelta
import pytz

# --- Configurações ---
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo", "O PLANO", "Sharks", "RED Canids"]
tz_brazil = pytz.timezone("America/Sao_Paulo")
today = datetime.now(tz_brazil).date()
date_range = [(today + timedelta(days=i)) for i in range(8)]  # hoje + 7 dias
calendar = Calendar()

async def fetch_matches():
    total_games = 0
    async with Hltv() as hltv:
        matches = await hltv.upcoming_matches()
        print(f"🔹 {len(matches)} partidas encontradas no HLTV")

        for idx, match in enumerate(matches, start=1):
            try:
                team1 = match['team1']['name']
                team2 = match['team2']['name']

                # Filtra só times brasileiros
                if not any(t in BRAZILIAN_TEAMS for t in [team1, team2]):
                    continue

                dt_utc = match['time']  # datetime em UTC
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
                print(f"⚠️ Erro ao processar partida {idx}: {repr(e)}")

    # Salvar arquivo .ics
    with open("calendar.ics", "w", encoding="utf-8") as f:
        f.writelines(calendar.serialize_iter())

    print(f"\n🔹 calendar.ics gerado com sucesso! Total de jogos adicionados: {total_games}")

if __name__ == "__main__":
    asyncio.run(fetch_matches())
