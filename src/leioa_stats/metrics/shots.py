"""Zonas de tiro a partir de las coordenadas del mapa de tiros.

Las coordenadas vienen normalizadas de 0 a 100 sobre una cancha FIBA de 28 × 15 m,
siempre atacando hacia el aro de la izquierda. Calibrado con los partidos 99138 y 99148:
ningún tiro de 2 pasa de 6,74 m y ningún triple baja de 6,81 m (la línea está a 6,75 m).
"""

import numpy as np
import pandas as pd

COURT_LENGTH = 28.0
COURT_WIDTH = 15.0
# El aro está a 1,575 m de la línea de fondo, en el centro de la cancha.
BASKET_X = 1.575 / COURT_LENGTH * 100
BASKET_Y = 50.0

NEAR_BASKET_METERS = 3.0
# El triple de esquina es el tramo recto de la línea, hasta 2,99 m de la línea de fondo.
CORNER_DEPTH_METERS = 2.99

ZONES = ["Cerca del aro", "Media distancia", "Triple de esquina", "Triple frontal"]


def distance_to_basket(x: pd.Series, y: pd.Series) -> pd.Series:
    """Distancia al aro en metros."""
    dx = (x - BASKET_X) / 100 * COURT_LENGTH
    dy = (y - BASKET_Y) / 100 * COURT_WIDTH
    return np.hypot(dx, dy)


def add_zones(shots: pd.DataFrame) -> pd.DataFrame:
    """Añade la distancia y la zona. Si es de 2 o de 3 lo dice la anotación, no la geometría."""
    shots = shots.copy()
    shots["distance"] = distance_to_basket(shots["x"], shots["y"]).round(2)
    depth = shots["x"] / 100 * COURT_LENGTH
    shots["zone"] = np.select(
        [
            (shots["value"] == 2) & (shots["distance"] < NEAR_BASKET_METERS),
            shots["value"] == 2,
            depth <= CORNER_DEPTH_METERS,
        ],
        ZONES[:3],
        default=ZONES[3],
    )
    return shots


def zone_summary(shots: pd.DataFrame) -> pd.DataFrame:
    """Intentos, acierto, puntos por tiro y reparto por zona."""
    grouped = add_zones(shots).groupby("zone")
    summary = pd.DataFrame(
        {
            "TCA": grouped.size(),
            "TCM": grouped["made"].sum(),
            "PTS": grouped.apply(lambda g: (g["value"] * g["made"]).sum(), include_groups=False),
        }
    ).reindex(ZONES, fill_value=0)
    attempts = summary["TCA"].where(summary["TCA"] > 0)
    summary["%"] = (100 * summary["TCM"] / attempts).round(1)
    summary["PTS/tiro"] = (summary["PTS"] / attempts).round(2)
    summary["% de los tiros"] = (100 * summary["TCA"] / summary["TCA"].sum()).round(1)
    return summary
