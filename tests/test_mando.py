"""Resumen ligero de la cola para la cabecera de mando."""

def crear(client, cabeceras, titulo="Fallo"):
    return client.post(
        "/incidencias", json={"titulo": titulo, "descripcion": "detalle"}, headers=cabeceras
    ).json()


def test_el_agente_ve_los_totales_de_la_cola(client, cuentas):
    crear(client, cuentas.solicitante.h, "Uno")
    crear(client, cuentas.solicitante.h, "Dos")

    resumen = client.get("/incidencias/resumen", headers=cuentas.agente.h)

    assert resumen.status_code == 200
    assert resumen.json()["abiertos"] == 2


def test_el_solicitante_solo_cuenta_los_suyos(client, cuentas):
    crear(client, cuentas.solicitante.h, "Mia")
    crear(client, cuentas.otro.h, "Ajena")

    resumen = client.get("/incidencias/resumen", headers=cuentas.solicitante.h)

    assert resumen.json()["abiertos"] == 1


def test_un_ticket_resuelto_sale_de_abiertos(client, cuentas):
    ticket = crear(client, cuentas.solicitante.h)
    client.patch(
        f"/incidencias/{ticket['id']}",
        json={"estado": "En progreso"},
        headers=cuentas.agente.h,
    )
    client.post(
        f"/incidencias/{ticket['id']}/resolver",
        json={"nota_resolucion": "Reiniciado el servicio"},
        headers=cuentas.agente.h,
    )

    resumen = client.get("/incidencias/resumen", headers=cuentas.agente.h).json()

    assert resumen["abiertos"] == 0


def test_la_ruta_no_tapa_el_detalle_por_codigo(client, cuentas):
    ticket = crear(client, cuentas.solicitante.h, "Sigue accesible")

    detalle = client.get(f"/incidencias/{ticket['id']}", headers=cuentas.solicitante.h)

    assert detalle.status_code == 200
    assert detalle.json()["titulo"] == "Sigue accesible"


def test_sin_sesion_no_hay_resumen(client):
    assert client.get("/incidencias/resumen").status_code == 401
