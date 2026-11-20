"""Finales apretados y lo que pasa tras un tiempo muerto, a partir del jugada a jugada.

Final apretado: últimos CLUTCH_SECONDS segundos del último cuarto o de una prórroga, con
CLUTCH_MARGIN puntos o menos de diferencia antes de la jugada. Hay muy pocos por equipo
(2-3 partidos en las primeras jornadas), así que se dan recuentos (quién se juega los tiros),
no porcentajes de acierto.

Tiempos muertos: puntos de cada equipo en los TIMEOUT_WINDOW segundos de juego siguientes a
un tiempo muerto del equipo, frente a lo que anota y encaja de media en ese mismo tiempo.
Con 2-3 tiempos muertos por partido, la muestra es muy pequeña: es solo descriptivo.
"""

import pandas as pd

from leioa_stats.metrics.lineups import elapsed_seconds
from leioa_stats.validate import (
    DUNK,
    FT_MADE,
    FT_MISSED,
    POINTS,
    THREE_MADE,
    THREE_MISSED,
    TIMEOUT,
    TURNOVER,
    TWO_MADE,
    TWO_MISSED,
)

CLUTCH_SECONDS = 5 * 60
CLUTCH_MARGIN = 5
TIMEOUT_WINDOW = 60
FIELD_GOALS = {TWO_MADE, TWO_MISSED, THREE_MADE, THREE_MISSED, DUNK}
MADE = {TWO_MADE, THREE_MADE, DUNK, FT_MADE}
CLUTCH_COLUMNS = ["TCA", "TCM", "T1A", "T1M", "PER"]


def clutch_rows(match: dict, stats: dict, moves: list[dict]) -> tuple[list[dict], list[dict]]:
    """(acciones de cada jugador en finales apretados, una fila por equipo y partido)."""
    names = {t["teamIdIntern"]: t["name"] for t in stats["teams"]}
    local = stats["localId"]
    score = {team: 0 for team in names}
    players: dict[tuple[str, str], dict] = {}
    clutch_teams = set()
    for move in moves:
        team = move["idTeam"]
        if team not in names:
            continue
        late = move["period"] >= 4 and move["min"] * 60 + move["sec"] <= CLUTCH_SECONDS
        margin = abs(score[local] - sum(v for t, v in score.items() if t != local))
        if late and margin <= CLUTCH_MARGIN:
            clutch_teams.add(team)
            code = move["idMove"]
            key = (names[team], move["actorName"])
            if not move["teamAction"] and code in FIELD_GOALS | {FT_MADE, FT_MISSED, TURNOVER}:
                row = players.setdefault(key, dict.fromkeys(CLUTCH_COLUMNS, 0))
                if code in FIELD_GOALS:
                    row["TCA"] += 1
                    row["TCM"] += code in MADE
                elif code in (FT_MADE, FT_MISSED):
                    row["T1A"] += 1
                    row["T1M"] += code == FT_MADE
                else:
                    row["PER"] += 1
        if move["idMove"] in POINTS:
            score[team] += POINTS[move["idMove"]]
    final = {names[t]: v for t, v in score.items()}
    games = []
    if clutch_teams:
        for team, name in names.items():
            other = next(n for t, n in names.items() if t != team)
            games.append({"match_id": match["id"], "team": name, "won": final[name] > final[other]})
    rows = [
        {"match_id": match["id"], "team": team, "player": player, **values}
        for (team, player), values in players.items()
    ]
    return rows, games


def clutch_summary(rows: pd.DataFrame, team: str) -> pd.DataFrame:
    """Por jugador: tiros de campo, tiros libres y pérdidas en finales apretados."""
    own = rows[rows["team"] == team] if not rows.empty else rows
    if own.empty:
        return pd.DataFrame(columns=CLUTCH_COLUMNS)
    table = own.groupby("player")[CLUTCH_COLUMNS].sum()
    table = table.sort_values(["TCA", "T1A"], ascending=False)
    return table.astype(int)


def clutch_record(games: pd.DataFrame, team: str) -> tuple[int, int]:
    """(victorias, derrotas) en partidos con final apretado."""
    own = games[games["team"] == team] if not games.empty else games
    wins = int(own["won"].sum()) if not own.empty else 0
    return wins, len(own) - wins


def timeout_rows(match: dict, stats: dict, moves: list[dict]) -> list[dict]:
    """Una fila por tiempo muerto: puntos del equipo y del rival en el minuto siguiente."""
    names = {t["teamIdIntern"]: t["name"] for t in stats["teams"]}
    durations = stats["periodDurationList"]
    times = [elapsed_seconds(m, durations) for m in moves]
    rows = []
    for i, move in enumerate(moves):
        if move["idMove"] != TIMEOUT or move["idTeam"] not in names:
            continue
        start = times[i]
        scored = {team: 0 for team in names}
        for later, now in zip(moves[i + 1 :], times[i + 1 :], strict=True):
            if now > start + TIMEOUT_WINDOW:
                break
            if later["idMove"] in POINTS and later["idTeam"] in names:
                scored[later["idTeam"]] += POINTS[later["idMove"]]
        other = next(t for t in names if t != move["idTeam"])
        rows.append(
            {
                "match_id": match["id"],
                "team": names[move["idTeam"]],
                "PTS": scored[move["idTeam"]],
                "PTS_opp": scored[other],
            }
        )
    return rows


def timeout_summary(rows: pd.DataFrame, teams: pd.DataFrame, team: str) -> pd.DataFrame:
    """Tiempos muertos del equipo: puntos a favor y en contra en el minuto siguiente, frente a
    su media por minuto en toda la temporada."""
    own = rows[rows["team"] == team] if not rows.empty else rows
    games = teams[teams["team"] == team]
    rivals = teams[(teams["opponent"] == team) & (teams["team"] != team)]
    minutes = games["game_minutes"].sum()
    per_window = TIMEOUT_WINDOW / 60
    return pd.DataFrame(
        {
            "Tiempos muertos": [len(own)],
            "PTS tras tiempo muerto": [own["PTS"].mean() if len(own) else float("nan")],
            "PTS rival tras tiempo muerto": [own["PTS_opp"].mean() if len(own) else float("nan")],
            "PTS por minuto (temporada)": [games["PTS"].sum() / minutes * per_window],
            "PTS rival por minuto (temporada)": [rivals["PTS"].sum() / minutes * per_window],
        },
        index=["Equipo"],
    ).round(2)
