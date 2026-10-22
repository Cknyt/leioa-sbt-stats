import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from leioa_stats.web import build, charts

FIXTURES = Path(__file__).parent / "fixtures"
MATCH_99138 = {
    "id": "99138",
    "uid": "6aca8d4dd75749bb61a6e292",
    "round": 1,
    "datetime": "2026-10-10 19:15:00",
    "local": "LEIOA SBT",
    "visitor": "EASO BASKET",
    "local_score": 76,
    "visitor_score": 70,
}


@pytest.fixture
def site(tmp_path):
    """Genera la web con el partido 99138 como única jornada."""
    raw = tmp_path / "raw"
    shutil.copytree(FIXTURES / "99138", raw / "matches" / "99138")
    (raw / "matches.json").write_text(json.dumps([MATCH_99138]), encoding="utf-8")
    (raw / "upcoming.json").write_text(json.dumps([UPCOMING]), encoding="utf-8")
    out = tmp_path / "site"
    pages = build.build_site(raw, out, "LEIOA SBT")
    return out, pages


UPCOMING = {
    "id": "99999",
    "uid": None,
    "round": 2,
    "datetime": "2026-10-17 18:00:00",
    "local": "EASO BASKET",
    "visitor": "LEIOA SBT",
    "local_score": None,
    "visitor_score": None,
}


def test_build_site_creates_pages(site):
    out, pages = site
    assert pages == [
        out / "index.html",
        out / "jugadores.html",
        out / "partidos" / "99138.html",
        out / "equipos" / "leioa-sbt.html",
        out / "equipos" / "easo-basket.html",
    ]
    assert (out / "style.css").exists()
    assert (out / "players.js").exists()


def test_next_match_links_to_rival_report(site):
    out, _ = site
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "Próximo partido · Jornada 2" in html
    assert '<span class="chip">17/10/2026 18:00</span>' in html
    assert '<span class="chip accent">Fuera</span>' in html
    assert 'href="equipos/easo-basket.html">Ver el informe del rival' in html


def test_team_page(site):
    out, _ = site
    html = (out / "equipos" / "easo-basket.html").read_text(encoding="utf-8")
    assert "Scouting" in html
    assert "Balance <strong>0-1</strong>" in html
    # Mapa del equipo + uno por cada uno de los 6 jugadores que más tiran.
    assert html.count('class="plotly-graph-div"') == 1 + build.TOP_SHOOTERS
    # Su partido contra el Leioa enlaza a la página del partido.
    assert 'href="../partidos/99138.html"' in html


@pytest.mark.parametrize(
    ("name", "expected"),
    [("ELABORADOS NATURALES VALLE DE EGÜÉS", "elaborados-naturales-valle-de-egues"),
     ("SPIRIT HOTELS & APARTMENTS SANTUTXU", "spirit-hotels-apartments-santutxu")],
)  # fmt: skip
def test_slug(name, expected):
    assert build.slug(name) == expected


def test_season_page(site):
    out, _ = site
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "<strong>1</strong><span>victorias" in html
    # Cifras destacadas con su puesto en la liga y barras de tiro por zonas.
    assert html.count('class="kpi"') == len(build.KPIS)
    assert 'class="zone-bar"' in html
    assert 'href="partidos/99138.html"' in html
    assert "Leioa SBT 76-70 Easo Basket" in html
    assert "Iñigo Carneros Villar" in html
    assert html.count('class="plotly-graph-div"') == 1


def test_players_page(site):
    out, _ = site
    html = (out / "jugadores.html").read_text(encoding="utf-8")
    assert 'aria-current="page">Jugadores' in html
    # Tarjeta propia solo con minutos suficientes; los demás, en una línea aparte.
    cards = html.count('<article class="player"')
    assert 0 < cards < 13
    assert f"Con menos de {build.MIN_MINUTES_FOR_CARD} minutos por partido" in html
    assert "Iñigo Carneros Villar" in html
    # Cada tarjeta lleva los valores con los que players.js la ordena.
    assert 'data-ts=""' not in html
    # La tabla completa sigue disponible.
    assert "Tabla completa de jugadores" in html


def test_match_page(site):
    out, _ = site
    html = (out / "partidos" / "99138.html").read_text(encoding="utf-8")
    assert "Jornada 1 · 10/10/2026 19:15" in html
    assert "85,6 posesiones" in html
    # Marcador, mapa de tiros del Leioa y mapa de tiros del rival.
    assert html.count('class="plotly-graph-div"') == 3
    # Aviso de validación: el cambio no anotado del Easo.
    assert "Julen Ugarte Aparicio".upper() in html


def test_pages_are_not_indexed(site):
    # Salen nombres de jugadores: la web no debe aparecer en buscadores.
    _, pages = site
    for page in pages:
        assert '<meta name="robots" content="noindex, nofollow">' in page.read_text(
            encoding="utf-8"
        )


def test_pages_have_no_missing_values(site):
    _, pages = site
    for page in pages:
        html = page.read_text(encoding="utf-8")
        assert ">nan<" not in html.lower()
        assert ">None<" not in html


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("IÑIGO CARNEROS VILLAR", "Iñigo Carneros Villar"),
        ("LEIOA SBT", "Leioa SBT"),
        ("CB SANTURTZI SK", "CB Santurtzi SK"),
        ("NAVASKET 1DM", "Navasket 1DM"),
    ],
)
def test_display_name(name, expected):
    assert build.display_name(name) == expected


@pytest.mark.parametrize(("value", "expected"), [(88.8, "88,8"), (85.0, "85"), (1.18, "1,18")])
def test_number(value, expected):
    assert build.number(value) == expected


def test_shot_chart_splits_made_and_missed():
    shots = pd.DataFrame(
        [
            {
                "made": True,
                "x": 6,
                "y": 50,
                "player": "A",
                "value": 2,
                "distance": 0.1,
                "period": 1,
            },
            {
                "made": False,
                "x": 30,
                "y": 50,
                "player": "B",
                "value": 3,
                "distance": 6.8,
                "period": 2,
            },
            {
                "made": False,
                "x": 80,
                "y": 50,
                "player": "C",
                "value": 3,
                "distance": 20,
                "period": 2,
            },
        ]
    )
    fig = charts.shot_chart(shots)
    made, missed = fig.data
    assert len(made.x) == 1
    assert len(missed.x) == 2
    # Un lanzamiento desde campo propio se dibuja junto a la línea central.
    assert max(missed.y) < charts.HALF_COURT
