import asyncio
import logging
import os

from .database import SessionLocal
from .sla_vigilancia import revisar_slas

logger = logging.getLogger("helpdesk.sla")

INTERVALO_POR_DEFECTO = 300  # 5 minutos


def scheduler_habilitado() -> bool:
    return os.getenv("SLA_SCHEDULER_ENABLED", "").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _intervalo() -> int:
    try:
        return max(30, int(os.getenv("SLA_CHECK_INTERVAL_SECONDS", INTERVALO_POR_DEFECTO)))
    except ValueError:
        return INTERVALO_POR_DEFECTO


def _revisar_en_hilo() -> dict:
    db = SessionLocal()
    try:
        return revisar_slas(db)
    finally:
        db.close()


async def bucle_revision_sla() -> None:
    """Revisa los SLA periódicamente sin bloquear el event loop."""
    intervalo = _intervalo()
    while True:
        try:
            resultado = await asyncio.to_thread(_revisar_en_hilo)
            if resultado["alertas_80"] or resultado["breaches"]:
                logger.info(
                    "Revisión SLA: %s alertas al 80%%, %s breaches",
                    resultado["alertas_80"],
                    resultado["breaches"],
                )
        except Exception:
            logger.exception("Error en la revisión periódica de SLA")
        await asyncio.sleep(intervalo)
