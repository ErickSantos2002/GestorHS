"""Converte o HTML de um certificado (os_certificados.html) em PDF A4 usando
Chromium headless via Playwright. O HTML do certificado é confiável (modelo de
admin/lab + valores já escapados na geração), então entra no documento sem escapar.

Defesa contra SSRF: o certificado carrega imagens externas legítimas (logo/selo
ISO em URL pública), então a rede do renderer fica LIGADA — mas todo request para
endereço privado/loopback/link-local/reservado (ex.: metadata de nuvem
169.254.169.254, serviços internos) é abortado antes de sair. Assim um template
malicioso (só editável por Admin/Laboratório) não consegue alcançar a rede interna."""
import ipaddress
import socket
from urllib.parse import urlparse

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


def host_bloqueado(host: str | None) -> bool:
    """True se o host resolve para um endereço não-roteável publicamente
    (privado/loopback/link-local/reservado/multicast). Falha de resolução
    também bloqueia (fail-closed)."""
    if not host:
        return True
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return True
    for info in infos:
        try:
            addr = ipaddress.ip_address(info[4][0])
        except ValueError:
            return True
        if (addr.is_private or addr.is_loopback or addr.is_link_local
                or addr.is_reserved or addr.is_multicast or addr.is_unspecified):
            return True
    return False


def _filtrar_requisicao(route) -> None:
    """Aborta requests com esquema não-http(s) ou destino não-público (anti-SSRF)."""
    parsed = urlparse(route.request.url)
    if parsed.scheme not in ("http", "https") or host_bloqueado(parsed.hostname):
        route.abort()
    else:
        route.continue_()


def html_para_pdf(html_cert: str) -> bytes:
    """Renderiza o certificado em PDF A4 com Chromium headless.
    Levanta exceção se o navegador falhar (o endpoint converte em 500)."""
    from playwright.sync_api import sync_playwright

    documento = montar_documento(html_cert)
    # --no-sandbox: o container roda como root; mitigação principal (SSRF) é o
    # filtro de rede abaixo. Rodar como usuário sem privilégio é follow-up de infra.
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        try:
            page = browser.new_page()
            page.route("**/*", _filtrar_requisicao)  # bloqueia rede interna (SSRF)
            page.set_content(documento, wait_until="networkidle")
            pdf = page.pdf(
                format="A4",
                print_background=True,
                margin={"top": "10mm", "bottom": "10mm", "left": "10mm", "right": "10mm"},
            )
        finally:
            browser.close()
    return pdf
