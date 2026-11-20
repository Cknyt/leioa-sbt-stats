from pathlib import Path

import pandas as pd
import pytest

from leioa_stats import parse, validate
from leioa_stats.metrics import insights, league
from leioa_stats.metrics.advanced import player_usage, team_games
from leioa_stats.metrics.basic import player_season
from leioa_stats.metrics.quarters import QUARTER_COLUMNS
from leioa_stats.metrics.shots import add_zones, zone_summary
from leioa_stats.web import build
from leioa_stats.web.glossary import TERMS

FIXTURES = Path(__file__).parent / "fixtures"
MATCH_99138 = {"id": "99138", "round": 1, "local": "LEIOA SBT", "visitor": "EASO BASKET"}


@pytest.fixture
def tables():
    stats, moves = validate.load_match(FIXTURES / "99138")
    return {
        "players": pd.DataFrame(parse.player_rows(MATCH_99138, stats)),
        "teams": pd.DataFrame(parse.team_rows(MATCH_99138, stats)),
        "shots": add_zones(pd.DataFrame(parse.shot_rows(MATCH_99138, stats, moves))),
        "moves": moves,
    }


LEAGUE_VALUES = {"RITMO": 82.0, "ORtg": 94.0, "DRtg": 94.0, "NETO": 0.0, "eFG%": 45.0,
                 "PER%": 22.0, "RO%": 34.0, "TL/TC": 23.0, "eFG% rival": 45.0,
                 "PER% rival": 22.0, "RO% rival": 34.0, "TL/TC rival": 23.0}  # fmt: skip


def synthetic_league(games: int, **teams: dict) -> tuple[pd.DataFrame, pd.Series]:
    """Liga en la que todos los equipos están en la media salvo lo que se indique."""
    rows = {name: {"PJ": games, "V": 0, "D": games, **LEAGUE_VALUES, **values}
            for name, values in teams.items()}  # fmt: skip
    return pd.DataFrame(rows).T, pd.Series(LEAGUE_VALUES)


def insights_with(tables, league_table, average, team="LEIOA SBT", **kwargs):
    season = player_season(tables["players"], team).join(
        player_usage(tables["players"], tables["teams"], team)
    )
    shots = tables["shots"]
    return insights.team_insights(
        team, league_table, average, season, shots[shots["team"] == team], shots, **kwargs
    )


def test_strengths_need_distance_not_rank(tables):
    # 110 frente a 94 en 16 partidos: error estándar 11,9 / 4 = 2,98, z = 5,4.
    # 25,5 frente a 22 en pérdidas: z = 3,5 / (4,6 / 4) = 3,0 → debilidad con confianza alta.
    league_table, average = synthetic_league(
        16, **{"LEIOA SBT": {"ORtg": 110.0, "PER%": 25.5}, "B": {"ORtg": 98.0}, "C": {}}
    )
    result = insights_with(tables, league_table, average)
    strength = next(i for i in result.strengths if i.text.startswith("Ataque muy eficiente"))
    assert strength.confidence == "alta"
    assert "(1.º de 3; media de la liga 94)" in strength.text
    assert any(i.text.startswith("Pierde muchos balones") for i in result.weaknesses)
    # B es el 2.º de 3 en ataque, pero solo está a 1,3 errores estándar de la media: no sale.
    other = insights_with(tables, league_table, average, team="B")
    assert not other.strengths


def test_few_games_give_no_conclusions(tables):
    # Las mismas cifras con 1 partido: z = 16 / 11,9 = 1,3, todavía puede ser suerte.
    league_table, average = synthetic_league(1, **{"LEIOA SBT": {"ORtg": 110.0}, "B": {}})
    result = insights_with(tables, league_table, average)
    assert not any(i.text.startswith("Ataque muy eficiente") for i in result.strengths)
    fact = next(f for f in result.facts if f.key == "ORtg")
    assert fact.confidence is None
    assert round(fact.z, 2) == 1.34


def test_medium_confidence(tables):
    # z = 4,8 / (11,9 / 4) = 1,6 → confianza media.
    league_table, average = synthetic_league(16, **{"LEIOA SBT": {"ORtg": 98.8}, "B": {}})
    result = insights_with(tables, league_table, average)
    assert [i.confidence for i in result.strengths] == ["media"]


def test_press_idea_needs_live_ball_turnovers(tables):
    league_table, average = synthetic_league(16, **{"LEIOA SBT": {"PER%": 26.0}, "B": {}})
    press = "Presionar el balón"
    # Sin saber el tipo de pérdidas, no se propone presionar.
    unknown = insights_with(tables, league_table, average)
    assert not any(i.text.startswith(press) for i in unknown.ideas)
    # La mayoría de sus pérdidas son sin robo (pasos, fuera...): presionar no las provoca.
    few = insights_with(tables, league_table, average, turnovers=(40.0, 57.0))
    assert not any(i.text.startswith(press) for i in few.ideas)
    assert "El 40 % de sus pérdidas son con robo (liga 57 %)" in few.weaknesses[0].text
    many = insights_with(tables, league_table, average, turnovers=(65.0, 57.0))
    assert any(i.text.startswith(press) for i in many.ideas)


def test_three_point_style_needs_a_clear_margin(tables):
    # El 50 % de los tiros del Leioa son triples (38 de 76) y el 46,8 % de los de la "liga"
    # (66 de 141): 3,2 puntos más, por debajo del margen de 8.
    league_table, average = synthetic_league(1, **{"LEIOA SBT": {}, "EASO BASKET": {}})
    result = insights_with(tables, league_table, average)
    assert not any(i.text.startswith("Vive del triple") for i in result.style)


def test_three_point_style(tables):
    team = "LEIOA SBT"
    shots = tables["shots"]
    # Una liga que casi no tira triples: 100 tiros de 2 más.
    twos = pd.DataFrame({"value": [2] * 100, "made": [True] * 100, "zone": ["Cerca del aro"] * 100})
    league_shots = pd.concat([shots[shots["team"] == team], twos])
    season = player_season(tables["players"], team).join(
        player_usage(tables["players"], tables["teams"], team)
    )
    league_table, average = synthetic_league(1, **{team: {}, "EASO BASKET": {}})
    result = insights.team_insights(
        team, league_table, average, season, shots[shots["team"] == team], league_shots
    )
    style = next(i for i in result.style if i.text.startswith("Vive del triple"))
    assert style.text.startswith("Vive del triple: el 50 % de sus tiros de campo")
    assert style.confidence == "alta"
    # Acierta 11 de 38 (28,9 %), igual que la "liga" (sus mismos triples): defender el triple.
    assert any(i.text.startswith("Defender la línea de triple") for i in result.ideas)


def season_row(**values) -> dict:
    row = {"PJ": 10, "MIN": 250, "MIN/PJ": 25, "PTS/PJ": 10, "PTS": 100, "USO%": 18,
           "TS%": 50, "TCA": 80, "T1A": 20, "T3M": 10, "T3A": 30, "T3%": 33.3}  # fmt: skip
    return {**row, **values}


BASELINE = insights.ShootingBaseline(ts=0.49, three=0.27, k_ts=50, k_three=100)


def test_player_rules():
    season = pd.DataFrame(
        {
            "STAR": season_row(**{"USO%": 30, "TS%": 55}),
            # 60/120 en triples: encogido (60 + 27) / 220 = 39,5 %, 12,5 puntos sobre la liga.
            "SHOOTER": season_row(**{"T3M": 60, "T3A": 120, "T3%": 50, "MIN": 400}),
            # 8/15 en triples (53,3 %): encogido (8 + 27) / 115 = 30,4 %, menos de 4 puntos
            # sobre la liga. Con tan pocos tiros, no se destaca.
            "LUCKY": season_row(**{"T3M": 8, "T3A": 15, "T3%": 53.3, "MIN": 400}),
            # 70 puntos en 88,8 tiros: TS% 39,4 %, encogido 42,9 %.
            "WASTEFUL": season_row(**{"USO%": 26, "TS%": 39.4, "PTS": 70}),
            # Mucho uso pero solo 10 minutos en total: no se destaca.
            "CAMEO": season_row(**{"MIN": 10, "MIN/PJ": 10, "USO%": 45, "TS%": 80}),
        }
    ).T.apply(pd.to_numeric)
    texts, ideas = insights._player_insights(season, BASELINE)
    joined = " ".join(i.text for i in texts)
    assert texts[0].text.startswith("Star es su referencia en ataque")
    assert texts[0].confidence == "alta"
    assert "Shooter es peligroso desde el triple: 60/120 (50 %; liga 27 %)" in joined
    assert "Lucky es peligroso" not in joined
    assert "Wasteful tira mucho con poco acierto" in joined
    assert "Cameo" not in joined
    assert "No dejar tirar solo a Shooter desde fuera." in [i.text for i in ideas]


def test_shooting_baseline(tables):
    baseline = insights.shooting_baseline(tables["players"])
    assert 0.4 < baseline.ts < 0.6
    assert baseline.three == pytest.approx(18 / 66)
    # Con solo dos equipos no hay jugadores suficientes para estimar K.
    assert baseline.k_three == insights.DEFAULT_K["T3%"]


def test_pick_ideas_avoids_conflicts_and_limits():
    ideas = [
        insights.Insight("Presionar", "media", 1.6, "presion"),
        insights.Insight("Evitar faltas", "alta", 2.5, "faltas"),
        *(insights.Insight(f"Idea {i}", "alta", 2.0) for i in range(6)),
    ]
    chosen = insights.pick_ideas(ideas)
    texts = [i.text for i in chosen]
    assert texts[0] == "Evitar faltas"
    assert "Presionar" not in texts
    assert len(chosen) == insights.MAX_IDEAS


def test_match_insights(tables):
    games = team_games(tables["teams"])
    own_game = games[games["team"] == "LEIOA SBT"]
    diffs = [3, 5, -1, 13, 6]
    keys = insights.match_insights(own_game, diffs, "LEIOA SBT", "EASO BASKET")
    assert keys[0].startswith("Leioa SBT fue claramente mejor en el cuidado del balón")
    assert keys[-1] == "Máxima ventaja de Leioa SBT: +13. Máxima desventaja: -1."


def describe(label: str) -> str | None:
    """Las mismas reglas que glossary.js para encontrar la definición de un término."""
    if label in TERMS:
        return TERMS[label]
    for suffix in ("/PJ", "/40"):
        if label.endswith(suffix) and label.removesuffix(suffix) in TERMS:
            return TERMS[label.removesuffix(suffix)]
    if label.endswith(" rival"):
        return describe(label.removesuffix(" rival"))
    return None


def test_every_column_has_a_definition(tables):
    zone_columns = list(zone_summary(tables["shots"]).columns)
    columns = (
        build.TEAM_COLUMNS + build.PLAYER_COLUMNS + build.BOX_COLUMNS + build.SCOUTING_COLUMNS
        + build.LEAGUE_COLUMNS + build.FACTOR_ROWS + zone_columns + league.COMPARISON_COLUMNS
        + QUARTER_COLUMNS
        + ["MIN", "PTS", "PTS rival", "+/-", "POSS", "ORtg", "DRtg", "NETO",
           "NETO en pista", "NETO en banquillo", "DIFERENCIA", "POSS en pista",
           "POSS en banquillo"]
    )  # fmt: skip
    missing = sorted({c for c in columns if describe(c) is None})
    assert missing == []
