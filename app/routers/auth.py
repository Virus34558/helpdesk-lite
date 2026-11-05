from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import auth, models, schemas
from ..database import get_db

router = APIRouter(prefix="/auth", tags=["Autenticación"])


class CambioRol(BaseModel):
    rol: schemas.RolUsuario


@router.post(
    "/registro",
    response_model=schemas.UsuarioRespuesta,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo usuario",
)
def registrar_usuario(
    datos: schemas.UsuarioRegistro, db: Session = Depends(get_db)
):
    usuario_existente = (
        db.query(models.Usuario)
        .filter(models.Usuario.email == datos.email.lower().strip())
        .first()
    )
    if usuario_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El correo electrónico ya está registrado",
        )

    # Si es el primer usuario en toda la base de datos, se le otorga rol de administrador
    total_usuarios = db.query(models.Usuario).count()
    rol_asignado = (
        models.RolUsuario.ADMINISTRADOR.value
        if total_usuarios == 0
        else (datos.rol.value if hasattr(datos.rol, "value") else str(datos.rol))
    )

    nuevo_usuario = models.Usuario(
        email=datos.email.lower().strip(),
        nombre_completo=datos.nombre_completo.strip(),
        password_hash=auth.hash_password(datos.password),
        rol=rol_asignado,
        departamento=datos.departamento,
        activo=True,
    )
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)
    return nuevo_usuario


@router.post(
    "/login",
    response_model=schemas.TokenRespuesta,
    summary="Iniciar sesión y obtener token JWT",
)
def iniciar_sesion(
    credenciales: schemas.UsuarioLogin, db: Session = Depends(get_db)
):
    usuario = (
        db.query(models.Usuario)
        .filter(models.Usuario.email == credenciales.email.lower().strip())
        .first()
    )
    if not usuario or not auth.verify_password(
        credenciales.password, usuario.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo electrónico o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta se encuentra inactiva",
        )

    token = auth.create_access_token(
        data={"sub": usuario.email, "rol": usuario.rol, "uid": usuario.id}
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "usuario": usuario,
    }


@router.get(
    "/me",
    response_model=schemas.UsuarioRespuesta,
    summary="Obtener perfil del usuario autenticado actual",
)
def perfil_usuario_actual(
    usuario_actual: models.Usuario = Depends(auth.get_current_user),
):
    return usuario_actual


@router.get(
    "/usuarios",
    response_model=list[schemas.UsuarioRespuesta],
    summary="Listar usuarios del sistema (Supervisor o Administrador)",
)
def listar_usuarios(
    rol: schemas.RolUsuario | None = None,
    db: Session = Depends(get_db),
    _usuario_autorizado: models.Usuario = Depends(
        auth.require_roles(
            models.RolUsuario.SUPERVISOR, models.RolUsuario.ADMINISTRADOR
        )
    ),
):
    query = db.query(models.Usuario)
    if rol:
        query = query.filter(models.Usuario.rol == rol.value)
    return query.order_by(models.Usuario.id.asc()).all()


@router.patch(
    "/usuarios/{usuario_id}/rol",
    response_model=schemas.UsuarioRespuesta,
    summary="Cambiar rol de un usuario (Solo Administrador)",
)
def cambiar_rol_usuario(
    usuario_id: int,
    cambio: CambioRol,
    db: Session = Depends(get_db),
    _admin: models.Usuario = Depends(
        auth.require_roles(models.RolUsuario.ADMINISTRADOR)
    ),
):
    usuario = db.get(models.Usuario, usuario_id)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    usuario.rol = (
        cambio.rol.value if hasattr(cambio.rol, "value") else str(cambio.rol)
    )
    db.commit()
    db.refresh(usuario)
    return usuario

