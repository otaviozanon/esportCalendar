import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
from ics import Calendar, Event
from ics.alarm import DisplayAlarm
import hashlib
import json # Importar para lidar com JSON-LD

# -------------------- Configurações Globais --------------------
# Lista de times brasileiros principais (nomes como aparecem no HTML, mas serão normalizados para comparação)
# Mantive a lista original, mas ela será usada para comparar com os nomes extraídos do JSON-LD
BRAZILIAN_TEAMS = ["FURIA", "paiN", "MIBR", "Imperial", "Fluxo",
                   "RED Canids", "Legacy", "ODDIK", "Imperial Esports"]

# Lista de exclusões (nomes como aparecem no HTML, mas serão normalizados para comparação)
BRAZILIAN_TEAMS_EXCLUSIONS = [
    "Imperial.A", "Imperial Fe", "MIBR.A", "paiN.A", "ODDIK.A",
    "Imperial Academy", "Imperial.Acd", "Imperial Female",
    "Furia Academy", "Furia.A", "Pain Academy", "Mibr Academy", "Legacy Academy", "ODDIK Academy",
    "RED Canids Academy", "Fluxo Academy"
]

TIPSGG_URL = "https://tips.gg/csgo/matches/"
CALENDAR_FILENAME = "calendar.ics"
BR_TZ = pytz.timezone('America/Sao_Paulo') # Fuso horário de Brasília

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

# Não exibir logs no console durante a execução, conforme sua preferência.
# print(f"🔍 Buscando partidas em {TIPSGG_URL}...")

try:
    response = requests.get(TIPSGG_URL, timeout=10)
    response.raise_for_status() # Levanta um erro para códigos de status HTTP ruins (4xx ou 5xx)
    soup = BeautifulSoup(response.text, 'html.parser')

    # Encontrar todos os blocos de script com type="application/ld+json"
    json_ld_scripts = soup.find_all('script', type='application/ld+json')
    # print(f"✅ Encontrados {len(json_ld_scripts)} blocos JSON-LD.")

    # Obter a data e hora atual para filtrar partidas futuras
    now_br = datetime.now(BR_TZ)

    for script_idx, script in enumerate(json_ld_scripts, 1):
        try:
            data = json.loads(script.string)

            # Verificar se é um evento esportivo e se tem os campos necessários
            if data.get('@type') == 'SportsEvent' and data.get('startDate') and data.get('competitor'):
                event_name_raw = data.get('name', 'Evento Desconhecido')
                event_description_raw = data.get('description', '')
                match_url_raw = data.get('url', TIPSGG_URL)
                organizer_name = data.get('organizer', {}).get('name', 'Torneio Desconhecido')

                # Extrair times
                competitors = data.get('competitor', [])
                if len(competitors) < 2:
                    continue # Ignora se não houver dois oponentes claros

                team1_raw = competitors[0].get('name', 'TBD')
                team2_raw = competitors[1].get('name', 'TBD')

                # Ignorar partidas com TBD
                if team1_raw == "TBD" or team2_raw == "TBD":
                    continue

                # Normaliza os nomes para a lógica de filtragem
                normalized_team1 = normalize_team(team1_raw)
                normalized_team2 = normalize_team(team2_raw)

                # Lógica de filtragem: verifica se algum time BR principal está envolvido E não é uma exclusão
                # E também verifica se a partida é futura, conforme sua preferência.
                is_br_team1 = normalized_team1 in NORMALIZED_BRAZILIAN_TEAMS
                is_br_team2 = normalized_team2 in NORMALIZED_BRAZILIAN_TEAMS

                is_excluded_team1 = normalized_team1 in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS
                is_excluded_team2 = normalized_team2 in NORMALIZED_BRAZILIAN_TEAMS_EXCLUSIONS

                is_br_team_involved = (is_br_team1 and not is_excluded_team1) or \
                                      (is_br_team2 and not is_excluded_team2)

                if not is_br_team_involved:
                    continue # Ignora se nenhum time BR principal (não excluído) estiver envolvido

                # Extrair timestamp e converter para BRT
                # O startDate já vem com o fuso horário, o que é ótimo!
                match_time_br = datetime.fromisoformat(data['startDate']).astimezone(BR_TZ)

                # Filtrar apenas partidas futuras
                if match_time_br < now_br:
                    continue

                # Extrair formato da partida (BO1, BO3, etc.) da descrição
                # A descrição geralmente contém "BO3 Match", "BO1 Match", etc.
                match_format_search = re.search(r'(BO\d+)\sMatch', event_description_raw, re.IGNORECASE)
                match_format = match_format_search.group(1).upper() if match_format_search else "BoX"

                # Novo formato para o nome do evento (summary)
                event_summary = f"{team1_raw} vs {team2_raw}"

                # Novo formato para a descrição do evento
                event_description = (
                    f"🏆- {match_format}\n"
                    f"📍{organizer_name}\n" # Usando o nome do organizador como local do evento
                    f"🌐{match_url_raw}"
                )

                # Gerar UID para o evento
                event_uid = hashlib.sha1(event_summary.encode('utf-8') + str(match_time_br).encode('utf-8')).hexdigest()

                e = Event()
                e.name = event_summary
                e.begin = match_time_br # Já está em BRT, mas o ics espera UTC ou timezone-aware
                e.duration = timedelta(hours=2) # Duração padrão de 2 horas
                e.description = event_description
                e.uid = event_uid

                # Adiciona alarme 15 minutos antes
                alarm = DisplayAlarm(trigger=timedelta(minutes=-15))
                e.alarms.append(alarm)

                cal.events.add(e)
                added_count += 1

        except json.JSONDecodeError as je:
            # print(f"❌ Erro ao decodificar JSON no script {script_idx}: {je}")
            pass # Não exibir logs no console
        except ValueError as ve:
            # print(f"❌ Erro de dados no script {script_idx}: {ve}")
            pass # Não exibir logs no console
        except Exception as e_inner:
            # print(f"❌ Erro inesperado ao processar script {script_idx}: {e_inner}")
            pass # Não exibir logs no console

except requests.exceptions.RequestException as e:
    # print(f"❌ Falha na requisição HTTP - {e}")
    pass # Não exibir logs no console
except Exception as e:
    # print(f"❌ Erro inesperado - {e}")
    pass # Não exibir logs no console

try:
    with open(CALENDAR_FILENAME, "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())
    # print(f"\n📌 {added_count} partidas BR salvas em {CALENDAR_FILENAME} (com alarmes no horário do jogo)")
except Exception as e:
    # print(f"❌ Erro ao salvar {CALENDAR_FILENAME}: {e}")
    pass # Não exibir logs no console

