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


def test_quadro_inclui_finalizada_agrupado(client, usuario_admin, fases_seed, os_base, db_session):
    _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 4)
    _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 6)
    _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 8)
    h = _headers(client, "admin", "senha123")
    colunas = client.get("/ordens/quadro", headers=h).json()
    assert [c["fase"] for c in colunas] == [4, 5, 6, 10, 7, 8]
    por_fase = {c["fase"]: len(c["ordens"]) for c in colunas}
    assert por_fase == {4: 1, 5: 0, 6: 1, 10: 0, 7: 0, 8: 1}
    por_total = {c["fase"]: c["total"] for c in colunas}
    assert por_total == {4: 1, 5: 0, 6: 1, 10: 0, 7: 0, 8: 1}
    col8 = next(c for c in colunas if c["fase"] == 8)
    assert col8["descricao"] == "Finalizada"


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


def test_detalhe_traz_garantias_derivando_manutencao(
    client, usuario_admin, fases_seed, os_base, db_session
):
    from datetime import date, datetime, timezone
    from app.models import EquipamentoCliente

    # aparelho com compra antiga (fora) e calibracao recente (em garantia)
    ec = db_session.query(EquipamentoCliente).get(os_base["equipamento_cliente"])
    ec.datacompra = date(2010, 1, 1)
    ec.ult_calibragem = date.today()
    db_session.commit()

    # OS de manutencao FINALIZADA recente -> vira a ultima manutencao
    _ordem(
        db_session, os_base["cliente"], os_base["equipamento_cliente"], 8,
        tipo_servico="M",
        data_calibracao=datetime.now(timezone.utc),
    )
    # OS atual (em andamento) que estamos consultando
    o = _ordem(
        db_session, os_base["cliente"], os_base["equipamento_cliente"], 5,
        tipo_servico="C",
    )

    h = _headers(client, "admin", "senha123")
    g = client.get(f"/ordens/{o.id}", headers=h).json()["garantias"]
    assert g is not None
    assert g["em_garantia"] is True
    assert g["calibracao"]["estado"] == "em_garantia"
    assert g["manutencao"]["estado"] == "em_garantia"   # derivada da OS 'M'
    assert g["compra"]["estado"] == "fora"


def test_detalhe_sem_aparelho_garantias_null(
    client, usuario_admin, fases_seed, db_session
):
    from app.models import Cliente
    cli = Cliente(nome="Sem aparelho")
    db_session.add(cli); db_session.commit(); db_session.refresh(cli)
    o = _ordem(db_session, cli.id, None, 4, tipo_servico="C")
    h = _headers(client, "admin", "senha123")
    assert client.get(f"/ordens/{o.id}", headers=h).json()["garantias"] is None


def test_quadro_finalizada_capada_com_total_real(
    client, usuario_admin, fases_seed, os_base, db_session, monkeypatch
):
    import app.api.ordens as ordens_api
    monkeypatch.setattr(ordens_api, "LIMITE_FINALIZADAS_QUADRO", 2)
    for _ in range(3):
        _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 8)
    _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 5)  # ativa
    h = _headers(client, "admin", "senha123")
    colunas = client.get("/ordens/quadro", headers=h).json()
    col8 = next(c for c in colunas if c["fase"] == 8)
    assert col8["total"] == 3
    assert len(col8["ordens"]) == 2  # capada
    col5 = next(c for c in colunas if c["fase"] == 5)
    assert col5["total"] == 1
    assert len(col5["ordens"]) == 1  # ativas nao capam


def test_quadro_finalizada_respeita_filtro_cliente(
    client, usuario_admin, fases_seed, os_base, db_session
):
    from app.models import Cliente
    outro = Cliente(nome="Outro Cliente")
    db_session.add(outro); db_session.commit(); db_session.refresh(outro)
    _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 8)
    _ordem(db_session, outro.id, None, 8)
    h = _headers(client, "admin", "senha123")
    colunas = client.get(
        f"/ordens/quadro?cliente={os_base['cliente']}", headers=h
    ).json()
    col8 = next(c for c in colunas if c["fase"] == 8)
    assert col8["total"] == 1
    assert len(col8["ordens"]) == 1
