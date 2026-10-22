from pathlib import Path

import pytest

from leioa_stats import validate

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def match_99138():
    # Partido real: Leioa SBT 76-70 Easo Basket (jornada 1).
    return validate.load_match(FIXTURES / "99138")


def details(issues, severity=None, check=None):
    return [
        f"{i.team}: {i.detail}"
        for i in issues
        if (severity is None or i.severity == severity) and (check is None or i.check == check)
    ]


def test_real_match_has_no_errors(match_99138):
    issues = validate.validate_match(*match_99138)
    assert details(issues, severity="error") == []


def test_real_match_team_rebounds_are_info(match_99138):
    issues = validate.validate_match(*match_99138)
    assert "LEIOA SBT: rebotes ofensivos de equipo (sin jugador): 3" in details(issues, "info")


def test_real_match_detects_missing_substitution(match_99138):
    issues = validate.check_lineups(*match_99138)
    found = details(issues, "aviso")
    assert len(found) == 1
    assert found[0].startswith("EASO BASKET: JULEN UGARTE APARICIO hace 2 acciones")


def test_detects_wrong_score(match_99138):
    stats, moves = match_99138
    # Quitamos la primera canasta de 2: el marcador anotado deja de cuadrar.
    first_basket = next(m for m in moves if m["idMove"] == validate.TWO_MADE)
    moves = [m for m in moves if m is not first_basket]
    assert details(validate.check_score(stats, moves), "error")
    assert details(validate.check_box_totals(stats, moves), "error")


def test_detects_missing_shot_coordinates(match_99138):
    stats, moves = match_99138
    period = stats["teams"][0]["periods"][0]
    period["shootingOfTwoFailedPoint"] = period["shootingOfTwoFailedPoint"][1:]
    issues = validate.check_shot_coordinates(stats, moves)
    assert details(issues, "aviso") == ["LEIOA SBT: 75 tiros con coordenadas de 76 tiros de campo"]


def test_detects_unannotated_substitution(match_99138):
    stats, moves = match_99138
    leioa = stats["teams"][0]["teamIdIntern"]
    # Borramos la primera entrada a pista de un jugador del Leioa.
    first_sub_in = next(m for m in moves if m["idTeam"] == leioa and m["idMove"] == validate.SUB_IN)
    moves = [m for m in moves if m is not first_sub_in]
    issues = validate.check_lineups(stats, moves)
    assert any(i.team == "LEIOA SBT" for i in issues)


def test_detects_unknown_foul_code(match_99138):
    stats, moves = match_99138
    moves[0] = {**moves[0], "idMove": 999, "move": "999, 1a falta"}
    issues = validate.check_unknown_moves(moves)
    assert details(issues, "aviso") == ["None: código 999 desconocido ('999, 1a falta'), 1 veces"]
