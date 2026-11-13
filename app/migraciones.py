from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def aplicar_migraciones_ligeras(engine: Engine) -> None:
    """Añade columnas nuevas a tablas existentes (create_all no las modifica).

    Es un puente mientras el proyecto no tenga Alembic. Solo cubre columnas
    nullable, que se pueden añadir sin reescribir datos.
    """
    inspector = inspect(engine)
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

    with engine.begin() as conexion:
        for columna, (tipo, indice) in pendientes.items():
            if columna in existentes:
                continue
            conexion.execute(
                text(f"ALTER TABLE incidencias ADD COLUMN {columna} {tipo}")
            )
            conexion.execute(
                text(
                    f"CREATE INDEX IF NOT EXISTS {indice} "
                    f"ON incidencias ({columna})"
                )
            )
