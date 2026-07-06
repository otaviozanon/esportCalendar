"""
Configuracoes centrais, modelos de dados e logica de filtragem de times.
"""

import os
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Optional, Dict, Set, List, Tuple


# ==================== CONSTANTES ====================

CALENDAR_FILENAME = "calendar.ics"
STATE_FILE = "scripts/data/state.json"
LOG_LEVEL = "INFO"

BR_TZ_NAME = "America/Sao_Paulo"
DELETE_OLDER_THAN_DAYS = 7

SOURCE_MARKER = "X-SETT-SOURCE:TIPSGG"
TIPS_URL_HINT = "https://tips.gg/matches/"

SCRAPE_DO_API_KEY = os.getenv("SCRAPE_DO_API_KEY", "")
SCRAPE_DO_URL = "https://api.scrape.do"

MAX_RETRIES = 3
RETRY_BACKOFF = 1.5


# ==================== MODELOS ====================

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

    def __post_init__(self):
        self.teams_norm = {self._normalize(t) for t in self.teams}
        self.exclusions_norm = {self._normalize(t) for t in self.exclusions}

    @staticmethod
    def _normalize(name: str) -> str:
        return (name or "").lower().strip()


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


# ==================== TIMES ====================

CS2_TEAMS = {
    "FURIA",
    "paiN Gaming",
    "MIBR",
    "Imperial",
    "Fluxo",
    "RED Canids",
    "Legacy",
    "ODDIK",
    "Imperial Esports",
    "Gaimin Gladiators",
}

CS2_EXCLUSIONS = {
    "Imperial.A",
    "Imperial Fe",
    "MIBR.A",
    "paiN.A",
    "ODDIK.A",
    "Imperial Academy",
    "Imperial.Acd",
    "Imperial Female",
    "Furia Academy",
    "Furia.A",
    "Pain Academy",
    "Mibr Academy",
    "Legacy Academy",
    "ODDIK Academy",
    "RED Canids Academy",
    "Fluxo Academy",
}

VALORANT_TEAMS = {
    "LOUD",
    "FURIA Esports",
    "MIBR LOS",
    "Team Liquid Brazil",
}

ROCKET_LEAGUE_TEAMS = {
    "FURIA Esports",
    "Team Secret",
}

LOL_TEAMS = {
    "paiN Gaming",
    "LOUD",
    "Vivo Keyd Stars",
    "RED Canids",
    "FURIA"
}


# ==================== FILTROS ====================

def normalize_team(name: str) -> str:
    """Normaliza nome do time: lowercase + strip para comparacao case-insensitive."""
    return (name or "").lower().strip()


def is_team_allowed(team_raw: str, cfg: GameConfig) -> bool:
    """Time permitido se esta na whitelist e nao esta nas exclusoes do jogo."""
    normalized = normalize_team(team_raw)
    return normalized in cfg.teams_norm and normalized not in cfg.exclusions_norm


def match_has_allowed_team(team1_raw: str, team2_raw: str, cfg: GameConfig) -> bool:
    """Partida valida se pelo menos um dos times eh permitido."""
    return is_team_allowed(team1_raw, cfg) or is_team_allowed(team2_raw, cfg)
