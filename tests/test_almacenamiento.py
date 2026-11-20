"""Almacenamiento de adjuntos: disco local y bucket S3 compatible."""

import io

import pytest

from app import almacenamiento


class ClienteS3Falso:
    """Imita el subconjunto de boto3 que usa la aplicación."""

    def __init__(self):
        self.subidas: dict[tuple[str, str], bytes] = {}
        self.borrados: list[tuple[str, str]] = []
        self.expiraciones: list[int] = []

    def upload_fileobj(self, archivo, Bucket, Key):
        self.subidas[(Bucket, Key)] = archivo.read()

    def generate_presigned_url(self, operacion, Params, ExpiresIn):
        self.expiraciones.append(ExpiresIn)
        return (
            f"https://s3.local/{Params['Bucket']}/{Params['Key']}"
            f"?operacion={operacion}&expira={ExpiresIn}"
        )

    def delete_object(self, Bucket, Key):
        self.borrados.append((Bucket, Key))


def test_almacen_local_guarda_el_archivo(tmp_path):
    almacen = almacenamiento.AlmacenLocal(tmp_path)

    almacen.guardar("abc.txt", io.BytesIO(b"hola"))

    assert (tmp_path / "abc.txt").read_bytes() == b"hola"
    assert almacen.descarga("abc.txt") == tmp_path / "abc.txt"


def test_almacen_local_elimina_sin_fallar_si_no_existe(tmp_path):
    almacen = almacenamiento.AlmacenLocal(tmp_path)
    almacen.guardar("abc.txt", io.BytesIO(b"hola"))

    almacen.eliminar("abc.txt")
    almacen.eliminar("abc.txt")

    assert not (tmp_path / "abc.txt").exists()


def test_almacen_s3_sube_al_bucket():
    cliente = ClienteS3Falso()
    almacen = almacenamiento.AlmacenS3(cliente, bucket="adjuntos", expiracion=900)

    almacen.guardar("abc.txt", io.BytesIO(b"hola"))

    assert cliente.subidas[("adjuntos", "abc.txt")] == b"hola"


def test_almacen_s3_descarga_con_url_firmada():
    cliente = ClienteS3Falso()
    almacen = almacenamiento.AlmacenS3(cliente, bucket="adjuntos", expiracion=900)

    url = almacen.descarga("abc.txt")

    assert url.startswith("https://s3.local/adjuntos/abc.txt")
    assert cliente.expiraciones == [900]


def test_almacen_s3_elimina_el_objeto():
    cliente = ClienteS3Falso()
    almacen = almacenamiento.AlmacenS3(cliente, bucket="adjuntos", expiracion=900)

    almacen.eliminar("abc.txt")

    assert cliente.borrados == [("adjuntos", "abc.txt")]


def test_obtener_almacen_usa_disco_local_por_defecto(monkeypatch, tmp_path):
    monkeypatch.delenv("STORAGE_BACKEND", raising=False)
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))

    almacen = almacenamiento.obtener_almacen()

    assert isinstance(almacen, almacenamiento.AlmacenLocal)
    assert almacen.directorio == tmp_path


def test_backend_s3_sin_bucket_falla_al_arrancar(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.delenv("S3_BUCKET", raising=False)

    with pytest.raises(RuntimeError, match="S3_BUCKET"):
        almacenamiento.obtener_almacen()
