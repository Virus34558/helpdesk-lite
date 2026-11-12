from datetime import datetime

from sqlalchemy.orm import Session

from . import auditoria, models, sla

# Umbral para avisar al agente (RF-4.3: advertencia al 80 %)
PCT_ALERTA_80 = 0.8

ROLES_SUPERVISION = (
    models.RolUsuario.SUPERVISOR.value,
    models.RolUsuario.ADMINISTRADOR.value,
)


def _destinatarios_supervision(db: Session) -> list[models.Usuario]:
    return (
        db.query(models.Usuario)
        .filter(
            models.Usuario.activo.is_(True),
            models.Usuario.rol.in_(ROLES_SUPERVISION),
        )
        .all()
    )


def _notificar(
    db: Session,
    usuario_id: int | None,
    incidencia: models.Incidencia,
    tipo: str,
    mensaje: str,
) -> bool:
    """Crea una notificación si no existía. Devuelve True si es nueva."""
    if usuario_id is None:
        return False

    existente = (
        db.query(models.Notificacion)
        .filter(
            models.Notificacion.usuario_id == usuario_id,
            models.Notificacion.incidencia_id == incidencia.id,
            models.Notificacion.tipo == tipo,
        )
        .first()
    )
    if existente:
        return False

    db.add(
        models.Notificacion(
            usuario_id=usuario_id,
            incidencia_id=incidencia.id,
            tipo=tipo,
            mensaje=mensaje,
        )
    )
    return True


def revisar_slas(db: Session, ahora: datetime | None = None) -> dict:
    """Revisa los SLA abiertos, persiste alertas y genera notificaciones.

    - Al 80 % avisa al agente asignado (o a supervisores si no hay agente).
    - Al 100 % marca el breach y avisa a supervisores y administradores.
    Es idempotente: los flags persistidos evitan repetir avisos.
    """
    momento = ahora or datetime.now()

    abiertas = (
        db.query(models.Incidencia)
        .filter(
            models.Incidencia.estado.notin_(
                ("Resuelto", "Cerrado", "Cancelado")
            ),
            models.Incidencia.sla_limite_resolucion.isnot(None),
        )
        .all()
    )

    alertas_80 = 0
    breaches = 0
    notificaciones = 0

    for incidencia in abiertas:
        # Los estados de pausa tienen el reloj detenido: no generan alertas
        if (
            incidencia.sla_pausado_en is not None
            or incidencia.estado in sla.ESTADOS_PAUSA
        ):
            continue

        porcentaje = sla.porcentaje_consumido_sla(incidencia, momento)
        vencido = momento > incidencia.sla_limite_resolucion

        if (vencido or porcentaje >= 1.0) and not incidencia.sla_breach_100:
            incidencia.sla_breach_100 = True
            incidencia.sla_resolucion_vencido = True

            mensaje = (
                f"SLA vencido: el ticket {incidencia.id_legible} "
                f"({incidencia.titulo}) ha superado el tiempo de resolución."
            )
            for supervisor in _destinatarios_supervision(db):
                if _notificar(
                    db,
                    supervisor.id,
                    incidencia,
                    "sla_vencido",
                    mensaje,
                ):
                    notificaciones += 1

            auditoria.registrar_evento(
                db,
                incidencia_id=incidencia.id,
                usuario_id=None,
                accion="breach_sla",
                campo="sla_resolucion",
                valor_nuevo=f"{porcentaje * 100:.0f}%",
                es_interno=True,
            )
            breaches += 1

        elif (
            porcentaje >= PCT_ALERTA_80
            and not incidencia.sla_en_riesgo_80
        ):
            incidencia.sla_en_riesgo_80 = True

            mensaje = (
                f"SLA en riesgo ({porcentaje * 100:.0f}%): el ticket "
                f"{incidencia.id_legible} ({incidencia.titulo}) está a punto "
                f"de vencer."
            )
            if incidencia.agente_asignado_id:
                destinatarios = [incidencia.agente_asignado_id]
            else:
                destinatarios = [
                    u.id for u in _destinatarios_supervision(db)
                ]

            for usuario_id in destinatarios:
                if _notificar(
                    db,
                    usuario_id,
                    incidencia,
                    "sla_en_riesgo",
                    mensaje,
                ):
                    notificaciones += 1

            auditoria.registrar_evento(
                db,
                incidencia_id=incidencia.id,
                usuario_id=None,
                accion="alerta_sla_80",
                campo="sla_resolucion",
                valor_nuevo=f"{porcentaje * 100:.0f}%",
                es_interno=True,
            )
            alertas_80 += 1

    db.commit()

    return {
        "revisados": len(abiertas),
        "alertas_80": alertas_80,
        "breaches": breaches,
        "notificaciones": notificaciones,
    }


def main() -> None:
    """Ejecución puntual desde cron: python -m app.sla_vigilancia."""
    from .database import SessionLocal

    db = SessionLocal()
    try:
        print(revisar_slas(db))
    finally:
        db.close()


if __name__ == "__main__":
    main()
