"""Jugadores parecidos: a qué jugador nuestro se parece cada jugador rival.

Perfil de cada jugador con MIN_MINUTES o más en la temporada (toda la liga), con cifras por
40 minutos o en porcentaje para que no pese cuánto juega:
- USO%, % de triples, % de tiros cerca del aro, asistencias, rebotes ofensivos y defensivos,
  pérdidas por 40 minutos, y tiros libres intentados por tiro de campo.
Cada cifra se tipifica (se resta la media de la liga y se divide por su desviación típica),
para que todas pesen igual, y la distancia entre dos jugadores es la euclídea entre sus
perfiles. El más parecido es el de menor distancia.

No mide calidad (el acierto no entra, porque con pocos tiros es casi azar): mide el papel en
el equipo. Sirve para explicar a un jugador "defiéndele como a nuestro X en los
entrenamientos".
"""

import numpy as np
import pandas as pd

from leioa_stats.format import display_name

MIN_MINUTES = 60
FEATURES = ["USO%", "% triples", "% cerca del aro", "AS/40", "RO/40", "RD/40", "PER/40", "TL/TC"]
# Rasgo marcado (|z| ≥ 1) -> cómo se dice, si está por encima o por debajo de la media.
TRAITS = {
    "USO%": ("mucho uso", "poco uso"),
    "% triples": ("tira mucho de tres", "apenas tira de tres"),
    "% cerca del aro": ("ataca mucho el aro", "poco cerca del aro"),
    "AS/40": ("reparte mucho", "apenas asiste"),
    "RO/40": ("rebote ofensivo", ""),
    "RD/40": ("rebote defensivo", ""),
    "PER/40": ("pierde bastantes balones", "cuida el balón"),
    "TL/TC": ("saca muchos tiros libres", ""),
}


def player_features(players: pd.DataFrame, shots: pd.DataFrame, usage: pd.Series) -> pd.DataFrame:
    """Perfil de cada jugador de la liga, indexado por (equipo, jugador).

    `shots` lleva la zona (metrics/shots.add_zones); `usage`, el USO% por (equipo, jugador).
    """
    box = players.groupby(["team", "player"])[
        ["MIN", "T2A", "T3A", "T1A", "AS", "RO", "RD", "PER"]
    ].sum()
    box = box[box["MIN"] >= MIN_MINUTES]
    attempts = (box["T2A"] + box["T3A"]).where(lambda a: a > 0)
    near = (
        shots[shots["zone"] == "Cerca del aro"].groupby(["team", "player"]).size()
        if len(shots)
        else pd.Series(dtype=float)
    )
    features = pd.DataFrame(
        {
            "USO%": usage.reindex(box.index),
            "% triples": 100 * box["T3A"] / attempts,
            "% cerca del aro": 100 * near.reindex(box.index).fillna(0) / attempts,
            "AS/40": 40 * box["AS"] / box["MIN"],
            "RO/40": 40 * box["RO"] / box["MIN"],
            "RD/40": 40 * box["RD"] / box["MIN"],
            "PER/40": 40 * box["PER"] / box["MIN"],
            "TL/TC": 100 * box["T1A"] / attempts,
        }
    )
    return features.dropna()


def standardize(features: pd.DataFrame) -> pd.DataFrame:
    spread = features.std().replace(0, 1)
    return (features - features.mean()) / spread


def traits(z: pd.Series) -> list[str]:
    """Rasgos marcados de un perfil tipificado (|z| ≥ 1)."""
    found = []
    for feature, (high, low) in TRAITS.items():
        if z[feature] >= 1 and high:
            found.append(high)
        elif z[feature] <= -1 and low:
            found.append(low)
    return found


def most_similar(features: pd.DataFrame, rival: str, own: str, players: list[str]) -> list[str]:
    """Para cada jugador rival de `players`: su jugador más parecido de nuestro equipo."""
    z = standardize(features)
    own_rows = z.loc[own] if own in z.index.get_level_values(0) else pd.DataFrame()
    texts = []
    if own_rows.empty or rival not in z.index.get_level_values(0):
        return texts
    rival_rows = z.loc[rival]
    for player in players:
        if player not in rival_rows.index:
            continue
        profile = rival_rows.loc[player]
        distances = np.sqrt(((own_rows - profile) ** 2).sum(axis=1))
        match = distances.idxmin()
        shared = [t for t in traits(profile) if t in traits(own_rows.loc[match])]
        detail = f" ({', '.join(shared)})" if shared else ""
        texts.append(f"{display_name(player)} → nuestro {display_name(match)}{detail}.")
    return texts
