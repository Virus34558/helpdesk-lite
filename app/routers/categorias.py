from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import auth, models, schemas
from ..database import get_db

router = APIRouter(prefix="/categorias", tags=["Categorías"])

solo_admin = auth.require_roles(models.RolUsuario.ADMINISTRADOR)


def _comprobar_nombre_unico(
    db: Session, nombre: str, categoria_id: int | None = None
) -> None:
    consulta = db.query(models.Categoria).filter(
        models.Categoria.nombre == nombre.strip()
    )
    if categoria_id is not None:
        consulta = consulta.filter(models.Categoria.id != categoria_id)
    if consulta.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una categoría con ese nombre",
        )


def _validar_padre(
    db: Session, parent_id: int | None, categoria_id: int | None = None
) -> None:
    if parent_id is None:
        return
    if categoria_id is not None and parent_id == categoria_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Una categoría no puede ser su propia categoría padre",
        )
    padre = db.get(models.Categoria, parent_id)
    if padre is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Categoría padre no encontrada",
        )

    # Evitar ciclos: el padre no puede ser descendiente de la categoría actual
    if categoria_id is not None:
        visitado = padre
        while visitado is not None:
            if visitado.id == categoria_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="La categoría padre crearía un ciclo",
                )
            visitado = (
                db.get(models.Categoria, visitado.parent_id)
                if visitado.parent_id
                else None
            )


@router.get(
    "",
    response_model=list[schemas.CategoriaRespuesta],
    summary="Listar categorías",
)
def listar_categorias(
    incluir_inactivas: bool = False,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.get_current_user),
):
    consulta = db.query(models.Categoria)
    es_admin = usuario.rol == models.RolUsuario.ADMINISTRADOR.value
    if not (incluir_inactivas and es_admin):
        consulta = consulta.filter(models.Categoria.activa.is_(True))
    return consulta.order_by(models.Categoria.nombre.asc()).all()


@router.post(
    "",
    response_model=schemas.CategoriaRespuesta,
    status_code=status.HTTP_201_CREATED,
    summary="Crear categoría (Administrador)",
)
def crear_categoria(
    datos: schemas.CategoriaCrear,
    db: Session = Depends(get_db),
    _admin: models.Usuario = Depends(solo_admin),
):
    _comprobar_nombre_unico(db, datos.nombre)
    _validar_padre(db, datos.parent_id)

    categoria = models.Categoria(
        nombre=datos.nombre.strip(),
        descripcion=datos.descripcion,
        parent_id=datos.parent_id,
        activa=datos.activa,
    )
    db.add(categoria)
    db.commit()
    db.refresh(categoria)
    return categoria


@router.patch(
    "/{categoria_id}",
    response_model=schemas.CategoriaRespuesta,
    summary="Actualizar categoría (Administrador)",
)
def actualizar_categoria(
    categoria_id: int,
    datos: schemas.CategoriaActualizar,
    db: Session = Depends(get_db),
    _admin: models.Usuario = Depends(solo_admin),
):
    categoria = db.get(models.Categoria, categoria_id)
    if categoria is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Categoría no encontrada",
        )

    cambios = datos.model_dump(exclude_unset=True)
    if "nombre" in cambios and cambios["nombre"] is not None:
        _comprobar_nombre_unico(db, cambios["nombre"], categoria_id)
        cambios["nombre"] = cambios["nombre"].strip()
    if "parent_id" in cambios:
        _validar_padre(db, cambios["parent_id"], categoria_id)

    for campo, valor in cambios.items():
        setattr(categoria, campo, valor)

    db.commit()
    db.refresh(categoria)
    return categoria
