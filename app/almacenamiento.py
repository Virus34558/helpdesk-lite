"""Almacenamiento de adjuntos: disco local o bucket S3 compatible.

En producción el disco de Render es efímero, así que el backend por defecto
(``local``) vale para desarrollo. Con ``STORAGE_BACKEND=s3`` los archivos van
a un bucket (AWS S3, MinIO, Backblaze...) y la descarga usa URL firmada.
"""

import os
import shutil
from pathlib import Path
from typing import BinaryIO, Protocol


class Almacen(Protocol):
    def guardar(self, nombre: str, archivo: BinaryIO) -> None: ...

    def descarga(self, nombre: str) -> Path | str: ...

    def eliminar(self, nombre: str) -> None: ...


class AlmacenLocal:
    """Guarda los adjuntos en una carpeta del disco."""

    def __init__(self, directorio: Path):
        self.directorio = Path(directorio)

    def guardar(self, nombre: str, archivo: BinaryIO) -> None:
        self.directorio.mkdir(parents=True, exist_ok=True)
        with (self.directorio / nombre).open("wb") as destino:
            shutil.copyfileobj(archivo, destino)

    def descarga(self, nombre: str) -> Path:
        return self.directorio / nombre

    def eliminar(self, nombre: str) -> None:
        (self.directorio / nombre).unlink(missing_ok=True)


class AlmacenS3:
    """Guarda los adjuntos en un bucket S3 compatible."""

    def __init__(self, cliente, bucket: str, expiracion: int = 300):
        self.cliente = cliente
        self.bucket = bucket
        self.expiracion = expiracion

    def guardar(self, nombre: str, archivo: BinaryIO) -> None:
        self.cliente.upload_fileobj(archivo, self.bucket, nombre)

    def descarga(self, nombre: str) -> str:
        return self.cliente.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": nombre},
            ExpiresIn=self.expiracion,
        )

    def eliminar(self, nombre: str) -> None:
        self.cliente.delete_object(Bucket=self.bucket, Key=nombre)


def _almacen_s3() -> AlmacenS3:
    bucket = os.getenv("S3_BUCKET")
    if not bucket:
        raise RuntimeError(
            "STORAGE_BACKEND=s3 requiere S3_BUCKET (y opcionalmente S3_ENDPOINT_URL, "
            "S3_REGION, S3_ACCESS_KEY_ID y S3_SECRET_ACCESS_KEY)."
        )

    try:
        import boto3
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise RuntimeError(
            "STORAGE_BACKEND=s3 requiere el paquete boto3 instalado "
            "(pip install boto3)."
        ) from exc

    try:
        expiracion = int(os.getenv("S3_PRESIGN_SECONDS", "300"))
    except ValueError:
        expiracion = 300

    cliente = boto3.client(
        "s3",
        endpoint_url=os.getenv("S3_ENDPOINT_URL") or None,
        region_name=os.getenv("S3_REGION") or None,
        aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID") or None,
        aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY") or None,
    )
    return AlmacenS3(cliente, bucket, max(60, expiracion))


def obtener_almacen() -> Almacen:
    backend = os.getenv("STORAGE_BACKEND", "local").strip().lower()
    if backend == "s3":
        return _almacen_s3()
    return AlmacenLocal(Path(os.getenv("UPLOAD_DIR", "uploads")))
