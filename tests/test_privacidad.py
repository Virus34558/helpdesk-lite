def test_comentarios_no_exponen_el_email_del_autor(client, cuentas):
    ticket = client.post(
        "/incidencias",
        json={"titulo": "Problema con el monitor"},
        headers=cuentas.solicitante.h,
    ).json()
    client.post(
        f"/incidencias/{ticket['id']}/comentarios",
        json={"contenido": "Estamos revisándolo", "es_interno": False},
        headers=cuentas.agente.h,
    )
    comentarios = client.get(
        f"/incidencias/{ticket['id']}/comentarios", headers=cuentas.solicitante.h
    ).json()
    assert len(comentarios) == 1
    assert "email" not in comentarios[0]["autor"]


def test_contrasena_de_menos_de_8_caracteres_se_rechaza(client):
    respuesta = client.post(
        "/auth/registro",
        json={
            "email": "nuevo@test.com",
            "nombre_completo": "Usuario Nuevo",
            "password": "abc1234",
        },
    )
    assert respuesta.status_code == 422
