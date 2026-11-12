from datetime import datetime, timedelta

# Tiempos objetivo según ITIL (Sección 4.1 de la especificación ERS)
OBJETIVOS_SLA = {
    "P1 - Crítica": {"frt_minutos": 15, "rt_horas": 4},
    "P2 - Alta": {"frt_minutos": 60, "rt_horas": 8},
    "P3 - Media": {"frt_minutos": 240, "rt_horas": 24},
    "P4 - Baja": {"frt_minutos": 480, "rt_horas": 72},
}

# Estados que congelan el temporizador de resolución ("Stop the Clock", RF-4.2)
ESTADOS_PAUSA = {"Pendiente de usuario", "Pendiente de tercero"}


def inicializar_sla(prioridad: str, fecha_base: datetime | None = None) -> tuple[datetime, datetime]:
    """Calcula las fechas límite de Primera Respuesta (FRT) y Resolución (RT)."""
    ahora = fecha_base or datetime.now()
    objetivo = OBJETIVOS_SLA.get(prioridad, OBJETIVOS_SLA["P4 - Baja"])
    limite_frt = ahora + timedelta(minutes=objetivo["frt_minutos"])
    limite_rt = ahora + timedelta(hours=objetivo["rt_horas"])
    return limite_frt, limite_rt


def registrar_primera_respuesta(incidencia, ahora: datetime | None = None) -> bool:
    """Registra la primera respuesta pública de un técnico si aún no se ha hecho."""
    if incidencia.primera_respuesta_en is not None:
        return False

    momento = ahora or datetime.now()
    incidencia.primera_respuesta_en = momento
    if incidencia.sla_limite_primera_respuesta:
        incidencia.sla_primera_respuesta_cumplido = momento <= incidencia.sla_limite_primera_respuesta
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
            segundos_pausa = max(0, int((momento - incidencia.sla_pausado_en).total_seconds()))
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
        segundos_pausa = max(0, int((momento - incidencia.sla_pausado_en).total_seconds()))
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


def recalcular_sla_por_cambio_prioridad(incidencia, nueva_prioridad: str):
    """Si la prioridad cambia en un ticket abierto, ajusta la fecha límite de resolución."""
    if incidencia.estado in ("Resuelto", "Cerrado", "Cancelado"):
        return

    objetivo = OBJETIVOS_SLA.get(nueva_prioridad, OBJETIVOS_SLA["P4 - Baja"])
    nuevo_limite_rt = incidencia.creada_en + timedelta(
        hours=objetivo["rt_horas"], seconds=(incidencia.sla_tiempo_pausado_segundos or 0)
    )
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

    tiempo_total = (incidencia.sla_limite_resolucion - incidencia.creada_en).total_seconds()
    if tiempo_total <= 0:
        return "vencido"

    tiempo_consumido = (momento - incidencia.creada_en).total_seconds() - (
        incidencia.sla_tiempo_pausado_segundos or 0
    )
    porcentaje = tiempo_consumido / tiempo_total
    if porcentaje >= 0.75:
        return "en_riesgo"

    return "en_tiempo"

