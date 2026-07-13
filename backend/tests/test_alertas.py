from datetime import date, timedelta


def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _setup(db_session):
    from app.models import Cliente, Equipamento, EquipamentoCliente
    hoje = date.today()
    cliA = Cliente(nome="Alfa Ltda")
    cliB = Cliente(nome="Beta SA")
    cliC = Cliente(nome="Gama ME")
    eq = Equipamento(descricao="Bafômetro")
    db_session.add_all([cliA, cliB, cliC, eq])
    db_session.flush()

    def ec(cli, prox, ativo=True):
        return EquipamentoCliente(cliente=cli, equipamento=eq.id, prox_calibragem=prox, ativo=ativo)

    db_session.add_all([
        ec(cliA.id, hoje - timedelta(days=10)),            # vencido
        ec(cliA.id, hoje - timedelta(days=5)),             # vencido
        ec(cliA.id, hoje + timedelta(days=30)),            # vencendo
        ec(cliA.id, hoje + timedelta(days=200)),           # em_dia (ignorado)
        ec(cliA.id, hoje - timedelta(days=1), ativo=False),# inativo (ignorado)
        ec(cliB.id, hoje - timedelta(days=2)),             # vencido
        ec(cliC.id, hoje + timedelta(days=300)),           # em_dia só -> C não aparece
    ])
    db_session.commit()
    return {"A": cliA.id, "B": cliB.id, "C": cliC.id}


def test_lista_agrupa_e_ordena(client, usuario_comum, db_session):
    ids = _setup(db_session)
    r = client.get("/alertas", headers=_headers(client, "comum@hs.com", "senha123"))
    assert r.status_code == 200
    body = r.json()
    clientes = [i["cliente"] for i in body["items"]]
    assert ids["C"] not in clientes
    assert clientes[0] == ids["A"] and clientes[1] == ids["B"]  # A (2 vencidos) antes de B
    a = body["items"][0]
    assert a["vencidos"] == 2 and a["vencendo"] == 1
    assert body["total"] == 2


def test_busca_por_cliente(client, usuario_comum, db_session):
    ids = _setup(db_session)
    r = client.get("/alertas?q=Beta", headers=_headers(client, "comum@hs.com", "senha123"))
    assert r.json()["total"] == 1 and r.json()["items"][0]["cliente"] == ids["B"]


def test_ocultar_recentes(client, usuario_comum, db_session):
    from app.models import EquipamentoCliente
    from app.api.ordens_acoes import agora
    ids = _setup(db_session)
    for ec in db_session.query(EquipamentoCliente).filter(EquipamentoCliente.cliente == ids["A"]).all():
        ec.ult_aviso = agora()
    db_session.commit()
    r = client.get("/alertas?ocultar_recentes=true", headers=_headers(client, "comum@hs.com", "senha123"))
    clientes = [i["cliente"] for i in r.json()["items"]]
    assert ids["A"] not in clientes
    assert ids["B"] in clientes


def test_registrar_contato_comercial(client, usuario_comercial, db_session):
    ids = _setup(db_session)
    r = client.post(f"/alertas/{ids['A']}/contato", headers=_headers(client, "comercial@hs.com", "senha123"))
    assert r.status_code == 200
    assert r.json()["atualizados"] == 3   # 2 vencidos + 1 vencendo (não em_dia/inativo)
    assert r.json()["ult_contato"] is not None


def test_registrar_contato_admin(client, usuario_admin, db_session):
    ids = _setup(db_session)
    r = client.post(f"/alertas/{ids['B']}/contato", headers=_headers(client, "admin@hs.com", "senha123"))
    assert r.json()["atualizados"] == 1


def test_registrar_contato_403(client, usuario_lab, db_session):
    ids = _setup(db_session)
    r = client.post(f"/alertas/{ids['A']}/contato", headers=_headers(client, "lab@hs.com", "senha123"))
    assert r.status_code == 403


def test_registrar_contato_404(client, usuario_comercial, db_session):
    r = client.post("/alertas/99999/contato", headers=_headers(client, "comercial@hs.com", "senha123"))
    assert r.status_code == 404


def test_contato_reflete_em_ult_contato(client, usuario_comercial, db_session):
    ids = _setup(db_session)
    h = _headers(client, "comercial@hs.com", "senha123")
    client.post(f"/alertas/{ids['A']}/contato", headers=h)
    item = next(i for i in client.get("/alertas", headers=h).json()["items"] if i["cliente"] == ids["A"])
    assert item["ult_contato"] is not None
