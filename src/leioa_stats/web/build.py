"""Genera la web estática en site/.

Páginas: la temporada del equipo, una por cada partido suyo y una por cada equipo de la liga
(scouting de rivales).
"""

import json
import shutil
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape
from plotly.offline import get_plotlyjs_version

from leioa_stats.download import TEAM_NAME, involves
from leioa_stats.format import display_name, number
from leioa_stats.metrics.advanced import (
    four_factors,
    games_summary,
    player_usage,
    ratings,
    team_advanced,
    team_games,
)
from leioa_stats.metrics.basic import add_shooting, player_season, team_season
from leioa_stats.metrics.insights import match_insights, team_insights
from leioa_stats.metrics.league import league_average, league_table, player_profiles, ranks
from leioa_stats.metrics.lineups import lineup_summary, player_on_off, stint_rows
from leioa_stats.metrics.shots import add_zones, zone_summary
from leioa_stats.parse import RAW_DIR, build_tables, iter_matches
from leioa_stats.validate import POINTS, validate_match
from leioa_stats.web import charts
from leioa_stats.web.glossary import ENTRIES, TERMS

SITE_DIR = Path("site")
HERE = Path(__file__).parent
TOP_LINEUPS = 10

TEAM_COLUMNS = ["PTS/PJ", "TC%", "T2%", "T3%", "T1%", "eFG%", "TS%", "RT/PJ", "RO/PJ",
                "RD/PJ", "AS/PJ", "PER/PJ", "REC/PJ", "TAP/PJ", "FP/PJ"]  # fmt: skip
PLAYER_COLUMNS = ["PJ", "TIT", "MIN/PJ", "PTS/PJ", "RT/PJ", "AS/PJ", "PER/PJ", "TC%", "T3M",
                  "T3A", "T3%", "T1%", "eFG%", "TS%", "USO%", "PTS/40"]  # fmt: skip
BOX_COLUMNS = ["Dorsal", "MIN", "PTS", "TC", "T3", "T1", "RO", "RD", "RT", "AS", "PER", "REC",
               "TAP", "FP", "FR", "VAL", "+/-"]  # fmt: skip
LINEUP_COLUMNS = ["MIN", "PTS", "PTS_opp", "+/-", "POSS", "ORtg", "DRtg", "NETO"]
SCOUTING_COLUMNS = ["PJ", "MIN/PJ", "PTS/PJ", "USO%", "TS%", "eFG%", "T3A", "T3%", "T1%", "RT/PJ",
                    "AS/PJ", "PER/PJ", "% cerca del aro", "% triples", "Perfil"]  # fmt: skip
LEAGUE_COLUMNS = ["PJ", "V", "D", "RITMO", "ORtg", "DRtg", "NETO", "eFG%", "PER%", "RO%", "TL/TC"]
FACTOR_ROWS = ["Ritmo", "Eficiencia (pts/100 pos.)", "eFG%", "PER%", "RO%", "TL/TC"]
# Jugadores con mapa de tiros propio en la página de cada equipo (los que más tiran).
TOP_SHOOTERS = 6


def slug(name: str) -> str:
    """'ELABORADOS NATURALES VALLE DE EGÜÉS' -> 'elaborados-naturales-valle-de-egues'."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return "-".join("".join(c if c.isalnum() else " " for c in ascii_name.lower()).split())


def table(df: pd.DataFrame, index_name: str = "") -> str:
    """Tabla HTML. Las celdas sin dato (por ejemplo, un % sin intentos) se muestran con '–'."""
    df = df.copy()
    # El nombre del índice va en la esquina de la cabecera, no en una segunda fila.
    df.index.name = None
    df.columns.name = index_name or None
    return df.to_html(classes="data", border=0, na_rep="–", float_format=number)


def lineup_table(lineups: pd.DataFrame, numbers: dict[str, str]) -> str:
    lineups = lineups.head(TOP_LINEUPS).copy()
    lineups.index = [
        "-".join(sorted((numbers.get(p, "?") for p in lineup.split(" | ")), key=_dorsal_key))
        for lineup in lineups.index
    ]
    return table(lineups[LINEUP_COLUMNS].rename(columns={"PTS_opp": "PTS rival"}), "Quinteto")


def _dorsal_key(number_: str) -> int:
    return int(number_) if number_.isdigit() else 999


def legend(numbers: dict[str, str]) -> list[tuple[str, str]]:
    return sorted(
        ((n, display_name(p)) for p, n in numbers.items()), key=lambda x: _dorsal_key(x[0])
    )


def match_date(match: dict, with_time: bool = True) -> str:
    """'2026-10-10 19:15:00' -> '10/10/2026 19:15'."""
    moment = datetime.fromisoformat(match["datetime"])
    return moment.strftime("%d/%m/%Y %H:%M" if with_time else "%d/%m/%Y")


def match_title(match: dict) -> str:
    return (
        f"{display_name(match['local'])} {match['local_score']}-{match['visitor_score']} "
        f"{display_name(match['visitor'])}"
    )


def box_score(players: pd.DataFrame, on_off: pd.DataFrame | None = None) -> pd.DataFrame:
    """Box score de un equipo en un partido. Con on_off añade el +/- reconstruido."""
    df = add_shooting(players.set_index("player"))
    on_court = on_off.index if on_off is not None else []
    df = df[(df["MIN"] > 0) | df.index.isin(on_court)]
    df["Dorsal"] = df["number"]
    df["TC"] = df["TCM"].astype(str) + "/" + df["TCA"].astype(str)
    df["T3"] = df["T3M"].astype(str) + "/" + df["T3A"].astype(str)
    df["T1"] = df["T1M"].astype(str) + "/" + df["T1A"].astype(str)
    columns = BOX_COLUMNS
    if on_off is not None:
        df["+/-"] = on_off["+/-"].reindex(df.index).fillna(0).astype(int)
    else:
        columns = [c for c in BOX_COLUMNS if c != "+/-"]
    df = df.sort_values("MIN", ascending=False)[columns]
    df.index = [display_name(p) for p in df.index]
    return df


def match_page(match, stats, moves, tables, stints, team_name) -> dict:
    """Datos de la página de un partido."""
    match_id = match["id"]
    teams = tables["teams"][tables["teams"]["match_id"] == match_id]
    players = tables["players"][tables["players"]["match_id"] == match_id]
    shots = tables["shots"][tables["shots"]["match_id"] == match_id]
    match_stints = stints[stints["match_id"] == match_id]
    games = team_games(teams)
    own_game = games[games["team"] == team_name]
    rival = own_game["opponent"].iloc[0]

    advanced = pd.DataFrame(
        {
            display_name(team_name): four_factors(own_game),
            display_name(rival): four_factors(own_game, "_opp"),
        }
    )
    rating = ratings(own_game)
    efficiency = pd.DataFrame(
        {
            display_name(team_name): [rating["ORtg"]],
            display_name(rival): [rating["DRtg"]],
        },
        index=["Eficiencia (pts/100 pos.)"],
    )
    quarters = pd.DataFrame(
        {
            display_name(t["name"]): [p["score"] for p in t["periods"]] + [t["data"]["score"]]
            for t in stats["teams"]
        },
        index=[
            *(f"C{i + 1}" if i < 4 else f"PR{i - 3}" for i in range(len(stats["periods"]))),
            "Total",
        ],
    ).T
    numbers = players[players["team"] == team_name].set_index("player")["number"].to_dict()
    issues = validate_match(stats, moves)
    home = next(t["name"] for t in stats["teams"] if t["teamIdIntern"] == stats["localId"])
    sign = 1 if home == team_name else -1
    score_diffs = [
        sign * (int(local) - int(visitor))
        for local, visitor in (m["score"].split("-") for m in moves if m["idMove"] in POINTS)
    ]
    return {
        "keys": match_insights(own_game, score_diffs, team_name, rival),
        "match": match,
        "title": match_title(match),
        "date": match_date(match),
        "rival": display_name(rival),
        "possessions": number(round(rating["POSS"], 1)),
        "pace": number(round(rating["RITMO"], 1)),
        "quarters": table(quarters),
        "factors": table(pd.concat([efficiency, advanced]).round(1)),
        "box": table(box_score(players[players["team"] == team_name], player_on_off(match_stints))),
        "box_rival": table(box_score(players[players["team"] != team_name])),
        "timeline": charts.to_html(charts.score_timeline(stats, moves, team_name)),
        "shots": charts.to_html(charts.shot_chart(shots[shots["team"] == team_name])),
        "shots_rival": charts.to_html(charts.shot_chart(shots[shots["team"] != team_name])),
        "zones": table(zone_summary(shots[shots["team"] == team_name]), "Zona"),
        "lineups": lineup_table(lineup_summary(match_stints), numbers),
        "legend": legend(numbers),
        "issues": [i for i in issues if i.severity != "info"],
    }


def season_page(matches, tables, stints, team_name, upcoming) -> dict:
    """Datos de la página de temporada. `matches` son solo los partidos del equipo."""
    players = tables["players"]
    shots = tables["shots"]
    own_players = players[players["team"] == team_name]
    numbers = own_players.groupby("player")["number"].last().to_dict()

    league = league_table(tables["teams"])
    next_match = upcoming[0] if upcoming else None
    next_rival = None
    if next_match:
        home = next_match["local"] == team_name
        next_rival = next_match["visitor"] if home else next_match["local"]
    league_rows = [
        {
            "name": display_name(name),
            "slug": slug(name),
            "own": name == team_name,
            "next": name == next_rival,
            "values": [number(row[c]) for c in LEAGUE_COLUMNS],
        }
        for name, row in league.iterrows()
    ]

    team = team_season(tables["teams"], team_name)
    team.index = [display_name(i) for i in team.index]
    full_season = (
        player_season(players, team_name)
        .join(player_usage(players, tables["teams"], team_name))
        .join(player_profiles(players, shots, team_name).drop(columns="TCA"))
    )
    insights = team_insights(
        team_name,
        league,
        league_average(tables["teams"]),
        full_season,
        shots[shots["team"] == team_name],
        shots,
    )
    season_players = full_season[PLAYER_COLUMNS]
    season_players.index = [display_name(p) for p in season_players.index]
    on_off = player_on_off(stints)
    on_off.index = [display_name(p) for p in on_off.index]
    advanced = team_advanced(tables["teams"], team_name)
    advanced.columns = [display_name(c) for c in advanced.columns]

    per_game = games_summary(tables["teams"], team_name)
    games = []
    for match, stats, moves in matches:
        row = per_game.loc[
            (match["round"], match["visitor"] if match["local"] == team_name else match["local"])
        ]
        won = (match["local_score"] > match["visitor_score"]) == (match["local"] == team_name)
        issues = [i for i in validate_match(stats, moves) if i.severity != "info"]
        games.append(
            {
                "match": match,
                "title": match_title(match),
                "won": won,
                "date": match_date(match, with_time=False),
                "pace": number(row["RITMO"]),
                "ortg": number(row["ORtg"]),
                "drtg": number(row["DRtg"]),
                "net": number(row["NETO"]),
                "issues": len(issues),
            }
        )
    incomplete = stints.loc[stints["size"] != 5, "seconds"].sum() / 60
    own_ids = {match["id"] for match, _, _ in matches}
    rival_shots = shots[shots["match_id"].isin(own_ids) & (shots["team"] != team_name)]
    return {
        "insights": insights,
        "games": games,
        "wins": sum(g["won"] for g in games),
        "losses": sum(not g["won"] for g in games),
        "team": table(team[TEAM_COLUMNS]),
        "advanced": table(advanced),
        "players": table(season_players, "Jugador"),
        "on_off": table(on_off, "Jugador"),
        "lineups": lineup_table(lineup_summary(stints), numbers),
        "lineups_incomplete": number(round(incomplete, 1)) if incomplete else None,
        "legend": legend(numbers),
        "shots": charts.to_html(charts.shot_chart(shots[shots["team"] == team_name])),
        "zones": table(zone_summary(shots[shots["team"] == team_name]), "Zona"),
        "zones_rivals": table(zone_summary(rival_shots), "Zona"),
        "issues_total": sum(g["issues"] for g in games),
        "next_match": next_match,
        "next_date": match_date(next_match) if next_match else None,
        "next_home": next_match is not None and next_match["local"] == team_name,
        "next_rival": display_name(next_rival) if next_rival else None,
        "next_rival_slug": slug(next_rival) if next_rival else None,
        "league_columns": LEAGUE_COLUMNS,
        "league_rows": league_rows,
    }


def team_page(team_name, all_matches, tables, stints, league, average, own_team) -> dict:
    """Datos de la página de scouting de un equipo de la liga."""
    players, shots = tables["players"], tables["shots"]
    team_shots = shots[shots["team"] == team_name]
    row = league.loc[team_name]
    factors = pd.DataFrame(
        {
            display_name(team_name): [
                row["RITMO"], row["ORtg"], row["eFG%"], row["PER%"], row["RO%"], row["TL/TC"],
            ],
            "Media de la liga": [
                average["RITMO"], average["ORtg"], average["eFG%"], average["PER%"],
                average["RO%"], average["TL/TC"],
            ],
            "Permite a sus rivales": [
                row["RITMO"], row["DRtg"], row["eFG% rival"], row["PER% rival"],
                row["RO% rival"], row["TL/TC rival"],
            ],
        },
        index=FACTOR_ROWS,
    )  # fmt: skip
    season = (
        player_season(players, team_name)
        .join(player_usage(players, tables["teams"], team_name))
        .join(player_profiles(players, shots, team_name).drop(columns="TCA"))
    )
    insights = team_insights(team_name, league, average, season, team_shots, shots)
    numbers = players[players["team"] == team_name].groupby("player")["number"].last().to_dict()
    player_charts = []
    for player, info in season.sort_values("TCA", ascending=False).head(TOP_SHOOTERS).iterrows():
        player_shots = team_shots[team_shots["player"] == player]
        if player_shots.empty:
            continue
        made = int(player_shots["made"].sum())
        profile = info["Perfil"].lower()
        player_charts.append(
            {
                "name": display_name(player),
                "number": numbers.get(player, ""),
                "summary": f"{made}/{len(player_shots)} tiros de campo · perfil {profile}",
                "chart": charts.to_html(charts.shot_chart(player_shots, height=420)),
                "zones": table(zone_summary(player_shots), "Zona"),
            }
        )
    season = season[SCOUTING_COLUMNS]
    season.index = [display_name(p) for p in season.index]
    results = []
    for match, _, _ in all_matches:
        if not involves(match, team_name):
            continue
        home = match["local"] == team_name
        own = match["local_score"] if home else match["visitor_score"]
        other = match["visitor_score"] if home else match["local_score"]
        results.append(
            {
                "round": match["round"],
                "rival": display_name(match["visitor"] if home else match["local"]),
                "where": "Casa" if home else "Fuera",
                "score": f"{own}-{other}",
                "won": own > other,
                "link": f"../partidos/{match['id']}.html" if involves(match, own_team) else None,
            }
        )
    return {
        "insights": insights,
        "name": display_name(team_name),
        "is_own": team_name == own_team,
        "record": f"{int(row['V'])}-{int(row['D'])}",
        "ranks": ranks(league, team_name),
        "n_teams": len(league),
        "factors": table(factors.round(1)),
        "players": table(season, "Jugador"),
        "shots": charts.to_html(charts.shot_chart(team_shots)),
        "zones": table(zone_summary(team_shots), "Zona"),
        "player_charts": player_charts,
        "lineups": lineup_table(lineup_summary(stints), numbers),
        "legend": legend(numbers),
        "results": results,
    }


def build_site(
    raw_dir: Path = RAW_DIR, out_dir: Path = SITE_DIR, team_name: str = TEAM_NAME
) -> list[Path]:
    """Genera la web y devuelve las páginas creadas."""
    all_matches = list(iter_matches(raw_dir))
    own_matches = [m for m in all_matches if involves(m[0], team_name)]
    upcoming_file = raw_dir / "upcoming.json"
    upcoming = (
        json.loads(upcoming_file.read_text(encoding="utf-8")) if upcoming_file.exists() else []
    )
    tables = build_tables(raw_dir)
    tables["shots"] = add_zones(tables["shots"])
    league = league_table(tables["teams"])
    average = league_average(tables["teams"])
    stints = {
        team: pd.DataFrame(
            [row for m in all_matches if involves(m[0], team) for row in stint_rows(*m, team)]
        )
        for team in league.index
    }

    env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape())
    common = {
        "team_name": display_name(team_name),
        "own_slug": slug(team_name),
        "plotly_url": f"https://cdn.plot.ly/plotly-{get_plotlyjs_version()}.min.js",
        "generated": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "n_games": len(own_matches),
        "n_league_games": len(all_matches),
        "glossary": ENTRIES,
        # Dentro de un <script>, "</" cerraría la etiqueta antes de tiempo.
        "glossary_json": json.dumps(TERMS, ensure_ascii=False).replace("</", "<\\/"),
    }
    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "partidos").mkdir(parents=True)
    (out_dir / "equipos").mkdir()
    for static_file in ("style.css", "glossary.js"):
        shutil.copy(HERE / "static" / static_file, out_dir / static_file)

    pages: list[Path] = []

    def render(path: Path, template: str, root: str, **context) -> None:
        html = env.get_template(template).render(**common, root=root, **context)
        path.write_text(html, encoding="utf-8")
        pages.append(path)

    render(
        out_dir / "index.html",
        "season.html.j2",
        "",
        **season_page(own_matches, tables, stints[team_name], team_name, upcoming),
    )
    for match, stats, moves in own_matches:
        render(
            out_dir / "partidos" / f"{match['id']}.html",
            "match.html.j2",
            "../",
            **match_page(match, stats, moves, tables, stints[team_name], team_name),
        )
    for team in league.index:
        render(
            out_dir / "equipos" / f"{slug(team)}.html",
            "team.html.j2",
            "../",
            **team_page(team, all_matches, tables, stints[team], league, average, team_name),
        )
    return pages
