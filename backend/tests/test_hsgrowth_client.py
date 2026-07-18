import pytest


def _ligar(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "HSGROWTH_BASE_URL", "https://growth.test")
    monkeypatch.setattr(settings, "HSGROWTH_API_KEY", "chave-123")


def test_desligada_sem_env(monkeypatch):
    from app.core.config import settings
    from app.integrations import hsgrowth_client as cli
    monkeypatch.setattr(settings, "HSGROWTH_BASE_URL", "")
    monkeypatch.setattr(settings, "HSGROWTH_API_KEY", "")
    assert cli.integracao_ativa() is False

    chamou = []
    monkeypatch.setattr(cli, "_post", lambda p: chamou.append(p))
    cli.enviar_card({"external_id": "1"})
    assert chamou == []          # nem tentou


def test_ligada_com_as_duas_envs(monkeypatch):
    from app.integrations import hsgrowth_client as cli
    _ligar(monkeypatch)
    assert cli.integracao_ativa() is True


def test_enviar_card_nunca_propaga(monkeypatch):
    """Best-effort: falha de rede nao pode derrubar o fluxo chamador."""
    from app.integrations import hsgrowth_client as cli
    _ligar(monkeypatch)

    def explode(_):
        raise RuntimeError("rede caiu")
    monkeypatch.setattr(cli, "_post", explode)
    cli.enviar_card({"external_id": "1"})      # nao levanta


def test_enviar_card_sync_propaga(monkeypatch):
    """A variante do script quer saber da falha para relatar."""
    from app.integrations import hsgrowth_client as cli
    _ligar(monkeypatch)

    def explode(_):
        raise RuntimeError("rede caiu")
    monkeypatch.setattr(cli, "_post", explode)
    with pytest.raises(RuntimeError):
        cli.enviar_card_sync({"external_id": "1"})


def test_url_e_header(monkeypatch):
    """Monta {base}/api/v1/integration/service-cards e manda X-API-Key."""
    from app.integrations import hsgrowth_client as cli
    _ligar(monkeypatch)
    capturado = {}

    class RespFake:
        status_code = 201
        def raise_for_status(self): pass
        def json(self): return {"id": 9, "created": True}

    def post_fake(url, json=None, headers=None, timeout=None):
        capturado.update(url=url, json=json, headers=headers)
        return RespFake()
    monkeypatch.setattr(cli.httpx, "post", post_fake)

    r = cli.enviar_card_sync({"external_id": "1"})
    assert capturado["url"] == "https://growth.test/api/v1/integration/service-cards"
    assert capturado["headers"]["X-API-Key"] == "chave-123"
    assert r["created"] is True
