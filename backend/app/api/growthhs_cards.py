"""Cards do GrowthHS disparados pelo fluxo da OS.

Mesmo papel que `espelhamento.py` cumpre para o TaskHS: consulta o banco, monta
o payload e agenda o envio — mantido fora dos routers para evitar import circular.
"""
import logging
from datetime import date
from types import SimpleNamespace

from app.core import fluxo_modulo
from app.core.caixa import ordens_do_card, principal_valido
from app.core.config import settings
from app.core.growthhs_os import montar_card_caixa
from app.core.growthhs_payload import montar_device
from app.integrations import hsgrowth_client
from app.integrations.log_integracao import registrar_log_integracao
from app.models import EquipamentoCliente, InstalacaoModulo

logger = logging.getLogger(__name__)


def buscar_elo(db, ec):
    """O Phoebus em que este modulo esta instalado, ou None.

    Devolve um objeto com `.serie` e `.descricao` — a PONTE obrigatoria para o
    `montar_device`, que espera esses nomes. A linha ORM de EquipamentoCliente
    expoe a descricao do catalogo como `.equipamento_descricao`, entao passar o
    ORM cru quebraria com AttributeError bem no caso interessante (modulo COM elo).
    """
    if ec is None or ec.equipamento != settings.EQUIPAMENTO_MODULO_ID:
        return None
    instalacao = (
        db.query(InstalacaoModulo)
        .filter(InstalacaoModulo.modulo == ec.id, InstalacaoModulo.saiu_em.is_(None))
        .first()
    )
    if instalacao is None:
        return None
    phoebus = db.get(EquipamentoCliente, instalacao.phoebus)
    if phoebus is None:
        return None
    return SimpleNamespace(serie=phoebus.serie, descricao=phoebus.equipamento_descricao)


def cliente_do_card(caixa):
    """O cliente que as integracoes usam: o principal (se ainda na caixa), com
    fallback na 1a OS — protege contra principal orfao/desatualizado."""
    clientes = [o.cliente for o in caixa.ordens]
    if principal_valido(caixa.cliente_principal, clientes) is not None:
        return caixa.cliente_principal_rel
    return caixa.ordens[0].cliente_rel if caixa.ordens else None


def agendar_card_caixa(db, background_tasks, caixa) -> None:
    """Agenda o card de CAIXA liberada do laboratorio no board Servicos do GrowthHS.

    Um device por OS da caixa (equipamentos sem vinculo sao pulados individualmente,
    sem no-op da caixa inteira). No-op se a integracao estiver desligada, se a caixa
    for de modulo/phoebus (fluxo proprio, fora do board) ou se nenhuma OS da caixa
    tiver equipamento.

    A MONTAGEM do payload roda dentro do try/except: uma linha ruim, um
    relacionamento faltando, qualquer coisa — nao pode propagar e derrubar o
    avanco da caixa (o envio em si, via `hsgrowth_client.enviar_card`, ja e'
    best-effort por conta propria).
    """
    if not hsgrowth_client.integracao_ativa():
        return
    do_card = ordens_do_card(caixa)
    if fluxo_modulo.caixa_de_modulo(do_card):
        registrar_log_integracao(integracao="growthhs", status="pulado",
                                 motivo="caixa_de_modulo",
                                 referencia_os=do_card[0].id if do_card else None)
        return
    ordens = [o for o in do_card if o.equipamento_rel is not None]
    if not ordens:
        return
    try:
        devices = []
        for o in ordens:
            ec = o.equipamento_rel
            elo = buscar_elo(db, ec)
            devices.append(montar_device(ec, o.equipamento_descricao, elo=elo))
        cliente = cliente_do_card(caixa)
        card = montar_card_caixa(caixa, cliente, devices, settings.HSGROWTH_BOARD_SERVICOS, date.today())
    except Exception:
        db.rollback()
        logger.exception("falha ao montar card de caixa para o GrowthHS (caixa=%s)", caixa.id)
        return
    background_tasks.add_task(hsgrowth_client.enviar_card, card)
