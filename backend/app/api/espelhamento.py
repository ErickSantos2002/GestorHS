"""Espelhamento da OS como card no TaskHS — compartilhado entre routers (ordens, notas_fiscais)
para evitar import circular. Comportamento identico ao que vivia antes em ordens.py."""

from app.core import certificado_link
from app.core import nota_fiscal_link
from app.core import taskhs
from app.integrations import taskhs_client
from app.models import OSCertificado


def agendar_espelhamento(db, background_tasks, ordem, *, lista, arquivado):
    """Monta descricao (com links de certificado e nota fiscal) e agenda o upsert no TaskHS."""
    if lista is None or not taskhs_client.integracao_ativa():
        return
    certs = db.query(OSCertificado).filter(OSCertificado.os == ordem.id).all()
    certificados = [
        {"tipo": c.tipo, "url": certificado_link.link_certificado(ordem.id, c.tipo)}
        for c in certs
    ]
    nf_url = nota_fiscal_link.link_nota_fiscal(ordem.id) if ordem.nota_fiscal else None
    descricao = taskhs.montar_descricao(ordem, certificados=certificados, nota_fiscal_url=nf_url)
    payload = taskhs.montar_payload(ordem, lista=lista, arquivado=arquivado, descricao=descricao)
    background_tasks.add_task(taskhs_client.enviar_card, payload)
