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
    tokens = client.post("/auth/login", json={"email": "admin@hs.com", "senha": "senha123"}).json()
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


def _ph(client):
    tok = client.post("/auth/login-portal", json={"documento": "11222333000144", "login": "cliente1", "senha": "portal123"}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _setup_informativo(db_session, cliente_id):
    from app.models import Cliente, Equipamento, EquipamentoCliente, Ordem
    hoje = date.today()
    eq = Equipamento(descricao="Bafômetro")
    outro = Cliente(nome="Outro Cli")
    db_session.add_all([eq, outro]); db_session.flush()
    os_cert = Ordem(cliente=cliente_id, fase=8, situacao="F", pdf_certificado="http://x/cert.pdf")
    db_session.add(os_cert); db_session.flush()
    db_session.add_all([
        EquipamentoCliente(cliente=cliente_id, equipamento=eq.id, serie="S-VEN", prox_calibragem=hoje - timedelta(days=5), ativo=True),
        EquipamentoCliente(cliente=cliente_id, equipamento=eq.id, serie="S-VND", prox_calibragem=hoje + timedelta(days=30), ativo=True),
        EquipamentoCliente(cliente=cliente_id, equipamento=eq.id, serie="S-OK", prox_calibragem=hoje + timedelta(days=200), ativo=True),
        EquipamentoCliente(cliente=cliente_id, equipamento=eq.id, serie="S-CERT", calib_cert="HF1", ult_calibragem=hoje, prox_calibragem=hoje + timedelta(days=300), ativo=True, os_atual=os_cert.id),
        EquipamentoCliente(cliente=outro.id, equipamento=eq.id, serie="OUTRO", prox_calibragem=hoje - timedelta(days=5), ativo=True),
        Ordem(cliente=cliente_id, fase=5, situacao="E"),
        Ordem(cliente=outro.id, fase=5, situacao="E"),
    ])
    db_session.commit()


def test_minha_frota(client, cliente_portal, fases_seed, db_session):
    _setup_informativo(db_session, cliente_portal.cliente)
    r = client.get("/portal/minha-frota", headers=_ph(client))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 4  # 4 ativos do cliente; o do "outro" não entra
    assert all(i["serie"] != "OUTRO" for i in body["items"])


def test_minha_frota_status_e_busca(client, cliente_portal, fases_seed, db_session):
    _setup_informativo(db_session, cliente_portal.cliente)
    r = client.get("/portal/minha-frota?status=vencido", headers=_ph(client))
    assert r.json()["total"] == 1 and r.json()["items"][0]["serie"] == "S-VEN"
    r2 = client.get("/portal/minha-frota?q=S-OK", headers=_ph(client))
    assert r2.json()["total"] == 1


def test_certificados(client, cliente_portal, fases_seed, db_session):
    _setup_informativo(db_session, cliente_portal.cliente)
    r = client.get("/portal/certificados", headers=_ph(client))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["calib_cert"] == "HF1"
    assert item["pdf"] == "http://x/cert.pdf"


def test_minhas_os(client, cliente_portal, fases_seed, db_session):
    _setup_informativo(db_session, cliente_portal.cliente)
    r = client.get("/portal/minhas-os", headers=_ph(client))
    assert r.status_code == 200
    assert r.json()["total"] == 2  # fase 8 (cert) + fase 5; não a do outro cliente


def test_minhas_os_em_andamento(client, cliente_portal, fases_seed, db_session):
    _setup_informativo(db_session, cliente_portal.cliente)
    r = client.get("/portal/minhas-os?em_andamento=true", headers=_ph(client))
    assert r.json()["total"] == 1  # só a fase 5


def test_portal_informativo_sem_token_401(client):
    assert client.get("/portal/minha-frota").status_code == 401
    assert client.get("/portal/certificados").status_code == 401
    assert client.get("/portal/minhas-os").status_code == 401
