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


class Prioridad(str, Enum):
    alta = "Alta"
    media = "Media"
    baja = "Baja"


class Estado(str, Enum):
    abierta = "Abierta"
    en_proceso = "En proceso"
    resuelta = "Resuelta"


class IncidenciaCrear(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    titulo: str = Field(min_length=3, max_length=100)
    descripcion: str = ""
    prioridad: Prioridad = Prioridad.media


class IncidenciaActualizar(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    titulo: str | None = Field(default=None, min_length=3, max_length=100)
    descripcion: str | None = None
    prioridad: Prioridad | None = None
    estado: Estado | None = None


class IncidenciaRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    titulo: str
    descripcion: str
    prioridad: Prioridad
    estado: Estado
    creada_en: datetime
    resuelta_en: datetime | None
