import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
from ics import Calendar, Event
from ics.alarm import DisplayAlarm
import hashlib
import json
import re

# Times principais
BRAZILIAN_TEAMS = [
    "FURIA", "paiN", "MIBR", "Imperial", "Fluxo",
    "RED Canids", "Legacy", "ODDIK", "Imperial Esports"
]

BRAZILIAN_TEAMS_EXCLUSIONS = [
    "Imperial.A", "Imperial Fe", "MIBR.A", "paiN.A", "ODDIK.A",
    "Imperial Academy", "Imperial.Acd", "Imperial Female",
    "Furia Academy", "Furia.A", "Pain Academy", "Mibr Academy",
    "Legacy Academy", "ODDIK Academy", "RED Canids Academy", 
    "Fluxo Academy"
]

TIPSGG_URL = "https://tips.gg/csgo/matches/"
CALENDAR_FILENAME = "calendar.ics"
BR_TZ = pytz.timezone("America/Sao_Paulo")

def normalize_team(name):
    return name.lower().strip() if name else ""

NORMALIZED_BRAZILIAN_TEAMS = {normalize_team(t) for t in BRAZILIAN_TEAMS}
NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS = {normalize_team(t) for t in BRAZILIAN_TEAMS_EXCLUSIONS}

cal = Calendar()
added_count = 0

print("🔍 Baixando página:", TIPSGG_URL)

try:
    response = requests.get(TIPSGG_URL, timeout=10)
    print("📡 HTTP Status:", response.status_code)

    soup = BeautifulSoup(response.text, "html.parser")

    scripts = soup.find_all("script", {"type": "application/ld+json"})
    print(f"📦 Encontrados {len(scripts)} scripts JSON-LD")

    now_br = datetime.now(BR_TZ)

    for script_idx, script_tag in enumerate(scripts, start=1):
        try:
            raw_json = script_tag.string.strip()
            print(f"\n────────── JSON-LD #{script_idx} ──────────")
            print(raw_json)

            data = json.loads(raw_json)

            if data.get("@type") != "SportsEvent":
                print("⏭️ Ignorando – não é SportsEvent")
                continue

            # Times
            competitors = data.get("competitor", [])
            if len(competitors) < 2:
                print("❌ JSON sem 2 competidores!")
                continue

            team1_raw = competitors[0].get("name", "")
            team2_raw = competitors[1].get("name", "")
            print("👥 Times:", team1_raw, "vs", team2_raw)

            nt1 = normalize_team(team1_raw)
            nt2 = normalize_team(team2_raw)

            is_br = (
                (nt1 in NORMALIZED_BRAZILIAN_TEAMS and nt1 not in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS) or
                (nt2 in NORMALIZED_BRAZILIAN_TEAMS and nt2 not in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS)
            )

            print("🇧🇷 É time BR?", is_br)

            if not is_br:
                print("⏭️ Ignorando – não envolve time BR principal")
                continue

            # Horário
            start_raw = data.get("startDate")
            print("⏰ startDate bruto:", start_raw)

            match_time_br = datetime.fromisoformat(start_raw).astimezone(BR_TZ)
            print("⏰ Convertido para BRT:", match_time_br)

            if match_time_br < now_br:
                print("⏭️ Ignorando – partida já passou")
                continue

            # Formato (BO1 / BO3)
            event_description_raw = data.get("description", "")
            mf = re.search(r"(BO\d+)", event_description_raw, re.IGNORECASE)
            match_format = mf.group(1).upper() if mf else "BoX"

            print("🎛 Formato:", match_format)

            organizer = data.get("organizer", {})
            organizer_name = organizer.get("name", "Desconhecido")

            match_url = "https://tips.gg" + data.get("url", "")

            event_summary = f"{team1_raw} vs {team2_raw}"
            event_description = (
                f"🏆- {match_format}\n"
                f"📍{organizer_name}\n"
                f"🌐{match_url}"
            )

            event_uid = hashlib.sha1(
                (event_summary + start_raw).encode("utf-8")
            ).hexdigest()

            print("🆔 UID:", event_uid)

            e = Event()
            e.name = event_summary
            e.begin = match_time_br
            e.duration = timedelta(hours=2)
            e.description = event_description
            e.uid = event_uid
            e.alarms.append(DisplayAlarm(trigger=timedelta(minutes=-15)))

            cal.events.add(e)
            added_count += 1

            print("✅ Adicionado ao calendário!")

        except Exception as err:
            print("❌ Erro ao processar JSON-LD:", err)

except Exception as err:
    print("❌ Erro geral:", err)

print("\n💾 Salvando arquivo:", CALENDAR_FILENAME)
with open(CALENDAR_FILENAME, "w", encoding="utf-8") as f:
    f.writelines(cal.serialize_iter())

print(f"📌 Total de partidas adicionadas: {added_count}")
