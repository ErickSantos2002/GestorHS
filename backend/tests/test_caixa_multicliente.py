def test_caixa_cliente_principal(db_session, fases_seed):
    from app.models import Cliente, Caixa
    cli = Cliente(nome="ACME"); db_session.add(cli); db_session.flush()
    cx = Caixa(fase=4, cliente_principal=cli.id); db_session.add(cx); db_session.flush()
    db_session.refresh(cx)
    assert cx.cliente_principal == cli.id
    assert cx.cliente_principal_nome == "ACME"
