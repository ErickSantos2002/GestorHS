def test_criar_servico_sem_auth_e_negado(client):
    # client_comercial mutaria os headers do mesmo TestClient (mesmo padrao de
    # client_lab/client_fin/client_exp); combinar as duas fixtures num so teste
    # faria o setup do client_comercial rodar antes do corpo do teste e a chamada
    # "sem auth" ja sairia com o token — por isso o caso sem auth vira teste proprio.
    r = client.post("/servicos", json={"nome": "Calibracao", "sku": "312", "preco": 395})
    assert r.status_code in (401, 403)


def test_criar_servico_exige_funcao(client_comercial):
    r = client_comercial.post("/servicos", json={"nome": "Calibracao", "sku": "312", "preco": 395})
    assert r.status_code == 201
    assert r.json()["sku"] == "312"


def test_listar_servicos(client_comercial):
    r = client_comercial.post("/servicos", json={"nome": "Calibracao", "sku": "312", "preco": 395})
    assert r.status_code == 201
    r = client_comercial.get("/servicos")
    assert r.status_code == 200
    nomes = [s["nome"] for s in r.json()]
    assert "Calibracao" in nomes


def test_atualizar_e_excluir_servico(client_comercial):
    r = client_comercial.post("/servicos", json={"nome": "Manutencao", "preco": 100})
    item_id = r.json()["id"]

    r = client_comercial.patch(f"/servicos/{item_id}", json={"preco": 150})
    assert r.status_code == 200
    assert r.json()["preco"] == 150

    r = client_comercial.delete(f"/servicos/{item_id}")
    assert r.status_code == 204

    r = client_comercial.get("/servicos")
    ids = [s["id"] for s in r.json()]
    assert item_id not in ids
