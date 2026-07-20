"""Cards do GrowthHS disparados pelo fluxo da OS.

Mesmo papel que `espelhamento.py` cumpre para o TaskHS: consulta o banco, monta
o payload e agenda o envio — mantido fora dos routers para evitar import circular.
"""
from types import SimpleNamespace

from app.core.config import settings
from app.models import EquipamentoCliente, InstalacaoModulo


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
