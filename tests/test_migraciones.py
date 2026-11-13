from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.migraciones import aplicar_migraciones

REVISION_INICIAL = "5c2debf054a0"


def _motor(tmp_path, nombre):
    return create_engine(f"sqlite:///{tmp_path / nombre}")


def test_crea_esquema_desde_cero(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTO_MIGRATE", "1")
    engine = _motor(tmp_path, "nueva.db")
    try:
        aplicar_migraciones(engine)
        tablas = set(inspect(engine).get_table_names())

        assert "incidencias" in tablas
        assert "alembic_version" in tablas
        with engine.connect() as conexion:
            version = conexion.execute(
                text("select version_num from alembic_version")
            ).scalar()
        assert version == REVISION_INICIAL
    finally:
        engine.dispose()


def test_sella_base_previa_sin_perder_datos(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTO_MIGRATE", "1")
    engine = _motor(tmp_path, "previa.db")
    try:
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        with Session() as db:
            db.add(
                models.Usuario(
                    email="previo@test.com",
                    nombre_completo="Usuario previo",
                    password_hash="no-se-usa",
                    rol=models.RolUsuario.SOLICITANTE.value,
                )
            )
            db.commit()

        aplicar_migraciones(engine)

        assert "alembic_version" in set(inspect(engine).get_table_names())
        with engine.connect() as conexion:
            version = conexion.execute(
                text("select version_num from alembic_version")
            ).scalar()
            total = conexion.execute(text("select count(*) from usuarios")).scalar()
        assert version == REVISION_INICIAL
        assert total == 1
    finally:
        engine.dispose()


def test_no_migra_si_esta_desactivado(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTO_MIGRATE", "0")
    engine = _motor(tmp_path, "desactivada.db")
    try:
        aplicar_migraciones(engine)
        assert "incidencias" not in set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
