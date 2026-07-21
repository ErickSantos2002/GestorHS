import pytest

from app.integrations import hsgrowth_client
from app.core.config import settings


class _Resp:
    def __init__(self, status_code, payload=None, text="ok"):
        self.status_code = status_code
        self._payload = payload or {"created": True}
        self.text = text

    def json(self):
        return self._payload


def _ativa(monkeypatch):
    monkeypatch.setattr(settings, "HSGROWTH_BASE_URL", "https://growth.test")
    monkeypatch.setattr(settings, "HSGROWTH_API_KEY", "k")


def test_enviar_card_loga_sucesso(monkeypatch):
    _ativa(monkeypatch)
    chamadas = []
    monkeypatch.setattr(hsgrowth_client, "registrar_log_integracao",
                        lambda **kw: chamadas.append(kw))
    monkeypatch.setattr(hsgrowth_client, "_post", lambda p: _Resp(200))
    hsgrowth_client.enviar_card({"source": "gestorhs.os", "external_id": "10853"})
    assert chamadas[0]["integracao"] == "growthhs"
    assert chamadas[0]["status"] == "sucesso"


def test_enviar_card_loga_pulado_desligado(monkeypatch):
    monkeypatch.setattr(settings, "HSGROWTH_BASE_URL", "")
    monkeypatch.setattr(settings, "HSGROWTH_API_KEY", "")
    chamadas = []
    monkeypatch.setattr(hsgrowth_client, "registrar_log_integracao",
                        lambda **kw: chamadas.append(kw))
    hsgrowth_client.enviar_card({"source": "gestorhs.os", "external_id": "10853"})
    assert chamadas[0]["status"] == "pulado"
    assert chamadas[0]["motivo"] == "desligado"


def test_enviar_card_sync_devolve_json_e_loga(monkeypatch):
    _ativa(monkeypatch)
    monkeypatch.setattr(hsgrowth_client, "registrar_log_integracao", lambda **kw: None)
    monkeypatch.setattr(hsgrowth_client, "_post",
                        lambda p: _Resp(200, {"id": 1, "created": True}))
    out = hsgrowth_client.enviar_card_sync({"source": "gestorhs.os", "external_id": "10853"})
    assert out["created"] is True


def test_enviar_card_sync_levanta_em_erro(monkeypatch):
    _ativa(monkeypatch)
    monkeypatch.setattr(hsgrowth_client, "registrar_log_integracao", lambda **kw: None)
    monkeypatch.setattr(hsgrowth_client, "_post", lambda p: _Resp(422, text="campo Y"))
    with pytest.raises(RuntimeError):
        hsgrowth_client.enviar_card_sync({"source": "gestorhs.os", "external_id": "10853"})
