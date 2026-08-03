from app.core.certificado_qr import bloco_qr, qr_data_uri

URL = "https://gestor.exemplo.com/publico/certificado-geral/1?t=abc123"


def test_qr_data_uri_e_svg_pronto_para_src_de_img():
    uri = qr_data_uri(URL)
    # SVG e nao PNG: o certificado e IMPRESSO, e vetor sai nitido em qualquer
    # resolucao. QR borrado nao escaneia.
    assert uri.startswith("data:image/svg+xml")


def test_qr_data_uri_e_deterministico_para_a_mesma_url():
    # Sustenta os testes que provam QUAL url foi codificada comparando o data URI.
    assert qr_data_uri(URL) == qr_data_uri(URL)


def test_qr_data_uri_muda_quando_a_url_muda():
    assert qr_data_uri(URL) != qr_data_uri(URL + "x")


def test_bloco_com_tres_itens_traz_os_tres_rotulos_e_tres_imagens():
    html = bloco_qr([
        ("Certificado do Gás", URL),
        ("Certificado do Termohigrômetro Digital", URL + "/2"),
        ("Certificado do Barômetro Digital", URL + "/3"),
    ])
    assert "Certificado do Gás" in html
    assert "Certificado do Termohigrômetro Digital" in html
    assert "Certificado do Barômetro Digital" in html
    assert html.count("<img") == 3


def test_bloco_codifica_a_url_recebida_em_cada_qr():
    # Prova QUAL url entrou em cada QR sem precisar de leitor optico: o data URI e
    # deterministico, entao gerar o esperado e procurar no bloco basta.
    html = bloco_qr([("Certificado do Gás", URL)])
    assert qr_data_uri(URL) in html


def test_bloco_sem_itens_e_string_vazia():
    # Nenhum documento configurado: o certificado sai sem o bloco, e nao com uma
    # tabela vazia ocupando espaco no rodape.
    assert bloco_qr([]) == ""


def test_bloco_com_um_item_so_sai_com_um_qr():
    html = bloco_qr([("Certificado do Gás", URL)])
    assert html.count("<img") == 1


def test_bloco_escapa_o_rotulo():
    # Hoje os rotulos sao constantes do codigo, mas o bloco entra no certificado SEM
    # passar pelo escape geral — o escape tem de estar aqui desde o inicio.
    html = bloco_qr([("<script>alerta</script>", URL)])
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
