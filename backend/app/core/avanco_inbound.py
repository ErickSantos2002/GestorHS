"""Regra do avanco inbound da caixa: Pos-Vendas(6) -> Financeiro(10). Puro, sem I/O.

Dois integradores pedem esse avanco por caminhos proprios — o GrowthHS ao marcar a
proposta como "Ganho" e o TaskHS ao mover o card para a lista do Financeiro — e a
pergunta "essa caixa pode avancar agora?" e' a mesma nos dois. O que NAO e' comum
(a chave de API, a obs gravada no log, as validacoes de escopo de cada um) fica em
cada endpoint.
"""
from app.core import os_workflow as wf

AVANCAR = "avancar"
NO_OP = "no_op"
FASE_ERRADA = "fase_errada"

# Fases que ja passaram do ponto de avanco. Chamada repetida vira no-op, nao erro:
# quem chama nao sabe se ja mandou este mesmo evento antes. No TaskHS o reenvio e'
# garantido por construcao — avancar a caixa move o card para a lista do
# Financeiro, o que dispara a automacao de volta. E' aqui que esse laco morre.
FASES_JA_AVANCADAS = (wf.FASE_FINANCEIRO, wf.FASE_PREPARANDO, wf.FASE_FINALIZADA)


def estado_para_avanco(fase: int | None) -> str:
    """O que fazer com uma caixa nesta fase: AVANCAR, NO_OP ou FASE_ERRADA.

    Recebe a FASE, nao a caixa: a regra nao depende de mais nada, e um `int` deixa
    o teste sem banco.

    `None` e' caixa arquivada (cancelada) e devolve FASE_ERRADA, nao NO_OP —
    avancar caixa arquivada e' erro de quem chamou, nao repeticao inofensiva.
    """
    if fase in FASES_JA_AVANCADAS:
        return NO_OP
    if fase == wf.FASE_POSVENDAS:
        return AVANCAR
    return FASE_ERRADA
