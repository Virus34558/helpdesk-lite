from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def _nombre_limpio(valor: str | None) -> str | None:
    if valor is None:
        return None
    valor = valor.strip()
    if len(valor) < 2:
        raise ValueError("El nombre debe tener al menos 2 caracteres")
    return valor


def _titulo_limpio(valor: str | None) -> str | None:
    if valor is None:
        return None
    valor = valor.strip()
    if len(valor) < 3:
        raise ValueError("El título debe tener al menos 3 caracteres")
    return valor


class RolUsuario(str, Enum):
    solicitante = "solicitante"
    agente = "agente"
    supervisor = "supervisor"
    administrador = "administrador"


class UsuarioBase(BaseModel):
    email: EmailStr
    nombre_completo: str = Field(min_length=2, max_length=150)
    rol: RolUsuario = RolUsuario.solicitante
    departamento: str | None = Field(default=None, max_length=100)


class UsuarioRegistro(BaseModel):
    # Sin campo "rol": el registro publico siempre crea un solicitante
    email: EmailStr
    nombre_completo: str = Field(min_length=2, max_length=150)
    departamento: str | None = Field(default=None, max_length=100)
    password: str = Field(min_length=8, max_length=128)


class UsuarioLogin(BaseModel):
    email: EmailStr
    password: str


class UsuarioRespuesta(UsuarioBase):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: int
    activo: bool
    creado_en: datetime


class TokenRespuesta(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioRespuesta


class CategoriaCrear(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    descripcion: str | None = Field(default=None, max_length=1000)
    parent_id: int | None = None
    activa: bool = True

    _validar_nombre = field_validator("nombre")(_nombre_limpio)


class CategoriaActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=100)
    descripcion: str | None = Field(default=None, max_length=1000)
    parent_id: int | None = None
    activa: bool | None = None

    _validar_nombre = field_validator("nombre")(_nombre_limpio)


class CategoriaRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    descripcion: str | None
    parent_id: int | None
    activa: bool
    creado_en: datetime


class MiembroGrupoRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int
    es_supervisor: bool
    usuario: UsuarioRespuesta


class GrupoCrear(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    descripcion: str | None = Field(default=None, max_length=1000)
    activo: bool = True

    _validar_nombre = field_validator("nombre")(_nombre_limpio)


class GrupoActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=100)
    descripcion: str | None = Field(default=None, max_length=1000)
    activo: bool | None = None

    _validar_nombre = field_validator("nombre")(_nombre_limpio)


class GrupoRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    descripcion: str | None
    activo: bool
    turno_round_robin: int
    miembros: list[MiembroGrupoRespuesta] = Field(default_factory=list)
    creado_en: datetime


CampoCondicion = Literal[
    "tipo",
    "canal_origen",
    "impacto",
    "urgencia",
    "prioridad",
    "categoria_id",
    "grupo_asignado_id",
    "solicitante_departamento",
    "titulo",
    "descripcion",
]


class CondicionRegla(BaseModel):
    campo: CampoCondicion
    operador: Literal["=", "!=", "contiene", "en"] = "="
    valor: Any = None


class AccionesRegla(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grupo_id: int | None = None
    agente_id: int | None = None
    auto_asignar: Literal["round_robin", "load_balanced"] | None = None


class ReglaCrear(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    descripcion: str | None = Field(default=None, max_length=1000)
    activa: bool = True
    orden: int = 100
    logica: Literal["AND", "OR"] = "AND"
    condiciones: list[CondicionRegla] = Field(default_factory=list)
    acciones: AccionesRegla = Field(default_factory=AccionesRegla)

    _validar_nombre = field_validator("nombre")(_nombre_limpio)


class ReglaActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    descripcion: str | None = Field(default=None, max_length=1000)
    activa: bool | None = None
    orden: int | None = None
    logica: Literal["AND", "OR"] | None = None
    condiciones: list[CondicionRegla] | None = None
    acciones: AccionesRegla | None = None

    _validar_nombre = field_validator("nombre")(_nombre_limpio)


class ReglaRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    descripcion: str | None
    activa: bool
    orden: int
    logica: str
    condiciones: list[CondicionRegla]
    acciones: AccionesRegla
    creada_en: datetime
    actualizada_en: datetime


class ArticuloCrear(BaseModel):
    titulo: str = Field(min_length=3, max_length=255)
    resumen: str | None = Field(default=None, max_length=500)
    contenido: str = Field(min_length=1, max_length=20000)
    categoria_id: int | None = None
    es_publico: bool = True

    _validar_titulo = field_validator("titulo")(_titulo_limpio)


class ArticuloActualizar(BaseModel):
    titulo: str | None = Field(default=None, min_length=3, max_length=255)
    resumen: str | None = Field(default=None, max_length=500)
    contenido: str | None = Field(default=None, min_length=1, max_length=20000)
    categoria_id: int | None = None
    es_publico: bool | None = None

    _validar_titulo = field_validator("titulo")(_titulo_limpio)


class ArticuloResumenRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    titulo: str
    resumen: str | None
    categoria_id: int | None
    autor_id: int
    es_publico: bool
    actualizado_en: datetime


class ArticuloRespuesta(ArticuloResumenRespuesta):
    contenido: str
    creado_en: datetime


class TipoTicket(str, Enum):
    incidencia = "Incidencia"
    solicitud = "Solicitud de Servicio"
    problema = "Problema"
    cambio = "Cambio"


class CanalOrigen(str, Enum):
    portal_web = "Portal Web"
    email = "Email"
    api = "API / Monitoreo"
    telefono = "Teléfono"
    chat = "Chat"


class Impacto(str, Enum):
    bajo = "Bajo"
    medio = "Medio"
    alto = "Alto"


class Urgencia(str, Enum):
    baja = "Baja"
    media = "Media"
    alta = "Alta"
    critica = "Crítica"


class Prioridad(str, Enum):
    p1 = "P1 - Crítica"
    p2 = "P2 - Alta"
    p3 = "P3 - Media"
    p4 = "P4 - Baja"


class Estado(str, Enum):
    nuevo = "Nuevo"
    en_progreso = "En progreso"
    pendiente_usuario = "Pendiente de usuario"
    pendiente_tercero = "Pendiente de tercero"
    resuelto = "Resuelto"
    cerrado = "Cerrado"
    cancelado = "Cancelado"


class IncidenciaCrear(BaseModel):
    model_config = ConfigDict(use_enum_values=True, validate_default=True)

    titulo: str = Field(min_length=3, max_length=100)
    descripcion: str = ""
    tipo: TipoTicket = TipoTicket.incidencia
    canal_origen: CanalOrigen = CanalOrigen.portal_web
    impacto: Impacto = Impacto.bajo
    urgencia: Urgencia = Urgencia.media
    categoria_id: int | None = None
    grupo_asignado_id: int | None = None


class IncidenciaActualizar(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    titulo: str | None = Field(default=None, min_length=3, max_length=100)
    descripcion: str | None = None
    tipo: TipoTicket | None = None
    impacto: Impacto | None = None
    urgencia: Urgencia | None = None
    estado: Estado | None = None
    agente_asignado_id: int | None = None
    grupo_asignado_id: int | None = None
    categoria_id: int | None = None
    nota_resolucion: str | None = Field(default=None, min_length=5, max_length=1000)
    version: int | None = Field(default=None, ge=1)


class AsignarAgente(BaseModel):
    agente_id: int | None = None


class ResolverIncidencia(BaseModel):
    nota_resolucion: str = Field(min_length=5, max_length=1000)


class IncidenciaRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    id_legible: str
    tipo: TipoTicket
    canal_origen: CanalOrigen
    titulo: str
    descripcion: str
    impacto: Impacto
    urgencia: Urgencia
    prioridad: Prioridad
    estado: Estado
    nota_resolucion: str | None
    solicitante_id: int
    agente_asignado_id: int | None
    grupo_asignado_id: int | None = None
    categoria_id: int | None = None
    creada_en: datetime
    actualizada_en: datetime
    resuelta_en: datetime | None
    version: int = 1
    csat_puntuacion: int | None = None
    csat_comentario: str | None = None

    # Métricas y temporizadores de SLA
    sla_limite_primera_respuesta: datetime | None = None
    sla_limite_resolucion: datetime | None = None
    primera_respuesta_en: datetime | None = None
    sla_primera_respuesta_cumplido: bool | None = None
    sla_tiempo_pausado_segundos: int = 0
    sla_resolucion_cumplido: bool | None = None
    sla_resolucion_vencido: bool = False
    sla_en_riesgo_80: bool = False
    sla_breach_100: bool = False
    estado_sla: str | None = None


class AutorComentarioRespuesta(BaseModel):
    # Sin email: un solicitante no debe ver el correo corporativo de los tecnicos
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: int
    nombre_completo: str
    rol: RolUsuario


class ComentarioCrear(BaseModel):
    contenido: str = Field(min_length=1, max_length=5000)
    es_interno: bool = False


class ComentarioRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: int
    incidencia_id: int
    autor_id: int
    autor: AutorComentarioRespuesta
    contenido: str
    es_interno: bool
    creado_en: datetime


class AutorAuditoriaRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: int
    nombre_completo: str
    rol: RolUsuario


class RegistroAuditoriaRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: int
    incidencia_id: int
    usuario_id: int | None
    usuario: AutorAuditoriaRespuesta | None
    accion: str
    campo: str | None
    valor_anterior: str | None
    valor_nuevo: str | None
    es_interno: bool
    creado_en: datetime


class AdjuntoRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    incidencia_id: int
    subido_por_id: int
    nombre_original: str
    content_type: str | None
    tamano_bytes: int
    es_interno: bool
    creado_en: datetime


class NotificacionRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int
    incidencia_id: int
    tipo: str
    mensaje: str
    leida: bool
    creado_en: datetime


class DistribucionItem(BaseModel):
    valor: str
    total: int


class DistribucionCategoriaItem(BaseModel):
    categoria_id: int | None
    nombre: str
    total: int


class ResumenDashboard(BaseModel):
    generado_en: datetime
    creados_hoy: int
    resueltos_hoy: int
    abiertos: int
    sin_asignar: int
    sla_en_riesgo: int
    sla_vencido: int
    sla_pausado: int
    por_estado: list[DistribucionItem]
    por_prioridad: list[DistribucionItem]
    por_canal: list[DistribucionItem]
    por_categoria: list[DistribucionCategoriaItem]


class KpisReporte(BaseModel):
    desde: date | None
    hasta: date | None
    tickets_creados: int
    tickets_resueltos: int
    cumplimiento_sla_pct: float | None
    mtta_minutos: float | None
    mttr_horas: float | None
    fcr_pct: float | None
    csat_respuestas: int = 0
    csat_media: float | None = None


class EncuestaCSATCrear(BaseModel):
    puntuacion: int = Field(ge=1, le=5)
    comentario: str | None = Field(default=None, max_length=1000)


class EncuestaCSATRespuesta(BaseModel):
    puntuacion: int
    comentario: str | None
    creada_en: datetime


class CorreoEntrante(BaseModel):
    """Correo normalizado que llega desde el conector IMAP/Graph/webhook."""

    remitente: EmailStr
    asunto: str = Field(default="", max_length=255)
    cuerpo: str = Field(default="", max_length=20000)
    mensaje_id: str | None = Field(default=None, max_length=255)
    en_respuesta_a: str | None = Field(default=None, max_length=255)
    auto_submitted: bool = False


class RespuestaIngesta(BaseModel):
    resultado: str
    incidencia_id: int | None = None
    motivo: str | None = None


class ObservadorCrear(BaseModel):
    email: EmailStr


class ObservadorRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    creado_en: datetime


class FusionCrear(BaseModel):
    nota: str | None = Field(default=None, max_length=1000)


class SugerenciaTriaje(BaseModel):
    tipo: TipoTicket
    impacto: Impacto
    urgencia: Urgencia
    prioridad: Prioridad
    categoria_id: int | None = None
    categoria: str | None = None
    motivo: str = ""


class MacroCrear(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    texto: str = Field(min_length=2, max_length=5000)
    es_interna: bool = False
    activa: bool = True


class MacroActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    texto: str | None = Field(default=None, min_length=2, max_length=5000)
    es_interna: bool | None = None
    activa: bool | None = None


class MacroRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    texto: str
    es_interna: bool
    activa: bool
