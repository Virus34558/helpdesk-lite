from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import auth, models, schemas
from ..database import get_db

router = APIRouter(prefix="/grupos", tags=["Grupos de soporte"])

solo_admin = auth.require_roles(models.RolUsuario.ADMINISTRADOR)
solo_gestores = auth.require_roles(
    models.RolUsuario.AGENTE,
    models.RolUsuario.SUPERVISOR,
    models.RolUsuario.ADMINISTRADOR,
)


def _comprobar_nombre_unico(
    db: Session, nombre: str, grupo_id: int | None = None
) -> None:
    consulta = db.query(models.GrupoSoporte).filter(
        models.GrupoSoporte.nombre == nombre.strip()
    )
    if grupo_id is not None:
        consulta = consulta.filter(models.GrupoSoporte.id != grupo_id)
    if consulta.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un grupo con ese nombre",
        )


def _obtener_grupo(db: Session, grupo_id: int) -> models.GrupoSoporte:
    grupo = db.get(models.GrupoSoporte, grupo_id)
    if grupo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grupo no encontrado",
        )
    return grupo


@router.get(
    "",
    response_model=list[schemas.GrupoRespuesta],
    summary="Listar grupos de soporte",
)
def listar_grupos(
    incluir_inactivos: bool = False,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(solo_gestores),
):
    consulta = db.query(models.GrupoSoporte)
    es_admin = usuario.rol == models.RolUsuario.ADMINISTRADOR.value
    if not (incluir_inactivos and es_admin):
        consulta = consulta.filter(models.GrupoSoporte.activo.is_(True))
    return consulta.order_by(models.GrupoSoporte.nombre.asc()).all()


@router.post(
    "",
    response_model=schemas.GrupoRespuesta,
    status_code=status.HTTP_201_CREATED,
    summary="Crear grupo de soporte (Administrador)",
)
def crear_grupo(
    datos: schemas.GrupoCrear,
    db: Session = Depends(get_db),
    _admin: models.Usuario = Depends(solo_admin),
):
    _comprobar_nombre_unico(db, datos.nombre)
    grupo = models.GrupoSoporte(
        nombre=datos.nombre.strip(),
        descripcion=datos.descripcion,
        activo=datos.activo,
    )
    db.add(grupo)
    db.commit()
    db.refresh(grupo)
    return grupo


@router.patch(
    "/{grupo_id}",
    response_model=schemas.GrupoRespuesta,
    summary="Actualizar grupo de soporte (Administrador)",
)
def actualizar_grupo(
    grupo_id: int,
    datos: schemas.GrupoActualizar,
    db: Session = Depends(get_db),
    _admin: models.Usuario = Depends(solo_admin),
):
    grupo = _obtener_grupo(db, grupo_id)
    cambios = datos.model_dump(exclude_unset=True)
    for campo in ("nombre", "activo"):
        if campo in cambios and cambios[campo] is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El campo '{campo}' no puede ser nulo",
            )
    if "nombre" in cambios:
        _comprobar_nombre_unico(db, cambios["nombre"], grupo_id)
        cambios["nombre"] = cambios["nombre"].strip()

    for campo, valor in cambios.items():
        setattr(grupo, campo, valor)

    db.commit()
    db.refresh(grupo)
    return grupo


@router.delete(
    "/{grupo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar grupo de soporte (Administrador)",
)
def eliminar_grupo(
    grupo_id: int,
    db: Session = Depends(get_db),
    _admin: models.Usuario = Depends(solo_admin),
):
    grupo = _obtener_grupo(db, grupo_id)

    tickets = (
        db.query(models.Incidencia.id)
        .filter(models.Incidencia.grupo_asignado_id == grupo_id)
        .count()
    )
    if tickets:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"El grupo tiene {tickets} incidencia(s) asignada(s). "
                "Reasígnalas o desactiva el grupo en su lugar."
            ),
        )

    reglas = [
        regla.nombre
        for regla in db.query(models.ReglaAutomatizacion).all()
        if (regla.acciones or {}).get("grupo_id") == grupo_id
    ]
    if reglas:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "El grupo lo usan estas reglas de automatización: "
                + ", ".join(reglas)
            ),
        )

    db.delete(grupo)
    db.commit()


@router.post(
    "/{grupo_id}/miembros/{usuario_id}",
    response_model=schemas.GrupoRespuesta,
    status_code=status.HTTP_201_CREATED,
    summary="Añadir un técnico al grupo (Administrador)",
)
def agregar_miembro(
    grupo_id: int,
    usuario_id: int,
    es_supervisor: bool = False,
    db: Session = Depends(get_db),
    _admin: models.Usuario = Depends(solo_admin),
):
    grupo = _obtener_grupo(db, grupo_id)
    usuario = db.get(models.Usuario, usuario_id)
    if usuario is None or not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado o inactivo",
        )
    if usuario.rol == models.RolUsuario.SOLICITANTE.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se pueden añadir técnicos a un grupo de soporte",
        )

    existente = (
        db.query(models.GrupoMiembro)
        .filter(
            models.GrupoMiembro.grupo_id == grupo_id,
            models.GrupoMiembro.usuario_id == usuario_id,
        )
        .first()
    )
    if existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El usuario ya pertenece a este grupo",
        )

    db.add(
        models.GrupoMiembro(
            grupo_id=grupo_id,
            usuario_id=usuario_id,
            es_supervisor=es_supervisor,
        )
    )
    db.commit()
    db.refresh(grupo)
    return grupo


@router.delete(
    "/{grupo_id}/miembros/{usuario_id}",
    response_model=schemas.GrupoRespuesta,
    summary="Quitar un técnico del grupo (Administrador)",
)
def quitar_miembro(
    grupo_id: int,
    usuario_id: int,
    db: Session = Depends(get_db),
    _admin: models.Usuario = Depends(solo_admin),
):
    grupo = _obtener_grupo(db, grupo_id)
    miembro = (
        db.query(models.GrupoMiembro)
        .filter(
            models.GrupoMiembro.grupo_id == grupo_id,
            models.GrupoMiembro.usuario_id == usuario_id,
        )
        .first()
    )
    if miembro is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario no pertenece a este grupo",
        )

    db.delete(miembro)
    db.commit()
    db.refresh(grupo)
    return grupo
