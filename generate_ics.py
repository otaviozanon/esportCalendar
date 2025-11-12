import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
from ics import Calendar, Event, Alarm
import hashlib

# -------------------- Configurações Globais --------------------
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo",
                   "RED Canids", "Legacy", "ODDIK"]
BRAZILIAN_TEAMS_EXCLUSIONS = ["Imperial.A", "Imperial Fe", "MIBR.A" "paiN.A"]
URL_LIQUIPEDIA = "https://liquipedia.net/counterstrike/Liquipedia:Matches"
BR_TZ = pytz.timezone("America/Sao_Paulo")

cal = Calendar()
added_count = 0
unique_matches = set()

print(f"🔍 Buscando partidas em {URL_LIQUIPEDIA}...")

try:
    response = requests.get(URL_LIQUIPEDIA, timeout=10)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'lxml')
    
    MATCH_TABLE_CLASS = 'wikitable wikitable-striped infobox_matches_content'
    match_tables = soup.find_all('table', class_=MATCH_TABLE_CLASS)
    
    print(f"✅ Encontrados {len(match_tables)} blocos de partidas individuais com a classe '{MATCH_TABLE_CLASS}'.")
    
    if not match_tables:
        print("⚠️ Nenhum bloco de partida encontrado. Verifique se a classe da tabela mudou.")
        exit()
    
    for match_idx, match_table in enumerate(match_tables, 1):
        team1, team2, event_name, match_url = 'N/A', 'N/A', 'N/A', URL_LIQUIPEDIA
        match_format = 'Partida'
        
        try:
            rows = match_table.find_all('tr')
            if len(rows) < 2:
                continue
            
            team_cols = rows[0].find_all('td', recursive=False)
            team1_tag = team_cols[0].find('span', class_='team-template-text')
            team2_tag = team_cols[2].find('span', class_='team-template-text')
            
            team1 = team1_tag.text.strip() if team1_tag else team_cols[0].text.strip()
            team2 = team2_tag.text.strip() if team2_tag else team_cols[2].text.strip()
            
            if len(team_cols) > 1:
                versus_col = team_cols[1]
                format_abbr = versus_col.find('abbr')
                if format_abbr and format_abbr.text:
                    match_format = format_abbr.text.strip()
            
            time_tag = rows[1].find('span', class_='timer-object')
            if not time_tag or 'data-timestamp' not in time_tag.attrs:
                continue
            
            try:
                time_unix_timestamp = int(time_tag['data-timestamp'])
                match_time_utc = datetime.fromtimestamp(time_unix_timestamp, tz=pytz.utc)
            except ValueError:
                continue
            
            event_name_tag = rows[1].find('div', class_='text-nowrap')
            event_link = event_name_tag.find('a') if event_name_tag else None
            
            if event_link and event_link.text.strip():
                event_name = event_link.text.strip()
                match_url = f"https://liquipedia.net{event_link['href']}" if 'href' in event_link.attrs else URL_LIQUIPEDIA
            else:
                event_name = "Evento Desconhecido"
                match_url = URL_LIQUIPEDIA
            
            is_team_br = any(br.lower() in team1.lower() or br.lower() in team2.lower() for br in BRAZILIAN_TEAMS)
            is_excluded = any(ex.lower() in team1.lower() or ex.lower() in team2.lower() for ex in BRAZILIAN_TEAMS_EXCLUSIONS)
            
            if not is_team_br or is_excluded:
                continue
            
            match_time_br = match_time_utc.astimezone(BR_TZ)
            
            format_map = {
                'Bo1': 'Best of 1 (Bo1)',
                'Bo3': 'Best of 3 (Bo3)',
                'Bo5': 'Best of 5 (Bo5)',
                'Partida': 'Partida Simples'
            }
            full_match_format = format_map.get(match_format, match_format)
            
            e = Event()
            e.name = f"{team1} vs {team2}"
            e.begin = match_time_utc.astimezone(pytz.utc)
            e.end = e.begin + timedelta(hours=2)
            e.description = (
                f"🎮 Format: {full_match_format}\n"
                f"📅 Event: {event_name}"
            )
            e.url = match_url
            
            alarm = Alarm(trigger=timedelta(minutes=0), display_text=f"{team1} vs {team2}")
            e.alarms.append(alarm)
            
            uid_base = f"{team1}_{team2}_{event_name}_{e.begin.isoformat()}".encode("utf-8")
            stable_uid = hashlib.md5(uid_base).hexdigest()[:8]
            e.uid = f"{stable_uid}@cs2calendar"
            
            sorted_teams = tuple(sorted([team1.lower().strip(), team2.lower().strip()]))
            match_key = (sorted_teams, e.begin.isoformat(), event_name.lower().strip())
            
            if match_key in unique_matches:
                continue
            
            unique_matches.add(match_key)
            cal.events.add(e)
            added_count += 1
            
            print(f"      ✅ Adicionado: {e.name} ({match_time_br.strftime('%d/%m %H:%M')}) | {full_match_format} | Evento: {event_name}")
        
        except Exception as e:
            print(f"      ❌ Erro ao processar bloco {match_idx}: {e}")

except requests.exceptions.RequestException as e:
    print(f"❌ Falha na requisição HTTP - {e}")
except Exception as e:
    print(f"❌ Erro inesperado - {e}")

try:
    with open("calendar.ics", "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())
    print(f"\n📌 {added_count} partidas BR salvas em calendar.ics")
except Exception as e:
    print(f"❌ Erro ao salvar calendar.ics: {e}")
