import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
from ics import Calendar, Event
from ics.alarm import DisplayAlarm
import hashlib

# -------------------- Configurações Globais --------------------
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo",
                   "RED Canids", "Legacy", "ODDIK"]
BRAZILIAN_TEAMS_EXCLUSIONS = ["Imperial.A", "Imperial Fe", "MIBR.A", "paiN.A", "ODDIK.A"]
URL_LIQUIPEDIA = "https://liquipedia.net/counterstrike/Liquipedia:Matches"
BR_TZ = pytz.timezone("America/Sao_Paulo")

cal = Calendar()
added_count = 0
unique_matches = set()

print(f"🔍 Buscando partidas em {URL_LIQUIPEDIA}...")

try:
    response = requests.get(URL_LIQUIPEDIA, timeout=10)

    # --- LOG 1: Status da requisição HTTP ---
    print(f"--- DEBUG: Status da requisição HTTP: {response.status_code}")

    response.raise_for_status() # Isso vai levantar um erro para status 4xx/5xx

    soup = BeautifulSoup(response.text, 'lxml')

    # --- LOG 2: Um trecho do HTML retornado (apenas os primeiros 1000 caracteres para não poluir demais) ---
    print(f"--- DEBUG: Primeiros 1000 caracteres do HTML retornado:\n{response.text[:1000]}...")

    MATCH_TABLE_CLASS = 'wikitable wikitable-striped infobox_matches_content'
    match_tables = soup.find_all('table', class_=MATCH_TABLE_CLASS)

    # --- LOG 3: Verificando se há *alguma* tabela na página, independentemente da classe ---
    all_tables = soup.find_all('table')
    print(f"--- DEBUG: Total de elementos <table> encontrados na página: {len(all_tables)}")
    if all_tables:
        print(f"--- DEBUG: Exemplo da primeira tabela encontrada (tag e classes): {all_tables[0].name}, classes: {all_tables[0].get('class')}")

    print(f"✅ Encontrados {len(match_tables)} blocos de partidas individuais com a classe '{MATCH_TABLE_CLASS}'.")

    if not match_tables:
        print("⚠️ Nenhum bloco de partida encontrado. Verifique se a classe da tabela mudou.")
        # --- LOG 4: Se não encontrou, vamos tentar encontrar algo parecido ou o que pode ter substituído ---
        # Tenta encontrar divs que possam ser containers de partidas, caso a estrutura tenha mudado de table para div
        potential_match_containers = soup.find_all(lambda tag: tag.name == 'div' and 'match' in tag.get('class', []) or 'infobox' in tag.get('class', []))
        print(f"--- DEBUG: Encontrados {len(potential_match_containers)} potenciais containers de partida (divs com 'match' ou 'infobox' na classe).")
        if potential_match_containers:
            print(f"--- DEBUG: Exemplo do primeiro potencial container: {potential_match_containers[0].name}, classes: {potential_match_containers[0].get('class')}")

        exit()

    for match_idx, match_table in enumerate(match_tables, 1):
        team1, team2, event_name, match_url = 'N/A', 'N/A', 'N/A', URL_LIQUIPEDIA
        match_format = 'Partida'

        try:
            rows = match_table.find_all('tr')
            if len(rows) < 2:
                # --- LOG 5: Ignorando linhas insuficientes ---
                print(f"--- DEBUG: Bloco {match_idx} ignorado: menos de 2 linhas encontradas.")
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
                # --- LOG 6: Ignorando sem tag de tempo ou timestamp ---
                print(f"--- DEBUG: Bloco {match_idx} ignorado: sem tag de tempo ou atributo 'data-timestamp'.")
                continue

            try:
                time_unix_timestamp = int(time_tag['data-timestamp'])
                match_time_utc = datetime.fromtimestamp(time_unix_timestamp, tz=pytz.utc)
            except ValueError:
                # --- LOG 7: Erro de valor no timestamp ---
                print(f"--- DEBUG: Bloco {match_idx} ignorado: erro ao converter timestamp '{time_tag.get('data-timestamp')}' para inteiro.")
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
                # --- LOG 8: Ignorando times não BR ou excluídos ---
                print(f"--- DEBUG: Bloco {match_idx} ignorado: Times '{team1}' vs '{team2}' não são BR ou estão na lista de exclusão.")
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

            alarm = DisplayAlarm(trigger=timedelta(minutes=0), display_text=f"{team1} vs {team2}")
            e.alarms.append(alarm)

            uid_base = f"{team1}_{team2}_{event_name}_{e.begin.isoformat()}".encode("utf-8")
            stable_uid = hashlib.md5(uid_base).hexdigest()[:8]
            e.uid = f"{stable_uid}@cs2calendar"

            sorted_teams = tuple(sorted([team1.lower().strip(), team2.lower().strip()]))
            match_key = (sorted_teams, e.begin.isoformat(), event_name.lower().strip())

            if match_key in unique_matches:
                # --- LOG 9: Ignorando partida duplicada ---
                print(f"--- DEBUG: Bloco {match_idx} ignorado: Partida '{e.name}' em '{event_name}' às '{e.begin.isoformat()}' já adicionada.")
                continue

            unique_matches.add(match_key)
            cal.events.add(e)
            added_count += 1

            print(f"      ✅ Adicionado: {e.name} ({match_time_br.strftime('%d/%m %H:%M')}) | {full_match_format} | Evento: {event_name}")

        except Exception as e_inner:
            print(f"      ❌ Erro ao processar bloco {match_idx}: {e_inner} | Dados parciais: Team1='{team1}', Team2='{team2}', Evento='{event_name}'")

except requests.exceptions.RequestException as e:
    print(f"❌ Falha na requisição HTTP - {e}")
except Exception as e:
    print(f"❌ Erro inesperado - {e}")

try:
    with open("calendar.ics", "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())
    print(f"\n📌 {added_count} partidas BR salvas em calendar.ics (com alarmes no horário do jogo)")
except Exception as e:
    print(f"❌ Erro ao salvar calendar.ics: {e}")

