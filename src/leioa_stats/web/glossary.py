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
    (("Encajados",), "Puntos recibidos: los que anotan los rivales."),
    (("DIF",), "Diferencia de puntos: anotados menos encajados."),
    (
        ("Dif. C1", "Dif. C2", "Dif. C3", "Dif. C4"),
        "Diferencia de puntos (anotados menos encajados) por partido en ese cuarto. "
        "Positiva = el equipo suele ganar ese cuarto.",
    ),
    (
        ("2ª oportunidad",),
        "Puntos anotados en una posesión que sigue viva gracias a un rebote ofensivo propio "
        "(estimación a partir del jugada a jugada).",
    ),
    (
        ("PTS/RO",),
        "Puntos de 2ª oportunidad por cada rebote ofensivo: cuánto se aprovecha cada uno. "
        "La media de la liga ronda los 0,85.",
    ),
    (
        ("Tras pérdida",),
        "Puntos anotados en una posesión que empieza con una pérdida del rival o una "
        "recuperación propia (estimación a partir del jugada a jugada).",
    ),
    (
        ("Contraataque",),
        "Puntos anotados en los 8 segundos siguientes a un rebote defensivo o una "
        "recuperación. El umbral es una convención: el acta no dice si hubo contraataque.",
    ),
    (("Aro%",), "Acierto en los tiros cerca del aro (a menos de 3 metros)."),
    (("Forzadas",), "Pérdidas del rival: balones que le hace perder la defensa."),
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
    (
        ("NETO en pista",),
        "Neto del equipo mientras el jugador está en pista. Vacío con menos de 100 posesiones: "
        "con tan pocas, es casi puro ruido.",
    ),
    (("POSS en pista",), "Posesiones del equipo (estimación) con el jugador en pista."),
    (("POSS en banquillo",), "Posesiones del equipo (estimación) con el jugador en el banquillo."),
    (("NETO en banquillo",), "Neto del equipo mientras el jugador está en el banquillo."),
    (
        ("DIFERENCIA",),
        "Neto en pista menos neto en banquillo: cuánto mejor (o peor) va el equipo con él. "
        "Solo se calcula con 100 posesiones o más en pista y en el banquillo.",
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
    (
        ("% asistidas",),
        "Parte de sus canastas de campo que llegan tras una asistencia (según la mesa).",
    ),
    (("% triples asistidos",), "Parte de sus triples anotados que llegan tras una asistencia."),
    (
        ("Con robo",),
        "Pérdidas a balón vivo: el rival anota una recuperación en ese mismo segundo. Son las "
        "que provoca la presión y las que más contraataques dan.",
    ),
    (("Falta en ataque",), "Pérdidas por falta en ataque."),
    (
        ("Otras",),
        "Pérdidas a balón muerto sin falta: pasos, dobles, campo atrás, fuera de banda, "
        "24 segundos...",
    ),
    (("% con robo",), "Parte de las pérdidas que son con robo (a balón vivo)."),
    (("Pasa", "Anota", "Canastas"), "Quién da la asistencia, quién anota y cuántas canastas."),
    (("Triples",), "De esas canastas, cuántas son triples."),
    (
        ("2 en la 1.ª parte",),
        "Partidos en los que llegó a 2 faltas antes del descanso (minuto 20).",
    ),
    (
        ("4 antes del 4.º cuarto",),
        "Partidos en los que llegó a 4 faltas antes del último cuarto (minuto 30).",
    ),
    (("Eliminado",), "Partidos en los que llegó a 5 faltas."),
    (("C1", "C2", "C3", "C4"), "Cuarto del partido (PR = prórroga)."),
    (("Cifra",), "Lo que se cruza: tiro, pérdidas, rebote ofensivo, tiros libres..."),
    (
        ("Lado",),
        "Nuestro ataque contra su defensa, o su ataque contra nuestra defensa.",
    ),
    (("Ataque",), "Lo que hace el equipo que ataca en esa cifra (temporada)."),
    (("Permite",), "Lo que concede la defensa del otro equipo en esa cifra (temporada)."),
    (("Liga",), "Media de la liga en esa cifra."),
    (
        ("Esperable",),
        "Valor esperado en el partido: lo que hace el atacante + lo que permite el defensor − "
        "la media de la liga (modelo aditivo).",
    ),
    (
        ("Veredicto", "Previa"),
        "A favor o en contra si el cruce se aleja de la media 1,5 errores estándar o más. "
        "Choque: el ataque y la defensa son buenos a la vez.",
    ),
    (("Confianza",), "Alta (2 errores estándar o más) o media (entre 1,5 y 2)."),
    (("Real",), "Lo que pasó en el partido."),
    (
        ("¿Se cumplió?",),
        "Si el valor real quedó del lado que decía la previa respecto a la media de la liga.",
    ),
    (("Ficha",), "Posición y altura, según la hoja del cuerpo técnico."),
    (("Último partido",), "Si estuvo en el acta del último partido de su equipo."),
    (
        ("NETO aj.",),
        "Neto ajustado: corrige el neto por la calidad de los rivales a los que se ha enfrentado "
        "y por la ventaja de jugar en casa (ver metrics/adjusted.py).",
    ),
    (("ORtg aj.",), "Eficiencia ofensiva ajustada por rival y pista."),
    (("DRtg aj.",), "Eficiencia defensiva ajustada por rival y pista."),
    (
        ("Forma",),
        "↑ o ↓ si el neto de los 3 últimos partidos se aleja del de los anteriores 1,5 errores "
        "estándar o más. Hacen falta 6 partidos.",
    ),
    (("Pareja", "Trío"), "Dos o tres jugadores en pista a la vez, con cualquier compañero."),
    (("Tiempos muertos",), "Tiempos muertos pedidos por el equipo."),
    (
        ("PTS tras tiempo muerto",),
        "Puntos del equipo en el minuto de juego siguiente a su tiempo muerto (media).",
    ),
    (
        ("PTS rival tras tiempo muerto",),
        "Puntos del rival en el minuto de juego siguiente al tiempo muerto (media).",
    ),
    (("PTS por minuto (temporada)",), "Puntos del equipo por minuto en toda la temporada."),
    (
        ("PTS rival por minuto (temporada)",),
        "Puntos que encaja el equipo por minuto en toda la temporada.",
    ),
]

TERMS: dict[str, str] = {term: text for terms, text in ENTRIES for term in terms}
