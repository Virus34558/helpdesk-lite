"""Ingesta de tickets desde un webhook de correo (RF-1.2 del ERS).

El conector externo (IMAP, Microsoft Graph, SES) normaliza el mensaje y lo
entrega aquí. Se autentica con un token compartido en `X-Ingesta-Token`.
"""

import os
import re
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.orm import Session

from .. import auditoria, auth, models, reglas, schemas, sla
from ..database import get_db

router = APIRouter(prefix="/ingesta", tags=["Ingesta de correo"])

PATRON_CODIGO = re.compile(r"\b(?:INC|REQ|PRB|CHG)-\d{4}-\d{6}\b", re.IGNORECASE)
REMITENTES_IGNORADOS = (
    "no-reply@",
    "noreply@",
    "mailer-daemon@",
    "postmaster@",
)
ESTADOS_CERRADOS = ("Cerrado", "Cancelado")


def _autorizar(token: str | None) -> None:
    esperado = os.getenv("INGESTA_CORREO_TOKEN")
    if not esperado:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La ingesta de correo no está configurada (INGESTA_CORREO_TOKEN)",
        )
    if not token or not secrets.compare_digest(token, esperado):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de ingesta no válido",
        )


def _motivo_para_ignorar(correo: schemas.CorreoEntrante) -> str | None:
    if correo.auto_submitted:
        return "respuesta automática"
    remitente = correo.remitente.lower()
    if any(remitente.startswith(prefijo) for prefijo in REMITENTES_IGNORADOS):
        return "remitente automático"
    return None


def _codigo_en(correo: schemas.CorreoEntrante) -> str | None:
    for texto in (correo.asunto, correo.en_respuesta_a or ""):
        encontrado = PATRON_CODIGO.search(texto or "")
        if encontrado:
            return encontrado.group(0).upper()
    return None


def _usuario_para(db: Session, email: str) -> models.Usuario:
    email = email.lower().strip()
    usuario = db.query(models.Usuario).filter(models.Usuario.email == email).first()
    if usuario is not None:
        return usuario

    # Usuario provisional: puede entrar cuando restablezca la contraseña,
    # pero no se le inventa un acceso predecible.
    usuario = models.Usuario(
        email=email,
        nombre_completo=email.split("@")[0],
        password_hash=auth.hash_password(secrets.token_urlsafe(32)),
        rol=models.RolUsuario.SOLICITANTE.value,
        activo=True,
    )
    db.add(usuario)
    db.flush()
    return usuario


def _crear_ticket(
    db: Session, correo: schemas.CorreoEntrante, usuario: models.Usuario
) -> models.Incidencia:
    prioridad = reglas.calcular_prioridad("Bajo", "Media")
    titulo = (correo.asunto or "(sin asunto)").strip()[:100]

    incidencia = models.Incidencia(
        id_legible="TMP-" + secrets.token_hex(4),
        titulo=titulo,
        descripcion=correo.cuerpo.strip(),
        tipo=models.TipoTicket.INCIDENCIA.value,
        canal_origen=models.CanalOrigen.EMAIL.value,
        impacto="Bajo",
        urgencia="Media",
        prioridad=prioridad,
        solicitante_id=usuario.id,
    )
    db.add(incidencia)
    db.flush()
    incidencia.id_legible = reglas.generar_id_legible(
        incidencia.tipo, incidencia.id
    )

    limite_frt, limite_rt = sla.inicializar_sla(prioridad, incidencia.creada_en)
    incidencia.sla_limite_primera_respuesta = limite_frt
    incidencia.sla_limite_resolucion = limite_rt

    auditoria.registrar_evento(
        db,
        incidencia.id,
        usuario.id,
        accion="creacion",
        campo="canal_origen",
        valor_nuevo=models.CanalOrigen.EMAIL.value,
    )
    return incidencia


def _responder_ticket(
    db: Session, incidencia: models.Incidencia, correo: schemas.CorreoEntrante,
    usuario: models.Usuario,
) -> models.Comentario:
    comentario = models.Comentario(
        incidencia_id=incidencia.id,
        autor_id=usuario.id,
        contenido=correo.cuerpo.strip() or "(mensaje vacío)",
        es_interno=False,
    )
    db.add(comentario)
    db.flush()

    # RF-1.2: si el solicitante responde a un ticket pendiente, se reactiva
    if incidencia.estado == "Pendiente de usuario":
        auditoria.registrar_evento(
            db,
            incidencia.id,
            usuario.id,
            accion="reactivacion_automatica",
            campo="estado",
            valor_anterior=incidencia.estado,
            valor_nuevo="En progreso",
        )
        incidencia.estado = "En progreso"

    auditoria.registrar_evento(
        db,
        incidencia.id,
        usuario.id,
        accion="comentario_publico",
        campo="origen",
        valor_nuevo="correo",
    )
    return comentario


@router.post(
    "/correo",
    response_model=schemas.RespuestaIngesta,
    status_code=status.HTTP_201_CREATED,
    summary="Recibir un correo y crear un ticket o responder al hilo existente",
)
def ingesta_correo(
    correo: schemas.CorreoEntrante,
    respuesta: Response,
    db: Session = Depends(get_db),
    x_ingesta_token: str | None = Header(default=None),
):
    _autorizar(x_ingesta_token)

    motivo = _motivo_para_ignorar(correo)
    if motivo is None and correo.mensaje_id:
        duplicado = (
            db.query(models.CorreoIngestado)
            .filter(models.CorreoIngestado.mensaje_id == correo.mensaje_id)
            .first()
        )
        if duplicado is not None:
            motivo = "mensaje ya procesado"

    if motivo is not None:
        respuesta.status_code = status.HTTP_202_ACCEPTED
        return {"resultado": "ignorado", "motivo": motivo}

    codigo = _codigo_en(correo)
    incidencia = None
    if codigo:
        incidencia = (
            db.query(models.Incidencia)
            .filter(models.Incidencia.id_legible == codigo)
            .first()
        )

    usuario = _usuario_para(db, correo.remitente)

    if incidencia is not None and incidencia.estado not in ESTADOS_CERRADOS:
        _responder_ticket(db, incidencia, correo, usuario)
        resultado = "comentario"
        respuesta.status_code = status.HTTP_200_OK
    else:
        # Correo nuevo, o respuesta a un ticket ya cerrado: ticket de seguimiento
        incidencia = _crear_ticket(db, correo, usuario)
        resultado = "ticket_creado"

    if correo.mensaje_id:
        db.add(
            models.CorreoIngestado(
                mensaje_id=correo.mensaje_id,
                incidencia_id=incidencia.id,
            )
        )

    db.commit()
    db.refresh(incidencia)
    return {
        "resultado": resultado,
        "incidencia_id": incidencia.id,
    }
