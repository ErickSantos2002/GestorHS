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
