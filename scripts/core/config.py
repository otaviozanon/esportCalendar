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

# ==================== APIs DE SCRAPING ====================

# Scrape.do (Fallback)
SCRAPE_DO_API_KEY = os.getenv("SCRAPE_DO_API_KEY", "")
SCRAPE_DO_URL = "https://api.scrape.do/"

# Bright Data (Primario)
BRIGHT_DATA_API_KEY = os.getenv("BRIGHT_DATA_API_KEY", "")
BRIGHT_DATA_URL = "https://api.brightdata.com/request"
BRIGHT_DATA_ZONE = "sport_calendar"

# Configuracoes de retry
MAX_RETRIES = 1  # Reduzido de 3 para 1 (economiza requisicoes)
RETRY_BACKOFF = 1.5

# Configuracoes de eventos ICS
EVENT_DURATION_HOURS = 2
ALARM_MINUTES_BEFORE = 15

# Configuracoes de frequencia (dependem da API ativa)
# Bright Data (primario): CS2 a cada 50min (~27x/dia), outros 2x/dia
# Calculo: 5000 req/mes - (3 jogos × 2x/dia × 5 req × 30 dias) = 4100 req
# 4100 ÷ 5 req = 820 exec/mes ÷ 30 dias = 27 exec/dia = ~50min
CS2_RUN_INTERVAL_MINUTES_BRIGHTDATA = 50
VAL_RL_LOL_RUN_HOURS_BRIGHTDATA = [6, 18]

# Scrape.do (fallback): CS2 3x/dia, outros 1x/dia
CS2_RUN_HOURS_SCRAPEDO = [6, 12, 18]
VAL_RL_LOL_RUN_HOURS_SCRAPEDO = [6]


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

from functools import lru_cache

@lru_cache(maxsize=512)
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
