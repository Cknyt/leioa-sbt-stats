"""Resumen de la previa redactado por un modelo de lenguaje (GitHub Models, gratuito).

Cómo funciona:
1. La previa ya tiene sus conclusiones calculadas con reglas (metrics/preview.py). Solo esas
   frases, con sus números y su confianza, se mandan al modelo: no ve las tablas ni el
   jugada a jugada, así que no puede sacar conclusiones nuevas.
2. El modelo las ordena y las redacta en dos o tres párrafos para el cuerpo técnico.
3. Comprobación automática antes de publicar (verify): cada número del texto tiene que estar
   en las frases de partida, y cada jugador de la liga que nombre también. Si falla, no se
   publica el texto y la previa sale solo con las frases de las reglas.

Coste: GitHub Models es gratuito con la cuenta de GitHub, con un límite de peticiones al día
(unas 150 para los modelos pequeños). Se hace una petición por publicación, solo para el
próximo rival, y la respuesta se guarda en data/processed/ia/: si las frases no cambian, no
se vuelve a pedir.

Se activa en la publicación (GitHub Actions) con INFORME_IA=1 y el GITHUB_TOKEN del propio
workflow, que necesita el permiso "models: read". En local queda desactivado salvo que se
definan esas dos variables.

Dónde puede equivocarse el modelo: inventar causas que no están en los datos ("defienden en
zona"), confundir lo que hace un equipo con lo que permite, o presentar como seguro algo de
confianza media. Las instrucciones lo prohíben y la comprobación de números y nombres caza
los inventos más graves, pero no los matices: por eso la web avisa de que mandan las tablas.
"""

import hashlib
import json
import os
import re
from pathlib import Path

import httpx

ENDPOINT = "https://models.github.ai/inference/chat/completions"
MODEL = "openai/gpt-4.1-mini"
CACHE_DIR = Path("data/processed/ia")
TIMEOUT = 60

INSTRUCTIONS = """Eres analista de un cuerpo técnico de baloncesto amateur. Redacta en español,
en dos o tres párrafos cortos y sin listas, un resumen de la previa del próximo partido de
{own} contra {rival} para el entrenador.
Reglas estrictas:
- Usa solo la información de las frases que te doy. No añadas datos, causas, tácticas ni
  jugadores que no aparezcan en ellas.
- Copia los números tal cual (con coma decimal). No calcules números nuevos.
- Respeta la confianza: lo de confianza "media" preséntalo como indicio, no como hecho.
- Si una frase dice que algo no está claro, no lo conviertas en conclusión.
- Empieza por lo más importante para preparar el partido."""

NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def enabled() -> bool:
    return os.environ.get("INFORME_IA") == "1" and bool(os.environ.get("GITHUB_TOKEN"))


def payload_lines(preview: dict) -> list[str]:
    """Frases de la previa que se mandan al modelo, con su confianza."""
    lines = []
    if preview.get("forecast"):
        f = preview["forecast"]
        lines.append(
            f"Pronóstico orientativo: {f['own']}-{f['rival']}, probabilidad de victoria "
            f"{f['probability']} %, margen esperado {f['margin']}."
        )
    for title, items in (
        ("Clave", preview.get("keys", [])),
        ("Ataque", preview.get("attack", [])),
        ("Defensa", preview.get("defense", [])),
    ):
        for item in items:
            lines.append(f"{title} (confianza {item['confidence']}): {item['text']}")
    for item in preview.get("stop", []):
        lines.append(f"Jugador rival (confianza {item.confidence}): {item.text}")
    lines += [f"Faltas: {text}" for text in preview.get("fouls", [])]
    for item in preview.get("ideas", []):
        lines.append(f"Idea (confianza {item.confidence}): {item.text}")
    if preview.get("missed_last"):
        lines.append(f"No estuvieron en su último partido: {', '.join(preview['missed_last'])}.")
    return lines


def _numbers(text: str) -> set[str]:
    return {n.replace(".", ",") for n in NUMBER.findall(text)}


def verify(report: str, lines: list[str], league_players: list[str]) -> list[str]:
    """Problemas del texto: números o jugadores que no están en las frases de partida."""
    source = "\n".join(lines)
    problems = [f"número {n}" for n in sorted(_numbers(report) - _numbers(source))]
    source_lower, report_lower = source.lower(), report.lower()
    for player in league_players:
        name = player.lower()
        if name in report_lower and name not in source_lower:
            problems.append(f"jugador {player}")
    return problems


def _cache_path(lines: list[str], rival: str) -> Path:
    digest = hashlib.sha256((MODEL + "\n" + "\n".join(lines)).encode()).hexdigest()[:16]
    return CACHE_DIR / f"{rival}-{digest}.json"


def ask_model(lines: list[str], own: str, rival: str, token: str) -> str:
    response = httpx.post(
        ENDPOINT,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={
            "model": MODEL,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": INSTRUCTIONS.format(own=own, rival=rival)},
                {"role": "user", "content": "\n".join(lines)},
            ],
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def report_for(preview: dict, own: str, rival_slug: str, league_players: list[str]):
    """Párrafos verificados del resumen, o None si está desactivado o no pasa la comprobación.

    Los nombres de jugadores se comparan en el formato de la web (display_name).
    """
    if not enabled():
        return None
    lines = payload_lines(preview)
    if not lines:
        return None
    cache = _cache_path(lines, rival_slug)
    if cache.exists():
        text = json.loads(cache.read_text(encoding="utf-8"))["text"]
    else:
        try:
            text = ask_model(lines, own, preview["rival"], os.environ["GITHUB_TOKEN"])
        except (httpx.HTTPError, KeyError, ValueError) as error:
            print(f"Resumen redactado no disponible: {error}")
            return None
    problems = verify(text, lines, league_players)
    if problems:
        print(f"Resumen redactado descartado: no está en los datos ({', '.join(problems)})")
        return None
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"text": text}, ensure_ascii=False), encoding="utf-8")
    return [p.strip() for p in text.split("\n") if p.strip()]
