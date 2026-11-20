"""Rotación y disponibilidad de un equipo.

- Disponibilidad: minutos de cada jugador en cada jornada. El acta solo trae a los
  convocados, así que "no convocado" puede ser una baja, una sanción o una decisión técnica.
- Mapa de minutos: en qué parte del partido suele estar en pista cada jugador. Para cada
  minuto de juego (1-40), la fracción de los partidos del equipo en la que estaba en pista,
  según los tramos de metrics/lineups.py (reloj del jugada a jugada). Las prórrogas no
  cuentan.
- Quién cierra: tiempo en pista en los últimos CLOSING_MINUTES minutos del último cuarto.
Es descriptivo (lo que ha hecho, no una estimación), así que sirve desde la primera jornada.
"""

import numpy as np
import pandas as pd

REGULATION_MINUTES = 40
CLOSING_MINUTES = 4
NOT_LISTED = "–"


def availability(players: pd.DataFrame, team: str) -> pd.DataFrame:
    """Jugador × jornada: minutos jugados, 0 si fue convocado sin jugar y '–' si no estaba."""
    own = players[players["team"] == team]
    table = own.pivot_table(index="player", columns="round", values="MIN", aggfunc="sum")
    order = own.groupby("player")["MIN"].sum().sort_values(ascending=False).index
    table = table.loc[order]
    table.columns = [f"J{r}" for r in table.columns]
    return table.map(lambda v: NOT_LISTED if pd.isna(v) else str(int(v)))


def missed_last_game(players: pd.DataFrame, team: str) -> list[str]:
    """Jugadores habituales (en al menos la mitad de las convocatorias) que no estaban en la
    última jornada del equipo."""
    own = players[players["team"] == team]
    if own.empty:
        return []
    last = own["round"].max()
    games = own["round"].nunique()
    listed = own.groupby("player")["round"].nunique()
    regulars = listed[listed >= max(2, games / 2)].index
    present = set(own.loc[own["round"] == last, "player"])
    minutes = own.groupby("player")["MIN"].sum()
    return sorted((p for p in regulars if p not in present), key=lambda p: -minutes[p])


def minute_shares(stints: pd.DataFrame) -> pd.DataFrame:
    """Jugador × minuto (1-40): fracción de los partidos del equipo en la que estaba en pista."""
    if stints.empty:
        return pd.DataFrame(columns=range(1, REGULATION_MINUTES + 1))
    seconds: dict[str, np.ndarray] = {}
    for _, stint in stints.iterrows():
        start, end = stint["start"], min(stint["end"], REGULATION_MINUTES * 60)
        if end <= start:
            continue
        for player in stint["lineup"].split(" | "):
            on = seconds.setdefault(player, np.zeros(REGULATION_MINUTES))
            for minute in range(int(start // 60), int(np.ceil(end / 60))):
                overlap = min(end, (minute + 1) * 60) - max(start, minute * 60)
                if overlap > 0:
                    on[minute] += overlap
    games = stints["match_id"].nunique()
    shares = pd.DataFrame(seconds).T / (60 * games)
    shares.columns = range(1, REGULATION_MINUTES + 1)
    return shares.loc[shares.sum(axis=1).sort_values(ascending=False).index].clip(upper=1)


def closers(shares: pd.DataFrame, top: int = 5) -> pd.Series:
    """Los que más juegan los últimos minutos: fracción de ese tiempo en pista (0-1)."""
    last = list(range(REGULATION_MINUTES - CLOSING_MINUTES + 1, REGULATION_MINUTES + 1))
    if shares.empty:
        return pd.Series(dtype=float)
    return shares[last].mean(axis=1).sort_values(ascending=False).head(top)


def starters(players: pd.DataFrame, team: str) -> pd.Series:
    """Veces que ha salido de titular cada jugador (solo los que lo han hecho alguna vez)."""
    own = players[players["team"] == team]
    counts = own.groupby("player")["starter"].sum().astype(int)
    return counts[counts > 0].sort_values(ascending=False)
