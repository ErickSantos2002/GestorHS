"""Link publico assinado para download do certificado (sem login no GestorHS)."""
from app.core import assinatura
from app.core.config import settings

NOME_PUBLICO = {"C": "calibracao", "M": "manutencao"}


def _mensagem(ordem_id: int, tipo_codigo: str) -> str:
    # NAO MUDAR este formato: ha links de certificado ja publicados nos cards do TaskHS.
    return f"cert:{ordem_id}:{tipo_codigo}"


def assinar(ordem_id: int, tipo_codigo: str) -> str:
    return assinatura.assinar(_mensagem(ordem_id, tipo_codigo))


def verificar(ordem_id: int, tipo_codigo: str, token: str | None) -> bool:
    return assinatura.verificar(_mensagem(ordem_id, tipo_codigo), token)


def link_certificado(ordem_id: int, tipo_codigo: str) -> str | None:
    base = settings.CERT_PUBLIC_BASE_URL
    if not base:
        return None
    nome = NOME_PUBLICO[tipo_codigo]
    return f"{base.rstrip('/')}/publico/certificado/{ordem_id}/{nome}?t={assinar(ordem_id, tipo_codigo)}"
