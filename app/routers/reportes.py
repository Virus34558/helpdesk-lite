import csv
import io
from collections import Counter
from datetime import date, datetime, time

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import auth, models, schemas, sla
from ..database import get_db

router = APIRouter(prefix="/reportes", tags=["Reportes y KPIs"])

solo_supervision = auth.require_roles(
    models.RolUsuario.SUPERVISOR,
    models.RolUsuario.ADMINISTRADOR,
)

ESTADOS_FINALES = ("Cerrado", "Cancelado")
ESTADOS_SLA_CERRADOS = ("Resuelto", "Cerrado", "Cancelado")


def _validar_rango(desde: date | None, hasta: date | None) -> None:
    if desde and hasta and desde > hasta:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La fecha 'desde' no puede ser posterior a 'hasta'",
        )


def _aplicar_filtros(
    db: Session,
    consulta,
    desde: date | None = None,
    hasta: date | None = None,
    grupo_asignado_id: int | None = None,
    agente_asignado_id: int | None = None,
    solicitante_id: int | None = None,
    departamento: str | None = None,
    estado: str | None = None,
    prioridad: str | None = None,
    categoria_id: int | None = None,
):
    if desde:
        consulta = consulta.filter(
            models.Incidencia.creada_en >= datetime.combine(desde, time.min)
        )
    if hasta:
        consulta = consulta.filter(
            models.Incidencia.creada_en <= datetime.combine(hasta, time.max)
        )
    if grupo_asignado_id is not None:
        consulta = consulta.filter(
            models.Incidencia.grupo_asignado_id == grupo_asignado_id
        )
    if agente_asignado_id is not None:
        consulta = consulta.filter(
            models.Incidencia.agente_asignado_id == agente_asignado_id
        )
    if solicitante_id is not None:
        consulta = consulta.filter(
            models.Incidencia.solicitante_id == solicitante_id
        )
    if departamento:
        consulta = consulta.filter(
            models.Incidencia.solicitante_id.in_(
                db.query(models.Usuario.id).filter(
                    models.Usuario.departamento == departamento
                )
            )
        )
    if estado:
        consulta = consulta.filter(models.Incidencia.estado == estado)
    if prioridad:
        consulta = consulta.filter(models.Incidencia.prioridad == prioridad)
    if categoria_id is not None:
        consulta = consulta.filter(models.Incidencia.categoria_id == categoria_id)
    return consulta


def _distribucion(
    incidencias, campo: str, orden: tuple[str, ...] | None = None
) -> list[schemas.DistribucionItem]:
    contador = Counter(getattr(incidencia, campo) or "Sin valor" for incidencia in incidencias)
    if orden:
        valores = [
            (valor, contador[valor]) for valor in orden if contador[valor]
        ]
        valores += [
            (valor, total)
            for valor, total in contador.items()
            if valor not in orden
        ]
    else:
        valores = sorted(contador.items(), key=lambda par: (-par[1], par[0]))
    return [
        schemas.DistribucionItem(valor=valor, total=total)
        for valor, total in valores
    ]


def _distribucion_categorias(
    db: Session, incidencias
) -> list[schemas.DistribucionCategoriaItem]:
    nombres = {categoria.id: categoria.nombre for categoria in db.query(models.Categoria)}
    contador = Counter(incidencia.categoria_id for incidencia in incidencias)
    filas = []
    for categoria_id, total in sorted(
        contador.items(), key=lambda par: (-par[1], par[0] or 0)
    ):
        filas.append(
            schemas.DistribucionCategoriaItem(
                categoria_id=categoria_id,
                nombre=nombres.get(categoria_id, "Sin categoría")
                if categoria_id is not None
                else "Sin categoría",
                total=total,
            )
        )
    return filas


@router.get(
    "/resumen",
    response_model=schemas.ResumenDashboard,
    summary="Resumen en tiempo real (Supervisor o Administrador)",
)
def resumen_dashboard(
    db: Session = Depends(get_db),
    _usuario: models.Usuario = Depends(solo_supervision),
):
    ahora = datetime.now()
    inicio_hoy = ahora.replace(hour=0, minute=0, second=0, microsecond=0)

    creados_hoy = (
        db.query(models.Incidencia)
        .filter(models.Incidencia.creada_en >= inicio_hoy)
        .count()
    )
    resueltos_hoy = (
        db.query(models.Incidencia)
        .filter(models.Incidencia.resuelta_en >= inicio_hoy)
        .count()
    )

    abiertas = (
        db.query(models.Incidencia)
        .filter(models.Incidencia.estado.notin_(ESTADOS_FINALES))
        .all()
    )
    activas_sla = [
        incidencia
        for incidencia in abiertas
        if incidencia.estado not in ESTADOS_SLA_CERRADOS
    ]
    estados_sla = [sla.calcular_estado_sla(incidencia, ahora) for incidencia in activas_sla]

    return schemas.ResumenDashboard(
        generado_en=ahora,
        creados_hoy=creados_hoy,
        resueltos_hoy=resueltos_hoy,
        abiertos=len(abiertas),
        sin_asignar=sum(
            1 for incidencia in abiertas if incidencia.agente_asignado_id is None
        ),
        sla_en_riesgo=estados_sla.count("en_riesgo"),
        sla_vencido=estados_sla.count("vencido"),
        sla_pausado=estados_sla.count("pausado"),
        por_estado=_distribucion(
            abiertas,
            "estado",
            (
                "Nuevo",
                "En progreso",
                "Pendiente de usuario",
                "Pendiente de tercero",
                "Resuelto",
            ),
        ),
        por_prioridad=_distribucion(
            abiertas,
            "prioridad",
            ("P1 - Crítica", "P2 - Alta", "P3 - Media", "P4 - Baja"),
        ),
        por_canal=_distribucion(abiertas, "canal_origen"),
        por_categoria=_distribucion_categorias(db, abiertas),
    )


@router.get(
    "/kpis",
    response_model=schemas.KpisReporte,
    summary="KPIs históricos (Supervisor o Administrador)",
)
def kpis(
    desde: date | None = None,
    hasta: date | None = None,
    grupo_asignado_id: int | None = None,
    agente_asignado_id: int | None = None,
    solicitante_id: int | None = None,
    departamento: str | None = None,
    db: Session = Depends(get_db),
    _usuario: models.Usuario = Depends(solo_supervision),
):
    _validar_rango(desde, hasta)
    consulta = _aplicar_filtros(
        db,
        db.query(models.Incidencia),
        desde=desde,
        hasta=hasta,
        grupo_asignado_id=grupo_asignado_id,
        agente_asignado_id=agente_asignado_id,
        solicitante_id=solicitante_id,
        departamento=departamento,
    )
    tickets = consulta.all()
    resueltos = [
        incidencia for incidencia in tickets if incidencia.resuelta_en is not None
    ]
    ids = [incidencia.id for incidencia in tickets]

    cumplimiento = None
    if resueltos:
        cumplidos = sum(
            1 for incidencia in resueltos if incidencia.sla_resolucion_cumplido
        )
        cumplimiento = round(cumplidos * 100 / len(resueltos), 2)

    mttr = None
    if resueltos:
        segundos = [
            max(0.0, (incidencia.resuelta_en - incidencia.creada_en).total_seconds())
            for incidencia in resueltos
        ]
        mttr = round(sum(segundos) / len(segundos) / 3600, 2)

    asignaciones: dict[int, datetime] = {}
    if ids:
        eventos = (
            db.query(
                models.RegistroAuditoria.incidencia_id,
                models.RegistroAuditoria.creado_en,
            )
            .filter(
                models.RegistroAuditoria.incidencia_id.in_(ids),
                models.RegistroAuditoria.campo == "agente_asignado_id",
                models.RegistroAuditoria.valor_nuevo.isnot(None),
            )
            .order_by(models.RegistroAuditoria.creado_en.asc())
            .all()
        )
        for incidencia_id, momento in eventos:
            asignaciones.setdefault(incidencia_id, momento)

    mtta = None
    if asignaciones:
        minutos = [
            max(0.0, (momento - incidencia.creada_en).total_seconds() / 60)
            for incidencia in tickets
            if (momento := asignaciones.get(incidencia.id)) is not None
        ]
        if minutos:
            mtta = round(sum(minutos) / len(minutos), 2)

    fcr = None
    resueltos_ids = [incidencia.id for incidencia in resueltos]
    if resueltos_ids:
        comentarios_staff = dict(
            db.query(
                models.Comentario.incidencia_id,
                func.count(models.Comentario.id),
            )
            .join(models.Usuario, models.Usuario.id == models.Comentario.autor_id)
            .filter(
                models.Comentario.incidencia_id.in_(resueltos_ids),
                models.Comentario.es_interno.is_(False),
                models.Usuario.rol != models.RolUsuario.SOLICITANTE.value,
            )
            .group_by(models.Comentario.incidencia_id)
            .all()
        )
        resueltos_fcr = sum(
            1
            for incidencia in resueltos
            if comentarios_staff.get(incidencia.id, 0) <= 1
        )
        fcr = round(resueltos_fcr * 100 / len(resueltos), 2)

    valoraciones = [
        incidencia.csat_puntuacion
        for incidencia in tickets
        if incidencia.csat_puntuacion is not None
    ]
    csat_media = (
        round(sum(valoraciones) / len(valoraciones), 2) if valoraciones else None
    )

    return schemas.KpisReporte(
        desde=desde,
        hasta=hasta,
        tickets_creados=len(tickets),
        tickets_resueltos=len(resueltos),
        cumplimiento_sla_pct=cumplimiento,
        mtta_minutos=mtta,
        mttr_horas=mttr,
        fcr_pct=fcr,
        csat_respuestas=len(valoraciones),
        csat_media=csat_media,
    )


@router.get(
    "/incidencias.csv",
    summary="Exportar incidencias a CSV (Supervisor o Administrador)",
)
def exportar_incidencias_csv(
    desde: date | None = None,
    hasta: date | None = None,
    grupo_asignado_id: int | None = None,
    agente_asignado_id: int | None = None,
    solicitante_id: int | None = None,
    departamento: str | None = None,
    estado: str | None = None,
    prioridad: str | None = None,
    categoria_id: int | None = None,
    db: Session = Depends(get_db),
    _usuario: models.Usuario = Depends(solo_supervision),
):
    _validar_rango(desde, hasta)
    consulta = _aplicar_filtros(
        db,
        db.query(models.Incidencia),
        desde=desde,
        hasta=hasta,
        grupo_asignado_id=grupo_asignado_id,
        agente_asignado_id=agente_asignado_id,
        solicitante_id=solicitante_id,
        departamento=departamento,
        estado=estado,
        prioridad=prioridad,
        categoria_id=categoria_id,
    )
    incidencias = consulta.order_by(models.Incidencia.id.asc()).all()

    categorias = {categoria.id: categoria.nombre for categoria in db.query(models.Categoria)}
    grupos = {grupo.id: grupo.nombre for grupo in db.query(models.GrupoSoporte)}
    usuarios = {
        usuario.id: usuario.nombre_completo for usuario in db.query(models.Usuario)
    }

    salida = io.StringIO()
    escritor = csv.writer(salida, lineterminator="\n")
    escritor.writerow(
        [
            "id",
            "id_legible",
            "tipo",
            "canal_origen",
            "titulo",
            "descripcion",
            "estado",
            "prioridad",
            "impacto",
            "urgencia",
            "categoria",
            "grupo",
            "agente",
            "solicitante",
            "creada_en",
            "actualizada_en",
            "resuelta_en",
            "primera_respuesta_en",
            "sla_limite_primera_respuesta",
            "sla_limite_resolucion",
            "sla_estado",
            "sla_resolucion_cumplido",
        ]
    )

    def fecha(valor):
        return valor.isoformat(timespec="seconds") if valor else ""

    for incidencia in incidencias:
        escritor.writerow(
            [
                incidencia.id,
                incidencia.id_legible,
                incidencia.tipo,
                incidencia.canal_origen,
                incidencia.titulo,
                incidencia.descripcion,
                incidencia.estado,
                incidencia.prioridad,
                incidencia.impacto,
                incidencia.urgencia,
                categorias.get(incidencia.categoria_id, ""),
                grupos.get(incidencia.grupo_asignado_id, ""),
                usuarios.get(incidencia.agente_asignado_id, ""),
                usuarios.get(incidencia.solicitante_id, ""),
                fecha(incidencia.creada_en),
                fecha(incidencia.actualizada_en),
                fecha(incidencia.resuelta_en),
                fecha(incidencia.primera_respuesta_en),
                fecha(incidencia.sla_limite_primera_respuesta),
                fecha(incidencia.sla_limite_resolucion),
                incidencia.estado_sla,
                incidencia.sla_resolucion_cumplido,
            ]
        )

    contenido = "\ufeff" + salida.getvalue()
    return Response(
        content=contenido,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="incidencias.csv"'},
    )
