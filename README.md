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
- Parte de los rebotes y pérdidas se anotan "de equipo", sin jugador: el total del equipo es mayor que la suma de sus jugadores.
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

Descarga las estadísticas y el jugada a jugada de todos los partidos ya jugados del Leioa SBT en `data/raw/`. Los partidos que ya están descargados no se vuelven a pedir, así que basta con ejecutarlo después de cada jornada:

```bash
uv run python -m leioa_stats.download
```

## Resultado

El proyecto genera una web estática (carpeta `site/`) con un informe por partido, uno de temporada y uno por jugador, pensada para verse en el móvil y en el ordenador.

## Estado

Proyecto en fase inicial: la descarga de partidos ya funciona. El siguiente paso es comprobar automáticamente si el jugada a jugada de cada partido cuadra con el box score.
