"""Bloqueo optimista: dos agentes sobre el mismo ticket."""

def crear(client, cabeceras):
    return client.post(
        "/incidencias",
        json={"titulo": "Servidor lento", "descripcion": "tarda en responder"},
        headers=cabeceras,
    ).json()


def test_la_incidencia_expone_su_version(client, cuentas):
    ticket = crear(client, cuentas.solicitante.h)

    assert ticket["version"] == 1


def test_sin_version_la_actualizacion_sigue_funcionando(client, cuentas):
    ticket = crear(client, cuentas.solicitante.h)

    respuesta = client.patch(
        f"/incidencias/{ticket['id']}",
        json={"estado": "En progreso"},
        headers=cuentas.agente.h,
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["version"] == 2


def test_con_la_version_correcta_se_actualiza(client, cuentas):
    ticket = crear(client, cuentas.solicitante.h)

    respuesta = client.patch(
        f"/incidencias/{ticket['id']}",
        json={"estado": "En progreso", "version": 1},
        headers=cuentas.agente.h,
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "En progreso"


def test_con_version_obsoleta_se_rechaza(client, cuentas):
    ticket = crear(client, cuentas.solicitante.h)
    client.patch(
        f"/incidencias/{ticket['id']}",
        json={"estado": "En progreso"},
        headers=cuentas.agente.h,
    )

    respuesta = client.patch(
        f"/incidencias/{ticket['id']}",
        json={"urgencia": "Alta", "version": 1},
        headers=cuentas.agente.h,
    )

    assert respuesta.status_code == 409


def test_el_rechazo_no_modifica_nada(client, cuentas):
    ticket = crear(client, cuentas.solicitante.h)
    client.patch(
        f"/incidencias/{ticket['id']}",
        json={"estado": "En progreso"},
        headers=cuentas.agente.h,
    )

    client.patch(
        f"/incidencias/{ticket['id']}",
        json={"urgencia": "Alta", "version": 1},
        headers=cuentas.agente.h,
    )
    detalle = client.get(
        f"/incidencias/{ticket['id']}", headers=cuentas.agente.h
    ).json()

    assert detalle["urgencia"] == "Media"
    assert detalle["version"] == 2
