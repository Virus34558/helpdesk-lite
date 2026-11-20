"""Calendario laboral con festivos y pólizas SLA configurables."""

from datetime import datetime

from app import sla


def test_un_festivo_no_es_hora_habil(monkeypatch):
    monkeypatch.setenv("DIAS_FESTIVOS", "2026-01-05")

    assert sla.es_hora_habil(datetime(2026, 1, 5, 10, 0)) is False


def test_sin_festivo_el_lunes_es_habil(monkeypatch):
    monkeypatch.delenv("DIAS_FESTIVOS", raising=False)

    assert sla.es_hora_habil(datetime(2026, 1, 5, 10, 0)) is True


def test_el_sla_salta_el_festivo(monkeypatch):
    monkeypatch.setenv("DIAS_FESTIVOS", "2026-01-05")

    frt, _ = sla.inicializar_sla("P3 - Media", datetime(2026, 1, 2, 17, 0))

    # 1 h el viernes + 3 h el martes (el lunes es festivo)
    assert frt == datetime(2026, 1, 6, 12, 0)


def test_festivos_mal_escritos_se_ignoran(monkeypatch):
    monkeypatch.setenv("DIAS_FESTIVOS", "basura,2026-13-45,2026-01-05")

    assert sla.es_hora_habil(datetime(2026, 1, 5, 10, 0)) is False
    assert sla.es_hora_habil(datetime(2026, 1, 6, 10, 0)) is True


def test_politica_sla_configurable(monkeypatch):
    monkeypatch.setenv(
        "SLA_POLITICAS", '{"P4 - Baja": {"frt_minutos": 60, "rt_horas": 8}}'
    )

    frt, _ = sla.inicializar_sla("P4 - Baja", datetime(2026, 1, 5, 9, 0))

    assert frt == datetime(2026, 1, 5, 10, 0)


def test_politica_incompleta_hereda_los_valores_por_defecto(monkeypatch):
    monkeypatch.setenv("SLA_POLITICAS", '{"P4 - Baja": {"frt_minutos": 60}}')

    objetivo = sla.objetivo_de("P4 - Baja")

    assert objetivo["frt_minutos"] == 60
    assert objetivo["rt_horas"] == 72
    assert objetivo["calendario"] == "laboral"


def test_json_invalido_no_rompe_el_sla(monkeypatch):
    monkeypatch.setenv("SLA_POLITICAS", "{no es json")

    objetivo = sla.objetivo_de("P4 - Baja")

    assert objetivo["frt_minutos"] == 480
