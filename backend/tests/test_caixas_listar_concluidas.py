from app.models import Caixa, Cliente, Ordem


def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _caixa_com_ordens(db_session, fases):
    """Cria uma caixa com OS nas fases dadas (lista vazia => caixa sem OS)."""
    cli = Cliente(nome="Cliente Cx")
    db_session.add(cli); db_session.flush()
    cx = Caixa(obs="cx")
    db_session.add(cx); db_session.flush()
    for f in fases:
        db_session.add(Ordem(cliente=cli.id, fase=f, situacao="E", caixa=cx.id))
    db_session.commit(); db_session.refresh(cx)
    return cx.id


def _ids(resp):
    return {c["id"] for c in resp.json()["items"]}


def test_lista_oculta_concluidas_por_padrao(client, usuario_admin, fases_seed, db_session):
    h = _headers(client, "admin", "senha123")
    ativa = _caixa_com_ordens(db_session, [4])         # tem OS ativa -> visivel
    vazia = _caixa_com_ordens(db_session, [])          # sem OS -> visivel
    terminais = _caixa_com_ordens(db_session, [8, 9])  # finalizada + cancelada -> oculta
    so_final = _caixa_com_ordens(db_session, [8])      # so finalizada -> oculta

    ids = _ids(client.get("/caixas", headers=h))
    assert ativa in ids
    assert vazia in ids
    assert terminais not in ids
    assert so_final not in ids


def test_lista_inclui_concluidas_quando_pedido(client, usuario_admin, fases_seed, db_session):
    h = _headers(client, "admin", "senha123")
    ativa = _caixa_com_ordens(db_session, [5])
    concluida = _caixa_com_ordens(db_session, [8])

    ids = _ids(client.get("/caixas?incluir_concluidas=true", headers=h))
    assert ativa in ids
    assert concluida in ids


def test_lista_caixa_mista_com_ativa_fica_visivel(client, usuario_admin, fases_seed, db_session):
    h = _headers(client, "admin", "senha123")
    mista = _caixa_com_ordens(db_session, [8, 5])  # uma finalizada + uma ativa -> visivel
    assert mista in _ids(client.get("/caixas", headers=h))
