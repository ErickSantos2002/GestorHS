def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _ordem(db_session, cliente, equipamento_cliente, fase, **kw):
    from app.models import Ordem
    o = Ordem(cliente=cliente, equipamento_cliente=equipamento_cliente, fase=fase,
              situacao=kw.pop("situacao", "E"), **kw)
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    return o


def test_lista_paginada_e_total(client, usuario_admin, fases_seed, os_base, db_session):
    for fase in (4, 5, 6, 8):
        _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], fase)
    h = _headers(client, "admin", "senha123")
    r = client.get("/ordens?limit=2", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 4
    assert len(body["items"]) == 2
    # ordem id desc
    assert body["items"][0]["id"] > body["items"][1]["id"]


def test_lista_filtra_por_fase(client, usuario_admin, fases_seed, os_base, db_session):
    _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 5)
    _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 8)
    h = _headers(client, "admin", "senha123")
    r = client.get("/ordens?fase=5", headers=h)
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["fase"] == 5
    assert r.json()["items"][0]["fase_descricao"] == "Laboratório"


def test_lista_busca_por_id_numerico(client, usuario_admin, fases_seed, os_base, db_session):
    o = _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 4)
    h = _headers(client, "admin", "senha123")
    r = client.get(f"/ordens?q={o.id}", headers=h)
    assert r.json()["total"] == 1 and r.json()["items"][0]["id"] == o.id


def test_lista_busca_por_nome_cliente(client, usuario_admin, fases_seed, os_base, db_session):
    _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 4)
    h = _headers(client, "admin", "senha123")
    r = client.get("/ordens?q=Cliente OS", headers=h)
    assert r.json()["total"] == 1


def test_quadro_so_ativas_agrupado(client, usuario_admin, fases_seed, os_base, db_session):
    _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 4)
    _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 6)
    _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 8)  # finalizada, fora
    h = _headers(client, "admin", "senha123")
    colunas = client.get("/ordens/quadro", headers=h).json()
    assert [c["fase"] for c in colunas] == [4, 5, 6, 7]
    por_fase = {c["fase"]: len(c["ordens"]) for c in colunas}
    assert por_fase == {4: 1, 5: 0, 6: 1, 7: 0}


def test_detalhe_e_404(client, usuario_admin, fases_seed, os_base, db_session):
    o = _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 4, tipo_servico="C")
    h = _headers(client, "admin", "senha123")
    r = client.get(f"/ordens/{o.id}", headers=h)
    assert r.status_code == 200
    assert r.json()["cliente_nome"] == "Cliente OS"
    assert r.json()["equipamento_serie"] == "SER-1"
    assert client.get("/ordens/9999", headers=h).status_code == 404


def test_logs_da_os(client, usuario_admin, fases_seed, os_base, db_session):
    from app.models import LogOS
    o = _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 4)
    db_session.add(LogOS(os=o.id, usuario=None, texto="aberta")); db_session.commit()
    h = _headers(client, "admin", "senha123")
    r = client.get(f"/ordens/{o.id}/logs", headers=h)
    assert r.status_code == 200 and len(r.json()) == 1 and r.json()[0]["texto"] == "aberta"
    assert client.get("/ordens/9999/logs", headers=h).status_code == 404


def test_leitura_liberada_a_qualquer_interno(client, usuario_admin, usuario_comum, fases_seed, os_base, db_session):
    _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 4)
    h = _headers(client, "comum", "senha123")
    assert client.get("/ordens", headers=h).status_code == 200
    assert client.get("/ordens/quadro", headers=h).status_code == 200
