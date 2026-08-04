"""QR codes dos certificados auxiliares (gas, termohigrometro, barometro) que vao no
rodape do certificado de calibracao.

Modulo PURO: sem Session, sem I/O, sem import de app.models. Descobrir QUAIS documentos
entram e qual e a URL de cada um e trabalho de `core/certificado_config.documentos_qr`;
aqui so se transforma (rotulo, url) em HTML.
"""
from collections.abc import Sequence
from html import escape as _html_escape

import segno

# Escala do SVG gerado pelo segno. Nao decide o tamanho impresso — quem decide e o
# width/height do <img> abaixo, porque SVG e vetorial. Fica alta so para o arquivo nao
# nascer minusculo e depender de upscale em algum leitor de PDF menos cuidadoso.
_ESCALA = 5

# Lado da imagem no HTML, em px. E ISTO que define o tamanho impresso.
#
# 04/08/2026: subiu de 90 para 200 porque um celular do laboratorio nao conseguiu ler.
# A conta que importa e o tamanho FISICO de cada modulo do QR, nao o numero de px.
# A URL de producao gera um simbolo de 49 modulos (versao 6, nivel L). Medido no PDF
# renderizado: 35,4 mm de lado / 49 modulos = ~0,72 mm por modulo.
# Com 90 px dava 0,39 mm, abaixo do minimo pratico (~0,6 mm) para camera de celular.
# Para remedir depois de qualquer mudanca: renderizar o PDF, `pdftoppm -r 300`, e ler o
# tamanho do simbolo com um decodificador — a olho nao da para saber se encolheu.
#
# Nao subir o nivel de correcao para M achando que ajuda a LER: M leva o simbolo a 57
# modulos, o que deixa cada modulo MENOR no mesmo espaco. M protege contra sujeira e
# dobra no papel, nao contra modulo pequeno.
#
# Teto: os tres QRs tem de caber lado a lado sem empurrar o certificado para uma
# terceira pagina — trocar tres documentos impressos por uma folha a mais em todo
# certificado comeria parte do ganho que motivou a funcionalidade.
_LADO_PX = 200


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
