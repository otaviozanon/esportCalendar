"""
Healthcheck module para monitoramento do GitHub Actions.
Gera healthcheck.json com status da execucao.
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, List

import pytz

HEALTHCHECK_FILE = "scripts/data/healthcheck.json"


def save_healthcheck(
    success: bool,
    total_added: int = 0,
    total_scraped: int = 0,
    errors: List[str] = None,
    execution_time_seconds: float = 0.0,
    games_processed: Dict[str, Dict[str, Any]] = None
) -> None:
    """
    Salva healthcheck JSON para monitoramento.
    
    Args:
        success: Se execucao foi bem-sucedida
        total_added: Total de eventos adicionados
        total_scraped: Total de eventos scrapeados (incluindo filtrados)
        errors: Lista de erros encontrados
        execution_time_seconds: Tempo total de execucao
        games_processed: Detalhes por jogo
    """
    errors = errors or []
    games_processed = games_processed or {}
    
    healthcheck = {
        "timestamp": datetime.now(pytz.utc).isoformat(),
        "success": success,
        "stats": {
            "events_added": total_added,
            "events_scraped": total_scraped,
            "execution_time_seconds": round(execution_time_seconds, 2)
        },
        "games": games_processed,
        "errors": errors,
        "version": "1.0.0"
    }
    
    try:
        with open(HEALTHCHECK_FILE, "w", encoding="utf-8") as f:
            json.dump(healthcheck, f, indent=2)
    except (IOError, PermissionError) as e:
        # Nao falha execucao principal se healthcheck falhar
        print(f"Warning: Falha ao salvar healthcheck: {e}")


def load_healthcheck() -> Dict[str, Any] | None:
    """Carrega ultimo healthcheck. Retorna None se nao existir."""
    if not os.path.exists(HEALTHCHECK_FILE):
        return None
    
    try:
        with open(HEALTHCHECK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, PermissionError):
        return None


def is_healthy() -> bool:
    """Verifica se ultima execucao foi bem-sucedida."""
    healthcheck = load_healthcheck()
    if not healthcheck:
        return False
    return healthcheck.get("success", False)


def get_last_execution_time() -> str | None:
    """Retorna timestamp da ultima execucao."""
    healthcheck = load_healthcheck()
    if not healthcheck:
        return None
    return healthcheck.get("timestamp")


def get_stats() -> Dict[str, Any]:
    """Retorna estatisticas da ultima execucao."""
    healthcheck = load_healthcheck()
    if not healthcheck:
        return {
            "events_added": 0,
            "events_scraped": 0,
            "execution_time_seconds": 0.0
        }
    return healthcheck.get("stats", {})
