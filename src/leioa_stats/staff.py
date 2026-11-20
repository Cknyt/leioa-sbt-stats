"""Hoja del cuerpo técnico: posición, altura y disponibilidad de los jugadores.

La federación no publica posiciones, alturas ni lesiones. El cuerpo técnico puede apuntarlas
en un CSV (separado por comas, UTF-8) con estas columnas:

    equipo,jugador,posicion,altura,disponible
    LEIOA SBT,IÑIGO CARNEROS VILLAR,Base,1.82,si
    NAVASKET 1DM,INACIO GOMES MENDEZ,Pívot,2.01,no

- equipo y jugador, escritos como en el acta (las mayúsculas y los espacios dan igual).
- disponible: "si" o "no". Solo se guarda si está disponible, nunca el motivo: la web se ve
  con el enlace y una lesión es un dato de salud.
- El resto de columnas pueden quedar vacías.

El archivo es data/plantilla.csv, que no se versiona (el repositorio es público). En la
publicación, GitHub Actions lo escribe a partir del secreto PLANTILLA_CSV, si existe. Sin el
archivo, la web se genera igual, sin esos datos.
"""

from pathlib import Path

import pandas as pd

STAFF_FILE = Path("data/plantilla.csv")
COLUMNS = ["equipo", "jugador", "posicion", "altura", "disponible"]


def _key(text: str) -> str:
    return " ".join(str(text).upper().split())


def load_staff(path: Path = STAFF_FILE) -> pd.DataFrame:
    """Tabla indexada por (equipo, jugador) normalizados. Vacía si no hay archivo."""
    if not path.exists():
        return pd.DataFrame(
            columns=COLUMNS[2:], index=pd.MultiIndex.from_tuples([], names=["equipo", "jugador"])
        )
    df = pd.read_csv(path, dtype=str).fillna("")
    missing = set(COLUMNS[:2]) - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas en {path}: {', '.join(sorted(missing))}")
    for column in COLUMNS[2:]:
        if column not in df.columns:
            df[column] = ""
    df["equipo"] = df["equipo"].map(_key)
    df["jugador"] = df["jugador"].map(_key)
    df["disponible"] = df["disponible"].str.strip().str.lower()
    return df.set_index(["equipo", "jugador"])[COLUMNS[2:]]


def unavailable(staff: pd.DataFrame, team: str) -> list[str]:
    """Jugadores del equipo marcados como no disponibles (nombres tal cual en la hoja)."""
    if staff.empty or _key(team) not in staff.index.get_level_values(0):
        return []
    rows = staff.loc[_key(team)]
    return sorted(rows.index[rows["disponible"].isin(["no", "n", "0", "false"])])


def describe_player(staff: pd.DataFrame, team: str, player: str) -> str:
    """'Base, 1,82 m' o '' si no hay datos de ese jugador."""
    key = (_key(team), _key(player))
    if staff.empty or key not in staff.index:
        return ""
    row = staff.loc[key]
    parts = [row["posicion"].strip()] if row["posicion"].strip() else []
    if row["altura"].strip():
        parts.append(f"{row['altura'].strip().replace('.', ',')} m")
    return ", ".join(parts)
