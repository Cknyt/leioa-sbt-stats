"""Bloque de profundidad: ajuste por rival y pista, forma, pronóstico, parejas, basura,
finales apretados, tiempos muertos, historial y prueba retrospectiva."""

import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from leioa_stats import backtest, history, parse, validate
from leioa_stats.metrics import adjusted, clutch, insights, lineups

FIXTURES = Path(__file__).parent / "fixtures"
MATCH_99138 = {"id": "99138", "round": 1, "local": "LEIOA SBT", "visitor": "EASO BASKET"}


def game(match_id, round_, home, away, home_pts, away_pts, poss=80):
    """Dos filas de equipo (formato parse.team_rows) con posesiones exactas: TCA = poss."""
    base = {"T1M": 0, "T1A": 0, "T2M": 0, "T3M": 0, "T3A": 0, "RO": 0, "RD": 30, "AS": 0,
            "PER": 0, "REC": 0, "TAP": 0, "FP": 0, "FR": 0, "VAL": 0,
            "game_minutes": 40}  # fmt: skip
    return [
        {**base, "match_id": match_id, "round": round_, "team": home, "opponent": away,
         "home": True, "PTS": home_pts, "T2A": poss},
        {**base, "match_id": match_id, "round": round_, "team": away, "opponent": home,
         "home": False, "PTS": away_pts, "T2A": poss},
    ]  # fmt: skip


def league_of(games: list[list[dict]]) -> pd.DataFrame:
    return pd.DataFrame([row for g in games for row in g])


def test_adjustment_rewards_a_hard_schedule():
    # A gana a C por 20 y a B (que ganó a C por 40) por 4. B solo jugó contra C.
    # Ajustado por rival, el +4 contra un equipo fuerte vale más de lo que parece.
    teams = league_of([
        game("1", 1, "A", "C", 90, 70), game("2", 2, "B", "C", 100, 60),
        game("3", 3, "B", "A", 82, 78), game("4", 4, "C", "A", 70, 90),
    ])  # fmt: skip
    ratings = adjusted.adjusted_ratings(teams)
    assert ratings["NETO aj."].sum() == pytest.approx(0, abs=0.5)
    assert (
        ratings.loc["B", "NETO aj."] > ratings.loc["A", "NETO aj."] > ratings.loc["C", "NETO aj."]
    )


def test_home_advantage_is_shrunk():
    # Un solo partido con +20 del local: la ventaja se queda cerca de los 3 puntos de partida.
    teams = league_of([game("1", 1, "A", "B", 90, 70)])
    h = adjusted.home_advantage(teams)
    assert h == pytest.approx((25 + 30 * 3) / 31)


def test_forecast_is_symmetric():
    teams = league_of([game("1", 1, "A", "B", 80, 80), game("2", 2, "B", "A", 80, 80)])
    paces = pd.Series({"A": 80.0, "B": 80.0})
    result = adjusted.forecast(teams, paces, "A", "B")
    # Equipos iguales: solo cuenta la ventaja de jugar en casa.
    assert result.home_win > 0.5
    assert result.sd >= adjusted.MIN_MARGIN_SD
    flipped = adjusted.forecast(teams, paces, "B", "A")
    assert result.home_win == pytest.approx(flipped.home_win)


def test_recent_form_needs_enough_games():
    teams = league_of(
        [game(str(i), i, "A", "B", 80 + (20 if i > 3 else 0), 80) for i in range(1, 7)]
    )
    form = adjusted.recent_form(teams, spread_net=10)
    # Neto +25 en los 3 últimos frente a 0 antes: z = 25 / (10 × √(2/3)) = 3,1.
    assert form.loc["A", "Forma"] == "↑"
    assert form.loc["B", "Forma"] == "↓"
    short = adjusted.recent_form(teams[teams["round"] <= 4], spread_net=10)
    assert short.loc["A", "Forma"] == ""


@pytest.fixture
def match_99138():
    return validate.load_match(FIXTURES / "99138")


def test_pairs_and_trios(match_99138):
    stats, moves = match_99138
    stints = pd.DataFrame(lineups.stint_rows(MATCH_99138, stats, moves, "LEIOA SBT"))
    pairs = lineups.combination_summary(stints, 2)
    trios = lineups.combination_summary(stints, 3)
    # Cada minuto en pista hay 10 parejas y 10 tríos distintos.
    assert pairs["seconds"].sum() == 10 * 40 * 60
    assert trios["seconds"].sum() == 10 * 40 * 60
    assert not stints["garbage"].any()  # el 99138 se decidió por 6


def test_best_first_sorts_by_plus_minus_then_minutes():
    summary = pd.DataFrame(
        {
            "NETO": [-12.7, float("nan"), float("nan"), 2.3],
            "+/-": [-13, 14, 3, 3],
            "seconds": [2800, 2600, 300, 3600],
        },
        index=["-13 con neto", "+14 sin neto", "+3 y pocos min", "+3 y más min"],
    )
    # Un solo criterio para todas las filas, tengan neto o no. A igualdad, más minutos.
    assert list(lineups.best_first(summary).index) == [
        "+14 sin neto",
        "+3 y más min",
        "+3 y pocos min",
        "-13 con neto",
    ]


def test_garbage_time_is_left_out():
    stints = pd.DataFrame(
        [
            {"lineup": "A | B", "size": 5, "garbage": False, "match_id": "1", "seconds": 600,
             "PTS": 20, "TCA": 20, "T1A": 0, "RO": 0, "PER": 0, "PTS_opp": 10, "TCA_opp": 20,
             "T1A_opp": 0, "RO_opp": 0, "PER_opp": 0},
            {"lineup": "C | D", "size": 5, "garbage": True, "match_id": "1", "seconds": 300,
             "PTS": 2, "TCA": 10, "T1A": 0, "RO": 0, "PER": 0, "PTS_opp": 20, "TCA_opp": 10,
             "T1A_opp": 0, "RO_opp": 0, "PER_opp": 0},
        ]
    )  # fmt: skip
    assert list(lineups.lineup_summary(stints).index) == ["A | B"]
    assert lineups.garbage_minutes(stints) == 5
    # El +/- sí cuenta todo, como el de la federación.
    on_off = lineups.player_on_off(stints)
    assert on_off.loc["C", "+/-"] == -18


def test_clutch_and_timeouts(match_99138):
    stats, moves = match_99138
    players, games = clutch.clutch_rows(MATCH_99138, stats, moves)
    rows = pd.DataFrame(players)
    # 76-70 al final: hubo final apretado y el Leioa lo ganó.
    assert clutch.clutch_record(pd.DataFrame(games), "LEIOA SBT") == (1, 0)
    assert clutch.clutch_summary(rows, "LEIOA SBT")["TCA"].sum() > 0
    timeouts = pd.DataFrame(clutch.timeout_rows(MATCH_99138, stats, moves))
    assert len(timeouts) == sum(m["idMove"] == validate.TIMEOUT for m in moves)
    teams = pd.DataFrame(parse.team_rows(MATCH_99138, stats))
    summary = clutch.timeout_summary(timeouts, teams, "LEIOA SBT")
    assert summary.loc["Equipo", "PTS por minuto (temporada)"] == round(76 / 40, 2)


def test_history_priors(tmp_path):
    raw = tmp_path / "history" / "1234"
    shutil.copytree(FIXTURES / "99138", raw / "matches" / "99138")
    (raw / "matches.json").write_text(json.dumps([MATCH_99138]), encoding="utf-8")
    past = history.past_players(tmp_path / "history")
    assert past["player_id"].notna().all()
    shooting = history.shooting_history(past)
    stats, _ = validate.load_match(FIXTURES / "99138")
    players = pd.DataFrame(parse.player_rows(MATCH_99138, stats))
    baseline = insights.shooting_baseline(players, shooting)
    # Los mismos jugadores "la temporada pasada": cada uno parte de su propio historial.
    shooter = players.loc[players["T3A"].idxmax(), "player"]
    assert shooter in baseline.three_priors
    assert baseline.three_for("NADIE") == baseline.three
    assert history.shooting_history(pd.DataFrame()).empty


def test_backtest_runs_on_one_match():
    stats, _ = validate.load_match(FIXTURES / "99138")
    teams = pd.DataFrame(parse.team_rows(MATCH_99138, stats))
    summary = backtest.backtest(teams, cut_round=1)
    # Cortar en la última jornada: todo se mantiene.
    assert (summary["% se mantiene"] == 100).all()
