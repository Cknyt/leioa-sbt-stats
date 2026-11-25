"""Comparación entre temporadas (metrics/seasons.py) y su página."""

import json
import math
import shutil
from pathlib import Path

import pytest

from leioa_stats import history, parse
from leioa_stats.metrics import seasons
from leioa_stats.web import build

FIXTURES = Path(__file__).parent / "fixtures"
MATCH_99138 = {
    "id": "99138",
    "round": 1,
    "datetime": "2026-10-10 19:15:00",
    "local": "LEIOA SBT",
    "visitor": "EASO BASKET",
    "local_score": 76,
    "visitor_score": 70,
}


def copy_season(folder: Path) -> Path:
    """El partido 99138 como única jornada de una temporada."""
    shutil.copytree(FIXTURES / "99138", folder / "matches" / "99138")
    (folder / "matches.json").write_text(json.dumps([MATCH_99138]), encoding="utf-8")
    return folder


@pytest.fixture
def tables(tmp_path):
    return parse.build_tables(copy_season(tmp_path / "raw"))


def test_team_seasons(tables):
    summary = seasons.team_seasons({"2025-26": tables["teams"]}, "LEIOA SBT")
    row = summary.loc["2025-26"]
    assert (row["PJ"], row["V"], row["D"], row["Puesto"], row["equipos"]) == (1, 1, 0, 1, 2)
    assert row["PTS/PJ"] == 76
    assert row["Encajados/PJ"] == 70
    # Con dos equipos, el que anota más es 1.º en ataque y el que encaja menos, en defensa.
    assert row["ORtg puesto"] == 1
    assert row["DRtg puesto"] == 1
    # Un partido: la media de la liga es la de los dos equipos juntos.
    assert row["ORtg"] > row["ORtg liga"] > row["DRtg"]
    # Una temporada sin el equipo se salta.
    assert seasons.team_seasons({"2025-26": tables["teams"]}, "NADIE").empty


def test_change_z():
    # 40 % con 100 intentos frente a 30 % con 100: z ≈ 1,49 (por debajo de "media").
    z = seasons.change_z(40, 100, 30, 100)
    assert z == pytest.approx(1.486, abs=0.01)
    assert seasons.change_z(30, 100, 40, 100) == pytest.approx(-z)
    assert math.isnan(seasons.change_z(3, 0, 3, 10))
    assert math.isnan(seasons.change_z(0, 10, 0, 10))


def test_returning_players(tables):
    both = {"2025-26": tables, "2026-27": tables}
    players = seasons.returning_players(both, "2026-27", "LEIOA SBT")
    played = tables["players"].query("team == 'LEIOA SBT' and MIN > 0")
    assert len(players) == played["player_id"].nunique()
    first = players[0]
    assert list(first["table"].index) == ["2025-26", "2026-27"]
    assert list(first["table"].columns) == seasons.PLAYER_COLUMNS
    assert first["compared_with"] == "2025-26"
    # Las mismas cifras las dos temporadas: no hay cambio.
    assert first["changes"] == {"TS%": None, "T3%": None}
    # Sin temporadas pasadas no sigue nadie.
    assert seasons.returning_players({"2026-27": tables}, "2026-27", "LEIOA SBT") == []


def test_past_seasons_named_and_ordered(tmp_path):
    for group in (2511, 2138):
        copy_season(tmp_path / "history" / str(group))
    past = history.past_seasons(tmp_path / "history")
    assert list(past) == ["2024-25", "2025-26"]
    assert len(history.past_players(seasons=past)) == 2 * len(past["2024-25"]["players"])


def test_seasons_page(tmp_path):
    raw = copy_season(tmp_path / "raw")
    copy_season(raw / "history" / "2511")
    (raw / "upcoming.json").write_text("[]", encoding="utf-8")
    out = tmp_path / "site"
    build.build_site(raw, out, "LEIOA SBT")
    html = (out / "temporadas.html").read_text(encoding="utf-8")
    assert 'aria-current="page">Temporadas' in html
    assert "<th>2025-26</th>" in html and "<th>2026-27</th>" in html
    assert "1.º de 2" in html
    assert 'class="player-card"' in html
    assert "No hay temporadas pasadas" not in html
