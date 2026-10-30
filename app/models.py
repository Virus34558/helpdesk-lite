from datetime import datetime
from sqlalchemy import String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


class Incidencia(Base):
    __tablename__ = "incidencias"

    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(100))
    descripcion: Mapped[str] = mapped_column(Text, default="")
    prioridad: Mapped[str] = mapped_column(String(10), default="Media")
    estado: Mapped[str] = mapped_column(String(15), default="Abierta")
    creada_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    resuelta_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)