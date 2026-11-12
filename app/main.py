import secrets
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from . import auditoria, auth, models, reglas, schemas, sla
from .database import engine, get_db
from .routers import auth as auth_router

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="HelpDesk Lite - ITSM",
    description="Sistema de Gestión de Helpdesk y Soporte Técnico (ITSM)",
    version="1.4.0",
)

app.include_router(auth_router.router)

# Quien puede gestionar incidencias (cambiar estado, impacto, asignar, resolver...)
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


def _buscar_por_id_o_codigo(db: Session, identificador: str) -> models.Incidencia:
    """Busca una incidencia por su ID numérico o por su id_legible (ej: INC-2026-000001)."""
    if identificador.isascii() and identificador.isdigit() and len(identificador) <= 9:
        incidencia = db.get(models.Incidencia, int(identificador))
    else:
        incidencia = (
            db.query(models.Incidencia)
            .filter(models.Incidencia.id_legible == identificador.upper().strip())
            .first()
        )
    if incidencia is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incidencia no encontrada",
        )
    return incidencia


def _buscar_visible(db: Session, identificador: str, usuario: models.Usuario):
    """Devuelve la incidencia o 404. Un solicitante solo ve las suyas."""
    incidencia = _buscar_por_id_o_codigo(db, identificador)
    if _es_solicitante(usuario) and incidencia.solicitante_id != usuario.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incidencia no encontrada",
        )
    return incidencia


def _cambiar_estado(incidencia: models.Incidencia, nuevo: str, nota: str | None):
    """Valida la transición y aplica las reglas de negocio del cambio de estado."""
    if not reglas.transicion_permitida(incidencia.estado, nuevo):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Transición no permitida: {incidencia.estado} -> {nuevo}",
        )
    estado_anterior = incidencia.estado
    if nuevo == "Resuelto":
        if not nota:
            raise HTTPException(
                status_code=422,
                detail="Para resolver hay que indicar la nota de resolución",
            )
        incidencia.nota_resolucion = nota
        incidencia.resuelta_en = datetime.now()
        sla.gestionar_transicion_estado_sla(incidencia, estado_anterior, nuevo)
        sla.finalizar_sla_resolucion(incidencia)
    elif incidencia.estado == "Resuelto" and nuevo == "En progreso":
        incidencia.resuelta_en = None  # se reabre
        sla.gestionar_transicion_estado_sla(incidencia, estado_anterior, nuevo)
    else:
        sla.gestionar_transicion_estado_sla(incidencia, estado_anterior, nuevo)
    incidencia.estado = nuevo


def _validar_y_asignar_agente(
    db: Session, incidencia: models.Incidencia, agente_id: int | None
):
    """Valida que el usuario a asignar sea un técnico (agente, supervisor o admin)."""
    if agente_id is None:
        incidencia.agente_asignado_id = None
        return

    agente = db.get(models.Usuario, agente_id)
    if not agente or not agente.activo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario técnico no encontrado o inactivo",
        )
    if agente.rol == models.RolUsuario.SOLICITANTE.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se pueden asignar incidencias a personal de soporte (agente, supervisor o administrador)",
        )

    incidencia.agente_asignado_id = agente.id

    # Si la incidencia estaba en 'Nuevo', al asignarse pasa a 'En progreso'
    if incidencia.estado == "Nuevo":
        incidencia.estado = "En progreso"


@app.post("/incidencias", response_model=schemas.IncidenciaRespuesta, status_code=201)
def crear_incidencia(
    datos: schemas.IncidenciaCrear,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.get_current_user),
):
    valores = datos.model_dump()

    if _es_solicitante(usuario):
        tipo = getattr(valores["tipo"], "value", valores["tipo"])
        if tipo not in ("Incidencia", "Solicitud de Servicio"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Un solicitante solo puede crear Incidencias o Solicitudes de servicio",
            )
        # Impacto y urgencia los fija el personal de soporte, no el solicitante
        valores["impacto"] = "Bajo"
        valores["urgencia"] = "Media"
        # El canal de origen lo decide el sistema, no el usuario
        valores["canal_origen"] = "Portal Web"

    incidencia = models.Incidencia(
        **valores,
        id_legible="TMP-" + secrets.token_hex(4),  # provisional, se sustituye abajo
        prioridad=reglas.calcular_prioridad(valores["impacto"], valores["urgencia"]),
        solicitante_id=usuario.id,
    )
    db.add(incidencia)
    db.flush()  # la base de datos asigna el id, que es único
    incidencia.id_legible = reglas.generar_id_legible(valores["tipo"], incidencia.id)

    # Inicializar SLA según la prioridad calculada
    limite_frt, limite_rt = sla.inicializar_sla(incidencia.prioridad, incidencia.creada_en)
    incidencia.sla_limite_primera_respuesta = limite_frt
    incidencia.sla_limite_resolucion = limite_rt

    auditoria.registrar_evento(
        db,
        incidencia_id=incidencia.id,
        usuario_id=usuario.id,
        accion="creacion",
        campo="id_legible",
        valor_nuevo=incidencia.id_legible,
    )
    db.commit()
    db.refresh(incidencia)
    return incidencia


@app.get("/incidencias", response_model=list[schemas.IncidenciaRespuesta])
def listar_incidencias(
    estado: schemas.Estado | None = None,
    prioridad: schemas.Prioridad | None = None,
    tipo: schemas.TipoTicket | None = None,
    canal_origen: schemas.CanalOrigen | None = None,
    agente_asignado_id: int | None = None,
    sin_asignar: bool | None = None,
    sla_vencido: bool | None = None,
    sla_en_riesgo: bool | None = None,
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
    if tipo:
        consulta = consulta.filter(models.Incidencia.tipo == tipo.value)
    if canal_origen:
        consulta = consulta.filter(models.Incidencia.canal_origen == canal_origen.value)
    if agente_asignado_id is not None:
        consulta = consulta.filter(
            models.Incidencia.agente_asignado_id == agente_asignado_id
        )
    if sin_asignar is True:
        consulta = consulta.filter(models.Incidencia.agente_asignado_id.is_(None))
    if sla_vencido is True:
        consulta = consulta.filter(models.Incidencia.sla_resolucion_vencido.is_(True))

    resultados = consulta.order_by(models.Incidencia.id.desc()).all()

    # sla_en_riesgo: filtro en memoria (cálculo temporal dinámico)
    if sla_en_riesgo is True:
        resultados = [t for t in resultados if t.estado_sla == "en_riesgo"]

    return resultados


@app.get("/incidencias/{identificador}", response_model=schemas.IncidenciaRespuesta)
def obtener_incidencia(
    identificador: str,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.get_current_user),
):
    return _buscar_visible(db, identificador, usuario)


@app.patch("/incidencias/{identificador}", response_model=schemas.IncidenciaRespuesta)
def actualizar_incidencia(
    identificador: str,
    datos: schemas.IncidenciaActualizar,
    db: Session = Depends(get_db),
    _gestor: models.Usuario = Depends(solo_gestores),
):
    incidencia = _buscar_por_id_o_codigo(db, identificador)

    if incidencia.estado in ("Cerrado", "Cancelado"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No se pueden modificar incidencias en estado {incidencia.estado}",
        )

    cambios = datos.model_dump(exclude_unset=True)
    nuevo_estado = cambios.pop("estado", None)
    nota = cambios.pop("nota_resolucion", None)

    estado_anterior = incidencia.estado
    prioridad_anterior = incidencia.prioridad
    agente_anterior = incidencia.agente_asignado_id

    # Primero se valida el estado: si falla, no se ha modificado nada
    if nuevo_estado is not None and nuevo_estado != incidencia.estado:
        _cambiar_estado(incidencia, nuevo_estado, nota)
        auditoria.registrar_evento(
            db,
            incidencia.id,
            _gestor.id,
            accion="cambio_estado",
            campo="estado",
            valor_anterior=estado_anterior,
            valor_nuevo=nuevo_estado,
        )

    if "agente_asignado_id" in cambios:
        agente_id = cambios.pop("agente_asignado_id")
        _validar_y_asignar_agente(db, incidencia, agente_id)
        auditoria.registrar_evento(
            db,
            incidencia.id,
            _gestor.id,
            accion="asignacion_tecnico",
            campo="agente_asignado_id",
            valor_anterior=str(agente_anterior) if agente_anterior else None,
            valor_nuevo=str(agente_id) if agente_id else None,
        )

    for campo, valor in cambios.items():
        if valor is not None:
            valor_ant = getattr(incidencia, campo, None)
            if valor_ant != valor:
                setattr(incidencia, campo, valor)
                auditoria.registrar_evento(
                    db,
                    incidencia.id,
                    _gestor.id,
                    accion="modificacion",
                    campo=campo,
                    valor_anterior=str(valor_ant) if valor_ant is not None else None,
                    valor_nuevo=str(valor),
                )

    incidencia.prioridad = reglas.calcular_prioridad(
        incidencia.impacto, incidencia.urgencia
    )
    if incidencia.prioridad != prioridad_anterior:
        auditoria.registrar_evento(
            db,
            incidencia.id,
            _gestor.id,
            accion="cambio_prioridad",
            campo="prioridad",
            valor_anterior=prioridad_anterior,
            valor_nuevo=incidencia.prioridad,
        )
        sla.recalcular_sla_por_cambio_prioridad(incidencia, incidencia.prioridad)

    db.commit()
    db.refresh(incidencia)
    return incidencia


@app.post(
    "/incidencias/{identificador}/asignar",
    response_model=schemas.IncidenciaRespuesta,
    summary="Asignar o desasignar técnico (Solo personal de soporte)",
)
def asignar_incidencia(
    identificador: str,
    datos: schemas.AsignarAgente,
    db: Session = Depends(get_db),
    _gestor: models.Usuario = Depends(solo_gestores),
):
    incidencia = _buscar_por_id_o_codigo(db, identificador)
    if incidencia.estado in ("Cerrado", "Cancelado"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No se puede asignar personal a una incidencia en estado {incidencia.estado}",
        )
    agente_anterior = incidencia.agente_asignado_id
    _validar_y_asignar_agente(db, incidencia, datos.agente_id)
    auditoria.registrar_evento(
        db,
        incidencia.id,
        _gestor.id,
        accion="asignacion_tecnico",
        campo="agente_asignado_id",
        valor_anterior=str(agente_anterior) if agente_anterior else None,
        valor_nuevo=str(datos.agente_id) if datos.agente_id else None,
    )
    db.commit()
    db.refresh(incidencia)
    return incidencia


@app.post(
    "/incidencias/{identificador}/resolver",
    response_model=schemas.IncidenciaRespuesta,
    summary="Resolver una incidencia con nota obligatoria",
)
def resolver_incidencia(
    identificador: str,
    datos: schemas.ResolverIncidencia,
    db: Session = Depends(get_db),
    _gestor: models.Usuario = Depends(solo_gestores),
):
    incidencia = _buscar_por_id_o_codigo(db, identificador)
    estado_anterior = incidencia.estado
    _cambiar_estado(incidencia, "Resuelto", datos.nota_resolucion)
    auditoria.registrar_evento(
        db,
        incidencia.id,
        _gestor.id,
        accion="resolucion",
        campo="nota_resolucion",
        valor_anterior=estado_anterior,
        valor_nuevo=datos.nota_resolucion,
    )
    db.commit()
    db.refresh(incidencia)
    return incidencia


@app.post(
    "/incidencias/{identificador}/comentarios",
    response_model=schemas.ComentarioRespuesta,
    status_code=status.HTTP_201_CREATED,
    summary="Añadir comentario al hilo (Respuesta pública o Nota interna)",
)
def agregar_comentario(
    identificador: str,
    datos: schemas.ComentarioCrear,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.get_current_user),
):
    incidencia = _buscar_visible(db, identificador, usuario)

    if incidencia.estado in ("Cerrado", "Cancelado"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No se pueden añadir comentarios a una incidencia en estado {incidencia.estado}",
        )

    # Regla RBAC: un solicitante no puede publicar notas internas
    if _es_solicitante(usuario) and datos.es_interno:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Los solicitantes no tienen permiso para crear notas internas",
        )

    es_interno = False if _es_solicitante(usuario) else datos.es_interno

    # Regla ITIL: si el solicitante responde estando 'Pendiente de usuario',
    # el ticket se reactiva automáticamente a 'En progreso'
    if _es_solicitante(usuario) and incidencia.estado == "Pendiente de usuario":
        estado_ant = incidencia.estado
        incidencia.estado = "En progreso"
        auditoria.registrar_evento(
            db,
            incidencia.id,
            usuario.id,
            accion="reactivacion_automatica",
            campo="estado",
            valor_anterior=estado_ant,
            valor_nuevo="En progreso",
        )

    comentario = models.Comentario(
        incidencia_id=incidencia.id,
        autor_id=usuario.id,
        contenido=datos.contenido.strip(),
        es_interno=es_interno,
    )
    db.add(comentario)
    db.flush()

    # SLA: registrar primera respuesta pública de un técnico
    if not _es_solicitante(usuario) and not es_interno:
        sla.registrar_primera_respuesta(incidencia)

    auditoria.registrar_evento(
        db,
        incidencia_id=incidencia.id,
        usuario_id=usuario.id,
        accion="nota_interna" if es_interno else "comentario_publico",
        campo="comentarios",
        valor_nuevo=str(comentario.id),
        es_interno=es_interno,
    )
    db.commit()
    db.refresh(comentario)
    return comentario


@app.get(
    "/incidencias/{identificador}/comentarios",
    response_model=list[schemas.ComentarioRespuesta],
    summary="Listar hilo de conversación de la incidencia",
)
def listar_comentarios(
    identificador: str,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.get_current_user),
):
    incidencia = _buscar_visible(db, identificador, usuario)

    consulta = db.query(models.Comentario).filter(
        models.Comentario.incidencia_id == incidencia.id
    )
    # Regla RBAC: el solicitante jamás ve las notas internas de los técnicos
    if _es_solicitante(usuario):
        consulta = consulta.filter(models.Comentario.es_interno.is_(False))

    return consulta.order_by(models.Comentario.creado_en.asc()).all()


@app.get(
    "/incidencias/{identificador}/historial",
    response_model=list[schemas.RegistroAuditoriaRespuesta],
    summary="Consultar el historial inmutable de auditoría de una incidencia",
)
def obtener_historial_auditoria(
    identificador: str,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.get_current_user),
):
    incidencia = _buscar_visible(db, identificador, usuario)

    consulta = db.query(models.RegistroAuditoria).filter(
        models.RegistroAuditoria.incidencia_id == incidencia.id
    )
    # Regla RBAC: El solicitante jamás ve eventos de auditoría internos
    if _es_solicitante(usuario):
        consulta = consulta.filter(models.RegistroAuditoria.es_interno.is_(False))

    return consulta.order_by(models.RegistroAuditoria.creado_en.asc()).all()



@app.get(
    "/incidencias/{identificador}/historial",
    response_model=list[schemas.RegistroAuditoriaRespuesta],
    summary="Consultar el historial inmutable de auditoría de una incidencia",
)
def obtener_historial_auditoria(
    identificador: str,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.get_current_user),
):
    incidencia = _buscar_visible(db, identificador, usuario)

    consulta = db.query(models.RegistroAuditoria).filter(
        models.RegistroAuditoria.incidencia_id == incidencia.id
    )
    # Regla RBAC: El solicitante jamás ve eventos de auditoría internos
    if _es_solicitante(usuario):
        consulta = consulta.filter(models.RegistroAuditoria.es_interno.is_(False))

    return consulta.order_by(models.RegistroAuditoria.creado_en.asc()).all()