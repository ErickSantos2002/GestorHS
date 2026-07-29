"""Testes do endpoint inbound `POST /integracao/growthhs/caixas/{id}/ganho`,
chamado pelo GrowthHS ao mover um card de proposta para "Ganho" — precisa
avancar a caixa correspondente de Pos-Vendas(6) para Financeiro(10).

Usa o `client` (TestClient com db_session override) do conftest.py, ja que o
endpoint mora no app principal; a autenticacao aqui e via header X-API-Key
(nao JWT), entao nao precisa de client_com/client_fin autenticado.
"""
from app.core.config import settings
from app.models import Caixa, Ordem, LogOS


def test_caixa_posvendas_avanca_para_financeiro(client, caixa_posvendas, db_session, monkeypatch):
    monkeypatch.setattr(settings, "GROWTHHS_INBOUND_API_KEY", "segredo-123")

    resp = client.post(
        f"/integracao/growthhs/caixas/{caixa_posvendas}/ganho",
        json={"observacao": "Proposta #123"},
        headers={"X-API-Key": "segredo-123"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"movida": True, "caixa_id": caixa_posvendas, "fase": 10}

    ordens = db_session.query(Ordem).filter(Ordem.caixa == caixa_posvendas).all()
    assert len(ordens) == 2
    for o in ordens:
        assert o.aceite is True
        assert o.fase == 10

    logs = db_session.query(LogOS).filter(LogOS.os.in_([o.id for o in ordens])).all()
    assert any("Proposta #123" in (log.texto or "") for log in logs)


def test_ganho_grava_numero_proposta_ao_avancar(client, caixa_posvendas, db_session, monkeypatch):
    monkeypatch.setattr(settings, "GROWTHHS_INBOUND_API_KEY", "segredo-123")

    resp = client.post(
        f"/integracao/growthhs/caixas/{caixa_posvendas}/ganho",
        json={"observacao": "Proposta #123", "numero_proposta": 123},
        headers={"X-API-Key": "segredo-123"},
    )
    assert resp.status_code == 200

    cx = db_session.query(Caixa).filter(Caixa.id == caixa_posvendas).first()
    assert cx.numero_proposta == 123


def test_ganho_grava_numero_proposta_mesmo_no_noop(client, caixa_financeiro, db_session, monkeypatch):
    monkeypatch.setattr(settings, "GROWTHHS_INBOUND_API_KEY", "segredo-123")

    resp = client.post(
        f"/integracao/growthhs/caixas/{caixa_financeiro}/ganho",
        json={"observacao": "Proposta #999", "numero_proposta": 999},
        headers={"X-API-Key": "segredo-123"},
    )
    assert resp.status_code == 200
    assert resp.json()["movida"] is False

    cx = db_session.query(Caixa).filter(Caixa.id == caixa_financeiro).first()
    assert cx.numero_proposta == 999


def test_ganho_sem_numero_proposta_fica_none(client, caixa_posvendas, db_session, monkeypatch):
    monkeypatch.setattr(settings, "GROWTHHS_INBOUND_API_KEY", "segredo-123")

    resp = client.post(
        f"/integracao/growthhs/caixas/{caixa_posvendas}/ganho",
        json={"observacao": "sem numero"},
        headers={"X-API-Key": "segredo-123"},
    )
    assert resp.status_code == 200

    cx = db_session.query(Caixa).filter(Caixa.id == caixa_posvendas).first()
    assert cx.numero_proposta is None


def test_caixa_ja_em_financeiro_nao_reavanca(client, caixa_financeiro, db_session, monkeypatch):
    monkeypatch.setattr(settings, "GROWTHHS_INBOUND_API_KEY", "segredo-123")

    resp = client.post(
        f"/integracao/growthhs/caixas/{caixa_financeiro}/ganho",
        json={"observacao": "Proposta #999"},
        headers={"X-API-Key": "segredo-123"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"movida": False, "caixa_id": caixa_financeiro, "fase": 10}

    # nao deve ter logado nada referente a essa chamada (sem duplo efeito)
    ordens = db_session.query(Ordem).filter(Ordem.caixa == caixa_financeiro).all()
    logs = db_session.query(LogOS).filter(LogOS.os.in_([o.id for o in ordens])).all()
    assert not any("Proposta #999" in (log.texto or "") for log in logs)


def test_caixa_em_laboratorio_devolve_409(client, caixa_lab_todos_terminais, monkeypatch):
    monkeypatch.setattr(settings, "GROWTHHS_INBOUND_API_KEY", "segredo-123")

    resp = client.post(
        f"/integracao/growthhs/caixas/{caixa_lab_todos_terminais}/ganho",
        json={"observacao": "Proposta #1"},
        headers={"X-API-Key": "segredo-123"},
    )
    assert resp.status_code == 409


def test_caixa_inexistente_devolve_404(client, monkeypatch):
    monkeypatch.setattr(settings, "GROWTHHS_INBOUND_API_KEY", "segredo-123")

    resp = client.post(
        "/integracao/growthhs/caixas/999999/ganho",
        json={"observacao": "Proposta #1"},
        headers={"X-API-Key": "segredo-123"},
    )
    assert resp.status_code == 404


def test_chave_errada_devolve_401(client, caixa_posvendas, monkeypatch):
    monkeypatch.setattr(settings, "GROWTHHS_INBOUND_API_KEY", "segredo-123")

    resp = client.post(
        f"/integracao/growthhs/caixas/{caixa_posvendas}/ganho",
        json={"observacao": "Proposta #1"},
        headers={"X-API-Key": "chave-errada"},
    )
    assert resp.status_code == 401


def test_chave_vazia_devolve_503(client, caixa_posvendas, monkeypatch):
    monkeypatch.setattr(settings, "GROWTHHS_INBOUND_API_KEY", "")

    resp = client.post(
        f"/integracao/growthhs/caixas/{caixa_posvendas}/ganho",
        json={"observacao": "Proposta #1"},
        headers={"X-API-Key": "qualquer-coisa"},
    )
    assert resp.status_code == 503
