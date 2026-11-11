"""Tests del diario de visitas: registrar.php (el receptor) e informe.php (el informe).

Se ejecutan con el PHP instalado en el equipo (en GitHub Actions viene de serie). Cada test
carga el archivo PHP, que en modo consola solo define sus funciones, y llama a una de ellas.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

PHP_DIR = Path(__file__).parents[1] / "src" / "leioa_stats" / "web" / "php"
REGISTRAR = PHP_DIR / "registrar.php"
REPORT = PHP_DIR / "informe.php"
NOW = 1_762_700_000  # 9/11/2025, para que el archivo del mes sea conocido.
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Safari/604.1"

pytestmark = pytest.mark.skipif(shutil.which("php") is None, reason="PHP no está instalado")


def run_php(code: str, php_file: Path = REGISTRAR) -> str:
    script = f"require {json.dumps(str(php_file))};\ndate_default_timezone_set('Europe/Madrid');\n"
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


ANDROID = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 Chrome/141.0 Mobile Safari/537.36"
WINDOWS = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/141.0 Safari/537.36"


def report(code: str):
    return json.loads(run_php(f"echo json_encode({code});", REPORT))


@pytest.mark.parametrize(
    ("ua", "expected"),
    [
        (UA, "iPhone · iOS 18 · Safari · 390×844"),
        (ANDROID, "Android 10 · Chrome · 390×844"),
        (WINDOWS, "Ordenador Windows · Chrome · 390×844"),
    ],
)
def test_describe_device(ua, expected):
    assert report(f"describe_device({json.dumps(ua)}, '390x844@3')") == expected


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/leioa/", "Resumen"),
        ("/leioa/index.html#quintetos", "Resumen › Quintetos"),
        ("/leioa/jugadores.html", "Jugadores"),
        ("/leioa/partidos/99138.html", "Partido 99138"),
        ("/leioa/equipos/easo-basket.html", "Equipo easo basket"),
    ],
)
def test_page_label(path, expected):
    assert report(f"page_label({json.dumps(path)})") == expected


def test_visits_group_pages_of_the_same_device():
    def start(view, ts, page, ua=UA):
        return {"ts": ts, "v": view, "t": "start", "p": page, "r": "", "w": "390x844@3", "ua": ua}

    records = [
        start("a", NOW, "/leioa/index.html"),
        {"ts": NOW + 30, "v": "a", "t": "section", "id": "quintetos"},
        {"ts": NOW + 120, "v": "a", "t": "ping", "s": 120},
        # Mismo aparato 5 minutos después: misma visita.
        start("b", NOW + 400, "/leioa/jugadores.html"),
        {"ts": NOW + 460, "v": "b", "t": "ping", "s": 60},
        # Mismo aparato 2 horas después: otra visita.
        start("c", NOW + 7200, "/leioa/index.html"),
        # Otro aparato a la vez: otra visita.
        start("d", NOW + 10, "/leioa/comparativa.html", ua=WINDOWS),
        # Aviso de una página cuyo inicio no llegó: se ignora.
        {"ts": NOW, "v": "zzz", "t": "ping", "s": 999},
    ]
    visits = report(
        f"build_visits(build_views(json_decode({json.dumps(json.dumps(records))}, true)))"
    )
    assert [(v["seconds"], v["pages"]) for v in visits] == [
        (180, ["Resumen (Quintetos)", "Jugadores"]),
        (0, ["Comparativa"]),
        (0, ["Resumen"]),
    ]
    assert visits[0]["device"] == visits[2]["device"] != visits[1]["device"]


def test_duration():
    assert report("[duration(45), duration(150), duration(4000)]") == ["45 s", "2 min", "1 h 6 min"]


# Aviso por Telegram (registrar.php). El envío en sí no se prueba: necesitaría internet y un bot.

START = {
    "ts": NOW,
    "v": "abc123xyz",
    "t": "start",
    "p": "/leioa/index.html#quintetos",
    "r": "",
    "w": "390x844@3",
    "ua": UA,
}


def php_value(code: str):
    return json.loads(run_php(f"echo json_encode({code});"))


def php_json(value) -> str:
    """Valor de Python escrito como expresión de PHP (un array asociativo)."""
    return f"json_decode({json.dumps(json.dumps(value))}, true)"


def test_alert_text_describes_the_visit():
    text = php_value(f"alert_text({php_json(START | {'r': 'web.whatsapp.com'})}, [])")
    assert text.splitlines() == [
        "Nueva visita a la web del Leioa",
        "iPhone · iOS 18 · Safari · 390×844",
        f"Resumen › Quintetos · {time_of(NOW)}",
        "Llega desde web.whatsapp.com",
    ]


def time_of(ts: int) -> str:
    return run_php(f"echo date('H:i', {ts});")


def test_alert_text_uses_the_name_and_skips_my_devices():
    key = php_value(f"device_key({json.dumps(UA)}, '390x844@3')")
    named = php_value(f"alert_text({php_json(START)}, {php_json({key: {'name': 'Mister'}})})")
    assert named.splitlines()[1] == "Mister (iPhone · iOS 18 · Safari · 390×844)"
    mine = php_json({key: {"name": "Yo", "me": True}})
    assert php_value(f"alert_text({php_json(START)}, {mine})") is None


def decide(state: dict, device: str, now: int) -> tuple[bool, dict]:
    alert, new_state = php_value(f"alert_decision({php_json(state)}, '{device}', {now})")
    return alert, new_state


def test_one_alert_per_visit():
    alert, state = decide({}, "aaaaaa", NOW)
    assert alert
    # Otra página 10 minutos después: misma visita, sin aviso.
    alert, state = decide(state, "aaaaaa", NOW + 600)
    assert not alert
    # 25 minutos después de esa página: sigue siendo la misma visita.
    alert, state = decide(state, "aaaaaa", NOW + 600 + 1500)
    assert not alert
    # Más de 30 minutos sin páginas: visita nueva.
    alert, state = decide(state, "aaaaaa", NOW + 600 + 1500 + 1801)
    assert alert
    # Otro aparato a la vez: su propio aviso.
    assert decide(state, "bbbbbb", NOW + 600 + 1500 + 1802)[0]


def test_alerts_per_hour_are_limited():
    state: dict = {}
    alerts = []
    for i in range(12):
        alert, state = decide(state, f"{i:06d}", NOW + i)
        alerts.append(alert)
    assert alerts == [True] * 10 + [False] * 2
    # Una hora después del primero vuelve a haber hueco.
    assert decide(state, "nuevo1", NOW + 3600)[0]


def test_alert_state_is_saved_protected(tmp_path):
    file = json.dumps(str(tmp_path / "telegram.php"))
    change = "fn($s) => alert_decision($s, 'aaaaaa', " + str(NOW) + ")"
    assert php_value(f"update_alert_state({file}, {change})") is True
    assert php_value(f"update_alert_state({file}, {change})") is False
    lines = (tmp_path / "telegram.php").read_text(encoding="utf-8").splitlines()
    assert lines[0] == "<?php http_response_code(404); exit; ?>"
    assert json.loads(lines[1]) == {"devices": {"aaaaaa": NOW}, "sent": [NOW]}


@pytest.mark.parametrize(
    ("configured", "state", "expected"),
    [
        (False, {}, "desactivado"),
        (True, {}, "todavía sin envíos"),
        (True, {"last": {"ts": NOW, "result": "ok"}}, "último envío correcto"),
        (
            True,
            {"last": {"ts": NOW, "result": "error 400 chat not found"}},
            "(error 400 chat not found)",
        ),
    ],
)
def test_telegram_status(configured, state, expected):
    flag = "true" if configured else "false"
    assert expected in report(f"telegram_status({flag}, {php_json(state)})")


def test_send_errors_never_show_the_token():
    # Sin conexión (o sin HTTPS en el PHP local), el error de PHP repite la dirección con el token.
    result = run_php("echo send_telegram('123:secreto', '42', 'hola');")
    assert result.startswith("error")
    assert "secreto" not in result
