"""Caixa de Phoebus/Modulo sai do laboratorio direto para o Financeiro.

O servico desses aparelhos nao passa pelo comercial — e' o mesmo motivo pelo qual a
caixa deles ja nao vira card no TaskHS/GrowthHS. O criterio e' UM so:
`fluxo_modulo.caixa_de_modulo`.
"""
import pytest

from app.core.config import settings
from app.models import Caixa, Cliente, Equipamento, EquipamentoCliente, Ordem


def _caixa_no_lab(db, *, catalogo_id, desfecho="concluido"):
    """Caixa em fase 5 com 1 OS pronta para sair do laboratorio.

    Id do catalogo explicito (nao autoincrement): a regra depende justamente dele.
    """
    cli = Cliente(nome="Cliente Fluxo")
    eq = Equipamento(id=catalogo_id, descricao=f"Equipamento {catalogo_id}")
    db.add_all([cli, eq]); db.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie=f"SER-{catalogo_id}")
    cx = Caixa(obs="Caixa fluxo", fase=5)
    db.add_all([ec, cx]); db.flush()
    o = Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=5, situacao="E",
              caixa=cx.id, desfecho_lab=desfecho)
    db.add(o); db.commit(); db.refresh(cx)
    return cx.id, o.id


@pytest.mark.parametrize("catalogo_id", [
    settings.EQUIPAMENTO_PHOEBUS_ID,
    settings.EQUIPAMENTO_MODULO_ID,
])
def test_caixa_de_modulo_vai_do_lab_direto_ao_financeiro(client_lab, db_session, catalogo_id):
    cx_id, _ = _caixa_no_lab(db_session, catalogo_id=catalogo_id)
    r = client_lab.post(f"/caixas/{cx_id}/avancar", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["fase"] == 10
    assert all(o["fase"] == 10 for o in body["ordens"])   # fan-out acompanha


def test_caixa_comum_continua_indo_para_posvendas(client_lab, db_session):
    """Controle positivo: sem ele, o desvio poderia valer para todo mundo e os
    testes acima passariam do mesmo jeito."""
    cx_id, _ = _caixa_no_lab(db_session, catalogo_id=1)
    r = client_lab.post(f"/caixas/{cx_id}/avancar", json={})
    assert r.status_code == 200
    assert r.json()["fase"] == 6


def test_caixa_de_modulo_nao_ganha_aceite_ao_pular_posvendas(client_lab, db_session):
    """Aceite e' o registro da aprovacao comercial. Pulando a fase 6, ninguem
    aprovou nada — inventar `aceite=True` seria forjar um aval que nao houve."""
    cx_id, os_id = _caixa_no_lab(db_session, catalogo_id=settings.EQUIPAMENTO_PHOEBUS_ID)
    assert client_lab.post(f"/caixas/{cx_id}/avancar", json={}).status_code == 200

    o = db_session.get(Ordem, os_id)
    db_session.refresh(o)
    assert o.fase == 10
    assert o.aceite is not True
    assert o.data_aceite is None


def test_caixa_de_modulo_segue_o_fluxo_normal_do_financeiro_em_diante(client_lab, db_session):
    """Depois do desvio, a caixa volta a andar como qualquer outra: 10 -> 7 -> 8.
    Protege contra o desvio 'vazar' para as fases seguintes."""
    from app.core import os_workflow as wf
    cx_id, _ = _caixa_no_lab(db_session, catalogo_id=settings.EQUIPAMENTO_MODULO_ID)
    assert client_lab.post(f"/caixas/{cx_id}/avancar", json={}).status_code == 200

    cx = db_session.get(Caixa, cx_id)
    db_session.refresh(cx)
    assert cx.fase == wf.FASE_FINANCEIRO
    assert wf.proxima_fase(cx.fase, pula_posvendas=True) == wf.FASE_PREPARANDO


def test_caixa_de_modulo_travada_no_lab_continua_travada(client_lab, db_session):
    """O desvio nao e' um atalho: aparelho sem desfecho ainda trava a saida do
    laboratorio, igual a qualquer caixa."""
    cx_id, _ = _caixa_no_lab(db_session, catalogo_id=settings.EQUIPAMENTO_PHOEBUS_ID,
                             desfecho="pendente")
    r = client_lab.post(f"/caixas/{cx_id}/avancar", json={})
    assert r.status_code == 409
    assert "faltam" in r.json()["detail"].lower()
