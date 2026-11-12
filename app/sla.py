from datetime import datetime, timedelta

# Tiempos objetivo según ITIL (Sección 4.1 de la especificación ERS)
OBJETIVOS_SLA = {
    "P1 - Crítica": {"frt_minutos": 15, "rt_horas": 4, "calendario": "continuo"},
    "P2 - Alta": {"frt_minutos": 60, "rt_horas": 8, "calendario": "laboral"},
    "P3 - Media": {"frt_minutos": 240, "rt_horas": 24, "calendario": "laboral"},
    "P4 - Baja": {"frt_minutos": 480, "rt_horas": 72, "calendario": "laboral"},
}

# Estados que congelan el temporizador de resolución ("Stop the Clock", RF-4.2)
ESTADOS_PAUSA = {"Pendiente de usuario", "Pendiente de tercero"}

# Calendario laboral: Lunes a Viernes de 09:00 a 18:00
DIAS_LABORALES = {0, 1, 2, 3, 4}
HORA_INICIO_LABORAL = 9
HORA_FIN_LABORAL = 18


def _inicio_dia_habil(dt: datetime) -> datetime:
    """Devuelve el inicio del horario laboral (09:00) del día dado si es laborable."""
    return dt.replace(hour=HORA_INICIO_LABORAL, minute=0, second=0, microsecond=0)


def _fin_dia_habil(dt: datetime) -> datetime:
    """Devuelve el fin del horario laboral (18:00) del día dado."""
    return dt.replace(hour=HORA_FIN_LABORAL, minute=0, second=0, microsecond=0)


def es_hora_habil(dt: datetime) -> bool:
    """Devuelve True si la fecha está dentro del horario laboral (L-V 09:00-18:00)."""
    return dt.weekday() in DIAS_LABORALES and HORA_INICIO_LABORAL <= dt.hour < HORA_FIN_LABORAL


def _siguiente_inicio_habil(dt: datetime) -> datetime:
    """Devuelve el siguiente inicio de horario laboral a partir de dt."""
    candidato = dt.replace(hour=HORA_INICIO_LABORAL, minute=0, second=0, microsecond=0)
    if not es_hora_habil(candidato):
        # Si ya pasó las 18:00 o es fin de semana, avanzar al siguiente día hábil
        candidato += timedelta(days=1)
        candidato = candidato.replace(
            hour=HORA_INICIO_LABORAL, minute=0, second=0, microsecond=0
        )
    while candidato.weekday() not in DIAS_LABORALES:
        candidato += timedelta(days=1)
        candidato = candidato.replace(
            hour=HORA_INICIO_LABORAL, minute=0, second=0, microsecond=0
        )
    return candidato


def sumar_horas_habiles(fecha_inicio: datetime, horas: float) -> datetime:
    """Suma horas hábiles a una fecha. Solo cuenta tiempo dentro del horario laboral."""
    if horas <= 0:
        return fecha_inicio

    segundos_restantes = horas * 3600
    actual = fecha_inicio

    if not es_hora_habil(actual):
        actual = _siguiente_inicio_habil(actual)

    while segundos_restantes > 0:
        fin_dia = _fin_dia_habil(actual)
        segundos_hasta_fin_dia = int((fin_dia - actual).total_seconds())

        if segundos_hasta_fin_dia <= 0:
            actual += timedelta(days=1)
            actual = _siguiente_inicio_habil(actual)
            continue

        segundos_a_usar = min(segundos_restantes, segundos_hasta_fin_dia)
        actual += timedelta(seconds=segundos_a_usar)
        segundos_restantes -= segundos_a_usar

        if segundos_restantes > 0 and actual >= fin_dia:
            actual += timedelta(days=1)
            actual = _siguiente_inicio_habil(actual)

    return actual


def horas_habiles_entre(inicio: datetime, fin: datetime) -> float:
    """Calcula horas hábiles entre dos fechas (solo horario laboral)."""
    if fin <= inicio:
        return 0.0

    total_segundos = 0.0
    actual = inicio

    while actual < fin:
        if not es_hora_habil(actual):
            actual = _siguiente_inicio_habil(actual)
            if actual >= fin:
                break
            continue

        fin_dia = _fin_dia_habil(actual)
        fin_segmento = min(fin_dia, fin)
        total_segundos += (fin_segmento - actual).total_seconds()
        actual = fin_segmento

        if actual >= fin_dia:
            actual += timedelta(days=1)

    return total_segundos / 3600.0


def _es_calendario_continuo(prioridad: str) -> bool:
    objetivo = OBJETIVOS_SLA.get(prioridad, OBJETIVOS_SLA["P4 - Baja"])
    return objetivo.get("calendario") == "continuo"


def _limite_primera_respuesta(
    prioridad: str, fecha_base: datetime, objetivo: dict
) -> datetime:
    """Calcula el límite de FRT respetando el calendario de la póliza."""
    if _es_calendario_continuo(prioridad):
        return fecha_base + timedelta(minutes=objetivo["frt_minutos"])
    return sumar_horas_habiles(fecha_base, objetivo["frt_minutos"] / 60)


def inicializar_sla(
    prioridad: str, fecha_base: datetime | None = None
) -> tuple[datetime, datetime]:
    """Calcula las fechas límite de Primera Respuesta (FRT) y Resolución (RT).

    P1 usa calendario continuo (24×7). P2-P4 usan horario laboral (8×5).
    """
    ahora = fecha_base or datetime.now()
    objetivo = OBJETIVOS_SLA.get(prioridad, OBJETIVOS_SLA["P4 - Baja"])

    limite_frt = _limite_primera_respuesta(prioridad, ahora, objetivo)

    if _es_calendario_continuo(prioridad):
        limite_rt = ahora + timedelta(hours=objetivo["rt_horas"])
    else:
        limite_rt = sumar_horas_habiles(ahora, objetivo["rt_horas"])

    return limite_frt, limite_rt


def registrar_primera_respuesta(incidencia, ahora: datetime | None = None) -> bool:
    """Registra la primera respuesta pública de un técnico si aún no se ha hecho."""
    if incidencia.primera_respuesta_en is not None:
        return False

    momento = ahora or datetime.now()
    incidencia.primera_respuesta_en = momento
    if incidencia.sla_limite_primera_respuesta:
        incidencia.sla_primera_respuesta_cumplido = (
            momento <= incidencia.sla_limite_primera_respuesta
        )
    else:
        incidencia.sla_primera_respuesta_cumplido = True
    return True


def gestionar_transicion_estado_sla(
    incidencia, estado_anterior: str, nuevo_estado: str, ahora: datetime | None = None
):
    """Aplica la lógica de 'Stop the Clock' cuando entra o sale de estados de pausa."""
    momento = ahora or datetime.now()

    # Entra en estado de pausa ("Stop the Clock")
    if nuevo_estado in ESTADOS_PAUSA and estado_anterior not in ESTADOS_PAUSA:
        incidencia.sla_pausado_en = momento

    # Sale del estado de pausa y vuelve a estar activo
    elif estado_anterior in ESTADOS_PAUSA and nuevo_estado not in ESTADOS_PAUSA:
        if incidencia.sla_pausado_en is not None:
            segundos_pausa = max(
                0, int((momento - incidencia.sla_pausado_en).total_seconds())
            )
            incidencia.sla_tiempo_pausado_segundos = (
                incidencia.sla_tiempo_pausado_segundos or 0
            ) + segundos_pausa

            # Extiende la fecha límite de resolución sumando el tiempo que estuvo pausado
            if incidencia.sla_limite_resolucion:
                incidencia.sla_limite_resolucion += timedelta(seconds=segundos_pausa)

            incidencia.sla_pausado_en = None


def finalizar_sla_resolucion(incidencia, ahora: datetime | None = None):
    """Sella el cumplimiento del SLA de resolución cuando el ticket se resuelve."""
    momento = ahora or datetime.now()

    # Si estaba en pausa en el momento de resolverse, contabiliza la pausa final
    if incidencia.sla_pausado_en is not None:
        segundos_pausa = max(
            0, int((momento - incidencia.sla_pausado_en).total_seconds())
        )
        incidencia.sla_tiempo_pausado_segundos = (
            incidencia.sla_tiempo_pausado_segundos or 0
        ) + segundos_pausa
        if incidencia.sla_limite_resolucion:
            incidencia.sla_limite_resolucion += timedelta(seconds=segundos_pausa)
        incidencia.sla_pausado_en = None

    if incidencia.sla_limite_resolucion:
        incidencia.sla_resolucion_cumplido = momento <= incidencia.sla_limite_resolucion
        incidencia.sla_resolucion_vencido = not incidencia.sla_resolucion_cumplido
    else:
        incidencia.sla_resolucion_cumplido = True
        incidencia.sla_resolucion_vencido = False

    # Flags de alerta y breach (RF-4.3)
    incidencia.sla_en_riesgo_80 = False
    incidencia.sla_breach_100 = incidencia.sla_resolucion_vencido


def recalcular_sla_por_cambio_prioridad(incidencia, nueva_prioridad: str):
    """Si la prioridad cambia en un ticket abierto, ajusta la fecha límite de resolución."""
    if incidencia.estado in ("Resuelto", "Cerrado", "Cancelado"):
        return

    objetivo = OBJETIVOS_SLA.get(nueva_prioridad, OBJETIVOS_SLA["P4 - Baja"])

    # Si aún no hubo primera respuesta, el límite de FRT también se ajusta
    if incidencia.primera_respuesta_en is None:
        incidencia.sla_limite_primera_respuesta = _limite_primera_respuesta(
            nueva_prioridad, incidencia.creada_en, objetivo
        )

    if _es_calendario_continuo(nueva_prioridad):
        nuevo_limite_rt = incidencia.creada_en + timedelta(
            hours=objetivo["rt_horas"],
            seconds=(incidencia.sla_tiempo_pausado_segundos or 0),
        )
    else:
        # Horas hábiles ya consumidas desde la creación hasta ahora
        ahora = datetime.now()
        horas_consumidas = horas_habiles_entre(incidencia.creada_en, ahora)
        horas_restantes = max(0, objetivo["rt_horas"] - horas_consumidas)
        nuevo_limite_rt = sumar_horas_habiles(ahora, horas_restantes)

    incidencia.sla_limite_resolucion = nuevo_limite_rt


def calcular_estado_sla(incidencia, ahora: datetime | None = None) -> str:
    """Calcula el estado del SLA en tiempo real: en_tiempo, en_riesgo, vencido, pausado o cumplido."""
    momento = ahora or datetime.now()

    if incidencia.estado in ("Resuelto", "Cerrado"):
        return "cumplido" if incidencia.sla_resolucion_cumplido else "vencido"

    if incidencia.sla_pausado_en is not None or incidencia.estado in ESTADOS_PAUSA:
        return "pausado"

    if not incidencia.sla_limite_resolucion:
        return "en_tiempo"

    if momento > incidencia.sla_limite_resolucion:
        return "vencido"

    objetivo = OBJETIVOS_SLA.get(incidencia.prioridad, OBJETIVOS_SLA["P4 - Baja"])

    if _es_calendario_continuo(incidencia.prioridad):
        tiempo_total = (
            incidencia.sla_limite_resolucion - incidencia.creada_en
        ).total_seconds()
        tiempo_consumido = (momento - incidencia.creada_en).total_seconds() - (
            incidencia.sla_tiempo_pausado_segundos or 0
        )
    else:
        tiempo_total = objetivo["rt_horas"] * 3600
        tiempo_consumido = (
            horas_habiles_entre(incidencia.creada_en, momento) * 3600
        ) - (incidencia.sla_tiempo_pausado_segundos or 0)

    if tiempo_total <= 0:
        return "vencido"

    porcentaje = tiempo_consumido / tiempo_total

    # Marcar flags de alerta y breach en la instancia si se pasan como argumentos
    if porcentaje >= 1.0:
        incidencia.sla_breach_100 = True
        return "vencido"

    if porcentaje >= 0.75:
        incidencia.sla_en_riesgo_80 = True
        return "en_riesgo"

    return "en_tiempo"
