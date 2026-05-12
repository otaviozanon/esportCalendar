"""
Esport Calendar Scraper - Raspa eventos de tips.gg e gera calendário ICS.
Versão Profissional e Assíncrona.
"""

import os
import json
import asyncio
import logging
from datetime import datetime, timedelta, date
from typing import Optional, Dict, List, Tuple, Set

import httpx
from bs4 import BeautifulSoup
from icalendar import Event, Alarm
import pytz

from core import (
    GameKey, GameConfig, ScrapedMatch, ScrapStats,
    StateManager, CalendarManager,
    BR_TZ, DELETE_OLDER_THAN_DAYS, SOURCE_MARKER,
    build_stable_uid, normalize_team, setup_logger
)

# -------------------- Configurações de Jogos --------------------
GAMES_CONFIG: Dict[GameKey, GameConfig] = {
    GameKey.CS2: GameConfig(
        prefix="[CS2] ",
        base_path="https://tips.gg/csgo/matches/",
        days_to_scrape=3,
        once_per_day=False,
        run_at_hour=0,
        teams={"FURIA", "paiN Gaming", "MIBR", "Imperial", "Fluxo", "RED Canids", "Legacy", "ODDIK", "Imperial Esports", "Gaimin Gladiators"},
        exclusions={"Imperial.A", "Imperial Fe", "MIBR.A", "paiN.A", "ODDIK.A", "Imperial Academy", "Imperial.Acd", "Imperial Female", "Furia Academy", "Furia.A", "Pain Academy", "Mibr Academy", "Legacy Academy", "ODDIK Academy", "RED Canids Academy", "Fluxo Academy"},
    ),
    GameKey.VAL: GameConfig(
        prefix="[V] ",
        base_path="https://tips.gg/valorant/matches/",
        days_to_scrape=1,
        once_per_day=True,
        run_at_hour=0,
        teams={"LOUD", "FURIA", "MIBR"},
        exclusions=set(),
    ),
    GameKey.RL: GameConfig(
        prefix="[RL] ",
        base_path="https://tips.gg/rl/matches/",
        days_to_scrape=1,
        once_per_day=True,
        run_at_hour=0,
        teams={"FURIA", "Team Secret"},
        exclusions=set(),
    ),
    GameKey.LOL: GameConfig(
        prefix="[LOL] ",
        base_path="https://tips.gg/lol/matches/",
        days_to_scrape=1,
        once_per_day=True,
        run_at_hour=0,
        teams={"paiN Gaming", "LOUD", "Vivo Keyd Stars", "RED Canids"},
        exclusions=set(),
    ),
}

# -------------------- Scraper --------------------
class TipsGGScraper:
    SCRAPE_DO_URL = "https://api.scrape.do"
    MAX_RETRIES = 3

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.logger = setup_logger("scraper")
        if not api_key:
            self.logger.error("❌ SCRAPE_DO_API_KEY não configurada")

    async def fetch_url(self, client: httpx.AsyncClient, url: str) -> Optional[str]:
        for attempt in range(self.MAX_RETRIES):
            try:
                params = {"token": self.api_key, "url": url}
                resp = await client.get(self.SCRAPE_DO_URL, params=params, timeout=60.0)
                resp.raise_for_status()
                return resp.text
            except Exception as e:
                self.logger.warning(f"⚠️ Erro ao buscar {url} (tentativa {attempt+1}/{self.MAX_RETRIES}): {e}")
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(2 ** attempt)
        return None

    def parse_matches(self, html: str, game_key: GameKey, cfg: GameConfig, existing_uids: Set[str]) -> Tuple[List[Event], ScrapStats]:
        stats = ScrapStats()
        events = []
        soup = BeautifulSoup(html, 'html.parser')
        scripts = soup.find_all('script', {'type': 'application/ld+json'})
        
        stats.scripts_total = len(scripts)
        now_utc = datetime.now(pytz.utc)

        for script in scripts:
            try:
                content = script.string
                if not content: continue
                data = json.loads(content)
                items = data.get("@graph", []) or [data]
                
                for item in items:
                    if item.get("@type") != "SportsEvent": continue
                    
                    competitors = item.get("competitor", [])
                    if len(competitors) < 2: continue
                    
                    t1_raw = competitors[0].get("name", "")
                    t2_raw = competitors[1].get("name", "")
                    
                    if not t1_raw or not t2_raw: continue
                    if "TBD" in t1_raw or "TBD" in t2_raw:
                        stats.skipped_tbd += 1
                        continue

                    # Time check
                    try:
                        time_str = item.get("startDate", "")
                        match_time_utc = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                        if match_time_utc.tzinfo is None:
                            match_time_utc = pytz.utc.localize(match_time_utc)
                    except Exception:
                        continue

                    if match_time_utc < now_utc:
                        stats.skipped_past += 1
                        continue

                    # Filter teams
                    t1 = normalize_team(t1_raw)
                    t2 = normalize_team(t2_raw)
                    if not ((t1 in cfg.teams_norm and t1 not in cfg.exclusions_norm) or 
                            (t2 in cfg.teams_norm and t2 not in cfg.exclusions_norm)):
                        stats.skipped_not_allowed += 1
                        continue

                    # Create event
                    summary = f"{cfg.prefix}{t1_raw} vs {t2_raw}"
                    match_url = item.get("url", "")
                    if match_url and not match_url.startswith("http"):
                        match_url = f"https://tips.gg{match_url}"
                    
                    uid = build_stable_uid(game_key, summary, match_time_utc, match_url)
                    if uid in existing_uids: continue

                    event = Event()
                    event.add('summary', summary)
                    event.add('dtstart', match_time_utc)
                    event.add('dtend', match_time_utc + timedelta(hours=2))
                    event.add('uid', uid)
                    event.add('dtstamp', now_utc)
                    
                    tournament = item.get("name", "Tournament")
                    organizer = item.get("organizer", {}).get("name", "Organizer")
                    desc = f"🏆 {tournament}\n📍 {organizer}\n🌐 {match_url}\n{SOURCE_MARKER}"
                    event.add('description', desc)

                    alarm = Alarm()
                    alarm.add('action', 'DISPLAY')
                    alarm.add('trigger', timedelta(minutes=-15))
                    alarm.add('description', f'Lembrete: {summary}')
                    event.add_component(alarm)

                    events.append(event)
                    existing_uids.add(uid)
                    stats.added += 1
                    stats.matches.append(ScrapedMatch(
                        teams=f"{t1_raw} x {t2_raw}",
                        time=match_time_utc.astimezone(BR_TZ).strftime("%H:%M")
                    ))
            except Exception:
                continue
        return events, stats

async def run_game_scrape(scraper: TipsGGScraper, client: httpx.AsyncClient, game_key: GameKey, cfg: GameConfig, target_days: List[date], existing_uids: Set[str]) -> Tuple[List[Event], ScrapStats]:
    all_events = []
    agg_stats = ScrapStats()
    
    for day in target_days:
        url = f"{cfg.base_path}{day.strftime('%d-%m-%Y')}/"
        html = await scraper.fetch_url(client, url)
        if html:
            events, stats = scraper.parse_matches(html, game_key, cfg, existing_uids)
            all_events.extend(events)
            agg_stats.days_scraped += 1
            agg_stats.scripts_total += stats.scripts_total
            agg_stats.added += stats.added
            agg_stats.skipped_tbd += stats.skipped_tbd
            agg_stats.skipped_past += stats.skipped_past
            agg_stats.skipped_not_allowed += stats.skipped_not_allowed
            agg_stats.matches.extend(stats.matches)
    
    return all_events, agg_stats

async def main():
    logger = setup_logger()
    logger.info("=" * 60)
    logger.info("🚀 INICIANDO SCRAPER PROFISSIONAL")
    logger.info("=" * 60)

    cm = CalendarManager()
    sm = StateManager()
    scraper = TipsGGScraper(os.getenv("SCRAPE_DO_API_KEY", ""))
    
    now = datetime.now(BR_TZ)
    today = now.date()

    # Initial cleanup
    removed_dupes = cm.dedupe()
    if removed_dupes: logger.info(f"🗑️  Removidos {removed_dupes} duplicados")
    
    cutoff = today - timedelta(days=DELETE_OLDER_THAN_DAYS)
    removed_old = cm.prune_old(cutoff)
    if removed_old: logger.info(f"🗑️  Removidos {removed_old} antigos (< {cutoff})")

    existing_uids = cm.get_uids()
    total_added = 0

    async with httpx.AsyncClient(http2=True) as client:
        tasks = []
        for game_key, cfg in GAMES_CONFIG.items():
            if not sm.should_run(game_key, cfg, now):
                logger.info(f"⏭️  {game_key.value} pulado (já executado ou fora do horário)")
                continue

            if game_key == GameKey.CS2:
                target_days = [today + timedelta(days=sm.cs2_offset)]
                logger.info(f"📅 {game_key.value} | Offset {sm.cs2_offset} | Alvo: {target_days[0]}")
            else:
                target_days = [today]
                logger.info(f"📅 {game_key.value} | Alvo: {today}")

            tasks.append((game_key, cfg, target_days))

        if not tasks:
            logger.info("✅ Nada para processar agora.")
        else:
            results = await asyncio.gather(*(run_game_scrape(scraper, client, g, c, d, existing_uids) for g, c, d in tasks))
            
            for (game_key, cfg, _), (events, stats) in zip(tasks, results):
                for ev in events:
                    cm.add_event(ev)
                total_added += stats.added
                
                logger.info(f"✅ {game_key.value}: Scripts({stats.scripts_total}) | Add({stats.added}) | Skip({stats.skipped_not_allowed})")
                if stats.matches:
                    matches_str = " | ".join([f"{m.teams} ({m.time})" for m in stats.matches])
                    logger.info(f"   Matches: {matches_str}")

                # Update state
                if cfg.once_per_day:
                    sm.mark_as_run(game_key)
                if game_key == GameKey.CS2:
                    next_offset = sm.advance_cs2_offset()
                    logger.info(f"   Próximo offset CS2: {next_offset}")

    if total_added > 0:
        cm.dedupe()
        cm.save()
        logger.info(f"💾 Calendário salvo com {total_added} novos eventos.")
    else:
        logger.info("ℹ️  Nenhum evento novo adicionado.")

    logger.info("=" * 60)
    logger.info("✅ FIM DA EXECUÇÃO")
    logger.info("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
