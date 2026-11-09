import enum
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


class RolUsuario(str, enum.Enum):
    SOLICITANTE = "solicitante"
    AGENTE = "agente"
    SUPERVISOR = "supervisor"
    ADMINISTRADOR = "administrador"


class TipoTicket(str, enum.Enum):
    INCIDENCIA = "Incidencia"
    SOLICITUD = "Solicitud de Servicio"
    PROBLEMA = "Problema"
    CAMBIO = "Cambio"


class CanalOrigen(str, enum.Enum):
    PORTAL_WEB = "Portal Web"
    EMAIL = "Email"
    API = "API / Monitoreo"
    TELEFONO = "Teléfono"
    CHAT = "Chat"


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    nombre_completo: Mapped[str] = mapped_column(String(150))
    password_hash: Mapped[str] = mapped_column(String(255))
    rol: Mapped[str] = mapped_column(String(30), default=RolUsuario.SOLICITANTE.value, index=True)
    departamento: Mapped[str | None] = mapped_column(String(100), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Incidencia(Base):
    __tablename__ = "incidencias"

    id: Mapped[int] = mapped_column(primary_key=True)
    id_legible: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    tipo: Mapped[str] = mapped_column(String(30), default=TipoTicket.INCIDENCIA.value)
    canal_origen: Mapped[str] = mapped_column(String(30), default=CanalOrigen.PORTAL_WEB.value)
    titulo: Mapped[str] = mapped_column(String(100))
    descripcion: Mapped[str] = mapped_column(Text, default="")
    impacto: Mapped[str] = mapped_column(String(10), default="Bajo")
    urgencia: Mapped[str] = mapped_column(String(10), default="Media")
    prioridad: Mapped[str] = mapped_column(String(15), default="P4 - Baja")
    estado: Mapped[str] = mapped_column(String(25), default="Nuevo")
    nota_resolucion: Mapped[str | None] = mapped_column(Text, nullable=True)
    solicitante_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    agente_asignado_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id"), nullable=True, index=True
    )
    creada_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    actualizada_en: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )
    resuelta_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
