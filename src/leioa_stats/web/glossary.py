"""Definiciones de los términos técnicos de la web.

Es la única fuente: de aquí salen el glosario del final de cada página y los botones "?" que
explican cada término en las tablas. Cada entrada: (términos que la usan, definición).
Las variantes "/PJ", "/40" y " rival" se explican solas a partir del término base (glossary.js).
"""

ENTRIES: list[tuple[tuple[str, ...], str]] = [
    (("PJ",), "Partidos jugados (con algún minuto en pista)."),
    (("TIT",), "Partidos como titular."),
    (("MIN",), "Minutos jugados."),
    (("PTS",), "Puntos."),
    (("PTS rival",), "Puntos del rival mientras ese quinteto estaba en pista."),
    (("Dorsal",), "Número de la camiseta."),
    (
        ("TC", "TCM", "TCA"),
        "Tiros de campo: los de 2 más los de 3 (no incluye tiros libres). "
        "M = anotados, A = intentados.",
    ),
    (("T2", "T2M", "T2A"), "Tiros de 2. M = anotados, A = intentados."),
    (("T3", "T3M", "T3A"), "Triples. M = anotados, A = intentados."),
    (("T1", "T1M", "T1A"), "Tiros libres. M = anotados, A = intentados."),
    (("TC%",), "Porcentaje de acierto en tiros de campo: TCM / TCA."),
    (("T2%",), "Porcentaje de acierto en tiros de 2."),
    (("T3%",), "Porcentaje de acierto en triples."),
    (("T1%",), "Porcentaje de acierto en tiros libres."),
    (
        ("eFG%", "Tiro (eFG%)"),
        "Acierto efectivo: (TCM + 0,5 × T3M) / TCA. Como el TC%, pero dando a cada triple el "
        "valor extra que tiene. La media de la liga ronda el 46 %.",
    ),
    (
        ("TS%",),
        "Acierto real: PTS / (2 × (TCA + 0,44 × T1A)). Mide cuántos puntos saca un jugador de "
        "sus tiros, contando también los tiros libres.",
    ),
    (("RO",), "Rebotes ofensivos: los que coge el equipo que ha fallado el tiro."),
    (("RD",), "Rebotes defensivos."),
    (("RT",), "Rebotes totales (ofensivos + defensivos)."),
    (("AS",), "Asistencias: pases que terminan directamente en canasta."),
    (("PER",), "Pérdidas de balón."),
    (("REC",), "Recuperaciones (robos de balón)."),
    (("TAP",), "Tapones."),
    (("FP",), "Faltas personales cometidas."),
    (("FR",), "Faltas recibidas."),
    (("VAL",), "Valoración de la federación: suma lo positivo y resta lo negativo del acta."),
    (
        ("+/-",),
        "Diferencia de puntos (a favor menos en contra) mientras el jugador o el quinteto "
        "estaba en pista.",
    ),
    (
        ("POSS",),
        "Posesiones (estimación): TCA + 0,44 × T1A − RO + PER. Cada posesión termina en tiro, "
        "tiros libres o pérdida.",
    ),
    (
        ("RITMO", "Ritmo"),
        "Posesiones por 40 minutos: cuántas veces ataca cada equipo en un partido. "
        "Alto = juego rápido. La media de la liga ronda las 82.",
    ),
    (
        ("ORtg", "Ataque", "Eficiencia (pts/100 pos.)"),
        "Eficiencia ofensiva: puntos anotados por cada 100 posesiones. "
        "La media de la liga ronda los 94.",
    ),
    (
        ("DRtg", "Defensa"),
        "Eficiencia defensiva: puntos encajados por cada 100 posesiones. Bajo = mejor.",
    ),
    (
        ("NETO", "Neto"),
        "Diferencia entre la eficiencia ofensiva y la defensiva: puntos de diferencia por cada "
        "100 posesiones.",
    ),
    (
        ("PER%", "Pérdidas"),
        "Pérdidas por cada 100 posesiones. Bajo = cuida mejor el balón.",
    ),
    (
        ("RO%", "Rebote of."),
        "Porcentaje de rebote ofensivo: de los tiros que falla, cuántos rebotes recupera "
        "(RO / (RO + RD del rival)).",
    ),
    (
        ("TL/TC", "Tiros libres"),
        "Tiros libres anotados por cada 100 tiros de campo: cuánto saca de ir a la línea.",
    ),
    (
        ("USO%",),
        "Parte de las jugadas del equipo que termina el jugador (con un tiro, tiros libres o "
        "una pérdida) mientras está en pista. La media es el 20 %; por encima del 25 %, es una "
        "referencia del ataque.",
    ),
    (("NETO en pista",), "Neto del equipo mientras el jugador está en pista."),
    (("NETO en banquillo",), "Neto del equipo mientras el jugador está en el banquillo."),
    (
        ("DIFERENCIA",),
        "Neto en pista menos neto en banquillo: cuánto mejor (o peor) va el equipo con él.",
    ),
    (
        ("% cerca del aro",),
        "Parte de sus tiros de campo lanzados a menos de 3 metros del aro.",
    ),
    (("% triples",), "Parte de sus tiros de campo que son triples."),
    (
        ("Perfil",),
        "Estimación a partir de dónde tira y de sus rebotes ofensivos (la federación no publica "
        "posiciones). Interior: la mitad de sus tiros cerca del aro. Exterior: la mitad, triples. "
        "Mixto: el resto. Con menos de 10 tiros no se estima.",
    ),
    (
        ("PTS/tiro",),
        "Puntos por cada tiro de campo desde esa zona. Un triple al 33 % da 1 punto por tiro.",
    ),
    (("% de los tiros",), "Parte de todos los tiros de campo que se lanzan desde esa zona."),
    (("%",), "Porcentaje de acierto."),
    (
        ("Zona",),
        "Cerca del aro (menos de 3 m), media distancia (resto de tiros de 2), triple de esquina "
        "y triple frontal. Se calculan con las coordenadas del mapa de tiros.",
    ),
    (
        ("Quinteto",),
        "Los cinco jugadores en pista, por dorsales. Solo cuentan los tramos con 5 jugadores "
        "bien anotados.",
    ),
    (("V", "D"), "Victorias y derrotas."),
]

TERMS: dict[str, str] = {term: text for terms, text in ENTRIES for term in terms}
