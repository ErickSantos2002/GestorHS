"""Link publico assinado para download do certificado (sem login no GestorHS)."""
import hashlib
import hmac

from app.core.config import settings

NOME_PUBLICO = {"C": "calibracao", "M": "manutencao"}


def assinar(ordem_id: int, tipo_codigo: str) -> str:
    mensagem = f"cert:{ordem_id}:{tipo_codigo}".encode()
    return hmac.new(settings.JWT_SECRET_KEY.encode(), mensagem, hashlib.sha256).hexdigest()


def verificar(ordem_id: int, tipo_codigo: str, token: str) -> bool:
    return hmac.compare_digest(assinar(ordem_id, tipo_codigo), token or "")


def link_certificado(ordem_id: int, tipo_codigo: str) -> str | None:
    base = settings.CERT_PUBLIC_BASE_URL
    if not base:
        return None
    nome = NOME_PUBLICO[tipo_codigo]
    return f"{base.rstrip('/')}/publico/certificado/{ordem_id}/{nome}?t={assinar(ordem_id, tipo_codigo)}"
