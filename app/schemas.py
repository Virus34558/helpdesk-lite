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


class UsuarioRegistro(UsuarioBase):
    password: str = Field(min_length=6, max_length=128)


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
    impacto: Impacto = Impacto.bajo
    urgencia: Urgencia = Urgencia.media


class IncidenciaActualizar(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    titulo: str | None = Field(default=None, min_length=3, max_length=100)
    descripcion: str | None = None
    impacto: Impacto | None = None
    urgencia: Urgencia | None = None
    estado: Estado | None = None
    nota_resolucion: str | None = Field(default=None, min_length=5, max_length=1000)


class ResolverIncidencia(BaseModel):
    nota_resolucion: str = Field(min_length=5, max_length=1000)


class IncidenciaRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    titulo: str
    descripcion: str
    impacto: Impacto
    urgencia: Urgencia
    prioridad: Prioridad
    estado: Estado
    nota_resolucion: str | None
    solicitante_id: int
    creada_en: datetime
    actualizada_en: datetime
    resuelta_en: datetime | None