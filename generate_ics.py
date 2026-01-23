import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
from ics import Calendar, Event
from ics.alarm import DisplayAlarm
import hashlib
import json
import re

# -------------------- Configurações Globais --------------------
# Lista de times brasileiros principais (nomes como aparecem no HTML, mas serão normalizados para comparação)
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo",
                   "RED Canids", "Legacy", "ODDIK", "Imperial Esports"]

# Lista de exclusões (nomes como aparecem no HTML, mas serão normalizados para comparação)
BRAZILIAN_TEAMS_EXCLUSIONS = [
    "Imperial.A", "Imperial Fe", "MIBR.A", "paiN.A", "ODDIK.A",
    "Imperial Academy", "Imperial.Acd", "Imperial Female",
    "Furia Academy", "Furia.A", "Pain Academy", "Mibr Academy",
    "Legacy Academy", "ODDIK Academy", "RED Canids Academy",
    "Fluxo Academy"
]

TIPSGG_URL = "https://tips.gg/csgo/matches/"
CALENDAR_FILENAME = "calendar.ics"
BR_TZ = pytz.timezone('America/Sao_Paulo') # Fuso horário de Brasília

# Adicionamos um conjunto mais completo de HEADERS para simular um navegador
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Cache-Control': 'max-age=0'
}

# -------------------- Funções Auxiliares --------------------
def normalize_team(name):
    """
    Normaliza o nome do time para comparação, convertendo para minúsculas e removendo espaços extras.
    Mantém caracteres especiais e espaços internos para comparações literais.
    """
    if not name:
        return ""
    return name.lower().strip()

# Pré-normaliza as listas de times para otimizar as comparações
NORMALIZED_BRAZILIAN_TEAMS = {normalize_team(team) for team in BRAZILIAN_TEAMS}
NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS = {normalize_team(team) for team in BRAZILIAN_TEAMS_EXCLUSIONS}

# -------------------- Lógica Principal --------------------
cal = Calendar()
added_count = 0

print(f"🔍 Baixando página: {TIPSGG_URL}")

try:
    # Passamos os HEADERS mais completos na requisição
    response = requests.get(TIPSGG_URL, headers=HEADERS, timeout=10)
    response.raise_for_status() # Levanta um erro para códigos de status HTTP ruins (4xx ou 5xx)
    print(f"✅ Página baixada com sucesso! HTTP Status: {response.status_code}")

    soup = BeautifulSoup(response.text, 'html.parser')

    # Encontrar todos os blocos de script com type="application/ld+json"
    script_blocks = soup.find_all('script', type='application/ld+json')
    print(f"📄 Encontrados {len(script_blocks)} blocos <script type='application/ld+json'>.")

    current_time_br = datetime.now(BR_TZ)
    print(f"⏰ Horário atual em BRT: {current_time_br}")

    for script_idx, script_block in enumerate(script_blocks, 1):
        # print(f"\n--- Processando script {script_idx} ---")
        try:
            json_data = json.loads(script_block.string)
            # print("JSON-LD bruto:", json.dumps(json_data, indent=2)) # Log do JSON bruto

            # Verificar se é um SportsEvent e se tem os dados necessários
            if json_data.get("@type") == "SportsEvent" and json_data.get("name") and json_data.get("startDate"):
                # Extrair dados
                event_name_raw = json_data.get("name", "Nome do Evento Desconhecido")
                start_raw = json_data.get("startDate")
                description_raw = json_data.get("description", "")
                match_url_raw = "https://tips.gg" + json_data.get("url", TIPSGG_URL) # Adiciona o domínio base
                organizer_name = json_data.get("organizer", {}).get("name", "Torneio Desconhecido")

                competitors = json_data.get("competitor", [])
                team1_raw = competitors[0].get("name", "TBD") if len(competitors) > 0 else "TBD"
                team2_raw = competitors[1].get("name", "TBD") if len(competitors) > 1 else "TBD"

                # print(f"  Equipes: {team1_raw} vs {team2_raw}")
                # print(f"  Torneio: {organizer_name}")
                # print(f"  Início (raw): {start_raw}")

                # Ignorar partidas com TBD
                if team1_raw == "TBD" or team2_raw == "TBD":
                    # print("  🚫 Ignorando: Time TBD.")
                    continue

                # Normaliza os nomes para a lógica de filtragem
                normalized_team1 = normalize_team(team1_raw)
                normalized_team2 = normalize_team(team2_raw)

                # Lógica de filtragem: verifica se algum time BR principal está envolvido E não é uma exclusão
                is_br_team1 = normalized_team1 in NORMALIZED_BRAZILIAN_TEAMS
                is_br_team2 = normalized_team2 in NORMALIZED_BRAZILIAN_TEAMS

                is_excluded_team1 = normalized_team1 in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS
                is_excluded_team2 = normalized_team2 in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS

                is_br_team_involved = (is_br_team1 and not is_excluded_team1) or \
                                      (is_br_team2 and not is_excluded_team2)

                if not is_br_team_involved:
                    # print(f"  🚫 Ignorando: Nenhuma equipe BR principal (não excluída) envolvida. ({team1_raw}, {team2_raw})")
                    continue

                # Converter data/hora para o fuso horário de Brasília
                # O formato do startDate é ISO 8601 com offset de fuso horário (-0300)
                # datetime.fromisoformat() pode lidar com isso diretamente
                match_time_utc_aware = datetime.fromisoformat(start_raw)
                match_time_br = match_time_utc_aware.astimezone(BR_TZ)

                # print(f"  Horário da partida (BRT): {match_time_br}")

                # Filtrar partidas que já ocorreram ou estão em andamento
                # Consideramos que uma partida dura 2 horas para esta checagem
                if match_time_br + timedelta(hours=2) < current_time_br:
                    # print(f"  🚫 Ignorando: Partida já ocorreu ou está em andamento. ({match_time_br} < {current_time_br})")
                    continue

                # Extrair formato da partida (Bo1, Bo3, etc.) da descrição
                match_format_match = re.search(r'(BO\d+)\sMatch', description_raw)
                match_format = match_format_match.group(1) if match_format_match else "BoX"

                # Novo formato para o nome do evento (summary)
                event_summary = f"{team1_raw} vs {team2_raw}"

                # Novo formato para a descrição do evento
                event_description = (
                    f"🏆- {match_format}\n"
                    f"📍{organizer_name}\n"
                    f"🌐{match_url_raw}"
                )

                # Gerar UID único para o evento
                event_uid = hashlib.sha1(
                    (event_summary + start_raw).encode("utf-8")
                ).hexdigest()

                # print("🆔 UID:", event_uid)

                e = Event()
                e.name = event_summary
                e.begin = match_time_br # O objeto `ics` lida bem com datetimes timezone-aware
                e.duration = timedelta(hours=2) # Duração padrão de 2 horas
                e.description = event_description
                e.uid = event_uid

                # Adiciona alarme 15 minutos antes
                alarm = DisplayAlarm(trigger=timedelta(minutes=-15))
                e.alarms.append(alarm)

                cal.events.add(e)
                added_count += 1

                # print("✅ Adicionado ao calendário!")

        except json.JSONDecodeError as je:
            print(f"❌ Erro ao decodificar JSON no script {script_idx}: {je}")
        except ValueError as ve:
            print(f"❌ Erro de dados no script {script_idx}: {ve}")
        except Exception as e_inner:
            print(f"❌ Erro inesperado ao processar script {script_idx}: {e_inner}")

except requests.exceptions.RequestException as e:
    print(f"❌ Falha na requisição HTTP - {e}")
except Exception as e:
    print(f"❌ Erro inesperado - {e}")

print(f"\n💾 Salvando arquivo: {CALENDAR_FILENAME}")
try:
    with open(CALENDAR_FILENAME, "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())
    print(f"📌 Total de partidas adicionadas: {added_count}")
except Exception as e:
    print(f"❌ Erro ao salvar {CALENDAR_FILENAME}: {e}")
