"""Límite de intentos por IP y ruta en los endpoints de autenticación.

El contador vive en memoria del proceso: frena ataques de fuerza bruta y
abuso de bcrypt en un despliegue de un solo worker. Con varios workers cada
uno lleva su propia cuenta, así que el límite efectivo se multiplica.
"""

import os
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

_historial: dict[str, deque[float]] = defaultdict(deque)
_cerrojo = threading.Lock()


def _configuracion() -> tuple[int, float]:
    try:
        maximo = int(os.getenv("AUTH_MAX_INTENTOS", "10"))
    except ValueError:
        maximo = 10
    try:
        ventana = float(os.getenv("AUTH_VENTANA_SEGUNDOS", "60"))
    except ValueError:
        ventana = 60.0
    return max(1, maximo), max(1.0, ventana)


def reiniciar() -> None:
    """Vacía los contadores (tests y reinicios controlados)."""
    with _cerrojo:
        _historial.clear()


def limitar_auth(request: Request) -> None:
    """Dependencia de FastAPI: rechaza con 429 al superar el límite."""
    maximo, ventana = _configuracion()
    host = request.client.host if request.client else "desconocido"
    clave = f"{host}:{request.url.path}"
    ahora = time.monotonic()

    with _cerrojo:
        marcas = _historial[clave]
        while marcas and ahora - marcas[0] >= ventana:
            marcas.popleft()

        if len(marcas) >= maximo:
            espera = int(ventana - (ahora - marcas[0])) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    "Demasiados intentos. Espera unos segundos y vuelve a probar."
                ),
                headers={"Retry-After": str(espera)},
            )

        marcas.append(ahora)

        if len(_historial) > 1000:
            for clave_vacia in [c for c, v in _historial.items() if not v]:
                del _historial[clave_vacia]
