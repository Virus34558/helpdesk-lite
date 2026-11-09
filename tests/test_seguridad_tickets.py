def test_solicitante_no_puede_crear_problemas_ni_cambios(client, cuentas):
    for tipo in ("Problema", "Cambio"):
        respuesta = client.post(
            "/incidencias",
            json={"titulo": "Intento de colarse", "tipo": tipo},
            headers=cuentas.solicitante.h,
        )
        assert respuesta.status_code == 403


def test_solicitante_puede_crear_solicitud_de_servicio(client, cuentas):
    respuesta = client.post(
        "/incidencias",
        json={"titulo": "Necesito un portátil", "tipo": "Solicitud de Servicio"},
        headers=cuentas.solicitante.h,
    )
    assert respuesta.status_code == 201
    assert respuesta.json()["id_legible"].startswith("REQ-")


def test_solicitante_no_puede_falsear_el_canal_de_origen(client, cuentas):
    respuesta = client.post(
        "/incidencias",
        json={"titulo": "Canal falso", "canal_origen": "Email"},
        headers=cuentas.solicitante.h,
    )
    assert respuesta.status_code == 201
    assert respuesta.json()["canal_origen"] == "Portal Web"


def test_solicitante_no_ve_incidencia_ajena_por_codigo_legible(client, cuentas):
    ajena = client.post(
        "/incidencias", json={"titulo": "Incidencia ajena"}, headers=cuentas.otro.h
    ).json()
    codigo = ajena["id_legible"]
    assert client.get(f"/incidencias/{codigo}", headers=cuentas.otro.h).status_code == 200
    assert client.get(f"/incidencias/{codigo}", headers=cuentas.solicitante.h).status_code == 404


def test_codigos_legibles_unicos_y_con_prefijo(client, cuentas):
    codigos = []
    for tipo in ("Incidencia", "Solicitud de Servicio", "Incidencia"):
        respuesta = client.post(
            "/incidencias",
            json={"titulo": "Prueba de codigo", "tipo": tipo},
            headers=cuentas.agente.h,
        )
        codigos.append(respuesta.json()["id_legible"])
    assert len(set(codigos)) == 3
    assert codigos[0].startswith("INC-")
    assert codigos[1].startswith("REQ-")
    assert codigos[2].startswith("INC-")