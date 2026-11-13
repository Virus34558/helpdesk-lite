import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection, Engine

from .database import Base

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
ALEMBIC_INI = RAIZ_PROYECTO / "alembic.ini"
DIRECTORIO_MIGRACIONES = RAIZ_PROYECTO / "migrations"


def _config_alembic() -> Config:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(DIRECTORIO_MIGRACIONES))
    return config


def aplicar_migraciones_ligeras(conexion: Connection) -> None:
    """Puente para bases creadas antes de adoptar Alembic.

    Añade las dos columnas que se incorporaron con ``ALTER TABLE`` y que
    ``create_all`` no puede añadir por sí solo.
    """
    inspector = inspect(conexion)
    if "incidencias" not in inspector.get_table_names():
        return

    existentes = {columna["name"] for columna in inspector.get_columns("incidencias")}
    pendientes = {
        "grupo_asignado_id": (
            "INTEGER REFERENCES grupos_soporte(id)",
            "ix_incidencias_grupo_asignado_id",
        ),
        "categoria_id": (
            "INTEGER REFERENCES categorias(id)",
            "ix_incidencias_categoria_id",
        ),
    }

    for columna, (tipo, indice) in pendientes.items():
        if columna in existentes:
            continue
        conexion.execute(text(f"ALTER TABLE incidencias ADD COLUMN {columna} {tipo}"))
        conexion.execute(
            text(f"CREATE INDEX IF NOT EXISTS {indice} ON incidencias ({columna})")
        )


def _preparar_base_existente(conexion: Connection) -> bool:
    """Prepara una base previa a Alembic y devuelve si hay que sellarla.

    Si las tablas ya existen pero no hay ``alembic_version``, se crea lo que
    falte y se aplican las columnas puente antes de sellar la revisión actual,
    para no intentar recrear tablas que ya contienen datos.
    """
    inspector = inspect(conexion)
    tablas = set(inspector.get_table_names())
    if "alembic_version" in tablas or not tablas:
        return False

    Base.metadata.create_all(bind=conexion, checkfirst=True)
    aplicar_migraciones_ligeras(conexion)
    return True


def aplicar_migraciones(engine: Engine) -> None:
    """Lleva la base de datos a la última revisión de Alembic.

    Se puede desactivar con ``AUTO_MIGRATE=0`` (útil para ejecutar
    ``alembic upgrade head`` como paso separado en el despliegue).
    """
    if os.getenv("AUTO_MIGRATE", "1").lower() in {"0", "false", "no", "off"}:
        return

    config = _config_alembic()

    with engine.begin() as conexion:
        sello_inicial = _preparar_base_existente(conexion)

    with engine.connect() as conexion:
        config.attributes["connection"] = conexion
        if sello_inicial:
            command.stamp(config, "head")
        command.upgrade(config, "head")
