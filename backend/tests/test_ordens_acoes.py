def test_concluir_laboratorio_espelha_e_marca(db_session, fases_seed):
    from app.models import Cliente, Equipamento, EquipamentoCliente, Ordem
    from app.api.ordens_acoes import concluir_laboratorio

    cat = Equipamento(descricao="Mark X"); db_session.add(cat); db_session.flush()
    cli = Cliente(nome="ACME"); db_session.add(cli); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=cat.id, serie="S1")
    db_session.add(ec); db_session.flush()
    o = Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=5, situacao="E",
              tipo_servico="C", calib_cert="C-1", calib_situacao="Aprovado",
              desfecho_lab="pendente")
    db_session.add(o); db_session.commit(); db_session.refresh(o)

    concluir_laboratorio(db_session, o)
    db_session.commit()
    db_session.refresh(o); db_session.refresh(ec)

    assert o.desfecho_lab == "concluido"
    assert o.desfecho_lab_obs is None
    assert ec.calib_cert == "C-1"          # espelhado na frota
    assert ec.calib_situacao == "Aprovado"
