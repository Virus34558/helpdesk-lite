from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import auth, models, schemas
from ..database import get_db

router = APIRouter(prefix="/conocimiento", tags=["Base de Conocimiento"])

solo_gestores = auth.require_roles(
    models.RolUsuario.AGENTE,
    models.RolUsuario.SUPERVISOR,
    models.RolUsuario.ADMINISTRADOR,
)
solo_admin = auth.require_roles(models.RolUsuario.ADMINISTRADOR)


def _es_solicitante(usuario: models.Usuario) -> bool:
    return usuario.rol == models.RolUsuario.SOLICITANTE.value


def _validar_categoria(db: Session, categoria_id: int | None) -> None:
    if categoria_id is None:
        return
    categoria = db.get(models.Categoria, categoria_id)
    if categoria is None or not categoria.activa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Categoría no encontrada o inactiva",
        )


def _resumen_por_defecto(contenido: str) -> str:
    texto = " ".join(contenido.split())
    return texto[:280] + ("…" if len(texto) > 280 else "")


def _consulta_visible(db: Session, usuario: models.Usuario):
    consulta = db.query(models.ArticuloConocimiento)
    if _es_solicitante(usuario):
        consulta = consulta.filter(
            models.ArticuloConocimiento.es_publico.is_(True)
        )
    return consulta


def _obtener_visible(
    db: Session, articulo_id: int, usuario: models.Usuario
) -> models.ArticuloConocimiento:
    articulo = _consulta_visible(db, usuario).filter(
        models.ArticuloConocimiento.id == articulo_id
    ).first()
    if articulo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artículo no encontrado",
        )
    return articulo


@router.get(
    "",
    response_model=list[schemas.ArticuloResumenRespuesta],
    summary="Listar artículos de la base de conocimiento",
)
def listar_articulos(
    q: str | None = None,
    categoria_id: int | None = None,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.get_current_user),
):
    consulta = _consulta_visible(db, usuario)
    if q and q.strip():
        patron = f"%{q.strip()}%"
        consulta = consulta.filter(
            or_(
                models.ArticuloConocimiento.titulo.ilike(patron),
                models.ArticuloConocimiento.resumen.ilike(patron),
                models.ArticuloConocimiento.contenido.ilike(patron),
            )
        )
    if categoria_id is not None:
        consulta = consulta.filter(
            models.ArticuloConocimiento.categoria_id == categoria_id
        )
    return (
        consulta.order_by(
            models.ArticuloConocimiento.actualizado_en.desc(),
            models.ArticuloConocimiento.id.desc(),
        )
        .limit(100)
        .all()
    )


@router.get(
    "/sugerencias",
    response_model=list[schemas.ArticuloResumenRespuesta],
    summary="Sugerir artículos públicos mientras se escribe el título",
)
def sugerir_articulos(
    q: str = Query(default="", max_length=200),
    db: Session = Depends(get_db),
    _usuario: models.Usuario = Depends(auth.get_current_user),
):
    texto = q.strip()
    if len(texto) < 2:
        return []
    patron = f"%{texto}%"
    return (
        db.query(models.ArticuloConocimiento)
        .filter(
            models.ArticuloConocimiento.es_publico.is_(True),
            or_(
                models.ArticuloConocimiento.titulo.ilike(patron),
                models.ArticuloConocimiento.resumen.ilike(patron),
                models.ArticuloConocimiento.contenido.ilike(patron),
            ),
        )
        .order_by(
            models.ArticuloConocimiento.actualizado_en.desc(),
            models.ArticuloConocimiento.id.desc(),
        )
        .limit(5)
        .all()
    )


@router.get(
    "/{articulo_id}",
    response_model=schemas.ArticuloRespuesta,
    summary="Consultar un artículo",
)
def obtener_articulo(
    articulo_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.get_current_user),
):
    return _obtener_visible(db, articulo_id, usuario)


@router.post(
    "",
    response_model=schemas.ArticuloRespuesta,
    status_code=status.HTTP_201_CREATED,
    summary="Crear artículo (Agente, Supervisor o Administrador)",
)
def crear_articulo(
    datos: schemas.ArticuloCrear,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(solo_gestores),
):
    _validar_categoria(db, datos.categoria_id)
    articulo = models.ArticuloConocimiento(
        titulo=datos.titulo,
        resumen=datos.resumen or _resumen_por_defecto(datos.contenido),
        contenido=datos.contenido,
        categoria_id=datos.categoria_id,
        autor_id=usuario.id,
        es_publico=datos.es_publico,
    )
    db.add(articulo)
    db.commit()
    db.refresh(articulo)
    return articulo


@router.patch(
    "/{articulo_id}",
    response_model=schemas.ArticuloRespuesta,
    summary="Actualizar artículo (Agente, Supervisor o Administrador)",
)
def actualizar_articulo(
    articulo_id: int,
    datos: schemas.ArticuloActualizar,
    db: Session = Depends(get_db),
    _usuario: models.Usuario = Depends(solo_gestores),
):
    articulo = db.get(models.ArticuloConocimiento, articulo_id)
    if articulo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artículo no encontrado",
        )

    cambios = datos.model_dump(exclude_unset=True)
    for campo in ("titulo", "contenido", "es_publico"):
        if campo in cambios and cambios[campo] is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El campo '{campo}' no puede ser nulo",
            )
    if "categoria_id" in cambios:
        _validar_categoria(db, cambios["categoria_id"])

    for campo, valor in cambios.items():
        setattr(articulo, campo, valor)

    db.commit()
    db.refresh(articulo)
    return articulo


@router.delete(
    "/{articulo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar artículo (Administrador)",
)
def eliminar_articulo(
    articulo_id: int,
    db: Session = Depends(get_db),
    _admin: models.Usuario = Depends(solo_admin),
):
    articulo = db.get(models.ArticuloConocimiento, articulo_id)
    if articulo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artículo no encontrado",
        )
    db.delete(articulo)
    db.commit()
