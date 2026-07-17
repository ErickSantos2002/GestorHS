"""Cliente HTTP da integracao com o TaskHS (best-effort, gating por env)."""
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def integracao_ativa() -> bool:
    return bool(settings.TASKHS_BASE_URL and settings.TASKHS_API_KEY)


def _post(payload: dict) -> None:
    """Faz o POST e levanta em erro (httpx.HTTPStatusError / rede)."""
    url = f"{settings.TASKHS_BASE_URL.rstrip('/')}/integration/cards"
    resp = httpx.post(
        url, json=payload,
        headers={"X-API-Key": settings.TASKHS_API_KEY},
        timeout=5,
    )
    resp.raise_for_status()


def enviar_card(payload: dict) -> None:
    """Alvo do BackgroundTask: no-op se desligada; nunca propaga (best-effort)."""
    if not integracao_ativa():
        return
    try:
        _post(payload)
    except Exception:
        logger.exception(
            "falha ao espelhar card no TaskHS (external_id=%s) — reconcilia no proximo upsert",
            payload.get("external_id"),
        )


def enviar_card_sync(payload: dict) -> None:
    """Envia PROPAGANDO erro (uso no script de backfill, que quer relatar falhas)."""
    _post(payload)
