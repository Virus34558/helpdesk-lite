from datetime import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field


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