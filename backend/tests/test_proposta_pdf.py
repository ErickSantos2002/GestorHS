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


def test_montar_html_endereco_entrega_documento_formatado():
    from app.core import proposta_pdf
    from app.models import Cliente, Proposta

    cli = Cliente(nome="ACME", cgc="08857492000148")
    p = Proposta(
        id=4,
        numero=102,
        endereco_entrega_diferente=True,
        endereco_entrega={
            "rua": "Rua Destino",
            "municipio": "Recife",
            "estado": "PE",
            "documento": "36312056000552",
        },
    )

    html = proposta_pdf.montar_html(p, cli)

    assert "36.312.056/0005-52" in html
    assert "36312056000552" not in html


def test_montar_html_mostra_cep_do_cadastro_na_linha_de_cidade():
    from app.core import proposta_pdf
    from app.models import Cliente, Proposta

    cli = Cliente(nome="ACME", cgc="08857492000148", municipio="Recife",
                  estado="PE", cep="50030230")
    p = Proposta(id=1, numero=101)

    html = proposta_pdf.montar_html(p, cli)

    assert "Recife - PE — CEP: 50030-230" in html


def test_montar_html_usa_o_cep_do_override_quando_houver():
    from app.core import proposta_pdf
    from app.models import Cliente, Proposta

    cli = Cliente(nome="ACME", municipio="Recife", estado="PE", cep="50030230")
    p = Proposta(id=2, numero=102, cliente_override={"cep": "01310100"})

    html = proposta_pdf.montar_html(p, cli)

    assert "CEP: 01310-100" in html
    assert "50030-230" not in html


def test_montar_html_sem_cep_nenhum_nao_emite_a_parte_de_cep():
    from app.core import proposta_pdf
    from app.models import Cliente, Proposta

    cli = Cliente(nome="ACME", municipio="Recife", estado="PE", cep=None)
    p = Proposta(id=3, numero=103)

    html = proposta_pdf.montar_html(p, cli)

    assert "CEP:" not in html
    assert "Recife - PE" in html


def test_montar_html_override_so_municipio_mantem_estado_do_cadastro():
    from app.core import proposta_pdf
    from app.models import Cliente, Proposta

    # cadastro Recife/PE (o remetente do letreiro do PDF tambem e Recife/PE,
    # entao a asserção-chave e a combinacao completa, nao so a presenca da UF)
    cli = Cliente(nome="ACME", municipio="Recife", estado="PE")
    p = Proposta(id=10, numero=110, cliente_override={"municipio": "Olinda"})

    html = proposta_pdf.montar_html(p, cli)

    assert "Olinda - PE" in html
    assert "Olinda - SP" not in html


def test_montar_html_override_so_estado_mantem_municipio_do_cadastro():
    from app.core import proposta_pdf
    from app.models import Cliente, Proposta

    cli = Cliente(nome="ACME", municipio="Recife", estado="PE")
    p = Proposta(id=11, numero=111, cliente_override={"estado": "SP"})

    html = proposta_pdf.montar_html(p, cli)

    assert "Recife - SP" in html


def test_montar_html_override_municipio_e_estado_substitui_os_dois():
    from app.core import proposta_pdf
    from app.models import Cliente, Proposta

    cli = Cliente(nome="ACME", municipio="Recife", estado="PE")
    p = Proposta(
        id=12, numero=112,
        cliente_override={"municipio": "Olinda", "estado": "SP"},
    )

    html = proposta_pdf.montar_html(p, cli)

    assert "Olinda - SP" in html
    assert "Olinda - PE" not in html
    assert "Recife - SP" not in html


def test_montar_html_endereco_entrega_cep_formatado():
    from app.core import proposta_pdf
    from app.models import Cliente, Proposta

    cli = Cliente(nome="ACME", cgc="08857492000148")
    p = Proposta(
        id=13,
        numero=113,
        endereco_entrega_diferente=True,
        endereco_entrega={
            "rua": "Rua Destino",
            "municipio": "Recife",
            "estado": "PE",
            "cep": "50030230",
        },
    )

    html = proposta_pdf.montar_html(p, cli)

    assert "CEP: 50030-230" in html
    assert "CEP: 50030230" not in html
