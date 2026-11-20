"""Paginación y búsqueda del listado de incidencias."""

def crear(client, cabeceras, titulo, descripcion="Sin detalle"):
    respuesta = client.post(
        "/incidencias",
        json={"titulo": titulo, "descripcion": descripcion},
        headers=cabeceras,
    )
    assert respuesta.status_code == 201
    return respuesta.json()


def test_limite_recorta_el_listado(client, cuentas):
    for titulo in ("Uno", "Dos", "Tres"):
        crear(client, cuentas.solicitante.h, titulo)

    respuesta = client.get("/incidencias?limite=2", headers=cuentas.solicitante.h)

    assert respuesta.status_code == 200
    assert len(respuesta.json()) == 2


def test_el_total_llega_en_la_cabecera(client, cuentas):
    for titulo in ("Uno", "Dos", "Tres"):
        crear(client, cuentas.solicitante.h, titulo)

    respuesta = client.get("/incidencias?limite=1", headers=cuentas.solicitante.h)

    assert respuesta.headers["X-Total-Count"] == "3"


def test_desplazamiento_salta_los_primeros(client, cuentas):
    for titulo in ("Uno", "Dos", "Tres"):
        crear(client, cuentas.solicitante.h, titulo)

    respuesta = client.get(
        "/incidencias?limite=2&desplazamiento=2", headers=cuentas.solicitante.h
    )

    assert [t["titulo"] for t in respuesta.json()] == ["Uno"]


def test_busqueda_por_titulo(client, cuentas):
    crear(client, cuentas.solicitante.h, "La impresora no imprime")
    crear(client, cuentas.solicitante.h, "Teclado roto")

    respuesta = client.get("/incidencias?q=impresora", headers=cuentas.solicitante.h)

    assert [t["titulo"] for t in respuesta.json()] == ["La impresora no imprime"]


def test_busqueda_por_descripcion(client, cuentas):
    crear(client, cuentas.solicitante.h, "Incidencia A", "falla la VPN")
    crear(client, cuentas.solicitante.h, "Incidencia B", "todo correcto")

    respuesta = client.get("/incidencias?q=vpn", headers=cuentas.solicitante.h)

    assert [t["titulo"] for t in respuesta.json()] == ["Incidencia A"]


def test_busqueda_por_codigo_legible(client, cuentas):
    creada = crear(client, cuentas.solicitante.h, "Solo esta")

    respuesta = client.get(
        f"/incidencias?q={creada['id_legible']}", headers=cuentas.solicitante.h
    )

    assert [t["id_legible"] for t in respuesta.json()] == [creada["id_legible"]]


def test_el_total_respeta_la_busqueda(client, cuentas):
    crear(client, cuentas.solicitante.h, "La impresora no imprime")
    crear(client, cuentas.solicitante.h, "Teclado roto")

    respuesta = client.get("/incidencias?q=impresora", headers=cuentas.solicitante.h)

    assert respuesta.headers["X-Total-Count"] == "1"


def test_el_solicitante_solo_cuenta_las_suyas(client, cuentas):
    crear(client, cuentas.solicitante.h, "Mia")
    crear(client, cuentas.otro.h, "Ajena")

    respuesta = client.get("/incidencias?limite=10", headers=cuentas.solicitante.h)

    assert respuesta.headers["X-Total-Count"] == "1"


def test_limite_fuera_de_rango_se_rechaza(client, cuentas):
    assert (
        client.get("/incidencias?limite=0", headers=cuentas.solicitante.h).status_code
        == 422
    )
    assert (
        client.get("/incidencias?limite=500", headers=cuentas.solicitante.h).status_code
        == 422
    )
