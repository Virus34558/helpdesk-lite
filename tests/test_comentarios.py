def crear_ticket(client, cabeceras, titulo="Problema con el monitor"):
    return client.post(
        "/incidencias",
        json={"titulo": titulo, "descripcion": "Pantalla parpadea"},
        headers=cabeceras,
    ).json()


def test_solicitante_crea_comentario_publico(client, cuentas):
    ticket = crear_ticket(client, cuentas.solicitante.h)
    respuesta = client.post(
        f"/incidencias/{ticket['id']}/comentarios",
        json={"contenido": "Adjunto más información: el cable está bien conectado.", "es_interno": False},
        headers=cuentas.solicitante.h,
    )
    assert respuesta.status_code == 201
    datos = respuesta.json()
    assert datos["contenido"] == "Adjunto más información: el cable está bien conectado."
    assert datos["es_interno"] is False
    assert datos["autor"]["id"] == cuentas.solicitante.id
    assert datos["autor"]["rol"] == "solicitante"


def test_agente_crea_nota_interna(client, cuentas):
    ticket = crear_ticket(client, cuentas.solicitante.h)
    respuesta = client.post(
        f"/incidencias/{ticket['id']}/comentarios",
        json={"contenido": "Nota para N2: Revisar si la gráfica está fallando en garantía.", "es_interno": True},
        headers=cuentas.agente.h,
    )
    assert respuesta.status_code == 201
    datos = respuesta.json()
    assert datos["es_interno"] is True
    assert datos["autor"]["rol"] == "agente"


def test_solicitante_no_puede_crear_nota_interna(client, cuentas):
    ticket = crear_ticket(client, cuentas.solicitante.h)
    respuesta = client.post(
        f"/incidencias/{ticket['id']}/comentarios",
        json={"contenido": "Quiero crear una nota oculta", "es_interno": True},
        headers=cuentas.solicitante.h,
    )
    assert respuesta.status_code == 403
    assert "Los solicitantes no tienen permiso para crear notas internas" in respuesta.json()["detail"]


def test_solicitante_no_ve_notas_internas(client, cuentas):
    ticket = crear_ticket(client, cuentas.solicitante.h)

    # El agente añade una respuesta pública y una nota interna
    client.post(
        f"/incidencias/{ticket['id']}/comentarios",
        json={"contenido": "Mensaje visible para el cliente", "es_interno": False},
        headers=cuentas.agente.h,
    )
    client.post(
        f"/incidencias/{ticket['id']}/comentarios",
        json={"contenido": "Nota confidencial del equipo técnico", "es_interno": True},
        headers=cuentas.agente.h,
    )

    # El solicitante consulta el hilo
    res_solicitante = client.get(
        f"/incidencias/{ticket['id']}/comentarios",
        headers=cuentas.solicitante.h,
    )
    assert res_solicitante.status_code == 200
    mensajes = res_solicitante.json()
    assert len(mensajes) == 1
    assert mensajes[0]["contenido"] == "Mensaje visible para el cliente"
    assert mensajes[0]["es_interno"] is False


def test_agente_ve_comentarios_publicos_e_internos(client, cuentas):
    ticket = crear_ticket(client, cuentas.solicitante.h)

    client.post(
        f"/incidencias/{ticket['id']}/comentarios",
        json={"contenido": "Mensaje público", "es_interno": False},
        headers=cuentas.agente.h,
    )
    client.post(
        f"/incidencias/{ticket['id']}/comentarios",
        json={"contenido": "Nota técnica interna", "es_interno": True},
        headers=cuentas.agente.h,
    )

    res_agente = client.get(
        f"/incidencias/{ticket['id']}/comentarios",
        headers=cuentas.agente.h,
    )
    assert res_agente.status_code == 200
    mensajes = res_agente.json()
    assert len(mensajes) == 2
    assert any(m["es_interno"] is False for m in mensajes)
    assert any(m["es_interno"] is True for m in mensajes)


def test_solicitante_no_puede_comentar_en_incidencia_ajena(client, cuentas):
    ticket_ajeno = crear_ticket(client, cuentas.otro.h)

    respuesta = client.post(
        f"/incidencias/{ticket_ajeno['id']}/comentarios",
        json={"contenido": "Intentando comentar en ticket ajeno"},
        headers=cuentas.solicitante.h,
    )
    assert respuesta.status_code == 404


def test_no_se_puede_comentar_en_incidencia_cerrada(client, cuentas):
    ticket = crear_ticket(client, cuentas.solicitante.h)
    # Pasar a En progreso -> Resuelto -> Cerrado
    client.patch(f"/incidencias/{ticket['id']}", json={"estado": "En progreso"}, headers=cuentas.agente.h)
    client.post(
        f"/incidencias/{ticket['id']}/resolver",
        json={"nota_resolucion": "Solución completada"},
        headers=cuentas.agente.h,
    )
    client.patch(f"/incidencias/{ticket['id']}", json={"estado": "Cerrado"}, headers=cuentas.agente.h)

    # Intentar comentar en estado Cerrado
    respuesta = client.post(
        f"/incidencias/{ticket['id']}/comentarios",
        json={"contenido": "Hola, esto ya está cerrado"},
        headers=cuentas.solicitante.h,
    )
    assert respuesta.status_code == 409
    assert "No se pueden añadir comentarios a una incidencia en estado Cerrado" in respuesta.json()["detail"]


def test_comentario_de_solicitante_reactiva_pendiente_de_usuario(client, cuentas):
    ticket = crear_ticket(client, cuentas.solicitante.h)

    # Agente pone la incidencia en Pendiente de usuario
    client.patch(f"/incidencias/{ticket['id']}", json={"estado": "En progreso"}, headers=cuentas.agente.h)
    client.patch(
        f"/incidencias/{ticket['id']}",
        json={"estado": "Pendiente de usuario"},
        headers=cuentas.agente.h,
    )

    # Solicitante responde con datos
    respuesta = client.post(
        f"/incidencias/{ticket['id']}/comentarios",
        json={"contenido": "Ya he reiniciado el router como me pedisteis"},
        headers=cuentas.solicitante.h,
    )
    assert respuesta.status_code == 201

    # Comprobar que la incidencia se ha reactivado automáticamente a 'En progreso'
    ticket_actualizado = client.get(f"/incidencias/{ticket['id']}", headers=cuentas.agente.h).json()
    assert ticket_actualizado["estado"] == "En progreso"


def test_buscar_comentarios_por_codigo_legible(client, cuentas):
    ticket = crear_ticket(client, cuentas.solicitante.h)
    codigo = ticket["id_legible"]

    # Publicar usando código amigable (ej: INC-2026-000001)
    res_post = client.post(
        f"/incidencias/{codigo}/comentarios",
        json={"contenido": "Mensaje publicado por código legible"},
        headers=cuentas.agente.h,
    )
    assert res_post.status_code == 201

    # Listar usando código amigable
    res_get = client.get(
        f"/incidencias/{codigo}/comentarios",
        headers=cuentas.agente.h,
    )
    assert res_get.status_code == 200
    assert len(res_get.json()) == 1
    assert res_get.json()[0]["contenido"] == "Mensaje publicado por código legible"

