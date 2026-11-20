def crear_categoria(client, cuentas, nombre="SAP", **extra):
    respuesta = client.post(
        "/categorias",
        json={"nombre": nombre, **extra},
        headers=cuentas.admin.h,
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def crear_grupo(client, cuentas, nombre="Soporte SAP", **extra):
    respuesta = client.post(
        "/grupos",
        json={"nombre": nombre, **extra},
        headers=cuentas.admin.h,
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def test_admin_crea_categoria_y_solicitante_la_consulta(client, cuentas):
    categoria = crear_categoria(client, cuentas, "Redes")

    respuesta = client.get("/categorias", headers=cuentas.solicitante.h)
    assert respuesta.status_code == 200
    assert [c["nombre"] for c in respuesta.json()] == ["Redes"]
    assert respuesta.json()[0]["id"] == categoria["id"]


def test_solicitante_no_puede_crear_categoria(client, cuentas):
    respuesta = client.post(
        "/categorias",
        json={"nombre": "No permitida"},
        headers=cuentas.solicitante.h,
    )
    assert respuesta.status_code == 403


def test_categoria_duplicada_devuelve_409(client, cuentas):
    crear_categoria(client, cuentas, "SAP")
    respuesta = client.post(
        "/categorias",
        json={"nombre": "SAP"},
        headers=cuentas.admin.h,
    )
    assert respuesta.status_code == 409


def test_categoria_padre_inexistente(client, cuentas):
    respuesta = client.post(
        "/categorias",
        json={"nombre": "Huérfana", "parent_id": 9999},
        headers=cuentas.admin.h,
    )
    assert respuesta.status_code == 404


def test_jerarquia_de_categorias(client, cuentas):
    padre = crear_categoria(client, cuentas, "Infraestructura")
    hija = crear_categoria(
        client, cuentas, "Redes", parent_id=padre["id"]
    )
    assert hija["parent_id"] == padre["id"]

    respuesta = client.patch(
        f"/categorias/{padre['id']}",
        json={"parent_id": hija["id"]},
        headers=cuentas.admin.h,
    )
    assert respuesta.status_code == 400


def test_admin_crea_grupo_y_gestiona_miembros(client, cuentas):
    grupo = crear_grupo(client, cuentas)

    respuesta = client.post(
        f"/grupos/{grupo['id']}/miembros/{cuentas.agente.id}",
        headers=cuentas.admin.h,
    )
    assert respuesta.status_code == 201
    datos = respuesta.json()
    assert [m["usuario_id"] for m in datos["miembros"]] == [cuentas.agente.id]
    assert datos["miembros"][0]["usuario"]["rol"] == "agente"

    duplicado = client.post(
        f"/grupos/{grupo['id']}/miembros/{cuentas.agente.id}",
        headers=cuentas.admin.h,
    )
    assert duplicado.status_code == 409

    eliminado = client.delete(
        f"/grupos/{grupo['id']}/miembros/{cuentas.agente.id}",
        headers=cuentas.admin.h,
    )
    assert eliminado.status_code == 200
    assert eliminado.json()["miembros"] == []


def test_solicitante_no_puede_ver_grupos(client, cuentas):
    respuesta = client.get("/grupos", headers=cuentas.solicitante.h)
    assert respuesta.status_code == 403


def test_no_se_puede_anadir_solicitante_a_un_grupo(client, cuentas):
    grupo = crear_grupo(client, cuentas)
    respuesta = client.post(
        f"/grupos/{grupo['id']}/miembros/{cuentas.solicitante.id}",
        headers=cuentas.admin.h,
    )
    assert respuesta.status_code == 400


def test_crear_ticket_con_categoria_y_grupo(client, cuentas):
    categoria = crear_categoria(client, cuentas, "SAP")
    grupo = crear_grupo(client, cuentas)

    respuesta = client.post(
        "/incidencias",
        json={
            "titulo": "Error en SAP",
            "descripcion": "No puedo entrar",
            "categoria_id": categoria["id"],
            "grupo_asignado_id": grupo["id"],
        },
        headers=cuentas.agente.h,
    )
    assert respuesta.status_code == 201
    datos = respuesta.json()
    assert datos["categoria_id"] == categoria["id"]
    assert datos["grupo_asignado_id"] == grupo["id"]


def test_solicitante_puede_elegir_categoria_pero_no_grupo(client, cuentas):
    categoria = crear_categoria(client, cuentas, "Software")
    grupo = crear_grupo(client, cuentas)

    respuesta = client.post(
        "/incidencias",
        json={
            "titulo": "Ayuda con Office",
            "categoria_id": categoria["id"],
            "grupo_asignado_id": grupo["id"],
        },
        headers=cuentas.solicitante.h,
    )
    assert respuesta.status_code == 201
    datos = respuesta.json()
    assert datos["categoria_id"] == categoria["id"]
    assert datos["grupo_asignado_id"] is None


def test_no_se_puede_usar_categoria_o_grupo_inactivos(client, cuentas):
    categoria = crear_categoria(client, cuentas, "Antigua", activa=False)
    grupo = crear_grupo(client, cuentas, "Antiguo", activo=False)

    por_categoria = client.post(
        "/incidencias",
        json={"titulo": "Prueba categoría", "categoria_id": categoria["id"]},
        headers=cuentas.solicitante.h,
    )
    assert por_categoria.status_code == 400

    por_grupo = client.post(
        "/incidencias",
        json={"titulo": "Prueba grupo", "grupo_asignado_id": grupo["id"]},
        headers=cuentas.agente.h,
    )
    assert por_grupo.status_code == 400


def test_filtros_por_categoria_y_grupo(client, cuentas):
    categoria = crear_categoria(client, cuentas, "Hardware")
    grupo = crear_grupo(client, cuentas)

    client.post(
        "/incidencias",
        json={
            "titulo": "Portátil roto",
            "categoria_id": categoria["id"],
            "grupo_asignado_id": grupo["id"],
        },
        headers=cuentas.agente.h,
    )
    client.post(
        "/incidencias",
        json={"titulo": "Otro ticket"},
        headers=cuentas.agente.h,
    )

    por_categoria = client.get(
        f"/incidencias?categoria_id={categoria['id']}",
        headers=cuentas.agente.h,
    )
    assert len(por_categoria.json()) == 1

    por_grupo = client.get(
        f"/incidencias?grupo_asignado_id={grupo['id']}",
        headers=cuentas.agente.h,
    )
    assert len(por_grupo.json()) == 1

    sin_grupo = client.get(
        "/incidencias?sin_grupo=true", headers=cuentas.agente.h
    )
    assert len(sin_grupo.json()) == 1


def test_asignar_tecnico_fuera_del_grupo_falla(client, cuentas, motor):
    from sqlalchemy.orm import sessionmaker

    from app import models

    grupo = crear_grupo(client, cuentas)
    client.post(
        f"/grupos/{grupo['id']}/miembros/{cuentas.agente.id}",
        headers=cuentas.admin.h,
    )

    TestingSession = sessionmaker(bind=motor)
    with TestingSession() as db:
        otro_agente = models.Usuario(
            email="agente2@test.com",
            nombre_completo="Agente Dos",
            password_hash="hash",
            rol="agente",
        )
        db.add(otro_agente)
        db.commit()
        db.refresh(otro_agente)
        otro_id = otro_agente.id

    ticket = client.post(
        "/incidencias",
        json={"titulo": "Ticket con grupo", "grupo_asignado_id": grupo["id"]},
        headers=cuentas.admin.h,
    ).json()

    respuesta = client.post(
        f"/incidencias/{ticket['id']}/asignar",
        json={"agente_id": otro_id},
        headers=cuentas.admin.h,
    )
    assert respuesta.status_code == 400
    assert "no pertenece al grupo" in respuesta.json()["detail"]

    valida = client.post(
        f"/incidencias/{ticket['id']}/asignar",
        json={"agente_id": cuentas.agente.id},
        headers=cuentas.admin.h,
    )
    assert valida.status_code == 200
    assert valida.json()["agente_asignado_id"] == cuentas.agente.id


def test_eliminar_grupo_sin_uso(client, cuentas):
    grupo = crear_grupo(client, cuentas)

    respuesta = client.delete(f"/grupos/{grupo['id']}", headers=cuentas.admin.h)
    assert respuesta.status_code == 204

    listado = client.get(
        "/grupos?incluir_inactivos=true", headers=cuentas.admin.h
    )
    assert listado.json() == []

    repetido = client.delete(f"/grupos/{grupo['id']}", headers=cuentas.admin.h)
    assert repetido.status_code == 404


def test_no_eliminar_grupo_con_tickets(client, cuentas):
    grupo = crear_grupo(client, cuentas)
    client.post(
        "/incidencias",
        json={"titulo": "Ticket del grupo", "grupo_asignado_id": grupo["id"]},
        headers=cuentas.agente.h,
    )

    respuesta = client.delete(f"/grupos/{grupo['id']}", headers=cuentas.admin.h)
    assert respuesta.status_code == 409
    assert "incidencia" in respuesta.json()["detail"]


def test_no_eliminar_grupo_usado_por_regla(client, cuentas):
    grupo = crear_grupo(client, cuentas)
    client.post(
        "/reglas",
        json={
            "nombre": "Regla con grupo",
            "condiciones": [],
            "acciones": {"grupo_id": grupo["id"]},
        },
        headers=cuentas.admin.h,
    )

    respuesta = client.delete(f"/grupos/{grupo['id']}", headers=cuentas.admin.h)
    assert respuesta.status_code == 409
    assert "regla" in respuesta.json()["detail"]


def test_eliminar_categoria_sin_uso(client, cuentas):
    categoria = crear_categoria(client, cuentas, "Temporal")

    respuesta = client.delete(
        f"/categorias/{categoria['id']}", headers=cuentas.admin.h
    )
    assert respuesta.status_code == 204
    assert client.get("/categorias", headers=cuentas.admin.h).json() == []


def test_no_eliminar_categoria_con_tickets(client, cuentas):
    categoria = crear_categoria(client, cuentas, "Con tickets")
    client.post(
        "/incidencias",
        json={"titulo": "Ticket categorizado", "categoria_id": categoria["id"]},
        headers=cuentas.solicitante.h,
    )

    respuesta = client.delete(
        f"/categorias/{categoria['id']}", headers=cuentas.admin.h
    )
    assert respuesta.status_code == 409
    assert "incidencia" in respuesta.json()["detail"]


def test_no_eliminar_categoria_con_subcategorias(client, cuentas):
    padre = crear_categoria(client, cuentas, "Padre")
    crear_categoria(client, cuentas, "Hija", parent_id=padre["id"])

    respuesta = client.delete(
        f"/categorias/{padre['id']}", headers=cuentas.admin.h
    )
    assert respuesta.status_code == 409
    assert "subcategor" in respuesta.json()["detail"]


def test_no_eliminar_categoria_usada_por_regla(client, cuentas):
    categoria = crear_categoria(client, cuentas, "Usada")
    client.post(
        "/reglas",
        json={
            "nombre": "Regla con categoría",
            "condiciones": [
                {
                    "campo": "categoria_id",
                    "operador": "=",
                    "valor": categoria["id"],
                }
            ],
            "acciones": {},
        },
        headers=cuentas.admin.h,
    )

    respuesta = client.delete(
        f"/categorias/{categoria['id']}", headers=cuentas.admin.h
    )
    assert respuesta.status_code == 409
    assert "regla" in respuesta.json()["detail"]


def test_no_se_pueden_dejar_campos_obligatorios_nulos(client, cuentas):
    categoria = crear_categoria(client, cuentas, "Categoría")
    grupo = crear_grupo(client, cuentas, "Grupo")
    regla = client.post(
        "/reglas",
        json={"nombre": "Regla válida", "condiciones": [], "acciones": {}},
        headers=cuentas.admin.h,
    ).json()

    por_categoria = client.patch(
        f"/categorias/{categoria['id']}",
        json={"activa": None},
        headers=cuentas.admin.h,
    )
    assert por_categoria.status_code == 400

    por_grupo = client.patch(
        f"/grupos/{grupo['id']}",
        json={"nombre": None},
        headers=cuentas.admin.h,
    )
    assert por_grupo.status_code == 400

    por_regla = client.patch(
        f"/reglas/{regla['id']}",
        json={"orden": None},
        headers=cuentas.admin.h,
    )
    assert por_regla.status_code == 400


def test_nombres_solo_con_espacios_se_rechazan(client, cuentas):
    respuesta = client.post(
        "/grupos",
        json={"nombre": "   "},
        headers=cuentas.admin.h,
    )
    assert respuesta.status_code == 422

    categoria = crear_categoria(client, cuentas, "Original")
    cambio = client.patch(
        f"/categorias/{categoria['id']}",
        json={"nombre": "  "},
        headers=cuentas.admin.h,
    )
    assert cambio.status_code == 422
