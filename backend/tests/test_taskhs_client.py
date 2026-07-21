import httpx
import pytest

from app.core.config import settings
from app.integrations import taskhs_client


class FakeResp:
    def __init__(self, status_code=200, text="ok"):
        self.status_code = status_code
        self.text = text


@pytest.fixture()
def ativa(monkeypatch):
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "http://taskhs.test/api")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "k-123")


@pytest.fixture(autouse=True)
def _sem_banco(monkeypatch):
    # o writer abre SessionLocal proprio; nestes testes de unidade nao queremos DB
    monkeypatch.setattr(taskhs_client, "registrar_log_integracao", lambda **kw: None)


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

    def fake_post(url, json, headers, timeout):
        capturado.update(url=url, json=json, headers=headers, timeout=timeout)
        return FakeResp(200)

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

    def fake(payload):
        enviados.update(payload)
        return FakeResp(200)

    monkeypatch.setattr(taskhs_client, "_post", fake)
    taskhs_client.enviar_card_sync({"external_id": "9"})
    assert enviados["external_id"] == "9"


def test_enviar_card_sync_propaga_excecao(monkeypatch, ativa):
    def boom(payload):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(taskhs_client, "_post", boom)
    with pytest.raises(httpx.ConnectError):
        taskhs_client.enviar_card_sync({"external_id": "1"})
