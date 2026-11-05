from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from . import auth, models, reglas, schemas
from .database import engine, get_db
from .routers import auth as auth_router

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="HelpDesk Lite - ITSM",
    description="Sistema de Gestión de Helpdesk y Soporte Técnico (ITSM)",
    version="1.2.0",
)

app.include_router(auth_router.router)

# Quien puede gestionar incidencias (cambiar estado, impacto, resolver...)
solo_gestores = auth.require_roles(
    models.RolUsuario.AGENTE,
    models.RolUsuario.SUPERVISOR,
    models.RolUsuario.ADMINISTRADOR,
)


@app.get("/", include_in_schema=False)
def inicio():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


def _es_solicitante(usuario: models.Usuario) -> bool:
    return usuario.rol == models.RolUsuario.SOLICITANTE.value


def _buscar_visible(db: Session, incidencia_id: int, usuario: models.Usuario):
    """Devuelve la incidencia o 404. Un solicitante solo ve las suyas."""
    incidencia = db.get(models.Incidencia, incidencia_id)
    if incidencia is None or (
        _es_solicitante(usuario) and incidencia.solicitante_id != usuario.id
    ):
        raise HTTPException(status_code=404, detail="Incidencia no encontrada")
    return incidencia


def _cambiar_estado(incidencia: models.Incidencia, nuevo: str, nota: str | None):
    """Valida la transicion y aplica las reglas de negocio del cambio de estado."""
    if not reglas.transicion_permitida(incidencia.estado, nuevo):
        raise HTTPException(
            status_code=409,
            detail=f"Transición no permitida: {incidencia.estado} -> {nuevo}",
        )
    if nuevo == "Resuelto":
        if not nota:
            raise HTTPException(
                status_code=422,
                detail="Para resolver hay que indicar la nota de resolución",
            )
        incidencia.nota_resolucion = nota
        incidencia.resuelta_en = datetime.now()
    elif incidencia.estado == "Resuelto" and nuevo == "En progreso":
        incidencia.resuelta_en = None  # se reabre
    incidencia.estado = nuevo


@app.post("/incidencias", response_model=schemas.IncidenciaRespuesta, status_code=201)
def crear_incidencia(
    datos: schemas.IncidenciaCrear,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.get_current_user),
):
    valores = datos.model_dump()
    if _es_solicitante(usuario):
        # Impacto y urgencia los fija el personal de soporte, no el solicitante
        valores["impacto"] = "Bajo"
        valores["urgencia"] = "Media"

    incidencia = models.Incidencia(
        **valores,
        prioridad=reglas.calcular_prioridad(valores["impacto"], valores["urgencia"]),
        solicitante_id=usuario.id,
    )
    db.add(incidencia)
    db.commit()
    db.refresh(incidencia)
    return incidencia


@app.get("/incidencias", response_model=list[schemas.IncidenciaRespuesta])
def listar_incidencias(
    estado: schemas.Estado | None = None,
    prioridad: schemas.Prioridad | None = None,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.get_current_user),
):
    consulta = db.query(models.Incidencia)
    if _es_solicitante(usuario):
        consulta = consulta.filter(models.Incidencia.solicitante_id == usuario.id)
    if estado:
        consulta = consulta.filter(models.Incidencia.estado == estado.value)
    if prioridad:
        consulta = consulta.filter(models.Incidencia.prioridad == prioridad.value)
    return consulta.order_by(models.Incidencia.id.desc()).all()


@app.get("/incidencias/{incidencia_id}", response_model=schemas.IncidenciaRespuesta)
def obtener_incidencia(
    incidencia_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.get_current_user),
):
    return _buscar_visible(db, incidencia_id, usuario)


@app.patch("/incidencias/{incidencia_id}", response_model=schemas.IncidenciaRespuesta)
def actualizar_incidencia(
    incidencia_id: int,
    datos: schemas.IncidenciaActualizar,
    db: Session = Depends(get_db),
    _gestor: models.Usuario = Depends(solo_gestores),
):
    incidencia = db.get(models.Incidencia, incidencia_id)
    if incidencia is None:
        raise HTTPException(status_code=404, detail="Incidencia no encontrada")

    cambios = datos.model_dump(exclude_unset=True)
    nuevo_estado = cambios.pop("estado", None)
    nota = cambios.pop("nota_resolucion", None)

    # Primero se valida el estado: si falla, no se ha modificado nada
    if nuevo_estado is not None and nuevo_estado != incidencia.estado:
        _cambiar_estado(incidencia, nuevo_estado, nota)

    for campo, valor in cambios.items():
        if valor is not None:
            setattr(incidencia, campo, valor)

    incidencia.prioridad = reglas.calcular_prioridad(
        incidencia.impacto, incidencia.urgencia
    )

    db.commit()
    db.refresh(incidencia)
    return incidencia


@app.post("/incidencias/{incidencia_id}/resolver", response_model=schemas.IncidenciaRespuesta)
def resolver_incidencia(
    incidencia_id: int,
    datos: schemas.ResolverIncidencia,
    db: Session = Depends(get_db),
    _gestor: models.Usuario = Depends(solo_gestores),
):
    incidencia = db.get(models.Incidencia, incidencia_id)
    if incidencia is None:
        raise HTTPException(status_code=404, detail="Incidencia no encontrada")

    _cambiar_estado(incidencia, "Resuelto", datos.nota_resolucion)
    db.commit()
    db.refresh(incidencia)
    return incidencia