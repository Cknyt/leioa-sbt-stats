from pathlib import Path

import pandas as pd
import pytest

from leioa_stats import parse, validate
from leioa_stats.metrics import league

FIXTURES = Path(__file__).parent / "fixtures"
MATCH_99138 = {"id": "99138", "round": 1, "local": "LEIOA SBT", "visitor": "EASO BASKET"}


@pytest.fixture
def tables():
    stats, moves = validate.load_match(FIXTURES / "99138")
    return {
        "players": pd.DataFrame(parse.player_rows(MATCH_99138, stats)),
        "teams": pd.DataFrame(parse.team_rows(MATCH_99138, stats)),
        "shots": pd.DataFrame(parse.shot_rows(MATCH_99138, stats, moves)),
    }


def test_league_table(tables):
    table = league.league_table(tables["teams"])
    assert list(table.index) == ["LEIOA SBT", "EASO BASKET"]
    assert table.loc["LEIOA SBT", ["PJ", "V", "D"]].tolist() == [1, 1, 0]
    # Lo que permite un equipo es lo que hace su rival.
    assert table.loc["LEIOA SBT", "eFG% rival"] == table.loc["EASO BASKET", "eFG%"]


def test_ranks(tables):
    table = league.league_table(tables["teams"])
    leioa = league.ranks(table, "LEIOA SBT")
    assert leioa["NETO"] == 1
    # Leioa pierde menos balones que Easo (15 frente a 26): mejor puesto en PER%.
    assert leioa["PER%"] == 1


def test_league_average_is_balanced(tables):
    average = league.league_average(tables["teams"])
    # En toda la liga, los puntos anotados son los recibidos.
    assert average["ORtg"] == average["DRtg"]


@pytest.mark.parametrize(
    ("near", "threes", "offensive_rebounds", "attempts", "expected"),
    [
        (60, 10, 1, 20, "Interior"),
        (30, 10, 4, 20, "Interior"),
        (10, 60, 1, 20, "Exterior"),
        (30, 30, 1, 20, "Mixto"),
        (90, 0, 5, 9, "Pocos tiros"),
    ],
)
def test_profile(near, threes, offensive_rebounds, attempts, expected):
    row = pd.Series(
        {"TCA": attempts, "% cerca del aro": near, "% triples": threes, "RO/40": offensive_rebounds}
    )
    assert league._profile(row) == expected


def test_player_profiles(tables):
    profiles = league.player_profiles(tables["players"], tables["shots"], "LEIOA SBT")
    assert profiles["TCA"].sum() == 76
    assert set(profiles["Perfil"]) <= {"Interior", "Exterior", "Mixto", "Pocos tiros"}


def test_dunk_counts_as_two_points():
    stats, moves = validate.load_match(FIXTURES / "99138")
    # Convertimos una canasta de 2 en un mate: los totales deben seguir cuadrando.
    first_basket = next(m for m in moves if m["idMove"] == validate.TWO_MADE)
    first_basket["idMove"] = validate.DUNK
    issues = validate.validate_match(stats, moves)
    assert [i for i in issues if i.severity == "error"] == []
