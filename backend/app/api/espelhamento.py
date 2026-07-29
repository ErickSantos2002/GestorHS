"""Espelhamento da OS como card no TaskHS — compartilhado entre routers (ordens, notas_fiscais)
para evitar import circular. Fonte única do payload (contrato v2: list_id + obs)."""

from app.core import certificado_link
from app.core import nota_fiscal_link
from app.core import proposta_link
from app.core import taskhs
from app.core.caixa import principal_valido
from app.integrations import taskhs_client
from app.models import OSCertificado, Proposta


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


def _montar_payload_caixa(db, caixa, *, list_id, arquivado) -> dict:
    """Junta certificados + nota fiscal de todas as OS da caixa, monta as obs e
    devolve o payload v2 completo. Espelho de `_montar_payload_os` para caixas."""
    from app.models import Ordem, OSCertificado

    ordens = [o for o in caixa.ordens if o.fase not in (9,)] or list(caixa.ordens)
    pid = principal_valido(caixa.cliente_principal, [o.cliente for o in ordens])
    if pid is not None:
        ordens.sort(key=lambda o: 0 if o.cliente == pid else 1)
    certificados_por_os = {}
    for o in ordens:
        certs = db.query(OSCertificado).filter(OSCertificado.os == o.id).all()
        certificados_por_os[o.id] = [
            {"tipo": c.tipo, "url": certificado_link.link_certificado(o.id, c.tipo)} for c in certs
        ]
    nf_url = None
    rep_nf = next((o for o in ordens if o.nota_fiscal), None)
    if rep_nf is not None:
        nf_url = nota_fiscal_link.link_nota_fiscal(rep_nf.id)
    proposta_url = None
    if caixa.numero_proposta is not None:
        p = db.query(Proposta).filter(Proposta.numero == caixa.numero_proposta,
                                       Proposta.is_deleted.is_(False)).first()
        if p is not None:
            proposta_url = proposta_link.link_proposta(p.id)
    obs = taskhs.montar_obs_caixa(caixa, ordens, certificados_por_os=certificados_por_os,
                                   nota_fiscal_url=nf_url, proposta_url=proposta_url)
    return taskhs.montar_payload_caixa(caixa, ordens, list_id=list_id, arquivado=arquivado, obs=obs)


def agendar_espelhamento_caixa(db, background_tasks, caixa, *, origem=None, arquivado=False):
    """Agenda o upsert no TaskHS do card da CAIXA (async, best-effort). No-op se
    sem list_id (fase sem mapeamento) ou integração desligada."""
    fase = origem if origem is not None else caixa.fase
    list_id = taskhs.list_id_da_fase(fase) if fase is not None else None
    if list_id is None or not taskhs_client.integracao_ativa():
        return
    payload = _montar_payload_caixa(db, caixa, list_id=list_id, arquivado=arquivado)
    background_tasks.add_task(taskhs_client.enviar_card, payload)
