def _hdr(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _cliente(db_session, cgc="11222333000144"):
    from app.models import Cliente
    c = Cliente(nome="ACME", cgc=cgc)
    db_session.add(c); db_session.commit(); db_session.refresh(c)
    return c


def test_criar_usuario_portal(client, usuario_admin, db_session):
    c = _cliente(db_session)
    h = _hdr(client, "admin", "senha123")
    r = client.post(f"/clientes/{c.id}/usuarios-portal", json={"login": "contato", "nome": "Contato", "email": "c@x.com", "senha": "temp12345"}, headers=h)
    assert r.status_code == 201
    body = r.json()
    assert body["login"] == "contato" and body["precisa_redefinir_senha"] is True
    assert "senha" not in body
    # a senha grava e o login-portal sinaliza precisa_redefinir (integração 6A)
    login = client.post("/auth/login-portal", json={"documento": "11222333000144", "login": "contato", "senha": "temp12345"}).json()
    assert login["precisa_redefinir"] is True


def test_criar_login_duplicado_409(client, usuario_admin, db_session):
    c = _cliente(db_session)
    h = _hdr(client, "admin", "senha123")
    p = {"login": "contato", "senha": "temp12345"}
    assert client.post(f"/clientes/{c.id}/usuarios-portal", json=p, headers=h).status_code == 201
    assert client.post(f"/clientes/{c.id}/usuarios-portal", json=p, headers=h).status_code == 409


def test_mesmo_login_clientes_diferentes_ok(client, usuario_admin, db_session):
    from app.models import Cliente
    c1 = _cliente(db_session)
    c2 = Cliente(nome="Beta", cgc="99888777000166"); db_session.add(c2); db_session.commit(); db_session.refresh(c2)
    h = _hdr(client, "admin", "senha123")
    assert client.post(f"/clientes/{c1.id}/usuarios-portal", json={"login": "contato", "senha": "temp12345"}, headers=h).status_code == 201
    assert client.post(f"/clientes/{c2.id}/usuarios-portal", json={"login": "contato", "senha": "temp12345"}, headers=h).status_code == 201


def test_listar_404_cliente(client, usuario_admin):
    assert client.get("/clientes/99999/usuarios-portal", headers=_hdr(client, "admin", "senha123")).status_code == 404


def test_patch_login_duplicado_409(client, usuario_admin, db_session):
    c = _cliente(db_session)
    h = _hdr(client, "admin", "senha123")
    a = client.post(f"/clientes/{c.id}/usuarios-portal", json={"login": "a", "senha": "temp12345"}, headers=h).json()
    client.post(f"/clientes/{c.id}/usuarios-portal", json={"login": "b", "senha": "temp12345"}, headers=h)
    assert client.patch(f"/usuarios-portal/{a['id']}", json={"login": "b"}, headers=h).status_code == 409
    assert client.patch(f"/usuarios-portal/{a['id']}", json={"nome": "Novo"}, headers=h).json()["nome"] == "Novo"


def test_redefinir_senha_portal(client, usuario_admin, db_session):
    from app.models import UsuarioCliente
    c = _cliente(db_session)
    h = _hdr(client, "admin", "senha123")
    uid = client.post(f"/clientes/{c.id}/usuarios-portal", json={"login": "a", "senha": "temp12345"}, headers=h).json()["id"]
    assert client.post(f"/usuarios-portal/{uid}/redefinir-senha", json={"nova_senha": "outra12345"}, headers=h).status_code == 204
    uc = db_session.get(UsuarioCliente, uid); db_session.refresh(uc)
    assert uc.precisa_redefinir_senha is True


def test_excluir_portal(client, usuario_admin, db_session):
    c = _cliente(db_session)
    h = _hdr(client, "admin", "senha123")
    uid = client.post(f"/clientes/{c.id}/usuarios-portal", json={"login": "a", "senha": "temp12345"}, headers=h).json()["id"]
    assert client.delete(f"/usuarios-portal/{uid}", headers=h).status_code == 204
    assert client.get(f"/clientes/{c.id}/usuarios-portal", headers=h).json() == []


def test_usuarios_portal_exige_admin(client, usuario_admin, usuario_comum, db_session):
    c = _cliente(db_session)
    h = _hdr(client, "comum", "senha123")
    assert client.get(f"/clientes/{c.id}/usuarios-portal", headers=h).status_code == 403
    assert client.post(f"/clientes/{c.id}/usuarios-portal", json={"login": "x", "senha": "temp12345"}, headers=h).status_code == 403
    assert client.delete("/usuarios-portal/1", headers=h).status_code == 403
