"""So a caixa 100% Modulo sai do laboratorio direto para o Financeiro.

O servico de bancada do modulo nao passa pelo comercial. O aparelho Phoebus passa —
sozinho ou acompanhado do modulo dele — e por isso volta ao fluxo normal. Ate
18/09/2026 o criterio era o mesmo do bloqueio de card (`caixa_de_modulo`, `any`), e
7 caixas de Phoebus+Modulo foram parar no Financeiro sem aceite comercial.

O criterio agora e' `fluxo_modulo.caixa_pula_posvendas` (`all`).
"""
from app.core.config import settings
from app.models import Caixa, Cliente, Equipamento, EquipamentoCliente, Ordem


def _caixa_no_lab(db, *, catalogos, desfecho="concluido"):
    """Caixa em fase 5 com uma OS por id de catalogo em `catalogos`.

    Ids explicitos (nao autoincrement): a regra depende justamente deles. A lista
    permite montar a caixa Phoebus+Modulo, que e' o caso que o desvio NAO pega.
    """
    cli = Cliente(nome="Cliente Fluxo")
    db.add(cli); db.flush()
    cx = Caixa(obs="Caixa fluxo", fase=5)
    db.add(cx); db.flush()
    os_ids = []
    for cat in catalogos:
        eq = db.query(Equipamento).filter(Equipamento.id == cat).one_or_none()
        if eq is None:
            eq = Equipamento(id=cat, descricao=f"Equipamento {cat}")
            db.add(eq); db.flush()
        ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id,
                                serie=f"SER-{cat}-{len(os_ids)}")
        db.add(ec); db.flush()
        o = Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=5, situacao="E",
                  caixa=cx.id, desfecho_lab=desfecho)
        db.add(o); db.flush()
        os_ids.append(o.id)
    db.commit(); db.refresh(cx)
    return cx.id, os_ids


def test_caixa_so_de_modulo_vai_do_lab_direto_ao_financeiro(client_lab, db_session):
    cx_id, _ = _caixa_no_lab(db_session, catalogos=[settings.EQUIPAMENTO_MODULO_ID])
    r = client_lab.post(f"/caixas/{cx_id}/avancar", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["fase"] == 10
    assert all(o["fase"] == 10 for o in body["ordens"])   # fan-out acompanha


def test_caixa_de_phoebus_com_modulo_passa_pelo_posvendas(client_lab, db_session):
    """O bug de 18/09/2026. O par completo gera servico e precisa do aceite comercial —
    no TaskHS essas caixas param em 'LIBERADOS DO LABORATORIO', antes de 'Servicos'."""
    cx_id, _ = _caixa_no_lab(db_session, catalogos=[settings.EQUIPAMENTO_PHOEBUS_ID,
                                                   settings.EQUIPAMENTO_MODULO_ID])
    r = client_lab.post(f"/caixas/{cx_id}/avancar", json={})
    assert r.status_code == 200
    assert r.json()["fase"] == 6


def test_caixa_so_de_phoebus_passa_pelo_posvendas(client_lab, db_session):
    """O aparelho sozinho tambem gera servico."""
    cx_id, _ = _caixa_no_lab(db_session, catalogos=[settings.EQUIPAMENTO_PHOEBUS_ID])
    r = client_lab.post(f"/caixas/{cx_id}/avancar", json={})
    assert r.status_code == 200
    assert r.json()["fase"] == 6


def test_caixa_mista_passa_pelo_posvendas(client_lab, db_session):
    """Modulo + aparelho comum: o comum precisa do aceite, entao a caixa inteira vai."""
    cx_id, _ = _caixa_no_lab(db_session, catalogos=[settings.EQUIPAMENTO_MODULO_ID, 1])
    r = client_lab.post(f"/caixas/{cx_id}/avancar", json={})
    assert r.status_code == 200
    assert r.json()["fase"] == 6


def test_caixa_comum_continua_indo_para_posvendas(client_lab, db_session):
    """Controle positivo: sem ele, o desvio poderia valer para todo mundo e os
    testes acima passariam do mesmo jeito."""
    cx_id, _ = _caixa_no_lab(db_session, catalogos=[1])
    r = client_lab.post(f"/caixas/{cx_id}/avancar", json={})
    assert r.status_code == 200
    assert r.json()["fase"] == 6


def test_caixa_so_de_modulo_nao_ganha_aceite_ao_pular_posvendas(client_lab, db_session):
    """Aceite e' o registro da aprovacao comercial. Pulando a fase 6, ninguem
    aprovou nada — inventar `aceite=True` seria forjar um aval que nao houve."""
    cx_id, os_ids = _caixa_no_lab(db_session, catalogos=[settings.EQUIPAMENTO_MODULO_ID])
    assert client_lab.post(f"/caixas/{cx_id}/avancar", json={}).status_code == 200

    o = db_session.get(Ordem, os_ids[0])
    db_session.refresh(o)
    assert o.fase == 10
    assert o.aceite is not True
    assert o.data_aceite is None


def test_caixa_so_de_modulo_segue_o_fluxo_normal_do_financeiro_em_diante(client_lab, db_session):
    """Depois do desvio, a caixa volta a andar como qualquer outra: 10 -> 7 -> 8.
    Protege contra o desvio 'vazar' para as fases seguintes."""
    from app.core import os_workflow as wf
    cx_id, _ = _caixa_no_lab(db_session, catalogos=[settings.EQUIPAMENTO_MODULO_ID])
    assert client_lab.post(f"/caixas/{cx_id}/avancar", json={}).status_code == 200

    cx = db_session.get(Caixa, cx_id)
    db_session.refresh(cx)
    assert cx.fase == wf.FASE_FINANCEIRO
    assert wf.proxima_fase(cx.fase, pula_posvendas=True) == wf.FASE_PREPARANDO


def test_caixa_so_de_modulo_travada_no_lab_continua_travada(client_lab, db_session):
    """O desvio nao e' um atalho: aparelho sem desfecho ainda trava a saida do
    laboratorio, igual a qualquer caixa."""
    cx_id, _ = _caixa_no_lab(db_session, catalogos=[settings.EQUIPAMENTO_MODULO_ID],
                             desfecho="pendente")
    r = client_lab.post(f"/caixas/{cx_id}/avancar", json={})
    assert r.status_code == 409
    assert "faltam" in r.json()["detail"].lower()
