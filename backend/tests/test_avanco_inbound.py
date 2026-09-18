"""Regra compartilhada do avanco inbound 6 -> 10.

Dois integradores chamam esse avanco por caminhos proprios — o GrowthHS ao marcar
a proposta como "Ganho" e o TaskHS ao mover o card para a lista do Financeiro — e a
pergunta "essa caixa pode avancar agora?" e' a mesma nos dois.
"""
from app.core import avanco_inbound as ai
from app.core import os_workflow as wf


def test_posvendas_avanca():
    assert ai.estado_para_avanco(wf.FASE_POSVENDAS) == ai.AVANCAR


def test_fases_ja_avancadas_sao_no_op():
    """Chamada repetida nao pode virar erro: quem chama nao sabe se ja mandou este
    mesmo evento antes. No caso do TaskHS o reenvio e' garantido por construcao —
    o GestorHS move o card para a lista do Financeiro ao avancar, o que dispara a
    automacao de volta."""
    for fase in (wf.FASE_FINANCEIRO, wf.FASE_PREPARANDO, wf.FASE_FINALIZADA):
        assert ai.estado_para_avanco(fase) == ai.NO_OP


def test_fases_anteriores_ao_posvendas_sao_erro():
    assert ai.estado_para_avanco(wf.FASE_RECEBIDO) == ai.FASE_ERRADA
    assert ai.estado_para_avanco(wf.FASE_LABORATORIO) == ai.FASE_ERRADA


def test_caixa_arquivada_e_erro_nao_no_op():
    """Fase None e' caixa cancelada/arquivada. Avancar isso e' erro de quem chamou,
    nao repeticao inofensiva — por isso nao cai no no_op."""
    assert ai.estado_para_avanco(None) == ai.FASE_ERRADA


def test_cancelada_e_erro():
    assert ai.estado_para_avanco(wf.FASE_CANCELADA) == ai.FASE_ERRADA


def test_fases_ja_avancadas_nao_inclui_posvendas():
    """Se a 6 entrasse nessa tupla, TODA chamada viraria no-op em silencio e a
    integracao pararia de funcionar sem erro nenhum."""
    assert wf.FASE_POSVENDAS not in ai.FASES_JA_AVANCADAS
