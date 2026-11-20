"""Validación de la configuración de arranque."""

import os


def es_produccion() -> bool:
    """Detecta si la app corre en producción (Render o ENTORNO=produccion)."""
    return bool(os.getenv("RENDER")) or os.getenv("ENTORNO", "").lower() == "produccion"


def validar_configuracion() -> None:
    """Falla al arrancar si producción quedaría usando SQLite efímero."""
    if es_produccion() and not os.getenv("DATABASE_URL"):
        raise RuntimeError(
            "DATABASE_URL es obligatoria en producción: sin ella la aplicación "
            "usaría SQLite local y perdería los datos en cada despliegue."
        )
