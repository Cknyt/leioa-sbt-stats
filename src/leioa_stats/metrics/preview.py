"""Informe prepartido: cruza lo que hace bien (o mal) un equipo con lo que concede el rival.

Cada cruce enfrenta una cifra de ataque de un equipo con la misma cifra que permite la defensa
del otro. Por ejemplo, nuestro eFG% con el eFG% que concede su defensa.

Valor esperado en el partido (modelo aditivo, el más sencillo):
    esperado = valor del atacante + valor que permite el defensor - media de la liga.
Si atacamos con un eFG% de 48 (liga 45) contra una defensa que permite 50, se espera un
48 + 50 - 45 = 53.

Confianza del cruce: el error estándar de la suma es √(ee_atacante² + ee_defensor²), así que
    z = (desviación del atacante + desviación del defensor) / √(ee_atacante² + ee_defensor²),
con signo positivo cuando favorece a nuestro equipo. Mismos umbrales que el resto de la web
(metrics/confidence.py): |z| ≥ 1,5 → media, |z| ≥ 2 → alta.

Veredicto de cada cruce:
- Choque de fuerzas: el ataque y la defensa son buenos a la vez (cada uno con z ≥ 1,5 por
  separado). Ninguno de los dos tiene ventaja clara: se avisa.
- Ventaja: z ≥ 1,5 a nuestro favor (en ataque, o en defensa si su ataque es flojo donde
  nuestra defensa es buena).
- Desventaja: z ≤ -1,5. "No insistir" si es en ataque; "qué nos pueden hacer" si es en defensa.
- Sin veredicto: puede ser azar. No se dice nada.

Límites:
- Con menos de MIN_GAMES partidos de alguno de los dos equipos no se da ningún veredicto: la
  variabilidad se toma por defecto y una sola noche de tiro lo decide todo.
- Si los dos equipos ya se han enfrentado, ese partido cuenta en los dos lados del cruce, y
  la confianza sale algo más alta de lo que debería.

La revisión pospartido calcula este mismo informe solo con las jornadas anteriores al
partido y lo compara con lo que pasó.
"""

import math
from dataclasses import dataclass, replace

import pandas as pd

from leioa_stats.format import number
from leioa_stats.metrics.confidence import Z_MEDIUM, label
from leioa_stats.metrics.insights import Fact

# (cifra de ataque, cifra que permite la defensa, más es mejor para el atacante, nombre).
PAIRS = [
    ("eFG%", "eFG% rival", True, "el tiro (eFG%)"),
    ("PER%", "PER% rival", False, "las pérdidas (por 100 posesiones)"),
    ("RO%", "RO% rival", True, "el rebote ofensivo (%)"),
    ("TL/TC", "TL/TC rival", True, "los tiros libres (anotados por 100 tiros de campo)"),
    ("T3%", "T3% rival", True, "el acierto en triples"),
    ("Aro%", "Aro% rival", True, "el acierto cerca del aro"),
]
VERDICTS = ("choque", "ventaja", "desventaja")
MIN_GAMES = 3


@dataclass(frozen=True)
class Matchup:
    key: str  # cifra de ataque ("eFG%"...)
    label: str
    side: str  # "ataque" (nuestro ataque contra su defensa) o "defensa" (su ataque)
    attacker: Fact
    defender: Fact
    average: float
    expected: float
    z: float  # positiva = favorece a nuestro equipo
    verdict: str  # "choque", "ventaja", "desventaja" o ""

    @property
    def confidence(self) -> str | None:
        return "media" if self.verdict == "choque" else label(self.z)


def shot_facts(team: str, shots: pd.DataFrame) -> list[Fact]:
    """Acierto en triples y cerca del aro de un equipo y lo que permite su defensa.

    `shots` lleva la zona (metrics/shots.add_zones). Error estándar de una proporción.
    """
    facts = []
    threes = shots[shots["value"] == 3]
    rim = shots[shots["zone"] == "Cerca del aro"]
    for key, subset in (("T3%", threes), ("Aro%", rim)):
        league_rate = subset["made"].mean() if len(subset) else float("nan")
        for suffix, rows in (("", subset["team"] == team), (" rival", subset["opponent"] == team)):
            made, attempts = subset.loc[rows, "made"].sum(), int(rows.sum())
            rate = made / attempts if attempts else float("nan")
            se = math.sqrt(league_rate * (1 - league_rate) / attempts) if attempts else math.nan
            good = (rate - league_rate) / se if attempts else math.nan
            facts.append(
                Fact(
                    key=key + suffix,
                    subject=team,
                    value=100 * rate,
                    average=100 * league_rate,
                    z=good if suffix == "" else -good,
                    n=attempts,
                    se=100 * se,
                )
            )
    return facts


def _matchup(key, allowed, higher, name, side, attacker, defender) -> Matchup:
    average = attacker.average
    deviation = (attacker.value - average) + (defender.value - average)
    se = math.sqrt(attacker.se**2 + defender.se**2)
    z_attack = deviation / se if se > 0 else math.nan
    if not higher:
        z_attack = -z_attack
    z = z_attack if side == "ataque" else -z_attack
    if attacker.z >= Z_MEDIUM and defender.z >= Z_MEDIUM:
        verdict = "choque"
    elif z >= Z_MEDIUM:
        verdict = "ventaja"
    elif z <= -Z_MEDIUM:
        verdict = "desventaja"
    else:
        verdict = ""
    return Matchup(
        key=key,
        label=name,
        side=side,
        attacker=attacker,
        defender=defender,
        average=average,
        expected=attacker.value + defender.value - average,
        z=z,
        verdict=verdict,
    )


def matchups(own: list[Fact], rival: list[Fact]) -> list[Matchup]:
    """Cruces de nuestro ataque con su defensa y de su ataque con nuestra defensa."""
    own_by_key = {f.key: f for f in own}
    rival_by_key = {f.key: f for f in rival}
    result = []
    for key, allowed, higher, name in PAIRS:
        if key in own_by_key and allowed in rival_by_key:
            result.append(
                _matchup(
                    key, allowed, higher, name, "ataque", own_by_key[key], rival_by_key[allowed]
                )  # fmt: skip
            )
        if key in rival_by_key and allowed in own_by_key:
            result.append(
                _matchup(
                    key, allowed, higher, name, "defensa", rival_by_key[key], own_by_key[allowed]
                )  # fmt: skip
            )
    return result


def describe(m: Matchup, own_name: str, rival_name: str) -> str:
    """Frase de un cruce, con los valores de los dos equipos y el esperado."""
    attacker, defender = (own_name, rival_name) if m.side == "ataque" else (rival_name, own_name)
    values = (
        f"{attacker} en ataque {number(round(m.attacker.value, 1))}, {defender} permite "
        f"{number(round(m.defender.value, 1))} (liga {number(round(m.average, 1))}); "
        f"esperable {number(round(m.expected, 1))}"
    )
    if m.verdict == "choque":
        return f"Choque de fuerzas en {m.label}: {values}. Los dos son buenos ahí."
    if m.side == "ataque":
        head = "Hacer daño con" if m.verdict == "ventaja" else "No insistir en"
    else:
        head = "Su ataque tiene poco margen en" if m.verdict == "ventaja" else "Vigilar"
    return f"{head} {m.label}: {values}."


def key_matchups(items: list[Matchup], limit: int = 3) -> list[Matchup]:
    """Las claves: los cruces con veredicto, de más a menos claros."""
    with_verdict = [m for m in items if m.verdict]
    return sorted(with_verdict, key=lambda m: -abs(m.z))[:limit]


def actual_values(
    own_game: pd.DataFrame | pd.Series, own_shots: pd.DataFrame, rival_shots: pd.DataFrame
):
    """Valores reales de un partido para cada cruce: {(cifra, lado): valor}."""
    from leioa_stats.metrics.advanced import four_factors

    game = own_game.to_frame().T.infer_objects() if isinstance(own_game, pd.Series) else own_game
    own, opp = four_factors(game), four_factors(game, "_opp")
    values = {}
    for key in ("eFG%", "PER%", "RO%", "TL/TC"):
        values[(key, "ataque")] = own[key]
        values[(key, "defensa")] = opp[key]
    for side, shots in (("ataque", own_shots), ("defensa", rival_shots)):
        threes = shots[shots["value"] == 3]
        rim = shots[shots["zone"] == "Cerca del aro"]
        values[("T3%", side)] = 100 * threes["made"].mean() if len(threes) else float("nan")
        values[("Aro%", side)] = 100 * rim["made"].mean() if len(rim) else float("nan")
    return values


def fulfilled(m: Matchup, actual: float) -> bool | None:
    """¿Se cumplió el veredicto? El valor real quedó del lado previsto respecto a la media."""
    if not m.verdict or m.verdict == "choque" or pd.isna(actual):
        return None
    higher = next(h for k, _, h, _ in PAIRS if k == m.key)
    good_for_attacker = (actual > m.average) == higher
    good_for_us = good_for_attacker if m.side == "ataque" else not good_for_attacker
    return good_for_us == (m.verdict == "ventaja")


def team_matchups(
    teams: pd.DataFrame,
    shots: pd.DataFrame,
    own: str,
    rival: str,
    before_round: int | None = None,
) -> list[Matchup]:
    """Cruces entre dos equipos con las jornadas jugadas (o solo las anteriores a una dada).

    `shots` lleva la zona (metrics/shots.add_zones). Devuelve [] si alguno de los dos equipos
    aún no ha jugado.
    """
    from leioa_stats.metrics.advanced import team_games
    from leioa_stats.metrics.confidence import league_spread
    from leioa_stats.metrics.insights import team_facts
    from leioa_stats.metrics.league import league_average, league_table

    if before_round is not None:
        teams = teams[teams["round"] < before_round]
        shots = shots[shots["round"] < before_round]
    if teams.empty or not {own, rival} <= set(teams["team"]):
        return []
    league = league_table(teams)
    average = league_average(teams)
    spread = league_spread(team_games(teams))

    def facts(team: str) -> list[Fact]:
        return team_facts(team, league, average, spread) + shot_facts(team, shots)

    items = matchups(facts(own), facts(rival))
    if min(league.loc[own, "PJ"], league.loc[rival, "PJ"]) < MIN_GAMES:
        items = [replace(m, verdict="") for m in items]
    return items
