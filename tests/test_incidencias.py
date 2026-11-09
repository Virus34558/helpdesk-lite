def crear(client, cabeceras, titulo="No funciona Internet", **extra):
    return client.post(
        "/incidencias",
        json={"titulo": titulo, "descripcion": "Prueba", **extra},
        headers=cabeceras,
    )


def poner_en_progreso(client, cabeceras, incidencia_id):
    return client.patch(
        f"/incidencias/{incidencia_id}",
        json={"estado": "En progreso"},
        headers=cabeceras,
    )


def resolver(client, cabeceras, incidencia_id, nota="Cable de red sustituido"):
    return client.post(
        f"/incidencias/{incidencia_id}/resolver",
        json={"nota_resolucion": nota},
        headers=cabeceras,
    )


# ---------- Autenticación obligatoria ----------

def test_sin_token_devuelve_401(client):
    assert client.get("/incidencias").status_code == 401
    assert client.post("/incidencias", json={"titulo": "Sin token"}).status_code == 401


# ---------- Crear ----------

def test_crear_incidencia_como_solicitante(client, cuentas):
    respuesta = crear(client, cuentas.solicitante.h)
    assert respuesta.status_code == 201
    datos = respuesta.json()
    assert datos["estado"] == "Nuevo"
    assert datos["solicitante_id"] == cuentas.solicitante.id
    assert datos["prioridad"] == "P4 - Baja"
    assert datos["resuelta_en"] is None


def test_solicitante_no_puede_fijar_impacto_ni_urgencia(client, cuentas):
    datos = crear(
        client, cuentas.solicitante.h, impacto="Alto", urgencia="Crítica"
    ).json()
    assert datos["impacto"] == "Bajo"
    assert datos["urgencia"] == "Media"
    assert datos["prioridad"] == "P4 - Baja"


def test_agente_fija_impacto_y_urgencia(client, cuentas):
    datos = crear(client, cuentas.agente.h, impacto="Alto", urgencia="Crítica").json()
    assert datos["prioridad"] == "P1 - Crítica"


def test_impacto_invalido_devuelve_422(client, cuentas):
    respuesta = crear(client, cuentas.agente.h, impacto="Gigante")
    assert respuesta.status_code == 422


def test_titulo_demasiado_corto_devuelve_422(client, cuentas):
    respuesta = crear(client, cuentas.solicitante.h, titulo="ab")
    assert respuesta.status_code == 422


# ---------- Consultar y visibilidad ----------

def test_solicitante_solo_ve_sus_incidencias(client, cuentas):
    mia = crear(client, cuentas.solicitante.h, "Mi incidencia").json()
    ajena = crear(client, cuentas.otro.h, "Incidencia ajena").json()

    lista = client.get("/incidencias", headers=cuentas.solicitante.h).json()
    assert [i["id"] for i in lista] == [mia["id"]]

    respuesta = client.get(f"/incidencias/{ajena['id']}", headers=cuentas.solicitante.h)
    assert respuesta.status_code == 404


def test_agente_ve_todas_las_incidencias(client, cuentas):
    crear(client, cuentas.solicitante.h, "Incidencia 1")
    crear(client, cuentas.otro.h, "Incidencia 2")
    lista = client.get("/incidencias", headers=cuentas.agente.h).json()
    assert len(lista) == 2


def test_filtrar_por_prioridad(client, cuentas):
    crear(client, cuentas.agente.h, "Servidor caído", impacto="Alto", urgencia="Crítica")
    crear(client, cuentas.agente.h, "Impresora sin tinta")
    respuesta = client.get(
        "/incidencias", params={"prioridad": "P4 - Baja"}, headers=cuentas.agente.h
    )
    resultado = respuesta.json()
    assert len(resultado) == 1
    assert resultado[0]["titulo"] == "Impresora sin tinta"


def test_filtrar_por_estado(client, cuentas):
    primera = crear(client, cuentas.agente.h, "Error de software").json()
    crear(client, cuentas.agente.h, "Otra incidencia")
    poner_en_progreso(client, cuentas.agente.h, primera["id"])
    respuesta = client.get(
        "/incidencias", params={"estado": "En progreso"}, headers=cuentas.agente.h
    )
    resultado = respuesta.json()
    assert len(resultado) == 1
    assert resultado[0]["id"] == primera["id"]


def test_obtener_incidencia_inexistente_devuelve_404(client, cuentas):
    respuesta = client.get("/incidencias/999", headers=cuentas.agente.h)
    assert respuesta.status_code == 404


# ---------- Permisos de gestión ----------

def test_solicitante_no_puede_actualizar(client, cuentas):
    incidencia = crear(client, cuentas.solicitante.h).json()
    respuesta = client.patch(
        f"/incidencias/{incidencia['id']}",
        json={"estado": "En progreso"},
        headers=cuentas.solicitante.h,
    )
    assert respuesta.status_code == 403


def test_solicitante_no_puede_resolver(client, cuentas):
    incidencia = crear(client, cuentas.solicitante.h).json()
    respuesta = resolver(client, cuentas.solicitante.h, incidencia["id"])
    assert respuesta.status_code == 403


# ---------- Estados ----------

def test_pasar_a_en_progreso(client, cuentas):
    incidencia = crear(client, cuentas.solicitante.h).json()
    respuesta = poner_en_progreso(client, cuentas.agente.h, incidencia["id"])
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "En progreso"


def test_transicion_invalida_devuelve_409(client, cuentas):
    incidencia = crear(client, cuentas.solicitante.h).json()
    respuesta = client.patch(
        f"/incidencias/{incidencia['id']}",
        json={"estado": "Resuelto", "nota_resolucion": "Solucionado ya"},
        headers=cuentas.agente.h,
    )
    assert respuesta.status_code == 409


def test_resolver_por_patch_exige_nota(client, cuentas):
    incidencia = crear(client, cuentas.solicitante.h).json()
    poner_en_progreso(client, cuentas.agente.h, incidencia["id"])
    respuesta = client.patch(
        f"/incidencias/{incidencia['id']}",
        json={"estado": "Resuelto"},
        headers=cuentas.agente.h,
    )
    assert respuesta.status_code == 422


def test_resolver_incidencia_guarda_nota_y_fecha(client, cuentas):
    incidencia = crear(client, cuentas.solicitante.h).json()
    poner_en_progreso(client, cuentas.agente.h, incidencia["id"])
    respuesta = resolver(client, cuentas.agente.h, incidencia["id"])
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["estado"] == "Resuelto"
    assert datos["nota_resolucion"] == "Cable de red sustituido"
    assert datos["resuelta_en"] is not None


def test_reabrir_incidencia_borra_fecha_de_resolucion(client, cuentas):
    incidencia = crear(client, cuentas.solicitante.h).json()
    poner_en_progreso(client, cuentas.agente.h, incidencia["id"])
    resolver(client, cuentas.agente.h, incidencia["id"])
    respuesta = poner_en_progreso(client, cuentas.agente.h, incidencia["id"])
    assert respuesta.status_code == 200
    assert respuesta.json()["resuelta_en"] is None


def test_cerrado_es_inmutable(client, cuentas):
    incidencia = crear(client, cuentas.solicitante.h).json()
    poner_en_progreso(client, cuentas.agente.h, incidencia["id"])
    resolver(client, cuentas.agente.h, incidencia["id"])
    cierre = client.patch(
        f"/incidencias/{incidencia['id']}",
        json={"estado": "Cerrado"},
        headers=cuentas.agente.h,
    )
    assert cierre.status_code == 200
    reapertura = poner_en_progreso(client, cuentas.agente.h, incidencia["id"])
    assert reapertura.status_code == 409


def test_cerrado_rechaza_edicion_de_campos(client, cuentas):
    incidencia = crear(client, cuentas.solicitante.h).json()
    poner_en_progreso(client, cuentas.agente.h, incidencia["id"])
    resolver(client, cuentas.agente.h, incidencia["id"])
    client.patch(
        f"/incidencias/{incidencia['id']}",
        json={"estado": "Cerrado"},
        headers=cuentas.agente.h,
    )
    respuesta = client.patch(
        f"/incidencias/{incidencia['id']}",
        json={"titulo": "Nuevo título imposible"},
        headers=cuentas.agente.h,
    )
    assert respuesta.status_code == 409
    assert "No se pueden modificar incidencias en estado Cerrado" in respuesta.json()["detail"]


def test_cambiar_impacto_y_urgencia_recalcula_prioridad(client, cuentas):
    incidencia = crear(client, cuentas.solicitante.h).json()
    assert incidencia["prioridad"] == "P4 - Baja"
    respuesta = client.patch(
        f"/incidencias/{incidencia['id']}",
        json={"impacto": "Alto", "urgencia": "Alta"},
        headers=cuentas.agente.h,
    )
    assert respuesta.json()["prioridad"] == "P1 - Crítica"


# ---------- Identificador legible y Tipología ----------

def test_generacion_id_legible(client, cuentas):
    respuesta = crear(client, cuentas.solicitante.h)
    assert respuesta.status_code == 201
    datos = respuesta.json()
    assert "id_legible" in datos
    assert datos["id_legible"].startswith("INC-")
    assert datos["tipo"] == "Incidencia"
    assert datos["canal_origen"] == "Portal Web"


def test_crear_solicitud_de_servicio_genera_prefijo_req(client, cuentas):
    respuesta = crear(
        client, cuentas.solicitante.h, tipo="Solicitud de Servicio"
    )
    assert respuesta.status_code == 201
    datos = respuesta.json()
    assert datos["id_legible"].startswith("REQ-")
    assert datos["tipo"] == "Solicitud de Servicio"


def test_buscar_por_id_legible(client, cuentas):
    incidencia = crear(client, cuentas.solicitante.h).json()
    codigo = incidencia["id_legible"]

    # Búsqueda por código legible tipo INC-2026-000001
    respuesta = client.get(f"/incidencias/{codigo}", headers=cuentas.agente.h)
    assert respuesta.status_code == 200
    assert respuesta.json()["id"] == incidencia["id"]
    assert respuesta.json()["id_legible"] == codigo


# ---------- Asignación de Agente ----------

def test_asignar_agente_a_incidencia(client, cuentas):
    incidencia = crear(client, cuentas.solicitante.h).json()
    assert incidencia["agente_asignado_id"] is None
    assert incidencia["estado"] == "Nuevo"

    # Agente toma/asigna el ticket
    respuesta = client.post(
        f"/incidencias/{incidencia['id']}/asignar",
        json={"agente_id": cuentas.agente.id},
        headers=cuentas.agente.h,
    )
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["agente_asignado_id"] == cuentas.agente.id
    # Al asignarse desde 'Nuevo', transiciona naturalmente a 'En progreso'
    assert datos["estado"] == "En progreso"


def test_asignar_a_solicitante_devuelve_400(client, cuentas):
    incidencia = crear(client, cuentas.solicitante.h).json()
    respuesta = client.post(
        f"/incidencias/{incidencia['id']}/asignar",
        json={"agente_id": cuentas.solicitante.id},
        headers=cuentas.agente.h,
    )
    assert respuesta.status_code == 400
    assert "Solo se pueden asignar incidencias a personal de soporte" in respuesta.json()["detail"]


def test_asignar_a_usuario_inexistente_devuelve_404(client, cuentas):
    incidencia = crear(client, cuentas.solicitante.h).json()
    respuesta = client.post(
        f"/incidencias/{incidencia['id']}/asignar",
        json={"agente_id": 99999},
        headers=cuentas.agente.h,
    )
    assert respuesta.status_code == 404


def test_solicitante_no_puede_asignar(client, cuentas):
    incidencia = crear(client, cuentas.solicitante.h).json()
    respuesta = client.post(
        f"/incidencias/{incidencia['id']}/asignar",
        json={"agente_id": cuentas.agente.id},
        headers=cuentas.solicitante.h,
    )
    assert respuesta.status_code == 403


def test_desasignar_agente(client, cuentas):
    incidencia = crear(client, cuentas.solicitante.h).json()
    client.post(
        f"/incidencias/{incidencia['id']}/asignar",
        json={"agente_id": cuentas.agente.id},
        headers=cuentas.agente.h,
    )
    # Desasignar pasando agente_id=None
    respuesta = client.post(
        f"/incidencias/{incidencia['id']}/asignar",
        json={"agente_id": None},
        headers=cuentas.agente.h,
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["agente_asignado_id"] is None


def test_filtrar_por_tipo(client, cuentas):
    crear(client, cuentas.solicitante.h, titulo="Fallo de red", tipo="Incidencia")
    crear(client, cuentas.solicitante.h, titulo="Nuevo ratón", tipo="Solicitud de Servicio")

    res = client.get(
        "/incidencias", params={"tipo": "Solicitud de Servicio"}, headers=cuentas.agente.h
    )
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["tipo"] == "Solicitud de Servicio"


def test_filtrar_por_agente_asignado_y_sin_asignar(client, cuentas):
    ticket1 = crear(client, cuentas.solicitante.h, titulo="Ticket 1").json()
    ticket2 = crear(client, cuentas.solicitante.h, titulo="Ticket 2").json()

    # Asignar ticket 1 al agente
    client.post(
        f"/incidencias/{ticket1['id']}/asignar",
        json={"agente_id": cuentas.agente.id},
        headers=cuentas.agente.h,
    )

    # Filtrar por agente
    res_agente = client.get(
        "/incidencias", params={"agente_asignado_id": cuentas.agente.id}, headers=cuentas.agente.h
    )
    assert len(res_agente.json()) == 1
    assert res_agente.json()[0]["id"] == ticket1["id"]

    # Filtrar sin asignar
    res_sin_asignar = client.get(
        "/incidencias", params={"sin_asignar": True}, headers=cuentas.agente.h
    )
    assert len(res_sin_asignar.json()) == 1
    assert res_sin_asignar.json()[0]["id"] == ticket2["id"]
