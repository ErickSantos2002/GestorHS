def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _cliente(client, h):
    return client.post("/clientes", json={"nome": "Cliente FX"}, headers=h).json()["id"]


def test_funcionarios_listar_de_cliente(client, usuario_admin):
    h = _headers(client, "admin@hs.com", "senha123")
    cid = _cliente(client, h)
    assert client.get(f"/clientes/{cid}/funcionarios", headers=h).json() == []
    assert client.get("/clientes/99999/funcionarios", headers=h).status_code == 404


def test_funcionario_crud_aninhado(client, usuario_admin):
    h = _headers(client, "admin@hs.com", "senha123")
    cid = _cliente(client, h)
    criado = client.post(f"/clientes/{cid}/funcionarios", json={"nome": "Maria", "cargo": "Motorista"}, headers=h)
    assert criado.status_code == 201
    assert criado.json()["cliente"] == cid
    fid = criado.json()["id"]
    assert client.patch(f"/funcionarios/{fid}", json={"cargo": "Supervisora"}, headers=h).json()["cargo"] == "Supervisora"
    assert client.delete(f"/funcionarios/{fid}", headers=h).status_code == 204
    assert client.get(f"/clientes/{cid}/funcionarios", headers=h).json() == []


def test_funcionario_cliente_inexistente_404(client, usuario_admin):
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.post("/clientes/99999/funcionarios", json={"nome": "X"}, headers=h)
    assert r.status_code == 404


def test_funcionarios_write_admin(client, usuario_admin, usuario_comum):
    h = _headers(client, "admin@hs.com", "senha123")
    cid = _cliente(client, h)
    hc = _headers(client, "comum@hs.com", "senha123")
    assert client.get(f"/clientes/{cid}/funcionarios", headers=hc).status_code == 200
    assert client.post(f"/clientes/{cid}/funcionarios", json={"nome": "X"}, headers=hc).status_code == 403
    assert client.patch("/funcionarios/1", json={"nome": "X"}, headers=hc).status_code == 403
    assert client.delete("/funcionarios/1", headers=hc).status_code == 403
