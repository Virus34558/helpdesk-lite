def crear_ticket(client, cabeceras, titulo="Problema con el teclado"):
    return client.post(
        "/incidencias",
        json={"titulo": titulo, "descripcion": "No responde al pulsar"},
        headers=cabeceras,
    ).json()


def subir(client, cabeceras, ticket_id, nombre="nota.txt", contenido=b"hola"):
    return client.post(
        f"/incidencias/{ticket_id}/adjuntos",
        files={"archivo": (nombre, contenido, "text/plain")},
        headers=cabeceras,
    )


def test_solicitante_sube_y_descarga_adjunto(client, cuentas):
    ticket = crear_ticket(client, cuentas.solicitante.h)

    respuesta = subir(client, cuentas.solicitante.h, ticket["id"])
    assert respuesta.status_code == 201
    datos = respuesta.json()
    assert datos["nombre_original"] == "nota.txt"
    assert datos["tamano_bytes"] == 4
    assert datos["es_interno"] is False

    listado = client.get(
        f"/incidencias/{ticket['id']}/adjuntos",
        headers=cuentas.solicitante.h,
    )
    assert listado.status_code == 200
    assert len(listado.json()) == 1

    descarga = client.get(
        f"/adjuntos/{datos['id']}",
        headers=cuentas.solicitante.h,
    )
    assert descarga.status_code == 200
    assert descarga.content == b"hola"
    assert "nota.txt" in descarga.headers["content-disposition"]


def test_solicitante_no_puede_crear_adjunto_interno(client, cuentas):
    ticket = crear_ticket(client, cuentas.solicitante.h)

    respuesta = client.post(
        f"/incidencias/{ticket['id']}/adjuntos",
        files={"archivo": ("privado.txt", b"secreto", "text/plain")},
        data={"es_interno": "true"},
        headers=cuentas.solicitante.h,
    )
    assert respuesta.status_code == 201
    assert respuesta.json()["es_interno"] is False


def test_adjunto_interno_oculto_al_solicitante(client, cuentas):
    ticket = crear_ticket(client, cuentas.solicitante.h)

    respuesta = client.post(
        f"/incidencias/{ticket['id']}/adjuntos",
        files={"archivo": ("interno.txt", b"secreto", "text/plain")},
        data={"es_interno": "true"},
        headers=cuentas.agente.h,
    )
    assert respuesta.status_code == 201
    adjunto_id = respuesta.json()["id"]

    listado_agente = client.get(
        f"/incidencias/{ticket['id']}/adjuntos",
        headers=cuentas.agente.h,
    )
    assert len(listado_agente.json()) == 1

    listado_solicitante = client.get(
        f"/incidencias/{ticket['id']}/adjuntos",
        headers=cuentas.solicitante.h,
    )
    assert listado_solicitante.json() == []

    descarga = client.get(f"/adjuntos/{adjunto_id}", headers=cuentas.solicitante.h)
    assert descarga.status_code == 404


def test_otro_solicitante_no_puede_descargar_adjunto(client, cuentas):
    ticket = crear_ticket(client, cuentas.solicitante.h)
    adjunto = subir(client, cuentas.solicitante.h, ticket["id"]).json()

    respuesta = client.get(f"/adjuntos/{adjunto['id']}", headers=cuentas.otro.h)
    assert respuesta.status_code == 404


def test_extension_peligrosa_bloqueada(client, cuentas):
    ticket = crear_ticket(client, cuentas.solicitante.h)

    respuesta = subir(client, cuentas.solicitante.h, ticket["id"], "virus.exe")
    assert respuesta.status_code == 400
    assert "no está permitida" in respuesta.json()["detail"]


def test_limite_de_tamano(client, cuentas, monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_MB", "0.001")
    ticket = crear_ticket(client, cuentas.solicitante.h)

    respuesta = subir(
        client,
        cuentas.solicitante.h,
        ticket["id"],
        contenido=b"x" * 2048,
    )
    assert respuesta.status_code == 413


def test_no_se_pueden_subir_adjuntos_a_ticket_cerrado(client, cuentas):
    ticket = crear_ticket(client, cuentas.solicitante.h)
    client.patch(
        f"/incidencias/{ticket['id']}",
        json={"estado": "En progreso"},
        headers=cuentas.agente.h,
    )
    client.post(
        f"/incidencias/{ticket['id']}/resolver",
        json={"nota_resolucion": "Resuelto"},
        headers=cuentas.agente.h,
    )
    client.patch(
        f"/incidencias/{ticket['id']}",
        json={"estado": "Cerrado"},
        headers=cuentas.agente.h,
    )

    respuesta = subir(client, cuentas.solicitante.h, ticket["id"])
    assert respuesta.status_code == 409
