def crear_ticket(client, cabeceras, titulo="Problema con el monitor"):
    return client.post(
        "/incidencias",
        json={"titulo": titulo, "descripcion": "Pantalla parpadea"},
        headers=cabeceras,
    ).json()


def poner_pendiente_de_usuario(client, cabeceras, ticket_id):
    client.patch(
        f"/incidencias/{ticket_id}", json={"estado": "En progreso"}, headers=cabeceras
    )
    client.patch(
        f"/incidencias/{ticket_id}",
        json={"estado": "Pendiente de usuario"},
        headers=cabeceras,
    )


def test_comentario_de_agente_no_reactiva_pendiente_de_usuario(client, cuentas):
    ticket = crear_ticket(client, cuentas.solicitante.h)
    poner_pendiente_de_usuario(client, cuentas.agente.h, ticket["id"])

    respuesta = client.post(
        f"/incidencias/{ticket['id']}/comentarios",
        json={"contenido": "Seguimos esperando tu respuesta", "es_interno": False},
        headers=cuentas.agente.h,
    )
    assert respuesta.status_code == 201

    actual = client.get(f"/incidencias/{ticket['id']}", headers=cuentas.agente.h).json()
    assert actual["estado"] == "Pendiente de usuario"


def test_notas_internas_de_admin_tampoco_las_ve_el_solicitante(client, cuentas):
    ticket = crear_ticket(client, cuentas.solicitante.h)
    client.post(
        f"/incidencias/{ticket['id']}/comentarios",
        json={"contenido": "Nota interna del administrador", "es_interno": True},
        headers=cuentas.admin.h,
    )
    comentarios = client.get(
        f"/incidencias/{ticket['id']}/comentarios", headers=cuentas.solicitante.h
    ).json()
    assert comentarios == []