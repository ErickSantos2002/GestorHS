"""Link publico assinado para download da nota fiscal (sem login no GestorHS).

A nota vive em DOIS arquivos — o PDF e o XML — e cada um tem o seu token: assinar
os dois com a mesma mensagem faria um link antigo de PDF baixar o XML.
"""
from app.core import assinatura
from app.core.config import settings

PDF = "pdf"
XML = "xml"


def _mensagem(ordem_id: int, tipo: str = PDF) -> str:
    # NAO MUDAR o formato do PDF: ha links de nota fiscal ja publicados nos cards
    # do TaskHS. O XML nasceu depois, com sufixo proprio.
    return f"nf:{ordem_id}" if tipo == PDF else f"nf:{ordem_id}:{tipo}"


def assinar(ordem_id: int, tipo: str = PDF) -> str:
    return assinatura.assinar(_mensagem(ordem_id, tipo))


def verificar(ordem_id: int, token: str | None, tipo: str = PDF) -> bool:
    return assinatura.verificar(_mensagem(ordem_id, tipo), token)


def link_nota_fiscal(ordem_id: int) -> str | None:
    base = settings.CERT_PUBLIC_BASE_URL
    if not base:
        return None
    return f"{base.rstrip('/')}/publico/nota-fiscal/{ordem_id}?t={assinar(ordem_id)}"


def link_nota_fiscal_xml(ordem_id: int) -> str | None:
    base = settings.CERT_PUBLIC_BASE_URL
    if not base:
        return None
    return f"{base.rstrip('/')}/publico/nota-fiscal/{ordem_id}/xml?t={assinar(ordem_id, XML)}"


# --- link por NOTA (tabela `notas_fiscais`) -------------------------------
# Prefixo proprio `nf:n:` para nao colidir com `nf:{ordem_id}`: os dois espacos
# de id sao numericos e se cruzariam sem ele.

def _mensagem_nota(nota_id: int, tipo: str = PDF) -> str:
    return f"nf:n:{nota_id}" if tipo == PDF else f"nf:n:{nota_id}:{tipo}"


def assinar_nota(nota_id: int, tipo: str = PDF) -> str:
    return assinatura.assinar(_mensagem_nota(nota_id, tipo))


def verificar_nota(nota_id: int, token: str | None, tipo: str = PDF) -> bool:
    return assinatura.verificar(_mensagem_nota(nota_id, tipo), token)


def link_nota(nota_id: int, tipo: str = PDF) -> str | None:
    base = settings.CERT_PUBLIC_BASE_URL
    if not base:
        return None
    sufixo = "" if tipo == PDF else "/xml"
    return f"{base.rstrip('/')}/publico/nota-fiscal/nota/{nota_id}{sufixo}?t={assinar_nota(nota_id, tipo)}"
