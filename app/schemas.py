from datetime import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, EmailStr


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


class IncidenciaActualizar(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    titulo: str | None = Field(default=None, min_length=3, max_length=100)
    descripcion: str | None = None
    tipo: TipoTicket | None = None
    impacto: Impacto | None = None
    urgencia: Urgencia | None = None
    estado: Estado | None = None
    agente_asignado_id: int | None = None
    nota_resolucion: str | None = Field(default=None, min_length=5, max_length=1000)


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
    creada_en: datetime
    actualizada_en: datetime
    resuelta_en: datetime | None


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