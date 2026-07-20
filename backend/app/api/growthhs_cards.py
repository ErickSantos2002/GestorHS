"""Cards do GrowthHS disparados pelo fluxo da OS.

Mesmo papel que `espelhamento.py` cumpre para o TaskHS: consulta o banco, monta
o payload e agenda o envio — mantido fora dos routers para evitar import circular.
"""
import logging
from datetime import date
from types import SimpleNamespace

from app.core.config import settings
from app.core.growthhs_os import montar_card_os
from app.core.growthhs_payload import montar_device
from app.integrations import hsgrowth_client
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


def agendar_card_os(db, background_tasks, ordem) -> None:
    """Agenda o card de OS liberada do laboratorio no board Servicos do GrowthHS.

    No-op se a integracao estiver desligada. A MONTAGEM do payload roda dentro
    do try/except: uma linha ruim, um relacionamento faltando, qualquer coisa
    — nao pode propagar e derrubar o `avancar` da OS (o envio em si, via
    `hsgrowth_client.enviar_card`, ja e' best-effort por conta propria).
    """
    if not hsgrowth_client.integracao_ativa():
        return
    ec = ordem.equipamento_rel
    if ec is None:
        # Dado benigno (OS sem equipamento vinculado) — nao e' excecao, nao
        # precisa de stack trace no log; so no-op mesmo, nao tem card pra montar.
        logger.warning("OS sem equipamento vinculado, card do GrowthHS nao agendado (os=%s)", ordem.id)
        return
    try:
        elo = buscar_elo(db, ec)
        device = montar_device(ec, ordem.equipamento_descricao, elo=elo)
        card = montar_card_os(
            ordem, ordem.cliente_rel, device, settings.HSGROWTH_BOARD_SERVICOS, date.today(),
        )
    except Exception:
        # A OS ja' foi commitada e avancada de fase antes deste gatilho rodar
        # (ver `avancar`); se a excecao veio de uma query aqui dentro (ex.: erro
        # de banco em `buscar_elo`), a sessao fica suja e a proxima query do
        # chamador (`_anotar_modelos_faltantes`) estouraria com
        # `PendingRollbackError` -> 500 pra uma OS que ja avancou de verdade.
        db.rollback()
        logger.exception("falha ao montar card de OS para o GrowthHS (os=%s)", ordem.id)
        return
    background_tasks.add_task(hsgrowth_client.enviar_card, card)
