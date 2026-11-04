"""Métricas de toda la liga: clasificación avanzada y perfil de juego de cada jugador.

Perfil de juego (estimación: la federación no publica posiciones). Se deduce de dónde tira
el jugador y de cuántos rebotes ofensivos coge:
- Interior: la mitad o más de sus tiros de campo son cerca del aro (< 3 m), o casi no tira
  triples (< 15 % de sus tiros) y coge 3 o más rebotes ofensivos por 40 minutos.
- Exterior: la mitad o más de sus tiros de campo son triples.
- Mixto: el resto.
Con menos de 10 tiros de campo no se estima.

Comparativa entre equipos: los acumulados de la temporada de cada equipo. Las cifras de
volumen (puntos, rebotes...) son medias por partido, para que no pese haber jugado uno más.
Los porcentajes salen de los totales de la temporada, no de la media de cada partido.
"""

import pandas as pd

from leioa_stats.metrics.advanced import four_factors, ratings, team_games
from leioa_stats.metrics.basic import season_totals
from leioa_stats.metrics.origins import origin_average, origin_profiles
from leioa_stats.metrics.quarters import DIFFERENCE_COLUMNS, quarter_differences
from leioa_stats.metrics.shots import add_zones

MIN_ATTEMPTS_FOR_PROFILE = 10

LEAGUE_COLUMNS = ["PJ", "V", "D", "RITMO", "ORtg", "DRtg", "NETO", "eFG%", "PER%", "RO%",
                  "TL/TC", "eFG% rival", "PER% rival", "RO% rival", "TL/TC rival"]  # fmt: skip

# Filas de la comparativa: (grupo, [(columna, sentido)]). Sentido 1 = más es mejor,
# -1 = menos es mejor, 0 = ni mejor ni peor (es estilo de juego, como el ritmo).
COMPARISON = [
    ("Ritmo y eficiencia", [("RITMO", 0), ("ORtg", 1), ("DRtg", -1), ("NETO", 1)]),
    ("Puntos", [("PTS/PJ", 1), ("Encajados/PJ", -1)]),
    ("Tiro", [("TC%", 1), ("T2%", 1), ("T3%", 1), ("T1%", 1), ("eFG%", 1), ("TS%", 1),
              ("T3A/PJ", 0), ("TL/TC", 1)]),
    ("Rebote y balón", [("RT/PJ", 1), ("RO/PJ", 1), ("RD/PJ", 1), ("RO%", 1), ("AS/PJ", 1),
                        ("PER/PJ", -1), ("PER%", -1), ("REC/PJ", 1), ("TAP/PJ", 1),
                        ("FP/PJ", -1)]),
    ("Por cuartos", [(column, 1) for column in DIFFERENCE_COLUMNS]),
    ("Origen de los puntos", [("2ª oportunidad/PJ", 1), ("PTS/RO", 1), ("Tras pérdida/PJ", 1),
                              ("Contraataque/PJ", 1)]),
    ("Lo que permite a sus rivales", [("eFG% rival", -1), ("PER% rival", 1), ("RO% rival", -1),
                                      ("TL/TC rival", -1), ("2ª oportunidad/PJ rival", -1),
                                      ("Tras pérdida/PJ rival", -1),
                                      ("Contraataque/PJ rival", -1)]),
]  # fmt: skip
COMPARISON_COLUMNS = [column for _, rows in COMPARISON for column, _ in rows]
# Las que no están en la clasificación (league_table) salen de los totales de cada equipo.
BOX_COMPARISON = ["PTS/PJ", "TC%", "T2%", "T3%", "T1%", "TS%", "T3A/PJ", "RT/PJ", "RO/PJ",
                  "RD/PJ", "AS/PJ", "PER/PJ", "REC/PJ", "TAP/PJ", "FP/PJ"]  # fmt: skip


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


def team_profiles(
    teams: pd.DataFrame, origins: pd.DataFrame, quarters: pd.DataFrame
) -> pd.DataFrame:
    """Una fila por equipo con todas las cifras de la comparativa (acumulado de la temporada).

    `origins` es la tabla de metrics/origins.py (origen de los puntos de cada partido) y
    `quarters`, la de cada cuarto (parse.quarter_rows).
    """
    table = league_table(teams)
    rows = {}
    for team in table.index:
        own = season_totals(teams[teams["team"] == team])[BOX_COMPARISON]
        rivals = teams[(teams["opponent"] == team) & (teams["team"] != team)]
        own["Encajados/PJ"] = season_totals(rivals)["PTS/PJ"]
        rows[team] = own
    box = pd.DataFrame(rows).T.astype(float)
    profiles = table.join(box).join(origin_profiles(origins)).join(quarter_differences(quarters))
    return profiles[COMPARISON_COLUMNS]


def profile_average(teams: pd.DataFrame, origins: pd.DataFrame) -> pd.Series:
    """Media de la liga de cada cifra de la comparativa (todos los partidos juntos)."""
    average = pd.concat(
        [league_average(teams), season_totals(teams)[BOX_COMPARISON], origin_average(origins)]
    )
    # En la liga entera, lo que se anota es lo que se encaja y lo que se permite es lo que se hace.
    average["Encajados/PJ"] = average["PTS/PJ"]
    for column in ["eFG%", "PER%", "RO%", "TL/TC"]:
        average[f"{column} rival"] = average[column]
    for column in DIFFERENCE_COLUMNS:
        average[column] = 0.0
    return average[COMPARISON_COLUMNS].astype(float).round(2)


def profile_ranks(profiles: pd.DataFrame) -> pd.DataFrame:
    """Puesto de cada equipo en cada cifra (1 = el mejor; si no hay mejor, 1 = el más alto)."""
    return pd.DataFrame(
        {
            column: profiles[column].rank(ascending=direction == -1, method="min").astype(int)
            for _, rows in COMPARISON
            for column, direction in rows
        }
    )


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
