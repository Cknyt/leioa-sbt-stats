"""Canastas asistidas y conexiones de pase, a partir del jugada a jugada.

La mesa anota la asistencia justo después de la canasta, en el mismo segundo (594 de las
602 asistencias de las 4 primeras jornadas). Una canasta de campo es asistida si tiene una
asistencia del mismo equipo en ese segundo, en la jugada anterior o en las dos siguientes.
Qué cuenta como asistencia lo decide la mesa: es un dato con criterio, no una medida exacta.
La mesa también anota a veces asistencias en jugadas que acaban en falta y tiros libres
(3 en el partido 99138): no son de canasta de campo y aquí no cuentan.
"""

import pandas as pd

from leioa_stats.validate import ASSIST, DUNK, THREE_MADE, TWO_MADE

MADE_FIELD_GOALS = {TWO_MADE: 2, DUNK: 2, THREE_MADE: 3}


def _same_moment(a: dict, b: dict) -> bool:
    return (a["period"], a["min"], a["sec"]) == (b["period"], b["min"], b["sec"])


def basket_rows(match: dict, stats: dict, moves: list[dict]) -> list[dict]:
    """Una fila por canasta de campo: quién anota, quién asiste (o nadie) y su valor."""
    names = {t["teamIdIntern"]: t["name"] for t in stats["teams"]}
    rows = []
    for i, move in enumerate(moves):
        value = MADE_FIELD_GOALS.get(move["idMove"])
        if value is None or move["idTeam"] not in names:
            continue
        passer = None
        for j in (i + 1, i - 1, i + 2):
            if 0 <= j < len(moves):
                other = moves[j]
                if (
                    other["idMove"] == ASSIST
                    and other["idTeam"] == move["idTeam"]
                    and _same_moment(other, move)
                ):
                    passer = other["actorName"]
                    break
        rows.append(
            {
                "match_id": match["id"],
                "team": names[move["idTeam"]],
                "scorer": move["actorName"],
                "passer": passer,
                "value": value,
            }
        )
    return rows


def connections(baskets: pd.DataFrame, team: str, top: int = 8) -> pd.DataFrame:
    """Parejas que más canastas generan: quién pasa, quién anota y cuántas son triples."""
    own = baskets[(baskets["team"] == team) & baskets["passer"].notna()]
    if own.empty:
        return pd.DataFrame(columns=["Pasa", "Anota", "Canastas", "Triples"])
    grouped = own.groupby(["passer", "scorer"])["value"]
    table = pd.DataFrame(
        {"Canastas": grouped.size(), "Triples": grouped.apply(lambda v: int((v == 3).sum()))}
    ).reset_index()
    table = table.rename(columns={"passer": "Pasa", "scorer": "Anota"})
    return table.sort_values(["Canastas", "Triples"], ascending=False).head(top)


def assisted_shares(baskets: pd.DataFrame, team: str) -> pd.DataFrame:
    """Por jugador: % de sus canastas de campo y de sus triples que vienen de una asistencia."""
    own = baskets[baskets["team"] == team].assign(assisted=lambda d: d["passer"].notna())
    grouped = own.groupby("scorer")
    threes = own[own["value"] == 3].groupby("scorer")
    return pd.DataFrame(
        {
            "% asistidas": (100 * grouped["assisted"].mean()).round(1),
            "% triples asistidos": (100 * threes["assisted"].mean()).round(1),
        }
    )


def team_assisted_share(baskets: pd.DataFrame) -> pd.Series:
    """Por equipo: % de sus canastas de campo que son asistidas."""
    assisted = baskets["passer"].notna()
    return (100 * assisted.groupby(baskets["team"]).mean()).round(1)
