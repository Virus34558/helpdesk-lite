from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import sessionmaker

from app import correo, models


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
        json={"titulo": "Fallo de correo", "descripcion": "Prueba"},
        headers=cabeceras,
    ).json()


def test_creacion_envia_correo_al_solicitante(client, cuentas, enviados):
    crear_ticket(client, cuentas.solicitante.h)

    assert len(enviados) == 1
    destinatario, asunto, _ = enviados[0]
    assert destinatario == "solicitante@test.com"
    assert "Incidencia registrada" in asunto


def test_nota_interna_no_envia_correo(client, cuentas, enviados):
    ticket = crear_ticket(client, cuentas.solicitante.h)
    enviados.clear()

    client.post(
        f"/incidencias/{ticket['id']}/comentarios",
        json={"contenido": "Nota interna", "es_interno": True},
        headers=cuentas.agente.h,
    )

    assert enviados == []


def test_respuesta_publica_de_agente_avisa_al_solicitante(client, cuentas, enviados):
    ticket = crear_ticket(client, cuentas.solicitante.h)
    enviados.clear()

    client.post(
        f"/incidencias/{ticket['id']}/comentarios",
        json={"contenido": "Estamos revisándolo", "es_interno": False},
        headers=cuentas.agente.h,
    )

    assert len(enviados) == 1
    assert enviados[0][0] == "solicitante@test.com"
    assert "equipo de soporte" in enviados[0][1]


def test_respuesta_publica_de_solicitante_avisa_al_agente(client, cuentas, enviados):
    ticket = crear_ticket(client, cuentas.solicitante.h)
    client.post(
        f"/incidencias/{ticket['id']}/asignar",
        json={"agente_id": cuentas.agente.id},
        headers=cuentas.admin.h,
    )
    enviados.clear()

    client.post(
        f"/incidencias/{ticket['id']}/comentarios",
        json={"contenido": "Sigo con el problema", "es_interno": False},
        headers=cuentas.solicitante.h,
    )

    assert len(enviados) == 1
    assert enviados[0][0] == "agente@test.com"
    assert "solicitante" in enviados[0][1]


def test_resolucion_envia_correo(client, cuentas, enviados):
    ticket = crear_ticket(client, cuentas.solicitante.h)
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

    assert len(enviados) == 1
    assert enviados[0][0] == "solicitante@test.com"
    assert "resuelta" in enviados[0][1].lower()


def test_alerta_sla_envia_correo_a_supervision(client, cuentas, motor, enviados):
    ticket = crear_ticket(client, cuentas.solicitante.h)

    TestingSession = sessionmaker(bind=motor)
    with TestingSession() as db:
        incidencia = db.get(models.Incidencia, ticket["id"])
        incidencia.sla_limite_resolucion = datetime.now() - timedelta(minutes=1)
        incidencia.sla_breach_100 = False
        db.commit()

    enviados.clear()
    respuesta = client.post("/sla/revisar", headers=cuentas.admin.h)
    assert respuesta.status_code == 200

    assert any(destinatario == "admin@test.com" for destinatario, _, _ in enviados)
