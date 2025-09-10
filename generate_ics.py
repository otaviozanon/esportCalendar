import requests
from ics import Calendar, Event
from datetime import datetime, timedelta

API_BASE = "https://exemplo-api.com"  # troque para sua API real
OUTPUT_FILE = "calendar.ics"

def fetch_matches():
    print(f"🔍 Buscando partidas em {API_BASE}/matches ...")
    try:
        resp = requests.get(f"{API_BASE}/matches", timeout=20)
        resp.raise_for_status()
        matches = resp.json()
        print(f"📦 {len(matches)} partidas recebidas")
        return matches
    except Exception as e:
        print(f"⚠️ Erro ao buscar partidas: {e}")
        return []  # continua sem cair

def generate_ics(matches):
    cal = Calendar()
    added_count = 0

    for match in matches:
        try:
            e = Event()
            e.name = match.get("name", "Partida")
            start_time = match.get("start_time")  # espera ISO 8601
            if start_time:
                e.begin = datetime.fromisoformat(start_time)
                e.duration = timedelta(hours=1)  # default 1h se não especificado
                cal.events.add(e)
                added_count += 1
        except Exception as e:
            print(f"⚠️ Erro ao adicionar partida: {e}")
            continue

    with open(OUTPUT_FILE, "w") as f:
        f.writelines(cal)
    
    print(f"\n📌 {added_count} partidas salvas em {OUTPUT_FILE}")

def main():
    matches = fetch_matches()
    generate_ics(matches)

if __name__ == "__main__":
    main()
