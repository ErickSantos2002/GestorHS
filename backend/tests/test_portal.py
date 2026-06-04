from datetime import date, timedelta


def _portal_headers(client):
    tok = client.post("/auth/login-portal", json={"documento": "11222333000144", "login": "cliente1", "senha": "portal123"}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def test_portal_me(client, cliente_portal):
    r = client.get("/portal/me", headers=_portal_headers(client))
    assert r.status_code == 200
    body = r.json()
    assert body["login"] == "cliente1"
    assert body["cliente"] == cliente_portal.cliente
    assert body["cliente_nome"] == "Cliente Teste"


def test_portal_me_sem_token_401(client):
    assert client.get("/portal/me").status_code == 401


def test_portal_me_token_de_usuario_401(client, usuario_admin):
    tokens = client.post("/auth/login", json={"login": "admin", "senha": "senha123"}).json()
    r = client.get("/portal/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert r.status_code == 401


def test_portal_resumo_escopado(client, cliente_portal, db_session, fases_seed):
    from app.models import Cliente, Equipamento, EquipamentoCliente, Ordem
    hoje = date.today()
    eq = Equipamento(descricao="Baf")
    outro = Cliente(nome="Outro")
    db_session.add_all([eq, outro]); db_session.flush()
    db_session.add_all([
        EquipamentoCliente(cliente=cliente_portal.cliente, equipamento=eq.id, prox_calibragem=hoje - timedelta(days=5), ativo=True),  # vencido
        EquipamentoCliente(cliente=cliente_portal.cliente, equipamento=eq.id, prox_calibragem=hoje + timedelta(days=200), ativo=True),  # em dia
        EquipamentoCliente(cliente=outro.id, equipamento=eq.id, prox_calibragem=hoje - timedelta(days=5), ativo=True),  # de outro cliente
        Ordem(cliente=cliente_portal.cliente, fase=5, situacao="E"),       # OS em andamento
        Ordem(cliente=cliente_portal.cliente, fase=8, situacao="F"),       # finalizada (não conta)
        Ordem(cliente=outro.id, fase=5, situacao="E"),                     # de outro cliente
    ])
    db_session.commit()
    r = client.get("/portal/resumo", headers=_portal_headers(client))
    assert r.status_code == 200
    body = r.json()
    assert body["aparelhos"] == 2
    assert body["vencidos"] == 1
    assert body["os_andamento"] == 1
