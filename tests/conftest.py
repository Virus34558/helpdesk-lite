from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import auth, limites, models
from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def motor():
    # Base de datos temporal en memoria: los tests no tocan helpdesk.db
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def client(motor, monkeypatch, tmp_path):
    # Si en tu PC existe ADMIN_EMAIL, no debe influir en los tests
    monkeypatch.delenv("ADMIN_EMAIL", raising=False)
    # El scheduler no debe arrancar durante los tests
    monkeypatch.delenv("SLA_SCHEDULER_ENABLED", raising=False)
    # Nunca enviar correos reales desde los tests
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    TestingSession = sessionmaker(bind=motor, autoflush=False)

    def get_db_de_prueba():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = get_db_de_prueba
    limites.reiniciar()
    with TestClient(app) as cliente:
        yield cliente
    limites.reiniciar()
    app.dependency_overrides.clear()


@pytest.fixture()
def cuentas(motor):
    """Crea 4 usuarios (admin, agente, solicitante y otro solicitante).

    Cada uno tiene .id y .h (cabeceras con su token). Se crean directamente
    en la base de datos para que los tests vayan rapidos (sin bcrypt).
    """
    TestingSession = sessionmaker(bind=motor, autoflush=False)
    resultado = {}
    with TestingSession() as db:
        for nombre, rol in [
            ("admin", "administrador"),
            ("agente", "agente"),
            ("solicitante", "solicitante"),
            ("otro", "solicitante"),
        ]:
            usuario = models.Usuario(
                email=f"{nombre}@test.com",
                nombre_completo=f"Usuario {nombre}",
                password_hash="no-se-usa-en-los-tests",
                rol=rol,
            )
            db.add(usuario)
            db.commit()
            db.refresh(usuario)
            token = auth.create_access_token(
                {"sub": usuario.email, "rol": usuario.rol, "uid": usuario.id}
            )
            resultado[nombre] = SimpleNamespace(
                id=usuario.id, h={"Authorization": f"Bearer {token}"}
            )
    return SimpleNamespace(**resultado)