"""Gráficos interactivos con plotly: mapa de tiros y evolución del marcador.

El mapa de tiros dibuja media cancha FIBA en metros, con el aro abajo:
eje horizontal = ancho de la cancha (0-15 m), eje vertical = distancia a la línea de fondo.
"""

import math

import pandas as pd
import plotly.graph_objects as go

from leioa_stats.metrics.lineups import elapsed_seconds
from leioa_stats.metrics.shots import BASKET_X, COURT_LENGTH, COURT_WIDTH
from leioa_stats.validate import POINTS

MADE_COLOR = "#1a9850"
MISSED_COLOR = "#d73027"
LINE_COLOR = "#8a8f98"
TEAM_COLOR = "#0b3d91"
RIVAL_COLOR = "#c0392b"

HALF_COURT = COURT_LENGTH / 2
BASKET = (COURT_WIDTH / 2, BASKET_X / 100 * COURT_LENGTH)  # (7,5 m; 1,575 m)
THREE_POINT_RADIUS = 6.75
CORNER_THREE_OFFSET = 0.9  # distancia del triple de esquina a la banda
PAINT_WIDTH, PAINT_DEPTH = 4.9, 5.8
FREE_THROW_RADIUS = 1.8

CONFIG = {"displayModeBar": False, "responsive": True}


def _arc(cx: float, cy: float, r: float, start: float, end: float, n: int = 60) -> str:
    """Trazo SVG de un arco (ángulos en grados, 0 = derecha, 90 = hacia el medio campo)."""
    points = [
        (cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))
        for a in [start + (end - start) * i / n for i in range(n + 1)]
    ]
    return "M " + " L ".join(f"{x:.3f},{y:.3f}" for x, y in points)


def court_shapes() -> list[dict]:
    """Líneas de media cancha FIBA."""
    line = {"color": LINE_COLOR, "width": 1.5}
    bx, by = BASKET
    # El arco del triple se une al tramo recto de las esquinas.
    corner_x = COURT_WIDTH / 2 - CORNER_THREE_OFFSET
    corner_angle = math.degrees(math.acos(corner_x / THREE_POINT_RADIUS))
    corner_y = by + THREE_POINT_RADIUS * math.sin(math.radians(corner_angle))
    left, right = CORNER_THREE_OFFSET, COURT_WIDTH - CORNER_THREE_OFFSET
    paint_left = bx - PAINT_WIDTH / 2
    return [
        {"type": "rect", "x0": 0, "y0": 0, "x1": COURT_WIDTH, "y1": HALF_COURT, "line": line},
        {
            "type": "rect",
            "x0": paint_left,
            "y0": 0,
            "x1": paint_left + PAINT_WIDTH,
            "y1": PAINT_DEPTH,
            "line": line,
        },
        {"type": "path", "path": _arc(bx, PAINT_DEPTH, FREE_THROW_RADIUS, 0, 180), "line": line},
        {"type": "line", "x0": left, "y0": 0, "x1": left, "y1": corner_y, "line": line},
        {"type": "line", "x0": right, "y0": 0, "x1": right, "y1": corner_y, "line": line},
        {
            "type": "path",
            "path": _arc(bx, by, THREE_POINT_RADIUS, corner_angle, 180 - corner_angle),
            "line": line,
        },
        {"type": "path", "path": _arc(bx, by, 1.25, 0, 180), "line": line},
        {"type": "line", "x0": bx - 0.9, "y0": 1.2, "x1": bx + 0.9, "y1": 1.2, "line": line},
        {
            "type": "circle",
            "x0": bx - 0.225,
            "y0": by - 0.225,
            "x1": bx + 0.225,
            "y1": by + 0.225,
            "line": {"color": "#e67e22", "width": 2},
        },
        {"type": "path", "path": _arc(bx, HALF_COURT, 1.8, 180, 360), "line": line},
    ]


def shot_chart(shots: pd.DataFrame, title: str = "", height: int = 520) -> go.Figure:
    """Mapa de tiros. Necesita las columnas de parse.shot_rows y la distancia de add_zones."""
    fig = go.Figure()
    for made, name, color, symbol in (
        (True, "Anotado", MADE_COLOR, "circle"),
        (False, "Fallado", MISSED_COLOR, "x"),
    ):
        df = shots[shots["made"] == made]
        fig.add_trace(
            go.Scatter(
                x=df["y"] / 100 * COURT_WIDTH,
                # Los tiros desde más allá de medio campo se dibujan pegados a la línea central.
                y=(df["x"] / 100 * COURT_LENGTH).clip(upper=HALF_COURT - 0.2),
                mode="markers",
                name=f"{name} ({len(df)})",
                marker={"color": color, "symbol": symbol, "size": 9, "opacity": 0.75},
                customdata=df[["player", "value", "distance", "period"]].to_numpy(),
                hovertemplate=(
                    "%{customdata[0]}<br>Tiro de %{customdata[1]}, a %{customdata[2]:.1f} m"
                    "<br>Cuarto %{customdata[3]}<extra></extra>"
                ),
            )
        )
    fig.update_layout(
        title=title or None,
        shapes=court_shapes(),
        xaxis={"range": [-0.3, COURT_WIDTH + 0.3], "visible": False, "fixedrange": True},
        yaxis={
            "range": [-0.3, HALF_COURT + 0.3],
            "visible": False,
            "scaleanchor": "x",
            "fixedrange": True,
        },
        legend={"orientation": "h", "y": -0.02},
        margin={"l": 5, "r": 5, "t": 40 if title else 5, "b": 5},
        plot_bgcolor="#fbf7ef",
        paper_bgcolor="rgba(0,0,0,0)",
        height=height,
    )
    return fig


def score_timeline(stats: dict, moves: list[dict], team_name: str) -> go.Figure:
    """Diferencia en el marcador a lo largo del partido (positiva = gana el equipo)."""
    home = next(t for t in stats["teams"] if t["teamIdIntern"] == stats["localId"])
    sign = 1 if home["name"] == team_name else -1
    durations = stats["periodDurationList"]
    times, diffs, labels = [0.0], [0], ["0-0"]
    for move in moves:
        if move["idMove"] not in POINTS:
            continue
        local, visitor = (int(v) for v in move["score"].split("-"))
        times.append(elapsed_seconds(move, durations) / 60)
        diffs.append(sign * (local - visitor))
        labels.append(move["score"])
    fig = go.Figure(
        go.Scatter(
            x=times,
            y=diffs,
            mode="lines",
            line={"shape": "hv", "color": TEAM_COLOR, "width": 2},
            fill="tozeroy",
            customdata=labels,
            hovertemplate="Minuto %{x:.1f}<br>Marcador %{customdata}<extra></extra>",
        )
    )
    quarter_ends = [sum(durations[: i + 1]) for i in range(len(durations) - 1)]
    for end in quarter_ends:
        fig.add_vline(x=end, line={"color": LINE_COLOR, "dash": "dot", "width": 1})
    fig.add_hline(y=0, line={"color": LINE_COLOR, "width": 1})
    fig.update_layout(
        xaxis={"title": "Minuto", "range": [0, sum(durations)], "fixedrange": True},
        yaxis={"title": "Diferencia de puntos", "fixedrange": True, "zeroline": False},
        margin={"l": 50, "r": 10, "t": 10, "b": 40},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=280,
        showlegend=False,
    )
    return fig


def to_html(fig: go.Figure) -> str:
    """HTML del gráfico sin la librería plotly.js, que la página carga una sola vez."""
    return fig.to_html(full_html=False, include_plotlyjs=False, config=CONFIG)
