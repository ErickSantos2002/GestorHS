def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def test_abrir_os_sucesso(client, usuario_comum, fases_seed, os_base, db_session):
    # usuario_comum = Expedição
    h = _headers(client, "comum", "senha123")
    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C",
        "condicao_chegada": "Com avarias",
    }, headers=h)
    assert r.status_code == 201
    body = r.json()
    assert body["fase"] == 4
    assert body["cliente"] == os_base["cliente"]      # derivado do equipamento
    assert body["recebido"] is True
    assert body["data_chegada"] is not None
    # os_atual atualizado no equipamento
    from app.models import EquipamentoCliente
    ec = db_session.get(EquipamentoCliente, os_base["equipamento_cliente"])
    db_session.refresh(ec)
    assert ec.os_atual == body["id"]
    # log de abertura
    logs = client.get(f"/ordens/{body['id']}/logs", headers=h).json()
    assert len(logs) == 1


def test_abrir_os_admin_tambem_pode(client, usuario_admin, fases_seed, os_base):
    h = _headers(client, "admin", "senha123")
    r = client.post("/ordens", json={"equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "M"}, headers=h)
    assert r.status_code == 201


def test_abrir_os_equipamento_inexistente_404(client, usuario_comum, fases_seed):
    h = _headers(client, "comum", "senha123")
    assert client.post("/ordens", json={"equipamento_cliente": 9999, "tipo_servico": "C"}, headers=h).status_code == 404


def test_abrir_os_duplicada_409(client, usuario_comum, fases_seed, os_base):
    h = _headers(client, "comum", "senha123")
    p = {"equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C"}
    assert client.post("/ordens", json=p, headers=h).status_code == 201
    assert client.post("/ordens", json=p, headers=h).status_code == 409  # já tem OS ativa


def test_abrir_os_exige_expedicao_ou_admin(client, usuario_admin, usuario_lab, fases_seed, os_base):
    h = _headers(client, "lab", "senha123")
    assert client.post("/ordens", json={"equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C"}, headers=h).status_code == 403


def test_abrir_os_com_caixa(client, usuario_comum, fases_seed, os_base):
    h = _headers(client, "comum", "senha123")
    cid = client.post("/caixas", json={"obs": "lote"}, headers=h).json()["id"]
    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"],
        "tipo_servico": "C", "caixa": cid,
    }, headers=h)
    assert r.status_code == 201
    assert r.json()["caixa"] == cid
    det = client.get(f"/caixas/{cid}", headers=h).json()
    assert det["total_os"] == 1


def test_abrir_os_caixa_inexistente_404(client, usuario_comum, fases_seed, os_base):
    h = _headers(client, "comum", "senha123")
    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"],
        "tipo_servico": "C", "caixa": 9999,
    }, headers=h)
    assert r.status_code == 404


def test_abrir_grava_recebimento(client, usuario_comum, fases_seed, os_base, db_session):
    h = _headers(client, "comum", "senha123")
    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"],
        "tipo_servico": "C",
        "data_chegada": "2026-06-08",
        "condicao_chegada": "Bom estado",
        "checklist": [3, 1],
        "pilhas": 4,
        "bocais": 2,
        "observacoes": "veio sem maleta",
    }, headers=h)
    assert r.status_code == 201
    body = r.json()
    assert body["condicao_chegada"] == "Bom estado"
    assert body["checklist_ids"] == [1, 3]
    assert body["acessorios_presentes"] == ["Bobinas", "Cabos USB"]
    assert body["pilhas"] == 4
    assert body["bocais"] == 2
    assert body["obs"] == "veio sem maleta"
    assert body["data_chegada"].startswith("2026-06-08")


def test_abrir_data_chegada_default_hoje(client, usuario_comum, fases_seed, os_base):
    h = _headers(client, "comum", "senha123")
    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "M",
    }, headers=h)
    assert r.status_code == 201
    assert r.json()["data_chegada"] is not None


def test_abrir_condicao_invalida_400(client, usuario_comum, fases_seed, os_base):
    h = _headers(client, "comum", "senha123")
    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C",
        "condicao_chegada": "INEXISTENTE",
    }, headers=h)
    assert r.status_code == 400


def test_abrir_checklist_id_invalido_400(client, usuario_comum, fases_seed, os_base):
    h = _headers(client, "comum", "senha123")
    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C",
        "checklist": [1, 99],
    }, headers=h)
    assert r.status_code == 400
