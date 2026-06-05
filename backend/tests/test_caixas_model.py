from datetime import date


def _seed_caixa_com_os(db_session):
    from app.models import Cliente, Equipamento, EquipamentoCliente, Caixa, Ordem, Fase, Funcao
    # seed Funcao + Fase necessários para FK ordens.fase
    funcao = Funcao(descricao="Expedição")
    db_session.add(funcao); db_session.flush()
    fase = Fase(id=4, descricao="Recebido", cor="3b82f6", funcao_responsavel=funcao.id)
    db_session.add(fase); db_session.flush()
    cli_a = Cliente(nome="Cliente A")
    cli_b = Cliente(nome="Cliente B")
    eq = Equipamento(descricao="Bafômetro")
    db_session.add_all([cli_a, cli_b, eq]); db_session.flush()
    cx = Caixa(data=date(2026, 6, 5), obs="Lote Cuiabá")
    db_session.add(cx); db_session.flush()
    o1 = Ordem(cliente=cli_a.id, fase=4, caixa=cx.id, situacao="E")
    o2 = Ordem(cliente=cli_b.id, fase=4, caixa=cx.id, situacao="E")
    o3 = Ordem(cliente=cli_a.id, fase=4, caixa=cx.id, situacao="E")  # cliente A repetido
    db_session.add_all([o1, o2, o3]); db_session.commit(); db_session.refresh(cx)
    return cx


def test_caixa_total_os(db_session):
    cx = _seed_caixa_com_os(db_session)
    assert cx.total_os == 3


def test_caixa_clientes_distintos(db_session):
    cx = _seed_caixa_com_os(db_session)
    assert sorted(cx.clientes) == ["Cliente A", "Cliente B"]


def test_ordem_caixa_rel(db_session):
    cx = _seed_caixa_com_os(db_session)
    o = cx.ordens[0]
    assert o.caixa_rel is not None
    assert o.caixa_obs == "Lote Cuiabá"
