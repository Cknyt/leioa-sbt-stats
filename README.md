# Leioa SBT Stats

Análisis estadístico de los partidos del **Leioa SBT** (senior masculino) a partir de los datos públicos que publica la Federación Vasca de Baloncesto en [basketbasko.com](https://basketbasko.com).

## Competición

- **Liga:** Primera División Masculina del País Vasco — "1ª Mas-Liga Regular - Único" (14 equipos, 26 jornadas).
- **Ámbito:** autonómico (pendiente de confirmar con el entrenador).
- **Grupo:** <https://basketbasko.com/es/group/?id=2876&round=1>

## Objetivo

Averiguar qué métricas se pueden obtener de los datos públicos de cada partido y hasta qué punto son fiables para que el cuerpo técnico tome decisiones:

- **Básicas:** puntos, tiros de campo y libres, rebotes, asistencias, pérdidas, recuperaciones, faltas, valoración.
- **Avanzadas:** posesiones, ritmo, eficiencia ofensiva y defensiva, Four Factors, TS%, eFG%, porcentaje de uso.
- **De jugada a jugada:** quintetos en pista, +/- por jugador y por quinteto, rachas de anotación y mapa de tiros.

## Fuentes de datos

Cada partido publica un resumen por equipo y por cuartos, el box score por jugador, el mapa de tiros y el jugada a jugada con los cambios. La web obtiene esos datos en formato JSON de los servicios de Optimal Way Consulting (ficha del partido, jugada a jugada y estadísticas con las coordenadas de cada tiro).

Partido de ejemplo: [Leioa SBT 76-70 Easo Basket](https://basketbasko.com/es/match/?id=99138&tab=1).

## Limitaciones conocidas

- Los datos se anotan a mano en la mesa de anotación, así que puede haber errores.
- Se creía que los tapones no se registraban, pero en el primer partido revisado (99138) sí aparecen. Queda pendiente confirmarlo con más partidos.
- Parte de los rebotes, pérdidas y recuperaciones se anotan "de equipo", sin jugador: el total del equipo es mayor que la suma de sus jugadores.
- En los 14 partidos de las dos primeras jornadas de la liga no hay errores en los datos, solo 12 avisos de anotación (cambios sin anotar, faltas técnicas que no aparecen en el jugada a jugada).
- La muestra es pequeña (26 jornadas por temporada), por lo que muchas métricas tendrán mucha variabilidad.

## Puesta en marcha

Hace falta tener instalado [uv](https://docs.astral.sh/uv/). Para crear el entorno con todas las dependencias:

```bash
uv sync
```

Para comprobar que todo funciona:

```bash
uv run python -m pytest
```

## Descargar los partidos

Descarga las estadísticas y el jugada a jugada de todos los partidos ya jugados **de la liga** (para el scouting de rivales) en `data/raw/`, y los próximos partidos del Leioa SBT en `data/raw/upcoming.json`. Los partidos que ya están descargados no se vuelven a pedir, así que basta con ejecutarlo después de cada jornada:

```bash
uv run python -m leioa_stats.download
```

## Validar los datos

Comprueba, partido a partido, si el jugada a jugada cuadra con el box score: marcador, totales de cada estadística, tapones, minutos, mapa de tiros y quintetos en pista. Cada incidencia se clasifica como **error** (los datos se contradicen), **aviso** (probable error de anotación en la mesa) o **info** (diferencia esperada, como los rebotes de equipo):

```bash
uv run python -m leioa_stats.validate
```

## Métricas básicas y de tiro

Muestra las métricas de la temporada del equipo (frente a sus rivales), de cada jugador y por zonas de tiro, y guarda las tablas en `data/processed/` (CSV):

```bash
uv run python -m leioa_stats.metrics
```

- **Tiro:** TC%, T2%, T3%, T1%, eFG% = (TCM + 0,5 × T3M) / TCA y TS% = PTS / (2 × (TCA + 0,44 × T1A)).
- **Producción:** medias por partido y por 40 minutos.
- **Zonas:** cerca del aro (< 3 m), media distancia, triple de esquina y triple frontal, calculadas a partir de las coordenadas del mapa de tiros.
- **Avanzadas** (estimaciones; fórmulas en `metrics/advanced.py`):
  - Posesiones = TCA + 0,44 × T1A - RO + PER, con la media de los dos equipos.
  - Ritmo = posesiones por 40 minutos.
  - Eficiencia ofensiva y defensiva = puntos anotados y recibidos por 100 posesiones.
  - Four Factors = eFG%, PER%, RO% y TL/TC, del equipo y de sus rivales.
  - % de uso de cada jugador.
- **Quintetos y +/-** (reconstruidos con el jugada a jugada; detalle en `metrics/lineups.py`): minutos, +/- y eficiencia de cada quinteto, y +/- y on/off de cada jugador (diferencia por 100 posesiones con él en pista y en el banquillo). El +/- coincide con el que calcula la federación.

## Web

Genera una web estática en `site/`, pensada para verse en el móvil y en el ordenador. Tiene una página de temporada (con el próximo partido y la clasificación avanzada de la liga), una por cada partido del Leioa y una de **scouting por cada equipo**: dónde es fuerte frente a la media de la liga, sus jugadores con su perfil de juego estimado (interior, exterior o mixto), el mapa de tiros de cada jugador y sus quintetos. Los gráficos son interactivos (plotly).

Cada término técnico lleva un botón **?** con su explicación (se toca en el móvil o se pasa el ratón en el ordenador), y cada página incluye **conclusiones automáticas**: estilo de juego, fortalezas, puntos débiles, jugadores clave, ideas para el partido y claves de cada partido. Las conclusiones salen de reglas fijas con umbrales explícitos (`metrics/insights.py`), no de un modelo de lenguaje, así que cada frase se puede comprobar con los números de la página.

Para generarla:

```bash
uv run python -m leioa_stats.web
```

Para verla en local, sírvela con:

```bash
uv run python -m http.server 8000 --directory site
```

Después abre <http://localhost:8000>. Es una web estática: se puede publicar en cualquier hosting que sirva HTML, sin necesidad de Python.

## Estado

Proyecto en fase inicial: la descarga y la validación de partidos ya funcionan. En los dos primeros partidos no hay errores, solo dos avisos de anotación (un cambio no anotado y una falta técnica que no aparece en el jugada a jugada). Ya se calculan las métricas básicas, de tiro, avanzadas, de quintetos y el +/-. La web ya se genera en local, con scouting de los 14 equipos. El siguiente paso es publicarla y automatizar la actualización tras cada jornada.
