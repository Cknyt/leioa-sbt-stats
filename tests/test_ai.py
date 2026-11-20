from pathlib import Path

import pandas as pd

from leioa_stats import ai_report, parse, validate
from leioa_stats.metrics import similarity
from leioa_stats.metrics.advanced import player_usage
from leioa_stats.metrics.insights import Insight
from leioa_stats.metrics.shots import add_zones

FIXTURES = Path(__file__).parent / "fixtures"
MATCH_99138 = {"id": "99138", "round": 1, "local": "LEIOA SBT", "visitor": "EASO BASKET"}

PREVIEW = {
    "rival": "Easo Basket",
    "forecast": {"own": 76, "rival": 74, "probability": 56, "margin": "+1,7"},
    "keys": [{"text": "Hacer daño con el tiro: esperable 52,7.", "confidence": "alta"}],
    "attack": [],
    "defense": [],
    "stop": [Insight("Ibai Milla es su referencia en ataque: 26,8 % de uso.", "media")],
    "fouls": [],
    "ideas": [Insight("Cerrar el rebote defensivo.", "media")],
    "missed_last": [],
}
PLAYERS = ["Ibai Milla", "Otro Jugador"]


def test_payload_keeps_confidence():
    lines = ai_report.payload_lines(PREVIEW)
    assert lines[0].startswith("Pronóstico orientativo: 76-74")
    assert "Clave (confianza alta): Hacer daño con el tiro" in lines[1]
    assert any(line.startswith("Jugador rival (confianza media)") for line in lines)


def test_verify_catches_invented_numbers_and_players():
    lines = ai_report.payload_lines(PREVIEW)
    good = "Ibai Milla concentra el 26,8 % del uso; se espera un eFG% de 52,7."
    assert ai_report.verify(good, lines, PLAYERS) == []
    bad = "Otro Jugador anota 18 puntos por partido y el tiro llega al 52.7."
    problems = ai_report.verify(bad, lines, PLAYERS)
    assert "número 18" in problems
    assert "jugador Otro Jugador" in problems
    # 52.7 con punto es el mismo número que 52,7.
    assert "número 52,7" not in problems


def test_report_is_off_by_default(monkeypatch):
    monkeypatch.delenv("INFORME_IA", raising=False)
    assert ai_report.report_for(PREVIEW, "Leioa SBT", "easo-basket", PLAYERS) is None


def test_report_is_discarded_if_it_invents(monkeypatch, tmp_path):
    monkeypatch.setenv("INFORME_IA", "1")
    monkeypatch.setenv("GITHUB_TOKEN", "token-de-prueba")
    monkeypatch.setattr(ai_report, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(ai_report, "ask_model", lambda *a: "Ganaremos de 15 puntos.")
    assert ai_report.report_for(PREVIEW, "Leioa SBT", "easo-basket", PLAYERS) is None
    assert not list(tmp_path.iterdir())


def test_report_is_kept_and_cached(monkeypatch, tmp_path):
    monkeypatch.setenv("INFORME_IA", "1")
    monkeypatch.setenv("GITHUB_TOKEN", "token-de-prueba")
    monkeypatch.setattr(ai_report, "CACHE_DIR", tmp_path)
    text = "Partido igualado: 56 % de opciones.\n\nVigilar a Ibai Milla."
    monkeypatch.setattr(ai_report, "ask_model", lambda *a: text)
    paragraphs = ai_report.report_for(PREVIEW, "Leioa SBT", "easo-basket", PLAYERS)
    assert paragraphs == ["Partido igualado: 56 % de opciones.", "Vigilar a Ibai Milla."]

    # Con las mismas frases no se vuelve a pedir: se lee de la caché.
    def fail(*args):
        raise AssertionError("no debería llamar al modelo")

    monkeypatch.setattr(ai_report, "ask_model", fail)
    assert ai_report.report_for(PREVIEW, "Leioa SBT", "easo-basket", PLAYERS) == paragraphs


def test_most_similar_players():
    stats, moves = validate.load_match(FIXTURES / "99138")
    players = pd.DataFrame(parse.player_rows(MATCH_99138, stats))
    teams = pd.DataFrame(parse.team_rows(MATCH_99138, stats))
    shots = add_zones(pd.DataFrame(parse.shot_rows(MATCH_99138, stats, moves)))
    usage = pd.concat({t: player_usage(players, teams, t) for t in teams["team"].unique()})
    # Un partido: bajamos el mínimo de minutos para tener jugadores.
    similarity.MIN_MINUTES, previous = 15, similarity.MIN_MINUTES
    try:
        features = similarity.player_features(players, shots, usage)
    finally:
        similarity.MIN_MINUTES = previous
    assert list(features.columns) == similarity.FEATURES
    easo = list(features.loc["EASO BASKET"].index[:2])
    texts = similarity.most_similar(features, "EASO BASKET", "LEIOA SBT", easo)
    assert len(texts) == 2
    assert all(" → nuestro " in t for t in texts)
