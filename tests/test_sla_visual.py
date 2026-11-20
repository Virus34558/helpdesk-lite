"""El porcentaje de SLA consumido se expone para poder dibujarlo."""

from datetime import datetime, timedelta


def crear(client, cabeceras, **extra):
    cuerpo = {"titulo": "Fallo en el almacén", "descripcion": "no responde"}
    cuerpo.update(extra)
    return client.post("/incidencias", json=cuerpo, headers=cabeceras).json()


def test_la_incidencia_expone_el_porcentaje(client, cuentas):
    ticket = crear(client, cuentas.solicitante.h)

    assert "sla_porcentaje" in ticket
    assert 0.0 <= ticket["sla_porcentaje"] < 0.5


def test_el_porcentaje_crece_con_el_tiempo(client, cuentas, motor):
    from sqlalchemy.orm import sessionmaker

    from app import models

    ticket = crear(client, cuentas.solicitante.h)
    antes = client.get(
        f"/incidencias/{ticket['id']}", headers=cuentas.solicitante.h
    ).json()["sla_porcentaje"]

    Session = sessionmaker(bind=motor, autoflush=False)
    with Session() as db:
        incidencia = db.get(models.Incidencia, ticket["id"])
        incidencia.creada_en = datetime.now() - timedelta(days=3)
        db.commit()

    despues = client.get(
        f"/incidencias/{ticket['id']}", headers=cuentas.solicitante.h
    ).json()["sla_porcentaje"]

    assert despues > antes
    assert 0.0 <= despues <= 1.5
