"""Catalogo de servicos de manutencao.

Laboratorio e Administrador cadastram e editam; excluir e' so do Administrador
— mesma decisao dos cilindros de gas (03/08/2026): quem opera nao deve apagar
sem querer.
"""


def test_laboratorio_cadastra_servico(client_lab):
    r = client_lab.post("/manutencao-servicos",
                        json={"descricao": "Troca da placa mãe", "resumo_padrao": "Placa substituída."})
    assert r.status_code == 201
    assert r.json()["descricao"] == "Troca da placa mãe"
    assert r.json()["ativo"] is True


def test_listar_devolve_os_cadastrados(client_lab):
    client_lab.post("/manutencao-servicos", json={"descricao": "A", "resumo_padrao": "a."})
    client_lab.post("/manutencao-servicos", json={"descricao": "B", "resumo_padrao": "b."})
    r = client_lab.get("/manutencao-servicos")
    assert r.status_code == 200
    assert [x["descricao"] for x in r.json()] == ["A", "B"]


def test_descricao_repetida_vira_409(client_lab):
    client_lab.post("/manutencao-servicos", json={"descricao": "A", "resumo_padrao": "a."})
    r = client_lab.post("/manutencao-servicos", json={"descricao": "A", "resumo_padrao": "outro."})
    assert r.status_code == 409


def test_laboratorio_edita_servico(client_lab):
    sid = client_lab.post("/manutencao-servicos", json={"descricao": "A", "resumo_padrao": "a."}).json()["id"]
    r = client_lab.put(f"/manutencao-servicos/{sid}", json={"resumo_padrao": "novo texto.", "ativo": False})
    assert r.status_code == 200
    assert r.json()["resumo_padrao"] == "novo texto."
    assert r.json()["ativo"] is False


def test_editar_com_descricao_nula_recusa_com_mensagem_propria(client_lab):
    """Sem a guarda, o NOT NULL do banco caia no except IntegrityError e o
    tecnico lia "ja existe um servico com essa descricao"."""
    sid = client_lab.post("/manutencao-servicos", json={"descricao": "A", "resumo_padrao": "a."}).json()["id"]
    r = client_lab.put(f"/manutencao-servicos/{sid}", json={"descricao": None})
    assert r.status_code == 422
    assert "vazia" in r.json()["detail"]
    assert "já existe" not in r.json()["detail"]


def test_editar_com_descricao_em_branco_recusa(client_lab):
    sid = client_lab.post("/manutencao-servicos", json={"descricao": "A", "resumo_padrao": "a."}).json()["id"]
    r = client_lab.put(f"/manutencao-servicos/{sid}", json={"descricao": "   "})
    assert r.status_code == 422
    assert "vazia" in r.json()["detail"]


def test_cadastrar_com_descricao_em_branco_recusa(client_lab):
    r = client_lab.post("/manutencao-servicos", json={"descricao": "  ", "resumo_padrao": "a."})
    assert r.status_code == 422
    assert "vazia" in r.json()["detail"]


def test_editar_so_o_resumo_nao_mexe_na_descricao(client_lab):
    """A guarda so vale quando `descricao` vem no corpo — PUT parcial continua valendo."""
    sid = client_lab.post("/manutencao-servicos", json={"descricao": "A", "resumo_padrao": "a."}).json()["id"]
    r = client_lab.put(f"/manutencao-servicos/{sid}", json={"resumo_padrao": "b."})
    assert r.status_code == 200
    assert r.json()["descricao"] == "A"


def test_laboratorio_nao_exclui(client_lab):
    sid = client_lab.post("/manutencao-servicos", json={"descricao": "A", "resumo_padrao": "a."}).json()["id"]
    assert client_lab.delete(f"/manutencao-servicos/{sid}").status_code == 403


def test_admin_exclui(client_admin):
    sid = client_admin.post("/manutencao-servicos", json={"descricao": "A", "resumo_padrao": "a."}).json()["id"]
    assert client_admin.delete(f"/manutencao-servicos/{sid}").status_code == 204


def test_outra_funcao_nao_cadastra(client, usuario_financeiro, fases_seed):
    tok = client.post("/auth/login", json={"email": "fin@hs.com", "senha": "senha123"}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    r = client.post("/manutencao-servicos", json={"descricao": "A", "resumo_padrao": "a."}, headers=h)
    assert r.status_code == 403


def test_exige_autenticacao(client):
    assert client.get("/manutencao-servicos").status_code == 401
