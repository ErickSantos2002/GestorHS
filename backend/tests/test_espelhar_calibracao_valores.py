from datetime import date, datetime, timezone


def _seed_fase_laboratorio(db_session):
    """Ordem.fase e FK: sem a fase 5 no banco o insert quebra por FOREIGN KEY."""
    from app.models import Fase, Funcao
    if db_session.query(Fase).filter(Fase.id == 5).first() is not None:
        return
    f = db_session.query(Funcao).filter(Funcao.descricao == "Laboratório").first()
    if f is None:
        f = Funcao(descricao="Laboratório")
        db_session.add(f); db_session.flush()
    db_session.add(Fase(id=5, descricao="Laboratório", cor="6366f1", funcao_responsavel=f.id))
    db_session.flush()


def _aparelho(db_session):
    from app.models import Cliente, Equipamento, EquipamentoCliente
    cli = Cliente(nome="ACME"); eq = Equipamento(descricao="Mark X")
    db_session.add_all([cli, eq]); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie="S1")
    db_session.add(ec); db_session.commit(); db_session.refresh(ec)
    return ec


def test_espelha_valores_soltos_no_aparelho(db_session):
    from app.api.ordens_acoes import espelhar_calibracao_valores
    ec = _aparelho(db_session)
    espelhar_calibracao_valores(
        db_session, ec,
        {"calib_cert": "V-001", "calib_temp": "22", "calib_pressao": "1013",
         "calib_teste1": "0,10", "calib_teste2": "0,11", "calib_teste3": "0,12",
         "calib_teste_media": "0,11", "calib_situacao": "Aparelho inicial"},
        ult=date(2026, 7, 20), prox=date(2027, 7, 20),
    )
    db_session.commit(); db_session.refresh(ec)
    assert ec.calib_cert == "V-001"
    assert ec.calib_situacao == "Aparelho inicial"
    assert ec.calib_teste_media == "0,11"
    assert ec.ult_calibragem == date(2026, 7, 20)
    assert ec.prox_calibragem == date(2027, 7, 20)


def test_valor_ausente_nao_apaga_o_que_ja_havia(db_session):
    from app.api.ordens_acoes import espelhar_calibracao_valores
    ec = _aparelho(db_session)
    ec.calib_temp = "20"
    db_session.commit()
    espelhar_calibracao_valores(db_session, ec, {"calib_cert": "V-002"},
                                ult=None, prox=None)
    db_session.commit(); db_session.refresh(ec)
    assert ec.calib_cert == "V-002"
    assert ec.calib_temp == "20"      # preservado


def test_espelhar_calibracao_da_os_continua_igual(db_session):
    """Regressao: o caminho da OS nao pode mudar de comportamento."""
    from app.api.ordens_acoes import espelhar_calibracao
    from app.models import Ordem
    ec = _aparelho(db_session)
    _seed_fase_laboratorio(db_session)
    ordem = Ordem(cliente=ec.cliente, equipamento_cliente=ec.id, situacao="E",
                  tipo_servico="C", fase=5,
                  calib_cert="OS-9", calib_temp="21", calib_situacao="Aparelho subsequente",
                  data_calibracao=datetime(2026, 7, 20, tzinfo=timezone.utc),
                  prox_calibragem=datetime(2027, 7, 20, tzinfo=timezone.utc))
    db_session.add(ordem); db_session.commit()
    espelhar_calibracao(db_session, ordem)
    db_session.commit(); db_session.refresh(ec)
    assert ec.calib_cert == "OS-9"
    assert ec.calib_temp == "21"
    assert ec.ult_calibragem == date(2026, 7, 20)
    assert ec.prox_calibragem == date(2027, 7, 20)
