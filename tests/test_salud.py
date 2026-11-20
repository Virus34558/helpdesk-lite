"""Salud del servicio y validación de configuración en producción."""

import pytest

from app import config


def test_health_responde_ok(client):
    respuesta = client.get("/health")

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "ok"


def test_health_comprueba_la_base_de_datos(client):
    respuesta = client.get("/health")

    assert respuesta.json()["base_datos"] == "ok"


def test_produccion_exige_database_url(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        config.validar_configuracion()


def test_produccion_con_database_url_arranca(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("DATABASE_URL", "postgresql://usuario:clave@host:5432/base")

    config.validar_configuracion()


def test_local_sin_database_url_arranca(monkeypatch):
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    config.validar_configuracion()
