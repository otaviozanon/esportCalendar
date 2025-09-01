import requests
from bs4 import BeautifulSoup
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

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
}

print(f"🔹 Buscando jogos de {date_range[0]} até {date_range[-1]}")

for d in date_range:
    url = f"https://www.hltv.org/matches?selectedDate={d.strftime('%Y-%m-%d')}"
    print(f"\n🔹 Acessando {url}")

    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            print(f"⚠️ Falha ao acessar {url}, status code: {r.status_code}")
            continue

        soup = BeautifulSoup(r.text, "html.parser")
        matches = soup.select("div.match-day div.upcomingMatch")
        print(f"🔹 Total de matches encontrados: {len(matches)}")

        for idx, m in enumerate(matches, start=1):
            try:
                teams = [t.text.strip() for t in m.select("div.matchTeamName span")]
                if len(teams) < 2:
                    print(f"⚠️ Match {idx} ignorado: menos de 2 times encontrados")
                    continue
                team1, team2 = teams[0], teams[1]
                print(f"🔹 Match {idx} detectado: {team1} vs {team2}")

                # Filtra só times brasileiros
                if not any(team in BRAZILIAN_TEAMS for team in [team1, team2]):
                    print(f"⚠️ Match {idx} ignorado: nenhum time brasileiro")
                    continue

                # Horário
                time_element = m.select_one("div.matchTime")
                if not time_element:
                    print(f"⚠️ Match {idx} ignorado: horário não encontrado")
                    continue

                match_time_text = time_element.text.strip()  # exemplo: "12:00"
                hour, minute = map(int, match_time_text.split(":"))
                dt_utc = datetime.combine(d, datetime.min.time()) + timedelta(hours=hour, minutes=minute)
                dt_utc = pytz.utc.localize(dt_utc)
                dt_brazil = dt_utc.astimezone(tz_brazil)
                print(f"🔹 Horário convertido para Brasília: {dt_brazil.strftime('%Y-%m-%d %H:%M')}")

                # Criar evento
                event = Event()
                event.name = f"{team1} vs {team2}"
                event.begin = dt_brazil
                event.end = dt_brazil + timedelta(hours=2)
                event.location = "HLTV.org"
                calendar.events.add(event)
                total_games += 1
                print(f"✅ Jogo adicionado: {team1} vs {team2} às {dt_brazil.strftime('%H:%M')}")

            except Exception as e:
                print(f"⚠️ Erro ao processar match {idx}: {repr(e)}")

    except Exception as e:
        print(f"⚠️ Erro geral ao acessar {url}: {repr(e)}")

# Salvar arquivo .ics
with open("calendar.ics", "w", encoding="utf-8") as f:
    f.writelines(calendar.serialize_iter())

print(f"\n🔹 calendar.ics gerado com sucesso! Total de jogos adicionados: {total_games}")
