import httpx
import pytest

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


def test_enviar_card_sync_chama_post(monkeypatch, ativa):
    enviados = {}
    monkeypatch.setattr(taskhs_client, "_post", lambda payload: enviados.update(payload))
    taskhs_client.enviar_card_sync({"external_id": "9"})
    assert enviados["external_id"] == "9"


def test_enviar_card_sync_propaga_excecao(monkeypatch, ativa):
    def boom(payload):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(taskhs_client, "_post", boom)
    with pytest.raises(httpx.ConnectError):
        taskhs_client.enviar_card_sync({"external_id": "1"})
