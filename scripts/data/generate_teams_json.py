"""
Gera teams.json a partir do config.py para consumo pelo frontend.
Executado pelo workflow do GitHub Actions para manter app.bundle.js sincronizado.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "core"))

from config import (
    CS2_TEAMS,
    CS2_EXCLUSIONS,
    VALORANT_TEAMS,
    ROCKET_LEAGUE_TEAMS,
    LOL_TEAMS,
)


def build_teams_json():
    """Le dados de times do config.py e gera JSON para o frontend."""
    teams_data = {
        "cs2": sorted(CS2_TEAMS),
        "valorant": sorted(VALORANT_TEAMS),
        "rocket": sorted(ROCKET_LEAGUE_TEAMS),
        "lol": sorted(LOL_TEAMS),
    }

    output_path = os.path.join(os.path.dirname(__file__), "teams.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(teams_data, f, indent=2, ensure_ascii=False)

    total = sum(len(v) for v in teams_data.values())
    print(f"teams.json gerado com {total} times ({len(teams_data)} jogos)")
    for game, teams in teams_data.items():
        print(f"  {game}: {len(teams)} times")


if __name__ == "__main__":
    build_teams_json()
