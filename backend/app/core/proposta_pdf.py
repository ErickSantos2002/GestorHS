"""Motor de geração do HTML da Proposta Técnica e orquestração do PDF via
Playwright (renderizar_pdf, em app/core/certificado_pdf.py).

Portado de hsgrowth-sistema/backend/app/services/proposal_pdf_service.py:
mesma estrutura de seções (cabeçalho H&S, endereço, itens, outros itens
sanitizados, totais, condições, assinatura) e o mesmo CSS (verbatim). Duas
diferenças de domínio em relação à fonte:
- título "Proposta Técnica" (a fonte usa "Proposta Comercial");
- o Cliente do GestorHS não tem entidade Person: o "aos cuidados de" vem do
  campo texto `Proposta.contato` (sem fallback de pessoa).
"""
import base64
import re
from decimal import Decimal
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.core.certificado_pdf import renderizar_pdf
from app.core.config import settings
from app.models.proposta import Proposta

UPLOAD_DIR = Path(settings.UPLOAD_DIR)

# Logo H&S embutida no cabeçalho do PDF (base64), se o arquivo existir. Para
# trocar/adicionar a logo, basta colocar o arquivo em app/assets/hs_logo.png —
# nenhuma alteração de código é necessária. Sem o arquivo, o cabeçalho sai sem
# logo (fallback silencioso, igual ao comportamento portado do growthhs).
_LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "hs_logo.png"
_logo_cache: Optional[str] = None


def _logo_img_tag() -> str:
    """<img> com a logo H&S embutida (data URI). Retorna '' se o arquivo não existir."""
    global _logo_cache
    if _logo_cache is None:
        try:
            b64 = base64.b64encode(_LOGO_PATH.read_bytes()).decode("ascii")
            _logo_cache = f'<img class="header-logo" src="data:image/png;base64,{b64}" alt="H&amp;S" />'
        except Exception as e:  # arquivo ausente/ilegível → cabeçalho sem logo
            print(f"[PROPOSTA-PDF] logo nao carregada ({_LOGO_PATH}): {e}")
            _logo_cache = ""
    return _logo_cache


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_moeda(valor) -> str:
    """Formata um valor numérico como R$ 1.234,56 (pt-BR)."""
    if valor is None:
        return "R$ 0,00"
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return "R$ 0,00"
    # Formata com separadores pt-BR
    formatado = f"{v:,.2f}"          # ex.: "1,234.56"
    # Troca separadores: vírgula→placeholder, ponto→vírgula, placeholder→ponto
    formatado = formatado.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatado}"


def _fmt_data(d) -> str:
    """Formata um objeto date como dd/mm/aaaa."""
    if d is None:
        return "—"
    try:
        return d.strftime("%d/%m/%Y")
    except Exception:
        return str(d)


def _esc(texto: Optional[str]) -> str:
    """Escapa texto simples para uso seguro em HTML."""
    if not texto:
        return ""
    return (
        str(texto)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _fmt_documento(doc: Optional[str]) -> str:
    """Formata CPF (11 díg.) ou CNPJ (14 díg.); mantém original se não bater."""
    if not doc:
        return ""
    digitos = re.sub(r"\D", "", str(doc))
    if len(digitos) == 14:
        return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:]}"
    if len(digitos) == 11:
        return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"
    return _esc(doc)


def _sanitizar_html(html: Optional[str]) -> str:
    """
    Sanitização defensiva do HTML do editor rico (outros_itens) antes de
    renderizar no PDF. Remove scripts/estilos, elementos que carregam
    recursos externos (img/iframe/object/embed/link/source/base) e handlers
    de evento on*=. Junto com o filtro anti-SSRF do renderizar_pdf, fecha
    SSRF / leitura de arquivo local via recursos referenciados nesse HTML
    (o editor já sanitiza na entrada; isto é defense-in-depth no sink).
    """
    if not html:
        return ""
    # Blocos com conteúdo
    for tag in ("script", "style", "iframe", "object"):
        html = re.sub(rf"<{tag}[\s\S]*?</{tag}>", "", html, flags=re.IGNORECASE)
    # Elementos "void" que carregam/apontam recursos externos
    html = re.sub(r"<(?:img|link|embed|source|base)\b[^>]*>", "", html, flags=re.IGNORECASE)
    # Handlers de evento inline (onerror, onload, ...)
    html = re.sub(r"""\son\w+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)""", "", html, flags=re.IGNORECASE)
    return html


# ---------------------------------------------------------------------------
# CSS (copiado verbatim de proposal_pdf_service.py:117-337)
# ---------------------------------------------------------------------------

_CSS = """
@page {
    size: A4;
    margin: 1.5cm;
}

* {
    box-sizing: border-box;
}

body {
    font-family: Arial, Helvetica, sans-serif;
    font-size: 10.5px;
    color: #222;
    margin: 0;
    padding: 0;
    line-height: 1.5;
}

/* ── Cabeçalho ── */
.header {
    display: table;
    width: 100%;
    padding-bottom: 8px;
    border-bottom: 1px solid #333;
    margin-bottom: 12px;
}

.header-logo-area {
    display: table-cell;
    width: 38%;
    vertical-align: middle;
}

.header-logo {
    max-height: 52px;
    max-width: 100%;
    height: auto;
}

.header-company {
    display: table-cell;
    width: 62%;
    text-align: right;
    vertical-align: top;
}

.header-company .company-name {
    font-size: 10.5px;
    font-weight: bold;
    margin-bottom: 2px;
}

.header-company .company-line {
    font-size: 9.5px;
    color: #333;
    line-height: 1.45;
}

/* ── Título ── */
.titulo {
    text-align: center;
    font-size: 16px;
    font-weight: bold;
    margin: 10px 0 14px 0;
}

/* ── Linha Para / Aos cuidados de ── */
.para-linha {
    font-size: 10.5px;
    margin: 0 0 10px 0;
}

/* ── Seção genérica ── */
.secao {
    margin-bottom: 10px;
}

.secao-titulo {
    font-size: 12px;
    font-weight: bold;
    border-bottom: 1px solid #333;
    padding-bottom: 3px;
    margin-top: 14px;
    margin-bottom: 4px;
    /* sentence case — sem text-transform */
}

/* ── Caixa com borda ── */
.box {
    border: 1px solid #999;
    padding: 8px 10px;
    margin-top: 4px;
    font-size: 10px;
    line-height: 1.6;
}

/* ── Endereço em 1 caixa dividida ao meio (Cliente | Entrega) ── */
table.endereco-tbl {
    width: 100%;
    border-collapse: collapse;
    border: 1px solid #999;
    margin-top: 4px;
    table-layout: fixed;      /* largura fixa 50/50 */
    font-size: 10px;
    line-height: 1.6;
}
table.endereco-tbl td.ec-cell {
    width: 50%;
    vertical-align: top;
    padding: 8px 10px;
    border-left: 1px solid #999;   /* linha divisória no meio */
    word-wrap: break-word;
}
table.endereco-tbl td.ec-cell:first-child {
    border-left: none;
}
.ec-title {
    font-weight: bold;
    margin-bottom: 4px;
}

/* ── Tabela de itens ── */
table.itens {
    width: 100%;
    border-collapse: collapse;
    margin-top: 4px;
    font-size: 10px;
}

table.itens th {
    background: #f2f2f2;
    border: 1px solid #ccc;
    padding: 5px 7px;
    text-align: left;
    font-weight: bold;
}

table.itens td {
    border: 1px solid #ccc;
    padding: 5px 7px;
    vertical-align: top;
}

table.itens td.right,
table.itens th.right {
    text-align: right;
}

.itens-rodape {
    border: 1px solid #ccc;
    border-top: none;
    padding: 6px 8px;
    font-size: 10px;
    color: #333;
    text-align: right;
}

/* ── Tabela de 2 colunas (Condições gerais) ── */
table.cond2 {
    width: 100%;
    border-collapse: collapse;
    margin-top: 4px;
    font-size: 10px;
}
table.cond2 td {
    border: 1px solid #ccc;
    padding: 5px 8px;
    vertical-align: top;
}
table.cond2 td:first-child {
    background: #f7f7f7;
    width: 42%;
}

/* ── Tabela de totais (fechamento) ── */
table.totais {
    width: 100%;
    border-collapse: collapse;
    margin-top: 4px;
    font-size: 10px;
}

table.totais th {
    background: #f2f2f2;
    border: 1px solid #ccc;
    padding: 5px 7px;
    text-align: left;
    font-weight: bold;
}

table.totais td {
    border: 1px solid #ccc;
    padding: 5px 7px;
    vertical-align: top;
}

table.totais td.right,
table.totais th.right {
    text-align: right;
}

/* ── Outros itens (HTML do Quill) ── */
.outros-itens-conteudo {
    font-size: 10px;
    line-height: 1.6;
}

.outros-itens-conteudo p { margin: 0 0 4px 0; }
.outros-itens-conteudo ul, .outros-itens-conteudo ol {
    margin: 0 0 4px 1em;
    padding: 0;
}

/* ── Assinatura ── */
.assinatura {
    margin-top: 18px;
    font-size: 10.5px;
    line-height: 1.8;
}
"""


def montar_html(proposta, cliente) -> str:
    """Monta o HTML COMPLETO (documento com <html>/<head>/<body>) da Proposta
    Técnica, pronto para `renderizar_pdf`. `proposta` é o modelo `Proposta`
    (com `.itens` carregado); `cliente` é o `Cliente` vinculado (ou None)."""
    itens = proposta.itens or []

    # ── Dados do cliente ──
    cliente_display = "—"
    cliente_documento = ""
    cliente_endereco = ""
    cliente_cidade_estado = ""
    cliente_telefone = ""
    cliente_email = ""

    if cliente:
        cliente_display = _esc(cliente.nome or "—")
        cliente_documento = _fmt_documento(cliente.cgc or cliente.cpf)
        cliente_endereco = _esc(cliente.endereco or "")
        municipio = cliente.municipio or ""
        estado = cliente.estado or ""
        if municipio and estado:
            cliente_cidade_estado = _esc(f"{municipio} - {estado}")
        elif municipio:
            cliente_cidade_estado = _esc(municipio)
        elif estado:
            cliente_cidade_estado = _esc(estado)
        cliente_email = _esc(cliente.email or "")
        cliente_telefone = _esc(cliente.celular or cliente.whatsapp or cliente.telefones or "")

    # ── "Aos cuidados de" — sem entidade Person no Gestor: campo texto da proposta ──
    aos_cuidados = proposta.contato or ""

    # ── Override editável (dados editados só nesta proposta) ──
    # Campos preenchidos substituem os do cadastro; os vazios mantêm o do Cliente.
    ov = proposta.cliente_override or {}
    if ov.get("nome"):
        cliente_display = _esc(ov["nome"])
    if ov.get("documento"):
        cliente_documento = _fmt_documento(ov["documento"])
    if ov.get("endereco"):
        cliente_endereco = _esc(ov["endereco"])
    if ov.get("municipio") or ov.get("estado"):
        _m = ov.get("municipio") or ""
        _e = ov.get("estado") or ""
        cliente_cidade_estado = _esc(f"{_m} - {_e}" if _m and _e else (_m or _e))
    if ov.get("email"):
        cliente_email = _esc(ov["email"])
    if ov.get("telefone"):
        cliente_telefone = _esc(ov["telefone"])
    if ov.get("contato"):
        aos_cuidados = ov["contato"]

    aos_cuidados_esc = _esc(aos_cuidados) or "—"

    # Linha fone/email do box de endereço
    fone_email_parts = []
    if cliente_telefone:
        fone_email_parts.append(f"Fone: {cliente_telefone}")
    if cliente_email:
        fone_email_parts.append(f"E-mail: {cliente_email}")
    fone_email_line = " &nbsp;&middot;&nbsp; ".join(fone_email_parts) if fone_email_parts else ""

    # ── Itens ──
    total_itens = Decimal("0")
    soma_qtds = Decimal("0")
    linhas_html = ""
    for i, item in enumerate(itens, 1):
        qtd = Decimal(str(item.quantidade or 0))
        preco_un = float(item.preco_un or 0)
        total_item = float(item.total or 0)
        total_itens += Decimal(str(total_item))
        soma_qtds += qtd

        # Formata quantidade: 4 decimais, separadores pt-BR
        qtd_str = f"{float(qtd):,.4f}".replace(",", "X").replace(".", ",").replace("X", ".")

        linhas_html += f"""
        <tr>
          <td>{i}</td>
          <td>{_esc(item.descricao)}</td>
          <td>{_esc(item.sku or "")}</td>
          <td class="right">{qtd_str}</td>
          <td>{_esc(item.unidade or "")}</td>
          <td class="right">{_fmt_moeda(preco_un)}</td>
          <td class="right">{_fmt_moeda(total_item)}</td>
        </tr>"""

    n_itens = len(itens)
    soma_qtds_str = f"{float(soma_qtds):,.4f}".replace(",", "X").replace(".", ",").replace("X", ".")

    # ── Financeiro ──
    desconto = Decimal(str(proposta.desconto or 0))
    frete = Decimal(str(proposta.frete or 0))
    total_proposta = total_itens + frete - desconto

    # ── Outros itens (HTML sanitizado) ──
    outros_itens_html = _sanitizar_html(proposta.outros_itens or "")

    # ── Número da proposta ──
    numero_str = str(proposta.numero) if proposta.numero else "—"

    # ── Data da proposta ──
    data_proposta = _fmt_data(proposta.data)

    # ── Endereço de entrega (diferente) — linhas p/ o bloco de 2 colunas ──
    linhas_entrega = ""
    if proposta.endereco_entrega_diferente and proposta.endereco_entrega:
        de = proposta.endereco_entrega

        # Fallback: se existe campo "texto" (endereço em texto livre), usa-o
        texto_livre = de.get("texto")
        if texto_livre and str(texto_livre).strip():
            linhas_entrega = _esc(texto_livre).replace("\n", "<br>")
        else:
            # Caso contrário, monta a partir das chaves estruturadas
            def de_get(key):
                return _esc(str(de.get(key, "") or ""))

            linha_rua = de_get('rua')
            if de.get('numero'):
                linha_rua += f", {de_get('numero')}"
            if de.get('complemento'):
                linha_rua += f" {de_get('complemento')}"

            cidade_estado_cep = de_get('municipio')
            if de.get('estado'):
                cidade_estado_cep += f"/{de_get('estado')}"
            if de.get('cep'):
                cidade_estado_cep += f" — CEP: {de_get('cep')}"

            if de_get('destinatario'):
                linhas_entrega += f"{de_get('destinatario')}<br>"
            if linha_rua:
                linhas_entrega += f"{linha_rua}<br>"
            if de_get('bairro'):
                linhas_entrega += f"Bairro: {de_get('bairro')}<br>"
            if cidade_estado_cep:
                linhas_entrega += f"{cidade_estado_cep}<br>"
            if de.get('inscricao_estadual'):
                linhas_entrega += f"Insc. estadual: {de_get('inscricao_estadual')}<br>"
            if de.get('documento'):
                linhas_entrega += f"CPF/CNPJ: {de_get('documento')}<br>"
            if de.get('telefone'):
                linhas_entrega += f"Fone: {de_get('telefone')}<br>"

    # ── Condições gerais (linhas da tabela label | valor) ──
    def _cg_linha(label, valor):
        return f"<tr><td><strong>{label}</strong></td><td>{valor}</td></tr>" if valor else ""
    cond_gerais_linhas = (
        _cg_linha("Forma de envio", _esc(proposta.forma_envio or ""))
        + _cg_linha("Forma de frete", _esc(proposta.forma_frete or ""))
        + _cg_linha("Validade da proposta", f"{proposta.validade_dias} dias" if proposta.validade_dias else "")
        + _cg_linha("Data prevista de entrega", _fmt_data(proposta.data_entrega) if proposta.data_entrega else "")
        + _cg_linha("Prazo de entrega", _esc(proposta.descricao_entrega or ""))
    )

    # ── Assinatura ──
    assinatura_html = ""
    if proposta.assinatura:
        assinatura_esc = _esc(proposta.assinatura).replace("\n", "<br>")
        assinatura_html = f"""
<div class="assinatura">{assinatura_esc}</div>"""

    # ── Box do endereço do cliente ──
    linhas_endereco = ""
    if cliente_documento:
        linhas_endereco += f"{cliente_documento}<br>"
    if cliente_endereco:
        linhas_endereco += f"{cliente_endereco}<br>"
    if cliente_cidade_estado:
        linhas_endereco += f"{cliente_cidade_estado}<br>"
    if fone_email_line:
        linhas_endereco += fone_email_line
    if not linhas_endereco:
        linhas_endereco = "—"

    # ── Bloco de endereço: 1 caixa dividida ao meio (Cliente | Entrega) quando há entrega diferente ──
    if proposta.endereco_entrega_diferente and linhas_entrega:
        bloco_endereco = f"""
<div class="secao">
  <table class="endereco-tbl">
    <tr>
      <td class="ec-cell">
        <div class="ec-title">Endereço do Cliente</div>
        {linhas_endereco}
      </td>
      <td class="ec-cell">
        <div class="ec-title">Endereço de Entrega</div>
        {linhas_entrega}
      </td>
    </tr>
  </table>
</div>"""
    else:
        bloco_endereco = f"""
<div class="secao">
  <div class="secao-titulo">Endereço do Cliente</div>
  <div class="box">{linhas_endereco}</div>
</div>"""

    # ── Introdução ──
    bloco_intro = ""
    if proposta.intro:
        bloco_intro = f"""
<div class="secao">
  <div class="secao-titulo">Introdução</div>
  <p>{_esc(proposta.intro)}</p>
</div>"""

    # ── Outros itens ──
    bloco_outros = ""
    if outros_itens_html.strip():
        bloco_outros = f"""
<div class="secao">
  <div class="secao-titulo">Outros itens ou serviços</div>
  <div class="box"><div class="outros-itens-conteudo">{outros_itens_html}</div></div>
</div>"""

    # ── Condições comerciais block (Dias | Valor | Obs) ──
    bloco_cond_comerciais = ""
    if proposta.condicao_pagamento:
        bloco_cond_comerciais = f"""
<div class="secao">
  <div class="secao-titulo">Condições comerciais</div>
  <table class="totais">
    <thead><tr><th style="width:100px">Dias</th><th class="right" style="width:130px">Valor</th><th>Obs.</th></tr></thead>
    <tbody><tr><td>{_esc(proposta.condicao_pagamento)}</td><td class="right">{_fmt_moeda(total_proposta)}</td><td></td></tr></tbody>
  </table>
</div>"""

    # ── Condições gerais block (tabela label | valor) ──
    bloco_cond_gerais = ""
    if cond_gerais_linhas:
        bloco_cond_gerais = f"""
<div class="secao">
  <div class="secao-titulo">Condições gerais</div>
  <table class="cond2"><tbody>{cond_gerais_linhas}</tbody></table>
</div>"""

    # ── Observações ──
    bloco_obs = ""
    if proposta.observacoes:
        bloco_obs = f"""
<div class="secao">
  <div class="secao-titulo">Observações</div>
  <div class="box">{_esc(proposta.observacoes).replace(chr(10), '<br>')}</div>
</div>"""

    # ── Tabela de totais (fechamento) ──
    bloco_totais = f"""
<div class="secao">
  <div class="secao-titulo">Totais</div>
  <table class="totais">
    <thead>
      <tr>
        <th>Data</th>
        <th class="right">Total dos itens</th>
        <th class="right">Desconto</th>
        <th class="right">Frete</th>
        <th class="right">Total da proposta</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>{data_proposta}</td>
        <td class="right">{_fmt_moeda(total_itens)}</td>
        <td class="right">{_fmt_moeda(desconto)}</td>
        <td class="right">{_fmt_moeda(frete)}</td>
        <td class="right"><strong>{_fmt_moeda(total_proposta)}</strong></td>
      </tr>
    </tbody>
  </table>
</div>"""

    # ── Monta o HTML completo ──
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Proposta Técnica Nº {numero_str}</title>
  <style>{_CSS}</style>
</head>
<body>

<!-- ══ Cabeçalho ══ -->
<div class="header">
  <div class="header-logo-area">
    {_logo_img_tag()}
  </div>
  <div class="header-company">
    <div class="company-name">HEALTH &amp; SAFETY DISTRIBUICAO IMPORTACAO E EXPORTACAO DE INST</div>
    <div class="company-line">08.857.492/0001-48</div>
    <div class="company-line">www.healthsafety.com.br</div>
    <div class="company-line">(81) 3052-3350</div>
    <div class="company-line">R VISCONDESSA DO LIVRAMENTO, 54, SALA G &mdash; DERBY, Recife - PE &mdash; 52.010-065</div>
  </div>
</div>

<!-- ══ Título ══ -->
<div class="titulo">Proposta Técnica N&ordm; {_esc(numero_str)}</div>

<!-- ══ Para / Aos cuidados de ══ -->
<p class="para-linha">
  <strong>Para:</strong> {cliente_display}
  &nbsp;&nbsp;&middot;&nbsp;&nbsp;
  <strong>Aos cuidados de:</strong> {aos_cuidados_esc}
</p>

<!-- ══ Endereço do cliente (+ entrega, se diferente) ══ -->
{bloco_endereco}

{bloco_intro}

<!-- ══ Itens ══ -->
<div class="secao">
  <div class="secao-titulo">Itens de produto ou serviço</div>
  <table class="itens">
    <thead>
      <tr>
        <th style="width:26px">N&ordm;</th>
        <th>Item</th>
        <th style="width:88px">SKU / NCM</th>
        <th class="right" style="width:52px">Qtd</th>
        <th style="width:38px">Un</th>
        <th class="right" style="width:82px">Preço un</th>
        <th class="right" style="width:82px">Total</th>
      </tr>
    </thead>
    <tbody>
      {linhas_html if linhas_html else '<tr><td colspan="7" style="text-align:center;color:#888">Nenhum item</td></tr>'}
    </tbody>
  </table>
  <div class="itens-rodape">
    Número de itens: {n_itens}
    &nbsp;&nbsp;&middot;&nbsp;&nbsp;
    Soma das quantidades: {soma_qtds_str}
    &nbsp;&nbsp;&middot;&nbsp;&nbsp;
    Total dos itens: <strong>{_fmt_moeda(total_itens)}</strong>
  </div>
</div>

{bloco_outros}

{bloco_totais}

{bloco_cond_comerciais}

{bloco_cond_gerais}

{bloco_obs}

{assinatura_html}

</body>
</html>"""

    return html


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def gerar_pdf(db: Session, proposta_id: int) -> bytes:
    """Busca a proposta pelo ID (não-deletada), monta o HTML e renderiza o
    PDF via Playwright (documento completo → scale 1.0, sem margem extra;
    o @page 1.5cm do CSS já cuida da margem)."""
    proposta = (
        db.query(Proposta)
        .filter(Proposta.id == proposta_id, Proposta.is_deleted.is_(False))
        .first()
    )
    if not proposta:
        raise ValueError(f"Proposta {proposta_id} nao encontrada")

    cliente = proposta.cliente_rel
    html = montar_html(proposta, cliente)
    return renderizar_pdf(html, scale=1.0, margin_mm=0)


# ---------------------------------------------------------------------------
# Histórico de versões (PDF arquivado por versão)
# ---------------------------------------------------------------------------

def arquivar_pdf_versao(db: Session, proposta, numero_versao: int) -> Optional[str]:
    """
    Gera o PDF do estado ATUAL da proposta (pré-edição) e o arquiva em
    uploads/propostas/{id}/v{n}.pdf. Retorna o caminho relativo ou None se falhar.
    """
    try:
        pdf = gerar_pdf(db, proposta.id)
        prop_dir = UPLOAD_DIR / "propostas" / str(proposta.id)
        prop_dir.mkdir(parents=True, exist_ok=True)
        rel_path = f"propostas/{proposta.id}/v{numero_versao}.pdf"
        with open(UPLOAD_DIR / rel_path, "wb") as f:
            f.write(pdf)
        return rel_path
    except Exception as e:
        print(f"[PROPOSTA-PDF] erro ao arquivar PDF da versao {numero_versao} (proposta {proposta.id}): {e}")
        return None


def ler_pdf_versao(pdf_path: Optional[str]) -> bytes:
    """Lê o PDF arquivado de uma versão. Levanta FileNotFoundError se não existir."""
    if not pdf_path:
        raise FileNotFoundError("PDF desta versao nao disponivel")
    fp = UPLOAD_DIR / pdf_path
    if not fp.exists():
        raise FileNotFoundError("Arquivo de PDF da versao nao encontrado")
    return fp.read_bytes()
