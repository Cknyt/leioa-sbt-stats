"""Validación de los datos de cada partido: ¿cuadra el jugada a jugada con el box score?

Uso:
    uv run python -m leioa_stats.validate

Cada incidencia lleva una gravedad:
- "error": los datos se contradicen y afectan a las métricas.
- "aviso": probable error de anotación en la mesa; las métricas se ven poco afectadas.
- "info": diferencia esperada (por ejemplo, rebotes de equipo), no es un error.
"""

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

RAW_DIR = Path("data/raw")

# Códigos de jugada (idMove) del jugada a jugada.
FT_MADE, TWO_MADE, THREE_MADE = 92, 93, 94
FT_MISSED, TWO_MISSED, THREE_MISSED = 96, 97, 98
OFF_REBOUND, BLOCK, STEAL, DEF_REBOUND = 101, 102, 103, 104
BLOCK_RECEIVED, TURNOVER, ASSIST, FOUL_RECEIVED = 105, 106, 107, 110
SUB_IN, TIMEOUT, SUB_OUT, PERIOD_END = 112, 113, 115, 116
# Un mate es una canasta de 2 con su propio código.
DUNK = 100
# Jugada -> puntos que suma.
POINTS = {FT_MADE: 1, TWO_MADE: 2, DUNK: 2, THREE_MADE: 3}

NON_FOUL_MOVES = {
    FT_MADE, TWO_MADE, DUNK, THREE_MADE, FT_MISSED, TWO_MISSED, THREE_MISSED,
    OFF_REBOUND, BLOCK, STEAL, DEF_REBOUND, BLOCK_RECEIVED, TURNOVER, ASSIST,
    FOUL_RECEIVED, SUB_IN, TIMEOUT, SUB_OUT, PERIOD_END,
}  # fmt: skip
# Faltas vistas hasta ahora: en ataque (109), personal sin tiros, con 1, 2 o 3 tiros libres
# (159-162), antideportiva (166), técnica compensada (173), descalificante (200), técnica (537),
# técnica al entrenador (540), técnica al banquillo (544) y dos sin nombre en la web (565, 571).
KNOWN_FOUL_MOVES = {109, 159, 160, 161, 162, 166, 173, 200, 537, 540, 544, 565, 571}

SHOT_POINT_KEYS = [
    "shootingOfTwoSuccessfulPoint",
    "shootingOfTwoFailedPoint",
    "shootingOfThreeSuccessfulPoint",
    "shootingOfThreeFailedPoint",
]

# Estadística -> (nombre en el box score, nombre para mostrar).
BOX_FIELDS = {
    "PTS": ("score", "puntos"),
    "T1M": ("shotsOfOneSuccessful", "tiros libres anotados"),
    "T1A": ("shotsOfOneAttempted", "tiros libres intentados"),
    "T2M": ("shotsOfTwoSuccessful", "tiros de 2 anotados"),
    "T2A": ("shotsOfTwoAttempted", "tiros de 2 intentados"),
    "T3M": ("shotsOfThreeSuccessful", "tiros de 3 anotados"),
    "T3A": ("shotsOfThreeAttempted", "tiros de 3 intentados"),
    "RO": ("offensiveRebound", "rebotes ofensivos"),
    "RD": ("defensiveRebound", "rebotes defensivos"),
    "AS": ("assists", "asistencias"),
    "PER": ("lost", "pérdidas"),
    "REC": ("steals", "recuperaciones"),
    "TAP": ("block", "tapones"),
    "FP": ("faults", "faltas personales"),
}
# Estadísticas que se pueden anotar "de equipo", sin jugador.
TEAM_STATS = {"RO", "RD", "PER", "REC"}


@dataclass
class Issue:
    severity: str
    check: str
    team: str | None
    detail: str


def is_foul(move: dict) -> bool:
    return move["idMove"] not in NON_FOUL_MOVES


def clock(move: dict) -> str:
    period = move["period"]
    name = f"{period}º cuarto" if period <= 4 else f"prórroga {period - 4}"
    return f"{name} {move['min']}:{move['sec']:02d}"


def pbp_player_totals(moves: list[dict], team_id: int) -> dict[str, int]:
    """Totales del equipo según el jugada a jugada, contando solo acciones de jugadores."""
    player_moves = [m for m in moves if m["idTeam"] == team_id and not m["teamAction"]]
    c = Counter(m["idMove"] for m in player_moves)
    two_made = c[TWO_MADE] + c[DUNK]
    return {
        "PTS": sum(points * c[move] for move, points in POINTS.items()),
        "T1M": c[FT_MADE],
        "T1A": c[FT_MADE] + c[FT_MISSED],
        "T2M": two_made,
        "T2A": two_made + c[TWO_MISSED],
        "T3M": c[THREE_MADE],
        "T3A": c[THREE_MADE] + c[THREE_MISSED],
        "RO": c[OFF_REBOUND],
        "RD": c[DEF_REBOUND],
        "AS": c[ASSIST],
        "PER": c[TURNOVER],
        "REC": c[STEAL],
        "TAP": c[BLOCK],
        "FP": sum(1 for m in player_moves if is_foul(m)),
    }


def check_box_totals(stats: dict, moves: list[dict]) -> list[Issue]:
    """Compara jugada a jugada, total del equipo y suma de los jugadores."""
    issues = []
    for team in stats["teams"]:
        name = team["name"]
        pbp = pbp_player_totals(moves, team["teamIdIntern"])
        team_fouls_pbp = sum(
            1
            for m in moves
            if m["idTeam"] == team["teamIdIntern"] and m["teamAction"] and is_foul(m)
        )
        for stat, (field, label) in BOX_FIELDS.items():
            team_total = team["data"][field]
            players = sum(p["data"][field] for p in team["players"])
            if pbp[stat] != players:
                issues.append(
                    Issue(
                        "error",
                        "totales",
                        name,
                        f"{label}: {pbp[stat]} en el jugada a jugada y {players} "
                        "sumando los jugadores",
                    )
                )
            extra = team_total - players
            if stat == "FP":
                # Las técnicas al entrenador o al banquillo cuentan para el equipo.
                missing = extra - team_fouls_pbp
                if missing:
                    issues.append(
                        Issue(
                            "aviso",
                            "totales",
                            name,
                            f"faltas: el total del equipo ({team_total}) no cuadra con el "
                            f"jugada a jugada ({players + team_fouls_pbp}); "
                            f"diferencia de {missing}",
                        )
                    )
            elif stat in TEAM_STATS and extra > 0:
                issues.append(
                    Issue("info", "totales", name, f"{label} de equipo (sin jugador): {extra}")
                )
            elif extra != 0:
                issues.append(
                    Issue(
                        "error",
                        "totales",
                        name,
                        f"{label}: {team_total} en el total del equipo y {players} "
                        "sumando los jugadores",
                    )
                )
    return issues


def check_unknown_moves(moves: list[dict]) -> list[Issue]:
    """Códigos de jugada que no conocemos: podrían ser faltas mal contadas."""
    unknown = Counter(
        (m["idMove"], m["move"])
        for m in moves
        if is_foul(m) and m["idMove"] not in KNOWN_FOUL_MOVES
    )
    return [
        Issue("aviso", "tipos de jugada", None, f"código {code} desconocido ({name!r}), {n} veces")
        for (code, name), n in unknown.items()
    ]


def check_blocks(stats: dict, moves: list[dict]) -> list[Issue]:
    """Cada tapón de un equipo debe ser un 'tapón recibido' del otro."""
    issues = []
    team_a, team_b = stats["teams"]
    for blocker, shooter in ((team_a, team_b), (team_b, team_a)):
        blocks = sum(
            1 for m in moves if m["idTeam"] == blocker["teamIdIntern"] and m["idMove"] == BLOCK
        )
        received = sum(
            1
            for m in moves
            if m["idTeam"] == shooter["teamIdIntern"] and m["idMove"] == BLOCK_RECEIVED
        )
        if blocks != received:
            issues.append(
                Issue(
                    "aviso",
                    "tapones",
                    blocker["name"],
                    f"{blocks} tapones, pero el rival tiene {received} tapones recibidos",
                )
            )
    return issues


def check_score(stats: dict, moves: list[dict]) -> list[Issue]:
    """El marcador de cada canasta y el final deben coincidir con lo acumulado."""
    local, visitor = 0, 0
    mismatches = []
    for m in moves:
        if m["idMove"] not in POINTS:
            continue
        if m["idTeam"] == stats["localId"]:
            local += POINTS[m["idMove"]]
        else:
            visitor += POINTS[m["idMove"]]
        if m["score"] != f"{local}-{visitor}":
            mismatches.append((m, f"{local}-{visitor}"))
    issues = []
    if mismatches:
        first, expected = mismatches[0]
        issues.append(
            Issue(
                "error",
                "marcador",
                None,
                f"{len(mismatches)} canastas con un marcador que no coincide con lo acumulado "
                f"(la primera, {clock(first)}: anotado {first['score']}, acumulado {expected})",
            )
        )
    teams = {t["teamIdIntern"]: t for t in stats["teams"]}
    final = f"{teams[stats['localId']]['data']['score']}-{teams[stats['visitId']]['data']['score']}"
    if f"{local}-{visitor}" != final:
        issues.append(
            Issue(
                "error",
                "marcador",
                None,
                f"el jugada a jugada termina {local}-{visitor} y el box score {final}",
            )
        )
    return issues


def check_minutes(stats: dict) -> list[Issue]:
    """Cinco titulares y 5 jugadores en pista todo el partido."""
    issues = []
    expected = 5 * sum(stats["periodDurationList"])
    for team in stats["teams"]:
        starters = sum(p["starting"] for p in team["players"])
        if starters != 5:
            issues.append(Issue("error", "minutos", team["name"], f"{starters} titulares"))
        played = sum(p["timePlayed"] for p in team["players"])
        if played != expected:
            issues.append(
                Issue(
                    "aviso",
                    "minutos",
                    team["name"],
                    f"los jugadores suman {played} minutos y deberían ser {expected} "
                    "(los minutos de cada jugador vienen redondeados)",
                )
            )
    return issues


def check_shot_coordinates(stats: dict, moves: list[dict]) -> list[Issue]:
    """Todos los tiros de campo deben tener coordenadas enlazadas con su jugada."""
    issues = []
    uuids = {m["eventUuid"] for m in moves}
    for team in stats["teams"]:
        attempts = team["data"]["shotsOfTwoAttempted"] + team["data"]["shotsOfThreeAttempted"]
        points = [
            p for period in team["periods"] for k in SHOT_POINT_KEYS for p in period.get(k, [])
        ]
        if len(points) != attempts:
            issues.append(
                Issue(
                    "aviso",
                    "mapa de tiros",
                    team["name"],
                    f"{len(points)} tiros con coordenadas de {attempts} tiros de campo",
                )
            )
        unlinked = sum(p["eventUuid"] not in uuids for p in points)
        if unlinked:
            issues.append(
                Issue(
                    "aviso",
                    "mapa de tiros",
                    team["name"],
                    f"{unlinked} tiros con coordenadas que no aparecen en el jugada a jugada",
                )
            )
    return issues


def check_lineups(stats: dict, moves: list[dict]) -> list[Issue]:
    """Reconstruye quién está en pista y busca acciones de jugadores que no deberían estar."""
    issues = []
    for team in stats["teams"]:
        team_id = team["teamIdIntern"]
        on_court = {p["actorId"] for p in team["players"] if p["starting"]}
        off_court_actions: dict[str, list[dict]] = {}
        wrong_size = []
        team_moves = [m for m in moves if m["idTeam"] == team_id]
        for i, m in enumerate(team_moves):
            if m["idMove"] == SUB_IN:
                on_court.add(m["actorId"])
                continue
            if m["idMove"] == SUB_OUT:
                on_court.discard(m["actorId"])
                continue
            if m["teamAction"] or m["idMove"] in (TIMEOUT, PERIOD_END):
                continue
            if m["actorId"] not in on_court:
                off_court_actions.setdefault(m["actorName"], []).append(m)
            # Mientras se hacen varios cambios seguidos puede haber 4 o 6 en pista.
            next_is_sub = i + 1 < len(team_moves) and team_moves[i + 1]["idMove"] in (
                SUB_IN,
                SUB_OUT,
            )
            if len(on_court) != 5 and not next_is_sub:
                wrong_size.append((m, len(on_court)))
        for player, actions in off_court_actions.items():
            issues.append(
                Issue(
                    "aviso",
                    "quintetos",
                    team["name"],
                    f"{player} hace {len(actions)} acciones sin constar en pista "
                    f"({clock(actions[0])} - {clock(actions[-1])}): probable cambio no anotado",
                )
            )
        if wrong_size:
            m, size = wrong_size[0]
            issues.append(
                Issue(
                    "aviso",
                    "quintetos",
                    team["name"],
                    f"{len(wrong_size)} jugadas con un número de jugadores en pista distinto de 5 "
                    f"(la primera, {clock(m)}: {size} en pista)",
                )
            )
    return issues


def check_chronology(moves: list[dict]) -> list[Issue]:
    """Las jugadas deben venir en orden: por cuarto y con el reloj descendiendo."""
    keys = [(m["period"], -(m["min"] * 60 + m["sec"])) for m in moves]
    out_of_order = sum(a > b for a, b in zip(keys, keys[1:], strict=False))
    if out_of_order:
        return [Issue("aviso", "orden", None, f"{out_of_order} jugadas fuera de orden")]
    return []


def validate_match(stats: dict, moves: list[dict]) -> list[Issue]:
    return [
        *check_score(stats, moves),
        *check_box_totals(stats, moves),
        *check_unknown_moves(moves),
        *check_blocks(stats, moves),
        *check_minutes(stats),
        *check_shot_coordinates(stats, moves),
        *check_lineups(stats, moves),
        *check_chronology(moves),
    ]


def load_match(match_dir: Path) -> tuple[dict, list[dict]]:
    stats = json.loads((match_dir / "stats.json").read_text(encoding="utf-8"))
    moves = json.loads((match_dir / "moves.json").read_text(encoding="utf-8"))
    return stats, moves


SEVERITY_ORDER = {"error": 0, "aviso": 1, "info": 2}


def main() -> None:
    matches = json.loads((RAW_DIR / "matches.json").read_text(encoding="utf-8"))
    totals = Counter()
    for match in matches:
        issues = validate_match(*load_match(RAW_DIR / "matches" / match["id"]))
        totals.update(i.severity for i in issues)
        print(
            f"\nJ{match['round']} {match['local']} {match['local_score']}-"
            f"{match['visitor_score']} {match['visitor']} (partido {match['id']})"
        )
        if not issues:
            print("  sin incidencias")
        for issue in sorted(issues, key=lambda i: SEVERITY_ORDER[i.severity]):
            team = f"{issue.team}: " if issue.team else ""
            print(f"  [{issue.severity}] {issue.check} - {team}{issue.detail}")
    print(
        f"\nTotal: {totals['error']} errores, {totals['aviso']} avisos, "
        f"{totals['info']} informativas en {len(matches)} partidos"
    )


if __name__ == "__main__":
    main()
