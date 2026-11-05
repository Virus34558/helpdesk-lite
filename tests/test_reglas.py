import pytest

from app.reglas import calcular_prioridad, transicion_permitida

MATRIZ = [
    ("Alto", "Crítica", "P1 - Crítica"),
    ("Alto", "Alta", "P1 - Crítica"),
    ("Alto", "Media", "P2 - Alta"),
    ("Alto", "Baja", "P3 - Media"),
    ("Medio", "Crítica", "P1 - Crítica"),
    ("Medio", "Alta", "P2 - Alta"),
    ("Medio", "Media", "P3 - Media"),
    ("Medio", "Baja", "P4 - Baja"),
    ("Bajo", "Crítica", "P2 - Alta"),
    ("Bajo", "Alta", "P3 - Media"),
    ("Bajo", "Media", "P4 - Baja"),
    ("Bajo", "Baja", "P4 - Baja"),
]


@pytest.mark.parametrize("impacto,urgencia,esperada", MATRIZ)
def test_matriz_de_prioridad(impacto, urgencia, esperada):
    assert calcular_prioridad(impacto, urgencia) == esperada


@pytest.mark.parametrize(
    "actual,nuevo",
    [
        ("Nuevo", "En progreso"),
        ("En progreso", "Pendiente de usuario"),
        ("En progreso", "Resuelto"),
        ("Resuelto", "Cerrado"),
        ("Resuelto", "En progreso"),
    ],
)
def test_transiciones_permitidas(actual, nuevo):
    assert transicion_permitida(actual, nuevo)


@pytest.mark.parametrize(
    "actual,nuevo",
    [
        ("Nuevo", "Resuelto"),
        ("Nuevo", "Cerrado"),
        ("Resuelto", "Nuevo"),
        ("Cerrado", "En progreso"),
        ("Cancelado", "Nuevo"),
    ],
)
def test_transiciones_prohibidas(actual, nuevo):
    assert not transicion_permitida(actual, nuevo)