def registrar(
    client,
    email="test@empresa.com",
    nombre="Usuario Test",
    password="password123",
    rol="solicitante",
    departamento="Sistemas",
):
    return client.post(
        "/auth/registro",
        json={
            "email": email,
            "nombre_completo": nombre,
            "password": password,
            "rol": rol,
            "departamento": departamento,
        },
    )


def login(client, email="test@empresa.com", password="password123"):
    return client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )


def test_registro_primer_usuario_es_administrador(client):
    respuesta = registrar(client, email="admin@empresa.com", nombre="Admin Sistema")
    assert respuesta.status_code == 201
    datos = respuesta.json()
    assert datos["email"] == "admin@empresa.com"
    assert datos["rol"] == "administrador"
    assert datos["activo"] is True
    assert "password_hash" not in datos


def test_registro_segundo_usuario_mantiene_rol_solicitante(client):
    registrar(client, email="primero@empresa.com", nombre="Primero")
    respuesta = registrar(
        client,
        email="solicitante@empresa.com",
        nombre="Juan Solicitante",
        rol="solicitante",
    )
    assert respuesta.status_code == 201
    assert respuesta.json()["rol"] == "solicitante"


def test_registro_email_duplicado_devuelve_400(client):
    registrar(client, email="repetido@empresa.com")
    respuesta = registrar(client, email="repetido@empresa.com")
    assert respuesta.status_code == 400
    assert "ya está registrado" in respuesta.json()["detail"]


def test_login_exitoso_y_obtener_token(client):
    registrar(client, email="login@empresa.com", password="miPasswordSegura")
    respuesta = login(client, email="login@empresa.com", password="miPasswordSegura")
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert "access_token" in datos
    assert datos["token_type"] == "bearer"
    assert datos["usuario"]["email"] == "login@empresa.com"


def test_login_password_incorrecta_devuelve_401(client):
    registrar(client, email="error@empresa.com", password="passwordCorrecta")
    respuesta = login(client, email="error@empresa.com", password="passwordIncorrecta")
    assert respuesta.status_code == 401


def test_login_usuario_inexistente_devuelve_401(client):
    respuesta = login(client, email="noexiste@empresa.com", password="password123")
    assert respuesta.status_code == 401


def test_perfil_me_con_token_valido(client):
    registrar(client, email="perfil@empresa.com", password="secretPassword")
    login_res = login(client, email="perfil@empresa.com", password="secretPassword").json()
    token = login_res["access_token"]

    respuesta = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["email"] == "perfil@empresa.com"


def test_perfil_me_sin_token_devuelve_401(client):
    respuesta = client.get("/auth/me")
    assert respuesta.status_code == 401


def test_control_acceso_rbac_usuarios_listado(client):
    # Primer usuario: Admin
    admin_res = registrar(client, email="admin@corp.com", password="adminPass").json()
    token_admin = login(client, email="admin@corp.com", password="adminPass").json()["access_token"]

    # Segundo usuario: Solicitante
    registrar(client, email="cliente@corp.com", password="clientePass", rol="solicitante")
    token_cliente = login(client, email="cliente@corp.com", password="clientePass").json()["access_token"]

    # Solicitante intenta acceder a /auth/usuarios -> 403 Forbidden
    res_cliente = client.get(
        "/auth/usuarios", headers={"Authorization": f"Bearer {token_cliente}"}
    )
    assert res_cliente.status_code == 403

    # Admin accede a /auth/usuarios -> 200 OK y ve los 2 usuarios
    res_admin = client.get(
        "/auth/usuarios", headers={"Authorization": f"Bearer {token_admin}"}
    )
    assert res_admin.status_code == 200
    assert len(res_admin.json()) == 2


def test_cambio_rol_solo_por_administrador(client):
    # Crear Admin y usuario Solicitante
    registrar(client, email="admin@corp.com", password="adminPass")
    token_admin = login(client, email="admin@corp.com", password="adminPass").json()["access_token"]

    usuario_solicitante = registrar(
        client, email="tecnico@corp.com", password="tecnicoPass", rol="solicitante"
    ).json()

    # Admin asciende a solicitante a rol 'agente'
    res = client.patch(
        f"/auth/usuarios/{usuario_solicitante['id']}/rol",
        json={"rol": "agente"},
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    assert res.status_code == 200
    assert res.json()["rol"] == "agente"

