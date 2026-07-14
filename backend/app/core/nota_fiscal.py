"""Convencao de armazenamento da nota fiscal (pura). Fonte unica da verdade:
o subdir em disco e o media type sao definidos AQUI e consumidos pelos endpoints."""


def subdir(ordem_id: int) -> str:
    return f"notas-fiscais/{ordem_id}"


def media_type(basename: str) -> str:
    return "application/xml" if basename.lower().endswith(".xml") else "application/pdf"
