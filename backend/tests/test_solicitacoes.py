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
