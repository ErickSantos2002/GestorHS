import pytest

from app.integrations import taskhs_client
from app.core.config import settings


class _Resp:
    def __init__(self, status_code, text="ok"):
        self.status_code = status_code
        self.text = text


def _ativa(monkeypatch):
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "https://task.test")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "k")


def test_enviar_card_loga_sucesso(monkeypatch):
    _ativa(monkeypatch)
    chamadas = []
    monkeypatch.setattr(taskhs_client, "registrar_log_integracao",
                        lambda **kw: chamadas.append(kw))
    monkeypatch.setattr(taskhs_client, "_post", lambda p: _Resp(200))
    taskhs_client.enviar_card({"source": "gestorhs", "external_id": "1"})
    assert chamadas and chamadas[0]["integracao"] == "taskhs"
    assert chamadas[0]["status"] == "sucesso"
    assert chamadas[0]["http_status"] == 200


def test_enviar_card_loga_erro_http(monkeypatch):
    _ativa(monkeypatch)
    chamadas = []
    monkeypatch.setattr(taskhs_client, "registrar_log_integracao",
                        lambda **kw: chamadas.append(kw))
    monkeypatch.setattr(taskhs_client, "_post", lambda p: _Resp(422, "campo X invalido"))
    taskhs_client.enviar_card({"source": "gestorhs", "external_id": "1"})
    assert chamadas[0]["status"] == "erro"
    assert chamadas[0]["http_status"] == 422
    assert "campo X" in chamadas[0]["resposta"]


def test_enviar_card_loga_pulado_desligado(monkeypatch):
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "")
    chamadas = []
    monkeypatch.setattr(taskhs_client, "registrar_log_integracao",
                        lambda **kw: chamadas.append(kw))
    taskhs_client.enviar_card({"source": "gestorhs", "external_id": "1"})
    assert chamadas[0]["status"] == "pulado"
    assert chamadas[0]["motivo"] == "desligado"


def test_enviar_card_sync_levanta_em_erro(monkeypatch):
    _ativa(monkeypatch)
    monkeypatch.setattr(taskhs_client, "registrar_log_integracao", lambda **kw: None)
    monkeypatch.setattr(taskhs_client, "_post", lambda p: _Resp(500, "boom"))
    with pytest.raises(RuntimeError):
        taskhs_client.enviar_card_sync({"source": "gestorhs", "external_id": "1"})
