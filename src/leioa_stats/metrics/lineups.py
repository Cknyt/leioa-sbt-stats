"""Quintetos en pista, +/- y on/off a partir del jugada a jugada.

Cómo se reconstruyen:
- Se parte de los cinco titulares y se aplican las entradas y salidas en el orden del
  jugada a jugada. Cada tramo con los mismos jugadores en pista es un "stint".
- Una jugada en el mismo segundo que un cambio cuenta para el quinteto que está en pista
  según ese orden (por ejemplo, los tiros libres tras un cambio). Es el mismo criterio de la
  federación: el +/- reconstruido coincide con el suyo en los partidos 99138 y 99148.
- Los minutos salen del reloj del jugada a jugada, no del box score, que a veces difiere
  hasta en 2-3 minutos.
- Si en algún momento no hay 5 jugadores en pista (cambio mal anotado), ese tramo se marca
  como incompleto y no cuenta para la tabla de quintetos.

Posesiones de cada tramo = media de las de los dos equipos, con la fórmula de
metrics/advanced.py aplicada a las jugadas del tramo. El jugada a jugada no incluye los
rebotes y pérdidas "de equipo", así que es algo menos precisa que la de partido completo.
"""

from collections import Counter

import pandas as pd

from leioa_stats.validate import (
    FT_MADE,
    FT_MISSED,
    OFF_REBOUND,
    SUB_IN,
    SUB_OUT,
    THREE_MADE,
    THREE_MISSED,
    TURNOVER,
    TWO_MADE,
    TWO_MISSED,
)

POINTS = {FT_MADE: 1, TWO_MADE: 2, THREE_MADE: 3}
# Jugada -> contadores que suma para estimar posesiones.
POSSESSION_COUNTERS = {
    TWO_MADE: "TCA",
    TWO_MISSED: "TCA",
    THREE_MADE: "TCA",
    THREE_MISSED: "TCA",
    FT_MADE: "T1A",
    FT_MISSED: "T1A",
    OFF_REBOUND: "RO",
    TURNOVER: "PER",
}
COUNTERS = ["PTS", "TCA", "T1A", "RO", "PER"]


def elapsed_seconds(move: dict, durations: list[int]) -> int:
    """Segundos jugados desde el inicio del partido. El reloj de cada cuarto es descendente."""
    period = move["period"]
    before = sum(durations[: period - 1]) * 60
    return before + durations[period - 1] * 60 - (move["min"] * 60 + move["sec"])


def stint_rows(match: dict, stats: dict, moves: list[dict], team_name: str) -> list[dict]:
    """Tramos del partido con el mismo quinteto del equipo en pista."""
    team = next(t for t in stats["teams"] if t["name"] == team_name)
    team_id = team["teamIdIntern"]
    names = {p["actorId"]: p["name"] for p in team["players"]}
    durations = stats["periodDurationList"]
    on_court = {p["actorId"] for p in team["players"] if p["starting"]}
    rows = []
    start, counts = 0, Counter()

    def close(end: int) -> None:
        # Los cambios en bloque generan tramos de 0 segundos sin jugadas: se descartan.
        if end > start or counts:
            rows.append(
                {
                    "match_id": match["id"],
                    "round": match["round"],
                    "opponent": match["visitor"] if match["local"] == team_name else match["local"],
                    "lineup": " | ".join(sorted(names.get(a, str(a)) for a in on_court)),
                    "size": len(on_court),
                    "start": start,
                    "end": end,
                    "seconds": end - start,
                    **{c: counts[c] for c in COUNTERS},
                    **{f"{c}_opp": counts[f"{c}_opp"] for c in COUNTERS},
                }
            )

    for move in moves:
        now = elapsed_seconds(move, durations)
        if move["idTeam"] == team_id and move["idMove"] in (SUB_IN, SUB_OUT):
            close(now)
            if move["idMove"] == SUB_IN:
                on_court.add(move["actorId"])
            else:
                on_court.discard(move["actorId"])
            start, counts = now, Counter()
            continue
        suffix = "" if move["idTeam"] == team_id else "_opp"
        if move["idMove"] in POINTS:
            counts[f"PTS{suffix}"] += POINTS[move["idMove"]]
        if move["idMove"] in POSSESSION_COUNTERS:
            counts[f"{POSSESSION_COUNTERS[move['idMove']]}{suffix}"] += 1
    close(sum(durations) * 60)
    return rows


def add_ratings(df: pd.DataFrame) -> pd.DataFrame:
    """Añade minutos, +/-, posesiones y eficiencias a una tabla con sumas de tramos."""
    df = df.copy()
    own = df["TCA"] + 0.44 * df["T1A"] - df["RO"] + df["PER"]
    opp = df["TCA_opp"] + 0.44 * df["T1A_opp"] - df["RO_opp"] + df["PER_opp"]
    df["MIN"] = (df["seconds"] / 60).round(1)
    df["+/-"] = df["PTS"] - df["PTS_opp"]
    df["POSS"] = ((own + opp) / 2).round(1)
    poss = df["POSS"].where(df["POSS"] > 0)
    df["ORtg"] = (100 * df["PTS"] / poss).round(1)
    df["DRtg"] = (100 * df["PTS_opp"] / poss).round(1)
    df["NETO"] = (df["ORtg"] - df["DRtg"]).round(1)
    return df


SUM_COLUMNS = ["seconds", *COUNTERS, *[f"{c}_opp" for c in COUNTERS]]


def lineup_summary(stints: pd.DataFrame) -> pd.DataFrame:
    """Minutos, +/- y eficiencia de cada quinteto (solo tramos con 5 jugadores)."""
    complete = stints[stints["size"] == 5]
    summary = complete.groupby("lineup")[SUM_COLUMNS].sum()
    summary["PJ"] = complete.groupby("lineup")["match_id"].nunique()
    return add_ratings(summary).sort_values("seconds", ascending=False)


def player_on_off(stints: pd.DataFrame) -> pd.DataFrame:
    """+/- y eficiencia del equipo con cada jugador en pista y en el banquillo."""
    lineups = stints["lineup"].str.split(" | ", regex=False)
    players = sorted({p for lineup in lineups for p in lineup})
    rows = {}
    for player in players:
        on = lineups.apply(lambda ps, player=player: player in ps)
        on_totals = add_ratings(stints[on][SUM_COLUMNS].sum().to_frame().T).iloc[0]
        off_totals = add_ratings(stints[~on][SUM_COLUMNS].sum().to_frame().T).iloc[0]
        rows[player] = {
            "MIN": on_totals["MIN"],
            "+/-": on_totals["+/-"],
            "NETO en pista": on_totals["NETO"],
            "NETO en banquillo": off_totals["NETO"],
            "DIFERENCIA": round(on_totals["NETO"] - off_totals["NETO"], 1),
        }
    return pd.DataFrame(rows).T.sort_values("MIN", ascending=False)
