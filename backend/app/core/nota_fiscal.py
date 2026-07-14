"""Convencao de armazenamento da nota fiscal (pura). Fonte unica da verdade:
o subdir em disco e o media type sao definidos AQUI e consumidos pelos endpoints."""


def subdir(ordem_id: int) -> str:
    return f"notas-fiscais/{ordem_id}"


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
