from datetime import datetime
from enum import Enum

# Prefijos por tipo de ticket según especificación ITSM
PREFIJOS_TIPO = {
    "Incidencia": "INC",
    "Solicitud de Servicio": "REQ",
    "Problema": "PRB",
    "Cambio": "CHG",
}

# Matriz ITIL: (impacto, urgencia) -> prioridad
MATRIZ_PRIORIDAD = {
    ("Alto", "Crítica"): "P1 - Crítica",
    ("Alto", "Alta"): "P1 - Crítica",
    ("Alto", "Media"): "P2 - Alta",
    ("Alto", "Baja"): "P3 - Media",
    ("Medio", "Crítica"): "P1 - Crítica",
    ("Medio", "Alta"): "P2 - Alta",
    ("Medio", "Media"): "P3 - Media",
    ("Medio", "Baja"): "P4 - Baja",
    ("Bajo", "Crítica"): "P2 - Alta",
    ("Bajo", "Alta"): "P3 - Media",
    ("Bajo", "Media"): "P4 - Baja",
    ("Bajo", "Baja"): "P4 - Baja",
}

# Transiciones de estado permitidas: estado actual -> estados a los que puede pasar
TRANSICIONES = {
    "Nuevo": {"En progreso", "Cancelado"},
    "En progreso": {"Pendiente de usuario", "Pendiente de tercero", "Resuelto", "Cancelado"},
    "Pendiente de usuario": {"En progreso", "Resuelto", "Cancelado"},
    "Pendiente de tercero": {"En progreso", "Resuelto", "Cancelado"},
    "Resuelto": {"En progreso", "Cerrado"},
    "Cerrado": set(),
    "Cancelado": set(),
}


def _valor(dato):
    """Acepta tanto un texto como un Enum y devuelve siempre el texto."""
    return dato.value if isinstance(dato, Enum) else dato


def calcular_prioridad(impacto, urgencia) -> str:
    return MATRIZ_PRIORIDAD[(_valor(impacto), _valor(urgencia))]


def transicion_permitida(actual, nuevo) -> bool:
    return _valor(nuevo) in TRANSICIONES.get(_valor(actual), set())


def generar_id_legible(tipo, secuencia: int, anio: int | None = None) -> str:
    """Genera un identificador único amigable indexado (ej: INC-2026-000042)."""
    prefijo = PREFIJOS_TIPO.get(_valor(tipo), "INC")
    if anio is None:
        anio = datetime.now().year
    return f"{prefijo}-{anio}-{secuencia:06d}"
