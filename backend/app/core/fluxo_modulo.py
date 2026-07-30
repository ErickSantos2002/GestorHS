"""Modulo e Phoebus seguem um fluxo de servico proprio.

Caixa que contenha um deles NAO vira card no TaskHS nem no GrowthHS. Este modulo
responde a pergunta e nada mais — logica pura, sem I/O, para ser consumida pelos
dois pontos de estrangulamento (`api/espelhamento.py` e `api/growthhs_cards.py`).

Fora do escopo de proposito: as cargas por CLIENTE do GrowthHS (atrasados,
vencendo) continuam mandando modulo, porque o modulo e' o item que de fato
calibra e o elo com o Phoebus foi construido para aparecer nesses payloads.
"""

from app.core.config import settings


def equipamentos_de_modulo() -> set[int]:
    """Ids de catalogo que bloqueiam o card: Phoebus (36) e Modulo PHOEBUS (47).

    Lido a cada chamada em vez de num set de modulo: uma constante de modulo
    congelaria o valor no momento do import, furando override por env e
    monkeypatch em teste. O Modulo para EBS (49) e o EBS (37) NAO entram.
    """
    return {settings.EQUIPAMENTO_PHOEBUS_ID, settings.EQUIPAMENTO_MODULO_ID}


def os_de_modulo(ordem) -> bool:
    """True se o equipamento da OS e' modulo ou phoebus.

    `getattr` com default protege os fakes (SimpleNamespace) que os testes
    das integracoes montam sem a property; OS real sempre tem. OS sem
    equipamento vinculado devolve None, que nao esta no conjunto -> False.
    """
    return getattr(ordem, "equipamento_catalogo", None) in equipamentos_de_modulo()


def caixa_de_modulo(ordens) -> bool:
    """True se QUALQUER OS da lista e' de modulo/phoebus (caixa mista bloqueia).

    Recebe a lista de ordens JA FILTRADA pelo chamador (nao a caixa), para que o
    critério de "quais OS contam" fique visivel no ponto de uso.
    """
    return any(os_de_modulo(o) for o in ordens)
