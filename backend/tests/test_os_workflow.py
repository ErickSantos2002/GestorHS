from app.core import os_workflow as wf


def test_proxima_fase():
    assert wf.proxima_fase(4) == 5
    assert wf.proxima_fase(5) == 6
    assert wf.proxima_fase(6) == 7
    assert wf.proxima_fase(7) == 8
    assert wf.proxima_fase(8) is None   # terminal
    assert wf.proxima_fase(9) is None   # terminal


def test_eh_ativa():
    assert all(wf.eh_ativa(f) for f in (4, 5, 6, 7))
    assert not wf.eh_ativa(8)
    assert not wf.eh_ativa(9)


def test_constantes():
    assert wf.FASE_RECEBIDO == 4
    assert wf.FASE_FINALIZADA == 8
    assert wf.FASE_CANCELADA == 9
