from sqlalchemy.orm import Session
from . import models


def registrar_evento(
    db: Session,
    incidencia_id: int,
    usuario_id: int | None,
    accion: str,
    campo: str | None = None,
    valor_anterior: str | None = None,
    valor_nuevo: str | None = None,
    es_interno: bool = False,
) -> models.RegistroAuditoria:
    """Registra una entrada inmutable de auditoría (audit log) sobre una incidencia."""
    evento = models.RegistroAuditoria(
        incidencia_id=incidencia_id,
        usuario_id=usuario_id,
        accion=accion,
        campo=campo,
        valor_anterior=str(valor_anterior) if valor_anterior is not None else None,
        valor_nuevo=str(valor_nuevo) if valor_nuevo is not None else None,
        es_interno=es_interno,
    )
    db.add(evento)
    return evento

