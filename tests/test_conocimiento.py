def crear_articulo(client, cuentas, **extra):
    respuesta = client.post(
        "/conocimiento",
        json={
            "titulo": "Artículo de prueba",
            "contenido": "Contenido de prueba para la base de conocimiento.",
            **extra,
        },
        headers=cuentas.agente.h,
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def crear_categoria(client, cuentas, nombre, **extra):
    respuesta = client.post(
        "/categorias",
        json={"nombre": nombre, **extra},
        headers=cuentas.admin.h,
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def test_solicitante_no_puede_crear_articulo(client, cuentas):
    respuesta = client.post(
        "/conocimiento",
        json={"titulo": "No permitido", "contenido": "Texto"},
        headers=cuentas.solicitante.h,
    )
    assert respuesta.status_code == 403


def test_agente_crea_articulo_y_se_deriva_el_resumen(client, cuentas):
    articulo = crear_articulo(
        client,
        cuentas,
        titulo="Cómo reiniciar la VPN",
        contenido="Paso 1. Abre el cliente VPN.\nPaso 2. Pulsa desconectar.",
    )
    assert articulo["autor_id"] == cuentas.agente.id
    assert articulo["es_publico"] is True
    assert articulo["resumen"] == "Paso 1. Abre el cliente VPN. Paso 2. Pulsa desconectar."
    assert articulo["contenido"].startswith("Paso 1")


def test_solicitante_solo_ve_articulos_publicos(client, cuentas):
    publico = crear_articulo(
        client, cuentas, titulo="Artículo público", es_publico=True
    )
    interno = crear_articulo(
        client, cuentas, titulo="Artículo interno", es_publico=False
    )

    listado = client.get("/conocimiento", headers=cuentas.solicitante.h)
    assert listado.status_code == 200
    ids = [a["id"] for a in listado.json()]
    assert publico["id"] in ids
    assert interno["id"] not in ids

    oculto = client.get(
        f"/conocimiento/{interno['id']}", headers=cuentas.solicitante.h
    )
    assert oculto.status_code == 404

    visible = client.get(
        f"/conocimiento/{publico['id']}", headers=cuentas.solicitante.h
    )
    assert visible.status_code == 200
    assert visible.json()["contenido"]

    listado_gestor = client.get("/conocimiento", headers=cuentas.agente.h)
    ids_gestor = {a["id"] for a in listado_gestor.json()}
    assert {publico["id"], interno["id"]} <= ids_gestor


def test_busqueda_por_texto_y_categoria(client, cuentas):
    categoria = crear_categoria(client, cuentas, "Redes")
    crear_articulo(
        client,
        cuentas,
        titulo="Configurar proxy",
        contenido="Ajustes del proxy corporativo",
    )
    crear_articulo(
        client,
        cuentas,
        titulo="Reiniciar switch",
        contenido="Procedimiento del switch de planta",
        categoria_id=categoria["id"],
    )

    por_texto = client.get(
        "/conocimiento?q=switch", headers=cuentas.solicitante.h
    )
    assert [a["titulo"] for a in por_texto.json()] == ["Reiniciar switch"]

    por_categoria = client.get(
        f"/conocimiento?categoria_id={categoria['id']}",
        headers=cuentas.solicitante.h,
    )
    assert [a["titulo"] for a in por_categoria.json()] == ["Reiniciar switch"]


def test_sugerencias_limita_a_cinco_y_excluye_internos(client, cuentas):
    for indice in range(6):
        crear_articulo(
            client,
            cuentas,
            titulo=f"VPN solución {indice}",
            contenido="Pasos para resolver problemas de VPN",
        )
    crear_articulo(
        client,
        cuentas,
        titulo="VPN interno",
        contenido="Procedimiento interno de VPN",
        es_publico=False,
    )

    respuesta = client.get(
        "/conocimiento/sugerencias?q=vpn", headers=cuentas.solicitante.h
    )
    assert respuesta.status_code == 200
    assert len(respuesta.json()) == 5
    assert all(a["es_publico"] for a in respuesta.json())

    corta = client.get(
        "/conocimiento/sugerencias?q=v", headers=cuentas.solicitante.h
    )
    assert corta.json() == []


def test_actualizar_articulo_y_validaciones(client, cuentas):
    articulo = crear_articulo(client, cuentas)
    inactiva = crear_categoria(client, cuentas, "Antigua", activa=False)

    actualizado = client.patch(
        f"/conocimiento/{articulo['id']}",
        json={"titulo": "Título actualizado", "es_publico": False},
        headers=cuentas.admin.h,
    )
    assert actualizado.status_code == 200
    assert actualizado.json()["titulo"] == "Título actualizado"
    assert actualizado.json()["es_publico"] is False

    nulo = client.patch(
        f"/conocimiento/{articulo['id']}",
        json={"titulo": None},
        headers=cuentas.agente.h,
    )
    assert nulo.status_code == 400

    categoria_inactiva = client.patch(
        f"/conocimiento/{articulo['id']}",
        json={"categoria_id": inactiva["id"]},
        headers=cuentas.agente.h,
    )
    assert categoria_inactiva.status_code == 400

    prohibido = client.patch(
        f"/conocimiento/{articulo['id']}",
        json={"titulo": "Cambio de solicitante"},
        headers=cuentas.solicitante.h,
    )
    assert prohibido.status_code == 403


def test_crear_articulo_con_categoria_inactiva_falla(client, cuentas):
    inactiva = crear_categoria(client, cuentas, "Desactivada", activa=False)

    respuesta = client.post(
        "/conocimiento",
        json={
            "titulo": "Artículo inválido",
            "contenido": "Texto",
            "categoria_id": inactiva["id"],
        },
        headers=cuentas.agente.h,
    )
    assert respuesta.status_code == 400


def test_eliminar_articulo_solo_admin(client, cuentas):
    articulo = crear_articulo(client, cuentas)

    prohibido = client.delete(
        f"/conocimiento/{articulo['id']}", headers=cuentas.agente.h
    )
    assert prohibido.status_code == 403

    eliminado = client.delete(
        f"/conocimiento/{articulo['id']}", headers=cuentas.admin.h
    )
    assert eliminado.status_code == 204

    repetido = client.delete(
        f"/conocimiento/{articulo['id']}", headers=cuentas.admin.h
    )
    assert repetido.status_code == 404
