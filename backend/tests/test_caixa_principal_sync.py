"""Task 2: auto-set do cliente_principal quando a caixa tem 1 unico cliente,
e blindagem das integracoes (GrowthHS/TaskHS) contra principal orfao/stale."""
from app.api.caixas import sincronizar_principal
from app.api.growthhs_cards import cliente_do_card


def test_abrir_os_em_caixa_nova_define_principal(client_exp, os_base, caixa_base, db_session):
    from app.models import Caixa

    r = client_exp.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"],
        "tipo_servico": "C",
        "caixa": caixa_base,
    })
    assert r.status_code == 201

    cx = db_session.get(Caixa, caixa_base)
    db_session.refresh(cx)
    assert cx.cliente_principal == os_base["cliente"]


def test_mover_ressincroniza_principal_da_caixa_de_origem(client_exp, db_session, fases_seed):
    """Antes isto era provado pelo desvincular, que saiu (OS nao pode ficar sem
    caixa). A ressincronizacao da caixa de ORIGEM continua valendo — agora pelo
    unico caminho que restou, que e' mover para outra caixa."""
    from app.models import Cliente, Caixa, Ordem

    cli_a = Cliente(nome="Cliente Ressync A")
    cli_b = Cliente(nome="Cliente Ressync B")
    cx = Caixa(obs="Caixa ressync", fase=4)
    db_session.add_all([cli_a, cli_b, cx])
    db_session.flush()
    o_a = Ordem(cliente=cli_a.id, fase=4, situacao="E", caixa=cx.id)
    o_b = Ordem(cliente=cli_b.id, fase=4, situacao="E", caixa=cx.id)
    db_session.add_all([o_a, o_b])
    db_session.flush()
    cx.cliente_principal = cli_a.id
    db_session.commit()
    db_session.refresh(o_a)
    db_session.refresh(cx)

    destino = Caixa(obs="Caixa destino ressync", fase=4)
    db_session.add(destino)
    db_session.commit()
    db_session.refresh(destino)

    r = client_exp.post(f"/caixas/{destino.id}/ordens", json={"ordem_id": o_a.id})
    assert r.status_code == 200

    db_session.refresh(cx)
    assert cx.cliente_principal == cli_b.id


def test_vincular_ordem_em_caixa_define_principal(client_exp, db_session, caixa_base, os_cliente_b):
    from app.models import Caixa, Ordem

    ordem = db_session.get(Ordem, os_cliente_b)
    cliente_id = ordem.cliente

    r = client_exp.post(f"/caixas/{caixa_base}/ordens", json={"ordem_id": os_cliente_b})
    assert r.status_code == 200

    cx = db_session.get(Caixa, caixa_base)
    db_session.refresh(cx)
    assert cx.cliente_principal == cliente_id


def test_vincular_ressincroniza_principal_da_caixa_origem(
    client_exp, db_session, caixa_recebido_dois_clientes, cliente_a_id
):
    from app.models import Caixa, Ordem

    origem = db_session.get(Caixa, caixa_recebido_dois_clientes)
    origem.cliente_principal = cliente_a_id
    db_session.commit()

    clientes = [c for (c,) in db_session.query(Ordem.cliente)
                .filter(Ordem.caixa == caixa_recebido_dois_clientes).all()]
    cliente_b_id = next(c for c in clientes if c != cliente_a_id)

    ordem_a = db_session.query(Ordem).filter(
        Ordem.caixa == caixa_recebido_dois_clientes, Ordem.cliente == cliente_a_id
    ).first()

    destino = Caixa(obs="Caixa destino ressync", fase=4)
    db_session.add(destino)
    db_session.commit()
    db_session.refresh(destino)

    r = client_exp.post(f"/caixas/{destino.id}/ordens", json={"ordem_id": ordem_a.id})
    assert r.status_code == 200

    db_session.refresh(origem)
    assert origem.cliente_principal == cliente_b_id


def test_sincronizar_principal_nao_altera_principal_valido_com_dois_clientes(
    db_session, caixa_recebido_dois_clientes, cliente_a_id
):
    from app.models import Caixa

    cx = db_session.get(Caixa, caixa_recebido_dois_clientes)
    cx.cliente_principal = cliente_a_id
    db_session.commit()

    sincronizar_principal(db_session, cx)
    db_session.commit()
    db_session.refresh(cx)

    assert cx.cliente_principal == cliente_a_id


def test_cliente_do_card_usa_principal_valido(caixa_multi_com_principal_b):
    cx = caixa_multi_com_principal_b
    cliente = cliente_do_card(cx)
    assert cliente is not None
    assert cliente.id == cx.cliente_principal


def test_cliente_do_card_cai_para_primeira_os_quando_principal_stale(
    db_session, caixa_multi_com_principal_b
):
    cx = caixa_multi_com_principal_b
    from app.models import Cliente

    cli_externo = Cliente(nome="Cliente Externo Card")
    db_session.add(cli_externo)
    db_session.flush()
    cx.cliente_principal = cli_externo.id
    db_session.commit()
    db_session.refresh(cx)

    cliente = cliente_do_card(cx)
    assert cliente is not None
    assert cliente.id == cx.ordens[0].cliente


def test_cliente_do_card_cai_para_primeira_os_quando_principal_nulo(
    db_session, caixa_multi_com_principal_b
):
    cx = caixa_multi_com_principal_b
    cx.cliente_principal = None
    db_session.commit()
    db_session.refresh(cx)

    cliente = cliente_do_card(cx)
    assert cliente is not None
    assert cliente.id == cx.ordens[0].cliente
