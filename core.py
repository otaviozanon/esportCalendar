import os
import json
import logging
import hashlib
from datetime import datetime, timedelta, date
from typing import Optional, Dict, Set, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

import pytz
from icalendar import Calendar, Event, Alarm

# -------------------- Configurações Globais --------------------
CALENDAR_FILENAME = "calendar.ics"
STATE_FILE = "state.json"
LOG_LEVEL = logging.INFO
BR_TZ = pytz.timezone("America/Sao_Paulo")
DELETE_OLDER_THAN_DAYS = 7

# Marcadores para o ICS
SOURCE_MARKER = "X-SETT-SOURCE:TIPSGG"
TIPS_URL_HINT = "https://tips.gg/matches/"

# -------------------- Enums & Modelos --------------------
class GameKey(str, Enum):
    CS2 = "CS2"
    VAL = "VAL"
    RL = "RL"
    LOL = "LOL"

@dataclass
class GameConfig:
    prefix: str
    base_path: str
    days_to_scrape: int
    once_per_day: bool
    run_at_hour: int
    teams: Set[str]
    exclusions: Set[str]
    teams_norm: Set[str] = field(init=False)
    exclusions_norm: Set[str] = field(init=False)

    def __post_init__(self):
        self.teams_norm = {t.lower().strip() for t in self.teams}
        self.exclusions_norm = {t.lower().strip() for t in self.exclusions}

@dataclass
class ScrapedMatch:
    teams: str
    time: str

@dataclass
class ScrapStats:
    days_scraped: int = 0
    scripts_total: int = 0
    added: int = 0
    skipped_tbd: int = 0
    skipped_past: int = 0
    skipped_not_allowed: int = 0
    matches: List[ScrapedMatch] = field(default_factory=list)

# -------------------- Logger --------------------
def setup_logger(name: str = "esport_calendar") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(LOG_LEVEL)
        handler = logging.StreamHandler()
        formatter = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

logger = setup_logger()

# -------------------- Gerenciador de Estado --------------------
class StateManager:
    def __init__(self, path: str = STATE_FILE):
        self.path = path
        self.data = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"last_run": {}, "cs2_day_offset": 0}

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Erro ao salvar {self.path}: {e}")

    def should_run(self, game_key: str, cfg: GameConfig, now: datetime) -> bool:
        if not cfg.once_per_day:
            return True
        if now.hour < cfg.run_at_hour:
            return False
        last = self.data.get("last_run", {}).get(game_key)
        return last != now.strftime("%Y-%m-%d")

    def mark_as_run(self, game_key: str):
        if "last_run" not in self.data:
            self.data["last_run"] = {}
        self.data["last_run"][game_key] = datetime.now(BR_TZ).strftime("%Y-%m-%d")
        self.save()

    @property
    def cs2_offset(self) -> int:
        return self.data.get("cs2_day_offset", 0)

    def advance_cs2_offset(self) -> int:
        current = self.cs2_offset
        next_offset = (current + 1) % 3
        self.data["cs2_day_offset"] = next_offset
        self.save()
        return next_offset

# -------------------- Gerenciador de Calendário --------------------
class CalendarManager:
    def __init__(self, path: str = CALENDAR_FILENAME):
        self.path = path
        self.cal = self._load()

    def _load(self) -> Calendar:
        if os.path.exists(self.path):
            try:
                with open(self.path, "rb") as f:
                    return Calendar.from_ical(f.read())
            except Exception as e:
                logger.warning(f"⚠️ Falha ao ler {self.path}: {e}. Criando novo.")
        
        cal = Calendar()
        cal.add('prodid', '-//Esport Calendar BR//tips.gg//')
        cal.add('version', '2.0')
        return cal

    def save(self) -> bool:
        try:
            with open(self.path, "wb") as f:
                f.write(self.cal.to_ical())
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao salvar {self.path}: {e}")
            return False

    def get_uids(self) -> Set[str]:
        return {str(c.get('uid')) for c in self.cal.walk('VEVENT') if c.get('uid')}

    def add_event(self, event: Event):
        self.cal.add_component(event)

    def dedupe(self) -> int:
        seen_uids = {}
        to_remove = []
        for component in list(self.cal.walk('VEVENT')):
            if not self._is_ours(component):
                continue
            uid = str(component.get('uid', ''))
            if uid in seen_uids:
                to_remove.append(component)
            else:
                seen_uids[uid] = component
        
        for comp in to_remove:
            self.cal.subcomponents.remove(comp)
        return len(to_remove)

    def prune_old(self, cutoff: date) -> int:
        removed = 0
        for comp in list(self.cal.walk('VEVENT')):
            if not self._is_ours(comp):
                continue
            dtstart = comp.get('dtstart').dt
            event_date = dtstart.date() if isinstance(dtstart, datetime) else dtstart
            
            # Ajuste para timezone se for datetime
            if isinstance(dtstart, datetime):
                if dtstart.tzinfo is None:
                    dtstart = pytz.utc.localize(dtstart)
                event_date = dtstart.astimezone(BR_TZ).date()

            if event_date < cutoff:
                self.cal.subcomponents.remove(comp)
                removed += 1
        return removed

    def remove_events_by_prefix(self, prefix: str) -> int:
        removed = 0
        for comp in list(self.cal.walk('VEVENT')):
            summary = str(comp.get('summary', ''))
            if summary.startswith(prefix):
                self.cal.subcomponents.remove(comp)
                removed += 1
        return removed

    def _is_ours(self, component) -> bool:
        desc = str(component.get('description', ''))
        return SOURCE_MARKER in desc or TIPS_URL_HINT in component.get('url', '') or TIPS_URL_HINT in desc

# -------------------- Utils --------------------
def build_stable_uid(game_key: str, summary: str, match_time_utc: datetime, url: str) -> str:
    data = f"{game_key}|{summary}|{match_time_utc.isoformat()}|{url}"
    return hashlib.sha256(data.encode()).hexdigest()

def normalize_team(name: str) -> str:
    return (name or "").lower().strip()
