def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def test_marcas_read_interno_write_admin(client, usuario_admin, usuario_comum):
    assert client.get("/marcas", headers=_headers(client, "comum", "senha123")).status_code == 200
    assert client.post("/marcas", json={"descricao": "X"}, headers=_headers(client, "comum", "senha123")).status_code == 403
    h = _headers(client, "admin", "senha123")
    mid = client.post("/marcas", json={"descricao": "Dräger"}, headers=h).json()["id"]
    assert client.patch(f"/marcas/{mid}", json={"descricao": "Drager"}, headers=h).json()["descricao"] == "Drager"
    assert client.delete(f"/marcas/{mid}", headers=h).status_code == 204


def test_grupos_crud_com_texto(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    criado = client.post("/grupos", json={"descricao": "VIP", "texto": "clientes preferenciais"}, headers=h)
    assert criado.status_code == 201
    gid = criado.json()["id"]
    assert criado.json()["texto"] == "clientes preferenciais"
    assert client.patch(f"/grupos/{gid}", json={"texto": "atualizado"}, headers=h).json()["texto"] == "atualizado"
    assert client.delete(f"/grupos/{gid}", headers=h).status_code == 204
