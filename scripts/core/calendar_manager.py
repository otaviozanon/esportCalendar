"""
Operacoes de calendario ICS: carga, salvamento, deduplicacao e limpeza.
"""

import hashlib
import os
import re
from datetime import datetime, date, timedelta
from typing import Set, List

import pytz
from icalendar import Calendar, Event, Alarm

from config import (
    CALENDAR_FILENAME,
    BR_TZ_NAME,
    SOURCE_MARKER,
    TIPS_URL_HINT,
    DELETE_OLDER_THAN_DAYS,
    EVENT_DURATION_HOURS,
    ALARM_MINUTES_BEFORE,
)

BR_TZ = pytz.timezone(BR_TZ_NAME)

# Regex compilado para extrair URL (3x mais rapido)
URL_PATTERN = re.compile(r'\U0001f310\s*(.+)', re.MULTILINE)


def _ensure_calendar_props(cal: Calendar) -> None:
    props = {
        "x-wr-calname": "eSports Calendar",
        "x-wr-caldesc": "Calendario de jogos de eSports",
        "x-wr-timezone": BR_TZ_NAME,
        "refresh-interval;VALUE=DURATION": "PT1H",
        "x-published-ttl": "PT1H",
    }
    for key, value in props.items():
        if key not in cal:
            cal.add(key, value)


def load_calendar(path: str = CALENDAR_FILENAME) -> Calendar:
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                cal = Calendar.from_ical(f.read())
                _ensure_calendar_props(cal)
                return cal
        except (FileNotFoundError, ValueError, PermissionError):
            pass

    cal = Calendar()
    cal.add("prodid", "-//Esport Calendar BR//tips.gg//")
    cal.add("version", "2.0")
    _ensure_calendar_props(cal)
    return cal


def save_calendar(cal: Calendar, path: str = CALENDAR_FILENAME) -> bool:
    """Salva calendario ICS em disco. Levanta IOError em caso de falha."""
    try:
        with open(path, "wb") as f:
            f.write(cal.to_ical())
        return True
    except (IOError, PermissionError) as e:
        raise IOError(f"Erro ao salvar {path}: {e}")


def get_existing_uids(cal: Calendar) -> Set[str]:
    """Coleta todos UIDs ja existentes no calendario para evitar duplicatas."""
    return {
        str(comp.get("uid"))
        for comp in cal.walk("VEVENT")
        if comp.get("uid")
    }


def is_ours(component) -> bool:
    """Verifica se evento foi gerado por este scraper (marcador no description)."""
    desc = str(component.get("description", ""))
    return SOURCE_MARKER in desc or TIPS_URL_HINT in desc


def _event_start_date_local(component) -> date | None:
    """Extrai data de inicio do evento convertida para timezone local (BRT)."""
    try:
        dt = component.get("dtstart").dt
        if isinstance(dt, datetime):
            if dt.tzinfo is None:
                dt = pytz.utc.localize(dt)
            return dt.astimezone(BR_TZ).date()
        elif isinstance(dt, date):
            return dt
    except (AttributeError, ValueError, TypeError):
        pass
    return None


def dedupe_by_uid(cal: Calendar) -> int:
    """Remove eventos duplicados por UID. Mantem primeira ocorrencia. Retorna qtd removida."""
    seen = set()
    unique_components = []
    removed = 0

    # Coleta todos componentes, mantendo apenas eventos unicos
    for comp in cal.subcomponents[:]:
        if comp.name == 'VEVENT':
            if not is_ours(comp):
                unique_components.append(comp)
                continue

            uid = str(comp.get("uid", ""))
            if uid not in seen:
                seen.add(uid)
                unique_components.append(comp)
            else:
                removed += 1
        else:
            unique_components.append(comp)

    # Reconstroi subcomponents uma unica vez (O(n) ao inves de O(n²))
    cal.subcomponents = unique_components
    return removed


def dedupe_by_url(cal: Calendar) -> int:
    """Remove eventos duplicados por URL (link da partida). Remove os duplicados, mantem o primeiro."""
    url_seen = set()
    unique_components = []
    removed = 0

    for comp in cal.subcomponents[:]:
        if comp.name == 'VEVENT':
            if not is_ours(comp):
                unique_components.append(comp)
                continue

            desc = str(comp.get("description", ""))

            # Usa regex compilado (3x mais rapido)
            match = URL_PATTERN.search(desc)
            url = match.group(1).strip() if match else None

            if url:
                if url not in url_seen:
                    url_seen.add(url)
                    unique_components.append(comp)
                else:
                    removed += 1
            else:
                unique_components.append(comp)
        else:
            unique_components.append(comp)

    cal.subcomponents = unique_components
    return removed


def prune_older_than(cal: Calendar, cutoff_date: date) -> int:
    """Remove eventos cuja data de inicio eh anterior a data de corte."""
    unique_components = []
    removed = 0

    for comp in cal.subcomponents[:]:
        if comp.name == 'VEVENT':
            if is_ours(comp):
                event_date = _event_start_date_local(comp)
                if event_date and event_date < cutoff_date:
                    removed += 1
                    continue
            unique_components.append(comp)
        else:
            unique_components.append(comp)

    cal.subcomponents = unique_components
    return removed


def remove_events_by_prefix(cal: Calendar, prefix: str) -> int:
    """Remove todos eventos cujo summary comeca com o prefixo informado (ex: '[CS2]'). Retorna qtd removida."""
    removed = 0
    to_remove = [
        comp
        for comp in list(cal.walk("VEVENT"))
        if str(comp.get("summary", "")).startswith(prefix)
    ]
    for comp in to_remove:
        cal.subcomponents.remove(comp)
        removed += 1
    return removed


def normalize_event_datetime_utc(dt: datetime) -> datetime:
    """Converte datetime para UTC, remove segundos e microssegundos para comparacao estavel."""
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    return dt.astimezone(pytz.utc).replace(microsecond=0, second=0)


def build_stable_uid(
    game_key: str,
    event_summary: str,
    match_time_utc: datetime,
    tournament_desc: str,
    organizer_name: str,
    match_url: str,
) -> str:
    """Gera UID estavel via SHA256 com campos chave da partida. Mesmo jogo = mesmo UID."""
    data = f"{game_key}|{event_summary}|{match_time_utc.isoformat()}|{tournament_desc}|{organizer_name}|{match_url}"
    return hashlib.sha256(data.encode()).hexdigest()


def create_event(
    summary: str,
    start_utc: datetime,
    description: str,
    uid: str,
) -> Event:
    """Cria evento ICS com alarme e duracao configuravel. Tudo em UTC."""
    e = Event()
    e.add("summary", summary)
    e.add("dtstart", normalize_event_datetime_utc(start_utc))
    e.add("dtend", normalize_event_datetime_utc(start_utc) + timedelta(hours=EVENT_DURATION_HOURS))
    e.add("description", description)
    e.add("uid", uid)
    e.add("dtstamp", datetime.now(pytz.utc))

    alarm = Alarm()
    alarm.add("action", "DISPLAY")
    alarm.add("trigger", timedelta(minutes=-ALARM_MINUTES_BEFORE))
    alarm.add("description", f"Lembrete: {summary}")
    e.add_component(alarm)

    return e


class CalendarManager:
    """Fachada para operacoes de calendario: carrega, remove por prefixo, salva."""

    def __init__(self, calendar_path: str = None):
        self._path = calendar_path or CALENDAR_FILENAME
        self._calendar = load_calendar(self._path)

    def remove_events_by_prefix(self, prefix: str) -> int:
        """Remove eventos com summary iniciado por prefixo. Retorna quantidade removida."""
        return remove_events_by_prefix(self._calendar, prefix)

    def save(self) -> bool:
        """Persiste calendario em disco. Retorna True se sucesso, False se erro."""
        try:
            save_calendar(self._calendar, self._path)
            return True
        except Exception:
            return False


def cleanup_cs2_events() -> bool:
    """Remove todos eventos com prefixo [CS2] do calendario. Retorna True se sucesso."""
    from logger import setup_logger
    logger = setup_logger("delete_cs2")
    logger.info("=" * 60)
    logger.info("\U0001f680 INICIANDO LIMPEZA DE EVENTOS CS2")
    logger.info("=" * 60)

    cm = CalendarManager()
    prefix = "[CS2]"
    logger.info(f"\U0001f50d Procurando eventos com prefixo '{prefix}'...")

    removed = cm.remove_events_by_prefix(prefix)

    if removed > 0:
        logger.info(f"\U0001f5d1\ufe0f  REMOVIDOS: {removed} eventos")
        if cm.save():
            logger.info("\U0001f4be Calendario atualizado com sucesso.")
        else:
            logger.error("\u274c Falha ao salvar o calendario.")
            return False
    else:
        logger.info(f"\u2139\ufe0f  Nenhum evento '{prefix}' encontrado.")

    logger.info("=" * 60)
    logger.info("\u2705 CONCLUIDO")
    logger.info("=" * 60)
    return True
