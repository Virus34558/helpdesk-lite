"""Quién está mirando cada ticket (RF-2.5).

El registro vive en memoria del proceso: con varios workers cada uno ve solo
a los suyos. Suficiente para avisar de colisiones en un despliegue pequeño;
para varios workers haría falta un almacén compartido (Redis).
"""

import threading
import time

TTL_SEGUNDOS = 45

_vistas: dict[int, dict[str, float]] = {}
_cerrojo = threading.Lock()


def _ahora() -> float:
    return time.monotonic()


def _purgar(incidencia_id: int, momento: float) -> dict[str, float]:
    vistos = _vistas.get(incidencia_id)
    if vistos is None:
        return {}
    for usuario, marca in list(vistos.items()):
        if momento - marca > TTL_SEGUNDOS:
            del vistos[usuario]
    if not vistos:
        _vistas.pop(incidencia_id, None)
        return {}
    return vistos


def entrar(incidencia_id: int, usuario: str) -> None:
    with _cerrojo:
        _vistas.setdefault(incidencia_id, {})[usuario] = _ahora()


def salir(incidencia_id: int, usuario: str) -> None:
    with _cerrojo:
        vistos = _vistas.get(incidencia_id)
        if not vistos:
            return
        vistos.pop(usuario, None)
        if not vistos:
            _vistas.pop(incidencia_id, None)


def presentes(incidencia_id: int, excluir: str | None = None) -> list[str]:
    with _cerrojo:
        vistos = _purgar(incidencia_id, _ahora())
        return sorted(u for u in vistos if u != excluir)
