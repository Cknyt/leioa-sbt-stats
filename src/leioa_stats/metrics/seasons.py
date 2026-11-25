"""Comparación entre temporadas: el equipo año a año y los jugadores que siguen.

Equipo: cada temporada se mide con las mismas fórmulas que la actual (advanced.py y
basic.py) y, al lado de cada cifra, su puesto en la liga de ese año. El puesto importa más
que el valor: si toda la liga tira mejor un año, comparar porcentajes en bruto engaña.

Puesto en la clasificación: se ordena por victorias y, si empatan, por neto. No aplica los
desempates oficiales (enfrentamiento directo), así que puede diferir en algún empate.

Jugadores: se unen por el uuid del acta (player_id), que no cambia entre temporadas.
Cambio de acierto (TS% y T3%) entre la última temporada pasada y la actual: z de la
diferencia de dos proporciones,
    z = (p_actual - p_pasada) / √(p × (1 - p) × (1/n_actual + 1/n_pasada)),
con p = acierto de las dos temporadas juntas y n = intentos. En TS%, los "anotados" son
PTS / 2 y los intentos TCA + 0,44 × T1A. La confianza sigue confidence.label: alta con
|z| ≥ 2, media con |z| ≥ 1,5; por debajo no se marca cambio.
"""

import math

import pandas as pd

from leioa_stats.metrics.advanced import FT_FACTOR, player_usage
from leioa_stats.metrics.basic import add_shooting, player_season
from leioa_stats.metrics.confidence import label
from leioa_stats.metrics.league import league_average, league_table

# Columnas de la tabla del equipo, con True si cuanto más alto, mejor (para el puesto).
# El ritmo no es ni mejor ni peor: su puesto es 1 = el más rápido.
TEAM_METRICS = {
    "PTS/PJ": True,
    "Encajados/PJ": False,
    "RITMO": True,
    "ORtg": True,
    "DRtg": False,
    "NETO": True,
    "TS%": True,
    "T3%": True,
    "PER%": False,
    "RO%": True,
}
PLAYER_COLUMNS = ["PJ", "MIN/PJ", "PTS/PJ", "TS%", "T3A", "T3%", "USO%"]


def shooting_by_team(teams: pd.DataFrame) -> pd.DataFrame:
    """Puntos por partido (a favor y en contra), TS% y T3% de cada equipo de la liga."""
    totals = teams.groupby("team")[["PTS", "T1M", "T1A", "T2M", "T2A", "T3M", "T3A"]].sum()
    totals = add_shooting(totals.assign(RO=0, RD=0))
    games = teams.groupby("team").size()
    against = teams.groupby("opponent")["PTS"].sum().reindex(totals.index)
    return pd.DataFrame(
        {
            "PTS/PJ": (totals["PTS"] / games).round(1),
            "Encajados/PJ": (against / games).round(1),
            "TS%": totals["TS%"],
            "T3%": totals["T3%"],
        }
    )


def season_league(teams: pd.DataFrame) -> pd.DataFrame:
    """Tabla de la liga de una temporada con las columnas de TEAM_METRICS y el puesto."""
    table = league_table(teams).join(shooting_by_team(teams))
    table.insert(0, "Puesto", range(1, len(table) + 1))
    return table


def team_seasons(seasons: dict[str, pd.DataFrame], team: str) -> pd.DataFrame:
    """Una fila por temporada (en el orden recibido) con el equipo y la media de la liga.

    `seasons`: tabla "teams" de parse.build_tables de cada temporada, por etiqueta
    ("2025-26"). Las temporadas en las que no jugó el equipo se saltan.
    Columnas: PJ, V, D, Puesto, equipos, las de TEAM_METRICS, "<métrica> puesto" y
    "ORtg liga" (media de la liga: es también su DRtg, porque cada punto anotado es encajado).
    """
    rows = {}
    for season, teams in seasons.items():
        table = season_league(teams)
        if team not in table.index:
            continue
        row = table.loc[team, ["PJ", "V", "D", "Puesto", *TEAM_METRICS]].copy()
        row["equipos"] = len(table)
        for column, higher_is_better in TEAM_METRICS.items():
            position = table[column].rank(ascending=not higher_is_better, method="min")
            row[f"{column} puesto"] = int(position[team])
        row["ORtg liga"] = league_average(teams)["ORtg"]
        rows[season] = row
    return pd.DataFrame(rows).T


def roster(players: pd.DataFrame, teams: pd.DataFrame, team: str) -> pd.DataFrame:
    """Temporada de cada jugador del equipo con algún minuto, indexada por player_id."""
    season = player_season(players, team)
    season = season[season["PJ"] > 0].join(player_usage(players, teams, team))
    ids = players[players["team"] == team].dropna(subset=["player_id"])
    season["player_id"] = ids.groupby("player")["player_id"].first().reindex(season.index)
    season["TSA"] = season["TCA"] + FT_FACTOR * season["T1A"]
    return season.dropna(subset=["player_id"]).reset_index().set_index("player_id")


def change_z(made_now: float, tries_now: float, made_before: float, tries_before: float):
    """z del cambio de un acierto entre dos temporadas (positivo = ha mejorado)."""
    if tries_now <= 0 or tries_before <= 0:
        return float("nan")
    pooled = (made_now + made_before) / (tries_now + tries_before)
    if not 0 < pooled < 1:
        return float("nan")
    error = math.sqrt(pooled * (1 - pooled) * (1 / tries_now + 1 / tries_before))
    return (made_now / tries_now - made_before / tries_before) / error


def _change(now: pd.Series, before: pd.Series, made: str, tries: str) -> dict | None:
    """Flecha y confianza del cambio, o None si no hay cambio claro."""
    made_now = now["PTS"] / 2 if made == "PTS" else now[made]
    made_before = before["PTS"] / 2 if made == "PTS" else before[made]
    z = change_z(made_now, now[tries], made_before, before[tries])
    confidence = label(z)
    if confidence is None:
        return None
    return {"up": z > 0, "z": round(z, 1), "confidence": confidence}


def returning_players(
    seasons: dict[str, dict[str, pd.DataFrame]], current: str, team: str
) -> list[dict]:
    """Jugadores del equipo esta temporada que ya jugaron en él en alguna pasada.

    `seasons`: tablas "players" y "teams" por temporada, de la más antigua a la actual, que es
    la de etiqueta `current`. Cada jugador: nombre, tabla (una fila por temporada con
    PLAYER_COLUMNS) y cambio de TS% y T3% frente a su última temporada pasada.
    Ordenados por minutos de esta temporada.
    """
    rosters = {
        season: roster(tables["players"], tables["teams"], team)
        for season, tables in seasons.items()
    }
    now_roster = rosters[current]
    result = []
    for player_id, now in now_roster.sort_values("MIN", ascending=False).iterrows():
        past = [s for s in rosters if s != current and player_id in rosters[s].index]
        if not past:
            continue
        rows = {s: rosters[s].loc[player_id] for s in [*past, current]}
        before = rows[past[-1]]
        result.append(
            {
                "player": now["player"],
                "table": pd.DataFrame(rows).T[PLAYER_COLUMNS].astype(float),
                "compared_with": past[-1],
                "changes": {
                    "TS%": _change(now, before, "PTS", "TSA"),
                    "T3%": _change(now, before, "T3M", "T3A"),
                },
            }
        )
    return result
