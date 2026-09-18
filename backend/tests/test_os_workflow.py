from app.core import os_workflow as wf


def test_proxima_fase():
    assert wf.proxima_fase(4) == 5
    assert wf.proxima_fase(5) == 6
    assert wf.proxima_fase(6) == 10   # Pós-Vendas -> Financeiro
    assert wf.proxima_fase(10) == 7   # Financeiro -> Preparando Retorno
    assert wf.proxima_fase(7) == 8
    assert wf.proxima_fase(8) is None
    assert wf.proxima_fase(9) is None


def test_eh_ativa():
    assert all(wf.eh_ativa(f) for f in (4, 5, 6, 10, 7))
    assert not wf.eh_ativa(8)
    assert not wf.eh_ativa(9)


def test_posicao_ordena_logicamente():
    assert wf.posicao(4) < wf.posicao(5) < wf.posicao(6) < wf.posicao(10) < wf.posicao(7) < wf.posicao(8)
    assert wf.posicao(9) == 99      # cancelada/desconhecida -> fim
    assert wf.posicao(999) == 99


def test_constantes():
    assert wf.FASE_RECEBIDO == 4
    assert wf.FASE_FINANCEIRO == 10
    assert wf.FASE_FINALIZADA == 8
    assert wf.FASE_CANCELADA == 9


def test_proxima_fase_pulando_posvendas():
    """Caixa de Phoebus/Modulo sai do laboratorio direto para o Financeiro."""
    assert wf.proxima_fase(5, pula_posvendas=True) == 10


def test_rota_do_modulo_nunca_passa_por_posvendas():
    """Nenhuma fase leva a 6 na rota do modulo — e a 6 nao tem saida nela."""
    fase, visitadas = wf.FASE_RECEBIDO, []
    while fase is not None:
        visitadas.append(fase)
        fase = wf.proxima_fase(fase, pula_posvendas=True)
    assert visitadas == [4, 5, 10, 7, 8]


def test_pula_posvendas_nao_mexe_no_resto_do_fluxo():
    """So a saida do laboratorio muda; as outras transicoes sao as mesmas."""
    for origem in (4, 10, 7, 8, 9):
        assert wf.proxima_fase(origem, pula_posvendas=True) == wf.proxima_fase(origem)


def test_posicao_nao_muda_com_a_rota_do_modulo():
    """A 6 continua na ordem logica — so nao e visitada. Protege `posicao()`,
    de que dependem as janelas de nota fiscal e certificado."""
    assert wf.posicao(5) < wf.posicao(6) < wf.posicao(10)
