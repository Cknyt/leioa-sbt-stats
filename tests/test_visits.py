"""Tests de registrar.php, el receptor del diario de visitas.

Se ejecutan con el PHP instalado en el equipo (en GitHub Actions viene de serie). Cada test
carga registrar.php, que en modo consola solo define sus funciones, y llama a una de ellas.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REGISTRAR = Path(__file__).parents[1] / "src" / "leioa_stats" / "web" / "php" / "registrar.php"
NOW = 1_762_700_000  # 9/11/2025, para que el archivo del mes sea conocido.
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Safari/604.1"

pytestmark = pytest.mark.skipif(shutil.which("php") is None, reason="PHP no está instalado")


def run_php(code: str) -> str:
    script = f"require {json.dumps(str(REGISTRAR))};\ndate_default_timezone_set('Europe/Madrid');\n"
    result = subprocess.run(
        ["php", "-r", script + code], capture_output=True, text=True, check=True
    )
    return result.stdout


def build_record(data: dict) -> dict | None:
    code = (
        f"$data = json_decode({json.dumps(json.dumps(data))}, true);\n"
        f"echo json_encode(build_record($data, {json.dumps(UA)}, {NOW}));"
    )
    return json.loads(run_php(code))


def test_start_keeps_page_screen_and_device():
    record = build_record(
        {
            "v": "abc123xyz",
            "t": "start",
            "p": "/leioa/index.html#quintetos",
            "r": "",
            "w": "390x844@3",
        }
    )
    assert record == {
        "ts": NOW,
        "v": "abc123xyz",
        "t": "start",
        "p": "/leioa/index.html#quintetos",
        "r": "",
        "w": "390x844@3",
        "ua": UA,
    }


def test_ping_and_section():
    assert build_record({"v": "abc123xyz", "t": "ping", "s": 90})["s"] == 90
    assert build_record({"v": "abc123xyz", "t": "section", "id": "cuartos"})["id"] == "cuartos"


@pytest.mark.parametrize(
    "data",
    [
        {"v": "abc123xyz", "t": "otro"},  # tipo desconocido
        {"v": "AB!", "t": "ping", "s": 5},  # código de página raro
        {"v": "abc123xyz", "t": "ping", "s": -1},  # tiempo negativo
        {"v": "abc123xyz", "t": "ping", "s": "90"},  # tiempo que no es un número
        {"v": "abc123xyz", "t": "section", "id": "<script>"},
        {"v": "abc123xyz", "t": "start", "p": "<?php", "r": "", "w": "390x844@3"},
        {"v": "abc123xyz", "t": "start", "p": "/index.html", "r": "", "w": "grande"},
    ],
)
def test_rejects_invalid_notices(data):
    assert build_record(data) is None


def test_append_record_protects_the_data_file(tmp_path):
    folder = tmp_path / "datos"
    record = {"ts": NOW, "v": "abc123xyz", "t": "section", "id": "liga"}
    record_json = json.dumps(json.dumps(record))
    code = f"append_record({json.dumps(str(folder))}, json_decode({record_json}, true));"
    run_php(code)
    run_php(code)
    lines = (folder / "visitas-2025-11.php").read_text(encoding="utf-8").splitlines()
    # Primera línea: el "exit" que impide leer el archivo desde internet. Luego, un aviso por línea.
    assert lines[0] == "<?php http_response_code(404); exit; ?>"
    assert [json.loads(line) for line in lines[1:]] == [record, record]
    assert "Require all denied" in (folder / ".htaccess").read_text(encoding="utf-8")
