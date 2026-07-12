"""
Web scraping de partidas via tips.gg com fallback automatico entre APIs.
Primario: Bright Data (5k req/mes) | Fallback: Scrape.do (1k req/mes)
"""

import json
import time
from datetime import datetime, date
from typing import Optional, List, Tuple, Set
from enum import Enum

import pytz
import requests
from bs4 import BeautifulSoup

from config import (
    SCRAPE_DO_API_KEY,
    SCRAPE_DO_URL,
    BRIGHT_DATA_API_KEY,
    BRIGHT_DATA_URL,
    BRIGHT_DATA_ZONE,
    MAX_RETRIES,
    RETRY_BACKOFF,
    SOURCE_MARKER,
    BR_TZ_NAME,
    match_has_allowed_team,
)


class ScraperAPI(str, Enum):
    """APIs de scraping disponiveis."""
    BRIGHT_DATA = "brightdata"
    SCRAPE_DO = "scrapedo"
from config import GameConfig, ScrapStats, ScrapedMatch, GameKey
from calendar_manager import build_stable_uid, create_event
from logger import setup_logger

BR_TZ = pytz.timezone(BR_TZ_NAME)
logger = setup_logger("scraper")

# Session reutilizavel para keep-alive
_session = requests.Session()
_last_request_time = 0.0
MIN_REQUEST_INTERVAL = 1.0

# API ativa (comeca com BrightData, faz fallback para Scrape.do se falhar)
_active_api: ScraperAPI = ScraperAPI.BRIGHT_DATA
_brightdata_failed_count = 0
_max_brightdata_failures = 3  # Apos 3 falhas consecutivas, usa Scrape.do


def get_active_api() -> ScraperAPI:
    """Retorna API ativa (com fallback automatico)."""
    return _active_api


def set_active_api(api: ScraperAPI) -> None:
    """Define API ativa."""
    global _active_api
    _active_api = api
    logger.info(f"🔄 API ativa: {api.value.upper()}")


def build_url_for_day(base_path: str, target_date: date) -> str:
    """Monta URL da pagina de partidas para uma data especifica no formato DD-MM-YYYY."""
    date_str = target_date.strftime("%d-%m-%Y")
    return f"{base_path}{date_str}/"


def _fetch_brightdata(url: str, timeout: int = 60) -> Optional[str]:
    """Busca via Bright Data Web Unlocker API."""
    if not BRIGHT_DATA_API_KEY:
        logger.error("❌ Bright Data API key nao configurada")
        return None

    headers = {
        "Authorization": f"Bearer {BRIGHT_DATA_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "zone": BRIGHT_DATA_ZONE,
        "url": url,
        "format": "raw"
    }

    try:
        response = _session.post(BRIGHT_DATA_URL, headers=headers, json=payload, timeout=timeout)
        response.raise_for_status()
        return response.text
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code
        # Erros que indicam limite atingido ou necessidade de fallback
        if status in [402, 429, 403]:
            logger.warning(f"⚠️  Bright Data erro {status} (limite/bloqueio) - usando fallback")
            return None
        raise
    except Exception:
        raise


def _fetch_scrapedo(url: str, timeout: int = 60) -> Optional[str]:
    """Busca via Scrape.do."""
    if not SCRAPE_DO_API_KEY:
        logger.error("❌ Scrape.do API key nao configurada")
        return None

    params = {
        "token": SCRAPE_DO_API_KEY,
        "url": url,
        "render": "true"
    }

    response = _session.get(SCRAPE_DO_URL, params=params, timeout=timeout)
    response.raise_for_status()
    return response.text


def fetch_with_retry(url: str, max_retries: int = MAX_RETRIES) -> Optional[str]:
    """
    Busca pagina com retry e fallback automatico entre APIs.
    Tenta Bright Data primeiro, faz fallback para Scrape.do se falhar.
    """
    global _last_request_time, _active_api, _brightdata_failed_count

    for attempt in range(max_retries):
        try:
            # Rate limiting
            elapsed = time.time() - _last_request_time
            if elapsed < MIN_REQUEST_INTERVAL:
                time.sleep(MIN_REQUEST_INTERVAL - elapsed)

            timeout = 60 if attempt == 0 else 90

            # Tenta API ativa
            if _active_api == ScraperAPI.BRIGHT_DATA:
                try:
                    html = _fetch_brightdata(url, timeout)
                    if html:
                        _last_request_time = time.time()
                        _brightdata_failed_count = 0  # Reset contador de falhas
                        return html
                    else:
                        # Bright Data retornou None (limite atingido)
                        _brightdata_failed_count += 1
                        if _brightdata_failed_count >= _max_brightdata_failures:
                            logger.warning(
                                f"⚠️  Bright Data falhou {_brightdata_failed_count}x "
                                f"- mudando para Scrape.do permanentemente"
                            )
                            set_active_api(ScraperAPI.SCRAPE_DO)
                        # Tenta Scrape.do como fallback
                        logger.info("🔄 Tentando Scrape.do como fallback...")
                        html = _fetch_scrapedo(url, timeout)
                except Exception as e:
                    logger.warning(f"Bright Data erro: {type(e).__name__} - tentando Scrape.do")
                    _brightdata_failed_count += 1
                    html = _fetch_scrapedo(url, timeout)
            else:
                # Scrape.do como API principal
                html = _fetch_scrapedo(url, timeout)

            if html:
                _last_request_time = time.time()
                return html

        except requests.exceptions.HTTPError as e:
            logger.warning(
                f"HTTP {e.response.status_code} ao buscar {url} "
                f"(tentativa {attempt + 1}/{max_retries})"
            )
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout ao buscar {url} (tentativa {attempt + 1}/{max_retries})")
        except (requests.exceptions.RequestException, ConnectionError) as e:
            logger.warning(
                f"Erro ao buscar {url}: {type(e).__name__} "
                f"(tentativa {attempt + 1}/{max_retries})"
            )

        if attempt < max_retries - 1:
            wait_time = RETRY_BACKOFF**attempt
            logger.info(f"Aguardando {wait_time:.1f}s antes de retry...")
            time.sleep(wait_time)

    return None


def parse_event_time(match_time_str: str) -> Optional[datetime]:
    """Converte string ISO 8601 para datetime UTC. Retorna None se invalido."""
    try:
        dt = datetime.fromisoformat(match_time_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = pytz.utc.localize(dt)
        return dt.astimezone(pytz.utc)
    except Exception:
        return None


def clean_tournament_name(raw_name: str, team1: str, team2: str) -> str:
    match_prefix = f"{team1} vs {team2}"
    if raw_name.startswith(match_prefix):
        raw_name = raw_name[len(match_prefix):].strip()
        if raw_name.startswith(","):
            raw_name = raw_name[1:].strip()
    return raw_name


def scrape_days_for_game(
    game_key: str,
    cfg: GameConfig,
    target_days: List[date],
    existing_uids: Set[str],
) -> Tuple[List, ScrapStats]:
    """Scrapeia partidas para dias-alvo. Filtra por times permitidos, gera eventos ICS. Retorna (eventos, stats)."""
    stats = ScrapStats()
    new_events = []

    for target_day in target_days:
        url = build_url_for_day(cfg.base_path, target_day)
        html = fetch_with_retry(url)

        if not html:
            continue

        try:
            # Usa lxml parser (2-3x mais rapido que html.parser) com fallback
            try:
                soup = BeautifulSoup(html, "lxml")
            except Exception:
                soup = BeautifulSoup(html, "html.parser")

            scripts = soup.find_all("script", {"type": "application/ld+json"})
        except Exception as e:
            logger.warning(
                f"Erro ao parsear HTML de {target_day.strftime('%d/%m/%Y')}: "
                f"{type(e).__name__}"
            )
            continue

        stats.days_scraped += 1
        stats.scripts_total += len(scripts)

        now_utc = datetime.now(pytz.utc)

        for script in scripts:
            try:
                # Validar se script.string existe antes de parsear
                if not script.string:
                    continue
                data = json.loads(script.string)
            except json.JSONDecodeError:
                continue

            if not isinstance(data, dict):
                continue

            events = data.get("@graph", []) or [data]

            for event in events:
                if event.get("@type") != "SportsEvent":
                    continue

                competitors = event.get("competitor", [])

                # Validar competitors antes de acessar
                if not isinstance(competitors, list) or len(competitors) < 2:
                    continue

                team1_raw = competitors[0].get("name", "")
                team2_raw = competitors[1].get("name", "")

                if not team1_raw or not team2_raw:
                    continue

                if "TBD" in team1_raw or "TBD" in team2_raw:
                    stats.skipped_tbd += 1
                    continue

                match_time_utc = parse_event_time(event.get("startDate", ""))
                if not match_time_utc:
                    continue

                if match_time_utc < now_utc:
                    stats.skipped_past += 1
                    continue

                if not match_has_allowed_team(team1_raw, team2_raw, cfg):
                    stats.skipped_not_allowed += 1
                    continue

                event_summary = f"{cfg.prefix}{team1_raw} vs {team2_raw}"
                description = clean_tournament_name(event.get("name", ""), team1_raw, team2_raw)
                organizer_name = event.get("organizer", {}).get("name", "")
                match_url = event.get("url", "")

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

                if event_uid in existing_uids:
                    continue

                match_time_br = match_time_utc.astimezone(BR_TZ)
                stats.matches.append(
                    ScrapedMatch(
                        teams=f"{team1_raw} x {team2_raw}",
                        time=match_time_br.strftime("%H:%M"),
                    )
                )

                event_description = (
                    f"\U0001f3c6 {description}\n"
                    f"\U0001f310 {match_url}\n"
                    f"{SOURCE_MARKER}"
                )

                cal_event = create_event(
                    summary=event_summary,
                    start_utc=match_time_utc,
                    description=event_description,
                    uid=event_uid,
                )

                new_events.append(cal_event)
                existing_uids.add(event_uid)
                stats.added += 1

    return new_events, stats
