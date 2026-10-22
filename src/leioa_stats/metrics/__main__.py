"""Muestra las métricas de la temporada y las guarda en CSV.

Incluye las básicas, las de tiro, las avanzadas, los quintetos y el +/-.

Uso:
    uv run python -m leioa_stats.metrics
"""

from pathlib import Path

import pandas as pd

from leioa_stats.download import TEAM_NAME, involves
from leioa_stats.metrics.advanced import games_summary, player_usage, team_advanced
from leioa_stats.metrics.basic import player_season, team_season
from leioa_stats.metrics.lineups import lineup_summary, player_on_off, stint_rows
from leioa_stats.metrics.shots import add_zones, zone_summary
from leioa_stats.parse import build_tables, iter_matches

PROCESSED_DIR = Path("data/processed")
# Quintetos a mostrar (los de más minutos).
TOP_LINEUPS = 10
LINEUP_COLUMNS = ["PJ", "MIN", "PTS", "PTS_opp", "+/-", "POSS", "ORtg", "DRtg", "NETO"]

TEAM_COLUMNS = ["PJ", "PTS/PJ", "TC%", "T2%", "T3%", "T1%", "eFG%", "TS%", "RT/PJ", "RO/PJ",
                "RD/PJ", "AS/PJ", "PER/PJ", "REC/PJ", "TAP/PJ", "FP/PJ"]  # fmt: skip
PLAYER_COLUMNS = ["PJ", "TIT", "MIN/PJ", "PTS/PJ", "RT/PJ", "AS/PJ", "PER/PJ", "TCA", "TC%",
                  "T3M", "T3A", "T3%", "T1A", "T1%", "eFG%", "TS%", "USO%", "PTS/40"]  # fmt: skip


def main() -> None:
    tables = build_tables()
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    tables["shots"] = add_zones(tables["shots"])
    # Los partidos descargados son los de toda la liga: aquí solo cuentan los del equipo.
    own_matches = [m for m in iter_matches() if involves(m[0], TEAM_NAME)]
    own_ids = {match["id"] for match, _, _ in own_matches}
    tables["stints"] = pd.DataFrame(
        [row for match in own_matches for row in stint_rows(*match, TEAM_NAME)]
    )
    for name, df in tables.items():
        df.to_csv(PROCESSED_DIR / f"{name}.csv", index=False)

    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 30)
    games = len(own_ids)
    print(f"{TEAM_NAME} - {games} partidos\n")
    print("EQUIPO")
    print(team_season(tables["teams"], TEAM_NAME)[TEAM_COLUMNS].to_string())
    print("\nRITMO, EFICIENCIA Y FOUR FACTORS (en Rivales, lo que permite el equipo)")
    print(team_advanced(tables["teams"], TEAM_NAME).to_string())
    print("\nPOR PARTIDO")
    print(games_summary(tables["teams"], TEAM_NAME).to_string())
    print("\nJUGADORES")
    players = player_season(tables["players"], TEAM_NAME).join(
        player_usage(tables["players"], tables["teams"], TEAM_NAME)
    )
    print(players[PLAYER_COLUMNS].to_string())
    shots = tables["shots"]
    print(f"\nZONAS DE TIRO - {TEAM_NAME}")
    print(zone_summary(shots[shots["team"] == TEAM_NAME]).to_string())
    print("\nZONAS DE TIRO - Rivales")
    rival_shots = shots[shots["match_id"].isin(own_ids) & (shots["team"] != TEAM_NAME)]
    print(zone_summary(rival_shots).to_string())

    stints = tables["stints"]
    leioa_players = tables["players"][tables["players"]["team"] == TEAM_NAME]
    numbers = leioa_players.groupby("player")["number"].last().to_dict()
    lineups = lineup_summary(stints).head(TOP_LINEUPS)
    lineups.index = [
        "-".join(sorted((numbers[p] for p in lineup.split(" | ")), key=int))
        for lineup in lineups.index
    ]
    print(f"\nQUINTETOS (por dorsales; los {TOP_LINEUPS} con más minutos)")
    print(lineups[LINEUP_COLUMNS].to_string())
    incomplete = stints.loc[stints["size"] != 5, "seconds"].sum() / 60
    if incomplete:
        print(
            f"  {incomplete:.1f} minutos sin 5 jugadores en pista (cambio mal anotado) no cuentan"
        )
    legend = sorted(numbers.items(), key=lambda item: int(item[1]))
    print("\nDORSALES: " + ", ".join(f"{number} {player}" for player, number in legend))
    print("\n+/- Y ON/OFF (NETO = diferencia de puntos por 100 posesiones)")
    print(player_on_off(stints).to_string())
    print(f"\nTablas guardadas en {PROCESSED_DIR}/")


if __name__ == "__main__":
    main()
