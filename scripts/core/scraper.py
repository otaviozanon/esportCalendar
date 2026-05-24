"""
Web scraping de partidas via tips.gg usando Scrape.do como proxy.
"""

import json
import time
from datetime import datetime, date
from typing import Optional, List, Tuple, Set

import pytz
import requests
from bs4 import BeautifulSoup

from config import (
    SCRAPE_DO_API_KEY,
    SCRAPE_DO_URL,
    MAX_RETRIES,
    RETRY_BACKOFF,
    SOURCE_MARKER,
    BR_TZ_NAME,
    match_has_allowed_team,
)
from config import GameConfig, ScrapStats, ScrapedMatch, GameKey
from calendar_manager import build_stable_uid, create_event
from logger import setup_logger

BR_TZ = pytz.timezone(BR_TZ_NAME)
logger = setup_logger("scraper")


def build_url_for_day(base_path: str, target_date: date) -> str:
    """Monta URL da pagina de partidas para uma data especifica no formato DD-MM-YYYY."""
    date_str = target_date.strftime("%d-%m-%Y")
    return f"{base_path}{date_str}/"


def fetch_with_retry(url: str, max_retries: int = MAX_RETRIES) -> Optional[str]:
    """Busca pagina via Scrape.do com retry exponencial. Retorna HTML ou None se falhar."""
    if not SCRAPE_DO_API_KEY:
        logger.error("\u274c API key Scrape.do nao configurada")
        return None

    for attempt in range(max_retries):
        try:
            params = {"token": SCRAPE_DO_API_KEY, "url": url}
            response = requests.get(SCRAPE_DO_URL, params=params, timeout=60)
            response.raise_for_status()
            return response.text
        except requests.exceptions.HTTPError as e:
            logger.warning(
                f"HTTP {e.response.status_code} ao buscar {url} "
                f"(tentativa {attempt + 1}/{max_retries})"
            )
        except requests.exceptions.Timeout:
            logger.warning(
                f"Timeout ao buscar {url} (tentativa {attempt + 1}/{max_retries})"
            )
        except Exception as e:
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
                team1_raw = competitors[0].get("name", "") if len(competitors) > 0 else ""
                team2_raw = competitors[1].get("name", "") if len(competitors) > 1 else ""

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
                description = event.get("name", "")
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
                    f"\U0001f4cd {organizer_name}\n"
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
