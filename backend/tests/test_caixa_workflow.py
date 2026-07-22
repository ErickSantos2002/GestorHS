from app.models import Caixa, Ordem


def test_caixa_tem_coluna_fase():
    cx = Caixa(fase=4)
    assert cx.fase == 4


def test_ordem_desfecho_lab_default_pendente(db_session, fases_seed):
    # db_session: fixture do conftest que cria as tabelas em memoria
    from app.models import Cliente
    cli = Cliente(nome="ACME")
    db_session.add(cli)
    db_session.flush()
    o = Ordem(cliente=cli.id, fase=5)
    db_session.add(o)
    db_session.flush()
    assert o.desfecho_lab == "pendente"
    assert o.desfecho_lab_obs is None
