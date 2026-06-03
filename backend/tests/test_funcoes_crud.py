def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def test_criar_funcao(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    r = client.post("/funcoes", json={"descricao": "Recepção"}, headers=h)
    assert r.status_code == 201
    assert r.json()["descricao"] == "Recepção"


def test_criar_funcao_duplicada_409(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    client.post("/funcoes", json={"descricao": "Recepção"}, headers=h)
    assert client.post("/funcoes", json={"descricao": "Recepção"}, headers=h).status_code == 409


def test_patch_funcao(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    fid = client.post("/funcoes", json={"descricao": "Recepção"}, headers=h).json()["id"]
    r = client.patch(f"/funcoes/{fid}", json={"descricao": "Recepcao 2"}, headers=h)
    assert r.status_code == 200 and r.json()["descricao"] == "Recepcao 2"


def test_delete_funcao(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    fid = client.post("/funcoes", json={"descricao": "Temp"}, headers=h).json()["id"]
    assert client.delete(f"/funcoes/{fid}", headers=h).status_code == 204


def test_delete_funcao_em_uso_por_usuario_409(client, usuario_admin, usuario_comum):
    # usuario_comum tem função "Expedição"
    from app.models import Funcao
    h = _headers(client, "admin", "senha123")
    # descobre o id da função Expedição via lista
    fid = next(f["id"] for f in client.get("/funcoes", headers=h).json() if f["descricao"] == "Expedição")
    assert client.delete(f"/funcoes/{fid}", headers=h).status_code == 409


def test_delete_funcao_em_uso_por_fase_409(client, usuario_admin, fases_seed):
    h = _headers(client, "admin", "senha123")
    # função Laboratório é responsável pela fase 5
    fid = fases_seed["lab"]
    assert client.delete(f"/funcoes/{fid}", headers=h).status_code == 409


def test_funcoes_crud_exige_admin(client, usuario_admin, usuario_comum):
    h = _headers(client, "comum", "senha123")
    assert client.post("/funcoes", json={"descricao": "X"}, headers=h).status_code == 403
    assert client.patch("/funcoes/1", json={"descricao": "X"}, headers=h).status_code == 403
    assert client.delete("/funcoes/1", headers=h).status_code == 403
