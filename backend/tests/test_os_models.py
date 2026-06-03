def test_ordem_propriedades_e_relationships(db_session):
    from app.models import Cliente, Equipamento, EquipamentoCliente, Fase, Ordem, LogOS, Funcao
    exp = Funcao(descricao="Expedição")
    db_session.add(exp); db_session.flush()
    db_session.add(Fase(id=4, descricao="Recebido", cor="3b82f6", funcao_responsavel=exp.id))
    cli = Cliente(nome="ACME")
    eq = Equipamento(descricao="Bafômetro X")
    db_session.add_all([cli, eq]); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie="S-123")
    db_session.add(ec); db_session.flush()
    o = Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=4, tipo_servico="C")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    assert o.situacao == "E"        # default
    assert o.recebido is False      # default
    assert o.aceite is False        # default
    assert o.cliente_nome == "ACME"
    assert o.equipamento_serie == "S-123"
    assert o.equipamento_descricao == "Bafômetro X"
    assert o.fase_descricao == "Recebido"
    assert o.fase_cor == "3b82f6"
    log = LogOS(os=o.id, usuario=None, texto="abertura")
    db_session.add(log); db_session.commit(); db_session.refresh(log)
    assert log.os == o.id and log.texto == "abertura"


def test_fase_funcao_nome(db_session):
    from app.models import Fase, Funcao
    lab = Funcao(descricao="Laboratório")
    db_session.add(lab); db_session.flush()
    f = Fase(id=5, descricao="Laboratório", cor="6366f1", funcao_responsavel=lab.id)
    db_session.add(f); db_session.commit(); db_session.refresh(f)
    assert f.funcao_nome == "Laboratório"
    f2 = Fase(id=8, descricao="Finalizada", cor="10b981", funcao_responsavel=None)
    db_session.add(f2); db_session.commit(); db_session.refresh(f2)
    assert f2.funcao_nome is None
