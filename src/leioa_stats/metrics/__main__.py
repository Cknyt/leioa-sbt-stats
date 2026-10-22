"""Muestra las métricas básicas y de tiro de la temporada y las guarda en CSV.

Uso:
    uv run python -m leioa_stats.metrics
"""

from pathlib import Path

import pandas as pd

from leioa_stats.download import TEAM_NAME
from leioa_stats.metrics.basic import player_season, team_season
from leioa_stats.metrics.shots import add_zones, zone_summary
from leioa_stats.parse import build_tables

PROCESSED_DIR = Path("data/processed")

TEAM_COLUMNS = ["PJ", "PTS/PJ", "TC%", "T2%", "T3%", "T1%", "eFG%", "TS%", "RT/PJ", "RO/PJ",
                "RD/PJ", "AS/PJ", "PER/PJ", "REC/PJ", "TAP/PJ", "FP/PJ"]  # fmt: skip
PLAYER_COLUMNS = ["PJ", "TIT", "MIN/PJ", "PTS/PJ", "RT/PJ", "AS/PJ", "PER/PJ", "TCA", "TC%",
                  "T3M", "T3A", "T3%", "T1A", "T1%", "eFG%", "TS%", "PTS/40"]  # fmt: skip


def main() -> None:
    tables = build_tables()
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    tables["shots"] = add_zones(tables["shots"])
    for name, df in tables.items():
        df.to_csv(PROCESSED_DIR / f"{name}.csv", index=False)

    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 30)
    games = tables["teams"]["match_id"].nunique()
    print(f"{TEAM_NAME} - {games} partidos\n")
    print("EQUIPO")
    print(team_season(tables["teams"], TEAM_NAME)[TEAM_COLUMNS].to_string())
    print("\nJUGADORES")
    print(player_season(tables["players"], TEAM_NAME)[PLAYER_COLUMNS].to_string())
    shots = tables["shots"]
    print(f"\nZONAS DE TIRO - {TEAM_NAME}")
    print(zone_summary(shots[shots["team"] == TEAM_NAME]).to_string())
    print("\nZONAS DE TIRO - Rivales")
    print(zone_summary(shots[shots["team"] != TEAM_NAME]).to_string())
    print(f"\nTablas guardadas en {PROCESSED_DIR}/")


if __name__ == "__main__":
    main()
