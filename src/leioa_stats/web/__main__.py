"""Genera la web estática en site/.

Uso:
    uv run python -m leioa_stats.web

Abre site/index.html en el navegador para verla.
"""

from leioa_stats.web.build import SITE_DIR, build_site


def main() -> None:
    pages = build_site()
    print(f"{len(pages)} páginas generadas en {SITE_DIR}/ (abre {SITE_DIR / 'index.html'})")


if __name__ == "__main__":
    main()
