def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def test_listar_setores_qualquer_interno(client, usuario_comum):
    r = client.get("/setores", headers=_headers(client, "comum@hs.com", "senha123"))
    assert r.status_code == 200
    assert r.json() == []


def test_criar_setor_exige_admin(client, usuario_comum):
    r = client.post("/setores", json={"descricao": "Laboratório"}, headers=_headers(client, "comum@hs.com", "senha123"))
    assert r.status_code == 403


def test_crud_setor_admin(client, usuario_admin):
    h = _headers(client, "admin@hs.com", "senha123")
    criado = client.post("/setores", json={"descricao": "Expedição"}, headers=h)
    assert criado.status_code == 201
    sid = criado.json()["id"]
    assert client.get(f"/setores/{sid}", headers=h).json()["descricao"] == "Expedição"
    assert client.patch(f"/setores/{sid}", json={"descricao": "Expedição 2"}, headers=h).json()["descricao"] == "Expedição 2"
    assert client.get("/setores/99999", headers=h).status_code == 404
    assert client.delete(f"/setores/{sid}", headers=h).status_code == 204
    assert client.get(f"/setores/{sid}", headers=h).status_code == 404


def test_excluir_setor_em_uso_409(client, usuario_admin, db_session):
    from app.models import Setor, Categoria
    s = Setor(descricao="Em uso")
    db_session.add(s)
    db_session.flush()
    db_session.add(Categoria(descricao="Cat", setor=s.id, posicao=0))
    db_session.commit()
    r = client.delete(f"/setores/{s.id}", headers=_headers(client, "admin@hs.com", "senha123"))
    assert r.status_code == 409
