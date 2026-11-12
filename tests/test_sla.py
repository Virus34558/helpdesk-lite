from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import sessionmaker

from app import sla, models, auth, reglas
from app.database import Base


@pytest.fixture()
def db_session(motor):
    TestingSession = sessionmaker(bind=motor, autoflush=False)
    db = TestingSession()
    yield db
    db.close()


def _crear_incidencia_en_db(db, prioridad="P4 - Baja", estado="Nuevo", **kwargs):
    solicitante = models.Usuario(
        email="sla@test.com",
        nombre_completo="SLA Test",
        password_hash="hash",
        rol="solicitante",
    )
    db.add(solicitante)
    db.flush()

    ahora = datetime.now()
    incidencia = models.Incidencia(
        id_legible=reglas.generar_id_legible("Incidencia", 1, anio=2026),
        tipo="Incidencia",
        canal_origen="Portal Web",
        titulo="Ticket SLA",
        descripcion="Desc",
        impacto="Bajo",
        urgencia="Baja",
        prioridad=prioridad,
        estado=estado,
        solicitante_id=solicitante.id,
        creada_en=ahora,
        actualizada_en=ahora,
    )
    for campo, valor in kwargs.items():
        setattr(incidencia, campo, valor)

    db.add(incidencia)
    db.flush()
    db.refresh(incidencia)
    return incidencia


# ----------------------------------------------------------------
# 1. Inicialización de tiempos límite según P1-P4
# ----------------------------------------------------------------

def test_inicializar_sla_p1_critica():
    ahora = datetime(2026, 1, 1, 10, 0, 0)  # Jueves
    frt, rt = sla.inicializar_sla("P1 - Crítica", ahora)
    assert frt == ahora + timedelta(minutes=15)
    assert rt == ahora + timedelta(hours=4)  # Continuo: 14:00 mismo día


def test_inicializar_sla_p2_alta():
    ahora = datetime(2026, 1, 1, 10, 0, 0)  # Jueves, dentro horario laboral
    frt, rt = sla.inicializar_sla("P2 - Alta", ahora)
    assert frt == ahora + timedelta(hours=1)
    # 8 horas hábiles desde jueves 10:00 = jueves 18:00 (mismo día)
    assert rt == datetime(2026, 1, 1, 18, 0, 0)


def test_inicializar_sla_p3_media():
    ahora = datetime(2026, 1, 1, 10, 0, 0)  # Jueves
    frt, rt = sla.inicializar_sla("P3 - Media", ahora)
    assert frt == ahora + timedelta(hours=4)
    # 24 horas hábiles: jueves 10-18 (8h) + viernes 9-18 (9h) + lunes 9-16 (7h)
    assert rt == datetime(2026, 1, 5, 16, 0, 0)  # Lunes 16:00


def test_inicializar_sla_p4_baja():
    ahora = datetime(2026, 1, 1, 10, 0, 0)  # Jueves
    frt, rt = sla.inicializar_sla("P4 - Baja", ahora)
    assert frt == ahora + timedelta(hours=8)
    # 72 horas hábiles: martes 13 de enero a las 10:00
    assert rt == datetime(2026, 1, 13, 10, 0, 0)


def test_inicializar_sla_desconocida_usa_p4():
    ahora = datetime(2026, 1, 1, 10, 0, 0)  # Jueves
    frt, rt = sla.inicializar_sla("Prioridad Inexistente", ahora)
    assert frt == ahora + timedelta(hours=8)
    assert rt == datetime(2026, 1, 13, 10, 0, 0)  # Mismo que P4


# ----------------------------------------------------------------
# 2. Sellado de primera respuesta (FRT)
# ----------------------------------------------------------------

def test_registrar_primera_respuesta_dentro_de_plazo():
    ahora = datetime(2026, 1, 1, 10, 0, 0)
    incidencia = _crear_incidencia_en_db.__wrapped__ if False else None
    # Creamos una incidencia ligera sin DB para probar la función pura
    class FakeInc:
        primera_respuesta_en = None
        sla_limite_primera_respuesta = ahora + timedelta(minutes=10)
        sla_primera_respuesta_cumplido = None

    inc = FakeInc()
    resultado = sla.registrar_primera_respuesta(inc, ahora=ahora + timedelta(minutes=5))
    assert resultado is True
    assert inc.primera_respuesta_en == ahora + timedelta(minutes=5)
    assert inc.sla_primera_respuesta_cumplido is True


def test_registrar_primera_respuesta_fuera_de_plazo():
    class FakeInc:
        primera_respuesta_en = None
        sla_limite_primera_respuesta = datetime(2026, 1, 1, 10, 0, 0)
        sla_primera_respuesta_cumplido = None

    inc = FakeInc()
    resultado = sla.registrar_primera_respuesta(
        inc, ahora=datetime(2026, 1, 1, 10, 30, 0)
    )
    assert resultado is True
    assert inc.sla_primera_respuesta_cumplido is False


def test_registrar_primera_respuesta_solo_una_vez():
    class FakeInc:
        primera_respuesta_en = datetime(2026, 1, 1, 10, 0, 0)
        sla_limite_primera_respuesta = datetime(2026, 1, 1, 11, 0, 0)
        sla_primera_respuesta_cumplido = True

    inc = FakeInc()
    resultado = sla.registrar_primera_respuesta(inc, ahora=datetime(2026, 1, 1, 10, 5, 0))
    assert resultado is False


def test_primera_respuesta_sin_limite_se_asume_cumplido():
    class FakeInc:
        primera_respuesta_en = None
        sla_limite_primera_respuesta = None
        sla_primera_respuesta_cumplido = None

    inc = FakeInc()
    resultado = sla.registrar_primera_respuesta(inc)
    assert resultado is True
    assert inc.sla_primera_respuesta_cumplido is True


# ----------------------------------------------------------------
# 3. Stop the Clock (congela y reanuda)
# ----------------------------------------------------------------

def test_stop_the_clock_entra_en_pausa():
    ahora = datetime(2026, 1, 1, 10, 0, 0)
    class FakeInc:
        sla_pausado_en = None
        sla_tiempo_pausado_segundos = 0
        sla_limite_resolucion = ahora + timedelta(hours=4)

    inc = FakeInc()
    sla.gestionar_transicion_estado_sla(inc, "En progreso", "Pendiente de usuario", ahora=ahora)
    assert inc.sla_pausado_en == ahora


def test_stop_the_clock_sin_cambio_no_pausa():
    ahora = datetime(2026, 1, 1, 10, 0, 0)
    class FakeInc:
        sla_pausado_en = ahora
        sla_tiempo_pausado_segundos = 0

    inc = FakeInc()
    sla.gestionar_transicion_estado_sla(inc, "Pendiente de usuario", "Pendiente de usuario", ahora=ahora)
    assert inc.sla_pausado_en == ahora


def test_stop_the_clock_reanuda_y_extiende_limite():
    ahora_entrada = datetime(2026, 1, 1, 10, 0, 0)
    ahora_salida = datetime(2026, 1, 1, 10, 30, 0)  # 30 minutos pausado

    class FakeInc:
        sla_pausado_en = ahora_entrada
        sla_tiempo_pausado_segundos = 0
        sla_limite_resolucion = ahora_entrada + timedelta(hours=4)

    inc = FakeInc()
    sla.gestionar_transicion_estado_sla(
        inc, "Pendiente de usuario", "En progreso", ahora=ahora_salida
    )
    assert inc.sla_pausado_en is None
    assert inc.sla_tiempo_pausado_segundos == 1800
    assert inc.sla_limite_resolucion == ahora_entrada + timedelta(hours=4, minutes=30)


def test_stop_the_clock_resolucion_final_considera_pausa():
    ahora_entrada = datetime(2026, 1, 1, 10, 0, 0)
    ahora_resolucion = datetime(2026, 1, 1, 10, 45, 0)

    class FakeInc:
        sla_pausado_en = ahora_entrada
        sla_tiempo_pausado_segundos = 0
        sla_limite_resolucion = ahora_entrada + timedelta(hours=4)
        sla_resolucion_cumplido = None
        sla_resolucion_vencido = False

    inc = FakeInc()
    sla.finalizar_sla_resolucion(inc, ahora=ahora_resolucion)
    assert inc.sla_pausado_en is None
    assert inc.sla_tiempo_pausado_segundos == 2700
    # Límite extendido por los 45 min de pausa: 10:00 + 4h + 45min = 14:45
    # Resolución a las 10:45, así que cumplido
    assert inc.sla_resolucion_cumplido is True


# ----------------------------------------------------------------
# 4. Estado en tiempo real (en_tiempo, en_riesgo, vencido, pausado)
# ----------------------------------------------------------------

def test_estado_sla_resuelto_cumplido():
    class FakeInc:
        estado = "Resuelto"
        sla_resolucion_cumplido = True

    assert sla.calcular_estado_sla(FakeInc()) == "cumplido"


def test_estado_sla_resuelto_vencido():
    class FakeInc:
        estado = "Resuelto"
        sla_resolucion_cumplido = False

    assert sla.calcular_estado_sla(FakeInc()) == "vencido"


def test_estado_sla_pausado():
    class FakeInc:
        estado = "En progreso"
        sla_pausado_en = datetime.now()
        sla_limite_resolucion = datetime.now() + timedelta(hours=1)

    assert sla.calcular_estado_sla(FakeInc()) == "pausado"


def test_estado_sla_en_riesgo():
    creada = datetime(2026, 1, 1, 10, 0, 0)
    limite = datetime(2026, 1, 1, 12, 0, 0)  # 2 horas de total
    ahora = datetime(2026, 1, 1, 11, 30, 0)  # 90 min consumidos = 75%

    class FakeInc:
        estado = "En progreso"
        prioridad = "P1 - Crítica"
        sla_pausado_en = None
        sla_limite_resolucion = limite
        creada_en = creada
        sla_tiempo_pausado_segundos = 0

    assert sla.calcular_estado_sla(FakeInc(), ahora=ahora) == "en_riesgo"


def test_estado_sla_vencido():
    creada = datetime(2026, 1, 1, 10, 0, 0)
    limite = datetime(2026, 1, 1, 11, 0, 0)
    ahora = datetime(2026, 1, 1, 11, 30, 0)  # pasado el límite

    class FakeInc:
        estado = "En progreso"
        sla_pausado_en = None
        sla_limite_resolucion = limite
        creada_en = creada
        sla_tiempo_pausado_segundos = 0

    assert sla.calcular_estado_sla(FakeInc(), ahora=ahora) == "vencido"


def test_estado_sla_en_tiempo():
    creada = datetime(2026, 1, 1, 10, 0, 0)
    limite = datetime(2026, 1, 1, 14, 0, 0)
    ahora = datetime(2026, 1, 1, 11, 0, 0)

    class FakeInc:
        estado = "En progreso"
        prioridad = "P1 - Crítica"
        sla_pausado_en = None
        sla_limite_resolucion = limite
        creada_en = creada
        sla_tiempo_pausado_segundos = 0

    assert sla.calcular_estado_sla(FakeInc(), ahora=ahora) == "en_tiempo"


# ----------------------------------------------------------------
# 5. Integración API: inicialización y filtros SLA
# ----------------------------------------------------------------

def test_crear_incidencia_inicializa_sla(client, cuentas):
    respuesta = client.post(
        "/incidencias",
        json={"titulo": "SLA inicial", "descripcion": "Prueba", "impacto": "Alto", "urgencia": "Crítica"},
        headers=cuentas.agente.h,
    )
    assert respuesta.status_code == 201
    datos = respuesta.json()
    assert datos["prioridad"] == "P1 - Crítica"
    assert datos["sla_limite_primera_respuesta"] is not None
    assert datos["sla_limite_resolucion"] is not None
    assert datos["primera_respuesta_en"] is None
    assert datos["sla_primera_respuesta_cumplido"] is None


def test_primera_respuesta_al_comentar_agente(client, cuentas):
    ticket = client.post(
        "/incidencias",
        json={"titulo": "FRT", "descripcion": "Prueba"},
        headers=cuentas.solicitante.h,
    ).json()

    client.patch(
        f"/incidencias/{ticket['id']}",
        json={"estado": "En progreso"},
        headers=cuentas.agente.h,
    )

    respuesta = client.post(
        f"/incidencias/{ticket['id']}/comentarios",
        json={"contenido": "Primera respuesta del agente", "es_interno": False},
        headers=cuentas.agente.h,
    )
    assert respuesta.status_code == 201
    datos = respuesta.json()
    assert datos["es_interno"] is False

    actualizado = client.get(
        f"/incidencias/{ticket['id']}", headers=cuentas.agente.h
    ).json()
    assert actualizado["primera_respuesta_en"] is not None


def test_nota_interna_no_cuenta_como_primera_respuesta(client, cuentas):
    ticket = client.post(
        "/incidencias",
        json={"titulo": "FRT interna", "descripcion": "Prueba"},
        headers=cuentas.solicitante.h,
    ).json()

    client.patch(
        f"/incidencias/{ticket['id']}",
        json={"estado": "En progreso"},
        headers=cuentas.agente.h,
    )

    client.post(
        f"/incidencias/{ticket['id']}/comentarios",
        json={"contenido": "Nota interna", "es_interno": True},
        headers=cuentas.agente.h,
    )

    actualizado = client.get(
        f"/incidencias/{ticket['id']}", headers=cuentas.agente.h
    ).json()
    assert actualizado["primera_respuesta_en"] is None


def test_stop_the_clock_por_api(client, cuentas, db_session):
    ticket = client.post(
        "/incidencias",
        json={"titulo": "Stop clock", "descripcion": "Prueba"},
        headers=cuentas.solicitante.h,
    ).json()

    # Nuevo -> En progreso (transición válida)
    client.patch(
        f"/incidencias/{ticket['id']}",
        json={"estado": "En progreso"},
        headers=cuentas.agente.h,
    )
    # En progreso -> Pendiente de usuario (pausa)
    client.patch(
        f"/incidencias/{ticket['id']}",
        json={"estado": "Pendiente de usuario"},
        headers=cuentas.agente.h,
    )
    en_pausa = client.get(
        f"/incidencias/{ticket['id']}", headers=cuentas.agente.h
    ).json()
    assert en_pausa["estado"] == "Pendiente de usuario"

    # Pendiente de usuario -> En progreso (reanuda)
    client.patch(
        f"/incidencias/{ticket['id']}",
        json={"estado": "En progreso"},
        headers=cuentas.agente.h,
    )
    reanudado = client.get(
        f"/incidencias/{ticket['id']}", headers=cuentas.agente.h
    ).json()
    assert reanudado["estado"] == "En progreso"
    assert reanudado["sla_tiempo_pausado_segundos"] >= 0
    assert reanudado["sla_limite_resolucion"] is not None


def test_filtro_sla_vencido_api(client, cuentas, db_session):
    # Crear un ticket y marcarlo directamente como vencido en BD
    incidencia = _crear_incidencia_en_db(db_session, prioridad="P1 - Crítica", estado="Resuelto")
    db_session.query(models.Incidencia).filter(
        models.Incidencia.id == incidencia.id
    ).update({
        "sla_resolucion_vencido": True,
        "sla_resolucion_cumplido": False,
    })
    db_session.commit()

    respuesta = client.get(
        "/incidencias", params={"sla_vencido": True}, headers=cuentas.agente.h
    )
    assert respuesta.status_code == 200
    ids = [t["id"] for t in respuesta.json()]
    assert incidencia.id in ids


def test_filtro_sla_en_riesgo_api(client, cuentas, db_session):
    ahora = datetime.now()
    # P1 (continuo): 10h consumidas de 12h totales = 83.3% → en_riesgo
    incidencia = _crear_incidencia_en_db(
        db_session,
        prioridad="P1 - Crítica",
        estado="En progreso",
        sla_limite_resolucion=ahora + timedelta(hours=2),
        creada_en=ahora - timedelta(hours=10),
    )
    db_session.commit()

    respuesta = client.get(
        "/incidencias", params={"sla_en_riesgo": True}, headers=cuentas.agente.h
    )
    assert respuesta.status_code == 200
    ids = [t["id"] for t in respuesta.json()]
    assert incidencia.id in ids
