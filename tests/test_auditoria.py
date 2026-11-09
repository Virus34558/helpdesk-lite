def crear_ticket(client, cabeceras, titulo="Incidencia de auditoría"):
    return client.post(
        "/incidencias",
        json={"titulo": titulo, "descripcion": "Detalle del problema"},
        headers=cabeceras,
    ).json()


def test_creacion_ticket_registra_auditoria(client, cuentas):
    ticket = crear_ticket(client, cuentas.solicitante.h)
    historial = client.get(
        f"/incidencias/{ticket['id']}/historial", headers=cuentas.agente.h
    ).json()

    assert len(historial) >= 1
    evento_creacion = historial[0]
    assert evento_creacion["accion"] == "creacion"
    assert evento_creacion["valor_nuevo"] == ticket["id_legible"]
    assert evento_creacion["usuario"]["id"] == cuentas.solicitante.id


def test_cambio_estado_registra_auditoria(client, cuentas):
    ticket = crear_ticket(client, cuentas.solicitante.h)

    # Pasar a En progreso
    client.patch(
        f"/incidencias/{ticket['id']}",
        json={"estado": "En progreso"},
        headers=cuentas.agente.h,
    )

    historial = client.get(
        f"/incidencias/{ticket['id']}/historial", headers=cuentas.agente.h
    ).json()

    eventos_estado = [e for e in historial if e["accion"] == "cambio_estado"]
    assert len(eventos_estado) == 1
    assert eventos_estado[0]["campo"] == "estado"
    assert eventos_estado[0]["valor_anterior"] == "Nuevo"
    assert eventos_estado[0]["valor_nuevo"] == "En progreso"
    assert eventos_estado[0]["usuario"]["id"] == cuentas.agente.id


def test_asignacion_tecnico_registra_auditoria(client, cuentas):
    ticket = crear_ticket(client, cuentas.solicitante.h)

    client.post(
        f"/incidencias/{ticket['id']}/asignar",
        json={"agente_id": cuentas.agente.id},
        headers=cuentas.agente.h,
    )

    historial = client.get(
        f"/incidencias/{ticket['id']}/historial", headers=cuentas.agente.h
    ).json()

    eventos_asignacion = [e for e in historial if e["accion"] == "asignacion_tecnico"]
    assert len(eventos_asignacion) == 1
    assert eventos_asignacion[0]["campo"] == "agente_asignado_id"
    assert eventos_asignacion[0]["valor_anterior"] is None
    assert eventos_asignacion[0]["valor_nuevo"] == str(cuentas.agente.id)


def test_cambio_impacto_y_urgencia_registra_prioridad(client, cuentas):
    ticket = crear_ticket(client, cuentas.solicitante.h)
    assert ticket["prioridad"] == "P4 - Baja"

    client.patch(
        f"/incidencias/{ticket['id']}",
        json={"impacto": "Alto", "urgencia": "Crítica"},
        headers=cuentas.agente.h,
    )

    historial = client.get(
        f"/incidencias/{ticket['id']}/historial", headers=cuentas.agente.h
    ).json()

    eventos_prioridad = [e for e in historial if e["accion"] == "cambio_prioridad"]
    assert len(eventos_prioridad) == 1
    assert eventos_prioridad[0]["valor_anterior"] == "P4 - Baja"
    assert eventos_prioridad[0]["valor_nuevo"] == "P1 - Crítica"


def test_resolucion_registra_auditoria_con_nota(client, cuentas):
    ticket = crear_ticket(client, cuentas.solicitante.h)
    client.patch(
        f"/incidencias/{ticket['id']}", json={"estado": "En progreso"}, headers=cuentas.agente.h
    )
    client.post(
        f"/incidencias/{ticket['id']}/resolver",
        json={"nota_resolucion": "Sustituido disco duro averiado"},
        headers=cuentas.agente.h,
    )

    historial = client.get(
        f"/incidencias/{ticket['id']}/historial", headers=cuentas.agente.h
    ).json()

    eventos_resolucion = [e for e in historial if e["accion"] == "resolucion"]
    assert len(eventos_resolucion) == 1
    assert eventos_resolucion[0]["campo"] == "nota_resolucion"
    assert eventos_resolucion[0]["valor_nuevo"] == "Sustituido disco duro averiado"


def test_solicitante_no_ve_auditoria_de_notas_internas(client, cuentas):
    ticket = crear_ticket(client, cuentas.solicitante.h)

    # Agente añade una respuesta pública y una nota interna
    client.post(
        f"/incidencias/{ticket['id']}/comentarios",
        json={"contenido": "Respuesta para el usuario", "es_interno": False},
        headers=cuentas.agente.h,
    )
    client.post(
        f"/incidencias/{ticket['id']}/comentarios",
        json={"contenido": "Nota interna técnica", "es_interno": True},
        headers=cuentas.agente.h,
    )

    # El solicitante consulta el historial
    historial_solicitante = client.get(
        f"/incidencias/{ticket['id']}/historial", headers=cuentas.solicitante.h
    ).json()
    assert all(e["es_interno"] is False for e in historial_solicitante)
    assert not any(e["accion"] == "nota_interna" for e in historial_solicitante)

    # El agente sí ve la auditoría de la nota interna
    historial_agente = client.get(
        f"/incidencias/{ticket['id']}/historial", headers=cuentas.agente.h
    ).json()
    assert any(e["accion"] == "nota_interna" for e in historial_agente)


def test_solicitante_no_puede_ver_historial_de_ticket_ajeno(client, cuentas):
    ticket_ajeno = crear_ticket(client, cuentas.otro.h)

    res = client.get(
        f"/incidencias/{ticket_ajeno['id']}/historial", headers=cuentas.solicitante.h
    )
    assert res.status_code == 404


def test_historial_accesible_por_codigo_legible(client, cuentas):
    ticket = crear_ticket(client, cuentas.solicitante.h)
    codigo = ticket["id_legible"]

    res = client.get(f"/incidencias/{codigo}/historial", headers=cuentas.agente.h)
    assert res.status_code == 200
    assert len(res.json()) >= 1

