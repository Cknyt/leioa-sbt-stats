"""Descarga de los partidos del Leioa SBT publicados en basketbasko.com.

Uso:
    uv run python -m leioa_stats.download

Pasos:
1. Lee la clave de la API en el HTML de la página del grupo.
2. Pide la lista de partidos de cada jornada cuya fecha ya ha pasado.
3. Se queda con los partidos ya jugados del equipo.
4. Descarga las estadísticas y el jugada a jugada de cada partido en
   data/raw/matches/<idPartido>/. Si ya están descargados, no los vuelve a pedir.
"""

import base64
import json
import re
import time
from datetime import date
from pathlib import Path

import httpx

GROUP_ID = 2876
TEAM_NAME = "LEIOA SBT"

GROUP_PAGE_URL = "https://basketbasko.com/es/group/?id={group_id}"
ROUND_URL = "https://esb.optimalwayconsulting.com/esf/1/{key}/FCBQWeb/resultats/{group_id}/{round}"
MATCH_URLS = {
    "stats": "https://msstats.optimalwayconsulting.com/v1/esf/getJsonWithMatchStats/{uid}?currentSeason=true",
    "moves": "https://msstats.optimalwayconsulting.com/v1/esf/getJsonWithMatchMoves/{uid}?currentSeason=true",
}

RAW_DIR = Path("data/raw")
# Pausa entre peticiones para no cargar el servidor de la federación.
PAUSE_SECONDS = 1.5
# Las cabeceras HTTP solo admiten ASCII: sin tildes.
USER_AGENT = "leioa-sbt-stats (analisis estadistico del Leioa SBT)"

KEY_PATTERN = re.compile(r"esb\.optimalwayconsulting\.com/esf/1/([0-9A-Za-z]+)")


def extract_api_key(html: str) -> str:
    """Busca la clave de la API en el HTML de una página de basketbasko.com."""
    # La configuración va en JSON dentro de un <script> y a veces escapa las barras.
    match = KEY_PATTERN.search(html.replace("\\/", "/"))
    if match is None:
        raise ValueError("No se ha encontrado la clave de la API en la página")
    return match.group(1)


def decode_response(text: str) -> dict:
    """Descodifica una respuesta de la API de la federación (JSON en base64)."""
    data = json.loads(base64.b64decode(text))
    if data.get("result") != "OK":
        raise ValueError(f"La API ha devuelto un error: {data.get('message')!r}")
    return data["messageData"]


def rounds_until(rounds: dict, today: date) -> list[int]:
    """Jornadas cuya fecha es anterior o igual a hoy."""
    return sorted(
        int(number)
        for number, round_ in rounds.items()
        if date.fromisoformat(round_["date"]) <= today
    )


def played_team_matches(rounds: dict, team_name: str) -> list[dict]:
    """Partidos ya jugados del equipo, con lo necesario para descargarlos."""
    matches = []
    for number, round_ in rounds.items():
        for match in (round_.get("matches") or {}).values():
            if team_name not in (match["nameLocalTeam"], match["nameVisitorTeam"]):
                continue
            # state "1" = partido jugado. Sin universallyid no hay estadísticas publicadas.
            if match["state"] != "1" or not match["universallyid"]:
                continue
            matches.append(
                {
                    "id": match["idMatch"],
                    "uid": match["universallyid"],
                    "round": int(number),
                    "datetime": match["matchDay"],
                    "local": match["nameLocalTeam"],
                    "visitor": match["nameVisitorTeam"],
                    "local_score": int(match["localScore"]),
                    "visitor_score": int(match["visitorScore"]),
                }
            )
    return sorted(matches, key=lambda m: m["round"])


def is_downloaded(match_dir: Path) -> bool:
    return all((match_dir / f"{name}.json").exists() for name in MATCH_URLS)


class Downloader:
    """Cliente HTTP que deja una pausa entre peticiones."""

    def __init__(self, pause: float = PAUSE_SECONDS):
        self.client = httpx.Client(
            headers={"User-Agent": USER_AGENT}, timeout=30, follow_redirects=True
        )
        self.pause = pause
        self.last_request = 0.0

    def get(self, url: str) -> str:
        wait = self.last_request + self.pause - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        response = self.client.get(url)
        self.last_request = time.monotonic()
        response.raise_for_status()
        return response.text


def fetch_team_matches(downloader: Downloader, group_id: int, team_name: str) -> list[dict]:
    """Recorre las jornadas ya disputadas y devuelve los partidos jugados del equipo."""
    key = extract_api_key(downloader.get(GROUP_PAGE_URL.format(group_id=group_id)))

    def fetch_round(number: int) -> dict:
        url = ROUND_URL.format(key=key, group_id=group_id, round=number)
        return decode_response(downloader.get(url))["rounds"]

    # La respuesta de cualquier jornada trae el calendario completo (fechas de las 26).
    calendar = fetch_round(1)
    found = {}
    for number in rounds_until(calendar, date.today()):
        rounds = calendar if number == 1 else fetch_round(number)
        # Cada respuesta trae los partidos de la jornada pedida y a veces los de la siguiente;
        # nos quedamos solo con los de la pedida.
        for match in played_team_matches({str(number): rounds[str(number)]}, team_name):
            found[match["id"]] = match
    return sorted(found.values(), key=lambda m: m["round"])


def download_match(downloader: Downloader, match: dict, raw_dir: Path) -> bool:
    """Descarga los JSON de un partido. Devuelve False si ya estaban descargados."""
    match_dir = raw_dir / "matches" / match["id"]
    if is_downloaded(match_dir):
        return False
    match_dir.mkdir(parents=True, exist_ok=True)
    for name, url in MATCH_URLS.items():
        text = downloader.get(url.format(uid=match["uid"]))
        json.loads(text)  # comprueba que es JSON válido antes de guardarlo
        (match_dir / f"{name}.json").write_text(text, encoding="utf-8")
    return True


def main() -> None:
    downloader = Downloader()
    matches = fetch_team_matches(downloader, GROUP_ID, TEAM_NAME)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / "matches.json").write_text(
        json.dumps(matches, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"{len(matches)} partidos jugados de {TEAM_NAME}:")
    for match in matches:
        new = download_match(downloader, match, RAW_DIR)
        status = "descargado" if new else "ya estaba"
        print(
            f"  J{match['round']:>2} {match['local']} {match['local_score']}-"
            f"{match['visitor_score']} {match['visitor']} ({status})"
        )


if __name__ == "__main__":
    main()
