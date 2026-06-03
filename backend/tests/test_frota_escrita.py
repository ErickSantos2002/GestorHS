def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _base(db_session):
    from app.models import Cliente, Equipamento
    c = Cliente(nome="Cli")
    e = Equipamento(descricao="Eq")
    db_session.add_all([c, e])
    db_session.commit()
    return c.id, e.id


def test_frota_write_exige_admin(client, usuario_admin, usuario_comum, db_session):
    cid, eid = _base(db_session)
    hc = _headers(client, "comum", "senha123")
    assert client.post("/equipamentos-cliente", json={"cliente": cid, "equipamento": eid}, headers=hc).status_code == 403
    assert client.patch("/equipamentos-cliente/1", json={"serie": "X"}, headers=hc).status_code == 403
    assert client.delete("/equipamentos-cliente/1", headers=hc).status_code == 403


def test_frota_crud(client, usuario_admin, db_session):
    cid, eid = _base(db_session)
    h = _headers(client, "admin", "senha123")
    criado = client.post("/equipamentos-cliente", json={"cliente": cid, "equipamento": eid, "serie": "S1", "status": "A"}, headers=h)
    assert criado.status_code == 201
    iid = criado.json()["id"]
    assert criado.json()["cliente"] == cid
    assert client.patch(f"/equipamentos-cliente/{iid}", json={"patrimonio": "PAT-9"}, headers=h).json()["patrimonio"] == "PAT-9"
    assert client.delete(f"/equipamentos-cliente/{iid}", headers=h).status_code == 204
    assert client.get(f"/equipamentos-cliente/{iid}", headers=h).status_code == 404


def test_patch_nao_altera_campos_espelho(client, usuario_admin, db_session):
    from app.models import EquipamentoCliente
    cid, eid = _base(db_session)
    ec = EquipamentoCliente(cliente=cid, equipamento=eid, calib_cert="ORIG", os_atual=7)
    db_session.add(ec)
    db_session.commit()
    h = _headers(client, "admin", "senha123")
    r = client.patch(f"/equipamentos-cliente/{ec.id}", json={"serie": "NOVA", "calib_cert": "HACK", "os_atual": 99}, headers=h)
    assert r.status_code == 200
    assert r.json()["serie"] == "NOVA"
    assert r.json()["calib_cert"] == "ORIG"
    assert r.json()["os_atual"] == 7


def test_excluir_frota_em_uso_409(client, usuario_admin, db_session):
    from app.models import EquipamentoCliente, HistoricoEquipamento
    cid, eid = _base(db_session)
    ec = EquipamentoCliente(cliente=cid, equipamento=eid)
    db_session.add(ec)
    db_session.flush()
    db_session.add(HistoricoEquipamento(equipamento_cliente=ec.id, saida=1))
    db_session.commit()
    r = client.delete(f"/equipamentos-cliente/{ec.id}", headers=_headers(client, "admin", "senha123"))
    assert r.status_code == 409
