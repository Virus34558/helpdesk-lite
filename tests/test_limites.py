"""Límite de intentos en los endpoints de autenticación."""

import pytest

from app import limites

CREDENCIALES_MALAS = {"email": "nadie@test.com", "password": "contrasena-larga"}
REGISTRO = {
    "email": "nuevo@test.com",
    "nombre_completo": "Usuario Nuevo",
    "password": "contrasena-larga",
}


@pytest.fixture(autouse=True)
def limpiar_contadores():
    limites.reiniciar()
    yield
    limites.reiniciar()


def test_login_bloquea_pasado_el_limite(client, monkeypatch):
    monkeypatch.setenv("AUTH_MAX_INTENTOS", "3")

    for _ in range(3):
        assert client.post("/auth/login", json=CREDENCIALES_MALAS).status_code == 401

    respuesta = client.post("/auth/login", json=CREDENCIALES_MALAS)

    assert respuesta.status_code == 429


def test_bloqueo_indica_cuando_reintentar(client, monkeypatch):
    monkeypatch.setenv("AUTH_MAX_INTENTOS", "1")

    client.post("/auth/login", json=CREDENCIALES_MALAS)
    respuesta = client.post("/auth/login", json=CREDENCIALES_MALAS)

    assert respuesta.status_code == 429
    assert int(respuesta.headers["Retry-After"]) >= 1


def test_registro_tambien_esta_limitado(client, monkeypatch):
    monkeypatch.setenv("AUTH_MAX_INTENTOS", "1")

    primero = client.post("/auth/registro", json=REGISTRO)
    segundo = client.post(
        "/auth/registro", json=REGISTRO | {"email": "otro@test.com"}
    )

    assert primero.status_code == 201
    assert segundo.status_code == 429


def test_cada_ruta_tiene_su_propio_contador(client, monkeypatch):
    monkeypatch.setenv("AUTH_MAX_INTENTOS", "1")

    client.post("/auth/login", json=CREDENCIALES_MALAS)
    respuesta = client.post("/auth/registro", json=REGISTRO)

    assert respuesta.status_code == 201
