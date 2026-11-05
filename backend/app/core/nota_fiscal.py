"""Convencao de armazenamento da nota fiscal (pura). Fonte unica da verdade:
o subdir em disco e o media type sao definidos AQUI e consumidos pelos endpoints."""
import re
from pathlib import Path


def subdir(ordem_id: int) -> str:
    return f"notas-fiscais/{ordem_id}"


def subdir_caixa(caixa_id: int) -> str:
    return f"notas-fiscais/caixa/{caixa_id}"


def subdir_nota(ordem_id: int | None, caixa_id: int) -> str:
    """Onde estao os arquivos de uma nota da tabela `notas_fiscais`.

    `ordem_id` preenchido e' marca do backfill da migracao 0029: aquela nota
    reaproveita os arquivos que ja estavam no subdir da OS. Nota criada pela
    tela nasce com `ordem` nulo e vive no subdir da caixa. Nenhum arquivo e'
    movido de lugar — dai as duas convencoes conviverem.
    """
    return subdir(ordem_id) if ordem_id else subdir_caixa(caixa_id)


# Chave de acesso da NF-e (44 digitos): no atributo Id do infNFe ("NFe" + chave)
# ou no chNFe do protocolo de autorizacao.
_CHAVE = re.compile(rb'Id\s*=\s*["\']NFe(\d{44})["\']|<chNFe>\s*(\d{44})\s*</chNFe>')


def chave_de_acesso(conteudo: bytes | None) -> str | None:
    if not conteudo:
        return None
    m = _CHAVE.search(conteudo)
    return (m.group(1) or m.group(2)).decode() if m else None


def ler_xml(caminho: Path, basename: str) -> bytes | None:
    """Conteudo do arquivo quando ele e' o XML (para achar a chave); None no PDF.

    Unico ponto com I/O deste modulo — so o nome do download depende dele."""
    if not basename.lower().endswith(".xml"):
        return None
    try:
        return caminho.read_bytes()
    except OSError:
        return None


def nome_download_nota(numero: str, basename: str, conteudo: bytes | None = None) -> str:
    """Nome do arquivo no download.

    O XML sai como `<chave de acesso>.xml` — o nome original do emissor, e o
    unico que o VIPP (postagem da expedicao) aceita; "nota-fiscal-..." ele
    recusa. Sem chave (ex.: NFS-e), sai so o numero da nota, sem o prefixo.
    """
    xml = basename.lower().endswith(".xml")
    if xml and (chave := chave_de_acesso(conteudo)):
        return f"{chave}.xml"
    # o numero e' digitado pelo Financeiro e vai parar no Content-Disposition:
    # sai daqui reduzido a caracteres de nome de arquivo.
    seguro = re.sub(r"[^A-Za-z0-9._-]", "-", numero.strip()) or "s-n"
    return f"{seguro}.xml" if xml else f"nota-fiscal-{seguro}.pdf"


def media_type(basename: str) -> str:
    """Sempre um tipo que o navegador NAO renderiza inline.

    O XML da NF e conteudo enviado por usuario: servido como application/xml ele
    executaria <script> (polyglot XML/XHTML). Como nada precisa renderiza-lo no
    navegador, devolvemos octet-stream — o navegador so baixa.
    """
    return "application/octet-stream" if basename.lower().endswith(".xml") else "application/pdf"


def nome_download(ordem_id: int, basename: str, conteudo: bytes | None = None) -> str:
    ext = ".xml" if basename.lower().endswith(".xml") else ".pdf"
    if ext == ".xml" and (chave := chave_de_acesso(conteudo)):
        return f"{chave}.xml"
    return f"nota-fiscal-{ordem_id}{ext}"
