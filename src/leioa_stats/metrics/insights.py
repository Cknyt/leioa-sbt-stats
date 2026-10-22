"""Conclusiones automáticas en lenguaje de banquillo.

Cada conclusión sale de una regla fija con umbrales explícitos (no de un modelo de lenguaje),
así que siempre se puede comprobar con los números de la página:
- Fortaleza o debilidad de equipo: estar en el primer o el último cuarto de la liga en esa
  métrica (con 14 equipos, entre los 4 primeros o los 4 últimos).
- Perfil de tiro: tirar 8 puntos más (o menos) de triples que la media de la liga.
- Zonas: con 15 o más tiros en la zona, acertar 10 puntos más (o menos) que la liga.
- Jugadores: umbrales de uso, TS% y triples con un mínimo de minutos y de tiros.
- Partido: diferencias claras en los Four Factors y máxima ventaja en el marcador.
"""

from dataclasses import dataclass

import pandas as pd

from leioa_stats.format import display_name, number
from leioa_stats.metrics.advanced import four_factors

THREE_SHARE_MARGIN = 8
ZONE_MIN_ATTEMPTS = 15
ZONE_MARGIN = 10
PLAYER_MIN_MINUTES_PER_GAME = 12
PLAYER_MIN_MINUTES = 30  # en total: evita destacar a quien ha jugado un solo rato
PLAYER_MIN_SHOTS = 12


@dataclass(frozen=True)
class Metric:
    column: str
    higher_is_better: bool
    good: str
    bad: str
    value: str  # cómo se lee el valor, con {v}
    idea_if_good: str = ""  # idea para jugar contra un equipo fuerte en esto
    idea_if_bad: str = ""  # idea para jugar contra un equipo débil en esto


METRICS = [
    Metric("ORtg", True, "Ataque muy eficiente", "Ataque poco eficiente",
           "{v} puntos por 100 posesiones"),
    Metric("DRtg", False, "Defensa muy sólida", "Defensa que concede mucho",
           "{v} puntos encajados por 100 posesiones"),
    Metric("eFG%", True, "Tira muy bien", "Le cuesta anotar", "eFG% del {v} %",
           idea_if_good="Su fuerza es el tiro: defender cerca a sus tiradores y no conceder "
                        "tiros liberados."),
    Metric("PER%", False, "Cuida mucho el balón", "Pierde muchos balones",
           "{v} pérdidas por 100 posesiones",
           idea_if_bad="Presionar el balón: es de los equipos que más pierden."),
    Metric("RO%", True, "Fuerte en el rebote ofensivo", "Apenas captura rebotes ofensivos",
           "{v} % de rebote ofensivo",
           idea_if_good="Cerrar el rebote defensivo: recupera muchos de sus propios fallos."),
    Metric("TL/TC", True, "Saca mucho de la línea de tiros libres", "Apenas saca tiros libres",
           "{v} tiros libres anotados por 100 tiros de campo",
           idea_if_good="Evitar faltas innecesarias: saca mucho de la línea de tiros libres."),
    Metric("eFG% rival", False, "Defiende bien el tiro", "Deja tirar cómodos a sus rivales",
           "sus rivales tiran con un eFG% del {v} %",
           idea_if_good="Su defensa del tiro es buena: paciencia en ataque para buscar buenos "
                        "tiros.",
           idea_if_bad="Su defensa concede buenos tiros: aprovechar a los tiradores."),
    Metric("PER% rival", True, "Fuerza muchas pérdidas", "Apenas fuerza pérdidas",
           "{v} pérdidas rivales por 100 posesiones",
           idea_if_good="Fuerza muchas pérdidas: cuidar el balón ante su presión."),
    Metric("RO% rival", False, "Cierra bien su rebote defensivo",
           "Concede muchos rebotes ofensivos", "sus rivales cogen el {v} % de rebote ofensivo",
           idea_if_bad="Ir al rebote ofensivo: concede muchas segundas oportunidades."),
    Metric("TL/TC rival", False, "Hace pocas faltas que acaben en tiros libres",
           "Manda mucho a sus rivales a la línea de tiros libres",
           "sus rivales anotan {v} tiros libres por 100 tiros de campo",
           idea_if_bad="Atacar el aro: manda mucho a sus rivales a la línea de tiros libres."),
]  # fmt: skip

ZONE_PHRASES = {
    "Cerca del aro": "cerca del aro",
    "Media distancia": "en media distancia",
    "Triple de esquina": "en el triple de esquina",
    "Triple frontal": "en el triple frontal",
}


@dataclass
class TeamInsights:
    style: list[str]
    strengths: list[str]
    weaknesses: list[str]
    players: list[str]
    ideas: list[str]


def _rank(league: pd.DataFrame, column: str, team: str, higher_is_better: bool) -> int:
    return int(league[column].rank(ascending=not higher_is_better, method="min")[team])


def _average(average: pd.Series, column: str) -> float:
    # Lo que permite la liga en conjunto es lo mismo que hace: eFG% rival medio = eFG% medio.
    base = column.removesuffix(" rival")
    return average["ORtg" if base == "DRtg" else base]


def three_point_share(shots: pd.DataFrame) -> float:
    return 100 * (shots["value"] == 3).mean() if len(shots) else 0.0


def team_insights(
    team: str,
    league: pd.DataFrame,
    average: pd.Series,
    season_players: pd.DataFrame,
    team_shots: pd.DataFrame,
    league_shots: pd.DataFrame,
) -> TeamInsights:
    """Fortalezas, debilidades, jugadores clave e ideas para jugar contra el equipo.

    `team_shots` y `league_shots` deben llevar la zona (metrics.shots.add_zones).
    `season_players` es la tabla de temporada del equipo con USO% y Perfil.
    """
    n = len(league)
    cutoff = max(1, round(n / 4))
    style, strengths, weaknesses, ideas = [], [], [], []

    for metric in METRICS:
        rank = _rank(league, metric.column, team, metric.higher_is_better)
        value = metric.value.format(v=number(league.loc[team, metric.column]))
        context = f"({rank}.º de {n}; media de la liga {number(_average(average, metric.column))})"
        if rank <= cutoff:
            strengths.append(f"{metric.good}: {value} {context}.")
            if metric.idea_if_good:
                ideas.append(metric.idea_if_good)
        elif rank > n - cutoff:
            weaknesses.append(f"{metric.bad}: {value} {context}.")
            if metric.idea_if_bad:
                ideas.append(metric.idea_if_bad)

    pace_rank = _rank(league, "RITMO", team, True)
    pace = f"{number(league.loc[team, 'RITMO'])} posesiones por 40 minutos"
    if pace_rank <= cutoff:
        style.append(f"Juega rápido: {pace} ({pace_rank}.º de {n}).")
    elif pace_rank > n - cutoff:
        style.append(f"Juega lento: {pace} ({pace_rank}.º de {n}).")

    share = three_point_share(team_shots)
    league_share = three_point_share(league_shots)
    accuracy = 100 * team_shots.loc[team_shots["value"] == 3, "made"].mean()
    if share >= league_share + THREE_SHARE_MARGIN:
        style.append(
            f"Vive del triple: el {number(round(share, 1))} % de sus tiros de campo son triples "
            f"(media de la liga {number(round(league_share, 1))} %), con un "
            f"{number(round(accuracy, 1))} % de acierto."
        )
        ideas.append(
            "Defender la línea de triple: más de la mitad de su ataque sale de ahí."
            if share >= 50
            else "Defender la línea de triple: es su arma principal."
        )
    elif share <= league_share - THREE_SHARE_MARGIN:
        style.append(
            f"Juega por dentro: solo el {number(round(share, 1))} % de sus tiros son triples "
            f"(media de la liga {number(round(league_share, 1))} %)."
        )
        ideas.append("Proteger la zona: su ataque busca el aro más que el triple.")

    league_zones = league_shots.groupby("zone")["made"].mean() * 100
    for zone, zone_shots in team_shots.groupby("zone"):
        if len(zone_shots) < ZONE_MIN_ATTEMPTS:
            continue
        pct = 100 * zone_shots["made"].mean()
        diff = pct - league_zones[zone]
        detail = (
            f"{ZONE_PHRASES[zone]}: {number(round(pct, 1))} % en {len(zone_shots)} tiros "
            f"(media de la liga {number(round(league_zones[zone], 1))} %)."
        )
        if diff >= ZONE_MARGIN:
            strengths.append(f"Muy acertado {detail}")
        elif diff <= -ZONE_MARGIN:
            weaknesses.append(f"Poco acertado {detail}")

    players, player_ideas = _player_insights(season_players)
    ideas += player_ideas
    return TeamInsights(style, strengths, weaknesses, players, ideas)


def _player_insights(season: pd.DataFrame) -> tuple[list[str], list[str]]:
    regulars = season[
        (season["MIN/PJ"] >= PLAYER_MIN_MINUTES_PER_GAME) & (season["MIN"] >= PLAYER_MIN_MINUTES)
    ].copy()
    regulars["shots"] = regulars["TCA"] + 0.44 * regulars["T1A"]
    texts, ideas = [], []
    star = None
    if not regulars.empty and regulars["USO%"].max() >= 24:
        star = regulars["USO%"].idxmax()
        row = regulars.loc[star]
        texts.append(
            f"{display_name(star)} es su referencia en ataque: termina el "
            f"{number(row['USO%'])} % de las jugadas cuando está en pista "
            f"({number(row['PTS/PJ'])} puntos por partido, TS% del {number(row['TS%'])} %)."
        )
        ideas.append(f"Su ataque pasa por {display_name(star)}: centrar la defensa en él.")
    volume = regulars[regulars["shots"] >= PLAYER_MIN_SHOTS]
    for name, row in volume.sort_values("TS%", ascending=False).iterrows():
        if name != star and row["TS%"] >= 60:
            texts.append(
                f"{display_name(name)} es muy eficiente: TS% del {number(row['TS%'])} % con "
                f"{number(row['PTS/PJ'])} puntos por partido."
            )
    for name, row in volume.iterrows():
        if row["USO%"] >= 22 and row["TS%"] < 45:
            texts.append(
                f"{display_name(name)} tira mucho con poco acierto: uso del "
                f"{number(row['USO%'])} % y TS% del {number(row['TS%'])} %."
            )
    shooters = season[(season["T3A"] >= 8) & (season["T3%"] >= 40)]
    for name, row in shooters.sort_values("T3M", ascending=False).iterrows():
        texts.append(
            f"{display_name(name)} es peligroso desde el triple: {int(row['T3M'])}/"
            f"{int(row['T3A'])} ({number(row['T3%'])} %)."
        )
        ideas.append(f"No dejar tirar solo a {display_name(name)} desde fuera.")
    return texts, ideas


FACTOR_LABELS = {
    "eFG%": ("el tiro (eFG%)", 5, True, "{v} %"),
    "PER%": ("el cuidado del balón (pérdidas por 100 posesiones)", 5, False, "{v}"),
    "RO%": ("el rebote ofensivo", 8, True, "{v} %"),
    "TL/TC": ("los tiros libres (anotados por 100 tiros de campo)", 8, True, "{v}"),
}


def match_insights(
    own_game: pd.DataFrame, moves_diffs: list[int], team: str, rival: str
) -> list[str]:
    """Claves de un partido: en qué factores hubo diferencias claras y cómo fue el marcador.

    `own_game` es la fila de advanced.team_games del equipo en ese partido y `moves_diffs`, la
    diferencia en el marcador (a favor del equipo) tras cada canasta.
    """
    own, opp = four_factors(own_game), four_factors(own_game, "_opp")
    texts = []
    for column, (label, margin, higher_is_better, fmt) in FACTOR_LABELS.items():
        diff = own[column] - opp[column]
        if abs(diff) < margin:
            continue
        better = (diff > 0) == higher_is_better
        winner, loser = (team, rival) if better else (rival, team)
        a, b = (own[column], opp[column]) if better else (opp[column], own[column])
        texts.append(
            f"{display_name(winner)} fue claramente mejor en {label}: "
            f"{fmt.format(v=number(round(a, 1)))} frente a {fmt.format(v=number(round(b, 1)))} "
            f"de {display_name(loser)}."
        )
    if moves_diffs:
        best, worst = max(moves_diffs), min(moves_diffs)
        lead = f"Máxima ventaja de {display_name(team)}: {f'+{best}' if best > 0 else 'ninguna'}."
        deficit = (
            f" Máxima desventaja: {worst}."
            if worst < 0
            else f" {display_name(rival)} nunca fue por delante."
        )
        texts.append(lead + deficit)
    return texts
