from app.core import certificado_link as cl


def _os_com_cert(db_session, fases_seed):
    from app.models import Cliente, Equipamento, EquipamentoCliente, Ordem, OSCertificado
    cli = Cliente(nome="Cliente Pub")
    eq = Equipamento(descricao="Bafômetro")
    db_session.add_all([cli, eq]); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie="SER-PUB", patrimonio="PAT-PUB")
    db_session.add(ec); db_session.flush()
    o = Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=8, tipo_servico="C", situacao="F")
    db_session.add(o); db_session.flush()
    db_session.add(OSCertificado(os=o.id, tipo="C", html="<html>cert</html>"))
    db_session.commit()
    return o.id


def test_download_ok_com_token_valido(client, db_session, fases_seed, monkeypatch):
    from app.api import publico
    monkeypatch.setattr(publico, "html_para_pdf", lambda html: b"%PDF-fake")
    oid = _os_com_cert(db_session, fases_seed)
    tok = cl.assinar(oid, "C")
    r = client.get(f"/publico/certificado/{oid}/calibracao?t={tok}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content == b"%PDF-fake"


def test_403_token_errado(client, db_session, fases_seed):
    oid = _os_com_cert(db_session, fases_seed)
    r = client.get(f"/publico/certificado/{oid}/calibracao?t=errado")
    assert r.status_code == 403


def test_404_tipo_invalido(client, db_session, fases_seed):
    oid = _os_com_cert(db_session, fases_seed)
    tok = cl.assinar(oid, "C")
    r = client.get(f"/publico/certificado/{oid}/xpto?t={tok}")
    assert r.status_code == 404


def test_404_certificado_inexistente(client, db_session, fases_seed):
    from app.models import Cliente, Equipamento, EquipamentoCliente, Ordem
    cli = Cliente(nome="Cliente Pub")
    eq = Equipamento(descricao="Bafômetro")
    db_session.add_all([cli, eq]); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie="SER-PUB2", patrimonio="PAT-PUB2")
    db_session.add(ec); db_session.flush()
    o = Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=8, tipo_servico="C", situacao="F")
    db_session.add(o); db_session.commit()
    tok = cl.assinar(o.id, "M")
    r = client.get(f"/publico/certificado/{o.id}/manutencao?t={tok}")
    assert r.status_code == 404


def test_nao_exige_login(client, db_session, fases_seed, monkeypatch):
    from app.api import publico
    monkeypatch.setattr(publico, "html_para_pdf", lambda html: b"%PDF-fake")
    oid = _os_com_cert(db_session, fases_seed)
    tok = cl.assinar(oid, "C")
    # sem header Authorization
    assert client.get(f"/publico/certificado/{oid}/calibracao?t={tok}").status_code == 200
