"""Reversao do backfill: as caixas de Phoebus+Modulo voltam do Financeiro ao Pos-Vendas.

O alvo e' triplice de proposito — fase 10 E log do backfill E a regra nova dizendo que
nao devia ter desviado. So a fase pegaria caixa que chegou ao Financeiro sozinha; so o
log pegaria as 100% Modulo, que estao certas onde estao.
"""
import pytest

from app.api.ordens_acoes import registrar_log
from app.core.config import settings
from app.core import os_workflow as wf
from app.models import Caixa, Cliente, Equipamento, EquipamentoCliente, NotaFiscal, Ordem
from app.scripts import reverter_posvendas_phoebus_modulo as rev


@pytest.fixture(autouse=True)
def _fases(fases_seed):
    """`caixas.fase` e `ordens.fase` sao FK para `fases` — sem o seed o INSERT morre."""


def _caixa(db, *, catalogos, fase=10, com_log=True):
    """Caixa na fase informada, uma OS por id de catalogo, com o log do backfill."""
    cli = Cliente(nome="Cliente Rev")
    db.add(cli); db.flush()
    cx = Caixa(obs="Caixa rev", fase=fase)
    db.add(cx); db.flush()
    ordens = []
    for cat in catalogos:
        eq = db.query(Equipamento).filter(Equipamento.id == cat).one_or_none()
        if eq is None:
            eq = Equipamento(id=cat, descricao=f"Equipamento {cat}")
            db.add(eq); db.flush()
        ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id,
                                serie=f"S-{cx.id}-{cat}-{len(ordens)}")
        db.add(ec); db.flush()
        o = Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=fase, situacao="E",
                  caixa=cx.id)
        db.add(o); db.flush()
        ordens.append(o)
    if com_log:
        for o in ordens:
            registrar_log(db, o, None,
                          f"Caixa #{cx.id}: 6 -> 10 "
                          f"(fluxo do Phoebus/Modulo nao passa por Pos-Vendas)")
    db.commit(); db.refresh(cx)
    return cx.id, [o.id for o in ordens]


PAR = [settings.EQUIPAMENTO_PHOEBUS_ID, settings.EQUIPAMENTO_MODULO_ID]


def test_alvo_pega_phoebus_com_modulo_no_financeiro(db_session):
    cx_id, _ = _caixa(db_session, catalogos=PAR)
    assert [c.id for c in rev.caixas_alvo(db_session)] == [cx_id]


def test_alvo_ignora_caixa_so_de_modulo(db_session):
    """Essa desviou com razao: pela regra nova ela continua pulando o Pos-Vendas."""
    _caixa(db_session, catalogos=[settings.EQUIPAMENTO_MODULO_ID])
    assert rev.caixas_alvo(db_session) == []


def test_alvo_ignora_caixa_sem_o_log_do_backfill(db_session):
    """Caixa de aparelho comum que chegou ao Financeiro pelo fluxo normal nao e' erro."""
    _caixa(db_session, catalogos=[1], com_log=False)
    assert rev.caixas_alvo(db_session) == []


def test_alvo_ignora_caixa_em_outra_fase(db_session):
    """As 6 fechadas pelo ENC-ADM-20260918 ficam onde estao — decisao de 18/09/2026."""
    _caixa(db_session, catalogos=PAR, fase=8)
    assert rev.caixas_alvo(db_session) == []


def test_simula_por_padrao_sem_gravar(db_session):
    cx_id, os_ids = _caixa(db_session, catalogos=PAR)
    r = rev.processar(db_session, aplicar=False)
    assert r["caixas"] == 1 and r["ordens"] == 2

    db_session.expire_all()
    assert db_session.get(Caixa, cx_id).fase == wf.FASE_FINANCEIRO
    assert db_session.get(Ordem, os_ids[0]).fase == wf.FASE_FINANCEIRO


def test_aplicar_devolve_caixa_e_os_ao_posvendas(db_session):
    cx_id, os_ids = _caixa(db_session, catalogos=PAR)
    rev.processar(db_session, aplicar=True)

    db_session.expire_all()
    assert db_session.get(Caixa, cx_id).fase == wf.FASE_POSVENDAS
    assert all(db_session.get(Ordem, i).fase == wf.FASE_POSVENDAS for i in os_ids)


def test_aplicar_deixa_rastro_no_log_da_os(db_session):
    from app.models import LogOS
    _, os_ids = _caixa(db_session, catalogos=PAR)
    rev.processar(db_session, aplicar=True)

    textos = [l.texto for l in db_session.query(LogOS).filter(LogOS.os == os_ids[0]).all()]
    assert any("10 -> 6" in t for t in textos)


def test_recusa_lote_com_aceite(db_session):
    _, os_ids = _caixa(db_session, catalogos=PAR)
    o = db_session.get(Ordem, os_ids[0]); o.aceite = True; db_session.commit()

    with pytest.raises(rev.LoteSujo, match="aceite"):
        rev.processar(db_session, aplicar=False)


def test_recusa_lote_com_nota_fiscal_da_caixa(db_session):
    cx_id, _ = _caixa(db_session, catalogos=PAR)
    db_session.add(NotaFiscal(caixa=cx_id, numero="123",
                              arquivo_pdf="a.pdf", arquivo_xml="a.xml"))
    db_session.commit()

    with pytest.raises(rev.LoteSujo, match="nota fiscal"):
        rev.processar(db_session, aplicar=False)


def test_idempotente_segunda_rodada_nao_acha_nada(db_session):
    _caixa(db_session, catalogos=PAR)
    rev.processar(db_session, aplicar=True)
    assert rev.processar(db_session, aplicar=True)["caixas"] == 0
