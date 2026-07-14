def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def test_criar_caixa(client, usuario_comum, fases_seed):
    h = _headers(client, "comum@hs.com", "senha123")
    r = client.post("/caixas", json={"obs": "Lote Cuiabá"}, headers=h)
    assert r.status_code == 201
    body = r.json()
    assert body["obs"] == "Lote Cuiabá"
    assert body["data"] is not None
    assert body["total_os"] == 0


def test_listar_e_obter(client, usuario_comum):
    h = _headers(client, "comum@hs.com", "senha123")
    client.post("/caixas", json={"obs": "A"}, headers=h)
    client.post("/caixas", json={"obs": "B"}, headers=h)
    lista = client.get("/caixas", headers=h).json()
    assert lista["total"] == 2
    cid = lista["items"][0]["id"]
    det = client.get(f"/caixas/{cid}", headers=h)
    assert det.status_code == 200
    assert "ordens" in det.json()


def test_busca_por_obs(client, usuario_comum):
    h = _headers(client, "comum@hs.com", "senha123")
    client.post("/caixas", json={"obs": "Votorantim"}, headers=h)
    client.post("/caixas", json={"obs": "Outra"}, headers=h)
    r = client.get("/caixas?q=votor", headers=h).json()
    assert r["total"] == 1


def test_patch_obs(client, usuario_comum):
    h = _headers(client, "comum@hs.com", "senha123")
    cid = client.post("/caixas", json={"obs": "x"}, headers=h).json()["id"]
    r = client.patch(f"/caixas/{cid}", json={"obs": "novo"}, headers=h)
    assert r.status_code == 200
    assert r.json()["obs"] == "novo"


def test_delete_caixa_vazia(client, usuario_comum):
    h = _headers(client, "comum@hs.com", "senha123")
    cid = client.post("/caixas", json={}, headers=h).json()["id"]
    assert client.delete(f"/caixas/{cid}", headers=h).status_code == 204


def test_escrita_exige_expedicao_ou_admin(client, usuario_admin, usuario_lab):
    h = _headers(client, "lab@hs.com", "senha123")
    assert client.post("/caixas", json={}, headers=h).status_code == 403


def test_leitura_qualquer_interno(client, usuario_lab):
    h = _headers(client, "lab@hs.com", "senha123")
    assert client.get("/caixas", headers=h).status_code == 200


def test_patch_sem_obs_nao_zera(client, usuario_comum):
    h = _headers(client, "comum@hs.com", "senha123")
    cid = client.post("/caixas", json={"obs": "manter"}, headers=h).json()["id"]
    r = client.patch(f"/caixas/{cid}", json={}, headers=h)  # body vazio não deve apagar obs
    assert r.status_code == 200
    assert r.json()["obs"] == "manter"


def test_busca_por_id(client, usuario_comum):
    h = _headers(client, "comum@hs.com", "senha123")
    cid = client.post("/caixas", json={"obs": "alvo"}, headers=h).json()["id"]
    client.post("/caixas", json={"obs": "outra"}, headers=h)
    r = client.get(f"/caixas?q={cid}", headers=h).json()
    assert r["total"] == 1
    assert r["items"][0]["id"] == cid


def test_delete_caixa_com_os_409(client, usuario_comum, fases_seed, db_session):
    h = _headers(client, "comum@hs.com", "senha123")
    cid = client.post("/caixas", json={}, headers=h).json()["id"]
    # cria uma OS vinculada direto no banco (vincular via API é outra task)
    from app.models import Cliente, Ordem
    cli = Cliente(nome="Cliente Del")
    db_session.add(cli); db_session.flush()
    db_session.add(Ordem(cliente=cli.id, fase=4, caixa=cid, situacao="E"))
    db_session.commit()
    assert client.delete(f"/caixas/{cid}", headers=h).status_code == 409
