from datetime import date


def test_caixa_out_from_model(db_session):
    from app.models import Cliente, Ordem, Caixa, Funcao, Fase
    from app.schemas.caixas import CaixaOut, CaixaDetalhe

    # seed Funcao + Fase para satisfazer FK ordens.fase (igual test_caixas_model.py)
    funcao = Funcao(descricao="Expedição")
    db_session.add(funcao); db_session.flush()
    fase = Fase(id=4, descricao="Recebido", cor="3b82f6", funcao_responsavel=funcao.id)
    db_session.add(fase); db_session.flush()

    cli = Cliente(nome="Cliente Z")
    db_session.add(cli); db_session.flush()
    cx = Caixa(data=date(2026, 6, 5), status="P", obs="origem X")
    db_session.add(cx); db_session.flush()
    db_session.add(Ordem(cliente=cli.id, fase=4, caixa=cx.id, situacao="E"))
    db_session.commit(); db_session.refresh(cx)

    out = CaixaOut.model_validate(cx)
    assert out.id == cx.id
    assert out.status == "P"
    assert out.total_os == 1
    assert out.clientes == ["Cliente Z"]

    det = CaixaDetalhe.model_validate(cx)
    assert len(det.ordens) == 1
    assert det.ordens[0].cliente_nome == "Cliente Z"


def test_vincular_ordem_in():
    from app.schemas.caixas import VincularOrdemIn
    assert VincularOrdemIn(ordem_id=7).ordem_id == 7
