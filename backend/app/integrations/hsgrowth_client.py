"""Cliente HTTP da integracao com o GrowthHS (best-effort, gating por env).

Endpoint create-or-return: chamar de novo com o mesmo (source, external_id)
devolve o card existente e NAO altera nada."""
import logging

import httpx

from app.core.config import settings
from app.integrations.log_integracao import registrar_log_integracao

logger = logging.getLogger(__name__)

_CAMINHO = "/api/v1/integration/service-cards"


def integracao_ativa() -> bool:
    return bool(settings.HSGROWTH_BASE_URL and settings.HSGROWTH_API_KEY)


def _post(payload: dict) -> httpx.Response:
    """POST cru; devolve a Response. Levanta so em erro de rede (nao de status)."""
    url = f"{settings.HSGROWTH_BASE_URL.rstrip('/')}{_CAMINHO}"
    return httpx.post(
        url, json=payload,
        headers={"X-API-Key": settings.HSGROWTH_API_KEY},
        timeout=10,
    )


def enviar_card(payload: dict) -> None:
    """Alvo do BackgroundTask: no-op se desligada; nunca propaga (best-effort)."""
    if not integracao_ativa():
        registrar_log_integracao(integracao="growthhs", status="pulado",
                                 motivo="desligado", payload=payload)
        return
    try:
        resp = _post(payload)
    except Exception as e:
        registrar_log_integracao(integracao="growthhs", status="erro",
                                 payload=payload, resposta=str(e))
        logger.exception("falha de rede ao criar card no GrowthHS (external_id=%s)",
                         payload.get("external_id"))
        return
    if resp.status_code >= 400:
        registrar_log_integracao(integracao="growthhs", status="erro", payload=payload,
                                 http_status=resp.status_code, resposta=resp.text)
        logger.warning("GrowthHS respondeu %s (external_id=%s)",
                       resp.status_code, payload.get("external_id"))
        return
    registrar_log_integracao(integracao="growthhs", status="sucesso", payload=payload,
                             http_status=resp.status_code, resposta=resp.text)


def enviar_card_sync(payload: dict) -> dict:
    """Envia PROPAGANDO erro (uso nos scripts). Devolve o JSON da resposta."""
    resp = _post(payload)
    if resp.status_code >= 400:
        registrar_log_integracao(integracao="growthhs", status="erro", payload=payload,
                                 http_status=resp.status_code, resposta=resp.text)
        raise RuntimeError(f"GrowthHS respondeu {resp.status_code}: {resp.text[:500]}")
    registrar_log_integracao(integracao="growthhs", status="sucesso", payload=payload,
                             http_status=resp.status_code, resposta=resp.text)
    return resp.json()
