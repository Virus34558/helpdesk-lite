"""Ingesta de tickets desde un webhook de correo (RF-1.2)."""

import pytest

TOKEN = "token-de-ingesta-de-prueba"


@pytest.fixture()
def correo(monkeypatch):
    monkeypatch.setenv("INGESTA_CORREO_TOKEN", TOKEN)
    return {"X-Ingesta-Token": TOKEN}


def enviar(client, cabeceras, **campos):
    cuerpo = {
        "remitente": "cliente@empresa.com",
        "asunto": "No funciona el correo",
        "cuerpo": "Desde esta mañana no recibo nada.",
        "mensaje_id": "<mensaje-1@empresa.com>",
    }
    cuerpo.update(campos)
    return client.post("/ingesta/correo", json=cuerpo, headers=cabeceras)


def test_sin_token_configurado_esta_desactivado(client, monkeypatch):
    monkeypatch.delenv("INGESTA_CORREO_TOKEN", raising=False)

    respuesta = enviar(client, {"X-Ingesta-Token": TOKEN})

    assert respuesta.status_code == 503


def test_token_incorrecto_se_rechaza(client, correo):
    respuesta = enviar(client, {"X-Ingesta-Token": "otro"})

    assert respuesta.status_code == 401


def test_un_correo_nuevo_crea_ticket(client, correo):
    respuesta = enviar(client, correo)

    assert respuesta.status_code == 201
    datos = respuesta.json()
    assert datos["resultado"] == "ticket_creado"
    assert datos["incidencia_id"]


def test_el_ticket_ingestado_marca_canal_email(client, correo, cuentas):
    creado = enviar(client, correo, remitente="nueva@empresa.com").json()

    detalle = client.get(
        f"/incidencias/{creado['incidencia_id']}", headers=cuentas.admin.h
    ).json()

    assert detalle["canal_origen"] == "Email"
    assert detalle["titulo"] == "No funciona el correo"


def test_responder_con_el_codigo_añade_comentario(client, correo, cuentas):
    ticket = client.post(
        "/incidencias",
        json={"titulo": "Impresora", "descripcion": "no imprime"},
        headers=cuentas.solicitante.h,
    ).json()

    respuesta = enviar(
        client,
        correo,
        remitente="otro@empresa.com",
        asunto=f"Re: [{ticket['id_legible']}] Impresora",
        cuerpo="Sigue sin funcionar",
        mensaje_id="<mensaje-2@empresa.com>",
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["resultado"] == "comentario"
    assert respuesta.json()["incidencia_id"] == ticket["id"]


def test_la_respuesta_reactiva_al_ticket_pendiente(client, correo, cuentas):
    ticket = client.post(
        "/incidencias",
        json={"titulo": "VPN", "descripcion": "cae"},
        headers=cuentas.solicitante.h,
    ).json()
    client.patch(
        f"/incidencias/{ticket['id']}",
        json={"estado": "En progreso"},
        headers=cuentas.agente.h,
    )
    client.patch(
        f"/incidencias/{ticket['id']}",
        json={"estado": "Pendiente de usuario"},
        headers=cuentas.agente.h,
    )

    enviar(
        client,
        correo,
        asunto=f"[{ticket['id_legible']}] VPN",
        cuerpo="Ya lo he reiniciado y sigue igual",
        mensaje_id="<mensaje-3@empresa.com>",
    )

    detalle = client.get(
        f"/incidencias/{ticket['id']}", headers=cuentas.agente.h
    ).json()
    assert detalle["estado"] == "En progreso"


def test_las_autorespuestas_se_ignoran(client, correo):
    respuesta = enviar(client, correo, auto_submitted=True)

    assert respuesta.status_code == 202
    assert respuesta.json()["resultado"] == "ignorado"


def test_los_remitentes_no_reply_se_ignoran(client, correo):
    respuesta = enviar(client, correo, remitente="no-reply@empresa.com")

    assert respuesta.status_code == 202
    assert respuesta.json()["resultado"] == "ignorado"


def test_el_mismo_mensaje_no_duplica_el_ticket(client, correo):
    primero = enviar(client, correo)
    segundo = enviar(client, correo)

    assert primero.status_code == 201
    assert segundo.status_code == 202
    assert segundo.json()["resultado"] == "ignorado"
