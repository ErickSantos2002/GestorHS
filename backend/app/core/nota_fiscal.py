"""Convencao de armazenamento da nota fiscal (pura). Fonte unica da verdade:
o subdir em disco e o media type sao definidos AQUI e consumidos pelos endpoints."""
import re


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


def nome_download_nota(numero: str, basename: str) -> str:
    ext = ".xml" if basename.lower().endswith(".xml") else ".pdf"
    # o numero e' digitado pelo Financeiro e vai parar no Content-Disposition:
    # sai daqui reduzido a caracteres de nome de arquivo.
    seguro = re.sub(r"[^A-Za-z0-9._-]", "-", numero.strip()) or "s-n"
    return f"nota-fiscal-{seguro}{ext}"


def media_type(basename: str) -> str:
    """Sempre um tipo que o navegador NAO renderiza inline.

    O XML da NF e conteudo enviado por usuario: servido como application/xml ele
    executaria <script> (polyglot XML/XHTML). Como nada precisa renderiza-lo no
    navegador, devolvemos octet-stream — o navegador so baixa.
    """
    return "application/octet-stream" if basename.lower().endswith(".xml") else "application/pdf"


def nome_download(ordem_id: int, basename: str) -> str:
    ext = ".xml" if basename.lower().endswith(".xml") else ".pdf"
    return f"nota-fiscal-{ordem_id}{ext}"
