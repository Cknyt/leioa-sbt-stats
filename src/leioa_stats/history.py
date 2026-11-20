"""Temporadas pasadas: descarga e historial de tiro de cada jugador.

Uso:
    uv run python -m leioa_stats.history <id del grupo>

El id del grupo es el número de la dirección de la competición en basketbasko.com
(https://basketbasko.com/es/group/?id=<id>). Cada temporada tiene el suyo. Se descarga una
sola vez, con la misma pausa entre peticiones que la temporada actual, en
data/raw/history/<id>/, con la misma estructura que data/raw (así parse.build_tables sirve
igual). Si ya está descargado, no se vuelve a pedir.

Para qué sirve:
- Historial de tiro: el acierto de un jugador la temporada pasada predice mejor su acierto de
  esta que la media de la liga. El encogimiento (metrics/confidence.shrink) parte de su
  historial en vez de la media, y el historial a su vez se encoge hacia la media de la liga.
  Los jugadores se unen por el uuid del acta, que no cambia entre temporadas.
- Prueba retrospectiva (leioa_stats.backtest): con una temporada completa se puede ver qué
  conclusiones de las primeras jornadas seguían siendo ciertas al final.
"""

import json
import sys
from pathlib import Path

import pandas as pd

from leioa_stats.download import Downloader, download_match, fetch_league
from leioa_stats.parse import build_tables

HISTORY_DIR = Path("data/raw/history")


def download_season(group_id: int, history_dir: Path = HISTORY_DIR) -> Path:
    """Descarga todos los partidos jugados de una temporada pasada. Devuelve su carpeta."""
    raw_dir = history_dir / str(group_id)
    downloader = Downloader()
    # El nombre del equipo solo sirve para los próximos partidos, que aquí no hay.
    matches, _ = fetch_league(downloader, group_id, team_name="")
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "matches.json").write_text(
        json.dumps(matches, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for match in matches:
        download_match(downloader, match, raw_dir, current_season=False)
    return raw_dir


def past_players(history_dir: Path = HISTORY_DIR) -> pd.DataFrame:
    """Box score de todos los jugadores de las temporadas descargadas (vacío si no hay)."""
    tables = [
        build_tables(season)["players"]
        for season in sorted(history_dir.glob("*"))
        if (season / "matches.json").exists()
    ]
    return pd.concat(tables, ignore_index=True) if tables else pd.DataFrame()


def shooting_history(past: pd.DataFrame) -> pd.DataFrame:
    """Por jugador (uuid): triples anotados e intentados, puntos e intentos de TS% pasados."""
    if past.empty or "player_id" not in past.columns:
        return pd.DataFrame(columns=["T3M", "T3A", "PTS", "TSA"])
    totals = (
        past.dropna(subset=["player_id"])
        .groupby("player_id")[["T3M", "T3A", "PTS", "T2A", "T1A"]]
        .sum()
    )
    totals["TSA"] = totals["T2A"] + totals["T3A"] + 0.44 * totals["T1A"]
    return totals[["T3M", "T3A", "PTS", "TSA"]]


def main() -> None:
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        sys.exit("Uso: uv run python -m leioa_stats.history <id del grupo de basketbasko.com>")
    folder = download_season(int(sys.argv[1]))
    matches = json.loads((folder / "matches.json").read_text(encoding="utf-8"))
    print(f"{len(matches)} partidos en {folder}")


if __name__ == "__main__":
    main()
