# Financeiro passa a ter acesso de escrita (criar/editar) a propostas, servicos e
# produtos, igual ao Comercial Pos-Vendas. Este arquivo cobre so a gate de permissao
# (require_funcao) nesses 3 endpoints; os testes de negocio completos ja moram em
# test_propostas.py / test_servicos.py / test_produtos.py.


def test_criar_produto_financeiro_e_permitido(client_fin):
    r = client_fin.post("/produtos", json={"nome": "Parafuso M6", "sku": "P001", "preco": 5, "ncm": "7318152900"})
    assert r.status_code == 201
    assert r.json()["sku"] == "P001"


def test_criar_produto_laboratorio_e_negado(client_lab):
    r = client_lab.post("/produtos", json={"nome": "Parafuso M6", "sku": "P001", "preco": 5, "ncm": "7318152900"})
    assert r.status_code == 403


def test_criar_servico_financeiro_e_permitido(client_fin):
    r = client_fin.post("/servicos", json={"nome": "Calibracao", "sku": "312", "preco": 395})
    assert r.status_code == 201
    assert r.json()["sku"] == "312"


def test_criar_servico_laboratorio_e_negado(client_lab):
    r = client_lab.post("/servicos", json={"nome": "Calibracao", "sku": "312", "preco": 395})
    assert r.status_code == 403


def test_criar_proposta_financeiro_e_permitido(client_fin):
    r = client_fin.post("/propostas", json={"itens": []})
    assert r.status_code == 201


def test_criar_proposta_laboratorio_e_negado(client_lab):
    r = client_lab.post("/propostas", json={"itens": []})
    assert r.status_code == 403


def test_atualizar_produto_financeiro_e_permitido(client_fin):
    r = client_fin.post("/produtos", json={"nome": "Arruela", "preco": 2, "ncm": "7318162900"})
    item_id = r.json()["id"]
    r = client_fin.patch(f"/produtos/{item_id}", json={"preco": 3})
    assert r.status_code == 200
    assert r.json()["preco"] == 3


def test_atualizar_servico_financeiro_e_permitido(client_fin):
    r = client_fin.post("/servicos", json={"nome": "Manutencao", "preco": 100})
    item_id = r.json()["id"]
    r = client_fin.patch(f"/servicos/{item_id}", json={"preco": 150})
    assert r.status_code == 200
    assert r.json()["preco"] == 150


def test_atualizar_proposta_financeiro_e_permitido(client_fin):
    r = client_fin.post("/propostas", json={"itens": []})
    pid = r.json()["id"]
    r = client_fin.put(f"/propostas/{pid}", json={"desconto": 15})
    assert r.status_code == 200
    assert r.json()["desconto"] == 15
