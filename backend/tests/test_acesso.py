def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def test_listar_funcoes_admin(client, usuario_admin):
    r = client.get("/funcoes", headers=_headers(client, "admin", "senha123"))
    assert r.status_code == 200
    assert any(f["descricao"] == "Administrador" for f in r.json())


def test_funcoes_nega_nao_admin(client, usuario_comum):
    r = client.get("/funcoes", headers=_headers(client, "comum", "senha123"))
    assert r.status_code == 403


def test_listar_usuarios_admin(client, usuario_admin):
    r = client.get("/usuarios", headers=_headers(client, "admin", "senha123"))
    assert r.status_code == 200
    assert any(u["login"] == "admin" for u in r.json())


def test_usuarios_nega_nao_admin(client, usuario_comum):
    r = client.get("/usuarios", headers=_headers(client, "comum", "senha123"))
    assert r.status_code == 403


def test_criar_usuario(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    r = client.post("/usuarios", json={"login": "joao", "nome": "Joao", "senha": "segredo123"}, headers=h)
    assert r.status_code == 201
    assert r.json()["login"] == "joao"
    assert client.post("/auth/login", json={"login": "joao", "senha": "segredo123"}).status_code == 200


def test_criar_usuario_login_duplicado(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    r = client.post("/usuarios", json={"login": "admin", "senha": "segredo123"}, headers=h)
    assert r.status_code == 409


def test_criar_usuario_senha_curta(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    r = client.post("/usuarios", json={"login": "curto", "senha": "1234"}, headers=h)
    assert r.status_code == 422
