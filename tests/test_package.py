import leioa_stats


def test_package_imports():
    # Comprueba que el paquete está instalado en el entorno de uv.
    assert leioa_stats.__doc__
