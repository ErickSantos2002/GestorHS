"""Link publico assinado para download de certificado geral (sem login)."""
from app.core import assinatura
from app.core.config import settings


def _mensagem(cert_id: int) -> str:
    return f"certgeral:{cert_id}"


def assinar(cert_id: int) -> str:
    return assinatura.assinar(_mensagem(cert_id))


def verificar(cert_id: int, token: str | None) -> bool:
    return assinatura.verificar(_mensagem(cert_id), token)


def link_certificado_geral(cert_id: int) -> str | None:
    base = settings.CERT_PUBLIC_BASE_URL
    if not base:
        return None
    return f"{base.rstrip('/')}/publico/certificado-geral/{cert_id}?t={assinar(cert_id)}"
