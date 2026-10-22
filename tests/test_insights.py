from pathlib import Path

import pandas as pd
import pytest

from leioa_stats import parse, validate
from leioa_stats.metrics import insights, league
from leioa_stats.metrics.advanced import player_usage, team_games
from leioa_stats.metrics.basic import player_season
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


def leioa_insights(tables) -> insights.TeamInsights:
    team = "LEIOA SBT"
    season = (
        player_season(tables["players"], team)
        .join(player_usage(tables["players"], tables["teams"], team))
        .join(league.player_profiles(tables["players"], tables["shots"], team).drop(columns="TCA"))
    )
    shots = tables["shots"]
    return insights.team_insights(
        team,
        league.league_table(tables["teams"]),
        league.league_average(tables["teams"]),
        season,
        shots[shots["team"] == team],
        shots,
    )


def test_team_strengths_and_weaknesses(tables):
    result = leioa_insights(tables)
    # 15 pérdidas frente a 26 de Easo; 26,4 % de rebote ofensivo frente a 38,6 %.
    assert any(s.startswith("Cuida mucho el balón: 17,5") for s in result.strengths)
    assert any(s.startswith("Apenas captura rebotes ofensivos") for s in result.weaknesses)
    # Cada frase dice de dónde sale: su puesto y la media de la liga.
    assert all("de 2; media de la liga" in s for s in result.strengths + result.weaknesses
               if not s.startswith(("Muy acertado", "Poco acertado")))  # fmt: skip


def test_three_point_style_needs_a_clear_margin(tables):
    # El 50 % de los tiros del Leioa son triples (38 de 76) y el 46,8 % de los de la "liga"
    # (66 de 141): 3,2 puntos más, por debajo del margen de 8.
    assert not any(s.startswith("Vive del triple") for s in leioa_insights(tables).style)


def test_three_point_style(tables):
    team = "LEIOA SBT"
    shots = tables["shots"]
    # Una liga que casi no tira triples: 100 tiros de 2 más.
    twos = pd.DataFrame({"value": [2] * 100, "made": [True] * 100, "zone": ["Cerca del aro"] * 100})
    league_shots = pd.concat([shots[shots["team"] == team], twos])
    season = player_season(tables["players"], team).join(
        player_usage(tables["players"], tables["teams"], team)
    )
    result = insights.team_insights(
        team,
        league.league_table(tables["teams"]),
        league.league_average(tables["teams"]),
        season,
        shots[shots["team"] == team],
        league_shots,
    )
    assert any(s.startswith("Vive del triple: el 50 % de sus tiros de campo") for s in result.style)


def season_row(**values) -> dict:
    row = {"PJ": 2, "MIN": 50, "MIN/PJ": 25, "PTS/PJ": 10, "USO%": 18, "TS%": 50, "TCA": 15,
           "T1A": 4, "T3M": 2, "T3A": 6, "T3%": 33.3}  # fmt: skip
    return {**row, **values}


def test_player_rules():
    season = pd.DataFrame(
        {
            "STAR": season_row(**{"USO%": 30, "TS%": 55}),
            "SHOOTER": season_row(**{"T3M": 6, "T3A": 12, "T3%": 50}),
            "WASTEFUL": season_row(**{"USO%": 26, "TS%": 40}),
            # Mucho uso pero solo 10 minutos en total: no se destaca.
            "CAMEO": season_row(**{"MIN": 10, "MIN/PJ": 10, "USO%": 45, "TS%": 80}),
        }
    ).T
    texts, ideas = insights._player_insights(season)
    joined = " ".join(texts)
    assert texts[0].startswith("Star es su referencia en ataque")
    assert "Shooter es peligroso desde el triple: 6/12 (50 %)" in joined
    assert "Wasteful tira mucho con poco acierto" in joined
    assert "Cameo" not in joined
    assert "No dejar tirar solo a Shooter desde fuera." in ideas


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
    if label.endswith(" rival") and label.removesuffix(" rival") in TERMS:
        return TERMS[label.removesuffix(" rival")]
    return None


def test_every_column_has_a_definition(tables):
    zone_columns = list(zone_summary(tables["shots"]).columns)
    columns = (
        build.TEAM_COLUMNS + build.PLAYER_COLUMNS + build.BOX_COLUMNS + build.SCOUTING_COLUMNS
        + build.LEAGUE_COLUMNS + build.FACTOR_ROWS + zone_columns
        + ["MIN", "PTS", "PTS rival", "+/-", "POSS", "ORtg", "DRtg", "NETO",
           "NETO en pista", "NETO en banquillo", "DIFERENCIA"]
    )  # fmt: skip
    missing = sorted({c for c in columns if describe(c) is None})
    assert missing == []
