from pathlib import Path

import pandas as pd
import pytest

from leioa_stats import parse
from leioa_stats.metrics import basic, shots
from leioa_stats.validate import load_match

FIXTURES = Path(__file__).parent / "fixtures"
MATCH_99138 = {
    "id": "99138",
    "round": 1,
    "local": "LEIOA SBT",
    "visitor": "EASO BASKET",
}


@pytest.fixture
def tables():
    stats, moves = load_match(FIXTURES / "99138")
    return {
        "players": pd.DataFrame(parse.player_rows(MATCH_99138, stats)),
        "teams": pd.DataFrame(parse.team_rows(MATCH_99138, stats)),
        "shots": pd.DataFrame(parse.shot_rows(MATCH_99138, stats, moves)),
    }


def test_player_rows(tables):
    players = tables["players"]
    leioa = players[players["team"] == "LEIOA SBT"]
    assert len(leioa) == 12
    assert leioa["PTS"].sum() == 76
    assert set(leioa["opponent"]) == {"EASO BASKET"}
    assert leioa["home"].all()


def test_team_rows_include_team_rebounds(tables):
    teams = tables["teams"].set_index("team")
    # 11 rebotes ofensivos de jugadores + 3 de equipo.
    assert teams.loc["LEIOA SBT", "RO"] == 14
    assert teams.loc["EASO BASKET", "home"] == False  # noqa: E712


def test_shot_rows_have_player(tables):
    shot_table = tables["shots"]
    assert len(shot_table) == 76 + 65
    assert shot_table["player"].notna().all()


def test_add_shooting():
    df = pd.DataFrame(
        [{"PTS": 20, "T1M": 4, "T1A": 5, "T2M": 5, "T2A": 10, "T3M": 2, "T3A": 6,
          "RO": 1, "RD": 3}]
    )  # fmt: skip
    row = basic.add_shooting(df).iloc[0]
    assert row["TCA"] == 16
    assert row["TC%"] == 43.8  # 7 / 16
    assert row["eFG%"] == 50.0  # (7 + 0,5 × 2) / 16
    assert row["TS%"] == 54.9  # 20 / (2 × (16 + 0,44 × 5)) = 20 / 36,4
    assert row["RT"] == 4


def test_add_shooting_without_attempts_is_empty():
    df = pd.DataFrame(
        [{"PTS": 0, "T1M": 0, "T1A": 0, "T2M": 0, "T2A": 0, "T3M": 0, "T3A": 0, "RO": 0, "RD": 0}]
    )
    assert pd.isna(basic.add_shooting(df).iloc[0]["T3%"])


def test_player_season_ignores_games_without_minutes(tables):
    second_game = tables["players"].assign(match_id="2", MIN=0)
    players = pd.concat([tables["players"], second_game])
    season = basic.player_season(players, "LEIOA SBT")
    assert (season["PJ"] <= 1).all()


def test_team_season(tables):
    season = basic.team_season(tables["teams"], "LEIOA SBT")
    assert season.loc["LEIOA SBT", "PTS/PJ"] == 76
    assert season.loc["Rivales", "PTS/PJ"] == 70


@pytest.mark.parametrize(
    ("value", "x", "y", "zone"),
    [
        (2, shots.BASKET_X, 50, "Cerca del aro"),
        (2, 20, 50, "Media distancia"),  # a unos 4 m
        (3, 5.6, 2.5, "Triple de esquina"),
        (3, 30, 50, "Triple frontal"),
    ],
)
def test_zones(value, x, y, zone):
    df = pd.DataFrame([{"value": value, "made": True, "x": x, "y": y}])
    assert shots.add_zones(df).iloc[0]["zone"] == zone


def test_coordinates_match_three_point_line(tables):
    # Calibración: la línea de triple está a 6,75 m del aro.
    zoned = shots.add_zones(tables["shots"])
    assert zoned.loc[zoned["value"] == 2, "distance"].max() < 6.75
    assert zoned.loc[zoned["value"] == 3, "distance"].min() > 6.75


def test_zone_summary(tables):
    summary = shots.zone_summary(tables["shots"])
    assert list(summary.index) == shots.ZONES
    assert summary["TCA"].sum() == 141
    assert summary["% de los tiros"].sum() == pytest.approx(100, abs=0.2)
