from pathlib import Path

import pandas as pd
import pytest

from leioa_stats import validate
from leioa_stats.metrics import lineups

FIXTURES = Path(__file__).parent / "fixtures"
MATCH_99138 = {"id": "99138", "round": 1, "local": "LEIOA SBT", "visitor": "EASO BASKET"}


@pytest.fixture
def match_99138():
    return validate.load_match(FIXTURES / "99138")


def stints_for(stats, moves) -> pd.DataFrame:
    return pd.DataFrame(lineups.stint_rows(MATCH_99138, stats, moves, "LEIOA SBT"))


def federation_plus_minus(player: dict) -> int:
    """+/- de la federación: diferencia de marcador entre cada entrada y su salida."""
    return sum(
        e["pointDiff"] if e["type"] == "OUT_TYPE" else -e["pointDiff"] for e in player["inOutsList"]
    )


@pytest.mark.parametrize(
    ("period", "minute", "second", "expected"),
    [(1, 9, 58, 2), (2, 10, 0, 600), (4, 0, 0, 2400), (5, 0, 0, 2700)],
)
def test_elapsed_seconds(period, minute, second, expected):
    move = {"period": period, "min": minute, "sec": second}
    assert lineups.elapsed_seconds(move, [10, 10, 10, 10, 5]) == expected


def test_stints_cover_the_whole_match(match_99138):
    stints = stints_for(*match_99138)
    assert stints["seconds"].sum() == 40 * 60
    assert (stints["size"] == 5).all()
    assert stints["PTS"].sum() == 76
    assert stints["PTS_opp"].sum() == 70


def test_plus_minus_matches_federation(match_99138):
    stats, moves = match_99138
    on_off = lineups.player_on_off(stints_for(stats, moves))
    leioa = next(t for t in stats["teams"] if t["name"] == "LEIOA SBT")
    for player in leioa["players"]:
        if player["timePlayed"] or player["inOutsList"]:
            name = player["name"]
            assert on_off.loc[name, "+/-"] == federation_plus_minus(player), name


def test_lineup_summary_skips_incomplete_lineups(match_99138):
    stats, moves = match_99138
    leioa = next(t for t in stats["teams"] if t["name"] == "LEIOA SBT")["teamIdIntern"]
    # Sin la primera entrada a pista, el Leioa juega un rato con 4 jugadores.
    first_sub_in = next(m for m in moves if m["idTeam"] == leioa and m["idMove"] == validate.SUB_IN)
    stints = stints_for(stats, [m for m in moves if m is not first_sub_in])
    assert (stints["size"] == 4).any()
    summary = lineups.lineup_summary(stints)
    assert summary["seconds"].sum() == stints.loc[stints["size"] == 5, "seconds"].sum()
    assert summary["seconds"].sum() < 40 * 60


def test_add_ratings():
    df = pd.DataFrame(
        [{"seconds": 300, "PTS": 12, "TCA": 10, "T1A": 0, "RO": 2, "PER": 2,
          "PTS_opp": 8, "TCA_opp": 9, "T1A_opp": 0, "RO_opp": 1, "PER_opp": 2}]
    )  # fmt: skip
    row = lineups.add_ratings(df).iloc[0]
    # Posesiones: (10 - 2 + 2 + 9 - 1 + 2) / 2 = 10.
    assert row["POSS"] == 10
    assert row["MIN"] == 5
    assert row["+/-"] == 4
    assert row["ORtg"] == 120
    assert row["DRtg"] == 80
    assert row["NETO"] == 40
