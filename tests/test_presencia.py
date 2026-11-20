"""Registro de quién tiene abierto cada ticket (RF-2.5)."""

import pytest

from app import presencia


@pytest.fixture(autouse=True)
def registro_limpio():
    presencia._vistas.clear()
    yield
    presencia._vistas.clear()


def test_entrar_y_ver_presentes():
    presencia.entrar(1, "ana@empresa.com")

    assert presencia.presentes(1) == ["ana@empresa.com"]


def test_varios_agentes_a_la_vez():
    presencia.entrar(1, "ana@empresa.com")
    presencia.entrar(1, "luis@empresa.com")

    assert sorted(presencia.presentes(1)) == ["ana@empresa.com", "luis@empresa.com"]


def test_salir_elimina_la_presencia():
    presencia.entrar(1, "ana@empresa.com")

    presencia.salir(1, "ana@empresa.com")

    assert presencia.presentes(1) == []


def test_se_puede_excluir_al_propio_usuario():
    presencia.entrar(1, "ana@empresa.com")
    presencia.entrar(1, "luis@empresa.com")

    assert presencia.presentes(1, excluir="ana@empresa.com") == ["luis@empresa.com"]


def test_la_presencia_caduca(monkeypatch):
    ahora = [1000.0]
    monkeypatch.setattr(presencia, "_ahora", lambda: ahora[0])
    presencia.entrar(1, "ana@empresa.com")

    ahora[0] += presencia.TTL_SEGUNDOS + 1

    assert presencia.presentes(1) == []


def test_los_tickets_no_se_mezclan():
    presencia.entrar(1, "ana@empresa.com")
    presencia.entrar(2, "luis@empresa.com")

    assert presencia.presentes(1) == ["ana@empresa.com"]
    assert presencia.presentes(2) == ["luis@empresa.com"]


def test_las_claves_vacias_se_limpian():
    presencia.entrar(1, "ana@empresa.com")
    presencia.salir(1, "ana@empresa.com")

    presencia.entrar(2, "luis@empresa.com")

    assert 1 not in presencia._vistas
