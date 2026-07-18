"""Cliente HTTP da integracao com o GrowthHS (best-effort, gating por env).

Espelha o molde do taskhs_client, com uma diferenca importante de SEMANTICA:
o endpoint do GrowthHS e create-or-return, nao upsert — chamar de novo com o
mesmo (source, external_id) devolve o card existente e NAO altera nada.
"""
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_CAMINHO = "/api/v1/integration/service-cards"


def integracao_ativa() -> bool:
    return bool(settings.HSGROWTH_BASE_URL and settings.HSGROWTH_API_KEY)


def _post(payload: dict) -> dict:
    """POST no endpoint; levanta em erro. Devolve o JSON da resposta."""
    url = f"{settings.HSGROWTH_BASE_URL.rstrip('/')}{_CAMINHO}"
    resp = httpx.post(
        url, json=payload,
        headers={"X-API-Key": settings.HSGROWTH_API_KEY},
        timeout=10,
    )
    resp.raise_for_status()      # 201 e 200 passam; 4xx/5xx levantam
    return resp.json()


def enviar_card(payload: dict) -> None:
    """Alvo do BackgroundTask: no-op se desligada; nunca propaga (best-effort)."""
    if not integracao_ativa():
        return
    try:
        _post(payload)
    except Exception:
        logger.exception(
            "falha ao criar card no GrowthHS (source=%s external_id=%s)",
            payload.get("source"), payload.get("external_id"),
        )


def enviar_card_sync(payload: dict) -> dict:
    """Envia PROPAGANDO erro (uso nos scripts, que querem relatar falhas)."""
    return _post(payload)
