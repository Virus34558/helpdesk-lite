"""Encuesta de satisfacción (CSAT) al cerrar una incidencia."""


def crear(client, cabeceras, titulo="Impresora rota"):
    return client.post(
        "/incidencias",
        json={"titulo": titulo, "descripcion": "no imprime"},
        headers=cabeceras,
    ).json()


def resolver(client, cuentas, ticket_id):
    client.patch(
        f"/incidencias/{ticket_id}",
        json={"estado": "En progreso"},
        headers=cuentas.agente.h,
    )
    return client.post(
        f"/incidencias/{ticket_id}/resolver",
        json={"nota_resolucion": "Se sustituyó el tóner"},
        headers=cuentas.agente.h,
    )


def test_el_solicitante_valora_una_incidencia_resuelta(client, cuentas):
    ticket = crear(client, cuentas.solicitante.h)
    resolver(client, cuentas, ticket["id"])

    respuesta = client.post(
        f"/incidencias/{ticket['id']}/csat",
        json={"puntuacion": 5, "comentario": "Rapidísimos"},
        headers=cuentas.solicitante.h,
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["puntuacion"] == 5
    assert respuesta.json()["comentario"] == "Rapidísimos"


def test_la_valoracion_aparece_en_la_incidencia(client, cuentas):
    ticket = crear(client, cuentas.solicitante.h)
    resolver(client, cuentas, ticket["id"])
    client.post(
        f"/incidencias/{ticket['id']}/csat",
        json={"puntuacion": 4},
        headers=cuentas.solicitante.h,
    )

    detalle = client.get(
        f"/incidencias/{ticket['id']}", headers=cuentas.solicitante.h
    ).json()

    assert detalle["csat_puntuacion"] == 4


def test_no_se_puede_valorar_antes_de_resolver(client, cuentas):
    ticket = crear(client, cuentas.solicitante.h)

    respuesta = client.post(
        f"/incidencias/{ticket['id']}/csat",
        json={"puntuacion": 5},
        headers=cuentas.solicitante.h,
    )

    assert respuesta.status_code == 409


def test_solo_responde_el_solicitante_dueno(client, cuentas):
    ticket = crear(client, cuentas.solicitante.h)
    resolver(client, cuentas, ticket["id"])

    respuesta = client.post(
        f"/incidencias/{ticket['id']}/csat",
        json={"puntuacion": 3},
        headers=cuentas.agente.h,
    )

    assert respuesta.status_code == 403


def test_no_se_puede_valorar_dos_veces(client, cuentas):
    ticket = crear(client, cuentas.solicitante.h)
    resolver(client, cuentas, ticket["id"])
    client.post(
        f"/incidencias/{ticket['id']}/csat",
        json={"puntuacion": 5},
        headers=cuentas.solicitante.h,
    )

    respuesta = client.post(
        f"/incidencias/{ticket['id']}/csat",
        json={"puntuacion": 1},
        headers=cuentas.solicitante.h,
    )

    assert respuesta.status_code == 409


def test_puntuacion_fuera_de_rango(client, cuentas):
    ticket = crear(client, cuentas.solicitante.h)
    resolver(client, cuentas, ticket["id"])

    for puntuacion in (0, 6):
        respuesta = client.post(
            f"/incidencias/{ticket['id']}/csat",
            json={"puntuacion": puntuacion},
            headers=cuentas.solicitante.h,
        )
        assert respuesta.status_code == 422


def test_los_kpis_incluyen_la_media_de_csat(client, cuentas):
    for puntuacion in (4, 2):
        ticket = crear(client, cuentas.solicitante.h, f"Ticket {puntuacion}")
        resolver(client, cuentas, ticket["id"])
        client.post(
            f"/incidencias/{ticket['id']}/csat",
            json={"puntuacion": puntuacion},
            headers=cuentas.solicitante.h,
        )

    kpis = client.get("/reportes/kpis", headers=cuentas.agente.h)

    assert kpis.status_code == 403  # el agente no puede ver KPIs

    kpis = client.get("/reportes/kpis", headers=cuentas.admin.h).json()
    assert kpis["csat_respuestas"] == 2
    assert kpis["csat_media"] == 3.0
