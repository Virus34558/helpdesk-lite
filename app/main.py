from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from . import models, schemas
from .database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="HelpDesk Lite", description="Gestor de incidencias IT")


@app.get("/", include_in_schema=False)
def inicio():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.post("/incidencias", response_model=schemas.IncidenciaRespuesta, status_code=201)
def crear_incidencia(datos: schemas.IncidenciaCrear, db: Session = Depends(get_db)):
    incidencia = models.Incidencia(**datos.model_dump())
    db.add(incidencia)
    db.commit()
    db.refresh(incidencia)
    return incidencia


@app.get("/incidencias", response_model=list[schemas.IncidenciaRespuesta])
def listar_incidencias(
    estado: schemas.Estado | None = None,
    prioridad: schemas.Prioridad | None = None,
    db: Session = Depends(get_db),
):
    consulta = db.query(models.Incidencia)
    if estado:
        consulta = consulta.filter(models.Incidencia.estado == estado.value)
    if prioridad:
        consulta = consulta.filter(models.Incidencia.prioridad == prioridad.value)
    return consulta.order_by(models.Incidencia.id.desc()).all()


@app.get("/incidencias/{incidencia_id}", response_model=schemas.IncidenciaRespuesta)
def obtener_incidencia(incidencia_id: int, db: Session = Depends(get_db)):
    incidencia = db.get(models.Incidencia, incidencia_id)
    if incidencia is None:
        raise HTTPException(status_code=404, detail="Incidencia no encontrada")