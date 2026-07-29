"""Link publico assinado para download do PDF da proposta (sem login)."""
from app.core import assinatura
from app.core.config import settings


def _mensagem(proposta_id: int) -> str:
    # NAO MUDAR este formato: ha links de proposta publicados nos cards do TaskHS.
    return f"proposta:{proposta_id}"


def assinar(proposta_id: int) -> str:
    return assinatura.assinar(_mensagem(proposta_id))


def verificar(proposta_id: int, token: str | None) -> bool:
    return assinatura.verificar(_mensagem(proposta_id), token)


def link_proposta(proposta_id: int) -> str | None:
    base = settings.CERT_PUBLIC_BASE_URL
    if not base:
        return None
    return f"{base.rstrip('/')}/publico/proposta/{proposta_id}?t={assinar(proposta_id)}"
