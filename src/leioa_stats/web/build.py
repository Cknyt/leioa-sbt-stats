"""Genera la web estática en site/: una página de temporada y una por partido."""

import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape
from plotly.offline import get_plotlyjs_version

from leioa_stats.download import TEAM_NAME
from leioa_stats.metrics.advanced import (
    four_factors,
    games_summary,
    player_usage,
    ratings,
    team_advanced,
    team_games,
)
from leioa_stats.metrics.basic import add_shooting, player_season, team_season
from leioa_stats.metrics.lineups import lineup_summary, player_on_off, stint_rows
from leioa_stats.metrics.shots import add_zones, zone_summary
from leioa_stats.parse import RAW_DIR, build_tables, iter_matches
from leioa_stats.validate import validate_match
from leioa_stats.web import charts

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


def display_name(name: str) -> str:
    """'IÑIGO CARNEROS VILLAR' -> 'Iñigo Carneros Villar', 'LEIOA SBT' -> 'Leioa SBT'.

    Las siglas (palabras sin vocales o con números, como SBT, CB o 1DM) se dejan en mayúsculas.
    """

    def word(w: str) -> str:
        is_acronym = not any(c in "AEIOUÁÉÍÓÚÜ" for c in w) or any(c.isdigit() for c in w)
        return w if is_acronym else w.capitalize()

    return " ".join(word(w) for w in name.split())


def number(value: float) -> str:
    """Número con coma decimal y sin ceros sobrantes: 88.8 -> '88,8', 85.0 -> '85'."""
    return f"{value:.2f}".rstrip("0").rstrip(".").replace(".", ",")


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
    return {
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


def season_page(matches, tables, stints, team_name) -> dict:
    """Datos de la página de temporada."""
    players = tables["players"]
    shots = tables["shots"]
    own_players = players[players["team"] == team_name]
    numbers = own_players.groupby("player")["number"].last().to_dict()

    team = team_season(tables["teams"], team_name)
    team.index = [display_name(i) for i in team.index]
    season_players = player_season(players, team_name).join(
        player_usage(players, tables["teams"], team_name)
    )[PLAYER_COLUMNS]
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
    return {
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
        "zones_rivals": table(zone_summary(shots[shots["team"] != team_name]), "Zona"),
        "issues_total": sum(g["issues"] for g in games),
    }


def build_site(
    raw_dir: Path = RAW_DIR, out_dir: Path = SITE_DIR, team_name: str = TEAM_NAME
) -> list[Path]:
    """Genera la web y devuelve las páginas creadas."""
    matches = list(iter_matches(raw_dir))
    tables = build_tables(raw_dir)
    tables["shots"] = add_zones(tables["shots"])
    stints = pd.DataFrame([row for match in matches for row in stint_rows(*match, team_name)])

    env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape())
    common = {
        "team_name": display_name(team_name),
        "plotly_url": f"https://cdn.plot.ly/plotly-{get_plotlyjs_version()}.min.js",
        "generated": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "n_games": len(matches),
    }
    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "partidos").mkdir(parents=True)
    shutil.copy(HERE / "static" / "style.css", out_dir / "style.css")

    pages = [out_dir / "index.html"]
    pages[0].write_text(
        env.get_template("season.html.j2").render(
            **common, root="", **season_page(matches, tables, stints, team_name)
        ),
        encoding="utf-8",
    )
    for match, stats, moves in matches:
        page = out_dir / "partidos" / f"{match['id']}.html"
        page.write_text(
            env.get_template("match.html.j2").render(
                **common,
                root="../",
                **match_page(match, stats, moves, tables, stints, team_name),
            ),
            encoding="utf-8",
        )
        pages.append(page)
    return pages
