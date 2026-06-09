def test_montar_documento_embute_corpo_e_a4():
    from app.core.certificado_pdf import montar_documento
    doc = montar_documento("<table><tr><td>Cliente: ACME</td></tr></table>")
    assert "Cliente: ACME" in doc          # corpo embutido sem escapar
    assert "<table>" in doc
    assert "@page" in doc                  # CSS de impressão presente
    assert "A4" in doc
    assert doc.strip().lower().startswith("<!doctype html")


def test_montar_documento_corpo_vazio():
    from app.core.certificado_pdf import montar_documento
    doc = montar_documento("")
    assert "@page" in doc and "A4" in doc


def test_host_bloqueado_enderecos_internos():
    from app.core.certificado_pdf import host_bloqueado
    # loopback, privados, link-local (metadata de nuvem), reservado
    assert host_bloqueado("127.0.0.1")
    assert host_bloqueado("localhost")
    assert host_bloqueado("10.0.0.5")
    assert host_bloqueado("192.168.1.1")
    assert host_bloqueado("169.254.169.254")   # metadata AWS/GCP/Azure
    assert host_bloqueado(None)
    assert host_bloqueado("")


def test_host_bloqueado_permite_publico():
    from app.core.certificado_pdf import host_bloqueado
    assert host_bloqueado("8.8.8.8") is False   # IP público roteável
