"""Conclusiones automáticas en lenguaje de banquillo.

Dos pasos separados:
1. Hechos (Fact): cada cifra con su valor, la media de la liga, cuántos partidos o intentos
   hay detrás y su distancia a la media en errores estándar (z, ver metrics/confidence.py).
   El informe prepartido y la revisión pospartido parten de estos mismos hechos.
2. Frases (Insight): se redactan solo para los hechos con confianza alta o media, y cada
   una dice de dónde sale (valor, puesto y media de la liga).

Reglas (umbrales explícitos, se pueden comprobar con los números de la página):
- Fortaleza o debilidad de equipo: |z| ≥ 1,5 en esa métrica. El puesto se muestra, pero ya
  no decide nada (antes bastaba con estar entre los 4 primeros o los 4 últimos).
- Ritmo: |z| ≥ 1,5 → juega rápido o lento.
- Perfil de tiro: tirar 8 puntos más (o menos) de triples que la liga, con |z| ≥ 1,5 en el
  reparto. La idea depende del acierto: si acierta igual o más que la liga, defender el
  triple; si acierta menos, cerrar la zona.
- Zonas: con 15 o más tiros, |z| ≥ 1,5 en el acierto frente al de la liga.
- Jugadores: el acierto se encoge hacia la media de la liga (confidence.shrink) antes de
  aplicar los umbrales; las tablas siguen mostrando el dato real.
- Ideas para el partido: como mucho MAX_IDEAS, ordenadas por confianza y sin ideas que se
  contradigan (por ejemplo, presionar y evitar faltas).
- Partido: diferencias claras en los Four Factors y máxima ventaja en el marcador. Describe
  lo que pasó, no es una inferencia, así que no lleva confianza.
"""

import math
from dataclasses import dataclass, field

import pandas as pd

from leioa_stats.format import display_name, number
from leioa_stats.metrics.advanced import four_factors
from leioa_stats.metrics.confidence import (
    DEFAULT_K,
    DEFAULT_SPREAD,
    estimate_k,
    label,
    proportion_z,
    shrink,
    shrink_weight,
    team_z,
)

THREE_SHARE_MARGIN = 8
ZONE_MIN_ATTEMPTS = 15
PLAYER_MIN_MINUTES_PER_GAME = 12
PLAYER_MIN_MINUTES = 30  # en total: evita destacar a quien ha jugado un solo rato
PLAYER_MIN_SHOTS = 12
SHOOTER_MIN_THREES = 15
# Márgenes sobre la media de la liga, aplicados al acierto encogido.
EFFICIENT_MARGIN = 0.06  # TS% encogido 6 puntos por encima de la liga
WASTEFUL_MARGIN = 0.05  # TS% encogido 5 puntos por debajo, con mucho uso
SHOOTER_MARGIN = 0.04  # T3% encogido 4 puntos por encima de la liga
# Un jugador medio de la liga lanza unos 6-7 triples por 40 minutos.
VOLUME_THREES_PER_40 = 12
MAX_VOLUME_SHOOTERS = 2
STAR_USAGE = 24
WASTEFUL_USAGE = 22
STAR_MINUTES_HIGH = 100  # con menos minutos, la referencia en ataque es de confianza media
MAX_IDEAS = 5
# Ideas que no se proponen juntas: presionar el balón conlleva hacer más faltas.
CONFLICTS = {frozenset({"presion", "faltas"})}


@dataclass(frozen=True)
class Metric:
    column: str
    higher_is_better: bool
    good: str
    bad: str
    value: str  # cómo se lee el valor, con {v}
    idea_if_good: str = ""  # idea para jugar contra un equipo fuerte en esto
    idea_if_bad: str = ""  # idea para jugar contra un equipo débil en esto
    group: str = ""  # para descartar ideas que se contradicen


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
           idea_if_bad="Presionar el balón: es de los equipos que más pierden, y muchas de sus "
                       "pérdidas son con robo.", group="presion"),
    Metric("RO%", True, "Fuerte en el rebote ofensivo", "Apenas captura rebotes ofensivos",
           "{v} % de rebote ofensivo",
           idea_if_good="Cerrar el rebote defensivo: recupera muchos de sus propios fallos."),
    Metric("TL/TC", True, "Saca mucho de la línea de tiros libres", "Apenas saca tiros libres",
           "{v} tiros libres anotados por 100 tiros de campo",
           idea_if_good="Evitar faltas innecesarias: saca mucho de la línea de tiros libres.",
           group="faltas"),
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
METRIC_BY_COLUMN = {m.column: m for m in METRICS}

ZONE_PHRASES = {
    "Cerca del aro": "cerca del aro",
    "Media distancia": "en media distancia",
    "Triple de esquina": "en el triple de esquina",
    "Triple frontal": "en el triple frontal",
}


@dataclass(frozen=True)
class Fact:
    """Una cifra de un equipo frente a la liga. z > 0 = mejor que la media."""

    key: str
    subject: str
    value: float
    average: float
    z: float
    n: int
    rank: int | None = None
    se: float = float("nan")  # error estándar del valor

    @property
    def confidence(self) -> str | None:
        return label(self.z)


@dataclass(frozen=True)
class Insight:
    text: str
    confidence: str  # "alta" o "media"
    score: float = 0.0  # para ordenar: |z| o equivalente
    group: str = ""


@dataclass
class TeamInsights:
    style: list[Insight]
    strengths: list[Insight]
    weaknesses: list[Insight]
    players: list[Insight]
    ideas: list[Insight]
    facts: list[Fact] = field(default_factory=list)


@dataclass(frozen=True)
class ShootingBaseline:
    """Acierto de la liga (0-1) y fuerza del encogimiento para TS% y triples."""

    ts: float
    three: float
    k_ts: float = DEFAULT_K["TS%"]
    k_three: float = DEFAULT_K["T3%"]


def shooting_baseline(players: pd.DataFrame) -> ShootingBaseline:
    """Referencias de tiro de toda la liga a partir del box score de todos los jugadores."""
    totals = players.groupby(["team", "player"])[["PTS", "T2A", "T3A", "T3M", "T1A"]].sum()
    tsa = totals["T2A"] + totals["T3A"] + 0.44 * totals["T1A"]
    ts = totals["PTS"].sum() / (2 * tsa.sum()) if tsa.sum() else 0.5
    three = totals["T3M"].sum() / totals["T3A"].sum() if totals["T3A"].sum() else 0.3
    k_three = estimate_k(totals["T3M"], totals["T3A"], DEFAULT_K["T3%"])
    return ShootingBaseline(ts=ts, three=three, k_three=k_three)


def _rank(league: pd.DataFrame, column: str, team: str, higher_is_better: bool) -> int:
    return int(league[column].rank(ascending=not higher_is_better, method="min")[team])


def _average(average: pd.Series, column: str) -> float:
    # Lo que permite la liga en conjunto es lo mismo que hace: eFG% rival medio = eFG% medio.
    base = column.removesuffix(" rival")
    return average["ORtg" if base == "DRtg" else base]


def team_facts(
    team: str, league: pd.DataFrame, average: pd.Series, spread: pd.Series | None = None
) -> list[Fact]:
    """Hechos de un equipo: cada métrica de METRICS y el ritmo, con su z."""
    spread = pd.Series(DEFAULT_SPREAD) if spread is None else spread
    games = int(league.loc[team, "PJ"])
    facts = []
    for column, higher in [("RITMO", True)] + [(m.column, m.higher_is_better) for m in METRICS]:
        value = league.loc[team, column]
        avg = average["RITMO"] if column == "RITMO" else _average(average, column)
        facts.append(
            Fact(
                key=column,
                subject=team,
                value=float(value),
                average=float(avg),
                z=team_z(value, avg, spread[column], games, higher),
                n=games,
                rank=_rank(league, column, team, higher),
                se=spread[column] / math.sqrt(games) if games else float("nan"),
            )
        )
    return facts


def three_point_share(shots: pd.DataFrame) -> float:
    return 100 * (shots["value"] == 3).mean() if len(shots) else 0.0


def _context(fact: Fact, n_teams: int) -> str:
    return f"({fact.rank}.º de {n_teams}; media de la liga {number(round(fact.average, 1))})"


def team_insights(
    team: str,
    league: pd.DataFrame,
    average: pd.Series,
    season_players: pd.DataFrame,
    team_shots: pd.DataFrame,
    league_shots: pd.DataFrame,
    *,
    spread: pd.Series | None = None,
    shooting: ShootingBaseline | None = None,
    turnovers: tuple[float, float] | None = None,
) -> TeamInsights:
    """Fortalezas, debilidades, jugadores clave e ideas para jugar contra el equipo.

    `team_shots` y `league_shots` deben llevar la zona (metrics.shots.add_zones).
    `season_players` es la tabla de temporada del equipo con USO% (y Perfil).
    `shooting`: referencias de tiro de la liga (shooting_baseline). Sin ellas, se calculan con
    los jugadores del propio equipo.
    `turnovers`: (% de pérdidas con robo del equipo, % de la liga). Sin ese dato, la idea de
    presionar no se propone, porque no se sabe si sus pérdidas las provoca la presión.
    """
    n = len(league)
    facts = team_facts(team, league, average, spread)
    style, strengths, weaknesses, ideas = [], [], [], []

    for fact in facts:
        confidence = fact.confidence
        if confidence is None:
            continue
        if fact.key == "RITMO":
            pace = f"{number(round(fact.value, 1))} posesiones por 40 minutos"
            text = (
                f"Juega rápido: {pace} {_context(fact, n)}."
                if fact.z > 0
                else f"Juega lento: {pace} {_context(fact, n)}."
            )
            style.append(Insight(text, confidence, abs(fact.z)))
            continue
        metric = METRIC_BY_COLUMN[fact.key]
        value = metric.value.format(v=number(round(fact.value, 1)))
        if fact.z > 0:
            strengths.append(Insight(f"{metric.good}: {value} {_context(fact, n)}.", confidence,
                                     fact.z))  # fmt: skip
            if metric.idea_if_good:
                ideas.append(Insight(metric.idea_if_good, confidence, fact.z, metric.group))
        else:
            detail = ""
            if metric.column == "PER%" and turnovers is not None:
                detail = (
                    f" El {number(round(turnovers[0], 1))} % de sus pérdidas son con robo "
                    f"(liga {number(round(turnovers[1], 1))} %)."
                )
            weaknesses.append(
                Insight(
                    f"{metric.bad}: {value} {_context(fact, n)}.{detail}", confidence, -fact.z
                )  # fmt: skip
            )
            presses = metric.column == "PER%"
            if metric.idea_if_bad and (
                not presses or (turnovers is not None and turnovers[0] >= turnovers[1])
            ):
                ideas.append(Insight(metric.idea_if_bad, confidence, -fact.z, metric.group))

    shooting = shooting or shooting_baseline(season_players.assign(team=team).reset_index())
    _three_point_style(team_shots, league_shots, style, ideas)
    _zone_insights(team_shots, league_shots, strengths, weaknesses)
    players, player_ideas = _player_insights(season_players, shooting)
    ideas += player_ideas
    return TeamInsights(style, strengths, weaknesses, players, pick_ideas(ideas), facts=facts)


def _three_point_style(team_shots, league_shots, style, ideas) -> None:
    threes = team_shots[team_shots["value"] == 3]
    share = three_point_share(team_shots)
    league_share = three_point_share(league_shots)
    z_share = proportion_z(len(threes), len(team_shots), league_share / 100)
    confidence = label(z_share)
    if confidence is None:
        return
    league_threes = league_shots[league_shots["value"] == 3]
    league_accuracy = league_threes["made"].mean() if len(league_threes) else 0.0
    accuracy = threes["made"].mean() if len(threes) else 0.0
    if share >= league_share + THREE_SHARE_MARGIN:
        style.append(
            Insight(
                f"Vive del triple: el {number(round(share, 1))} % de sus tiros de campo son "
                f"triples (media de la liga {number(round(league_share, 1))} %), con un "
                f"{number(round(100 * accuracy, 1))} % de acierto (liga "
                f"{number(round(100 * league_accuracy, 1))} %).",
                confidence,
                abs(z_share),
            )
        )
        if accuracy >= league_accuracy:
            ideas.append(
                Insight(
                    "Defender la línea de triple: tira mucho de tres, con un acierto igual o "
                    "mayor que la media de la liga.",
                    confidence,
                    abs(z_share),
                )
            )
        else:
            ideas.append(
                Insight(
                    "Cerrar la zona antes que salir a todo: tira mucho de tres, pero con menos "
                    "acierto que la media de la liga.",
                    confidence,
                    abs(z_share),
                )
            )
    elif share <= league_share - THREE_SHARE_MARGIN:
        style.append(
            Insight(
                f"Juega por dentro: solo el {number(round(share, 1))} % de sus tiros son "
                f"triples (media de la liga {number(round(league_share, 1))} %).",
                confidence,
                abs(z_share),
            )
        )
        ideas.append(
            Insight(
                "Proteger la zona: su ataque busca el aro más que el triple.",
                confidence,
                abs(z_share),
            )  # fmt: skip
        )


def _zone_insights(team_shots, league_shots, strengths, weaknesses) -> None:
    league_zones = league_shots.groupby("zone")["made"].mean()
    for zone, zone_shots in team_shots.groupby("zone"):
        if len(zone_shots) < ZONE_MIN_ATTEMPTS:
            continue
        made = zone_shots["made"].sum()
        z = proportion_z(made, len(zone_shots), league_zones[zone])
        confidence = label(z)
        if confidence is None:
            continue
        pct = 100 * made / len(zone_shots)
        detail = (
            f"{ZONE_PHRASES[zone]}: {number(round(pct, 1))} % en {len(zone_shots)} tiros "
            f"(media de la liga {number(round(100 * league_zones[zone], 1))} %)."
        )
        target = strengths if z > 0 else weaknesses
        prefix = "Muy acertado" if z > 0 else "Poco acertado"
        target.append(Insight(f"{prefix} {detail}", confidence, abs(z)))


def _weight_label(attempts: float, k: float) -> str:
    """Confianza de un acierto encogido: alta si los datos del jugador pesan la mitad o más."""
    return "alta" if shrink_weight(attempts, k) >= 0.5 else "media"


def _player_insights(
    season: pd.DataFrame, shooting: ShootingBaseline
) -> tuple[list[Insight], list[Insight]]:
    regulars = season[
        (season["MIN/PJ"] >= PLAYER_MIN_MINUTES_PER_GAME) & (season["MIN"] >= PLAYER_MIN_MINUTES)
    ].copy()
    regulars["tsa"] = regulars["TCA"] + 0.44 * regulars["T1A"]
    regulars["ts_shrunk"] = [
        shrink(row["PTS"] / 2, row["tsa"], shooting.ts, shooting.k_ts)
        for _, row in regulars.iterrows()
    ]
    texts, ideas = [], []
    star = None
    if not regulars.empty and regulars["USO%"].max() >= STAR_USAGE:
        star = regulars["USO%"].idxmax()
        row = regulars.loc[star]
        confidence = "alta" if row["MIN"] >= STAR_MINUTES_HIGH else "media"
        texts.append(
            Insight(
                f"{display_name(star)} es su referencia en ataque: termina el "
                f"{number(row['USO%'])} % de las jugadas cuando está en pista "
                f"({number(row['PTS/PJ'])} puntos por partido, TS% del {number(row['TS%'])} %).",
                confidence,
                2.5,
            )
        )
        ideas.append(
            Insight(
                f"Su ataque pasa por {display_name(star)}: centrar la defensa en él.",
                confidence,
                2.5,
            )  # fmt: skip
        )
    volume = regulars[regulars["tsa"] >= PLAYER_MIN_SHOTS]
    league_ts = number(round(100 * shooting.ts, 1))
    for name, row in volume.sort_values("ts_shrunk", ascending=False).iterrows():
        if name != star and row["ts_shrunk"] >= shooting.ts + EFFICIENT_MARGIN:
            texts.append(
                Insight(
                    f"{display_name(name)} es muy eficiente: TS% del {number(row['TS%'])} % con "
                    f"{number(row['PTS/PJ'])} puntos por partido (liga {league_ts} %).",
                    _weight_label(row["tsa"], shooting.k_ts),
                    2.0,
                )
            )
    for name, row in volume.iterrows():
        if row["USO%"] >= WASTEFUL_USAGE and row["ts_shrunk"] <= shooting.ts - WASTEFUL_MARGIN:
            texts.append(
                Insight(
                    f"{display_name(name)} tira mucho con poco acierto: uso del "
                    f"{number(row['USO%'])} % y TS% del {number(row['TS%'])} % (liga "
                    f"{league_ts} %).",
                    _weight_label(row["tsa"], shooting.k_ts),
                    1.8,
                )
            )
    threes = season[
        (season["T3A"] >= SHOOTER_MIN_THREES) & (season["MIN"] >= PLAYER_MIN_MINUTES)
    ].copy()
    threes["shrunk"] = [
        shrink(row["T3M"], row["T3A"], shooting.three, shooting.k_three)
        for _, row in threes.iterrows()
    ]
    league_three = number(round(100 * shooting.three, 1))
    volume_shooters = 0
    for name, row in threes.sort_values("T3M", ascending=False).iterrows():
        confidence = _weight_label(row["T3A"], shooting.k_three)
        if row["shrunk"] >= shooting.three + SHOOTER_MARGIN:
            texts.append(
                Insight(
                    f"{display_name(name)} es peligroso desde el triple: {int(row['T3M'])}/"
                    f"{int(row['T3A'])} ({number(row['T3%'])} %; liga {league_three} %).",
                    confidence,
                    2.0,
                )
            )
            ideas.append(
                Insight(
                    f"No dejar tirar solo a {display_name(name)} desde fuera.", confidence, 2.0
                )  # fmt: skip
            )
        elif (
            volume_shooters < MAX_VOLUME_SHOOTERS
            and 40 * row["T3A"] / row["MIN"] >= VOLUME_THREES_PER_40
        ):
            volume_shooters += 1
            per_40 = number(round(40 * row["T3A"] / row["MIN"], 1))
            texts.append(
                Insight(
                    f"{display_name(name)} lanza mucho de tres: {per_40} triples por 40 minutos "
                    f"({int(row['T3M'])}/{int(row['T3A'])}, {number(row['T3%'])} %).",
                    "media",
                    1.5,
                )
            )
    return texts, ideas


def pick_ideas(ideas: list[Insight], limit: int = MAX_IDEAS) -> list[Insight]:
    """Las ideas con más confianza, sin repetir ni contradecirse, hasta `limit`."""
    chosen: list[Insight] = []
    for idea in sorted(ideas, key=lambda i: (i.confidence != "alta", -i.score)):
        if any(idea.text == c.text for c in chosen):
            continue
        if idea.group and any(
            frozenset({idea.group, c.group}) in CONFLICTS for c in chosen if c.group
        ):
            continue
        chosen.append(idea)
        if len(chosen) == limit:
            break
    return chosen


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
    for column, (label_, margin, higher_is_better, fmt) in FACTOR_LABELS.items():
        diff = own[column] - opp[column]
        if abs(diff) < margin:
            continue
        better = (diff > 0) == higher_is_better
        winner, loser = (team, rival) if better else (rival, team)
        a, b = (own[column], opp[column]) if better else (opp[column], own[column])
        texts.append(
            f"{display_name(winner)} fue claramente mejor en {label_}: "
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
