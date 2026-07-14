def _ph(client):
    tok = client.post("/auth/login-portal", json={"documento": "11222333000144", "login": "cliente1", "senha": "portal123"}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _aparelho(db_session, cliente_id):
    from app.models import Equipamento, EquipamentoCliente
    eq = Equipamento(descricao="Bafômetro")
    db_session.add(eq); db_session.flush()
    ec = EquipamentoCliente(cliente=cliente_id, equipamento=eq.id, serie="S1", ativo=True)
    db_session.add(ec); db_session.commit(); db_session.refresh(ec)
    return ec


def test_solicitar_cria_pendente(client, cliente_portal, db_session):
    ec = _aparelho(db_session, cliente_portal.cliente)
    r = client.post("/portal/solicitar-recalibracao", json={"equipamento_cliente": ec.id}, headers=_ph(client))
    assert r.status_code == 201
    assert r.json()["status"] == "pendente"
    assert r.json()["equipamento_cliente"] == ec.id


def test_solicitar_duplicada_409(client, cliente_portal, db_session):
    ec = _aparelho(db_session, cliente_portal.cliente)
    h = _ph(client)
    assert client.post("/portal/solicitar-recalibracao", json={"equipamento_cliente": ec.id}, headers=h).status_code == 201
    assert client.post("/portal/solicitar-recalibracao", json={"equipamento_cliente": ec.id}, headers=h).status_code == 409


def test_solicitar_aparelho_de_outro_cliente_404(client, cliente_portal, db_session):
    from app.models import Cliente, Equipamento, EquipamentoCliente
    outro = Cliente(nome="Outro")
    eq = Equipamento(descricao="B")
    db_session.add_all([outro, eq]); db_session.flush()
    ec = EquipamentoCliente(cliente=outro.id, equipamento=eq.id, ativo=True)
    db_session.add(ec); db_session.commit(); db_session.refresh(ec)
    r = client.post("/portal/solicitar-recalibracao", json={"equipamento_cliente": ec.id}, headers=_ph(client))
    assert r.status_code == 404


def test_minhas_solicitacoes(client, cliente_portal, db_session):
    ec = _aparelho(db_session, cliente_portal.cliente)
    client.post("/portal/solicitar-recalibracao", json={"equipamento_cliente": ec.id}, headers=_ph(client))
    r = client.get("/portal/minhas-solicitacoes", headers=_ph(client))
    assert r.status_code == 200
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["status"] == "pendente"


def test_minhas_solicitacoes_sem_token_401(client):
    assert client.get("/portal/minhas-solicitacoes").status_code == 401


def _hdr(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _solic(db_session, cliente_portal):
    from app.models import Equipamento, EquipamentoCliente, Solicitacao
    from app.api.ordens_acoes import agora
    eq = Equipamento(descricao="Bafômetro")
    db_session.add(eq); db_session.flush()
    ec = EquipamentoCliente(cliente=cliente_portal.cliente, equipamento=eq.id, ativo=True)
    db_session.add(ec); db_session.flush()
    s = Solicitacao(cliente=cliente_portal.cliente, equipamento_cliente=ec.id, status="pendente", data_solicitacao=agora())
    db_session.add(s); db_session.commit(); db_session.refresh(s)
    return s


def test_listar_solicitacoes_interno(client, usuario_comum, cliente_portal, db_session):
    _solic(db_session, cliente_portal)
    r = client.get("/solicitacoes", headers=_hdr(client, "comum@hs.com", "senha123"))
    assert r.status_code == 200
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["cliente_nome"] == "Cliente Teste"


def test_atender_comercial(client, usuario_comercial, cliente_portal, db_session):
    s = _solic(db_session, cliente_portal)
    r = client.post(f"/solicitacoes/{s.id}/atender", headers=_hdr(client, "comercial@hs.com", "senha123"))
    assert r.status_code == 200
    assert r.json()["status"] == "atendida"
    assert r.json()["atendido_por_nome"] is not None


def test_atender_admin(client, usuario_admin, cliente_portal, db_session):
    s = _solic(db_session, cliente_portal)
    assert client.post(f"/solicitacoes/{s.id}/atender", headers=_hdr(client, "admin@hs.com", "senha123")).json()["status"] == "atendida"


def test_atender_403(client, usuario_lab, cliente_portal, db_session):
    s = _solic(db_session, cliente_portal)
    assert client.post(f"/solicitacoes/{s.id}/atender", headers=_hdr(client, "lab@hs.com", "senha123")).status_code == 403


def test_reatender_409(client, usuario_comercial, cliente_portal, db_session):
    s = _solic(db_session, cliente_portal)
    h = _hdr(client, "comercial@hs.com", "senha123")
    client.post(f"/solicitacoes/{s.id}/atender", headers=h)
    assert client.post(f"/solicitacoes/{s.id}/atender", headers=h).status_code == 409


def test_atender_404(client, usuario_comercial, db_session):
    assert client.post("/solicitacoes/99999/atender", headers=_hdr(client, "comercial@hs.com", "senha123")).status_code == 404
