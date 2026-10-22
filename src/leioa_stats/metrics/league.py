"""Métricas de toda la liga: clasificación avanzada y perfil de juego de cada jugador.

Perfil de juego (estimación: la federación no publica posiciones). Se deduce de dónde tira
el jugador y de cuántos rebotes ofensivos coge:
- Interior: la mitad o más de sus tiros de campo son cerca del aro (< 3 m), o casi no tira
  triples (< 15 % de sus tiros) y coge 3 o más rebotes ofensivos por 40 minutos.
- Exterior: la mitad o más de sus tiros de campo son triples.
- Mixto: el resto.
Con menos de 10 tiros de campo no se estima.
"""

import pandas as pd

from leioa_stats.metrics.advanced import four_factors, ratings, team_games
from leioa_stats.metrics.shots import add_zones

MIN_ATTEMPTS_FOR_PROFILE = 10

LEAGUE_COLUMNS = ["PJ", "V", "D", "RITMO", "ORtg", "DRtg", "NETO", "eFG%", "PER%", "RO%",
                  "TL/TC", "eFG% rival", "PER% rival", "RO% rival", "TL/TC rival"]  # fmt: skip


def league_table(teams: pd.DataFrame) -> pd.DataFrame:
    """Una fila por equipo: balance, ritmo, eficiencia y Four Factors (propios y permitidos)."""
    games = team_games(teams)
    rows = {}
    for team, team_rows in games.groupby("team"):
        own = four_factors(team_rows)
        allowed = four_factors(team_rows, "_opp").add_suffix(" rival")
        wins = int((team_rows["PTS"] > team_rows["PTS_opp"]).sum())
        rows[team] = pd.concat(
            [
                pd.Series({"PJ": len(team_rows), "V": wins, "D": len(team_rows) - wins}),
                ratings(team_rows),
                own,
                allowed,
            ]
        )
    table = pd.DataFrame(rows).T[LEAGUE_COLUMNS]
    table[["PJ", "V", "D"]] = table[["PJ", "V", "D"]].astype(int)
    return table.round(1).sort_values(["V", "NETO"], ascending=False)


def league_average(teams: pd.DataFrame) -> pd.Series:
    """Media de la liga: ritmo, eficiencia y Four Factors de todos los partidos juntos."""
    games = team_games(teams)
    return pd.concat([ratings(games), four_factors(games)]).round(1)


def ranks(table: pd.DataFrame, team: str) -> dict[str, int]:
    """Puesto del equipo en la liga en cada métrica (1 = el mejor; en RITMO, el más rápido)."""
    # En estas métricas, cuanto más bajo, mejor.
    lower_is_better = {"DRtg", "PER%"}
    return {
        column: int(table[column].rank(ascending=column in lower_is_better, method="min")[team])
        for column in ["RITMO", "ORtg", "DRtg", "NETO", "eFG%", "PER%", "RO%", "TL/TC"]
    }


def player_profiles(players: pd.DataFrame, shots: pd.DataFrame, team: str) -> pd.DataFrame:
    """Reparto de los tiros de cada jugador del equipo y su perfil de juego estimado."""
    zoned = add_zones(shots[shots["team"] == team])
    grouped = zoned.groupby("player")
    attempts = grouped.size()
    near = grouped["zone"].apply(lambda z: (z == "Cerca del aro").sum())
    threes = grouped["value"].apply(lambda v: (v == 3).sum())
    own = players[players["team"] == team].groupby("player")[["MIN", "RO"]].sum()
    df = pd.DataFrame({"TCA": attempts, "near": near, "threes": threes}).join(own, how="right")
    df = df.fillna(0)
    df["% cerca del aro"] = (100 * df["near"] / df["TCA"].where(df["TCA"] > 0)).round(1)
    df["% triples"] = (100 * df["threes"] / df["TCA"].where(df["TCA"] > 0)).round(1)
    df["RO/40"] = (40 * df["RO"] / df["MIN"].where(df["MIN"] > 0)).round(1)
    df["Perfil"] = df.apply(_profile, axis=1)
    return df[["TCA", "% cerca del aro", "% triples", "RO/40", "Perfil"]]


def _profile(row: pd.Series) -> str:
    if row["TCA"] < MIN_ATTEMPTS_FOR_PROFILE:
        return "Pocos tiros"
    near, threes = row["% cerca del aro"], row["% triples"]
    if near >= 50 or (threes < 15 and row["RO/40"] >= 3):
        return "Interior"
    if threes >= 50:
        return "Exterior"
    return "Mixto"
