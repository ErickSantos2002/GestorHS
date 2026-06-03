def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def test_categorias_read_interno_write_admin(client, usuario_admin, usuario_comum):
    assert client.get("/categorias", headers=_headers(client, "comum", "senha123")).status_code == 200
    assert client.post("/categorias", json={"descricao": "X"}, headers=_headers(client, "comum", "senha123")).status_code == 403


def test_categoria_crud_com_setor(client, usuario_admin, db_session):
    from app.models import Setor
    s = Setor(descricao="Lab")
    db_session.add(s)
    db_session.commit()
    h = _headers(client, "admin", "senha123")
    criado = client.post("/categorias", json={"descricao": "Bafômetros", "setor": s.id, "posicao": 2}, headers=h)
    assert criado.status_code == 201
    cid = criado.json()["id"]
    assert criado.json()["setor"] == s.id
    assert criado.json()["posicao"] == 2
    assert client.patch(f"/categorias/{cid}", json={"descricao": "Bafômetros PRO"}, headers=h).json()["descricao"] == "Bafômetros PRO"
    assert client.delete(f"/categorias/{cid}", headers=h).status_code == 204
