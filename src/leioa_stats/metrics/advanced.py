"""Métricas avanzadas: posesiones, ritmo, eficiencia, Four Factors y % de uso.

Todas parten de los totales del equipo, que incluyen los rebotes y pérdidas "de equipo".

Fórmulas:
- Posesiones de un equipo (estimación) = TCA + 0,44 × T1A - RO + PER.
  Las del partido son la media de las de los dos equipos, que deberían ser casi iguales.
- Ritmo = posesiones × 40 / minutos del partido (posesiones por 40 minutos).
- Eficiencia ofensiva (ORtg) = 100 × puntos anotados / posesiones.
- Eficiencia defensiva (DRtg) = 100 × puntos recibidos / posesiones.
- Four Factors (Dean Oliver), para el ataque propio y el del rival:
  - eFG% = (TCM + 0,5 × T3M) / TCA.
  - PER% = 100 × pérdidas / posesiones.
  - RO% = 100 × RO / (RO + RD del rival).
  - TL/TC = 100 × T1M / TCA (cuántos tiros libres se anotan por cada 100 tiros de campo).
- % de uso de un jugador = 100 × (TCA + 0,44 × T1A + PER del jugador) × minutos del partido
  / (minutos del jugador × (TCA + 0,44 × T1A + PER del equipo)).
  Qué parte de las posesiones del equipo acaban en sus manos mientras está en pista (20 % = media).
"""

import pandas as pd

FT_FACTOR = 0.44


def used_possessions(df: pd.DataFrame) -> pd.Series:
    """Posesiones que termina un equipo o un jugador con un tiro, un tiro libre o una pérdida."""
    return df["T2A"] + df["T3A"] + FT_FACTOR * df["T1A"] + df["PER"]


def team_games(teams: pd.DataFrame) -> pd.DataFrame:
    """Una fila por equipo y partido, con sus números y los del rival (sufijo _opp)."""
    teams = teams.assign(POSS_EST=used_possessions(teams) - teams["RO"])
    rival = teams.drop(columns=["opponent", "home", "round", "game_minutes"]).rename(
        columns=lambda c: c if c == "match_id" else f"{c}_opp"
    )
    games = teams.merge(rival, on="match_id")
    games = games[games["team"] != games["team_opp"]].copy()
    games["POSS"] = (games["POSS_EST"] + games["POSS_EST_opp"]) / 2
    return games


def ratings(games: pd.DataFrame) -> pd.DataFrame:
    """Posesiones, ritmo y eficiencia a partir de sumas (sirve para un partido o para varios)."""
    totals = games.sum(numeric_only=True)
    return pd.Series(
        {
            "POSS": totals["POSS"],
            "RITMO": 40 * totals["POSS"] / totals["game_minutes"],
            "ORtg": 100 * totals["PTS"] / totals["POSS"],
            "DRtg": 100 * totals["PTS_opp"] / totals["POSS"],
        }
    ).pipe(lambda s: pd.concat([s, pd.Series({"NETO": s["ORtg"] - s["DRtg"]})]))


def four_factors(games: pd.DataFrame, side: str = "") -> pd.Series:
    """Four Factors del ataque propio (side="") o del rival (side="_opp")."""
    other = "_opp" if side == "" else ""
    t = games.sum(numeric_only=True)
    attempts = t[f"T2A{side}"] + t[f"T3A{side}"]
    made = t[f"T2M{side}"] + t[f"T3M{side}"]
    return pd.Series(
        {
            "eFG%": 100 * (made + 0.5 * t[f"T3M{side}"]) / attempts,
            "PER%": 100 * t[f"PER{side}"] / t["POSS"],
            "RO%": 100 * t[f"RO{side}"] / (t[f"RO{side}"] + t[f"RD{other}"]),
            "TL/TC": 100 * t[f"T1M{side}"] / attempts,
        }
    )


def games_summary(teams: pd.DataFrame, team_name: str) -> pd.DataFrame:
    """Posesiones, ritmo y eficiencia del equipo en cada partido."""
    games = team_games(teams)
    games = games[games["team"] == team_name]
    rows = {
        (row["round"], row["opponent"]): ratings(games[games["match_id"] == row["match_id"]])
        for _, row in games.iterrows()
    }
    summary = pd.DataFrame(rows).T.round(1)
    summary.index.names = ["J", "rival"]
    return summary.sort_index()


def team_advanced(teams: pd.DataFrame, team_name: str) -> pd.DataFrame:
    """Ritmo, eficiencia y Four Factors de la temporada: ataque propio frente al del rival."""
    games = team_games(teams)
    games = games[games["team"] == team_name]
    season = ratings(games)
    factors = pd.DataFrame({team_name: four_factors(games), "Rivales": four_factors(games, "_opp")})
    summary = pd.DataFrame(
        {
            team_name: [season["RITMO"], season["ORtg"]],
            "Rivales": [season["RITMO"], season["DRtg"]],
        },
        index=["RITMO", "Eficiencia (pts/100 pos.)"],
    )
    return pd.concat([summary, factors]).round(1)


def player_usage(players: pd.DataFrame, teams: pd.DataFrame, team_name: str) -> pd.Series:
    """% de uso de temporada de cada jugador del equipo."""
    team_used = teams.assign(team_used=used_possessions(teams))[["match_id", "team", "team_used"]]
    df = players[(players["team"] == team_name) & (players["MIN"] > 0)].merge(
        team_used, on=["match_id", "team"]
    )
    df["used"] = used_possessions(df)
    # Posesiones del equipo mientras el jugador estaba en pista.
    df["team_used_on_court"] = df["MIN"] * df["team_used"] / df["game_minutes"]
    grouped = df.groupby("player")[["used", "team_used_on_court"]].sum()
    return (100 * grouped["used"] / grouped["team_used_on_court"]).round(1).rename("USO%")
