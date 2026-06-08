def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _seed_fase5_se_necessario(db_session):
    from app.models import Fase, Funcao
    if db_session.query(Fase).filter(Fase.id == 5).first() is None:
        f = db_session.query(Funcao).filter(Funcao.descricao == "Laboratório").first()
        if f is None:
            f = Funcao(descricao="Laboratório")
            db_session.add(f); db_session.flush()
        db_session.add(Fase(id=5, descricao="Laboratório", cor="6366f1", funcao_responsavel=f.id))
        db_session.flush()


def _os_com_modelo(client, db_session, hadmin, tipos=("C",), tipo_servico="C"):
    from app.models import Cliente, Equipamento, EquipamentoCliente, Ordem, CertificadoModelo
    _seed_fase5_se_necessario(db_session)
    cat = Equipamento(descricao="Mark X"); db_session.add(cat); db_session.flush()
    cli = Cliente(nome="ACME"); db_session.add(cli); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=cat.id, serie="S1"); db_session.add(ec); db_session.flush()
    o = Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=5, situacao="E",
              tipo_servico=tipo_servico, calib_cert="C-1", calib_temp="25")
    db_session.add(o)
    for t in tipos:
        db_session.add(CertificadoModelo(equipamento=cat.id, tipo=t, texto=f"<p>[nomecli]-[serie]-{t}</p>"))
    db_session.commit(); db_session.refresh(o)
    return o.id


def test_gerar_calibracao(client, usuario_admin, db_session):
    h = _headers(client, "admin", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C",), tipo_servico="C")
    r = client.post(f"/ordens/{oid}/gerar-certificado", headers=h)
    assert r.status_code == 200
    tipos = {c["tipo"]: c for c in r.json()}
    assert "C" in tipos
    assert "ACME-S1-C" in tipos["C"]["html"]
    lista = client.get(f"/ordens/{oid}/certificados", headers=h).json()
    assert any(c["tipo"] == "C" for c in lista)


def test_gerar_manutencao_quando_servico_A(client, usuario_admin, db_session):
    h = _headers(client, "admin", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C", "M"), tipo_servico="A")
    r = client.post(f"/ordens/{oid}/gerar-certificado", headers=h).json()
    assert {c["tipo"] for c in r} == {"C", "M"}


def test_nao_gera_manutencao_quando_servico_C(client, usuario_admin, db_session):
    h = _headers(client, "admin", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C", "M"), tipo_servico="C")
    r = client.post(f"/ordens/{oid}/gerar-certificado", headers=h).json()
    assert {c["tipo"] for c in r} == {"C"}


def test_sem_modelo_nao_gera_mas_nao_quebra(client, usuario_admin, db_session):
    from app.models import Cliente, Equipamento, EquipamentoCliente, Ordem
    h = _headers(client, "admin", "senha123")
    _seed_fase5_se_necessario(db_session)
    cat = Equipamento(descricao="X"); db_session.add(cat); db_session.flush()
    cli = Cliente(nome="C"); db_session.add(cli); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=cat.id); db_session.add(ec); db_session.flush()
    o = Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=5, situacao="E", tipo_servico="C")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    r = client.post(f"/ordens/{o.id}/gerar-certificado", headers=h)
    assert r.status_code == 200
    assert r.json() == []


def test_regerar_atualiza_nao_duplica(client, usuario_admin, db_session):
    h = _headers(client, "admin", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C",), tipo_servico="C")
    client.post(f"/ordens/{oid}/gerar-certificado", headers=h)
    client.post(f"/ordens/{oid}/gerar-certificado", headers=h)
    lista = client.get(f"/ordens/{oid}/certificados", headers=h).json()
    assert len([c for c in lista if c["tipo"] == "C"]) == 1


def test_gerar_exige_lab_ou_admin(client, usuario_admin, usuario_comercial, db_session):
    h = _headers(client, "comercial", "senha123")
    oid = _os_com_modelo(client, db_session, _headers(client, "admin", "senha123"), tipos=("C",))
    assert client.post(f"/ordens/{oid}/gerar-certificado", headers=h).status_code == 403


def test_gerar_os_inexistente_404(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    assert client.post("/ordens/99999/gerar-certificado", headers=h).status_code == 404
