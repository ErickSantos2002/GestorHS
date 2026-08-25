"""Espelhamento da OS como card no TaskHS — compartilhado entre routers (ordens, notas_fiscais)
para evitar import circular. Fonte única do payload (contrato v2: list_id + obs)."""

from app.core import certificado_link
from app.core import fluxo_modulo
from app.core import nota_fiscal_link
from app.core import proposta_link
from app.core import taskhs
from app.core.caixa import ordens_do_card, principal_valido
from app.integrations import taskhs_client
from app.integrations.log_integracao import registrar_log_integracao
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
    """Agenda o upsert no TaskHS (async, best-effort). No-op se sem list_id,
    integração desligada ou OS de módulo/phoebus."""
    if list_id is None or not taskhs_client.integracao_ativa():
        return
    if fluxo_modulo.os_de_modulo(ordem):
        registrar_log_integracao(integracao="taskhs", status="pulado",
                                 motivo="caixa_de_modulo", referencia_os=ordem.id)
        return
    payload = _montar_payload_os(db, ordem, list_id=list_id, arquivado=arquivado)
    background_tasks.add_task(taskhs_client.enviar_card, payload)


def espelhar_os_sync(db, ordem, *, list_id, arquivado) -> bool:
    """Monta o payload e envia sincronamente, PROPAGANDO erro (uso no backfill).
    Devolve True se enviou, False se pulou por ser módulo/phoebus — o backfill
    relata o número real de OS enviadas."""
    if fluxo_modulo.os_de_modulo(ordem):
        registrar_log_integracao(integracao="taskhs", status="pulado",
                                 motivo="caixa_de_modulo", referencia_os=ordem.id)
        return False
    payload = _montar_payload_os(db, ordem, list_id=list_id, arquivado=arquivado)
    taskhs_client.enviar_card_sync(payload)
    return True


def _montar_payload_caixa(db, caixa, *, list_id, arquivado) -> dict:
    """Junta certificados + nota fiscal de todas as OS da caixa, monta as obs e
    devolve o payload v2 completo. Espelho de `_montar_payload_os` para caixas."""
    from app.models import OSCertificado

    ordens = ordens_do_card(caixa)
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


def espelhar_caixa_sync(db, caixa, *, list_id, arquivado=False) -> bool:
    """Versão síncrona de `agendar_espelhamento_caixa`, para backfill/correção em lote.

    Espelho de `espelhar_os_sync`, só que para o card da CAIXA: PROPAGA erro em vez
    de engolir, para o script conseguir relatar o que falhou. Devolve False quando a
    caixa é de módulo/phoebus (fluxo próprio, fora do board).
    """
    ordens = ordens_do_card(caixa)
    if fluxo_modulo.caixa_de_modulo(ordens):
        registrar_log_integracao(integracao="taskhs", status="pulado",
                                 motivo="caixa_de_modulo",
                                 referencia_os=ordens[0].id if ordens else None)
        return False
    payload = _montar_payload_caixa(db, caixa, list_id=list_id, arquivado=arquivado)
    taskhs_client.enviar_card_sync(payload)
    return True


def agendar_espelhamento_caixa(db, background_tasks, caixa, *, origem=None, arquivado=False):
    """Agenda o upsert no TaskHS do card da CAIXA (async, best-effort). No-op se
    sem list_id (fase sem mapeamento), integração desligada ou caixa de módulo."""
    fase = origem if origem is not None else caixa.fase
    list_id = taskhs.list_id_da_fase(fase) if fase is not None else None
    if list_id is None or not taskhs_client.integracao_ativa():
        return
    ordens = ordens_do_card(caixa)
    if fluxo_modulo.caixa_de_modulo(ordens):
        # Módulo/phoebus tem fluxo próprio, fora do board. Bloquear ANTES de montar
        # o payload também congela card antigo: criar, mover e arquivar são o mesmo
        # caminho, então nada mexe no que já foi enviado.
        registrar_log_integracao(integracao="taskhs", status="pulado",
                                 motivo="caixa_de_modulo",
                                 referencia_os=ordens[0].id if ordens else None)
        return
    payload = _montar_payload_caixa(db, caixa, list_id=list_id, arquivado=arquivado)
    background_tasks.add_task(taskhs_client.enviar_card, payload)
