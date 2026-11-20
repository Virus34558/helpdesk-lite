"""Triaje asistido: el modelo propone y el agente decide.

Reglas de la casa:
- Sin proveedor configurado la aplicación funciona igual; el endpoint devuelve 503.
- La prioridad se recalcula con la matriz ITIL, nunca se copia del modelo.
- La respuesta se valida y se normaliza: si no cuadra, 502 en vez de inventar.
- Hay caché por texto y tope diario por usuario (la demo es pública).
"""

import hashlib
import json
import os
import unicodedata
from datetime import date
from typing import Protocol

import httpx
from sqlalchemy.orm import Session

from . import models, reglas

MAX_TEXTO = 4000

TIPOS = ("Incidencia", "Solicitud de Servicio", "Problema", "Cambio")
IMPACTOS = ("Bajo", "Medio", "Alto")
URGENCIAS = ("Baja", "Media", "Alta", "Crítica")

_cache: dict[str, dict] = {}
_uso: dict[int, tuple[date, int]] = {}


class AsistenteNoDisponible(Exception):
    """No hay proveedor configurado o no responde."""


class LimiteAsistente(Exception):
    """El usuario ha agotado su cupo diario."""


class RespuestaInvalida(Exception):
    """El modelo devolvió algo que no se puede interpretar."""


class Proveedor(Protocol):
    def disponible(self) -> bool: ...

    def sugerir(self, texto: str) -> str: ...


class ProveedorOllama:
    def __init__(self, url: str, modelo: str, timeout: float = 60.0):
        self.url = url.rstrip("/")
        self.modelo = modelo
        self.timeout = timeout

    def disponible(self) -> bool:
        return bool(self.url and self.modelo)

    def sugerir(self, texto: str) -> str:
        respuesta = httpx.post(
            f"{self.url}/api/chat",
            json={
                "model": self.modelo,
                "messages": [{"role": "user", "content": texto}],
                "stream": False,
                "format": "json",
                "options": {"temperature": 0, "num_predict": 200},
            },
            timeout=self.timeout,
        )
        respuesta.raise_for_status()
        return respuesta.json()["message"]["content"]


def obtener_proveedor() -> Proveedor | None:
    nombre = os.getenv("ASISTENTE_PROVEEDOR", "ninguno").strip().lower()
    if nombre == "ollama":
        return ProveedorOllama(
            os.getenv("OLLAMA_URL", "http://127.0.0.1:11434"),
            os.getenv("OLLAMA_MODELO", "qwen2.5:7b-instruct"),
            _timeout(),
        )
    return None


def _timeout() -> float:
    try:
        return max(5.0, float(os.getenv("ASISTENTE_TIMEOUT", "60")))
    except ValueError:
        return 60.0


def _limite_diario() -> int:
    try:
        return max(1, int(os.getenv("ASISTENTE_MAX_DIA", "50")))
    except ValueError:
        return 50


def reiniciar() -> None:
    """Vacía caché y contadores (tests y reinicios controlados)."""
    _cache.clear()
    _uso.clear()


def _normalizar(valor: str) -> str:
    sin_tildes = (
        unicodedata.normalize("NFKD", str(valor))
        .encode("ascii", "ignore")
        .decode()
    )
    return sin_tildes.strip().lower()


def _elegir(valor, opciones: tuple[str, ...], campo: str) -> str:
    buscado = _normalizar(valor)
    for opcion in opciones:
        if _normalizar(opcion) == buscado:
            return opcion
    raise RespuestaInvalida(f"Valor no válido para {campo}: {valor!r}")


def _extraer_json(texto: str) -> dict:
    limpio = texto.strip()
    if limpio.startswith("```"):
        limpio = limpio.strip("`")
        if "\n" in limpio:
            limpio = limpio.split("\n", 1)[1]
    try:
        datos = json.loads(limpio)
    except json.JSONDecodeError as exc:
        raise RespuestaInvalida("El modelo no devolvió un JSON válido") from exc
    if not isinstance(datos, dict):
        raise RespuestaInvalida("El modelo no devolvió un objeto JSON")
    return datos


def _prompt(titulo: str, descripcion: str, categorias: list[models.Categoria]) -> str:
    lista = "\n".join(f"- {c.nombre}" for c in categorias) or "- (sin categorías)"
    return (
        "Eres un técnico de soporte IT. Clasifica el ticket.\n"
        "Responde SOLO con un objeto JSON con las claves: "
        "tipo, impacto, urgencia, categoria, motivo.\n"
        f"tipo debe ser uno de: {', '.join(TIPOS)}.\n"
        f"impacto debe ser uno de: {', '.join(IMPACTOS)}.\n"
        f"urgencia debe ser uno de: {', '.join(URGENCIAS)}.\n"
        "categoria debe ser exactamente una de esta lista, o null:\n"
        f"{lista}\n"
        "motivo: una frase corta en español que justifique la clasificación.\n\n"
        f"Ticket: {titulo}\n\n{descripcion}"
    )


def _comprobar_cupo(usuario_id: int) -> None:
    hoy = date.today()
    dia, usadas = _uso.get(usuario_id, (hoy, 0))
    if dia != hoy:
        dia, usadas = hoy, 0
    if usadas >= _limite_diario():
        raise LimiteAsistente(
            "Has agotado el cupo diario del asistente. Vuelve mañana."
        )
    _uso[usuario_id] = (dia, usadas + 1)


def sugerir_triaje(
    db: Session, incidencia: models.Incidencia, usuario_id: int
) -> dict:
    proveedor = obtener_proveedor()
    if proveedor is None or not proveedor.disponible():
        raise AsistenteNoDisponible(
            "El asistente no está configurado (ASISTENTE_PROVEEDOR=ollama)."
        )

    _comprobar_cupo(usuario_id)

    categorias = (
        db.query(models.Categoria)
        .filter(models.Categoria.activa.is_(True))
        .order_by(models.Categoria.nombre.asc())
        .all()
    )
    texto = f"{incidencia.titulo}\n\n{incidencia.descripcion or ''}".strip()[:MAX_TEXTO]
    clave = hashlib.sha256(
        (texto + "|" + ",".join(c.nombre for c in categorias)).encode("utf-8")
    ).hexdigest()

    if clave in _cache:
        return dict(_cache[clave])

    try:
        bruto = proveedor.sugerir(_prompt(incidencia.titulo, texto, categorias))
    except httpx.HTTPError as exc:
        raise AsistenteNoDisponible("El proveedor del asistente no responde") from exc

    datos = _extraer_json(bruto)
    impacto = _elegir(datos.get("impacto"), IMPACTOS, "impacto")
    urgencia = _elegir(datos.get("urgencia"), URGENCIAS, "urgencia")
    tipo = _elegir(datos.get("tipo"), TIPOS, "tipo")

    nombre_categoria = datos.get("categoria")
    categoria_id = None
    categoria_nombre = None
    if nombre_categoria:
        buscada = _normalizar(nombre_categoria)
        for categoria in categorias:
            if _normalizar(categoria.nombre) == buscada:
                categoria_id = categoria.id
                categoria_nombre = categoria.nombre
                break

    sugerencia = {
        "tipo": tipo,
        "impacto": impacto,
        "urgencia": urgencia,
        # La prioridad la decide la matriz ITIL, no el modelo
        "prioridad": reglas.calcular_prioridad(impacto, urgencia),
        "categoria_id": categoria_id,
        "categoria": categoria_nombre,
        "motivo": str(datos.get("motivo") or "").strip()[:300],
    }
    _cache[clave] = sugerencia
    return dict(sugerencia)
