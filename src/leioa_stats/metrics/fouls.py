"""Faltas: problemas de faltas de cada jugador y tiempo en bonus de cada equipo.

A partir del jugada a jugada (validate.is_foul): cuentan las faltas de los jugadores,
también las de ataque, las técnicas y las antideportivas; no las técnicas al entrenador o al
banquillo, que se anotan "de equipo".

- Problemas de faltas de un jugador, partido a partido:
  - 2 faltas en la 1.ª parte: su 2.ª falta llega antes del minuto 20.
  - 4 faltas antes del último cuarto: su 4.ª falta llega antes del minuto 30.
  - Eliminado: llega a 5 faltas.
- Bonus (reglas FIBA): desde la 5.ª falta de equipo en un cuarto, cada falta da tiros
  libres. El tiempo en bonus de un equipo es lo que queda del cuarto desde su 4.ª falta.
  Las prórrogas no cuentan.
"""

import pandas as pd

from leioa_stats.metrics.lineups import elapsed_seconds
from leioa_stats.validate import is_foul

BONUS_FOULS = 4
QUARTERS = 4


def foul_rows(match: dict, stats: dict, moves: list[dict]) -> tuple[list[dict], list[dict]]:
    """(una fila por jugador con faltas, una fila por equipo y cuarto con su tiempo en bonus)."""
    names = {t["teamIdIntern"]: t["name"] for t in stats["teams"]}
    durations = stats["periodDurationList"]
    times: dict[tuple[str, str], list[int]] = {}
    team_fouls: dict[tuple[str, int], list[int]] = {}
    for move in moves:
        if move["teamAction"] or move["idTeam"] not in names or not is_foul(move):
            continue
        team, now = names[move["idTeam"]], elapsed_seconds(move, durations)
        times.setdefault((team, move["actorName"]), []).append(now)
        if move["period"] <= QUARTERS:
            team_fouls.setdefault((team, move["period"]), []).append(now)
    players = [
        {
            "match_id": match["id"],
            "team": team,
            "player": player,
            "FP": len(t),
            "2 en la 1.ª parte": int(len(t) >= 2 and sorted(t)[1] < 20 * 60),
            "4 antes del 4.º cuarto": int(len(t) >= 4 and sorted(t)[3] < 30 * 60),
            "Eliminado": int(len(t) >= 5),
        }
        for (team, player), t in times.items()
    ]
    bonus = []
    for team in names.values():
        for quarter in range(1, QUARTERS + 1):
            fouls = sorted(team_fouls.get((team, quarter), []))
            end = sum(durations[:quarter]) * 60
            seconds = end - fouls[BONUS_FOULS - 1] if len(fouls) >= BONUS_FOULS else 0
            bonus.append(
                {"match_id": match["id"], "team": team, "period": quarter, "seconds": seconds}
            )
    return players, bonus


FOUL_TROUBLE_COLUMNS = ["2 en la 1.ª parte", "4 antes del 4.º cuarto", "Eliminado"]


def foul_trouble(fouls: pd.DataFrame, players: pd.DataFrame, team: str, min_minutes: float):
    """Por jugador del equipo (con minutos suficientes): faltas por 40 minutos y partidos con
    problemas de faltas."""
    box = players[players["team"] == team].groupby("player")[["MIN", "FP", "FR"]].sum()
    box["PJ"] = players[(players["team"] == team) & (players["MIN"] > 0)].groupby("player").size()
    box = box[box["MIN"] >= min_minutes]
    own = fouls[fouls["team"] == team].groupby("player")[FOUL_TROUBLE_COLUMNS].sum()
    table = box.join(own).fillna(0)
    table["FP/40"] = (40 * table["FP"] / table["MIN"]).round(1)
    table["FR/40"] = (40 * table["FR"] / table["MIN"]).round(1)
    for column in FOUL_TROUBLE_COLUMNS + ["PJ"]:
        table[column] = table[column].astype(int)
    return table.sort_values("FP/40", ascending=False)[
        ["PJ", "FP/40", "FR/40", *FOUL_TROUBLE_COLUMNS]
    ]


def bonus_minutes(bonus: pd.DataFrame, team: str) -> pd.DataFrame:
    """Minutos por cuarto en bonus del equipo y de sus rivales (media por partido)."""
    own = bonus[bonus["team"] == team]
    games = own["match_id"].unique()
    rivals = bonus[bonus["match_id"].isin(games) & (bonus["team"] != team)]

    def per_quarter(df: pd.DataFrame) -> pd.Series:
        means = df.groupby("period")["seconds"].sum() / 60 / max(len(games), 1)
        return means.reindex(range(1, QUARTERS + 1), fill_value=0).rename(lambda q: f"C{q}")

    return pd.DataFrame({"Equipo": per_quarter(own), "Rivales": per_quarter(rivals)}).T.round(1)
