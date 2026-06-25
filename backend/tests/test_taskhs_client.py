import httpx
import pytest
from types import SimpleNamespace

from app.core.config import settings
from app.integrations import taskhs_client


@pytest.fixture()
def ativa(monkeypatch):
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "http://taskhs.test/api")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "k-123")


def test_integracao_ativa_depende_das_envs(monkeypatch):
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "")
    assert taskhs_client.integracao_ativa() is False
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "http://x/api")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "k")
    assert taskhs_client.integracao_ativa() is True


def test_enviar_card_noop_sem_key(monkeypatch):
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "")
    chamou = []
    monkeypatch.setattr(httpx, "post", lambda *a, **k: chamou.append(1))
    taskhs_client.enviar_card({"external_id": "1"})
    assert chamou == []  # nem tentou


def test_enviar_card_faz_post_correto(monkeypatch, ativa):
    capturado = {}

    class FakeResp:
        def raise_for_status(self):
            return None

    def fake_post(url, json, headers, timeout):
        capturado.update(url=url, json=json, headers=headers, timeout=timeout)
        return FakeResp()

    monkeypatch.setattr(httpx, "post", fake_post)
    taskhs_client.enviar_card({"external_id": "1234"})
    assert capturado["url"] == "http://taskhs.test/api/integration/cards"
    assert capturado["headers"]["X-API-Key"] == "k-123"
    assert capturado["json"] == {"external_id": "1234"}
    assert capturado["timeout"] == 5


def test_enviar_card_engole_excecao(monkeypatch, ativa):
    def boom(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "post", boom)
    taskhs_client.enviar_card({"external_id": "1"})  # nao deve levantar


def test_espelhar_os_monta_payload_e_propaga(monkeypatch, ativa):
    enviados = {}

    def fake_post(payload):
        enviados.update(payload)

    monkeypatch.setattr(taskhs_client, "_post", fake_post)
    ordem = SimpleNamespace(
        id=7, cliente_nome="Cli", equipamento_descricao="Baf",
        equipamento_serie="S1", prox_calibragem=None, obs=None,
    )
    taskhs_client.espelhar_os(ordem, lista="🔬Laboratorio Calibracao", arquivado=False)
    assert enviados["external_id"] == "7"
    assert enviados["list"] == "🔬Laboratorio Calibracao"
    assert enviados["archived"] is False
