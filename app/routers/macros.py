"""Plantillas de respuesta (macros de texto) para agentes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import auth, models, schemas
from ..database import get_db

router = APIRouter(prefix="/macros", tags=["Plantillas de respuesta"])

solo_staff = auth.require_roles(
    models.RolUsuario.AGENTE,
    models.RolUsuario.SUPERVISOR,
    models.RolUsuario.ADMINISTRADOR,
)
solo_admin = auth.require_roles(models.RolUsuario.ADMINISTRADOR)


@router.get(
    "",
    response_model=list[schemas.MacroRespuesta],
    summary="Listar plantillas activas (Agente, Supervisor o Administrador)",
)
def listar_macros(
    db: Session = Depends(get_db),
    _staff: models.Usuario = Depends(solo_staff),
):
    return (
        db.query(models.Macro)
        .filter(models.Macro.activa.is_(True))
        .order_by(models.Macro.nombre.asc())
        .all()
    )


@router.post(
    "",
    response_model=schemas.MacroRespuesta,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una plantilla (Administrador)",
)
def crear_macro(
    datos: schemas.MacroCrear,
    db: Session = Depends(get_db),
    _admin: models.Usuario = Depends(solo_admin),
):
    nombre = datos.nombre.strip()
    if db.query(models.Macro).filter(models.Macro.nombre == nombre).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una plantilla con ese nombre",
        )

    macro = models.Macro(
        nombre=nombre,
        texto=datos.texto.strip(),
        es_interna=datos.es_interna,
        activa=datos.activa,
    )
    db.add(macro)
    db.commit()
    db.refresh(macro)
    return macro


@router.patch(
    "/{macro_id}",
    response_model=schemas.MacroRespuesta,
    summary="Actualizar una plantilla (Administrador)",
)
def actualizar_macro(
    macro_id: int,
    datos: schemas.MacroActualizar,
    db: Session = Depends(get_db),
    _admin: models.Usuario = Depends(solo_admin),
):
    macro = db.get(models.Macro, macro_id)
    if macro is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plantilla no encontrada",
        )

    cambios = datos.model_dump(exclude_unset=True)
    if "nombre" in cambios:
        nombre = cambios["nombre"].strip()
        repetido = (
            db.query(models.Macro)
            .filter(models.Macro.nombre == nombre, models.Macro.id != macro.id)
            .first()
        )
        if repetido is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe una plantilla con ese nombre",
            )
        cambios["nombre"] = nombre
    if "texto" in cambios:
        cambios["texto"] = cambios["texto"].strip()

    for campo, valor in cambios.items():
        setattr(macro, campo, valor)

    db.commit()
    db.refresh(macro)
    return macro


@router.delete(
    "/{macro_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar una plantilla (Administrador)",
)
def eliminar_macro(
    macro_id: int,
    db: Session = Depends(get_db),
    _admin: models.Usuario = Depends(solo_admin),
):
    macro = db.get(models.Macro, macro_id)
    if macro is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plantilla no encontrada",
        )
    db.delete(macro)
    db.commit()
    return None
