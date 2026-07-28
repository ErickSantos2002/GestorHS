import pytest


@pytest.fixture()
def caixa_recebido_principal_stale(db_session, fases_seed):
    """Caixa em fase 4 (Recebido) com 1 OS ativa de um único cliente, mas
    `cliente_principal` apontando para um cliente que não está entre as OS da
    caixa (stale). Devolve o id da caixa."""
    from app.models import Cliente, Caixa, Ordem
    cli = Cliente(nome="Cliente Recebido Stale")
    outro = Cliente(nome="Cliente Fora Da Caixa")
    db_session.add_all([cli, outro])
    db_session.flush()
    cx = Caixa(obs="Caixa recebido principal stale", fase=4, cliente_principal=outro.id)
    db_session.add(cx)
    db_session.flush()
    o = Ordem(cliente=cli.id, fase=4, situacao="E", caixa=cx.id)
    db_session.add(o)
    db_session.commit()
    db_session.refresh(cx)
    return cx.id


def _item_do_quadro(colunas, caixa_id):
    return next(it for col in colunas for it in col["caixas"] if it["id"] == caixa_id)


def test_quadro_um_cliente_principal_none(client_exp, caixa_recebido_um_cliente):
    colunas = client_exp.get("/caixas/quadro").json()
    item = _item_do_quadro(colunas, caixa_recebido_um_cliente)
    assert item["outros_clientes"] == 0


def test_quadro_um_cliente_principal_stale(client_exp, caixa_recebido_principal_stale):
    colunas = client_exp.get("/caixas/quadro").json()
    item = _item_do_quadro(colunas, caixa_recebido_principal_stale)
    assert item["outros_clientes"] == 0


def test_quadro_dois_clientes_sem_principal(client_exp, caixa_recebido_dois_clientes):
    colunas = client_exp.get("/caixas/quadro").json()
    item = _item_do_quadro(colunas, caixa_recebido_dois_clientes)
    assert item["outros_clientes"] == 1


def test_model_outros_clientes_um_cliente_principal_none(db_session, fases_seed):
    from app.models import Cliente, Caixa, Ordem
    cli = Cliente(nome="Cliente Unico Model")
    cx = Caixa(obs="Caixa model unico", fase=4)
    db_session.add_all([cli, cx])
    db_session.flush()
    o = Ordem(cliente=cli.id, fase=4, situacao="E", caixa=cx.id)
    db_session.add(o)
    db_session.commit()
    db_session.refresh(cx)
    assert cx.outros_clientes == 0
