from datetime import date


def test_abrir_in_novos_campos():
    from app.schemas.ordens import OrdemAbrirIn
    m = OrdemAbrirIn(
        equipamento_cliente=1, tipo_servico="C",
        data_chegada=date(2026, 6, 8), condicao_chegada="Bom estado",
        checklist=[1, 3], pilhas=4, bocais=2, observacoes="ok",
    )
    assert m.checklist == [1, 3]
    assert m.bocais == 2
    assert m.observacoes == "ok"
    assert not hasattr(m, "acessorios")


def test_abrir_in_minimo():
    from app.schemas.ordens import OrdemAbrirIn
    m = OrdemAbrirIn(equipamento_cliente=1, tipo_servico="M")
    assert m.data_chegada is None
    assert m.pilhas == 0
    assert m.bocais == 0
    assert m.checklist is None


def test_ordem_out_expoe_recebimento(db_session):
    from app.models import Cliente, Ordem
    from app.schemas.ordens import OrdemOut
    cli = Cliente(nome="Cliente Out")
    db_session.add(cli); db_session.flush()
    o = Ordem(cliente=cli.id, situacao="E", checklist="1,3", pilhas=5, sopradores=1)
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    out = OrdemOut.model_validate(o)
    assert out.checklist_ids == [1, 3]
    assert out.acessorios_presentes == ["Bobinas", "Cabos USB"]
    assert out.pilhas == 5
    assert out.bocais == 1
