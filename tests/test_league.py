from pathlib import Path

import pandas as pd
import pytest

from leioa_stats import parse, validate
from leioa_stats.metrics import league, origins, quarters

FIXTURES = Path(__file__).parent / "fixtures"
MATCH_99138 = {"id": "99138", "round": 1, "local": "LEIOA SBT", "visitor": "EASO BASKET"}


@pytest.fixture
def tables():
    stats, moves = validate.load_match(FIXTURES / "99138")
    return {
        "players": pd.DataFrame(parse.player_rows(MATCH_99138, stats)),
        "teams": pd.DataFrame(parse.team_rows(MATCH_99138, stats)),
        "shots": pd.DataFrame(parse.shot_rows(MATCH_99138, stats, moves)),
        "quarters": pd.DataFrame(parse.quarter_rows(MATCH_99138, stats)),
        "origins": pd.DataFrame(origins.origin_rows(MATCH_99138, stats, moves)),
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


def test_team_profiles(tables):
    profiles = league.team_profiles(tables["teams"], tables["origins"])
    assert list(profiles.columns) == league.COMPARISON_COLUMNS
    # Leioa ganó 76-70: lo que encaja uno es lo que anota el otro.
    assert profiles.loc["LEIOA SBT", ["PTS/PJ", "Encajados/PJ"]].tolist() == [76, 70]
    assert profiles.loc["EASO BASKET", "Encajados/PJ"] == 76
    ranks = league.profile_ranks(profiles)
    assert ranks.loc["LEIOA SBT", "PTS/PJ"] == 1
    # En las que menos es mejor, el 1º es el que menos tiene.
    assert ranks.loc["LEIOA SBT", "Encajados/PJ"] == 1
    assert ranks.loc["LEIOA SBT", "PER/PJ"] == 1


def test_profile_average(tables):
    average = league.profile_average(tables["teams"], tables["origins"])
    assert average["PTS/PJ"] == average["Encajados/PJ"] == 73
    assert average["eFG% rival"] == average["eFG%"]
    assert average["Contraataque/PJ rival"] == average["Contraataque/PJ"]


def test_origin_rows_assign_every_point(tables):
    rows = tables["origins"].set_index("team")
    # Se reparten los mismos puntos que da el box score (76-70).
    assert rows["PTS"].to_dict() == {"LEIOA SBT": 76, "EASO BASKET": 70}
    for column in origins.ORIGIN_COLUMNS:
        assert (rows[column] <= rows["PTS"]).all()
    assert rows.loc["LEIOA SBT", "opponent"] == "EASO BASKET"


def _move(team, code, period=1, minute=9, second=0):
    return {"idTeam": team, "idMove": code, "period": period, "min": minute, "sec": second}


def test_origin_rows_follow_possession():
    stats = {
        "teams": [{"teamIdIntern": 1, "name": "A"}, {"teamIdIntern": 2, "name": "B"}],
        "periodDurationList": [10, 10, 10, 10],
    }
    moves = [
        _move(2, validate.TWO_MISSED, second=50),
        _move(1, validate.DEF_REBOUND, second=48),
        _move(1, validate.TWO_MADE, second=44),  # contraataque: 4 s tras el rebote
        _move(2, validate.TURNOVER, second=30),
        _move(1, validate.THREE_MISSED, second=10),
        _move(1, validate.OFF_REBOUND, second=8),
        _move(1, validate.THREE_MADE, second=5),  # 2ª oportunidad, en la posesión tras pérdida
        _move(2, validate.TWO_MADE, minute=8, second=50),  # B ataca tras la canasta: sin origen
    ]
    rows = {r["team"]: r for r in origins.origin_rows({"id": "1"}, stats, moves)}
    assert rows["A"]["PTS"] == 5
    assert rows["A"]["Contraataque"] == 2
    assert rows["A"]["2ª oportunidad"] == 3
    assert rows["A"]["Tras pérdida"] == 0
    assert rows["A"]["RO"] == 1
    assert rows["B"]["PTS"] == 2
    assert rows["B"]["Contraataque"] == rows["B"]["Tras pérdida"] == 0


def test_quarter_summary(tables):
    summary = quarters.quarter_summary(tables["quarters"], tables["shots"], "LEIOA SBT")
    assert list(summary.index) == ["C1", "C2", "C3", "C4"]
    # Parciales del 99138: 22-20, 22-16, 14-17 y 18-17.
    assert summary["PTS/PJ"].tolist() == [22, 22, 14, 18]
    assert summary["Encajados/PJ"].tolist() == [20, 16, 17, 17]
    assert summary.loc["C3", "DIF/PJ"] == -3
    # Las pérdidas forzadas son las del rival en ese cuarto.
    easo = quarters.quarter_summary(tables["quarters"], tables["shots"], "EASO BASKET")
    assert summary["Forzadas/PJ"].tolist() == easo["PER/PJ"].tolist()


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
