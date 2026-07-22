from app.models import Caixa, Ordem
from app.core import os_workflow as wf


def test_caixa_tem_coluna_fase():
    cx = Caixa(fase=4)
    assert cx.fase == 4


def test_ordem_desfecho_lab_default_pendente(db_session, fases_seed):
    # db_session: fixture do conftest que cria as tabelas em memoria
    from app.models import Cliente
    cli = Cliente(nome="ACME")
    db_session.add(cli)
    db_session.flush()
    o = Ordem(cliente=cli.id, fase=5)
    db_session.add(o)
    db_session.flush()
    assert o.desfecho_lab == "pendente"
    assert o.desfecho_lab_obs is None


def test_gate_lab_bloqueia_com_pendente():
    ok, motivo = wf.pode_avancar_caixa(wf.FASE_LABORATORIO, ["concluido", "pendente"])
    assert ok is False
    assert "1" in motivo  # menciona quantos faltam


def test_gate_lab_libera_com_todos_terminais():
    ok, motivo = wf.pode_avancar_caixa(wf.FASE_LABORATORIO, ["concluido", "sem_conserto"])
    assert ok is True
    assert motivo is None


def test_gate_outras_fases_nao_checam_desfecho():
    # Recebido->Lab e Pos-Vendas->Financeiro nao olham desfecho
    assert wf.pode_avancar_caixa(4, ["pendente", "pendente"])[0] is True
    assert wf.pode_avancar_caixa(6, ["pendente"])[0] is True


def test_gate_fase_terminal_nao_avanca():
    ok, _ = wf.pode_avancar_caixa(wf.FASE_FINALIZADA, [])
    assert ok is False
