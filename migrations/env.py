import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Permite importar el paquete app aunque Alembic se ejecute desde otra ruta.
RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from app import models  # noqa: E402,F401  (registra las tablas en Base.metadata)
from app.database import DATABASE_URL, Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# SQLAlchemy Interpolation exige escapar los '%' de la URL.
config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))

target_metadata = Base.metadata


def _opciones(connection=None) -> dict:
    opciones = {
        "target_metadata": target_metadata,
        "compare_type": True,
        "compare_server_default": True,
    }
    if connection is None:
        opciones["url"] = DATABASE_URL
        opciones["render_as_batch"] = DATABASE_URL.startswith("sqlite")
    else:
        opciones["connection"] = connection
        opciones["render_as_batch"] = connection.dialect.name == "sqlite"
    return opciones


def run_migrations_offline() -> None:
    """Genera el SQL en modo offline (sin conectar a la base de datos)."""
    context.configure(
        **(_opciones() | {"literal_binds": True, "dialect_opts": {"paramstyle": "named"}})
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Aplica las migraciones conectando a la base de datos."""
    conexion = config.attributes.get("connection")

    if conexion is not None:
        context.configure(**_opciones(conexion))
        with context.begin_transaction():
            context.run_migrations()
        return

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(**_opciones(connection))
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
