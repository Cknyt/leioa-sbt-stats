import pandas as pd
import pytest

from leioa_stats import staff
from leioa_stats.metrics import preview
from leioa_stats.metrics.insights import Fact


def fact(key, value, z, se, average=45.0, subject="X"):
    return Fact(key=key, subject=subject, value=value, average=average, z=z, n=10, se=se)


def test_advantage():
    # Nuestro eFG% 50 (liga 45) contra una defensa que permite 49: esperable 54.
    # z = (5 + 4) / √(2² + 2²) = 3,2 → ventaja con confianza alta.
    own = [fact("eFG%", 50, 2.5, 2.0)]
    rival = [fact("eFG% rival", 49, -2.0, 2.0)]
    (m,) = preview.matchups(own, rival)
    assert m.side == "ataque"
    assert m.expected == 54
    assert m.verdict == "ventaja"
    assert m.confidence == "alta"
    assert preview.describe(m, "Leioa", "Rival").startswith("Hacer daño con el tiro (eFG%)")


def test_clash_of_strengths():
    # Buen ataque contra buena defensa: los dos con z ≥ 1,5 por separado.
    own = [fact("eFG%", 50, 2.5, 2.0)]
    rival = [fact("eFG% rival", 40, 2.5, 2.0)]
    (m,) = preview.matchups(own, rival)
    assert m.verdict == "choque"
    assert preview.describe(m, "Leioa", "Rival").startswith("Choque de fuerzas")


def test_turnovers_lower_is_better_and_defense_side():
    # Su ataque pierde 26 (liga 22) y nuestra defensa fuerza 25: malo para ellos, bueno para
    # nosotros. z para nosotros = (4 + 3) / √(1,2² + 1,2²) = 4,1.
    rival = [fact("PER%", 26, -3.3, 1.2, average=22)]
    own = [fact("PER% rival", 25, 2.5, 1.2, average=22)]
    (m,) = preview.matchups(own, rival)
    assert m.side == "defensa"
    assert m.verdict == "ventaja"
    assert m.z == pytest.approx(7 / (1.2 * 2**0.5))


def test_noise_has_no_verdict():
    own = [fact("eFG%", 46, 0.5, 2.0)]
    rival = [fact("eFG% rival", 46, -0.5, 2.0)]
    (m,) = preview.matchups(own, rival)
    assert m.verdict == ""
    assert preview.key_matchups([m]) == []


def test_fulfilled():
    own = [fact("eFG%", 50, 2.5, 2.0)]
    rival = [fact("eFG% rival", 49, -2.0, 2.0)]
    (m,) = preview.matchups(own, rival)
    # Ventaja en el tiro: se cumple si tiramos por encima de la media de la liga (45).
    assert preview.fulfilled(m, 47) is True
    assert preview.fulfilled(m, 42) is False
    assert preview.fulfilled(m, float("nan")) is None


def test_shot_facts():
    shots = pd.DataFrame(
        {
            "team": ["A"] * 4 + ["B"] * 4,
            "opponent": ["B"] * 4 + ["A"] * 4,
            "value": [3, 3, 2, 2, 3, 3, 2, 2],
            "made": [True, True, True, False, False, False, True, True],
            "zone": ["Triple frontal"] * 2 + ["Cerca del aro"] * 2
            + ["Triple frontal"] * 2 + ["Cerca del aro"] * 2,
        }
    )  # fmt: skip
    facts = {f.key: f for f in preview.shot_facts("A", shots)}
    assert facts["T3%"].value == 100
    assert facts["T3% rival"].value == 0
    # Su defensa del triple deja un 0 %: bueno para A (z positiva).
    assert facts["T3% rival"].z > 0


def test_staff_sheet(tmp_path):
    path = tmp_path / "plantilla.csv"
    path.write_text(
        "equipo,jugador,posicion,altura,disponible\n"
        "Leioa SBT,  iñigo carneros villar ,Base,1.82,si\n"
        "LEIOA SBT,PEDRO SAROBE FEIJOO,,,no\n",
        encoding="utf-8",
    )
    sheet = staff.load_staff(path)
    assert staff.describe_player(sheet, "LEIOA SBT", "IÑIGO CARNEROS VILLAR") == "Base, 1,82 m"
    assert staff.unavailable(sheet, "LEIOA SBT") == ["PEDRO SAROBE FEIJOO"]
    assert staff.describe_player(sheet, "OTRO", "NADIE") == ""


def test_staff_sheet_is_optional(tmp_path):
    sheet = staff.load_staff(tmp_path / "no-existe.csv")
    assert sheet.empty
    assert staff.unavailable(sheet, "LEIOA SBT") == []
