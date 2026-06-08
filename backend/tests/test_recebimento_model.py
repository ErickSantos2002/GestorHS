def test_ordem_checklist_properties(db_session):
    from app.models import Cliente, Ordem
    cli = Cliente(nome="Cliente CK")
    db_session.add(cli); db_session.flush()
    o = Ordem(cliente=cli.id, situacao="E", checklist="1,3,9", pilhas=4, sopradores=2)
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    assert o.checklist_ids == [1, 3, 9]
    assert o.acessorios_presentes == ["Bobinas", "Cabos USB", "Nf de Remessa"]
    assert o.bocais == 2


def test_ordem_checklist_vazio(db_session):
    from app.models import Cliente, Ordem
    cli = Cliente(nome="Cliente CK2")
    db_session.add(cli); db_session.flush()
    o = Ordem(cliente=cli.id, situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    assert o.checklist_ids == []
    assert o.acessorios_presentes == []
    assert o.bocais == 0
