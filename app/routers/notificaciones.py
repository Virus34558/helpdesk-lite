from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import auth, models, schemas
from ..database import get_db

router = APIRouter(prefix="/notificaciones", tags=["Notificaciones"])


@router.get(
    "",
    response_model=list[schemas.NotificacionRespuesta],
    summary="Listar mis notificaciones (SLA, avisos internos)",
)
def listar_notificaciones(
    solo_no_leidas: bool = False,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.get_current_user),
):
    consulta = db.query(models.Notificacion).filter(
        models.Notificacion.usuario_id == usuario.id
    )
    if solo_no_leidas:
        consulta = consulta.filter(models.Notificacion.leida.is_(False))
    return consulta.order_by(
        models.Notificacion.leida.asc(),
        models.Notificacion.creado_en.desc(),
    ).all()


@router.post(
    "/{notificacion_id}/leer",
    response_model=schemas.NotificacionRespuesta,
    summary="Marcar una notificación como leída",
)
def marcar_notificacion_leida(
    notificacion_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.get_current_user),
):
    notificacion = db.get(models.Notificacion, notificacion_id)
    if notificacion is None or notificacion.usuario_id != usuario.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notificación no encontrada",
        )

    notificacion.leida = True
    db.commit()
    db.refresh(notificacion)
    return notificacion
