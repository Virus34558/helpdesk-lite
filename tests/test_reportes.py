from datetime import date


def crear_ticket(client, cuentas, **extra):
    respuesta = client.post(
        "/incidencias",
        json={"titulo": "Ticket de prueba", **extra},
        headers=cuentas.solicitante.h,
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def resolver_ticket(client, cuentas, ticket_id):
    asignado = client.post(
        f"/incidencias/{ticket_id}/asignar",
        json={"agente_id": cuentas.agente.id},
        headers=cuentas.agente.h,
    )
    assert asignado.status_code == 200, asignado.text
    resuelto = client.post(
        f"/incidencias/{ticket_id}/resolver",
        json={"nota_resolucion": "Se reinició el servicio y quedó operativo"},
        headers=cuentas.agente.h,
    )
    assert resuelto.status_code == 200, resuelto.text
    return resuelto.json()


def test_solo_supervision_accede_a_reportes(client, cuentas):
    for ruta in (
        "/reportes/resumen",
        "/reportes/kpis",
        "/reportes/incidencias.csv",
    ):
        assert client.get(ruta, headers=cuentas.agente.h).status_code == 403
        assert client.get(ruta, headers=cuentas.solicitante.h).status_code == 403
        assert client.get(ruta, headers=cuentas.admin.h).status_code == 200


def test_resumen_dashboard(client, cuentas):
    crear_ticket(client, cuentas, titulo="Sigue abierto")
    resuelto = crear_ticket(client, cuentas, titulo="Ya resuelto")
    resolver_ticket(client, cuentas, resuelto["id"])

    respuesta = client.get("/reportes/resumen", headers=cuentas.admin.h)
    assert respuesta.status_code == 200
    datos = respuesta.json()

    assert datos["creados_hoy"] == 2
    assert datos["resueltos_hoy"] == 1
    assert datos["abiertos"] == 2
    assert datos["sin_asignar"] == 1
    assert datos["sla_en_riesgo"] == 0
    assert datos["sla_vencido"] == 0
    assert any(item["valor"] == "Nuevo" for item in datos["por_estado"])
    assert any(item["valor"] == "P4 - Baja" for item in datos["por_prioridad"])
    assert any(item["valor"] == "Portal Web" for item in datos["por_canal"])
    assert any(
        item["nombre"] == "Sin categoría" for item in datos["por_categoria"]
    )


def test_kpis_y_filtros(client, cuentas):
    crear_ticket(client, cuentas, titulo="Sin asignar")
    resuelto = crear_ticket(client, cuentas, titulo="Resuelto")
    resolver_ticket(client, cuentas, resuelto["id"])

    respuesta = client.get("/reportes/kpis", headers=cuentas.admin.h)
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["tickets_creados"] == 2
    assert datos["tickets_resueltos"] == 1
    assert datos["cumplimiento_sla_pct"] == 100.0
    assert datos["mtta_minutos"] is not None
    assert datos["mtta_minutos"] >= 0
    assert datos["mttr_horas"] is not None
    assert datos["mttr_horas"] >= 0
    assert datos["fcr_pct"] == 100.0

    filtrado = client.get(
        f"/reportes/kpis?agente_asignado_id={cuentas.agente.id}",
        headers=cuentas.admin.h,
    )
    assert filtrado.status_code == 200
    assert filtrado.json()["tickets_creados"] == 1
    assert filtrado.json()["tickets_resueltos"] == 1

    hoy = date.today().isoformat()
    por_fecha = client.get(
        f"/reportes/kpis?desde={hoy}&hasta={hoy}",
        headers=cuentas.admin.h,
    )
    assert por_fecha.status_code == 200
    assert por_fecha.json()["tickets_creados"] == 2


def test_rango_de_fechas_invalido(client, cuentas):
    respuesta = client.get(
        "/reportes/kpis?desde=2026-11-20&hasta=2026-11-10",
        headers=cuentas.admin.h,
    )
    assert respuesta.status_code == 400
    assert "desde" in respuesta.json()["detail"]


def test_exportar_csv(client, cuentas):
    ticket = crear_ticket(client, cuentas, titulo="Ticket exportable")
    resuelto = crear_ticket(client, cuentas, titulo="Ticket resuelto CSV")
    resolver_ticket(client, cuentas, resuelto["id"])

    respuesta = client.get(
        "/reportes/incidencias.csv", headers=cuentas.admin.h
    )
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/csv")
    assert "attachment" in respuesta.headers["content-disposition"]

    texto = respuesta.content.decode("utf-8-sig")
    assert "id_legible" in texto
    assert ticket["id_legible"] in texto
    assert resuelto["id_legible"] in texto

    solo_resueltos = client.get(
        "/reportes/incidencias.csv?estado=Resuelto",
        headers=cuentas.admin.h,
    )
    assert solo_resueltos.status_code == 200
    texto_resueltos = solo_resueltos.content.decode("utf-8-sig")
    assert resuelto["id_legible"] in texto_resueltos
    assert ticket["id_legible"] not in texto_resueltos
