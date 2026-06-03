def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def test_abrir_os_sucesso(client, usuario_comum, fases_seed, os_base, db_session):
    # usuario_comum = Expedição
    h = _headers(client, "comum", "senha123")
    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C",
        "condicao_chegada": "riscado", "acessorios": "case",
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
