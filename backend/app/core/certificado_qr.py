"""QR codes dos certificados auxiliares (gas, termohigrometro, barometro) que vao no
rodape do certificado de calibracao.

Modulo PURO: sem Session, sem I/O, sem import de app.models. Descobrir QUAIS documentos
entram e qual e a URL de cada um e trabalho de `core/certificado_config.documentos_qr`;
aqui so se transforma (rotulo, url) em HTML.
"""
from collections.abc import Sequence
from html import escape as _html_escape

import segno

# Escala do QR. 3 da ~90px de lado no PDF: grande o bastante para a camera de um celular
# pegar e pequeno o bastante para os tres caberem lado a lado no rodape da pagina 2 —
# que e o requisito, porque o pedido nasceu de economizar papel.
_ESCALA = 3

# Lado da imagem no HTML, em px. E SVG, entao reamostragem nao e o problema — o que
# importa e o tamanho: pequeno o bastante para os tres QRs caberem lado a lado no
# rodape sem empurrar o certificado para uma terceira pagina, que e o ponto de toda
# a funcionalidade (parar de imprimir os documentos auxiliares separados).
_LADO_PX = 90


def qr_data_uri(url: str) -> str:
    """URL -> QR como SVG num data: URI, pronto para o `src` de um `<img>`.

    SVG e nao PNG porque o certificado e IMPRESSO: vetor sai nitido em qualquer
    resolucao, enquanto um PNG de poucos pixels borra no papel — e QR borrado nao
    escaneia. De quebra, dispensa Pillow.
    """
    return segno.make(url).svg_data_uri(scale=_ESCALA)


def bloco_qr(itens: Sequence[tuple[str, str]]) -> str:
    """Os QRs lado a lado, cada um com seu rotulo acima. Sem itens devolve ''.

    O retorno entra no certificado SEM passar pelo escape geral (e um token
    estrutural), entao o escape do rotulo tem de acontecer aqui. Hoje os rotulos sao
    constantes do codigo; o dia em que virarem configuraveis, o escape ja esta no lugar.
    """
    if not itens:
        return ""
    celulas = "".join(
        '<td style="text-align:center; padding:0 10px; border:0">'
        f'<div style="font-size:11px; margin-bottom:3px">{_html_escape(rotulo)}</div>'
        f'<img src="{qr_data_uri(url)}" width="{_LADO_PX}" height="{_LADO_PX}" '
        f'alt="{_html_escape(rotulo)}" />'
        "</td>"
        for rotulo, url in itens
    )
    return (
        '<table align="center" cellpadding="0" cellspacing="0" '
        'style="border:0; margin:0 auto"><tbody><tr>'
        f"{celulas}"
        "</tr></tbody></table>"
    )
