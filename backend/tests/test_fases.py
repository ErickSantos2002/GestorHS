def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def test_listar_fases(client, usuario_admin, fases_seed):
    h = _headers(client, "admin", "senha123")
    r = client.get("/fases", headers=h)
    assert r.status_code == 200
    fases = r.json()
    assert [f["id"] for f in fases] == [4, 5, 6, 7, 8, 9, 10]
    recebido = next(f for f in fases if f["id"] == 4)
    assert recebido["descricao"] == "Recebido"
    assert recebido["funcao_nome"] == "Expedição"


def test_patch_fase_responsavel_admin(client, usuario_admin, usuario_lab, fases_seed):
    h = _headers(client, "admin", "senha123")
    lab_id = fases_seed["lab"]
    r = client.patch("/fases/4", json={"funcao_responsavel": lab_id}, headers=h)
    assert r.status_code == 200
    assert r.json()["funcao_responsavel"] == lab_id
    assert r.json()["funcao_nome"] == "Laboratório"


def test_patch_fase_funcao_inexistente_404(client, usuario_admin, fases_seed):
    h = _headers(client, "admin", "senha123")
    assert client.patch("/fases/4", json={"funcao_responsavel": 9999}, headers=h).status_code == 404


def test_patch_fase_inexistente_404(client, usuario_admin, fases_seed):
    h = _headers(client, "admin", "senha123")
    assert client.patch("/fases/99", json={"funcao_responsavel": None}, headers=h).status_code == 404


def test_patch_fase_exige_admin(client, usuario_admin, usuario_comum, fases_seed):
    h = _headers(client, "comum", "senha123")
    assert client.patch("/fases/4", json={"funcao_responsavel": None}, headers=h).status_code == 403
