# CLAUDE.md

Instrucciones para Claude Code en este repositorio. El contexto del proyecto está en [README.md](README.md).

## Comunicación

- Habla siempre en español.
- Explica paso a paso y con el porqué todo lo que tenga que hacer el usuario (Git, GitHub, terminal). Está aprendiendo, así que conviene explicar los conceptos nuevos la primera vez que aparezcan.
- Espera a que el usuario confirme cada paso antes de pasar al siguiente.
- Los comandos que tenga que ejecutar el usuario van en bloques de código separados, uno por bloque.

## Flujo de trabajo con Git

- `main` solo recibe cambios a través de Pull Requests. No hagas commits ni push directamente a `main`.
- Cada cambio va en su propia rama, con un nombre descriptivo y un prefijo: `feat/`, `fix/`, `docs/`, `chore/` o `data/`.
- Los mensajes de commit se escriben en español, en imperativo y de forma breve (por ejemplo, "Añade descarga del jugada a jugada").
- Las operaciones de Git y GitHub (crear ramas, commits, push, Pull Requests, merge) las hace el usuario. Claude le explica los comandos salvo que el usuario le pida expresamente que los ejecute.

## Tecnología

- Python 3.13, con el entorno y las dependencias gestionados por `uv`. No uses `pip` directamente.
- Librerías: httpx (descarga), pandas (tablas y cálculos), plotly (gráficos interactivos), Jinja2 (plantillas HTML).
- Calidad: pytest para los tests y ruff para el formato y el lint.
- Los nombres de archivos, funciones y variables van en inglés. Los comentarios, la documentación y los commits van en español.
- El resultado final es una web estática en `site/`, adaptada a móvil y ordenador. Todavía no se ha decidido si se publica en GitHub Pages o en el hosting del usuario.

Comandos habituales:

- `uv sync`: crea o actualiza el entorno.
- `uv add <paquete>`: añade una dependencia (`--dev` si solo se usa para desarrollar).
- `uv run python -m pytest`: ejecuta los tests. En este equipo el antivirus (Bitdefender) bloquea los lanzadores `.exe` que crea uv en `.venv/Scripts` ("Acceso denegado"), así que las herramientas de Python se ejecutan siempre con `python -m <herramienta>`.
- `uv run ruff check .` y `uv run ruff format .`: revisan y formatean el código.

## Estructura

- `src/leioa_stats/`: el código. `download.py` (descarga con caché), `parse.py` (JSON a tablas), `validate.py` (contraste del jugada a jugada con el box score) y `metrics/` (`basic.py`, `advanced.py`, `lineups.py`, `shots.py`).
- `data/raw/` y `data/processed/`: datos descargados y procesados. No se versionan.
- `notebooks/`: exploración con Jupyter.
- `site/`: web generada. No se versiona.
- `tests/`: tests. `tests/fixtures/` guarda el partido de ejemplo 99138.

Crea cada archivo o carpeta cuando haga falta, no antes.

## Antes de escribir código

- Propón la tecnología, las librerías y la estructura de carpetas, y espera la aprobación del usuario antes de implementar.
- Los cambios deben ser pequeños y fáciles de revisar en un Pull Request.

## Datos

- Fuente: datos públicos de basketbasko.com (Federación Vasca), servidos en JSON por los servicios de Optimal Way Consulting.
- Respeta el servidor: guarda en local lo que ya se ha descargado, no repitas descargas innecesarias y deja una pausa entre peticiones.
- No subas al repositorio claves, tokens ni configuración personal; van en `.env`, que está ignorado.

## Fiabilidad de las métricas

Cada métrica que se presente al entrenador debe ir acompañada de su grado de fiabilidad:

- Los datos se anotan a mano en la mesa, así que puede haber errores. Hay que contrastar los totales del jugada a jugada con el box score.
- Los tapones no parecen registrarse. Cualquier métrica que dependa de ellos queda incompleta.
- La muestra es pequeña (26 jornadas): indica el tamaño de muestra y evita sacar conclusiones con pocos minutos o pocos intentos.
- Si una métrica es una estimación (por ejemplo, las posesiones), explica la fórmula usada.
