"""Formato de nombres y números para mostrarlos (web y conclusiones)."""


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


def short_name(name: str) -> str:
    """'IÑIGO CARNEROS VILLAR' -> 'I. Carneros'. Para tablas estrechas (móvil)."""
    parts = display_name(name).split()
    return f"{parts[0][0]}. {parts[1]}" if len(parts) > 1 else display_name(name)


def short_labels(names) -> list[str]:
    """Nombres cortos de una lista de jugadores. Si dos coinciden (mismo nombre corto), esos
    dos se dejan completos para no confundirlos."""
    names = list(names)
    shorts = [short_name(n) for n in names]
    repeated = {s for s in shorts if shorts.count(s) > 1}
    return [display_name(n) if s in repeated else s for n, s in zip(names, shorts, strict=True)]
