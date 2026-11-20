"""Eficiencia ajustada por rival y pista, forma reciente y pronóstico.

Ajuste por rival y pista (el mismo modelo aditivo que la previa):
1. Ventaja de jugar en casa (H, en puntos por 100 posesiones): la media del neto de los
   equipos locales, encogida hacia HOME_PRIOR con el peso de HOME_PRIOR_GAMES partidos (con
   pocos partidos, la media observada baila mucho). En cada partido, el local tendría
   H / 2 menos de ataque y H / 2 más de defensa en pista neutral; el visitante, al revés.
2. Rival: a la eficiencia de cada partido se le resta lo que el rival concede (o anota) por
   encima de la media. Como la calidad de cada rival depende a su vez de sus rivales, se
   repite hasta que las cifras no cambian (ITERATIONS veces).
   ORtg ajustado = media de (ORtg del partido en neutral - (DRtg ajustado del rival - media)).
   DRtg ajustado = media de (DRtg del partido en neutral - (ORtg ajustado del rival - media)).
Hasta que cada equipo no se ha enfrentado a buena parte de la liga (jornada 6-7), el ajuste
cambia poco y se apoya en pocos rivales.

Forma reciente: neto medio de los RECENT_GAMES últimos partidos frente al de los anteriores.
Error estándar de la diferencia = variabilidad del neto × √(1/3 + 1/partidos anteriores).
Se marca con flecha solo si |z| ≥ 1,5 y hay al menos 3 partidos anteriores.

Pronóstico (orientativo):
    ritmo esperado = media del ritmo de los dos equipos.
    ORtg esperado del local = ORtg aj. local + DRtg aj. visitante - media + H / 2 (y al revés).
    puntos = ritmo × ORtg esperado / 100.
La incertidumbre es la desviación típica de los errores del modelo en los partidos ya
jugados, con un mínimo de MIN_MARGIN_SD puntos (la típica de un partido de baloncesto): con
pocos partidos el modelo se ajusta demasiado a lo visto y subestimaría el error.
Probabilidad de victoria = Φ(margen esperado / desviación típica), con Φ la normal.
"""

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from leioa_stats.metrics.advanced import team_games
from leioa_stats.metrics.confidence import Z_MEDIUM

HOME_PRIOR = 3.0
HOME_PRIOR_GAMES = 30
ITERATIONS = 30
RECENT_GAMES = 3
MIN_MARGIN_SD = 11.0


def _game_values(teams: pd.DataFrame) -> pd.DataFrame:
    games = team_games(teams)
    games["ORtg_g"] = 100 * games["PTS"] / games["POSS"]
    games["DRtg_g"] = 100 * games["PTS_opp"] / games["POSS"]
    games["NETO_g"] = games["ORtg_g"] - games["DRtg_g"]
    return games


def home_advantage(teams: pd.DataFrame) -> float:
    """Ventaja de jugar en casa en puntos de neto por 100 posesiones (encogida)."""
    games = _game_values(teams)
    home = games[games["home"]]
    n = len(home)
    observed = home["NETO_g"].mean() if n else 0.0
    return (n * observed + HOME_PRIOR_GAMES * HOME_PRIOR) / (n + HOME_PRIOR_GAMES)


def adjusted_ratings(teams: pd.DataFrame) -> pd.DataFrame:
    """Por equipo: ORtg, DRtg y neto ajustados por rival y pista."""
    games = _game_values(teams)
    h = home_advantage(teams)
    side = np.where(games["home"], 1, -1)
    games["ORtg_n"] = games["ORtg_g"] - side * h / 2
    games["DRtg_n"] = games["DRtg_g"] + side * h / 2
    average = games["ORtg_g"].mean()
    offense = games.groupby("team")["ORtg_n"].mean()
    defense = games.groupby("team")["DRtg_n"].mean()
    for _ in range(ITERATIONS):
        opp_defense = games["team_opp"].map(defense) - average
        opp_offense = games["team_opp"].map(offense) - average
        offense = (games["ORtg_n"] - opp_defense).groupby(games["team"]).mean()
        defense = (games["DRtg_n"] - opp_offense).groupby(games["team"]).mean()
        # Que la media de la liga no se desplace al iterar.
        offense += average - offense.mean()
        defense += average - defense.mean()
    result = pd.DataFrame({"ORtg aj.": offense, "DRtg aj.": defense})
    result["NETO aj."] = result["ORtg aj."] - result["DRtg aj."]
    return result.round(1)


def recent_form(teams: pd.DataFrame, spread_net: float) -> pd.DataFrame:
    """Por equipo: neto de los últimos partidos, de los anteriores, z y flecha."""
    games = _game_values(teams).sort_values("round")
    rows = {}
    for team, rows_team in games.groupby("team"):
        recent = rows_team.tail(RECENT_GAMES)["NETO_g"]
        before = rows_team.iloc[: max(0, len(rows_team) - RECENT_GAMES)]["NETO_g"]
        if len(before) < RECENT_GAMES:
            rows[team] = {"Últimos": recent.mean(), "Antes": math.nan, "z": math.nan, "Forma": ""}
            continue
        se = spread_net * math.sqrt(1 / len(recent) + 1 / len(before))
        z = (recent.mean() - before.mean()) / se
        arrow = "↑" if z >= Z_MEDIUM else "↓" if z <= -Z_MEDIUM else ""
        rows[team] = {"Últimos": recent.mean(), "Antes": before.mean(), "z": z, "Forma": arrow}
    return pd.DataFrame(rows).T


@dataclass(frozen=True)
class Forecast:
    home_points: float
    away_points: float
    margin: float  # a favor del local
    sd: float
    home_win: float  # probabilidad 0-1


def _normal_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _expected(adjusted, pace, h, home, away):
    average = adjusted["ORtg aj."].mean()
    home_rtg = adjusted.loc[home, "ORtg aj."] + adjusted.loc[away, "DRtg aj."] - average + h / 2
    away_rtg = adjusted.loc[away, "ORtg aj."] + adjusted.loc[home, "DRtg aj."] - average - h / 2
    return pace * home_rtg / 100, pace * away_rtg / 100


def margin_sd(teams: pd.DataFrame, adjusted: pd.DataFrame, paces: pd.Series, h: float) -> float:
    """Desviación típica de los errores del modelo en los partidos jugados (con mínimo)."""
    games = _game_values(teams)
    home = games[games["home"]]
    errors = []
    for _, g in home.iterrows():
        pace = (paces[g["team"]] + paces[g["team_opp"]]) / 2
        a, b = _expected(adjusted, pace, h, g["team"], g["team_opp"])
        errors.append((g["PTS"] - g["PTS_opp"]) - (a - b))
    observed = float(np.std(errors, ddof=1)) if len(errors) > 1 else 0.0
    return max(observed, MIN_MARGIN_SD)


def forecast(teams: pd.DataFrame, paces: pd.Series, home: str, away: str) -> Forecast:
    """Pronóstico de un partido. `paces`: ritmo de cada equipo (posesiones por 40 min)."""
    adjusted = adjusted_ratings(teams)
    h = home_advantage(teams)
    pace = (paces[home] + paces[away]) / 2
    home_points, away_points = _expected(adjusted, pace, h, home, away)
    sd = margin_sd(teams, adjusted, paces, h)
    margin = home_points - away_points
    return Forecast(home_points, away_points, margin, sd, _normal_cdf(margin / sd))
