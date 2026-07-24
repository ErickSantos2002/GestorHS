def test_montar_html_tem_titulo_tecnica(db_session):
    from app.core import proposta_pdf
    from app.models import Cliente, Proposta, PropostaItem
    cli = Cliente(nome="ACME", cgc="08857492000148")
    db_session.add(cli); db_session.flush()
    p = Proposta(numero=7, cliente=cli.id)
    p.itens.append(PropostaItem(descricao="Calibracao", quantidade=1, preco_un=395, total=395))
    db_session.add(p); db_session.flush()
    html = proposta_pdf.montar_html(p, cli)
    assert "Proposta Técnica" in html
    assert "ACME" in html
    assert "395" in html


def test_montar_html_documento_formatado_e_contato():
    from app.core import proposta_pdf
    from app.models import Cliente, Proposta, PropostaItem

    cli = Cliente(
        nome="ACME LTDA",
        cgc="08857492000148",
        endereco="Rua Teste, 100",
        municipio="Recife",
        estado="PE",
        email="contato@acme.com",
        celular="81999998888",
    )
    p = Proposta(
        id=1,
        numero=99,
        contato="Fulano de Tal",
        itens=[],
    )
    p.itens.append(PropostaItem(descricao="Servico X", quantidade=2, unidade="un", preco_un=100, total=200))

    html = proposta_pdf.montar_html(p, cli)

    assert "08.857.492/0001-48" in html
    assert "Recife - PE" in html
    assert "Fulano de Tal" in html
    assert "Servico X" in html or "Servi&ccedil;o X" in html


def test_montar_html_cliente_override_substitui_display():
    from app.core import proposta_pdf
    from app.models import Cliente, Proposta

    cli = Cliente(nome="ACME", cgc="08857492000148")
    p = Proposta(id=2, numero=100, cliente_override={"nome": "ACME FILIAL SP"})

    html = proposta_pdf.montar_html(p, cli)

    assert "ACME FILIAL SP" in html


def test_montar_html_endereco_entrega_texto_livre():
    from app.core import proposta_pdf
    from app.models import Cliente, Proposta

    cli = Cliente(nome="ACME", cgc="08857492000148")
    p = Proposta(
        id=3,
        numero=101,
        endereco_entrega_diferente=True,
        endereco_entrega={"texto": "Rua Teste 123, Recife-PE"},
    )

    html = proposta_pdf.montar_html(p, cli)

    assert "Rua Teste 123" in html
    assert "Recife-PE" in html
    assert "Endereço de Entrega" in html
