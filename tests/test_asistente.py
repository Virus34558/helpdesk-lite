"""Triaje asistido: el modelo propone, el agente decide."""

import json

import pytest

from app import asistente

CATEGORIA = {"nombre": "Hardware", "descripcion": "Equipos"}

RESPUESTA_VALIDA = json.dumps(
    {
        "tipo": "Incidencia",
        "impacto": "Medio",
        "urgencia": "Alta",
        "categoria": "Hardware",
        "motivo": "Afecta a un departamento y bloquea trabajo",
    }
)


class ProveedorFalso:
    def __init__(self, respuesta):
        self.respuesta = respuesta
        self.llamadas = []

    def disponible(self):
        return True

    def sugerir(self, texto):
        self.llamadas.append(texto)
        return self.respuesta


@pytest.fixture(autouse=True)
def estado_limpio():
    asistente.reiniciar()
    yield
    asistente.reiniciar()


@pytest.fixture()
def proveedor(monkeypatch):
    falso = ProveedorFalso(RESPUESTA_VALIDA)
    monkeypatch.setenv("ASISTENTE_PROVEEDOR", "fake")
    monkeypatch.setattr(asistente, "obtener_proveedor", lambda: falso)
    return falso


def crear(client, cabeceras, categoria_id=None):
    cuerpo = {
        "titulo": "La impresora no imprime",
        "descripcion": "Contabilidad lleva sin imprimir desde ayer",
    }
    if categoria_id:
        cuerpo["categoria_id"] = categoria_id
    return client.post("/incidencias", json=cuerpo, headers=cabeceras).json()


def categoria(client, cabeceras):
    return client.post("/categorias", json=CATEGORIA, headers=cabeceras).json()


def pedir(client, cabeceras, ticket_id):
    return client.post(
        f"/incidencias/{ticket_id}/asistencia/triaje", headers=cabeceras
    )


def test_sin_proveedor_configurado_no_esta_disponible(client, cuentas, monkeypatch):
    monkeypatch.setenv("ASISTENTE_PROVEEDOR", "ninguno")
    ticket = crear(client, cuentas.solicitante.h)

    respuesta = pedir(client, cuentas.agente.h, ticket["id"])

    assert respuesta.status_code == 503


def test_el_solicitante_no_puede_pedir_triaje(client, cuentas, proveedor):
    ticket = crear(client, cuentas.solicitante.h)

    respuesta = pedir(client, cuentas.solicitante.h, ticket["id"])

    assert respuesta.status_code == 403


def test_devuelve_la_sugerencia_normalizada(client, cuentas, proveedor):
    categoria(client, cuentas.admin.h)
    ticket = crear(client, cuentas.solicitante.h, categoria_id=1)

    respuesta = pedir(client, cuentas.agente.h, ticket["id"])

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["impacto"] == "Medio"
    assert datos["urgencia"] == "Alta"
    assert datos["categoria_id"] == 1


def test_la_prioridad_se_calcula_no_se_copia(client, cuentas, proveedor):
    categoria(client, cuentas.admin.h)
    ticket = crear(client, cuentas.solicitante.h, categoria_id=1)

    datos = pedir(client, cuentas.agente.h, ticket["id"]).json()

    # Impacto Medio + Urgencia Alta => P2 según la matriz ITIL
    assert datos["prioridad"] == "P2 - Alta"


def test_una_categoria_desconocida_no_rompe_la_sugerencia(client, cuentas, proveedor):
    proveedor.respuesta = json.dumps(
        {"tipo": "Incidencia", "impacto": "Bajo", "urgencia": "Media",
         "categoria": "Impresoras 3D", "motivo": "sin categoría clara"}
    )
    ticket = crear(client, cuentas.solicitante.h)

    datos = pedir(client, cuentas.agente.h, ticket["id"]).json()

    assert datos["categoria_id"] is None
    assert datos["impacto"] == "Bajo"


def test_una_respuesta_ilegible_devuelve_502(client, cuentas, proveedor):
    proveedor.respuesta = "no soy json"
    ticket = crear(client, cuentas.solicitante.h)

    respuesta = pedir(client, cuentas.agente.h, ticket["id"])

    assert respuesta.status_code == 502


def test_un_valor_fuera_de_rango_devuelve_502(client, cuentas, proveedor):
    proveedor.respuesta = json.dumps(
        {"tipo": "Incidencia", "impacto": "Extremo", "urgencia": "Alta",
         "categoria": "Hardware", "motivo": "x"}
    )
    ticket = crear(client, cuentas.solicitante.h)

    respuesta = pedir(client, cuentas.agente.h, ticket["id"])

    assert respuesta.status_code == 502


def test_se_aceptan_tildes_y_mayusculas(client, cuentas, proveedor):
    proveedor.respuesta = RESPUESTA_VALIDA.replace('"Alta"', '"ALTA"')
    ticket = crear(client, cuentas.solicitante.h)

    assert pedir(client, cuentas.agente.h, ticket["id"]).status_code == 200


def test_la_misma_consulta_usa_la_cache(client, cuentas, proveedor):
    ticket = crear(client, cuentas.solicitante.h)

    pedir(client, cuentas.agente.h, ticket["id"])
    pedir(client, cuentas.agente.h, ticket["id"])

    assert len(proveedor.llamadas) == 1


def test_el_texto_largo_se_recorta(client, cuentas, proveedor):
    ticket = client.post(
        "/incidencias",
        json={"titulo": "Fallo", "descripcion": "x" * 20000},
        headers=cuentas.solicitante.h,
    ).json()

    pedir(client, cuentas.agente.h, ticket["id"])

    assert len(proveedor.llamadas[0]) < 10000


def test_limite_diario_por_usuario(client, cuentas, proveedor, monkeypatch):
    monkeypatch.setenv("ASISTENTE_MAX_DIA", "2")
    primero = crear(client, cuentas.solicitante.h, categoria_id=None)
    segundo = crear(client, cuentas.solicitante.h, categoria_id=None)

    pedir(client, cuentas.agente.h, primero["id"])
    pedir(client, cuentas.agente.h, segundo["id"])
    respuesta = pedir(client, cuentas.agente.h, primero["id"])

    assert respuesta.status_code == 429
