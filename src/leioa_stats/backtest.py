"""Prueba retrospectiva: ¿las conclusiones de las primeras jornadas siguen siendo ciertas después?

Uso:
    uv run python -m leioa_stats.backtest [carpeta de datos] [jornada de corte]

Por defecto usa la temporada actual (data/raw) y corta en la mitad de las jornadas jugadas.
Con una temporada pasada completa (data/raw/history/<id>) y corte en la jornada 4, dice qué
habría pasado con las conclusiones de la jornada 4 al final de la temporada.

Para cada equipo y cada métrica de metrics/insights.METRICS se calcula el hecho con las
jornadas hasta el corte y con todas. Una conclusión "se mantiene" si al final el equipo sigue
del mismo lado de la media de la liga. Así se puede comprobar si los umbrales de confianza
(1,5 y 2 errores estándar) están bien puestos: las de confianza alta deberían mantenerse casi
siempre, y las que no se muestran, más o menos la mitad de las veces que las otras.
"""

import sys
from pathlib import Path

import pandas as pd

from leioa_stats.metrics.advanced import team_games
from leioa_stats.metrics.confidence import league_spread
from leioa_stats.metrics.insights import team_facts
from leioa_stats.metrics.league import league_average, league_table
from leioa_stats.parse import RAW_DIR, build_tables


def facts_at(teams: pd.DataFrame) -> pd.DataFrame:
    """Una fila por equipo y métrica: z (positiva = mejor que la media) y confianza."""
    league = league_table(teams)
    average = league_average(teams)
    spread = league_spread(team_games(teams))
    rows = []
    for team in league.index:
        for fact in team_facts(team, league, average, spread):
            rows.append(
                {
                    "team": team,
                    "metric": fact.key,
                    "z": fact.z,
                    "confidence": fact.confidence or "sin conclusión",
                }
            )
    return pd.DataFrame(rows)


def backtest(teams: pd.DataFrame, cut_round: int) -> pd.DataFrame:
    """Por nivel de confianza en el corte: cuántas conclusiones hay y qué % se mantiene."""
    early = facts_at(teams[teams["round"] <= cut_round])
    final = facts_at(teams)
    merged = early.merge(final, on=["team", "metric"], suffixes=("", "_final"))
    merged["kept"] = (merged["z"] > 0) == (merged["z_final"] > 0)
    summary = merged.groupby("confidence")["kept"].agg(["size", "mean"])
    summary.columns = ["conclusiones", "% se mantiene"]
    summary["% se mantiene"] = (100 * summary["% se mantiene"]).round(1)
    return summary.reindex(["alta", "media", "sin conclusión"]).dropna()


def main() -> None:
    raw_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else RAW_DIR
    teams = build_tables(raw_dir)["teams"]
    last = int(teams["round"].max())
    cut = int(sys.argv[2]) if len(sys.argv) > 2 else max(1, last // 2)
    print(f"Conclusiones con las jornadas 1-{cut}, comprobadas con las 1-{last}:")
    print(backtest(teams, cut).to_string())


if __name__ == "__main__":
    main()
