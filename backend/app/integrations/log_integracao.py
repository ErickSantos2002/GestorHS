"""Writer best-effort dos logs de integracao.

Chamado pelo choke point dos clientes (taskhs_client/hsgrowth_client). NUNCA
propaga: logar nao pode quebrar envio nem avanco de OS. Abre sessao propria
(SessionLocal) quando nenhuma e injetada — necessario porque o BackgroundTask
que envia nao tem sessao de request (a da request ja foi fechada)."""
import logging

from app.core.log_integracao import classificar_tipo, referencia_os_do_payload
from app.models.database import SessionLocal
from app.models.log_integracao import LogIntegracao

logger = logging.getLogger(__name__)


def registrar_log_integracao(*, integracao, status, payload=None, motivo=None,
                             http_status=None, resposta=None, referencia_os=None,
                             db=None) -> None:
    own = db is None
    try:
        if own:
            db = SessionLocal()
        source = (payload or {}).get("source")
        tipo = classificar_tipo(integracao, source)
        ref = referencia_os if referencia_os is not None else referencia_os_do_payload(tipo, payload)
        db.add(LogIntegracao(
            integracao=integracao,
            tipo=tipo,
            external_id=(payload or {}).get("external_id"),
            referencia_os=ref,
            status=status,
            motivo=motivo,
            http_status=http_status,
            resposta=(resposta[:2000] if resposta else None),
            payload=payload,
        ))
        db.commit()
    except Exception:
        logger.exception("falha ao registrar log de integracao (best-effort)")
        try:
            if db is not None:
                db.rollback()
        except Exception:
            pass
    finally:
        if own and db is not None:
            db.close()
