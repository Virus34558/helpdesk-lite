"""Fusión de tickets duplicados (RF-2.4)."""

def crear(client, cabeceras, titulo):
    return client.post(
        "/incidencias",
        json={"titulo": titulo, "descripcion": "detalle"},
        headers=cabeceras,
    ).json()


def comentar(client, cabeceras, ticket_id, texto, interno=False):
    return client.post(
        f"/incidencias/{ticket_id}/comentarios",
        json={"contenido": texto, "es_interno": interno},
        headers=cabeceras,
    ).json()


def fusionar(client, cabeceras, principal_id, secundario_id, nota=None):
    cuerpo = {"nota": nota} if nota else {}
    return client.post(
        f"/incidencias/{principal_id}/fusionar/{secundario_id}",
        json=cuerpo,
        headers=cabeceras,
    )


def test_el_secundario_queda_cerrado_con_nota_de_fusion(client, cuentas):
    principal = crear(client, cuentas.solicitante.h, "ERP caído")
    secundario = crear(client, cuentas.solicitante.h, "ERP no responde")

    respuesta = fusionar(client, cuentas.agente.h, principal["id"], secundario["id"])

    assert respuesta.status_code == 200
    detalle = client.get(
        f"/incidencias/{secundario['id']}", headers=cuentas.agente.h
    ).json()
    assert detalle["estado"] == "Cerrado"
    assert principal["id_legible"] in detalle["nota_resolucion"]


def test_los_comentarios_se_copian_en_orden(client, cuentas):
    principal = crear(client, cuentas.solicitante.h, "ERP caído")
    secundario = crear(client, cuentas.solicitante.h, "ERP no responde")
    comentar(client, cuentas.solicitante.h, secundario["id"], "primero")
    comentar(client, cuentas.agente.h, secundario["id"], "nota interna", interno=True)

    fusionar(client, cuentas.agente.h, principal["id"], secundario["id"])

    hilo = client.get(
        f"/incidencias/{principal['id']}/comentarios", headers=cuentas.agente.h
    ).json()
    assert [c["contenido"] for c in hilo] == ["primero", "nota interna"]
    assert hilo[1]["es_interno"] is True


def test_los_adjuntos_pasan_al_principal(client, cuentas):
    principal = crear(client, cuentas.solicitante.h, "ERP caído")
    secundario = crear(client, cuentas.solicitante.h, "ERP no responde")
    client.post(
        f"/incidencias/{secundario['id']}/adjuntos",
        files={"archivo": ("log.txt", b"error 500", "text/plain")},
        headers=cuentas.solicitante.h,
    )

    fusionar(client, cuentas.agente.h, principal["id"], secundario["id"])

    del_principal = client.get(
        f"/incidencias/{principal['id']}/adjuntos", headers=cuentas.solicitante.h
    ).json()
    del_secundario = client.get(
        f"/incidencias/{secundario['id']}/adjuntos", headers=cuentas.solicitante.h
    ).json()
    assert [a["nombre_original"] for a in del_principal] == ["log.txt"]
    assert del_secundario == []


def test_los_observadores_pasan_sin_duplicarse(client, cuentas):
    principal = crear(client, cuentas.solicitante.h, "ERP caído")
    secundario = crear(client, cuentas.solicitante.h, "ERP no responde")
    for ticket, email in (
        (principal, "jefe@empresa.com"),
        (secundario, "jefe@empresa.com"),
        (secundario, "compras@empresa.com"),
    ):
        client.post(
            f"/incidencias/{ticket['id']}/observadores",
            json={"email": email},
            headers=cuentas.solicitante.h,
        )

    fusionar(client, cuentas.agente.h, principal["id"], secundario["id"])

    observadores = client.get(
        f"/incidencias/{principal['id']}/observadores", headers=cuentas.solicitante.h
    ).json()
    assert sorted(o["email"] for o in observadores) == [
        "compras@empresa.com",
        "jefe@empresa.com",
    ]


def test_la_fusion_queda_en_la_auditoria_de_ambos(client, cuentas):
    principal = crear(client, cuentas.solicitante.h, "ERP caído")
    secundario = crear(client, cuentas.solicitante.h, "ERP no responde")

    fusionar(client, cuentas.agente.h, principal["id"], secundario["id"])

    for ticket, otro in ((principal, secundario), (secundario, principal)):
        historial = client.get(
            f"/incidencias/{ticket['id']}/historial", headers=cuentas.agente.h
        ).json()
        eventos = [e for e in historial if e["accion"] == "fusion"]
        assert len(eventos) == 1
        assert otro["id_legible"] in (eventos[0]["valor_nuevo"] or "")


def test_no_se_puede_fusionar_un_ticket_cerrado(client, cuentas):
    principal = crear(client, cuentas.solicitante.h, "ERP caído")
    secundario = crear(client, cuentas.solicitante.h, "ERP no responde")
    fusionar(client, cuentas.agente.h, principal["id"], secundario["id"])

    respuesta = fusionar(client, cuentas.agente.h, principal["id"], secundario["id"])

    assert respuesta.status_code == 409


def test_no_se_puede_fusionar_consigo_mismo(client, cuentas):
    principal = crear(client, cuentas.solicitante.h, "ERP caído")

    respuesta = fusionar(client, cuentas.agente.h, principal["id"], principal["id"])

    assert respuesta.status_code == 400


def test_un_solicitante_no_puede_fusionar(client, cuentas):
    principal = crear(client, cuentas.solicitante.h, "ERP caído")
    secundario = crear(client, cuentas.solicitante.h, "ERP no responde")

    respuesta = fusionar(
        client, cuentas.solicitante.h, principal["id"], secundario["id"]
    )

    assert respuesta.status_code == 403
