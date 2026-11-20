import pandas as pd
import pytest

from leioa_stats.metrics import confidence


@pytest.mark.parametrize(
    ("z", "expected"),
    [(2.1, "alta"), (-2.0, "alta"), (1.6, "media"), (-1.5, "media"), (1.2, None),
     (float("nan"), None), (None, None)],
)  # fmt: skip
def test_label(z, expected):
    assert confidence.label(z) == expected


def test_team_z():
    # 4 partidos: error estándar 12 / 2 = 6; 106 frente a 94 → 2 errores estándar.
    assert confidence.team_z(106, 94, 12, 4, higher_is_better=True) == 2
    # En defensa, encajar más que la media es peor: z negativa.
    assert confidence.team_z(106, 94, 12, 4, higher_is_better=False) == -2


def test_proportion_z():
    # 60 % en 100 tiros frente a un 50 %: error estándar 0,05 → z = 2.
    assert confidence.proportion_z(60, 100, 0.5) == pytest.approx(2)
    assert pd.isna(confidence.proportion_z(0, 0, 0.5))


def test_shrink():
    # 5/11 en triples con K = 100 y una liga al 27 %: (5 + 27) / 111 = 28,8 %.
    assert confidence.shrink(5, 11, 0.27, 100) == pytest.approx(32 / 111)
    assert confidence.shrink_weight(100, 100) == 0.5


def test_estimate_k_uses_default_when_all_is_noise():
    # Todos aciertan exactamente lo mismo: no hay diferencia real entre jugadores.
    attempts = pd.Series([40] * 40)
    made = pd.Series([12] * 40)
    assert confidence.estimate_k(made, attempts, default=100) == 100


def test_estimate_k_with_real_differences():
    # Mitad al 20 % y mitad al 40 %, con muchos intentos: la diferencia es real.
    attempts = pd.Series([400] * 40)
    made = pd.Series([80] * 20 + [160] * 20)
    k = confidence.estimate_k(made, attempts, default=100)
    assert confidence.K_LIMITS[0] <= k < 100


def test_league_spread_defaults_with_few_games():
    games = pd.DataFrame({"team": ["A", "B"]})
    # Sin grados de libertad suficientes no se calcula nada: valores por defecto.
    assert confidence.league_spread(games).equals(pd.Series(confidence.DEFAULT_SPREAD))
