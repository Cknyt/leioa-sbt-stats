"""Tipo de cada pérdida, a partir del jugada a jugada.

- Con robo: el rival anota una recuperación en el mismo segundo (pérdida a balón vivo; la
  presión sí las provoca y suelen acabar en contraataque).
- Falta en ataque: el propio equipo anota una falta en ataque en el mismo segundo.
- Otras: pasos, dobles, campo atrás, fuera de banda, 24 segundos... (balón muerto).
Las pérdidas "de equipo" (sin jugador) no aparecen en el jugada a jugada, así que el total
de aquí puede ser algo menor que el del acta.
"""

import pandas as pd

from leioa_stats.validate import STEAL, TURNOVER

OFFENSIVE_FOUL = 109
TURNOVER_TYPES = ["Con robo", "Falta en ataque", "Otras"]
# Jugadas vecinas que se miran a cada lado de la pérdida.
WINDOW = 3


def _same_moment(a: dict, b: dict) -> bool:
    return (a["period"], a["min"], a["sec"]) == (b["period"], b["min"], b["sec"])


def turnover_type(moves: list[dict], i: int) -> str:
    move = moves[i]
    near = [
        m
        for m in moves[max(0, i - WINDOW) : i + WINDOW + 1]
        if m is not move and _same_moment(m, move)
    ]
    if any(m["idMove"] == STEAL and m["idTeam"] != move["idTeam"] for m in near):
        return "Con robo"
    if any(m["idMove"] == OFFENSIVE_FOUL and m["idTeam"] == move["idTeam"] for m in near):
        return "Falta en ataque"
    return "Otras"


def turnover_rows(match: dict, stats: dict, moves: list[dict]) -> list[dict]:
    """Una fila por equipo y partido con sus pérdidas de cada tipo."""
    names = {t["teamIdIntern"]: t["name"] for t in stats["teams"]}
    other = dict(zip(names, reversed(list(names)), strict=True))
    counts = {team: dict.fromkeys(TURNOVER_TYPES, 0) for team in names}
    for i, move in enumerate(moves):
        if move["idMove"] == TURNOVER and move["idTeam"] in names:
            counts[move["idTeam"]][turnover_type(moves, i)] += 1
    return [
        {"match_id": match["id"], "team": names[t], "opponent": names[other[t]], **c}
        for t, c in counts.items()
    ]


def turnover_profiles(rows: pd.DataFrame) -> pd.DataFrame:
    """Por equipo: pérdidas de cada tipo (propias y forzadas) y % con robo."""
    own = rows.groupby("team")[TURNOVER_TYPES].sum()
    forced = rows.groupby("opponent")[TURNOVER_TYPES].sum()
    profiles = own.join(forced.add_suffix(" forzadas"))
    profiles["% con robo"] = (
        100 * own["Con robo"] / own.sum(axis=1).where(own.sum(axis=1) > 0)
    ).round(1)
    forced_total = forced.sum(axis=1)
    profiles["% con robo forzadas"] = (
        100 * forced["Con robo"] / forced_total.where(forced_total > 0)
    ).round(1)
    return profiles


def live_share(rows: pd.DataFrame) -> float:
    """% de pérdidas con robo en un conjunto de filas (toda la liga, por ejemplo)."""
    total = rows[TURNOVER_TYPES].to_numpy().sum()
    return 100 * rows["Con robo"].sum() / total if total else float("nan")
