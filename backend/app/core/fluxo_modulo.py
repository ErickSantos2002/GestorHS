"""Modulo e Phoebus tem regras proprias — duas, que NAO coincidem.

1. Caixa que contenha um deles nao vira card no TaskHS nem no GrowthHS
   (`caixa_de_modulo`, `any`). Consumido por `api/espelhamento.py` e
   `api/growthhs_cards.py`.
2. Caixa 100% Modulo nao passa pelo Pos-Vendas E fica fora do board do TaskHS
   (`caixa_so_de_modulo`, `all`; `caixa_pula_posvendas` delega a ele).
   Consumido por `api/caixas.py`, `api/espelhamento.py` e pelos scripts.

Ate 18/09/2026 a pergunta 2 reaproveitava o predicado da 1, e por isso caixa de
Phoebus+Modulo pulava o comercial sem dever. Logica pura, sem I/O.

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


def rotulo_modulo(ordens) -> str | None:
    """Que tipo de serviço de módulo a caixa carrega: `phoebus`, `modulo`, `ambos` ou None.

    Alimenta o aviso do Financeiro no quadro de Ordens — a caixa chega lá sem ter
    passado pelo Pos-Vendas, e quem recebe precisa saber por que. Os tres estados sao
    reais na base: no Financeiro de 18/09/2026 havia 7 caixas com os dois juntos (o
    aparelho e o modulo dele viajam na mesma caixa) e 1 so com modulo.

    Aparelho comum na mesma caixa nao muda o rotulo: o aviso e' sobre o que ha de
    Phoebus/modulo ali. O rotulo fala de COMPOSICAO, nao de desvio de fase — desde
    18/09/2026 so a caixa 100% Modulo desvia, e `rotulo_modulo` continua marcando
    Phoebus e o par. A implicacao que vale (e tem teste) e' a estreita: caixa que
    desvia tem rotulo 'modulo'.
    """
    tem_phoebus = any(getattr(o, "equipamento_catalogo", None) == settings.EQUIPAMENTO_PHOEBUS_ID
                      for o in ordens)
    tem_modulo = any(getattr(o, "equipamento_catalogo", None) == settings.EQUIPAMENTO_MODULO_ID
                     for o in ordens)
    if tem_phoebus and tem_modulo:
        return "ambos"
    if tem_phoebus:
        return "phoebus"
    if tem_modulo:
        return "modulo"
    return None


def caixa_de_modulo(ordens) -> bool:
    """True se QUALQUER OS da lista e' de modulo/phoebus — bloqueia o CARD.

    Responde SO a pergunta das integracoes; caixa mista bloqueia. Para o desvio do
    Pos-Vendas use `caixa_pula_posvendas`, que e' mais estreito.

    Recebe a lista de ordens JA FILTRADA pelo chamador (nao a caixa), para que o
    critério de "quais OS contam" fique visivel no ponto de uso.
    """
    return any(os_de_modulo(o) for o in ordens)


def caixa_so_de_modulo(ordens) -> bool:
    """True SO se todas as OS sao Modulo (47). Nucleo de DUAS decisoes: pular o
    Pos-Vendas e ficar fora do board do TaskHS.

    ⚠️ "modulo" aqui e' ESTRITAMENTE o catalogo 47. Em `caixa_de_modulo`, logo
    acima, "modulo" quer dizer "modulo OU phoebus" (`any`) — nomes parecidos,
    conjuntos diferentes. `caixa_de_modulo` segue valendo para o board do
    GrowthHS, que e' comercial e onde Phoebus nao tem proposta.

    Recebe a lista de ordens JA FILTRADA pelo chamador. Lista vazia devolve
    False: caixa sem OS ativa nao tem para onde desviar nem card a suprimir.
    """
    ativas = list(ordens)
    return bool(ativas) and all(
        getattr(o, "equipamento_catalogo", None) == settings.EQUIPAMENTO_MODULO_ID
        for o in ativas)


def caixa_pula_posvendas(ordens) -> bool:
    """A caixa 100% Modulo e' a unica que nao passa pelo comercial.

    Delega a `caixa_so_de_modulo`: o criterio e' o mesmo, e o nome existe porque
    "pula o Pos-Vendas" e' a frase que descreve a decisao no `api/caixas.py`.
    Foi reaproveitar o predicado ERRADO para esta pergunta que mandou 7 caixas de
    Phoebus+Modulo ao Financeiro sem aceite em 18/09/2026.
    """
    return caixa_so_de_modulo(ordens)
