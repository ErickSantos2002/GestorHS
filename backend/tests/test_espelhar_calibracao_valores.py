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


# ── Proxima calibracao calculada ─────────────────────────────────────────────
# Nada no GestorHS preenchia `prox_calibragem` da OS, entao o aparelho ficava com
# a data do ciclo ANTERIOR e virava "Vencido" recem-calibrado (caso do aparelho
# 7912 / OS 10905, 20/08/2026).

def test_os_sem_proxima_calibracao_calcula_um_ano_e_nao_deixa_a_data_velha(db_session):
    from app.api.ordens_acoes import espelhar_calibracao
    from app.models import Ordem
    ec = _aparelho(db_session)
    ec.prox_calibragem = date(2026, 7, 25)   # ciclo anterior, ja no passado
    db_session.commit()
    _seed_fase_laboratorio(db_session)
    ordem = Ordem(cliente=ec.cliente, equipamento_cliente=ec.id, situacao="E",
                  tipo_servico="C", fase=5, calib_cert="HF00561",
                  data_calibracao=datetime(2026, 7, 30, tzinfo=timezone.utc),
                  prox_calibragem=None)
    db_session.add(ordem); db_session.commit()

    espelhar_calibracao(db_session, ordem)
    db_session.commit(); db_session.refresh(ec); db_session.refresh(ordem)

    assert ec.ult_calibragem == date(2026, 7, 30)
    assert ec.prox_calibragem == date(2027, 7, 30), "a data do ciclo anterior nao pode sobreviver"
    # A OS tambem passa a mostrar a proxima calibracao, senao as duas telas divergem.
    assert ordem.prox_calibragem.date() == date(2027, 7, 30)


def test_proxima_calibracao_informada_na_os_manda_sobre_o_calculo(db_session):
    """O calculo e um default, nao uma imposicao: data explicita continua valendo."""
    from app.api.ordens_acoes import espelhar_calibracao
    from app.models import Ordem
    ec = _aparelho(db_session)
    _seed_fase_laboratorio(db_session)
    ordem = Ordem(cliente=ec.cliente, equipamento_cliente=ec.id, situacao="E",
                  tipo_servico="C", fase=5,
                  data_calibracao=datetime(2026, 7, 30, tzinfo=timezone.utc),
                  prox_calibragem=datetime(2026, 12, 1, tzinfo=timezone.utc))
    db_session.add(ordem); db_session.commit()

    espelhar_calibracao(db_session, ordem)
    db_session.commit(); db_session.refresh(ec)
    assert ec.prox_calibragem == date(2026, 12, 1)


def test_os_sem_data_de_calibracao_nao_inventa_proxima(db_session):
    from app.api.ordens_acoes import espelhar_calibracao
    from app.models import Ordem
    ec = _aparelho(db_session)
    ec.prox_calibragem = date(2026, 7, 25)
    db_session.commit()
    _seed_fase_laboratorio(db_session)
    ordem = Ordem(cliente=ec.cliente, equipamento_cliente=ec.id, situacao="E",
                  tipo_servico="C", fase=5, data_calibracao=None, prox_calibragem=None)
    db_session.add(ordem); db_session.commit()

    espelhar_calibracao(db_session, ordem)
    db_session.commit(); db_session.refresh(ec)
    assert ec.prox_calibragem == date(2026, 7, 25), "sem calibracao, nada a recalcular"


# ── Tipo de servico: manutencao NAO mexe na calibracao ────────────────────────
# A conclusao do laboratorio espelhava calibracao para QUALQUER OS. Numa OS tipo
# 'M' isso renovava `ult_calibragem`/`prox_calibragem` do aparelho com a data da
# manutencao — empurrando a proxima calibracao e fazendo a garantia de calibracao
# aparecer no lugar da de manutencao (OS 11166 / caixa 997, 03/09/2026).

def test_os_de_manutencao_nao_toca_na_calibracao_do_aparelho(db_session):
    from app.api.ordens_acoes import espelhar_calibracao
    from app.models import Ordem
    ec = _aparelho(db_session)
    ec.ult_calibragem = date(2026, 7, 28)
    ec.prox_calibragem = date(2027, 7, 28)
    db_session.commit()
    _seed_fase_laboratorio(db_session)
    ordem = Ordem(cliente=ec.cliente, equipamento_cliente=ec.id, situacao="E",
                  tipo_servico="M", fase=5,
                  data_calibracao=datetime(2026, 9, 3, tzinfo=timezone.utc),
                  prox_calibragem=None)
    db_session.add(ordem); db_session.commit()

    espelhar_calibracao(db_session, ordem)
    db_session.commit(); db_session.refresh(ec); db_session.refresh(ordem)

    assert ec.ult_calibragem == date(2026, 7, 28), "manutencao nao renova a calibracao"
    assert ec.prox_calibragem == date(2027, 7, 28), "manutencao nao empurra a proxima calibracao"
    assert ordem.prox_calibragem is None, "OS de manutencao nao inventa proxima calibracao"


def test_os_de_manutencao_nao_espelha_os_campos_de_calibracao(db_session):
    from app.api.ordens_acoes import espelhar_calibracao
    from app.models import Ordem
    ec = _aparelho(db_session)
    ec.calib_cert = "HF02429"
    db_session.commit()
    _seed_fase_laboratorio(db_session)
    ordem = Ordem(cliente=ec.cliente, equipamento_cliente=ec.id, situacao="E",
                  tipo_servico="M", fase=5, calib_cert="NAO-DEVE-ENTRAR",
                  data_calibracao=datetime(2026, 9, 3, tzinfo=timezone.utc))
    db_session.add(ordem); db_session.commit()

    espelhar_calibracao(db_session, ordem)
    db_session.commit(); db_session.refresh(ec)

    assert ec.calib_cert == "HF02429"


def test_os_ambas_continua_espelhando_a_calibracao(db_session):
    """Tipo 'A' faz os dois servicos — a calibracao dele vale."""
    from app.api.ordens_acoes import espelhar_calibracao
    from app.models import Ordem
    ec = _aparelho(db_session)
    _seed_fase_laboratorio(db_session)
    ordem = Ordem(cliente=ec.cliente, equipamento_cliente=ec.id, situacao="E",
                  tipo_servico="A", fase=5, calib_cert="OS-A",
                  data_calibracao=datetime(2026, 9, 3, tzinfo=timezone.utc))
    db_session.add(ordem); db_session.commit()

    espelhar_calibracao(db_session, ordem)
    db_session.commit(); db_session.refresh(ec)

    assert ec.calib_cert == "OS-A"
    assert ec.ult_calibragem == date(2026, 9, 3)
    assert ec.prox_calibragem == date(2027, 9, 3)


def test_os_legada_sem_tipo_servico_continua_espelhando(db_session):
    """`tipo_servico` nulo = calibracao (mesma regra de `tipos_para`)."""
    from app.api.ordens_acoes import espelhar_calibracao
    from app.models import Ordem
    ec = _aparelho(db_session)
    _seed_fase_laboratorio(db_session)
    ordem = Ordem(cliente=ec.cliente, equipamento_cliente=ec.id, situacao="E",
                  tipo_servico=None, fase=5, calib_cert="OS-LEGADA",
                  data_calibracao=datetime(2026, 9, 3, tzinfo=timezone.utc))
    db_session.add(ordem); db_session.commit()

    espelhar_calibracao(db_session, ordem)
    db_session.commit(); db_session.refresh(ec)

    assert ec.calib_cert == "OS-LEGADA"
    assert ec.ult_calibragem == date(2026, 9, 3)
