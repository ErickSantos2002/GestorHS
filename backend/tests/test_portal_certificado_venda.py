from datetime import date


def _login_portal(client):
    # rota real: /auth/login-portal (ver backend/tests/test_portal.py:5)
    tok = client.post("/auth/login-portal", json={
        "documento": "11222333000144", "login": "cliente1", "senha": "portal123",
    }).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _aparelho_vendido(db_session, cliente_id):
    """Aparelho com certificado de venda e SEM OS — o caso da feature."""
    from app.models import Equipamento, EquipamentoCliente, CertificadoVenda
    eq = Equipamento(descricao="Mark X")
    db_session.add(eq); db_session.flush()
    ec = EquipamentoCliente(cliente=cliente_id, equipamento=eq.id, serie="S1",
                            calib_cert="V-001", ult_calibragem=date(2026, 7, 20),
                            prox_calibragem=date(2027, 7, 20))
    db_session.add(ec); db_session.flush()
    db_session.add(CertificadoVenda(equipamento_cliente=ec.id,
                                    html="<p>certificado de venda</p>", calib_cert="V-001"))
    db_session.commit(); db_session.refresh(ec)
    return ec


def test_aparelho_vendido_sem_os_aparece_com_venda_true(client, cliente_portal, db_session):
    ec = _aparelho_vendido(db_session, cliente_portal.cliente)
    h = _login_portal(client)
    r = client.get("/portal/certificados", headers=h)
    assert r.status_code == 200
    items = r.json()["items"]
    alvo = [i for i in items if i["equipamento_cliente"] == ec.id]
    assert len(alvo) == 1
    assert alvo[0]["os"] is None
    assert alvo[0]["venda"] is True


def test_cliente_baixa_o_certificado_de_venda(client, cliente_portal, db_session, monkeypatch):
    from app.api import portal
    monkeypatch.setattr(portal, "html_para_pdf", lambda html: b"%PDF-fake")
    ec = _aparelho_vendido(db_session, cliente_portal.cliente)
    h = _login_portal(client)
    r = client.get(f"/portal/certificado-venda/{ec.id}", headers=h)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"


def test_cliente_nao_baixa_certificado_de_outro_tenant(client, cliente_portal, db_session):
    """Isolamento pelo token: o id na URL nao pode dar acesso."""
    from app.models import Cliente
    outro = Cliente(nome="Outra Empresa", cgc="99888777000166")
    db_session.add(outro); db_session.flush()
    ec_alheio = _aparelho_vendido(db_session, outro.id)
    h = _login_portal(client)
    r = client.get(f"/portal/certificado-venda/{ec_alheio.id}", headers=h)
    assert r.status_code == 404


def test_sem_certificado_de_venda_404(client, cliente_portal, db_session):
    from app.models import Equipamento, EquipamentoCliente
    eq = Equipamento(descricao="Mark X")
    db_session.add(eq); db_session.flush()
    ec = EquipamentoCliente(cliente=cliente_portal.cliente, equipamento=eq.id, serie="S9")
    db_session.add(ec); db_session.commit(); db_session.refresh(ec)
    h = _login_portal(client)
    assert client.get(f"/portal/certificado-venda/{ec.id}", headers=h).status_code == 404
