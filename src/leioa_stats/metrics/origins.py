"""Origen de los puntos, a partir del jugada a jugada (estimación).

Se sigue qué equipo tiene el balón en cada momento:
- Lo gana quien coge un rebote (ofensivo o defensivo) o hace una recuperación.
- Lo pierde quien comete una pérdida o anota una canasta de campo.
- Tras los tiros libres pasa al rival con su siguiente acción (tiro, rebote, pérdida...).
Cada punto se asigna a cómo empezó la posesión en la que se anota:
- 2ª oportunidad: tras un rebote ofensivo propio.
- Tras pérdida: tras una pérdida del rival (o una recuperación propia).
- Contraataque: en los 8 segundos siguientes a un rebote defensivo o una recuperación.
  El umbral de 8 segundos es una convención: el jugada a jugada no dice si hubo contraataque.
Un punto puede ser a la vez "tras pérdida" y "contraataque": no se suman entre sí.
"""

import pandas as pd

from leioa_stats.metrics.lineups import elapsed_seconds
from leioa_stats.validate import (
    DEF_REBOUND,
    FT_MADE,
    FT_MISSED,
    OFF_REBOUND,
    PERIOD_END,
    POINTS,
    STEAL,
    THREE_MISSED,
    TURNOVER,
    TWO_MISSED,
)

FAST_BREAK_SECONDS = 8
# Jugadas en las que el equipo que las hace tiene el balón.
ATTACKING_MOVES = {*POINTS, TWO_MISSED, THREE_MISSED, FT_MISSED, TURNOVER}
ORIGIN_COLUMNS = ["2ª oportunidad", "Tras pérdida", "Contraataque"]


def origin_rows(match: dict, stats: dict, moves: list[dict]) -> list[dict]:
    """Una fila por equipo: puntos, cuántos vienen de cada origen y rebotes ofensivos."""
    names = {t["teamIdIntern"]: t["name"] for t in stats["teams"]}
    other = dict(zip(names, reversed(list(names)), strict=True))
    durations = stats["periodDurationList"]
    counts = {team: dict.fromkeys(["PTS", *ORIGIN_COLUMNS, "RO"], 0) for team in names}
    ball, origin, since = None, None, 0
    for move in moves:
        team, code = move["idTeam"], move["idMove"]
        if code == PERIOD_END:
            ball, origin = None, None
            continue
        if team not in names:
            continue
        now = elapsed_seconds(move, durations)
        if code in ATTACKING_MOVES and ball != team:
            # Ataca sin que se haya visto cómo ganó el balón (saque tras tiros libres, inicio).
            ball, origin, since = team, None, now
        if code in POINTS:
            points = POINTS[code]
            counts[team]["PTS"] += points
            if origin == "offensive":
                counts[team]["2ª oportunidad"] += points
            if origin == "turnover":
                counts[team]["Tras pérdida"] += points
            if origin in ("defensive", "turnover") and now - since <= FAST_BREAK_SECONDS:
                counts[team]["Contraataque"] += points
            if code != FT_MADE:
                ball, origin, since = other[team], None, now
        elif code == OFF_REBOUND:
            counts[team]["RO"] += 1
            ball, origin, since = team, "offensive", now
        elif code == DEF_REBOUND:
            ball, origin, since = team, "defensive", now
        elif code == TURNOVER:
            ball, origin, since = other[team], "turnover", now
        elif code == STEAL:
            ball, origin, since = team, "turnover", now
    return [
        {"match_id": match["id"], "team": names[team], "opponent": names[other[team]], **c}
        for team, c in counts.items()
    ]


def origin_profiles(origins: pd.DataFrame) -> pd.DataFrame:
    """Una fila por equipo: puntos de cada origen por partido, a favor y en contra."""
    grouped = origins.groupby("team")
    games = grouped.size()
    own = grouped[ORIGIN_COLUMNS].sum().div(games, axis=0)
    allowed = origins.groupby("opponent")[ORIGIN_COLUMNS].sum().div(games, axis=0)
    profiles = own.add_suffix("/PJ").join(allowed.add_suffix("/PJ rival")).round(1)
    # Cuánto rinde cada rebote ofensivo (incluye los tiros libres que provoca).
    rebounds = grouped["RO"].sum()
    profiles["PTS/RO"] = (grouped["2ª oportunidad"].sum() / rebounds.where(rebounds > 0)).round(2)
    return profiles


def origin_summary(origins: pd.DataFrame) -> pd.Series:
    """Puntos de cada origen por partido y puntos por rebote ofensivo de un conjunto de filas."""
    summary = (origins[ORIGIN_COLUMNS].sum() / len(origins)).round(1).add_suffix("/PJ")
    rebounds = origins["RO"].sum()
    summary["PTS/RO"] = round(origins["2ª oportunidad"].sum() / rebounds, 2) if rebounds else None
    return summary


def origin_average(origins: pd.DataFrame) -> pd.Series:
    """Media de la liga: en la liga entera, lo que se anota es lo que se encaja."""
    own = origin_summary(origins)
    rival = own.drop("PTS/RO").add_suffix(" rival")
    return pd.concat([own, rival])
