"""`PUT /integracao/growthhs/caixas/{id}/proposta` — o CRM troca o numero da proposta
da caixa por API key, antes de gravar no card. Mesma regra da tela
(`PUT /caixas/{id}/proposta`): o miolo e' `aplicar_troca_proposta`, compartilhado.

O CRM mostra o `detail` das recusas direto no toast, entao as mensagens sao conferidas
aqui tambem: portugues legivel, com nome de cliente em vez de id.
"""
import pytest

from app.core.config import settings
from app.integrations import taskhs_client

CHAVE = {"X-API-Key": "segredo-123"}


@pytest.fixture(autouse=True)
def _chave(monkeypatch):
    monkeypatch.setattr(settings, "GROWTHHS_INBOUND_API_KEY", "segredo-123")


@pytest.fixture()
def captura(monkeypatch):
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "http://taskhs.test/api")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "k-123")
    chamadas = []
    monkeypatch.setattr(taskhs_client, "enviar_card", lambda payload: chamadas.append(payload))
    return chamadas


@pytest.fixture()
def cenario(db_session, fases_seed):
    """O caso da caixa 1212: aponta para a 474 (PM-SP), devia ser a 476 (Phoenix)."""
    from app.models import Caixa, Cliente, Ordem, Proposta
    pm = Cliente(nome="POLICIA MILITAR")
    phoenix = Cliente(nome="PHOENIX DO PECEM")
    outro = Cliente(nome="OUTRO CLIENTE")
    db_session.add_all([pm, phoenix, outro])
    db_session.flush()
    cx = Caixa(fase=6, cliente_principal=phoenix.id, numero_proposta=474)
    db_session.add(cx)
    db_session.flush()
    os_ = Ordem(cliente=phoenix.id, situacao="E", fase=6, caixa=cx.id, tipo_servico="C")
    db_session.add(os_)
    db_session.add_all([
        Proposta(numero=474, cliente=pm.id),
        Proposta(numero=476, cliente=phoenix.id),
        Proposta(numero=480, cliente=outro.id),
        Proposta(numero=481, cliente=phoenix.id, is_deleted=True),
    ])
    db_session.commit()
    db_session.refresh(cx)
    return {"caixa": cx, "ordem": os_}


def _put(client, caixa_id, corpo, headers=CHAVE):
    return client.put(f"/integracao/growthhs/caixas/{caixa_id}/proposta", json=corpo, headers=headers)


def test_troca_antes_do_ganho_e_loga_sem_usuario(client, cenario, db_session):
    from app.models import LogOS
    cx = cenario["caixa"]
    r = _put(client, cx.id, {"numero": 476, "observacao": "card #88 · por Fulana"})
    assert r.status_code == 200, r.text
    assert r.json() == {"caixa_id": cx.id, "numero_proposta": 476, "alterada": True}
    db_session.refresh(cx)
    assert cx.numero_proposta == 476
    logs = db_session.query(LogOS).filter(LogOS.os == cenario["ordem"].id).all()
    assert [l.texto for l in logs] == [
        f"Caixa #{cx.id}: proposta #474 -> #476 (via GrowthHS: card #88 · por Fulana)"]
    assert logs[0].usuario is None


def test_sem_observacao(client, cenario, db_session):
    from app.models import LogOS
    cx = cenario["caixa"]
    assert _put(client, cx.id, {"numero": 476, "observacao": None}).status_code == 200
    textos = [l.texto for l in db_session.query(LogOS).filter(LogOS.os == cenario["ordem"].id)]
    assert textos == [f"Caixa #{cx.id}: proposta #474 -> #476 (via GrowthHS)"]


def test_caixa_sem_proposta_antes(client, cenario, db_session):
    from app.models import LogOS
    cx = cenario["caixa"]
    cx.numero_proposta = None
    db_session.commit()
    assert _put(client, cx.id, {"numero": 476}).json()["alterada"] is True
    textos = [l.texto for l in db_session.query(LogOS).filter(LogOS.os == cenario["ordem"].id)]
    assert textos == [f"Caixa #{cx.id}: proposta (nenhuma) -> #476 (via GrowthHS)"]


def test_reespelha_o_card(client, cenario, captura):
    captura.clear()
    assert _put(client, cenario["caixa"].id, {"numero": 476}).status_code == 200
    assert len(captura) == 1
    assert "Proposta #476" in captura[0]["obs3"]


def test_numero_igual_devolve_alterada_false(client, cenario, captura, db_session):
    from app.models import LogOS
    cx = cenario["caixa"]
    captura.clear()
    r = _put(client, cx.id, {"numero": 474})
    assert r.status_code == 200
    assert r.json() == {"caixa_id": cx.id, "numero_proposta": 474, "alterada": False}
    assert captura == []
    assert db_session.query(LogOS).filter(LogOS.os == cenario["ordem"].id).count() == 0


def test_sem_chave_401(client, cenario):
    assert _put(client, cenario["caixa"].id, {"numero": 476}, headers={}).status_code == 401
    assert _put(client, cenario["caixa"].id, {"numero": 476},
                headers={"X-API-Key": "errada"}).status_code == 401


def test_caixa_inexistente_404(client, cenario):
    r = _put(client, 98765, {"numero": 476})
    assert r.status_code == 404
    assert "caixa" in r.json()["detail"].lower()


def test_proposta_inexistente_404(client, cenario):
    r = _put(client, cenario["caixa"].id, {"numero": 99999})
    assert r.status_code == 404
    assert "99999" in r.json()["detail"]


def test_outro_cliente_422_com_nomes(client, cenario, db_session):
    cx = cenario["caixa"]
    r = _put(client, cx.id, {"numero": 480})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert "OUTRO CLIENTE" in detail and "PHOENIX DO PECEM" in detail
    db_session.refresh(cx)
    assert cx.numero_proposta == 474


def test_desabilitada_422(client, cenario):
    r = _put(client, cenario["caixa"].id, {"numero": 481})
    assert r.status_code == 422
    assert "desabilitada" in r.json()["detail"]


@pytest.mark.parametrize("fase", [8, 9, None])
def test_fora_da_janela_409(client, cenario, db_session, fase):
    cx = cenario["caixa"]
    cx.fase = fase
    db_session.commit()
    r = _put(client, cx.id, {"numero": 476})
    assert r.status_code == 409
    assert "Preparando Retorno" in r.json()["detail"]
