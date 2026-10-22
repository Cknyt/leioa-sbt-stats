"""Métricas básicas y de tiro, por jugador y por equipo.

Fórmulas:
- TC (tiros de campo) = tiros de 2 + tiros de 3. Los tiros libres van aparte.
- eFG% = (TCM + 0,5 × T3M) / TCA. Da a cada triple el valor extra que tiene.
- TS% = PTS / (2 × (TCA + 0,44 × T1A)). Eficiencia de tiro contando también los libres.
  El 0,44 estima qué parte de los tiros libres "gasta" una posesión.
"""

import pandas as pd

COUNT_COLUMNS = [
    "MIN", "PTS", "T1M", "T1A", "T2M", "T2A", "T3M", "T3A",
    "RO", "RD", "AS", "PER", "REC", "TAP", "FP", "FR", "VAL",
]  # fmt: skip


def ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Porcentaje (0-100). Vacío cuando no hay intentos, en vez de dividir entre cero."""
    return (100 * numerator / denominator.where(denominator > 0)).round(1)


def add_shooting(df: pd.DataFrame) -> pd.DataFrame:
    """Añade rebotes totales, tiros de campo y porcentajes de tiro."""
    df = df.copy()
    df["RT"] = df["RO"] + df["RD"]
    df["TCM"] = df["T2M"] + df["T3M"]
    df["TCA"] = df["T2A"] + df["T3A"]
    df["TC%"] = ratio(df["TCM"], df["TCA"])
    df["T2%"] = ratio(df["T2M"], df["T2A"])
    df["T3%"] = ratio(df["T3M"], df["T3A"])
    df["T1%"] = ratio(df["T1M"], df["T1A"])
    df["eFG%"] = ratio(df["TCM"] + 0.5 * df["T3M"], df["TCA"])
    df["TS%"] = ratio(df["PTS"], 2 * (df["TCA"] + 0.44 * df["T1A"]))
    return df


def player_season(players: pd.DataFrame, team_name: str) -> pd.DataFrame:
    """Totales de temporada por jugador, con medias por partido y por 40 minutos."""
    team = players[players["team"] == team_name]
    grouped = team.groupby("player")
    season = grouped[COUNT_COLUMNS].sum()
    # Un jugador convocado que no llega a jugar aparece con 0 minutos: no cuenta como partido.
    season.insert(0, "PJ", grouped["MIN"].apply(lambda m: (m > 0).sum()))
    season.insert(1, "TIT", grouped["starter"].sum())
    season = add_shooting(season)
    for column in ["MIN", "PTS", "RT", "AS", "PER", "VAL"]:
        season[f"{column}/PJ"] = (season[column] / season["PJ"].where(season["PJ"] > 0)).round(1)
    for column in ["PTS", "RT", "AS", "PER"]:
        season[f"{column}/40"] = (
            40 * season[column] / season["MIN"].where(season["MIN"] > 0)
        ).round(1)
    return season.sort_values("MIN", ascending=False)


def team_season(teams: pd.DataFrame, team_name: str) -> pd.DataFrame:
    """Totales y medias del equipo frente a lo que han hecho sus rivales."""
    own = teams[teams["team"] == team_name]
    rivals = teams[(teams["opponent"] == team_name) & (teams["team"] != team_name)]
    rows = {}
    for label, df in ((team_name, own), ("Rivales", rivals)):
        totals = df[COUNT_COLUMNS[1:]].sum()
        totals["PJ"] = len(df)
        rows[label] = totals
    season = add_shooting(pd.DataFrame(rows).T)
    for column in ["PTS", "RT", "RO", "RD", "AS", "PER", "REC", "TAP", "FP"]:
        season[f"{column}/PJ"] = (season[column] / season["PJ"]).round(1)
    return season
