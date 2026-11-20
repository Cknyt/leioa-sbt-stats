"""Cuánta confianza merece cada cifra: errores estándar y encogimiento hacia la media.

Por qué: con pocos partidos, un equipo puede quedar 3.º o 11.º por pura suerte. En vez de
mirar el puesto, se mide cuánto se aleja de la media de la liga en relación con lo que baila
esa cifra de un partido a otro.

Equipos (métricas por posesión):
- Variabilidad de una métrica = desviación típica de sus valores partido a partido, tomada
  dentro de cada equipo (así no cuenta como ruido que unos equipos sean mejores que otros).
  Con menos de 20 grados de libertad se usan los valores por defecto (DEFAULT_SPREAD),
  medidos en las 4 primeras jornadas de la temporada 2026-27.
- Error estándar del equipo = variabilidad / √(partidos jugados).
- z = (valor del equipo - media de la liga) / error estándar, con signo positivo cuando es
  mejor que la media (en las métricas en las que menos es mejor, se le da la vuelta).

Porcentajes de tiro (equipos, zonas): error estándar de una proporción,
√(p × (1 - p) / intentos), con p = acierto de la liga.

Confianza: alta con |z| ≥ 2, media con |z| ≥ 1,5. Por debajo no se saca conclusión.
Como referencia, |z| ≥ 2 pasa por azar en un 5 % de los casos y |z| ≥ 1,5 en un 13 %.

Encogimiento (jugadores): se suman K tiros "de jugador medio de la liga" a los reales:
    acierto encogido = (anotados + K × acierto de la liga) / (intentos + K).
Con pocos tiros, el valor se queda cerca de la media; con muchos, manda el jugador.
K se estima con los datos (método de los momentos) y, si no se puede, vale DEFAULT_K.
"""

import math

import numpy as np
import pandas as pd

Z_HIGH = 2.0
Z_MEDIUM = 1.5
MIN_DEGREES_OF_FREEDOM = 20

# Desviación típica partido a partido dentro de cada equipo (4 jornadas, 28 partidos).
DEFAULT_SPREAD = {
    "RITMO": 3.8,
    "ORtg": 11.9,
    "DRtg": 14.3,
    "NETO": 18.0,
    "eFG%": 6.4,
    "PER%": 4.6,
    "RO%": 7.5,
    "TL/TC": 9.6,
    "eFG% rival": 7.4,
    "PER% rival": 5.2,
    "RO% rival": 7.9,
    "TL/TC rival": 9.0,
}
# Tiros "de jugador medio" que se suman al encogido. Triples: con 4 jornadas, la diferencia
# de acierto entre jugadores aún no se distingue del ruido, así que se usa este valor.
DEFAULT_K = {"T3%": 100, "TS%": 50}
K_LIMITS = (30, 300)


def label(z: float | None) -> str | None:
    """'alta', 'media' o None (no hay conclusión) según la distancia a la media."""
    if z is None or pd.isna(z):
        return None
    if abs(z) >= Z_HIGH:
        return "alta"
    if abs(z) >= Z_MEDIUM:
        return "media"
    return None


def per_game_values(games: pd.DataFrame) -> pd.DataFrame:
    """Valor de cada métrica en cada partido de cada equipo (filas de advanced.team_games)."""
    g = games
    attempts = g["T2A"] + g["T3A"]
    attempts_opp = g["T2A_opp"] + g["T3A_opp"]
    return pd.DataFrame(
        {
            "team": g["team"],
            "RITMO": 40 * g["POSS"] / g["game_minutes"],
            "ORtg": 100 * g["PTS"] / g["POSS"],
            "DRtg": 100 * g["PTS_opp"] / g["POSS"],
            "NETO": 100 * (g["PTS"] - g["PTS_opp"]) / g["POSS"],
            "eFG%": 100 * (g["T2M"] + 1.5 * g["T3M"]) / attempts,
            "PER%": 100 * g["PER"] / g["POSS"],
            "RO%": 100 * g["RO"] / (g["RO"] + g["RD_opp"]),
            "TL/TC": 100 * g["T1M"] / attempts,
            "eFG% rival": 100 * (g["T2M_opp"] + 1.5 * g["T3M_opp"]) / attempts_opp,
            "PER% rival": 100 * g["PER_opp"] / g["POSS"],
            "RO% rival": 100 * g["RO_opp"] / (g["RO_opp"] + g["RD"]),
            "TL/TC rival": 100 * g["T1M_opp"] / attempts_opp,
        }
    )


def league_spread(games: pd.DataFrame) -> pd.Series:
    """Variabilidad partido a partido de cada métrica, dentro de cada equipo."""
    degrees = len(games) - games["team"].nunique()
    if degrees < MIN_DEGREES_OF_FREEDOM:
        return pd.Series(DEFAULT_SPREAD)
    values = per_game_values(games)
    metrics = values.drop(columns="team")
    deviations = metrics - metrics.groupby(values["team"]).transform("mean")
    return np.sqrt((deviations**2).sum() / degrees)


def team_z(value: float, average: float, spread: float, games: int, higher_is_better: bool):
    """Distancia a la media en errores estándar (positiva = mejor que la media)."""
    if games <= 0 or pd.isna(value) or pd.isna(average):
        return float("nan")
    z = (value - average) / (spread / math.sqrt(games))
    return z if higher_is_better else -z


def proportion_z(made: float, attempts: float, league_rate: float) -> float:
    """z de un acierto (0-1) frente al de la liga, con el error de una proporción."""
    if attempts <= 0 or not 0 < league_rate < 1:
        return float("nan")
    rate = made / attempts
    return (rate - league_rate) / math.sqrt(league_rate * (1 - league_rate) / attempts)


def estimate_k(made: pd.Series, attempts: pd.Series, default: float) -> float:
    """Fuerza del encogimiento de un acierto, por el método de los momentos.

    Varianza real entre jugadores = varianza observada - varianza esperada por azar.
    K = p × (1 - p) / varianza real. Si la varianza real no es positiva (todo es ruido) o hay
    menos de 30 jugadores con 10 intentos, se usa el valor por defecto.
    """
    keep = attempts >= 10
    made, attempts = made[keep], attempts[keep]
    if len(attempts) < 30:
        return default
    rate = made.sum() / attempts.sum()
    observed = (made / attempts).var()
    by_chance = (rate * (1 - rate) / attempts).mean()
    real = observed - by_chance
    if real <= 0:
        return default
    return float(np.clip(rate * (1 - rate) / real, *K_LIMITS))


def shrink(made: float, attempts: float, league_rate: float, k: float) -> float:
    """Acierto encogido hacia el de la liga (misma escala que league_rate)."""
    return (made + k * league_rate) / (attempts + k)


def shrink_weight(attempts: float, k: float) -> float:
    """Peso de los datos del jugador en el valor encogido (0-1)."""
    return attempts / (attempts + k) if attempts + k > 0 else 0.0
