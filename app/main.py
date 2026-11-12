import asyncio
import os
import secrets
import uuid
from contextlib import asynccontextmanager, suppress
from datetime import datetime
from pathlib import Path

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from . import (
    auditoria,
    auth,
    correo,
    models,
    reglas,
    scheduler,
    schemas,
    sla,
    sla_vigilancia,
)
from .database import engine, get_db
from .routers import auth as auth_router
from .routers import notificaciones as notificaciones_router

models.Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    tarea = None
    if scheduler.scheduler_habilitado():
        tarea = asyncio.create_task(scheduler.bucle_revision_sla())
    yield
    if tarea:
        tarea.cancel()
        with suppress(asyncio.CancelledError):
            await tarea


app = FastAPI(
    title="HelpDesk Lite - ITSM",
    description="Sistema de Gestión de Helpdesk y Soporte Técnico (ITSM)",
    version="1.8.0",
    lifespan=lifespan,
)

app.include_router(auth_router.router)
app.include_router(notificaciones_router.router)

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


EXTENSIONES_BLOQUEADAS = {
    ".exe",
    ".bat",
    ".cmd",
    ".sh",
    ".vbs",
    ".msi",
    ".scr",
    ".ps1",
    ".jar",
}


def _directorio_uploads() -> Path:
    return Path(os.getenv("UPLOAD_DIR", "uploads"))


def _tamano_max_adjunto() -> int:
    try:
        mb = float(os.getenv("MAX_UPLOAD_MB", "25"))
    except ValueError:
        mb = 25.0
    return max(1, int(mb * 1024 * 1024))


async def _guardar_archivo(archivo: UploadFile) -> tuple[str, str, int]:
    """Valida y guarda el archivo en disco. Devuelve nombre, almacenado y tamaño."""
    nombre_original = (archivo.filename or "").replace("\\", "/").split("/")[-1]
    nombre_original = nombre_original.strip()
    if not nombre_original:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo no tiene un nombre válido",
        )

    extension = Path(nombre_original).suffix.lower()
    if extension in EXTENSIONES_BLOQUEADAS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La extensión {extension} no está permitida",
        )

    nombre_almacenado = f"{uuid.uuid4().hex}{extension}"
    directorio = _directorio_uploads()
    directorio.mkdir(parents=True, exist_ok=True)
    destino = directorio / nombre_almacenado
    maximo = _tamano_max_adjunto()
    total = 0

    try:
        with destino.open("wb") as salida:
            while trozo := await archivo.read(1024 * 1024):
                total += len(trozo)
                if total > maximo:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=(
                            "El archivo supera el tamaño máximo permitido "
                            f"({maximo // (1024 * 1024)} MB)"
                        ),
                    )
                salida.write(trozo)
    except HTTPException:
        destino.unlink(missing_ok=True)
        raise
    except Exception:
        destino.unlink(missing_ok=True)
        raise

    if total == 0:
        destino.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo está vacío",
        )

    return nombre_original, nombre_almacenado, total


def _email_de(db: Session, usuario_id: int | None) -> str | None:
    if usuario_id is None:
        return None
    usuario = db.get(models.Usuario, usuario_id)
    if usuario is None or not usuario.activo:
        return None
    return usuario.email


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
    background_tasks: BackgroundTasks,
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

    background_tasks.add_task(
        correo.enviar_correo_seguro,
        usuario.email,
        f"[{incidencia.id_legible}] Incidencia registrada",
        (
            f"Hola {usuario.nombre_completo},\n\n"
            f"Hemos registrado tu incidencia {incidencia.id_legible}: "
            f"{incidencia.titulo}.\n\n"
            "Puedes seguir su estado desde el portal."
        ),
    )
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
        # Incluye tanto los vencimientos ya sellados (tickets resueltos tarde)
        # como los tickets abiertos cuyo límite de resolución ya pasó.
        consulta = consulta.filter(
            or_(
                models.Incidencia.sla_resolucion_vencido.is_(True),
                and_(
                    models.Incidencia.sla_limite_resolucion.isnot(None),
                    models.Incidencia.sla_limite_resolucion < datetime.now(),
                    models.Incidencia.estado.notin_(
                        (
                            "Resuelto",
                            "Cerrado",
                            "Cancelado",
                            "Pendiente de usuario",
                            "Pendiente de tercero",
                        )
                    ),
                ),
            )
        )

    resultados = consulta.order_by(models.Incidencia.id.desc()).all()

    # sla_en_riesgo: filtro en memoria (cálculo temporal dinámico)
    if sla_en_riesgo is True:
        resultados = [t for t in resultados if t.estado_sla == "en_riesgo"]

    return resultados


@app.post(
    "/sla/revisar",
    summary="Revisar SLA y generar alertas/notificaciones (Supervisor o Administrador)",
)
def revisar_sla_manual(
    db: Session = Depends(get_db),
    _gestor: models.Usuario = Depends(
        auth.require_roles(
            models.RolUsuario.SUPERVISOR, models.RolUsuario.ADMINISTRADOR
        )
    ),
):
    return sla_vigilancia.revisar_slas(db)


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
    background_tasks: BackgroundTasks,
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
    destinatario = _email_de(db, incidencia.solicitante_id)
    db.commit()
    db.refresh(incidencia)

    if destinatario:
        background_tasks.add_task(
            correo.enviar_correo_seguro,
            destinatario,
            f"[{incidencia.id_legible}] Incidencia resuelta",
            (
                f"Tu incidencia {incidencia.id_legible} "
                f"({incidencia.titulo}) ha sido resuelta.\n\n"
                f"Nota de resolución:\n{datos.nota_resolucion}"
            ),
        )
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
    background_tasks: BackgroundTasks,
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

    destinatario = None
    asunto = ""
    if not es_interno:
        if _es_solicitante(usuario):
            destinatario = _email_de(db, incidencia.agente_asignado_id)
            asunto = (
                f"[{incidencia.id_legible}] Nueva respuesta del solicitante"
            )
        else:
            destinatario = _email_de(db, incidencia.solicitante_id)
            asunto = (
                f"[{incidencia.id_legible}] Nueva respuesta del equipo de soporte"
            )
        if destinatario == usuario.email:
            destinatario = None

    db.commit()
    db.refresh(comentario)

    if destinatario:
        background_tasks.add_task(
            correo.enviar_correo_seguro,
            destinatario,
            asunto,
            (
                f"Nueva respuesta en la incidencia {incidencia.id_legible} "
                f"({incidencia.titulo}):\n\n{datos.contenido.strip()}"
            ),
        )
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
    "/incidencias/{identificador}/adjuntos",
    response_model=list[schemas.AdjuntoRespuesta],
    summary="Listar los adjuntos de una incidencia",
)
def listar_adjuntos(
    identificador: str,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.get_current_user),
):
    incidencia = _buscar_visible(db, identificador, usuario)

    consulta = db.query(models.Adjunto).filter(
        models.Adjunto.incidencia_id == incidencia.id
    )
    if _es_solicitante(usuario):
        consulta = consulta.filter(models.Adjunto.es_interno.is_(False))

    return consulta.order_by(models.Adjunto.creado_en.asc()).all()


@app.post(
    "/incidencias/{identificador}/adjuntos",
    response_model=schemas.AdjuntoRespuesta,
    status_code=status.HTTP_201_CREATED,
    summary="Subir un adjunto a una incidencia",
)
async def subir_adjunto(
    identificador: str,
    archivo: UploadFile = File(...),
    es_interno: bool = Form(False),
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.get_current_user),
):
    incidencia = _buscar_visible(db, identificador, usuario)

    if incidencia.estado in ("Cerrado", "Cancelado"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "No se pueden añadir adjuntos a una incidencia en estado "
                f"{incidencia.estado}"
            ),
        )

    if _es_solicitante(usuario):
        es_interno = False

    nombre_original, nombre_almacenado, tamano = await _guardar_archivo(archivo)

    adjunto = models.Adjunto(
        incidencia_id=incidencia.id,
        subido_por_id=usuario.id,
        nombre_original=nombre_original,
        nombre_almacenado=nombre_almacenado,
        content_type=archivo.content_type,
        tamano_bytes=tamano,
        es_interno=es_interno,
    )
    db.add(adjunto)
    try:
        db.flush()
        auditoria.registrar_evento(
            db,
            incidencia_id=incidencia.id,
            usuario_id=usuario.id,
            accion="adjunto",
            campo="adjuntos",
            valor_nuevo=nombre_original,
            es_interno=es_interno,
        )
        db.commit()
    except Exception:
        db.rollback()
        (_directorio_uploads() / nombre_almacenado).unlink(missing_ok=True)
        raise

    db.refresh(adjunto)
    return adjunto


@app.get(
    "/adjuntos/{adjunto_id}",
    summary="Descargar un adjunto",
)
def descargar_adjunto(
    adjunto_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(auth.get_current_user),
):
    adjunto = db.get(models.Adjunto, adjunto_id)
    if adjunto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Adjunto no encontrado",
        )

    incidencia = db.get(models.Incidencia, adjunto.incidencia_id)
    if incidencia is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Adjunto no encontrado",
        )

    if _es_solicitante(usuario):
        if incidencia.solicitante_id != usuario.id or adjunto.es_interno:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Adjunto no encontrado",
            )

    if Path(adjunto.nombre_almacenado).name != adjunto.nombre_almacenado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Adjunto no encontrado",
        )

    ruta = _directorio_uploads() / adjunto.nombre_almacenado
    if not ruta.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El archivo ya no está disponible",
        )

    return FileResponse(
        ruta,
        media_type=adjunto.content_type or "application/octet-stream",
        filename=adjunto.nombre_original,
    )