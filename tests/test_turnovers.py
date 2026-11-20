from pathlib import Path

import pandas as pd

from leioa_stats import validate
from leioa_stats.metrics import turnovers

FIXTURES = Path(__file__).parent / "fixtures"
MATCH_99138 = {"id": "99138", "round": 1, "local": "LEIOA SBT", "visitor": "EASO BASKET"}


def test_every_turnover_has_one_type():
    stats, moves = validate.load_match(FIXTURES / "99138")
    rows = pd.DataFrame(turnovers.turnover_rows(MATCH_99138, stats, moves))
    in_moves = sum(m["idMove"] == validate.TURNOVER for m in moves)
    assert rows[turnovers.TURNOVER_TYPES].to_numpy().sum() == in_moves
    profiles = turnovers.turnover_profiles(rows)
    # Las pérdidas forzadas de un equipo son las propias del otro.
    leioa, easo = profiles.loc["LEIOA SBT"], profiles.loc["EASO BASKET"]
    assert leioa["Con robo forzadas"] == easo["Con robo"]
    assert 0 <= turnovers.live_share(rows) <= 100


def move(team, code, sec=30):
    return {"idTeam": team, "idMove": code, "period": 1, "min": 5, "sec": sec}


def test_turnover_type():
    steal = [move(1, validate.TURNOVER), move(2, validate.STEAL)]
    assert turnovers.turnover_type(steal, 0) == "Con robo"
    foul = [move(1, turnovers.OFFENSIVE_FOUL), move(1, validate.TURNOVER)]
    assert turnovers.turnover_type(foul, 1) == "Falta en ataque"
    # Una recuperación en otro segundo es de otra jugada.
    later = [move(1, validate.TURNOVER), move(2, validate.STEAL, sec=10)]
    assert turnovers.turnover_type(later, 0) == "Otras"
