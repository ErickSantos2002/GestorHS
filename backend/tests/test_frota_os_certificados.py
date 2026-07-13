def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _seed_fases(db_session):
    from app.models import Fase, Funcao
    for fase_id, descricao in [(5, "Laboratório"), (8, "Finalizada")]:
        if db_session.query(Fase).filter(Fase.id == fase_id).first() is None:
            f = db_session.query(Funcao).filter(Funcao.descricao == descricao).first()
            if f is None:
                f = Funcao(descricao=descricao)
                db_session.add(f)
                db_session.flush()
            db_session.add(Fase(id=fase_id, descricao=descricao, cor="000000", funcao_responsavel=f.id))
    db_session.flush()


def _aparelho_com_os(db_session):
    from app.models import Cliente, Equipamento, EquipamentoCliente, Ordem, OSCertificado
    _seed_fases(db_session)
    cli = Cliente(nome="ACME"); eq = Equipamento(descricao="Mark X")
    db_session.add_all([cli, eq]); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie="S1")
    outro = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie="S2")
    db_session.add_all([ec, outro]); db_session.flush()
    o1 = Ordem(cliente=cli.id, equipamento_cliente=ec.id, situacao="E", tipo_servico="C", fase=5)
    o2 = Ordem(cliente=cli.id, equipamento_cliente=ec.id, situacao="F", tipo_servico="C", fase=8)
    o_outro = Ordem(cliente=cli.id, equipamento_cliente=outro.id, situacao="E", tipo_servico="C", fase=5)
    db_session.add_all([o1, o2, o_outro]); db_session.flush()
    db_session.add(OSCertificado(os=o1.id, tipo="C", html="<p>x</p>"))
    db_session.commit()
    return ec.id, outro.id, o1.id, o2.id


def test_ordens_do_aparelho(client, usuario_admin, db_session):
    ec_id, _outro, o1, o2 = _aparelho_com_os(db_session)
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.get(f"/equipamentos-cliente/{ec_id}/ordens", headers=h)
    assert r.status_code == 200
    ids = [o["id"] for o in r.json()]
    assert ids == sorted(ids, reverse=True)
    assert o1 in ids and o2 in ids
    assert len(ids) == 2


def test_certificados_do_aparelho(client, usuario_admin, db_session):
    ec_id, _outro, o1, _o2 = _aparelho_com_os(db_session)
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.get(f"/equipamentos-cliente/{ec_id}/certificados", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["os"] == o1 and body[0]["tipo"] == "C"
    assert "data_geracao" in body[0]


def test_ordens_aparelho_inexistente_404(client, usuario_admin):
    h = _headers(client, "admin@hs.com", "senha123")
    assert client.get("/equipamentos-cliente/99999/ordens", headers=h).status_code == 404
    assert client.get("/equipamentos-cliente/99999/certificados", headers=h).status_code == 404
