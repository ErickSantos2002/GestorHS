"""Converte o HTML de um certificado (os_certificados.html) em PDF A4 usando
Chromium headless via Playwright. O HTML do certificado é confiável (modelo de
admin/lab + valores já escapados na geração), então entra no documento sem escapar."""

_DOCUMENTO = """<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<style>
  @page {{ size: A4; margin: 10mm; }}
  html, body {{ margin: 0; padding: 0; background: #fff; color: #000; }}
  * {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
</style>
</head>
<body>
{corpo}
</body>
</html>"""


def montar_documento(html_cert: str) -> str:
    """Embrulha o HTML do certificado num documento A4 imprimível."""
    return _DOCUMENTO.format(corpo=html_cert or "")


def html_para_pdf(html_cert: str) -> bytes:
    """Renderiza o certificado em PDF A4 com Chromium headless.
    Levanta exceção se o navegador falhar (o endpoint converte em 500)."""
    from playwright.sync_api import sync_playwright

    documento = montar_documento(html_cert)
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        try:
            page = browser.new_page()
            page.set_content(documento, wait_until="networkidle")
            pdf = page.pdf(
                format="A4",
                print_background=True,
                margin={"top": "10mm", "bottom": "10mm", "left": "10mm", "right": "10mm"},
            )
        finally:
            browser.close()
    return pdf
