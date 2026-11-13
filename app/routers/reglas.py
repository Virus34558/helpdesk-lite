from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import auth, models, schemas
from ..database import get_db

router = APIRouter(prefix="/reglas", tags=["Automatización"])

solo_admin = auth.require_roles(models.RolUsuario.ADMINISTRADOR)


def _comprobar_nombre_unico(
    db: Session, nombre: str, regla_id: int | None = None
) -> None:
    consulta = db.query(models.ReglaAutomatizacion).filter(
        models.ReglaAutomatizacion.nombre == nombre.strip()
    )
    if regla_id is not None:
        consulta = consulta.filter(models.ReglaAutomatizacion.id != regla_id)
    if consulta.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una regla con ese nombre",
        )


def _validar_acciones(db: Session, acciones: dict) -> None:
    grupo_id = acciones.get("grupo_id")
    agente_id = acciones.get("agente_id")

    if grupo_id is not None:
        grupo = db.get(models.GrupoSoporte, grupo_id)
        if grupo is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Grupo de destino no encontrado",
            )
        if not grupo.activo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El grupo de destino está inactivo",
            )

    if agente_id is not None:
        agente = db.get(models.Usuario, agente_id)
        if agente is None or not agente.activo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agente de destino no encontrado o inactivo",
            )
        if agente.rol == models.RolUsuario.SOLICITANTE.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El destino no puede ser un solicitante",
            )
        if grupo_id is not None:
            pertenece = (
                db.query(models.GrupoMiembro)
                .filter(
                    models.GrupoMiembro.grupo_id == grupo_id,
                    models.GrupoMiembro.usuario_id == agente_id,
                )
                .first()
            )
            if pertenece is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El agente de destino no pertenece al grupo indicado",
                )


@router.get(
    "",
    response_model=list[schemas.ReglaRespuesta],
    summary="Listar reglas de automatización (Administrador)",
)
def listar_reglas(
    db: Session = Depends(get_db),
    _admin: models.Usuario = Depends(solo_admin),
):
    return (
        db.query(models.ReglaAutomatizacion)
        .order_by(
            models.ReglaAutomatizacion.orden.asc(),
            models.ReglaAutomatizacion.id.asc(),
        )
        .all()
    )


@router.post(
    "",
    response_model=schemas.ReglaRespuesta,
    status_code=status.HTTP_201_CREATED,
    summary="Crear regla de automatización (Administrador)",
)
def crear_regla(
    datos: schemas.ReglaCrear,
    db: Session = Depends(get_db),
    _admin: models.Usuario = Depends(solo_admin),
):
    _comprobar_nombre_unico(db, datos.nombre)
    acciones = datos.acciones.model_dump(exclude_none=True)
    _validar_acciones(db, acciones)

    regla = models.ReglaAutomatizacion(
        nombre=datos.nombre.strip(),
        descripcion=datos.descripcion,
        activa=datos.activa,
        orden=datos.orden,
        logica=datos.logica,
        condiciones=[c.model_dump() for c in datos.condiciones],
        acciones=acciones,
    )
    db.add(regla)
    db.commit()
    db.refresh(regla)
    return regla


@router.patch(
    "/{regla_id}",
    response_model=schemas.ReglaRespuesta,
    summary="Actualizar regla de automatización (Administrador)",
)
def actualizar_regla(
    regla_id: int,
    datos: schemas.ReglaActualizar,
    db: Session = Depends(get_db),
    _admin: models.Usuario = Depends(solo_admin),
):
    regla = db.get(models.ReglaAutomatizacion, regla_id)
    if regla is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Regla no encontrada",
        )

    cambios = datos.model_dump(exclude_unset=True)
    if "nombre" in cambios and cambios["nombre"] is not None:
        _comprobar_nombre_unico(db, cambios["nombre"], regla_id)
        cambios["nombre"] = cambios["nombre"].strip()
    if "condiciones" in cambios and cambios["condiciones"] is not None:
        cambios["condiciones"] = [
            schemas.CondicionRegla(**c).model_dump()
            for c in cambios["condiciones"]
        ]
    if "acciones" in cambios and cambios["acciones"] is not None:
        acciones = schemas.AccionesRegla(**cambios["acciones"]).model_dump(
            exclude_none=True
        )
        _validar_acciones(db, acciones)
        cambios["acciones"] = acciones

    for campo, valor in cambios.items():
        setattr(regla, campo, valor)

    db.commit()
    db.refresh(regla)
    return regla


@router.delete(
    "/{regla_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar regla de automatización (Administrador)",
)
def eliminar_regla(
    regla_id: int,
    db: Session = Depends(get_db),
    _admin: models.Usuario = Depends(solo_admin),
):
    regla = db.get(models.ReglaAutomatizacion, regla_id)
    if regla is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Regla no encontrada",
        )
    db.delete(regla)
    db.commit()
