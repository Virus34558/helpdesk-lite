"""Observadores en copia (CC) de una incidencia."""

import pytest

from app import correo

OBSERVADOR = "jefe@empresa.com"


@pytest.fixture()
def enviados(monkeypatch):
    registrados = []

    def falso(destinatario, asunto, cuerpo):
        registrados.append((destinatario, asunto, cuerpo))
        return True

    monkeypatch.setattr(correo, "enviar_correo_seguro", falso)
    return registrados


def crear_ticket(client, cabeceras):
    return client.post(
        "/incidencias",
        json={"titulo": "Fallo del ERP", "descripcion": "no carga"},
        headers=cabeceras,
    ).json()


def añadir(client, cabeceras, ticket_id, email=OBSERVADOR):
    return client.post(
        f"/incidencias/{ticket_id}/observadores",
        json={"email": email},
        headers=cabeceras,
    )


def test_el_solicitante_añade_un_observador(client, cuentas):
    ticket = crear_ticket(client, cuentas.solicitante.h)

    respuesta = añadir(client, cuentas.solicitante.h, ticket["id"])

    assert respuesta.status_code == 201
    assert respuesta.json()["email"] == OBSERVADOR


def test_el_observador_aparece_en_el_listado(client, cuentas):
    ticket = crear_ticket(client, cuentas.solicitante.h)
    añadir(client, cuentas.solicitante.h, ticket["id"])

    listado = client.get(
        f"/incidencias/{ticket['id']}/observadores",
        headers=cuentas.solicitante.h,
    )

    assert [o["email"] for o in listado.json()] == [OBSERVADOR]


def test_no_se_duplica_el_observador(client, cuentas):
    ticket = crear_ticket(client, cuentas.solicitante.h)
    añadir(client, cuentas.solicitante.h, ticket["id"])

    respuesta = añadir(client, cuentas.solicitante.h, ticket["id"])

    assert respuesta.status_code == 409


def test_un_email_invalido_se_rechaza(client, cuentas):
    ticket = crear_ticket(client, cuentas.solicitante.h)

    respuesta = añadir(client, cuentas.solicitante.h, ticket["id"], "sin-arroba")

    assert respuesta.status_code == 422


def test_otro_solicitante_no_ve_ni_toca_el_ticket(client, cuentas):
    ticket = crear_ticket(client, cuentas.solicitante.h)

    assert añadir(client, cuentas.otro.h, ticket["id"]).status_code == 404
    assert (
        client.get(
            f"/incidencias/{ticket['id']}/observadores", headers=cuentas.otro.h
        ).status_code
        == 404
    )


def test_el_agente_puede_añadir_observador(client, cuentas):
    ticket = crear_ticket(client, cuentas.solicitante.h)

    respuesta = añadir(client, cuentas.agente.h, ticket["id"])

    assert respuesta.status_code == 201


def test_se_puede_eliminar_el_observador(client, cuentas):
    ticket = crear_ticket(client, cuentas.solicitante.h)
    observador = añadir(client, cuentas.solicitante.h, ticket["id"]).json()

    borrado = client.delete(
        f"/incidencias/{ticket['id']}/observadores/{observador['id']}",
        headers=cuentas.solicitante.h,
    )

    assert borrado.status_code == 204
    listado = client.get(
        f"/incidencias/{ticket['id']}/observadores",
        headers=cuentas.solicitante.h,
    )
    assert listado.json() == []


def test_el_observador_recibe_las_respuestas_publicas(client, cuentas, enviados):
    ticket = crear_ticket(client, cuentas.solicitante.h)
    añadir(client, cuentas.solicitante.h, ticket["id"])
    enviados.clear()

    client.post(
        f"/incidencias/{ticket['id']}/comentarios",
        json={"contenido": "El técnico revisa el servidor"},
        headers=cuentas.agente.h,
    )

    destinatarios = [destino for destino, _, _ in enviados]
    assert OBSERVADOR in destinatarios


def test_el_observador_recibe_la_resolucion(client, cuentas, enviados):
    ticket = crear_ticket(client, cuentas.solicitante.h)
    añadir(client, cuentas.solicitante.h, ticket["id"])
    client.patch(
        f"/incidencias/{ticket['id']}",
        json={"estado": "En progreso"},
        headers=cuentas.agente.h,
    )
    enviados.clear()

    client.post(
        f"/incidencias/{ticket['id']}/resolver",
        json={"nota_resolucion": "Reiniciado el servicio"},
        headers=cuentas.agente.h,
    )

    destinatarios = [destino for destino, _, _ in enviados]
    assert OBSERVADOR in destinatarios
