"""Assinatura HMAC para links publicos (puro).

A mensagem assinada e namespaceada por dominio (ex.: "cert:...", "nf:...") para que um
token de um recurso nunca sirva para outro.
"""
import hashlib
import hmac

from app.core.config import settings


def assinar(mensagem: str) -> str:
    return hmac.new(settings.JWT_SECRET_KEY.encode(), mensagem.encode(), hashlib.sha256).hexdigest()


def verificar(mensagem: str, token: str | None) -> bool:
    return hmac.compare_digest(assinar(mensagem), token or "")
