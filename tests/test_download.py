import base64
import json
from datetime import date
from pathlib import Path

import pytest

from leioa_stats import download

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def round_2_response() -> dict:
    # Respuesta real de la jornada 2 (ya descodificada): trae las jornadas 2 y 3.
    return json.loads((FIXTURES / "round_2.json").read_text(encoding="utf-8"))


def test_extract_api_key():
    html = '<script>var owbasket = {"esb":{"url":"https://esb.optimalwayconsulting.com/esf/1/AbC123"}};'
    assert download.extract_api_key(html) == "AbC123"


def test_extract_api_key_with_escaped_slashes():
    html = r'{"url":"https:\/\/esb.optimalwayconsulting.com\/esf\/1\/AbC123"}'
    assert download.extract_api_key(html) == "AbC123"


def test_extract_api_key_missing():
    with pytest.raises(ValueError):
        download.extract_api_key("<html></html>")


def test_decode_response(round_2_response):
    encoded = base64.b64encode(json.dumps(round_2_response).encode()).decode()
    assert download.decode_response(encoded) == round_2_response["messageData"]


def test_decode_response_error():
    encoded = base64.b64encode(b'{"result": "KO", "message": "fallo"}').decode()
    with pytest.raises(ValueError):
        download.decode_response(encoded)


def test_rounds_until(round_2_response):
    rounds = round_2_response["messageData"]["rounds"]
    assert download.rounds_until(rounds, date(2026, 10, 18)) == [1, 2]


def test_played_team_matches_skips_unplayed(round_2_response):
    rounds = round_2_response["messageData"]["rounds"]
    matches = download.played_team_matches(rounds, "LEIOA SBT")
    # La jornada 3 (Leioa SBT - CB Santurtzi SK) aún no se ha jugado.
    assert matches == [
        {
            "id": "99148",
            "uid": "6ad3b4d58f5cbfd747a66f4a",
            "round": 2,
            "datetime": "2026-10-17 18:00:00",
            "local": "ELABORADOS NATURALES VALLE DE EGÜÉS",
            "visitor": "LEIOA SBT",
            "local_score": 82,
            "visitor_score": 79,
        }
    ]


class FakeDownloader:
    def __init__(self):
        self.urls = []

    def get(self, url: str) -> str:
        self.urls.append(url)
        return "{}"


def test_download_match_uses_cache(tmp_path):
    match = {"id": "99148", "uid": "abc"}
    downloader = FakeDownloader()

    assert download.download_match(downloader, match, tmp_path) is True
    assert (tmp_path / "matches" / "99148" / "stats.json").exists()
    assert (tmp_path / "matches" / "99148" / "moves.json").exists()
    assert len(downloader.urls) == 2

    # La segunda vez no pide nada: el partido ya está descargado.
    assert download.download_match(downloader, match, tmp_path) is False
    assert len(downloader.urls) == 2
