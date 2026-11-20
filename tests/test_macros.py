"""Plantillas de respuesta reutilizables para agentes."""

PLANTILLA = {
    "nombre": "Saludo inicial",
    "texto": "Hola, hemos recibido tu incidencia y la estamos revisando.",
}


def crear(client, cabeceras, **cambios):
    return client.post("/macros", json=PLANTILLA | cambios, headers=cabeceras)


def test_el_admin_crea_una_plantilla(client, cuentas):
    respuesta = crear(client, cuentas.admin.h)

    assert respuesta.status_code == 201
    assert respuesta.json()["nombre"] == "Saludo inicial"


def test_el_agente_puede_listarlas(client, cuentas):
    crear(client, cuentas.admin.h)

    listado = client.get("/macros", headers=cuentas.agente.h)

    assert listado.status_code == 200
    assert [m["nombre"] for m in listado.json()] == ["Saludo inicial"]


def test_el_solicitante_no_las_ve(client, cuentas):
    respuesta = client.get("/macros", headers=cuentas.solicitante.h)

    assert respuesta.status_code == 403


def test_solo_el_admin_crea_plantillas(client, cuentas):
    respuesta = crear(client, cuentas.agente.h)

    assert respuesta.status_code == 403


def test_el_nombre_no_se_repite(client, cuentas):
    crear(client, cuentas.admin.h)

    respuesta = crear(client, cuentas.admin.h)

    assert respuesta.status_code == 409


def test_se_puede_actualizar_el_texto(client, cuentas):
    plantilla = crear(client, cuentas.admin.h).json()

    respuesta = client.patch(
        f"/macros/{plantilla['id']}",
        json={"texto": "Hola de nuevo, seguimos con ello."},
        headers=cuentas.admin.h,
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["texto"] == "Hola de nuevo, seguimos con ello."


def test_las_inactivas_no_se_listan(client, cuentas):
    crear(client, cuentas.admin.h, activa=False)

    listado = client.get("/macros", headers=cuentas.agente.h)

    assert listado.json() == []


def test_se_puede_eliminar(client, cuentas):
    plantilla = crear(client, cuentas.admin.h).json()

    borrado = client.delete(f"/macros/{plantilla['id']}", headers=cuentas.admin.h)
    listado = client.get("/macros", headers=cuentas.agente.h)

    assert borrado.status_code == 204
    assert listado.json() == []
