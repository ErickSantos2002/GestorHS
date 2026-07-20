from datetime import date, datetime, timezone


def test_preencher_substitui_campos():
    from app.core.certificado_gerar import preencher
    html = "Cliente: [nomecli] / Série: [serie] / Temp: [temperatura]"
    out = preencher(html, {"nomecli": "ACME", "serie": "S1", "temperatura": "25"})
    assert out == "Cliente: ACME / Série: S1 / Temp: 25"


def test_preencher_campo_sem_valor_some():
    from app.core.certificado_gerar import preencher
    assert preencher("X[inexistente]Y", {}) == "X[inexistente]Y"


def test_preencher_escapa_valor_malicioso():
    from app.core.certificado_gerar import preencher
    out = preencher("Cliente: [nomecli]", {"nomecli": "<script>alert(1)</script>"})
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_preencher_pulapagina_vira_quebra():
    from app.core.certificado_gerar import preencher
    out = preencher("A[pulapagina]B", {})
    assert "[pulapagina]" not in out
    assert "page-break-after" in out


def test_contexto_tem_nomes_legados(db_session):
    from app.models import Cliente, Ordem
    from app.core.certificado_gerar import montar_contexto
    cli = Cliente(nome="ACME"); db_session.add(cli); db_session.flush()
    o = Ordem(cliente=cli.id, situacao="E", calib_temp="25", calib_pressao="1",
              calib_teste1="a", calib_teste2="b", calib_teste3="c",
              calib_teste_media="0,20", calib_situacao="Aprovado")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    ctx = montar_contexto(db_session, o)
    # nomes legados usados pelos 12 modelos migrados
    assert ctx["calibtemp"] == "25"
    assert ctx["calibpressao"] == "1"
    assert ctx["calibteste1"] == "a"
    assert ctx["calibtestemedia"] == "0,20"
    assert ctx["situcalib"] == "Aprovado"
    assert "datacali" in ctx and "dataentr" in ctx


def test_montar_contexto(db_session):
    from app.models import Cliente, Equipamento, Marca, EquipamentoCliente, Ordem
    from app.core.certificado_gerar import montar_contexto
    marca = Marca(descricao="Alcovisor"); db_session.add(marca); db_session.flush()
    cat = Equipamento(descricao="Mark X", marca=marca.id); db_session.add(cat); db_session.flush()
    cli = Cliente(nome="ACME LTDA", cgc="11222333000144", endereco="Rua A", municipio="SP", estado="SP")
    db_session.add(cli); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=cat.id, serie="SER-9", patrimonio="PAT-9")
    db_session.add(ec); db_session.flush()
    o = Ordem(cliente=cli.id, equipamento_cliente=ec.id, situacao="E",
              calib_cert="C-100", calib_temp="25", calib_pressao="1", calib_teste_media="0,20",
              calib_situacao="Aprovado", data_calibracao=datetime(2026, 6, 8, tzinfo=timezone.utc))
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    ctx = montar_contexto(db_session, o)
    assert ctx["nomecli"] == "ACME LTDA"
    assert ctx["cnpj"] == "11.222.333/0001-44"
    assert ctx["modelo"] == "Mark X"
    assert ctx["marca"] == "Alcovisor"
    assert ctx["serie"] == "SER-9"
    assert ctx["patrimonio"] == "PAT-9"
    assert ctx["calibcert"] == "C-100"
    assert ctx["temperatura"] == "25"
    assert ctx["media"] == "0,20"
    assert ctx["situacao"] == "Aprovado"
    assert ctx["os"] == str(o.id)
    assert ctx["datacalibracao"] == "08/06/2026"


def test_montar_contexto_aplica_overrides(db_session):
    from app.models import Cliente, Ordem
    from app.core.certificado_gerar import montar_contexto
    cli = Cliente(nome="ACME LTDA", cgc="111"); db_session.add(cli); db_session.flush()
    o = Ordem(cliente=cli.id, situacao="E", cert_overrides={"nomecli": "NOME ESPECIAL", "cnpj": "999"})
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    ctx = montar_contexto(db_session, o)
    assert ctx["nomecli"] == "NOME ESPECIAL"
    assert ctx["cnpj"] == "999"


def test_montar_contexto_override_vazio_mantem_derivado(db_session):
    from app.models import Cliente, Ordem
    from app.core.certificado_gerar import montar_contexto
    cli = Cliente(nome="ACME LTDA"); db_session.add(cli); db_session.flush()
    o = Ordem(cliente=cli.id, situacao="E", cert_overrides={"nomecli": ""})
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    ctx = montar_contexto(db_session, o)
    assert ctx["nomecli"] == "ACME LTDA"
