import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

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


class GrupoSoporte(Base):
    __tablename__ = "grupos_soporte"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    turno_round_robin: Mapped[int] = mapped_column(Integer, default=0)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    miembros: Mapped[list["GrupoMiembro"]] = relationship(
        back_populates="grupo",
        cascade="all, delete-orphan",
        order_by="GrupoMiembro.id.asc()",
    )


class GrupoMiembro(Base):
    __tablename__ = "grupo_miembros"
    __table_args__ = (
        UniqueConstraint("grupo_id", "usuario_id", name="uq_grupo_miembro"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    grupo_id: Mapped[int] = mapped_column(
        ForeignKey("grupos_soporte.id"), index=True
    )
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    es_supervisor: Mapped[bool] = mapped_column(Boolean, default=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    grupo: Mapped["GrupoSoporte"] = relationship(back_populates="miembros")
    usuario: Mapped["Usuario"] = relationship()


class Categoria(Base):
    __tablename__ = "categorias"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("categorias.id"), nullable=True, index=True
    )
    activa: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class ReglaAutomatizacion(Base):
    __tablename__ = "reglas_automatizacion"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    activa: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    orden: Mapped[int] = mapped_column(Integer, default=100)
    logica: Mapped[str] = mapped_column(String(3), default="AND")
    condiciones: Mapped[list] = mapped_column(JSON, default=list)
    acciones: Mapped[dict] = mapped_column(JSON, default=dict)
    creada_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    actualizada_en: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )


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
    grupo_asignado_id: Mapped[int | None] = mapped_column(
        ForeignKey("grupos_soporte.id"), nullable=True, index=True
    )
    categoria_id: Mapped[int | None] = mapped_column(
        ForeignKey("categorias.id"), nullable=True, index=True
    )
    creada_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    actualizada_en: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )
    resuelta_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Encuesta de satisfacción (CSAT) que rellena el solicitante al resolverse
    csat_puntuacion: Mapped[int | None] = mapped_column(Integer, nullable=True)
    csat_comentario: Mapped[str | None] = mapped_column(Text, nullable=True)
    csat_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Métricas y temporizadores de SLA
    sla_limite_primera_respuesta: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    sla_limite_resolucion: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, index=True
    )
    primera_respuesta_en: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    sla_primera_respuesta_cumplido: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True
    )
    sla_pausado_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sla_tiempo_pausado_segundos: Mapped[int] = mapped_column(Integer, default=0)
    sla_resolucion_cumplido: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True
    )
    sla_resolucion_vencido: Mapped[bool] = mapped_column(
        Boolean, default=False, index=True
    )
    sla_en_riesgo_80: Mapped[bool] = mapped_column(
        Boolean, default=False, index=True
    )
    sla_breach_100: Mapped[bool] = mapped_column(
        Boolean, default=False, index=True
    )

    comentarios: Mapped[list["Comentario"]] = relationship(
        back_populates="incidencia",
        cascade="all, delete-orphan",
        order_by="Comentario.creado_en.asc()",
    )
    auditorias: Mapped[list["RegistroAuditoria"]] = relationship(
        back_populates="incidencia",
        cascade="all, delete-orphan",
        order_by="RegistroAuditoria.creado_en.asc()",
    )

    @property
    def estado_sla(self) -> str:
        from . import sla

        return sla.calcular_estado_sla(self)


class Comentario(Base):
    __tablename__ = "comentarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    incidencia_id: Mapped[int] = mapped_column(
        ForeignKey("incidencias.id"), index=True
    )
    autor_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    contenido: Mapped[str] = mapped_column(Text)
    es_interno: Mapped[bool] = mapped_column(Boolean, default=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    autor: Mapped["Usuario"] = relationship()
    incidencia: Mapped["Incidencia"] = relationship(back_populates="comentarios")


class Adjunto(Base):
    __tablename__ = "adjuntos"

    id: Mapped[int] = mapped_column(primary_key=True)
    incidencia_id: Mapped[int] = mapped_column(
        ForeignKey("incidencias.id"), index=True
    )
    subido_por_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id"), index=True
    )
    nombre_original: Mapped[str] = mapped_column(String(255))
    nombre_almacenado: Mapped[str] = mapped_column(String(255), unique=True)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tamano_bytes: Mapped[int] = mapped_column(Integer, default=0)
    es_interno: Mapped[bool] = mapped_column(Boolean, default=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    incidencia: Mapped["Incidencia"] = relationship()
    subido_por: Mapped["Usuario"] = relationship()


class Notificacion(Base):
    __tablename__ = "notificaciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    incidencia_id: Mapped[int] = mapped_column(
        ForeignKey("incidencias.id"), index=True
    )
    tipo: Mapped[str] = mapped_column(String(30), index=True)
    mensaje: Mapped[str] = mapped_column(Text)
    leida: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    usuario: Mapped["Usuario"] = relationship()
    incidencia: Mapped["Incidencia"] = relationship()


class ArticuloConocimiento(Base):
    __tablename__ = "articulos_conocimiento"

    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(255), index=True)
    resumen: Mapped[str | None] = mapped_column(String(500), nullable=True)
    contenido: Mapped[str] = mapped_column(Text)
    categoria_id: Mapped[int | None] = mapped_column(
        ForeignKey("categorias.id"), nullable=True, index=True
    )
    autor_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    es_publico: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    autor: Mapped["Usuario"] = relationship()
    categoria: Mapped["Categoria | None"] = relationship()


class Observador(Base):
    """Persona en copia (CC) que recibe las respuestas públicas del ticket."""

    __tablename__ = "observadores"
    __table_args__ = (
        UniqueConstraint("incidencia_id", "email", name="uq_observador_incidencia_email"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    incidencia_id: Mapped[int] = mapped_column(
        ForeignKey("incidencias.id"), index=True
    )
    email: Mapped[str] = mapped_column(String(255))
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class CorreoIngestado(Base):
    """Mensajes de correo ya procesados, para no duplicar tickets (antiloop)."""

    __tablename__ = "correos_ingestados"

    id: Mapped[int] = mapped_column(primary_key=True)
    mensaje_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    incidencia_id: Mapped[int] = mapped_column(
        ForeignKey("incidencias.id"), index=True
    )
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class RegistroAuditoria(Base):
    __tablename__ = "registros_auditoria"

    id: Mapped[int] = mapped_column(primary_key=True)
    incidencia_id: Mapped[int] = mapped_column(
        ForeignKey("incidencias.id"), index=True
    )
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id"), nullable=True, index=True
    )
    accion: Mapped[str] = mapped_column(String(50))
    campo: Mapped[str | None] = mapped_column(String(50), nullable=True)
    valor_anterior: Mapped[str | None] = mapped_column(Text, nullable=True)
    valor_nuevo: Mapped[str | None] = mapped_column(Text, nullable=True)
    es_interno: Mapped[bool] = mapped_column(Boolean, default=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    usuario: Mapped["Usuario | None"] = relationship()
    incidencia: Mapped["Incidencia"] = relationship(back_populates="auditorias")
