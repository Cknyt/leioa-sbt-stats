from pathlib import Path

import pandas as pd
import pytest

from leioa_stats import parse
from leioa_stats.metrics import advanced
from leioa_stats.validate import load_match

FIXTURES = Path(__file__).parent / "fixtures"
MATCH_99138 = {"id": "99138", "round": 1, "local": "LEIOA SBT", "visitor": "EASO BASKET"}


@pytest.fixture
def tables():
    stats, _ = load_match(FIXTURES / "99138")
    return {
        "players": pd.DataFrame(parse.player_rows(MATCH_99138, stats)),
        "teams": pd.DataFrame(parse.team_rows(MATCH_99138, stats)),
    }


def test_possessions(tables):
    # Leioa: 76 + 0,44 × 21 - 14 + 15 = 86,24. Easo: 65 + 0,44 × 25 - 17 + 26 = 85.
    games = advanced.team_games(tables["teams"]).set_index("team")
    assert games.loc["LEIOA SBT", "POSS_EST"] == pytest.approx(86.24)
    assert games.loc["EASO BASKET", "POSS_EST"] == pytest.approx(85)
    assert games.loc["LEIOA SBT", "POSS"] == pytest.approx(85.62)
    assert games.loc["EASO BASKET", "POSS"] == pytest.approx(85.62)


def test_games_summary(tables):
    summary = advanced.games_summary(tables["teams"], "LEIOA SBT")
    row = summary.loc[(1, "EASO BASKET")]
    assert row["RITMO"] == 85.6
    assert row["ORtg"] == 88.8  # 100 × 76 / 85,62
    assert row["DRtg"] == 81.8  # 100 × 70 / 85,62
    assert row["NETO"] == 7.0


def test_four_factors(tables):
    factors = advanced.team_advanced(tables["teams"], "LEIOA SBT")
    leioa, rivals = factors["LEIOA SBT"], factors["Rivales"]
    assert leioa["RO%"] == 26.4  # 14 / (14 + 39)
    assert rivals["RO%"] == 38.6  # 17 / (17 + 27), con el rebote defensivo de equipo
    assert leioa["PER%"] == 17.5  # 15 / 85,62
    assert leioa["TL/TC"] == 17.1  # 13 / 76
    assert leioa["eFG%"] == 41.4  # (26 + 0,5 × 11) / 76


def test_usage_averages_twenty_percent(tables):
    # Ponderado por minutos, el uso medio de los jugadores de un equipo es el 20 % (1 de 5).
    usage = advanced.player_usage(tables["players"], tables["teams"], "LEIOA SBT")
    players = tables["players"].set_index("player")
    minutes = players.loc[usage.index, "MIN"]
    assert (usage * minutes).sum() / minutes.sum() == pytest.approx(20, abs=0.5)
