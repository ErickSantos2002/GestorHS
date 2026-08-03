from datetime import date


def _aparelho(db_session):
    from app.models import Cliente, Equipamento, EquipamentoCliente, Marca
    m = Marca(descricao="Alcoscan")
    db_session.add(m); db_session.flush()
    cli = Cliente(nome="ACME Ltda", cgc="11222333000144",
                  endereco="Rua X", numero=10, bairro="Centro",
                  municipio="Recife", estado="PE")
    eq = Equipamento(descricao="Mark X", marca=m.id)
    db_session.add_all([cli, eq]); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie="S1",
                            patrimonio="P1", datacompra=date(2026, 1, 5))
    db_session.add(ec); db_session.commit(); db_session.refresh(ec)
    return ec


def _valores(**kw):
    base = {
        "calib_cert": "V-001", "data_calibracao": date(2026, 7, 20),
        "prox_calibragem": date(2027, 7, 20),
        "calib_temp": "22", "calib_pressao": "1013",
        "calib_teste1": "0,10", "calib_teste2": "0,11", "calib_teste3": "0,12",
        "calib_teste_media": "0,11", "calib_situacao": "Aparelho inicial",
    }
    base.update(kw)
    return base


def test_contexto_venda_tem_o_mesmo_conjunto_de_chaves_da_os(db_session):
    """Blindagem contra token vazando como [token] no PDF."""
    from app.core.certificado_gerar import montar_contexto_venda, _montar_contexto
    ec = _aparelho(db_session)
    ctx = montar_contexto_venda(db_session, ec, _valores())
    assert set(ctx.keys()) == set(_montar_contexto().keys())


def test_contexto_venda_puxa_cliente_e_aparelho_do_cadastro(db_session):
    from app.core.certificado_gerar import montar_contexto_venda
    ec = _aparelho(db_session)
    ctx = montar_contexto_venda(db_session, ec, _valores())
    assert ctx["nomecli"] == "ACME Ltda"
    assert ctx["cnpj"] == "11.222.333/0001-44"
    assert "Rua X" in ctx["endcli"] and "Recife" in ctx["endcli"]
    assert ctx["modelo"] == "Mark X"
    assert ctx["marca"] == "Alcoscan"
    assert ctx["serie"] == "S1"
    assert ctx["patrimonio"] == "P1"
    assert ctx["datacompra"] == "05/01/2026"


def test_contexto_venda_usa_XXXX_como_numero_de_os(db_session):
    """Nao ha OS: mesma convencao ja usada no certificado avulso."""
    from app.core.certificado_gerar import montar_contexto_venda
    ec = _aparelho(db_session)
    ctx = montar_contexto_venda(db_session, ec, _valores())
    assert ctx["os"] == "XXXX"


def test_contexto_venda_dataentr_cai_na_data_de_compra(db_session):
    from app.core.certificado_gerar import montar_contexto_venda
    ec = _aparelho(db_session)
    ctx = montar_contexto_venda(db_session, ec, _valores())
    assert ctx["dataentr"] == "05/01/2026"


def test_contexto_venda_dataentr_cai_em_hoje_sem_data_de_compra(db_session):
    from app.core.certificado_gerar import montar_contexto_venda
    ec = _aparelho(db_session)
    ec.datacompra = None
    db_session.commit()
    ctx = montar_contexto_venda(db_session, ec, _valores())
    assert ctx["dataentr"] == date.today().strftime("%d/%m/%Y")


def test_contexto_venda_preenche_proxima_calibragem(db_session):
    from app.core.certificado_gerar import montar_contexto_venda
    ec = _aparelho(db_session)
    ctx = montar_contexto_venda(db_session, ec, _valores())
    assert ctx["proxcalibragem"] == "20/07/2027"


def test_contexto_venda_valores_do_modal_sobrepoem_o_cadastro(db_session):
    """O laboratorio pode corrigir serie/patrimonio na hora de gerar."""
    from app.core.certificado_gerar import montar_contexto_venda
    ec = _aparelho(db_session)
    ctx = montar_contexto_venda(db_session, ec, _valores(serie="S1-CORRIGIDA",
                                                         nomecli="ACME Filial"))
    assert ctx["serie"] == "S1-CORRIGIDA"
    assert ctx["nomecli"] == "ACME Filial"


def test_venda_calcula_erro_e_incerteza_da_planilha(db_session):
    """O venda agora calcula o bloco EPS-LAB-002 igual a OS — mesma planilha,
    mesmos numeros: cinco medicoes de 0,16 dao erro 0,06 e U 0,1301."""
    from app.core.certificado_gerar import montar_contexto_venda
    ec = _aparelho(db_session)
    ctx = montar_contexto_venda(db_session, ec, _valores(
        calib_teste1="0.16", calib_teste2="0.16", calib_teste3="0.16",
        calib_teste4="0.16", calib_teste5="0.16",
    ))
    assert ctx["erro1"] == "0,060"
    assert ctx["erro5"] == "0,060"
    assert ctx["mediamedicoes"] == "0,160"
    assert ctx["incertezaexpandida"] == "0,1301"


def test_venda_com_cilindro_vigente_preenche_padrao_e_drygasppm(db_session):
    """Assercao de nao-vazio explicita: "" == "" passaria vazio e nao provaria nada."""
    from app.models import CertificadoPadrao
    from app.core.certificado_gerar import montar_contexto_venda

    padrao = CertificadoPadrao(
        numero_cilindro="CC747704", numero_certificado="202231419",
        concentracao=100.1, incerteza_concentracao=2.0, unidade="µmol/mol",
        vigencia_inicio=date(2020, 1, 1), vigencia_fim=None, ativo=True,
    )
    db_session.add(padrao)
    db_session.commit()

    ec = _aparelho(db_session)
    ctx = montar_contexto_venda(db_session, ec, _valores())
    assert ctx["padraocilindro"] == "CC747704"
    assert ctx["padraocilindro"] != ""
    assert ctx["drygasppm"] == ctx["padraoconcentracao"]
    assert ctx["drygasppm"] != ""


def test_venda_sem_cilindro_para_a_data_deixa_campos_vazios_sem_erro(db_session):
    from app.core.certificado_gerar import montar_contexto_venda
    ec = _aparelho(db_session)
    ctx = montar_contexto_venda(db_session, ec, _valores())
    assert ctx["padraocilindro"] == ""
    assert ctx["drygasppm"] == ""


def test_venda_teste4_e_teste5_do_payload_chegam_ao_contexto(db_session):
    from app.core.certificado_gerar import montar_contexto_venda
    ec = _aparelho(db_session)
    ctx = montar_contexto_venda(db_session, ec, _valores(calib_teste4="0,15", calib_teste5="0,17"))
    assert ctx["calibteste4"] == "0,15"
    assert ctx["calibteste5"] == "0,17"


def test_venda_teste4_e_teste5_caem_no_fallback_da_frota_quando_nao_digitados(db_session):
    """Sem teste4/teste5 no payload, o valor ja gravado na frota (equipamento_cliente)
    alimenta tanto o token exibido quanto o calculo do erro."""
    from app.core.certificado_gerar import montar_contexto_venda
    ec = _aparelho(db_session)
    ec.calib_teste4 = "0,20"
    ec.calib_teste5 = "0,21"
    db_session.commit()

    ctx = montar_contexto_venda(db_session, ec, _valores())   # sem teste4/5 no payload
    assert ctx["calibteste4"] == "0,20"
    assert ctx["calibteste5"] == "0,21"
    # valor_referencia default e 0,1 -> confirma que o fallback da frota tambem
    # alimenta o CALCULO (erro = medicao - referencia), nao so o token exibido.
    assert ctx["erro4"] == "0,100"
    assert ctx["erro5"] == "0,110"


def test_venda_traz_tecnico_e_campos_de_config_nao_da_os(db_session):
    """tecnico, cargo, equipamentos auxiliares, margem de temperatura e limites
    vem da CONFIG do laboratorio — nao ha razao para sairem vazios."""
    from app.core.certificado_config import obter_config
    from app.core.certificado_gerar import montar_contexto_venda

    config = obter_config(db_session)
    config.equipamentos_auxiliares = "TESTO 622"
    db_session.commit()

    ec = _aparelho(db_session)
    ctx = montar_contexto_venda(db_session, ec, _valores())
    assert ctx["tecnico"] == "Walbert Santos"
    assert ctx["tecnicocargo"] == "Técnico em Metrologia"
    assert ctx["equipamentosauxiliares"] == "TESTO 622"
    assert ctx["margemtemp"] == "20 ºC ~ 24 ºC"
    assert ctx["limitemin"] == "0,150"
    assert ctx["limitemax"] == "0,190"


def test_nenhum_token_vaza_no_html_de_venda(db_session):
    """Template usando TODOS os tokens nao pode deixar nenhum [token] literal."""
    from app.core.certificado_gerar import CAMPOS, montar_contexto_venda, preencher
    ec = _aparelho(db_session)
    template = " ".join(f"[{nome}]" for nome, _ in CAMPOS)
    html = preencher(template, montar_contexto_venda(db_session, ec, _valores()))
    assert "[" not in html
