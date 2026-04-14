import os
import json
import hashlib
from datetime import datetime, timedelta, date

import pytz
from bs4 import BeautifulSoup
from icalendar import Calendar, Event, Alarm
import requests


# -------------------- Configurações Globais --------------------
CALENDAR_FILENAME = "calendar.ics"
STATE_FILE = "state.json"

BR_TZ = pytz.timezone("America/Sao_Paulo")
DELETE_OLDER_THAN_DAYS = 7

SOURCE_MARKER = "X-SETT-SOURCE:TIPSGG"
TIPS_URL_HINT = "https://tips.gg/matches/"

SCRAPE_DO_API_KEY = os.getenv("SCRAPE_DO_API_KEY", "")
SCRAPE_DO_URL = "https://api.scrape.do"


# -------------------- Jogos / Times --------------------
def normalize_team(name: str) -> str:
    """Normaliza nome do time para comparação."""
    return (name or "").lower().strip()


GAMES = {
    "CS2": {
        "prefix": "[CS2] ",
        "base_path": "https://tips.gg/csgo/matches/",
        "days_to_scrape": 3,
        "once_per_day": False,
        "teams": {"FURIA", "paiN Gaming", "MIBR", "Imperial", "Fluxo", "RED Canids", "Legacy", "ODDIK", "Imperial Esports", "Gaimin Gladiators"},
        "exclusions": {
            "Imperial.A", "Imperial Fe", "MIBR.A", "paiN.A", "ODDIK.A",
            "Imperial Academy", "Imperial.Acd", "Imperial Female",
            "Furia Academy", "Furia.A", "Pain Academy", "Mibr Academy", "Legacy Academy", "ODDIK Academy",
            "RED Canids Academy", "Fluxo Academy"
        },
    },
    "VAL": {
        "prefix": "[V] ",
        "base_path": "https://tips.gg/valorant/matches/",
        "days_to_scrape": 1,
        "once_per_day": True,
        "run_at_hour": 0,
        "teams": {"LOUD", "FURIA", "MIBR"},
        "exclusions": set(),
    },
    "RL": {
        "prefix": "[RL] ",
        "base_path": "https://tips.gg/rl/matches/",
        "days_to_scrape": 1,
        "once_per_day": True,
        "run_at_hour": 0,
        "teams": {"FURIA", "Team Secret"},
        "exclusions": set(),
    },
    "LOL": {
        "prefix": "[LOL] ",
        "base_path": "https://tips.gg/lol/matches/",
        "days_to_scrape": 1,
        "once_per_day": True,
        "run_at_hour": 0,
        "teams": {"paiN Gaming", "LOUD", "Vivo Keyd Stars", "RED Canids"},
        "exclusions": set(),
    },
}

# Normaliza times e exclusões na inicialização
for k, cfg in GAMES.items():
    cfg["teams_norm"] = {normalize_team(t) for t in cfg["teams"]}
    cfg["exclusions_norm"] = {normalize_team(t) for t in cfg["exclusions"]}


# -------------------- Helpers --------------------
def log(msg: str):
    """Log com timestamp."""
    now = datetime.now(BR_TZ).strftime("%H:%M:%S")
    print(f"[{now}] {msg}")


def build_url_for_day(base_path: str, target_date: date) -> str:
    """Constrói URL para data específica."""
    date_str = target_date.strftime("%d-%m-%Y")
    return f"{base_path}{date_str}/"


def fetch_page_scrape_do(url: str) -> str:
    """Busca página usando Scrape.do. Retorna HTML ou string vazia."""
    if not SCRAPE_DO_API_KEY:
        log(f"❌ ERRO: API key Scrape.do não configurada")
        return ""

    try:
        params = {"token": SCRAPE_DO_API_KEY, "url": url}
        response = requests.get(SCRAPE_DO_URL, params=params, timeout=60)
        response.raise_for_status()
        return response.text
    except requests.exceptions.HTTPError as e:
        log(f"❌ HTTP {e.response.status_code} ao buscar {url}")
        return ""
    except requests.exceptions.Timeout:
        log(f"❌ Timeout (60s) ao buscar {url}")
        return ""
    except Exception as e:
        log(f"❌ Erro ao buscar {url}: {type(e).__name__}: {str(e)}")
        return ""


def load_calendar(path: str) -> Calendar:
    """Carrega ou cria calendário."""
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                return Calendar.from_ical(f.read())
        except Exception as e:
            log(f"⚠️ Falha ao ler {path}: {e}. Criando novo.")

    cal = Calendar()
    cal.add('prodid', '-//Esport Calendar BR//tips.gg//')
    cal.add('version', '2.0')
    return cal


def save_calendar(cal: Calendar, path: str):
    """Salva calendário em arquivo."""
    try:
        with open(path, "wb") as f:
            f.write(cal.to_ical())
    except Exception as e:
        log(f"❌ Erro ao salvar {path}: {e}")
        raise


def get_existing_uids(cal: Calendar) -> set:
    """Retorna UIDs existentes no calendário."""
    uids = set()
    for component in cal.walk('VEVENT'):
        uid = component.get('uid')
        if uid:
            uids.add(str(uid))
    return uids


def normalize_event_datetime_utc(dt: datetime) -> datetime:
    """Normaliza datetime para UTC sem microsegundos."""
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    return dt.astimezone(pytz.utc).replace(microsecond=0, second=0)


def is_ours(component) -> bool:
    """Verifica se evento foi criado por este script."""
    desc = str(component.get('description', ''))
    return (SOURCE_MARKER in desc) or (TIPS_URL_HINT in desc)


def event_start_date_local(component) -> date | None:
    """Extrai data local do evento."""
    try:
        dt = component.get('dtstart').dt
        if isinstance(dt, datetime):
            if dt.tzinfo is None:
                dt = pytz.utc.localize(dt)
            return dt.astimezone(BR_TZ).date()
        elif isinstance(dt, date):
            return dt
    except Exception:
        pass
    return None


def prune_older_than(cal: Calendar, cutoff_date: date) -> int:
    """Remove eventos nossos com data anterior a cutoff. Retorna quantidade removida."""
    to_remove = []
    for component in list(cal.walk('VEVENT')):
        if not is_ours(component):
            continue
        event_date = event_start_date_local(component)
        if event_date and event_date < cutoff_date:
            to_remove.append(component)

    for comp in to_remove:
        cal.subcomponents.remove(comp)

    return len(to_remove)


def load_state() -> dict:
    """Carrega estado ou cria novo."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_run": {}, "cs2_day_offset": 0}


def save_state(state: dict):
    """Salva estado."""
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        log(f"❌ Erro ao salvar state.json: {e}")


def should_run_game(game_key: str, cfg: dict, now: datetime, state: dict) -> bool:
    """Verifica se jogo deve ser raspado agora."""
    if not cfg.get("once_per_day", False):
        return True

    run_at = cfg.get("run_at_hour", 0)
    if now.hour < run_at:
        return False

    last = state.get("last_run", {}).get(game_key)
    if last == now.strftime("%Y-%m-%d"):
        return False

    return True


def mark_game_as_run(game_key: str, state: dict):
    """Marca jogo como executado hoje."""
    if "last_run" not in state:
        state["last_run"] = {}
    state["last_run"][game_key] = datetime.now(BR_TZ).strftime("%Y-%m-%d")
    save_state(state)


def get_cs2_target_days(today: date, state: dict) -> list:
    """Retorna dia alvo para CS2 baseado em offset."""
    offset = state.get("cs2_day_offset", 0)
    return [today + timedelta(days=offset)]


def advance_cs2_offset(state: dict):
    """Avança offset de CS2 (0→1→2→0). Retorna (current, next)."""
    current = state.get("cs2_day_offset", 0)
    next_offset = (current + 1) % 3
    state["cs2_day_offset"] = next_offset
    save_state(state)
    return current, next_offset


def dedupe_calendar_events(cal: Calendar) -> int:
    """Remove eventos duplicados (mesmo UID). Retorna quantidade removida."""
    seen = {}
    to_remove = []
    for component in list(cal.walk('VEVENT')):
        if not is_ours(component):
            continue
        uid = str(component.get('uid', ''))
        if uid in seen:
            to_remove.append(component)
        else:
            seen[uid] = component

    for comp in to_remove:
        cal.subcomponents.remove(comp)

    return len(to_remove)


def dedupe_by_url_keep_latest(cal: Calendar) -> int:
    """Remove eventos duplicados por URL (mantém primeiro). Retorna quantidade removida."""
    url_map = {}
    to_remove = []
    for component in list(cal.walk('VEVENT')):
        if not is_ours(component):
            continue
        desc = str(component.get('description', ''))
        url = None
        for line in desc.split('\n'):
            if line.startswith('🌐'):
                url = line.replace('🌐 ', '').strip()
                break
        if url:
            if url not in url_map:
                url_map[url] = component
            else:
                to_remove.append(component)

    for comp in to_remove:
        cal.subcomponents.remove(comp)

    return len(to_remove)


def build_stable_uid(game_key: str, event_summary: str, match_time_utc: datetime, tournament_desc: str, organizer_name: str, match_url: str) -> str:
    """Gera UID estável baseado em dados do evento."""
    data = f"{game_key}|{event_summary}|{match_time_utc.isoformat()}|{tournament_desc}|{organizer_name}|{match_url}"
    return hashlib.sha256(data.encode()).hexdigest()


def scrape_days_for_game(game_key: str, cfg: dict, today: date, target_days: list, existing_uids: set) -> tuple:
    """Raspa dias para jogo. Retorna (lista_eventos, stats)."""
    new_events = []
    stats = {
        "days_scraped": 0,
        "scripts_total": 0,
        "sports_events": 0,
        "added": 0,
        "skipped_tbd": 0,
        "skipped_past": 0,
        "skipped_not_allowed": 0,
        "matches": [],  # Nova lista para armazenar detalhes dos jogos
    }

    prefix = cfg.get("prefix", "")
    base_path = cfg.get("base_path", "")
    teams_norm = cfg.get("teams_norm", set())
    exclusions_norm = cfg.get("exclusions_norm", set())

    for target_day in target_days:
        url = build_url_for_day(base_path, target_day)
        html = fetch_page_scrape_do(url)

        if not html:
            continue

        try:
            soup = BeautifulSoup(html, 'html.parser')
            scripts = soup.find_all('script', {'type': 'application/ld+json'})
        except Exception as e:
            log(f"❌ Erro ao parsear HTML de {target_day.strftime('%d/%m/%Y')}: {e}")
            continue

        stats["days_scraped"] += 1
        stats["scripts_total"] += len(scripts)

        now_utc = datetime.now(pytz.utc)

        for script in scripts:
            try:
                data = json.loads(script.string)
            except json.JSONDecodeError as e:
                log(f"❌ JSON inválido em script: {e}")
                continue

            if not isinstance(data, dict):
                continue

            events = data.get("@graph", []) or [data]

            for event in events:
                try:
                    if event.get("@type") != "SportsEvent":
                        continue

                    competitors = event.get("competitor", [])
                    team1_raw = competitors[0].get("name", "") if len(competitors) > 0 else ""
                    team2_raw = competitors[1].get("name", "") if len(competitors) > 1 else ""

                    if not team1_raw or not team2_raw:
                        continue

                    # TBD check
                    if "TBD" in team1_raw or "TBD" in team2_raw:
                        stats["skipped_tbd"] += 1
                        continue

                    # Parse data/hora
                    try:
                        match_time_str = event.get("startDate", "")
                        match_time_utc = datetime.fromisoformat(match_time_str.replace("Z", "+00:00"))
                        if match_time_utc.tzinfo is None:
                            match_time_utc = pytz.utc.localize(match_time_utc)
                        match_time_utc = match_time_utc.astimezone(pytz.utc)
                    except Exception as e:
                        log(f"❌ Erro ao parsear data '{match_time_str}': {e}")
                        continue

                    # Evento no passado
                    if match_time_utc < now_utc:
                        stats["skipped_past"] += 1
                        continue

                    # Verifica times permitidos
                    t1 = normalize_team(team1_raw)
                    t2 = normalize_team(team2_raw)

                    allowed_t1 = (t1 in teams_norm) and (t1 not in exclusions_norm)
                    allowed_t2 = (t2 in teams_norm) and (t2 not in exclusions_norm)

                    if not (allowed_t1 or allowed_t2):
                        stats["skipped_not_allowed"] += 1
                        continue

                    # Monta evento
                   event_summary = f"{prefix}{team1_raw} vs {team2_raw}"
                    description = event.get("name", "")
                    organizer_name = event.get("organizer", {}).get("name", "")
                    match_url = event.get("url", "")

                    # Garante URL completa
                    if match_url and not match_url.startswith("http"):
                        match_url = f"https://tips.gg{match_url}"

                    event_uid = build_stable_uid(
                        game_key=game_key,
                        event_summary=event_summary,
                        match_time_utc=match_time_utc,
                        tournament_desc=description,
                        organizer_name=organizer_name,
                        match_url=match_url,
                    )

                    # Já existe
                    if event_uid in existing_uids:
                        continue

                    # Armazena detalhes do jogo
                    match_time_br = match_time_utc.astimezone(BR_TZ)
                    stats["matches"].append({
                        "teams": f"{team1_raw} | {team2_raw}",
                        "time": match_time_br.strftime("%H:%M")
                    })

                    event_description = (
                        f"🏆 {description}\n"
                        f"📍 {organizer_name}\n"
                        f"🌐 {match_url}\n"
                        f"{SOURCE_MARKER}"
                    )

                    e = Event()
                    e.add('summary', event_summary)
                    e.add('dtstart', normalize_event_datetime_utc(match_time_utc))
                    e.add('dtend', normalize_event_datetime_utc(match_time_utc) + timedelta(hours=2))
                    e.add('description', event_description)
                    e.add('uid', event_uid)
                    e.add('dtstamp', datetime.now(pytz.utc))

                    alarm = Alarm()
                    alarm.add('action', 'DISPLAY')
                    alarm.add('trigger', timedelta(minutes=-15))
                    alarm.add('description', f'Lembrete: {event_summary}')
                    e.add_component(alarm)

                    new_events.append(e)
                    existing_uids.add(event_uid)
                    stats["added"] += 1

                except Exception as e:
                    log(f"❌ Erro ao processar evento: {type(e).__name__}: {e}")
                    continue

    return new_events, stats


# -------------------- Execução --------------------
log("=" * 60)
log("🚀 INICIANDO LIMPEZA DE DADOS")
log("=" * 60)

cal = load_calendar(CALENDAR_FILENAME)
state = load_state()
now = datetime.now(BR_TZ)
today = now.date()

# Limpeza inicial
deduped = dedupe_calendar_events(cal)
if deduped > 0:
    log(f"🗑️  Removidos {deduped} eventos duplicados (UID)")

deduped_url = dedupe_by_url_keep_latest(cal)
if deduped_url > 0:
    log(f"🗑️  Removidos {deduped_url} eventos duplicados (URL)")

existing_uids = get_existing_uids(cal)

# Prune antigos
cutoff = today - timedelta(days=DELETE_OLDER_THAN_DAYS)
removed = prune_older_than(cal, cutoff)
if removed > 0:
    log(f"🗑️  Removidos {removed} eventos anteriores a {cutoff.strftime('%d/%m/%Y')}")

total_added = 0

try:
    for game_key, cfg in GAMES.items():
        if not should_run_game(game_key, cfg, now, state):
            run_at = cfg.get("run_at_hour", 0)
            next_run_date = today if now.hour < run_at else today + timedelta(days=1)
            log(f"⏭️  {game_key} próxima execução: {run_at:02d}:00 ({next_run_date.strftime('%d/%m/%Y')})")
            continue

        if game_key == "CS2":
            current_offset = state.get("cs2_day_offset", 0)
            target_days = get_cs2_target_days(today, state)
            next_offset = (current_offset + 1) % 3
            log(f"📅 {game_key} offset {current_offset}→{next_offset} | LIMPANDO {target_days[0].strftime('%d/%m/%Y')}")
        else:
            target_days = [today]
            log(f"📅 {game_key} | LIMPANDO {today.strftime('%d/%m/%Y')}")

        new_events, stats = scrape_days_for_game(game_key, cfg, today, target_days, existing_uids)

        for ev in new_events:
            cal.add_component(ev)

        total_added += stats["added"]

        # Resumo com contadores
        log(f"- ENCONTRADOS ( {stats['scripts_total']} ) | NÃO PERMITIDOS ( {stats['skipped_not_allowed']} ) | ADICIONADOS ( {stats['added']} )")

        # Exibe jogos encontrados
        if stats["matches"]:
            matches_str = " | ".join([f"{m['teams'].replace(' | ', ' x ')} - {m['time']}" for m in stats["matches"]])
            log(f"- JOGOS {target_days[0].strftime('%d/%m/%Y')} | {matches_str}")

        log("-" * 60)

        if cfg.get("once_per_day", False):
            mark_game_as_run(game_key, state)

        if game_key == "CS2":
            current, next_offset = advance_cs2_offset(state)
            next_day = today + timedelta(days=next_offset)
            log(f"CS2 próximo offset: {next_offset} ({next_day.strftime('%d/%m/%Y')})")
            log("-" * 60)

    # Dedup final
    deduped_final = dedupe_calendar_events(cal)
    if deduped_final > 0:
        log(f"🗑️  Removidos {deduped_final} eventos duplicados (final)")

except Exception as e:
    log(f"❌ ERRO GERAL: {type(e).__name__}: {e}")
    import traceback
    log(f"📍 Stack trace:\n{traceback.format_exc()}")

# Salva
log(f"💾 Salvando {CALENDAR_FILENAME}...")
save_calendar(cal, CALENDAR_FILENAME)
log(f"✅ Concluído | Total adicionados: {total_added}")
log("=" * 60)
