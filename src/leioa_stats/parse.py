"""Convierte los JSON descargados en tablas (DataFrames de pandas).

Tablas:
- players: una fila por jugador y partido (box score).
- teams: una fila por equipo y partido, con los totales del equipo (incluye rebotes de equipo).
- shots: una fila por tiro de campo, con sus coordenadas.
"""

import json
from collections.abc import Iterator
from pathlib import Path

import pandas as pd

RAW_DIR = Path("data/raw")

# Columna -> nombre en el box score de la API.
BOX_COLUMNS = {
    "PTS": "score",
    "T1M": "shotsOfOneSuccessful",
    "T1A": "shotsOfOneAttempted",
    "T2M": "shotsOfTwoSuccessful",
    "T2A": "shotsOfTwoAttempted",
    "T3M": "shotsOfThreeSuccessful",
    "T3A": "shotsOfThreeAttempted",
    "RO": "offensiveRebound",
    "RD": "defensiveRebound",
    "AS": "assists",
    "PER": "lost",
    "REC": "steals",
    "TAP": "block",
    "FP": "faults",
    "FR": "faultReceived",
    "VAL": "valoration",
}

# Clave en la API -> (valor del tiro, anotado).
SHOT_KEYS = {
    "shootingOfTwoSuccessfulPoint": (2, True),
    "shootingOfTwoFailedPoint": (2, False),
    "shootingOfThreeSuccessfulPoint": (3, True),
    "shootingOfThreeFailedPoint": (3, False),
}


def match_context(match: dict, stats: dict, team_name: str) -> dict:
    """Columnas comunes a todas las filas de un equipo en un partido."""
    home = match["local"] == team_name
    return {
        "match_id": match["id"],
        "round": match["round"],
        "team": team_name,
        "opponent": match["visitor"] if home else match["local"],
        "home": home,
        # Duración del partido en minutos: 40, o más si hay prórrogas.
        "game_minutes": sum(stats["periodDurationList"]),
    }


def box(data: dict) -> dict:
    return {column: data[field] for column, field in BOX_COLUMNS.items()}


def player_rows(match: dict, stats: dict) -> list[dict]:
    rows = []
    for team in stats["teams"]:
        context = match_context(match, stats, team["name"])
        for player in team["players"]:
            rows.append(
                {
                    **context,
                    "player": player["name"],
                    "number": player["dorsal"],
                    "starter": player["starting"],
                    "MIN": player["timePlayed"],
                    **box(player["data"]),
                }
            )
    return rows


def team_rows(match: dict, stats: dict) -> list[dict]:
    return [
        {**match_context(match, stats, team["name"]), **box(team["data"])}
        for team in stats["teams"]
    ]


def shot_rows(match: dict, stats: dict, moves: list[dict]) -> list[dict]:
    players = {m["eventUuid"]: m["actorName"] for m in moves}
    rows = []
    for team in stats["teams"]:
        context = match_context(match, stats, team["name"])
        for period in team["periods"]:
            for key, (value, made) in SHOT_KEYS.items():
                for point in period.get(key, []):
                    rows.append(
                        {
                            **context,
                            "player": players.get(point["eventUuid"]),
                            "period": point["period"],
                            "value": value,
                            "made": made,
                            "x": point["xnormalize"],
                            "y": point["ynormalize"],
                        }
                    )
    return rows


def iter_matches(raw_dir: Path = RAW_DIR) -> Iterator[tuple[dict, dict, list[dict]]]:
    """Recorre los partidos descargados: (datos del partido, estadísticas, jugada a jugada)."""
    matches = json.loads((raw_dir / "matches.json").read_text(encoding="utf-8"))
    for match in matches:
        match_dir = raw_dir / "matches" / match["id"]
        stats = json.loads((match_dir / "stats.json").read_text(encoding="utf-8"))
        moves = json.loads((match_dir / "moves.json").read_text(encoding="utf-8"))
        yield match, stats, moves


def build_tables(raw_dir: Path = RAW_DIR) -> dict[str, pd.DataFrame]:
    """Lee todos los partidos descargados y devuelve las tablas players, teams y shots."""
    players, teams, shots = [], [], []
    for match, stats, moves in iter_matches(raw_dir):
        players += player_rows(match, stats)
        teams += team_rows(match, stats)
        shots += shot_rows(match, stats, moves)
    return {
        "players": pd.DataFrame(players),
        "teams": pd.DataFrame(teams),
        "shots": pd.DataFrame(shots),
    }
