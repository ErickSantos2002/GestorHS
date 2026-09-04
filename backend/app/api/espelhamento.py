"""Espelhamento da CAIXA como card no TaskHS — compartilhado entre routers (ordens,
caixas, notas_fiscais) para evitar import circular. Fonte única do payload (contrato
v2: list_id + obs).

A unidade do board é a CAIXA, nunca a OS: os aparelhos entram como linhas das obs do
card da caixa. O caminho por OS existiu até set/2026 e foi removido — enquanto ele
vivia, uma OS reespelhada abria um SEGUNDO card para a mesma caixa (e `external_id`
era o id da OS no mesmo namespace do id da caixa, então dava para sobrescrever o card
da caixa em silêncio)."""

from app.core import certificado_link
from app.core import fluxo_modulo
from app.core import nota_fiscal_link
from app.core import proposta_link
from app.core import taskhs
from app.core.caixa import ordens_do_card, principal_valido
from app.integrations import taskhs_client
from app.integrations.log_integracao import registrar_log_integracao
from app.models import NotaFiscal, OSCertificado, Proposta


def _montar_payload_caixa(db, caixa, *, list_id, arquivado) -> dict:
    """Junta certificados + nota fiscal de todas as OS da caixa, monta as obs e
    devolve o payload v2 completo."""
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
    # Fonte nova: uma linha por nota da CAIXA, com os dois links assinados.
    notas = [
        {"numero": nf.numero,
         "pdf": nota_fiscal_link.link_nota(nf.id),
         "xml": nota_fiscal_link.link_nota(nf.id, nota_fiscal_link.XML)}
        for nf in db.query(NotaFiscal).filter(NotaFiscal.caixa == caixa.id)
                    .order_by(NotaFiscal.id).all()
    ]
    nf_url = nf_xml_url = None
    # o MESMO representante para os dois links: PDF de uma OS e XML de outra seriam
    # notas diferentes no mesmo card.
    rep_nf = next((o for o in ordens if o.nota_fiscal or o.nota_fiscal_xml), None)
    if rep_nf is not None:
        if rep_nf.nota_fiscal:
            nf_url = nota_fiscal_link.link_nota_fiscal(rep_nf.id)
        if rep_nf.nota_fiscal_xml:
            nf_xml_url = nota_fiscal_link.link_nota_fiscal_xml(rep_nf.id)
    proposta_url = None
    if caixa.numero_proposta is not None:
        p = db.query(Proposta).filter(Proposta.numero == caixa.numero_proposta,
                                       Proposta.is_deleted.is_(False)).first()
        if p is not None:
            proposta_url = proposta_link.link_proposta(p.id)
    obs = taskhs.montar_obs_caixa(caixa, ordens, certificados_por_os=certificados_por_os,
                                   nota_fiscal_url=nf_url, nota_fiscal_xml_url=nf_xml_url,
                                   proposta_url=proposta_url, notas=notas)
    return taskhs.montar_payload_caixa(caixa, ordens, list_id=list_id, arquivado=arquivado, obs=obs)


def espelhar_caixa_sync(db, caixa, *, list_id, arquivado=False) -> bool:
    """Versão síncrona de `agendar_espelhamento_caixa`, para backfill/correção em lote.

    PROPAGA erro em vez de engolir, para o script conseguir relatar o que falhou.
    Devolve False quando a caixa é de módulo/phoebus (fluxo próprio, fora do board).
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
