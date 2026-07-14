"""Link publico assinado para download da nota fiscal (sem login no GestorHS)."""
from app.core import assinatura
from app.core.config import settings


def _mensagem(ordem_id: int) -> str:
    return f"nf:{ordem_id}"


def assinar(ordem_id: int) -> str:
    return assinatura.assinar(_mensagem(ordem_id))


def verificar(ordem_id: int, token: str | None) -> bool:
    return assinatura.verificar(_mensagem(ordem_id), token)


def link_nota_fiscal(ordem_id: int) -> str | None:
    base = settings.CERT_PUBLIC_BASE_URL
    if not base:
        return None
    return f"{base.rstrip('/')}/publico/nota-fiscal/{ordem_id}?t={assinar(ordem_id)}"
