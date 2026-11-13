from sqlalchemy.orm import sessionmaker

from app import models


def crear_categoria(client, cuentas, nombre="SAP"):
    return client.post(
        "/categorias",
        json={"nombre": nombre},
        headers=cuentas.admin.h,
    ).json()


def crear_grupo(client, cuentas, nombre="Soporte SAP"):
    return client.post(
        "/grupos",
        json={"nombre": nombre},
        headers=cuentas.admin.h,
    ).json()


def crear_agente(motor, email="agente2@test.com", nombre="Agente Dos"):
    TestingSession = sessionmaker(bind=motor)
    with TestingSession() as db:
        usuario = models.Usuario(
            email=email,
            nombre_completo=nombre,
            password_hash="hash",
            rol="agente",
        )
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
        return usuario.id


def anadir_miembro(client, cuentas, grupo_id, usuario_id):
    respuesta = client.post(
        f"/grupos/{grupo_id}/miembros/{usuario_id}",
        headers=cuentas.admin.h,
    )
    assert respuesta.status_code == 201, respuesta.text


def crear_regla(client, cuentas, condiciones, acciones, **extra):
    respuesta = client.post(
        "/reglas",
        json={
            "nombre": extra.pop("nombre", "Regla SAP"),
            "condiciones": condiciones,
            "acciones": acciones,
            **extra,
        },
        headers=cuentas.admin.h,
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def crear_ticket(client, cuentas, **extra):
    respuesta = client.post(
        "/incidencias",
        json={"titulo": "Ticket automatizado", **extra},
        headers=cuentas.solicitante.h,
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def test_round_robin_reparte_entre_agentes_del_grupo(client, cuentas, motor):
    categoria = crear_categoria(client, cuentas)
    grupo = crear_grupo(client, cuentas)
    agente2_id = crear_agente(motor)
    anadir_miembro(client, cuentas, grupo["id"], cuentas.agente.id)
    anadir_miembro(client, cuentas, grupo["id"], agente2_id)

    crear_regla(
        client,
        cuentas,
        [{"campo": "categoria_id", "operador": "=", "valor": categoria["id"]}],
        {"grupo_id": grupo["id"], "auto_asignar": "round_robin"},
    )

    primero = crear_ticket(client, cuentas, categoria_id=categoria["id"])
    segundo = crear_ticket(client, cuentas, categoria_id=categoria["id"])

    assert primero["grupo_asignado_id"] == grupo["id"]
    assert primero["agente_asignado_id"] == cuentas.agente.id
    assert primero["estado"] == "En progreso"
    assert segundo["agente_asignado_id"] == agente2_id

    historial = client.get(
        f"/incidencias/{primero['id']}/historial",
        headers=cuentas.admin.h,
    ).json()
    acciones = {evento["accion"] for evento in historial}
    assert "regla_aplicada" in acciones
    assert "auto_asignacion" in acciones
    assert "regla_automatizacion" in acciones


def test_load_balanced_elige_al_agente_con_menos_tickets(client, cuentas, motor):
    categoria = crear_categoria(client, cuentas)
    grupo = crear_grupo(client, cuentas)
    agente2_id = crear_agente(motor)
    anadir_miembro(client, cuentas, grupo["id"], cuentas.agente.id)
    anadir_miembro(client, cuentas, grupo["id"], agente2_id)

    ocupado = client.post(
        "/incidencias",
        json={"titulo": "Ticket ya abierto", "grupo_asignado_id": grupo["id"]},
        headers=cuentas.admin.h,
    ).json()
    client.post(
        f"/incidencias/{ocupado['id']}/asignar",
        json={"agente_id": cuentas.agente.id},
        headers=cuentas.admin.h,
    )

    crear_regla(
        client,
        cuentas,
        [{"campo": "categoria_id", "operador": "=", "valor": categoria["id"]}],
        {"grupo_id": grupo["id"], "auto_asignar": "load_balanced"},
    )

    nuevo = crear_ticket(client, cuentas, categoria_id=categoria["id"])
    assert nuevo["agente_asignado_id"] == agente2_id


def test_regla_con_logica_or(client, cuentas, motor):
    categoria = crear_categoria(client, cuentas)
    grupo = crear_grupo(client, cuentas)
    anadir_miembro(client, cuentas, grupo["id"], cuentas.agente.id)

    crear_regla(
        client,
        cuentas,
        [
            {"campo": "categoria_id", "operador": "=", "valor": categoria["id"]},
            {"campo": "impacto", "operador": "=", "valor": "Alto"},
        ],
        {"grupo_id": grupo["id"], "auto_asignar": "round_robin"},
        logica="OR",
    )

    ticket = crear_ticket(client, cuentas, categoria_id=categoria["id"])
    assert ticket["grupo_asignado_id"] == grupo["id"]
    assert ticket["agente_asignado_id"] == cuentas.agente.id


def test_regla_con_logica_and_no_coincide(client, cuentas):
    categoria = crear_categoria(client, cuentas)
    grupo = crear_grupo(client, cuentas)
    anadir_miembro(client, cuentas, grupo["id"], cuentas.agente.id)

    crear_regla(
        client,
        cuentas,
        [
            {"campo": "categoria_id", "operador": "=", "valor": categoria["id"]},
            {"campo": "impacto", "operador": "=", "valor": "Alto"},
        ],
        {"grupo_id": grupo["id"], "auto_asignar": "round_robin"},
        logica="AND",
    )

    ticket = crear_ticket(client, cuentas, categoria_id=categoria["id"])
    assert ticket["grupo_asignado_id"] is None
    assert ticket["agente_asignado_id"] is None


def test_regla_inactiva_no_se_aplica(client, cuentas):
    grupo = crear_grupo(client, cuentas)
    anadir_miembro(client, cuentas, grupo["id"], cuentas.agente.id)

    crear_regla(
        client,
        cuentas,
        [],
        {"grupo_id": grupo["id"], "auto_asignar": "round_robin"},
        activa=False,
    )

    ticket = crear_ticket(client, cuentas)
    assert ticket["grupo_asignado_id"] is None
    assert ticket["agente_asignado_id"] is None


def test_la_ultima_regla_por_orden_gana(client, cuentas):
    grupo1 = crear_grupo(client, cuentas, "Nivel 1")
    grupo2 = crear_grupo(client, cuentas, "Nivel 2")
    anadir_miembro(client, cuentas, grupo1["id"], cuentas.agente.id)
    anadir_miembro(client, cuentas, grupo2["id"], cuentas.agente.id)

    crear_regla(
        client,
        cuentas,
        [],
        {"grupo_id": grupo1["id"]},
        nombre="Primera",
        orden=1,
    )
    crear_regla(
        client,
        cuentas,
        [],
        {"grupo_id": grupo2["id"]},
        nombre="Segunda",
        orden=2,
    )

    ticket = crear_ticket(client, cuentas)
    assert ticket["grupo_asignado_id"] == grupo2["id"]


def test_cambiar_categoria_reevalua_reglas(client, cuentas):
    categoria = crear_categoria(client, cuentas)
    grupo = crear_grupo(client, cuentas)
    anadir_miembro(client, cuentas, grupo["id"], cuentas.agente.id)

    crear_regla(
        client,
        cuentas,
        [{"campo": "categoria_id", "operador": "=", "valor": categoria["id"]}],
        {"grupo_id": grupo["id"], "auto_asignar": "round_robin"},
    )

    ticket = crear_ticket(client, cuentas)
    assert ticket["grupo_asignado_id"] is None

    actualizado = client.patch(
        f"/incidencias/{ticket['id']}",
        json={"categoria_id": categoria["id"]},
        headers=cuentas.agente.h,
    )
    assert actualizado.status_code == 200
    assert actualizado.json()["grupo_asignado_id"] == grupo["id"]
    assert actualizado.json()["agente_asignado_id"] == cuentas.agente.id


def test_endpoint_manual_de_aplicar_reglas(client, cuentas):
    grupo = crear_grupo(client, cuentas)
    anadir_miembro(client, cuentas, grupo["id"], cuentas.agente.id)
    regla = crear_regla(
        client,
        cuentas,
        [],
        {"grupo_id": grupo["id"], "auto_asignar": "round_robin"},
        activa=False,
    )

    ticket = client.post(
        "/incidencias",
        json={"titulo": "Se crea sin reglas activas"},
        headers=cuentas.solicitante.h,
    ).json()
    assert ticket["grupo_asignado_id"] is None

    # Se reactiva la regla y se fuerza la reevaluación a mano
    client.patch(
        f"/reglas/{regla['id']}",
        json={"activa": True},
        headers=cuentas.admin.h,
    )
    respuesta = client.post(
        f"/incidencias/{ticket['id']}/aplicar-reglas",
        headers=cuentas.admin.h,
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["grupo_asignado_id"] == grupo["id"]
    assert respuesta.json()["agente_asignado_id"] == cuentas.agente.id


def test_solo_administrador_gestiona_reglas(client, cuentas):
    listado = client.get("/reglas", headers=cuentas.agente.h)
    assert listado.status_code == 403

    listado_admin = client.get("/reglas", headers=cuentas.admin.h)
    assert listado_admin.status_code == 200


def test_regla_con_grupo_inexistente_falla(client, cuentas):
    respuesta = client.post(
        "/reglas",
        json={
            "nombre": "Destino inválido",
            "condiciones": [],
            "acciones": {"grupo_id": 9999},
        },
        headers=cuentas.admin.h,
    )
    assert respuesta.status_code == 404


def test_historial_empieza_por_la_creacion(client, cuentas):
    grupo = crear_grupo(client, cuentas)
    anadir_miembro(client, cuentas, grupo["id"], cuentas.agente.id)
    crear_regla(
        client,
        cuentas,
        [],
        {"grupo_id": grupo["id"], "auto_asignar": "load_balanced"},
    )

    ticket = crear_ticket(client, cuentas)
    historial = client.get(
        f"/incidencias/{ticket['id']}/historial",
        headers=cuentas.admin.h,
    ).json()
    assert historial[0]["accion"] == "creacion"


def test_editar_titulo_reevalua_reglas(client, cuentas):
    grupo = crear_grupo(client, cuentas)
    anadir_miembro(client, cuentas, grupo["id"], cuentas.agente.id)
    crear_regla(
        client,
        cuentas,
        [{"campo": "titulo", "operador": "contiene", "valor": "vpn"}],
        {"grupo_id": grupo["id"], "auto_asignar": "load_balanced"},
    )

    ticket = crear_ticket(client, cuentas, titulo="Consulta general")
    assert ticket["grupo_asignado_id"] is None

    actualizado = client.patch(
        f"/incidencias/{ticket['id']}",
        json={"titulo": "Fallo de VPN"},
        headers=cuentas.agente.h,
    )
    assert actualizado.status_code == 200
    assert actualizado.json()["grupo_asignado_id"] == grupo["id"]
    assert actualizado.json()["agente_asignado_id"] == cuentas.agente.id


def test_regla_con_grupo_borrado_no_rompe(client, cuentas, motor):
    grupo = crear_grupo(client, cuentas)
    crear_regla(client, cuentas, [], {"grupo_id": grupo["id"]})

    # Se borra el grupo directamente en la BD para simular una referencia obsoleta
    TestingSession = sessionmaker(bind=motor)
    with TestingSession() as db:
        db.delete(db.get(models.GrupoSoporte, grupo["id"]))
        db.commit()

    ticket = crear_ticket(client, cuentas)
    assert ticket["grupo_asignado_id"] is None
