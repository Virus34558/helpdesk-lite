def crear(client, titulo="No funciona Internet", prioridad="Alta"):
    return client.post(
        "/incidencias",
        json={"titulo": titulo, "descripcion": "Prueba", "prioridad": prioridad},
    )


def test_crear_incidencia(client):
    respuesta = crear(client)
    assert respuesta.status_code == 201
    datos = respuesta.json()
    assert datos["titulo"] == "No funciona Internet"
    assert datos["prioridad"] == "Alta"
    assert datos["estado"] == "Abierta"
    assert datos["resuelta_en"] is None


def test_prioridad_invalida_devuelve_422(client):
    respuesta = crear(client, prioridad="Urgentisima")
    assert respuesta.status_code == 422


def test_titulo_demasiado_corto_devuelve_422(client):
    respuesta = crear(client, titulo="ab")
    assert respuesta.status_code == 422


def test_listar_incidencias(client):
    crear(client, "Incidencia 1")
    crear(client, "Incidencia 2")
    respuesta = client.get("/incidencias")
    assert respuesta.status_code == 200
    assert len(respuesta.json()) == 2


def test_filtrar_por_prioridad(client):
    crear(client, "Internet caido", "Alta")
    crear(client, "Impresora sin tinta", "Baja")
    respuesta = client.get("/incidencias", params={"prioridad": "Baja"})
    resultado = respuesta.json()
    assert len(resultado) == 1
    assert resultado[0]["titulo"] == "Impresora sin tinta"


def test_filtrar_por_estado(client):
    incidencia = crear(client, "Error de software", "Media").json()
    crear(client, "Otra incidencia", "Baja")
    client.post(f"/incidencias/{incidencia['id']}/resolver")
    resueltas = client.get("/incidencias", params={"estado": "Resuelta"}).json()
    assert len(resueltas) == 1
    assert resueltas[0]["id"] == incidencia["id"]


def test_obtener_incidencia_inexistente_devuelve_404(client):
    respuesta = client.get("/incidencias/999")
    assert respuesta.status_code == 404


def test_actualizar_estado_a_en_proceso(client):
    incidencia = crear(client).json()
    respuesta = client.patch(
        f"/incidencias/{incidencia['id']}", json={"estado": "En proceso"}
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "En proceso"


def test_resolver_incidencia_rellena_fecha(client):
    incidencia = crear(client).json()
    respuesta = client.post(f"/incidencias/{incidencia['id']}/resolver")
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["estado"] == "Resuelta"
    assert datos["resuelta_en"] is not None


def test_reabrir_incidencia_borra_fecha_de_resolucion(client):
    incidencia = crear(client).json()
    client.post(f"/incidencias/{incidencia['id']}/resolver")
    respuesta = client.patch(
        f"/incidencias/{incidencia['id']}", json={"estado": "Abierta"}
    )
    assert respuesta.json()["resuelta_en"] is None