"""Espelhamento da OS como card no TaskHS — compartilhado entre routers (ordens, notas_fiscais)
para evitar import circular. Fonte única do payload (contrato v2: list_id + obs)."""

from app.core import certificado_link
from app.core import nota_fiscal_link
from app.core import taskhs
from app.integrations import taskhs_client
from app.models import OSCertificado


def _montar_payload_os(db, ordem, *, list_id, arquivado) -> dict:
    """Junta certificados + nota fiscal, monta as obs e devolve o payload v2 completo."""
    certs = db.query(OSCertificado).filter(OSCertificado.os == ordem.id).all()
    certificados = [
        {"tipo": c.tipo, "url": certificado_link.link_certificado(ordem.id, c.tipo)}
        for c in certs
    ]
    nf_url = nota_fiscal_link.link_nota_fiscal(ordem.id) if ordem.nota_fiscal else None
    obs = taskhs.montar_obs(ordem, certificados=certificados, nota_fiscal_url=nf_url)
    return taskhs.montar_payload(ordem, list_id=list_id, arquivado=arquivado, obs=obs)


def agendar_espelhamento(db, background_tasks, ordem, *, list_id, arquivado):
    """Agenda o upsert no TaskHS (async, best-effort). No-op se sem list_id ou integração desligada."""
    if list_id is None or not taskhs_client.integracao_ativa():
        return
    payload = _montar_payload_os(db, ordem, list_id=list_id, arquivado=arquivado)
    background_tasks.add_task(taskhs_client.enviar_card, payload)


def espelhar_os_sync(db, ordem, *, list_id, arquivado):
    """Monta o payload e envia sincronamente, PROPAGANDO erro (uso no backfill)."""
    payload = _montar_payload_os(db, ordem, list_id=list_id, arquivado=arquivado)
    taskhs_client.enviar_card_sync(payload)
