from datetime import date, timedelta


def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _base(db_session):
    from app.models import Cliente, Equipamento
    c = Cliente(nome="Cliente Frota")
    e = Equipamento(descricao="Alcotest 6820")
    db_session.add_all([c, e])
    db_session.commit()
    return c.id, e.id


def test_frota_read_liberada_a_interno(client, usuario_comum):
    r = client.get("/equipamentos-cliente", headers=_headers(client, "comum@hs.com", "senha123"))
    assert r.status_code == 200
    assert r.json() == {"items": [], "total": 0}


def test_frota_filtro_por_status(client, usuario_admin, db_session):
    from app.models import EquipamentoCliente
    cid, eid = _base(db_session)
    hoje = date.today()
    db_session.add_all([
        EquipamentoCliente(cliente=cid, equipamento=eid, serie="VENC", prox_calibragem=hoje - timedelta(days=1)),
        EquipamentoCliente(cliente=cid, equipamento=eid, serie="VGND", prox_calibragem=hoje + timedelta(days=10)),
        EquipamentoCliente(cliente=cid, equipamento=eid, serie="EMDIA", prox_calibragem=hoje + timedelta(days=200)),
        EquipamentoCliente(cliente=cid, equipamento=eid, serie="SEMD", prox_calibragem=None),
    ])
    db_session.commit()
    h = _headers(client, "admin@hs.com", "senha123")
    assert client.get("/equipamentos-cliente", headers=h).json()["total"] == 4
    assert client.get("/equipamentos-cliente?status=vencido", headers=h).json()["total"] == 1
    assert client.get("/equipamentos-cliente?status=vencendo", headers=h).json()["total"] == 1
    assert client.get("/equipamentos-cliente?status=em_dia", headers=h).json()["total"] == 1
    sem = client.get("/equipamentos-cliente?status=sem_data", headers=h).json()
    assert sem["total"] == 1 and sem["items"][0]["status_calibracao"] == "sem_data"


def test_frota_filtro_cliente_e_busca(client, usuario_admin, db_session):
    from app.models import Cliente, EquipamentoCliente
    cid, eid = _base(db_session)
    outro = Cliente(nome="Outro")
    db_session.add(outro)
    db_session.commit()
    db_session.add_all([
        EquipamentoCliente(cliente=cid, equipamento=eid, serie="AAA111", patrimonio="P1"),
        EquipamentoCliente(cliente=outro.id, equipamento=eid, serie="BBB222", patrimonio="P2"),
    ])
    db_session.commit()
    h = _headers(client, "admin@hs.com", "senha123")
    assert client.get(f"/equipamentos-cliente?cliente={cid}", headers=h).json()["total"] == 1
    assert client.get("/equipamentos-cliente?q=BBB", headers=h).json()["total"] == 1
    item = client.get(f"/equipamentos-cliente?cliente={cid}", headers=h).json()["items"][0]
    assert item["cliente_nome"] == "Cliente Frota"
    assert item["equipamento_descricao"] == "Alcotest 6820"


def test_frota_detalhe_e_404(client, usuario_admin, db_session):
    from app.models import EquipamentoCliente
    cid, eid = _base(db_session)
    ec = EquipamentoCliente(cliente=cid, equipamento=eid, serie="X1", calib_cert="CERT-1")
    db_session.add(ec)
    db_session.commit()
    h = _headers(client, "admin@hs.com", "senha123")
    d = client.get(f"/equipamentos-cliente/{ec.id}", headers=h)
    assert d.status_code == 200
    assert d.json()["calib_cert"] == "CERT-1"
    assert client.get("/equipamentos-cliente/99999", headers=h).status_code == 404


def test_frota_historico(client, usuario_admin, db_session):
    from app.models import EquipamentoCliente, HistoricoEquipamento
    cid, eid = _base(db_session)
    ec = EquipamentoCliente(cliente=cid, equipamento=eid)
    db_session.add(ec)
    db_session.flush()
    db_session.add(HistoricoEquipamento(equipamento_cliente=ec.id, datamov=date.today(), saida=1, entrada=2))
    db_session.commit()
    h = _headers(client, "admin@hs.com", "senha123")
    hist = client.get(f"/equipamentos-cliente/{ec.id}/historico", headers=h).json()
    assert len(hist) == 1 and hist[0]["saida"] == 1
    assert client.get("/equipamentos-cliente/99999/historico", headers=h).status_code == 404


def test_frota_nao_expoe_mais_o_campo_status(client, usuario_admin, db_session):
    """O campo `status` (A/I/M) era morto — nenhuma regra o lia — e saiu da API.
    `status_calibracao`, que e' outra coisa, continua."""
    from app.models import Cliente, Equipamento, EquipamentoCliente
    cli = Cliente(nome="Cliente Status")
    eq = Equipamento(descricao="Bafometro")
    db_session.add_all([cli, eq]); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie="S-ST")
    db_session.add(ec); db_session.commit(); db_session.refresh(ec)
    tok = client.post("/auth/login", json={"email": "admin@hs.com", "senha": "senha123"}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}

    lista = client.get("/equipamentos-cliente", headers=h)
    assert lista.status_code == 200
    item = lista.json()["items"][0]
    assert "status" not in item
    assert "status_calibracao" in item

    detalhe = client.get(f"/equipamentos-cliente/{ec.id}", headers=h)
    assert detalhe.status_code == 200
    assert "status" not in detalhe.json()
    assert "status_calibracao" in detalhe.json()


def _dois_aparelhos(db):
    """Um ativo e um inativo, do mesmo cliente."""
    from app.models import Cliente, Equipamento, EquipamentoCliente
    cli = Cliente(nome="Cliente Ativo/Inativo")
    eq = Equipamento(descricao="Bafometro")
    db.add_all([cli, eq]); db.flush()
    ativo = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie="S-ATIVO", ativo=True)
    inativo = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie="S-INATIVO", ativo=False)
    db.add_all([ativo, inativo]); db.commit()
    return cli.id


def test_frota_filtro_ativo_true(client, usuario_admin, db_session):
    _dois_aparelhos(db_session)
    tok = client.post("/auth/login", json={"email": "admin@hs.com", "senha": "senha123"}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    r = client.get("/equipamentos-cliente?ativo=true", headers=h)
    assert r.status_code == 200
    series = [i["serie"] for i in r.json()["items"]]
    assert series == ["S-ATIVO"]


def test_frota_filtro_ativo_false(client, usuario_admin, db_session):
    _dois_aparelhos(db_session)
    tok = client.post("/auth/login", json={"email": "admin@hs.com", "senha": "senha123"}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    r = client.get("/equipamentos-cliente?ativo=false", headers=h)
    assert r.status_code == 200
    series = [i["serie"] for i in r.json()["items"]]
    assert series == ["S-INATIVO"]


def test_frota_sem_filtro_ativo_devolve_os_dois(client, usuario_admin, db_session):
    """Compatibilidade: sem o parametro a lista continua trazendo tudo, como antes."""
    _dois_aparelhos(db_session)
    tok = client.post("/auth/login", json={"email": "admin@hs.com", "senha": "senha123"}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    r = client.get("/equipamentos-cliente", headers=h)
    assert r.status_code == 200
    assert r.json()["total"] == 2


def test_frota_filtro_ativo_combina_com_filtro_de_calibracao(client, usuario_admin, db_session):
    """Os dois filtros sao independentes e se somam."""
    from datetime import date, timedelta
    from app.models import Cliente, Equipamento, EquipamentoCliente
    cli = Cliente(nome="Cliente Combinado")
    eq = Equipamento(descricao="Bafometro")
    db_session.add_all([cli, eq]); db_session.flush()
    ontem = date.today() - timedelta(days=1)
    db_session.add_all([
        EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie="S-AT-VENC",
                           ativo=True, prox_calibragem=ontem),
        EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie="S-IN-VENC",
                           ativo=False, prox_calibragem=ontem),
    ])
    db_session.commit()
    tok = client.post("/auth/login", json={"email": "admin@hs.com", "senha": "senha123"}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    r = client.get("/equipamentos-cliente?ativo=true&status=vencido", headers=h)
    assert r.status_code == 200
    assert [i["serie"] for i in r.json()["items"]] == ["S-AT-VENC"]
