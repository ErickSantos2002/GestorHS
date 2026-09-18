"""Encerramento administrativo das caixas de Phoebus/Modulo que ja sairam da empresa.

Depois do backfill de 18/09/2026 elas ficaram paradas no Financeiro (fase 10) sem nota
fiscal e sem rastreio — o fluxo normal nao consegue fecha-las. Este script fecha na mao,
deixando marcador rastreavel, no mesmo criterio do ENC-ADM de 30/07/2026.
"""
import pytest

from app.core.config import settings
from app.models import Caixa, Cliente, Equipamento, EquipamentoCliente, LogOS, Ordem
from app.scripts.finalizar_caixas_phoebus import MARCADOR, caixas_alvo, processar


@pytest.fixture(autouse=True)
def _fases(fases_seed):
    """`caixas.fase` e `ordens.fase` sao FK para `fases`."""


def _caixa(db, *, catalogo_id=None, fase=10, cancelada=False):
    catalogo_id = catalogo_id if catalogo_id is not None else settings.EQUIPAMENTO_MODULO_ID
    cli = Cliente(nome=f"Cliente {catalogo_id}")
    eq = db.query(Equipamento).filter(Equipamento.id == catalogo_id).one_or_none()
    if eq is None:
        eq = Equipamento(id=catalogo_id, descricao=f"Equipamento {catalogo_id}")
        db.add(eq)
    db.add(cli); db.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie=f"S-{catalogo_id}")
    cx = Caixa(obs="Caixa enc", fase=fase)
    db.add_all([ec, cx]); db.flush()
    o = Ordem(cliente=cli.id, equipamento_cliente=ec.id,
              fase=9 if cancelada else fase, situacao="C" if cancelada else "E",
              caixa=cx.id, desfecho_lab="concluido")
    db.add(o); db.commit(); db.refresh(cx)
    return cx.id, o.id


def test_alvo_pega_caixa_de_modulo_no_financeiro(db_session):
    cx_id, _ = _caixa(db_session)
    assert [c.id for c in caixas_alvo(db_session, excluir=set())] == [cx_id]


def test_excluir_tira_a_caixa_da_lista(db_session):
    """E' a lista que o Erick passou: as caixas que ainda estao na empresa."""
    cx_id, _ = _caixa(db_session)
    assert caixas_alvo(db_session, excluir={cx_id}) == []


def test_alvo_ignora_caixa_comum_no_financeiro(db_session):
    """Controle positivo: caixa de aparelho normal no Financeiro tem nota fiscal a
    receber e segue o fluxo dela."""
    _caixa(db_session, catalogo_id=1)
    assert caixas_alvo(db_session, excluir=set()) == []


def test_alvo_ignora_caixa_de_modulo_em_outra_fase(db_session):
    """So a fase 10 e' alvo — no laboratorio a caixa ainda tem servico a fazer."""
    _caixa(db_session, fase=5)
    assert caixas_alvo(db_session, excluir=set()) == []


def test_simula_por_padrao_sem_gravar(db_session):
    cx_id, os_id = _caixa(db_session)
    r = processar(db_session, excluir=set(), aplicar=False)

    assert r["caixas"] == 1 and r["ordens"] == 1
    assert db_session.get(Caixa, cx_id).fase == 10
    assert db_session.get(Ordem, os_id).fase == 10


def test_aplicar_finaliza_caixa_e_os(db_session):
    cx_id, os_id = _caixa(db_session)
    processar(db_session, excluir=set(), aplicar=True)

    assert db_session.get(Caixa, cx_id).fase == 8
    o = db_session.get(Ordem, os_id)
    assert o.fase == 8
    assert o.situacao == "F"
    assert o.data_retorno is not None


def test_aplicar_grava_o_marcador_rastreavel(db_session):
    """Sem o marcador nao da para achar nem reverter essas OS depois — foi o que
    salvou o encerramento de 30/07 (`cod_retorno='ENC-ADM-20260730'`)."""
    _, os_id = _caixa(db_session)
    processar(db_session, excluir=set(), aplicar=True)

    assert db_session.get(Ordem, os_id).cod_retorno == MARCADOR


def test_aplicar_nao_marca_pago_nem_aceite(db_session):
    """Afirmaria pagamento e aval do cliente que ninguem confirmou. Mesmo criterio
    do ENC-ADM de julho e do legado."""
    _, os_id = _caixa(db_session)
    processar(db_session, excluir=set(), aplicar=True)

    o = db_session.get(Ordem, os_id)
    assert o.pago is not True
    assert o.aceite is not True
    assert o.data_pagamento is None
    assert o.data_aceite is None


def test_aplicar_deixa_rastro_no_log_da_os(db_session):
    _, os_id = _caixa(db_session)
    processar(db_session, excluir=set(), aplicar=True)

    logs = db_session.query(LogOS).filter(LogOS.os == os_id).all()
    assert len(logs) == 1
    assert MARCADOR in logs[0].texto


def test_nao_mexe_em_os_cancelada(db_session):
    cx_id, os_ativa = _caixa(db_session)
    cancelada = Ordem(cliente=db_session.get(Ordem, os_ativa).cliente, fase=9,
                      situacao="C", caixa=cx_id, desfecho_lab="concluido")
    db_session.add(cancelada); db_session.commit()

    r = processar(db_session, excluir=set(), aplicar=True)

    assert r["ordens"] == 1
    assert db_session.get(Ordem, cancelada.id).fase == 9
    assert db_session.get(Ordem, cancelada.id).cod_retorno is None


def test_idempotente_segunda_rodada_nao_acha_nada(db_session):
    _caixa(db_session)
    processar(db_session, excluir=set(), aplicar=True)

    assert caixas_alvo(db_session, excluir=set()) == []
    assert processar(db_session, excluir=set(), aplicar=True)["caixas"] == 0


def test_alvo_ignora_caixa_com_phoebus_no_financeiro(db_session):
    """Caixa com o aparelho dentro segue o fluxo dela — inclusive a que voltou para o
    Pos-Vendas na reversao de 18/09/2026."""
    _caixa(db_session, catalogo_id=settings.EQUIPAMENTO_PHOEBUS_ID)
    assert caixas_alvo(db_session, excluir=set()) == []
