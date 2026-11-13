from sqlalchemy import func
from sqlalchemy.orm import Session

from . import auditoria, models

ESTADOS_FINALES = ("Resuelto", "Cerrado", "Cancelado")


def _texto(valor) -> str:
    if valor is None:
        return ""
    return str(valor).strip().lower()


def _valor_campo(
    db: Session, incidencia: models.Incidencia, campo: str
):
    if campo == "solicitante_departamento":
        solicitante = db.get(models.Usuario, incidencia.solicitante_id)
        return solicitante.departamento if solicitante else None
    return getattr(incidencia, campo, None)


def _coincide_condicion(
    db: Session, incidencia: models.Incidencia, condicion: dict
) -> bool:
    campo = condicion.get("campo")
    operador = condicion.get("operador", "=")
    esperado = condicion.get("valor")
    actual = _valor_campo(db, incidencia, campo)

    if operador == "=":
        if isinstance(esperado, (int, float)) and isinstance(actual, (int, float)):
            return actual == esperado
        return _texto(actual) == _texto(esperado)
    if operador == "!=":
        return _texto(actual) != _texto(esperado)
    if operador == "contiene":
        return _texto(esperado) in _texto(actual)
    if operador == "en":
        if not isinstance(esperado, (list, tuple, set)):
            return False
        return any(_texto(actual) == _texto(v) for v in esperado)
    return False


def regla_coincide(
    db: Session, incidencia: models.Incidencia, regla: models.ReglaAutomatizacion
) -> bool:
    condiciones = regla.condiciones or []
    if not condiciones:
        return True
    resultados = [
        _coincide_condicion(db, incidencia, condicion)
        for condicion in condiciones
    ]
    if (regla.logica or "AND").upper() == "OR":
        return any(resultados)
    return all(resultados)


def _miembros_grupo(db: Session, grupo_id: int) -> list[models.Usuario]:
    return (
        db.query(models.Usuario)
        .join(
            models.GrupoMiembro,
            models.GrupoMiembro.usuario_id == models.Usuario.id,
        )
        .filter(
            models.GrupoMiembro.grupo_id == grupo_id,
            models.Usuario.activo.is_(True),
            models.Usuario.rol != models.RolUsuario.SOLICITANTE.value,
        )
        .order_by(models.Usuario.id.asc())
        .all()
    )


def _es_miembro(db: Session, grupo_id: int, usuario_id: int) -> bool:
    return (
        db.query(models.GrupoMiembro)
        .filter(
            models.GrupoMiembro.grupo_id == grupo_id,
            models.GrupoMiembro.usuario_id == usuario_id,
        )
        .first()
        is not None
    )


def _elegir_agente(
    db: Session, grupo: models.GrupoSoporte, modo: str
) -> models.Usuario | None:
    miembros = _miembros_grupo(db, grupo.id)
    if not miembros:
        return None

    if modo == "load_balanced":
        ids = [m.id for m in miembros]
        abiertos = dict(
            db.query(
                models.Incidencia.agente_asignado_id,
                func.count(models.Incidencia.id),
            )
            .filter(
                models.Incidencia.agente_asignado_id.in_(ids),
                models.Incidencia.estado.notin_(ESTADOS_FINALES),
            )
            .group_by(models.Incidencia.agente_asignado_id)
            .all()
        )
        return min(miembros, key=lambda u: (abiertos.get(u.id, 0), u.id))

    indice = grupo.turno_round_robin % len(miembros)
    grupo.turno_round_robin += 1
    return miembros[indice]


def _asignar_agente(
    db: Session,
    incidencia: models.Incidencia,
    agente: models.Usuario,
    usuario_id: int | None,
) -> bool:
    if incidencia.agente_asignado_id == agente.id:
        return False

    anterior = incidencia.agente_asignado_id
    incidencia.agente_asignado_id = agente.id

    estado_anterior = incidencia.estado
    if incidencia.estado == "Nuevo":
        incidencia.estado = "En progreso"

    auditoria.registrar_evento(
        db,
        incidencia.id,
        usuario_id,
        accion="auto_asignacion",
        campo="agente_asignado_id",
        valor_anterior=str(anterior) if anterior else None,
        valor_nuevo=str(agente.id),
        es_interno=True,
    )
    if estado_anterior != incidencia.estado:
        auditoria.registrar_evento(
            db,
            incidencia.id,
            usuario_id,
            accion="cambio_estado",
            campo="estado",
            valor_anterior=estado_anterior,
            valor_nuevo=incidencia.estado,
            es_interno=True,
        )
    return True


def aplicar_reglas(
    db: Session,
    incidencia: models.Incidencia,
    usuario_id: int | None = None,
    permitir_reasignar: bool = True,
) -> dict:
    """Evalúa las reglas activas y aplica grupo y auto-asignación.

    Las reglas se ejecutan por orden. La última que indique grupo/agente gana.
    No lanza errores si un destino ya no existe: simplemente no lo aplica.
    """
    reglas = (
        db.query(models.ReglaAutomatizacion)
        .filter(models.ReglaAutomatizacion.activa.is_(True))
        .order_by(
            models.ReglaAutomatizacion.orden.asc(),
            models.ReglaAutomatizacion.id.asc(),
        )
        .all()
    )

    aplicadas = [
        regla
        for regla in reglas
        if regla_coincide(db, incidencia, regla)
    ]
    if not aplicadas:
        return {
            "reglas_aplicadas": [],
            "grupo_id": incidencia.grupo_asignado_id,
            "agente_id": incidencia.agente_asignado_id,
        }

    grupo_final = incidencia.grupo_asignado_id
    modo_auto = None
    agente_fijo = None
    for regla in aplicadas:
        acciones = regla.acciones or {}
        if acciones.get("grupo_id") is not None:
            grupo_final = acciones["grupo_id"]
        if acciones.get("auto_asignar"):
            modo_auto = acciones["auto_asignar"]
        if acciones.get("agente_id") is not None:
            agente_fijo = acciones["agente_id"]

    grupo = db.get(models.GrupoSoporte, grupo_final) if grupo_final else None
    if grupo is not None and not grupo.activo:
        grupo = None
        grupo_final = None

    cambio_grupo = grupo_final != incidencia.grupo_asignado_id
    if cambio_grupo:
        anterior = incidencia.grupo_asignado_id
        incidencia.grupo_asignado_id = grupo_final
        auditoria.registrar_evento(
            db,
            incidencia.id,
            usuario_id,
            accion="regla_automatizacion",
            campo="grupo_asignado_id",
            valor_anterior=str(anterior) if anterior else None,
            valor_nuevo=str(grupo_final) if grupo_final else None,
            es_interno=True,
        )

    # Si el agente actual no pertenece al nuevo grupo, se libera
    if (
        grupo is not None
        and incidencia.agente_asignado_id
        and not _es_miembro(db, grupo.id, incidencia.agente_asignado_id)
    ):
        anterior = incidencia.agente_asignado_id
        incidencia.agente_asignado_id = None
        auditoria.registrar_evento(
            db,
            incidencia.id,
            usuario_id,
            accion="auto_asignacion",
            campo="agente_asignado_id",
            valor_anterior=str(anterior),
            valor_nuevo=None,
            es_interno=True,
        )

    agente = None
    puede_asignar = (
        permitir_reasignar or incidencia.agente_asignado_id is None
    )
    if puede_asignar and agente_fijo is not None:
        candidato = db.get(models.Usuario, agente_fijo)
        if (
            candidato is not None
            and candidato.activo
            and candidato.rol != models.RolUsuario.SOLICITANTE.value
            and (
                grupo is None
                or _es_miembro(db, grupo.id, candidato.id)
            )
        ):
            agente = candidato
    elif puede_asignar and modo_auto and grupo is not None:
        agente = _elegir_agente(db, grupo, modo_auto)

    if agente is not None:
        _asignar_agente(db, incidencia, agente, usuario_id)

    if cambio_grupo or agente is not None:
        auditoria.registrar_evento(
            db,
            incidencia.id,
            usuario_id,
            accion="regla_aplicada",
            campo="automatizacion",
            valor_nuevo=", ".join(regla.nombre for regla in aplicadas),
            es_interno=True,
        )

    return {
        "reglas_aplicadas": [regla.nombre for regla in aplicadas],
        "grupo_id": incidencia.grupo_asignado_id,
        "agente_id": incidencia.agente_asignado_id,
    }
