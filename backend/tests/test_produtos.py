def test_criar_produto_sem_auth_e_negado(client):
    # client_comercial mutaria os headers do mesmo TestClient (mesmo padrao de
    # client_lab/client_fin/client_exp); combinar as duas fixtures num so teste
    # faria o setup do client_comercial rodar antes do corpo do teste e a chamada
    # "sem auth" ja sairia com o token — por isso o caso sem auth vira teste proprio.
    r = client.post("/produtos", json={"nome": "Parafuso M6", "sku": "P001", "preco": 5, "ncm": "7318152900"})
    assert r.status_code in (401, 403)


def test_criar_produto_exige_funcao(client_comercial):
    r = client_comercial.post("/produtos", json={"nome": "Parafuso M6", "sku": "P001", "preco": 5, "ncm": "7318152900"})
    assert r.status_code == 201
    assert r.json()["sku"] == "P001"
    assert r.json()["ncm"] == "7318152900"


def test_listar_produtos(client_comercial):
    r = client_comercial.post("/produtos", json={"nome": "Parafuso M6", "sku": "P001", "preco": 5, "ncm": "7318152900"})
    assert r.status_code == 201
    r = client_comercial.get("/produtos")
    assert r.status_code == 200
    nomes = [p["nome"] for p in r.json()]
    assert "Parafuso M6" in nomes


def test_atualizar_e_excluir_produto(client_comercial):
    r = client_comercial.post("/produtos", json={"nome": "Arruela", "preco": 2, "ncm": "7318162900"})
    item_id = r.json()["id"]

    r = client_comercial.patch(f"/produtos/{item_id}", json={"preco": 3})
    assert r.status_code == 200
    assert r.json()["preco"] == 3

    r = client_comercial.delete(f"/produtos/{item_id}")
    assert r.status_code == 204

    r = client_comercial.get("/produtos")
    ids = [p["id"] for p in r.json()]
    assert item_id not in ids
