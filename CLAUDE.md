# CLAUDE.md

Instrucciones para Claude Code en este repositorio. El contexto del proyecto está en [README.md](README.md).

## Comunicación

- Habla siempre en español.
- El usuario está aprendiendo: explica con el porqué los conceptos nuevos la primera vez que aparezcan.
- Detente solo para las decisiones del usuario: aprobar un diseño o una fórmula y fusionar un PR. Los pasos rutinarios (tests, ruff, actualizar `main`, borrar ramas) hazlos sin preguntar y resúmelos.
- Propuesta y código van juntos: implementa directamente y explica las decisiones (fórmulas incluidas) en la descripción del PR, para que el usuario las revise allí.
- Si el usuario tiene que ejecutar algún comando, va en un bloque de código propio, uno por bloque.

## Flujo de trabajo con Git

- `main` solo recibe cambios a través de Pull Requests. No hagas commits ni push directamente a `main`.
- Cada cambio va en su propia rama, con un nombre descriptivo y un prefijo: `feat/`, `fix/`, `docs/`, `chore/` o `data/`.
- Los mensajes de commit se escriben en español, en imperativo y de forma breve (por ejemplo, "Añade descarga del jugada a jugada").
- Claude hace las operaciones de Git y GitHub: crear la rama, commit, push y abrir el PR. Después comprueba que el CI está en verde.
- Fusionar es decisión del usuario: lo hace él en GitHub o dice "fusiona" y lo hace Claude (`gh pr merge <n> --merge --delete-branch`, y luego actualizar `main` y borrar la rama local). Nunca se fusiona con el CI en rojo.

## Tecnología

- Python 3.13, con el entorno y las dependencias gestionados por `uv`. No uses `pip` directamente.
- Librerías: httpx (descarga), pandas (tablas y cálculos), plotly (gráficos interactivos), Jinja2 (plantillas HTML).
- Calidad: pytest para los tests y ruff para el formato y el lint.
- Los nombres de archivos, funciones y variables van en inglés. Los comentarios, la documentación y los commits van en español.
- El resultado final es una web estática en `site/`, adaptada a móvil y ordenador. Todavía no se ha decidido si se publica en GitHub Pages o en el hosting del usuario.

Comandos habituales:

- `uv sync`: crea o actualiza el entorno.
- `uv add <paquete>`: añade una dependencia (`--dev` si solo se usa para desarrollar).
- `uv run python -m pytest`: ejecuta los tests. GitHub Actions los ejecuta también en cada PR, junto con ruff (`.github/workflows/ci.yml`). En este equipo el antivirus (Bitdefender) bloquea los lanzadores `.exe` que crea uv en `.venv/Scripts` ("Acceso denegado"), así que las herramientas de Python se ejecutan siempre con `python -m <herramienta>`.
- `uv run ruff check .` y `uv run ruff format .`: revisan y formatean el código.

## Estructura

- `src/leioa_stats/`: el código. `download.py` (descarga con caché), `parse.py` (JSON a tablas), `validate.py` (contraste del jugada a jugada con el box score) y `metrics/` (`basic.py`, `advanced.py`, `lineups.py`, `shots.py`).
- `data/raw/` y `data/processed/`: datos descargados y procesados. No se versionan.
- `notebooks/`: exploración con Jupyter.
- `src/leioa_stats/web/`: generación de la web (`build.py`, `charts.py`, `templates/` con Jinja2 y `static/style.css`). Se genera con `uv run python -m leioa_stats.web`.
- `site/`: web generada. No se versiona. Para revisarla en el navegador, usa la configuración `web` de `.claude/launch.json` (servidor en el puerto 8000).
- `tests/`: tests. `tests/fixtures/` guarda el partido de ejemplo 99138.

Crea cada archivo o carpeta cuando haga falta, no antes.

## Antes de escribir código

- Los cambios de tecnología, de librerías o de estructura de carpetas se proponen y se esperan a que el usuario los apruebe.
- Los cambios deben ser pequeños y fáciles de revisar en un Pull Request.
- Con esfuerzo medio basta para casi todo. Pide subirlo a alto para los quintetos y el +/-.

## Datos

- Fuente: datos públicos de basketbasko.com (Federación Vasca), servidos en JSON por los servicios de Optimal Way Consulting.
- Cómo se obtienen (detalle en `src/leioa_stats/download.py`):
  - La lista de partidos de cada jornada sale de `esb.../FCBQWeb/resultats/<grupo>/<jornada>`. La respuesta va en base64 y necesita una clave que viene en el HTML de la página del grupo.
  - Las estadísticas y el jugada a jugada de un partido salen de `msstats.../getJsonWithMatchStats|Moves/<universallyid>` y no necesitan clave.
- `data/raw/matches.json` contiene los partidos de **toda la liga**. Para las métricas del Leioa, filtra con `download.involves(match, TEAM_NAME)`. `data/raw/upcoming.json` tiene sus próximos partidos.
- Respeta el servidor: guarda en local lo que ya se ha descargado, no repitas descargas innecesarias y deja una pausa entre peticiones.
- No subas al repositorio claves, tokens ni configuración personal; van en `.env`, que está ignorado.

## Fiabilidad de las métricas

Cada métrica que se presente al entrenador debe ir acompañada de su grado de fiabilidad:

- Los datos se anotan a mano en la mesa, así que puede haber errores. Hay que contrastar los totales del jugada a jugada con el box score.
- Los tapones sí aparecen en el partido 99138, aunque al principio se creyó que no se registraban. Hay que confirmarlo con más partidos antes de usarlos.
- Parte de los rebotes, pérdidas y recuperaciones son "de equipo" (sin jugador): el total del equipo es mayor que la suma de los jugadores. Para calcular posesiones se usan los totales del equipo.
- Un mate tiene su propio código (`100`) y es una canasta de 2: está en `validate.POINTS`, que usan todos los cálculos de puntos.
- Las faltas técnicas al entrenador cuentan para el equipo, no para ningún jugador. Hay códigos de jugada sin nombre en la web (por ejemplo, `565` y `571`, que son faltas). `validate.py` avisa si aparece un código desconocido: antes de darlo por error de la mesa, comprueba si es un tipo de jugada que aún no conocemos.
- Coordenadas de tiro: `xnormalize` e `ynormalize` van de 0 a 100 sobre una cancha de 28 × 15 m, siempre atacando hacia el aro de la izquierda (x = 5,625, y = 50). Están calibradas con la línea de triple (6,75 m). Ver `metrics/shots.py`.
- Antes de calcular métricas de un partido, revisa sus incidencias con `uv run python -m leioa_stats.validate`. Los quintetos y el +/- dependen de que los cambios estén bien anotados.
- Minutos: los del box score (`timePlayed`) a veces difieren hasta 2-3 minutos del reloj del jugada a jugada. Para los quintetos, el +/- y el on/off se usan los del jugada a jugada, que son los coherentes con el +/- de la federación.
- Quintetos: hay muchas combinaciones y pocos minutos por quinteto. No saques conclusiones de un quinteto con pocos minutos ni de un on/off con pocos partidos.
- La muestra es pequeña (26 jornadas): indica el tamaño de muestra y evita sacar conclusiones con pocos minutos o pocos intentos.
- Si una métrica es una estimación (por ejemplo, las posesiones), explica la fórmula usada.
