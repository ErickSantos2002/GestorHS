"""Cliente HTTP da integracao com o TaskHS (best-effort, gating por env)."""
import logging

import httpx

from app.core.config import settings
from app.integrations.log_integracao import registrar_log_integracao

logger = logging.getLogger(__name__)


def integracao_ativa() -> bool:
    return bool(settings.TASKHS_BASE_URL and settings.TASKHS_API_KEY)


def _post(payload: dict) -> httpx.Response:
    """POST cru; devolve a Response. Levanta so em erro de rede (nao de status)."""
    url = f"{settings.TASKHS_BASE_URL.rstrip('/')}/integration/cards"
    return httpx.post(
        url, json=payload,
        headers={"X-API-Key": settings.TASKHS_API_KEY},
        timeout=5,
    )


def enviar_card(payload: dict) -> None:
    """Alvo do BackgroundTask: no-op se desligada; nunca propaga (best-effort)."""
    if not integracao_ativa():
        registrar_log_integracao(integracao="taskhs", status="pulado",
                                 motivo="desligado", payload=payload)
        return
    try:
        resp = _post(payload)
    except Exception as e:
        registrar_log_integracao(integracao="taskhs", status="erro",
                                 payload=payload, resposta=str(e))
        logger.exception("falha de rede ao espelhar card no TaskHS (external_id=%s)",
                         payload.get("external_id"))
        return
    if resp.status_code >= 400:
        registrar_log_integracao(integracao="taskhs", status="erro", payload=payload,
                                 http_status=resp.status_code, resposta=resp.text)
        logger.warning("TaskHS respondeu %s (external_id=%s)",
                       resp.status_code, payload.get("external_id"))
        return
    registrar_log_integracao(integracao="taskhs", status="sucesso", payload=payload,
                             http_status=resp.status_code, resposta=resp.text)


def enviar_card_sync(payload: dict) -> None:
    """Envia PROPAGANDO erro (uso no script de backfill, que quer relatar falhas)."""
    resp = _post(payload)
    if resp.status_code >= 400:
        registrar_log_integracao(integracao="taskhs", status="erro", payload=payload,
                                 http_status=resp.status_code, resposta=resp.text)
        raise RuntimeError(f"TaskHS respondeu {resp.status_code}: {resp.text[:500]}")
    registrar_log_integracao(integracao="taskhs", status="sucesso", payload=payload,
                             http_status=resp.status_code, resposta=resp.text)
