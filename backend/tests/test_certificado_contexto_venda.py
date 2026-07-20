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
    assert ctx["cnpj"] == "11222333000144"
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


def test_nenhum_token_vaza_no_html_de_venda(db_session):
    """Template usando TODOS os tokens nao pode deixar nenhum [token] literal."""
    from app.core.certificado_gerar import CAMPOS, montar_contexto_venda, preencher
    ec = _aparelho(db_session)
    template = " ".join(f"[{nome}]" for nome, _ in CAMPOS)
    html = preencher(template, montar_contexto_venda(db_session, ec, _valores()))
    assert "[" not in html
