"""Rendimiento por cuartos: anotación, tiro y pérdidas del equipo y de sus rivales.

Sale del box score de cada cuarto, que suma exactamente lo mismo que el del partido (incluye
los rebotes y pérdidas "de equipo"). El acierto cerca del aro sale del mapa de tiros.
Las prórrogas se juntan en una fila (PR). Las medias por partido se dividen entre los
partidos en los que hubo ese periodo.
"""

import pandas as pd

from leioa_stats.metrics.shots import add_zones

QUARTER_COLUMNS = ["PJ", "PTS/PJ", "Encajados/PJ", "DIF/PJ", "T2%", "T3%", "Aro%",
                   "Aro% rival", "PER/PJ", "Forzadas/PJ", "FP/PJ"]  # fmt: skip
LABELS = ["C1", "C2", "C3", "C4", "PR"]
# Columnas de la comparativa: diferencia de puntos por partido en cada cuarto.
DIFFERENCE_COLUMNS = [f"Dif. C{n}" for n in range(1, 5)]


def period_label(period: pd.Series) -> pd.Series:
    return period.map(lambda p: f"C{p}" if p <= 4 else "PR")


def _rim(shots: pd.DataFrame) -> tuple[int, int]:
    near = shots[shots["zone"] == "Cerca del aro"]
    return int(near["made"].sum()), len(near)


def quarter_summary(quarters: pd.DataFrame, shots: pd.DataFrame, team_name: str) -> pd.DataFrame:
    """Una fila por cuarto (C1-C4 y PR) con las cifras del equipo y lo que hicieron sus rivales."""
    own = quarters[quarters["team"] == team_name]
    rival = quarters[(quarters["opponent"] == team_name) & (quarters["team"] != team_name)]
    games = set(own["match_id"])
    shots = add_zones(shots[shots["match_id"].isin(games)])
    shots = shots.assign(label=period_label(shots["period"]))
    rows = {}
    for label in LABELS:
        own_q = own[period_label(own["period"]) == label]
        if own_q.empty:
            continue
        rival_q = rival[period_label(rival["period"]) == label]
        n = own_q["match_id"].nunique()
        t, r = own_q.sum(numeric_only=True), rival_q.sum(numeric_only=True)
        rim_made, rim_attempts = _rim(
            shots[(shots["label"] == label) & (shots["team"] == team_name)]
        )
        rival_made, rival_attempts = _rim(
            shots[(shots["label"] == label) & (shots["team"] != team_name)]
        )
        rows[label] = {
            "PJ": n,
            "PTS/PJ": t["PTS"] / n,
            "Encajados/PJ": r["PTS"] / n,
            "DIF/PJ": (t["PTS"] - r["PTS"]) / n,
            "T2%": 100 * t["T2M"] / t["T2A"] if t["T2A"] else None,
            "T3%": 100 * t["T3M"] / t["T3A"] if t["T3A"] else None,
            "Aro%": 100 * rim_made / rim_attempts if rim_attempts else None,
            "Aro% rival": 100 * rival_made / rival_attempts if rival_attempts else None,
            "PER/PJ": t["PER"] / n,
            "Forzadas/PJ": r["PER"] / n,
            "FP/PJ": t["FP"] / n,
        }
    summary = pd.DataFrame(rows).T.astype(float).round(1)
    summary["PJ"] = summary["PJ"].astype(int)
    return summary


def quarter_differences(quarters: pd.DataFrame) -> pd.DataFrame:
    """Una fila por equipo: diferencia de puntos por partido en cada cuarto (sin prórrogas)."""
    regular = quarters[quarters["period"] <= 4]
    rival = regular[["match_id", "period", "team", "PTS"]].rename(
        columns={"team": "opponent", "PTS": "PTS_opp"}
    )
    games = regular.merge(rival, on=["match_id", "period", "opponent"])
    games["DIF"] = games["PTS"] - games["PTS_opp"]
    differences = games.pivot_table(index="team", columns="period", values="DIF", aggfunc="mean")
    differences.columns = [f"Dif. C{p}" for p in differences.columns]
    return differences.round(1)
