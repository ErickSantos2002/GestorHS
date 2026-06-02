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
