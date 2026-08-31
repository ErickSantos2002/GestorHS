"""SSO Microsoft (Entra ID).

O backend/.env local esta preenchido com as credenciais reais e o `settings`
le esse arquivo no import — entao todo teste que depende do estado do SSO
forca os valores por monkeypatch, nunca confia no default.
"""
import pytest

from app.core.config import settings
from app.core import sso_tickets


@pytest.fixture()
def sso_desligado(monkeypatch):
    monkeypatch.setattr(settings, "MS_CLIENT_ID", "")
    monkeypatch.setattr(settings, "MS_TENANT_ID", "")
    monkeypatch.setattr(settings, "MS_CLIENT_SECRET", "")
    monkeypatch.setattr(settings, "MS_REDIRECT_URI", "")
    monkeypatch.setattr(settings, "FRONTEND_URL", "")


@pytest.fixture()
def sso_ligado(monkeypatch):
    monkeypatch.setattr(settings, "MS_CLIENT_ID", "client-de-teste")
    monkeypatch.setattr(settings, "MS_TENANT_ID", "tenant-de-teste")
    monkeypatch.setattr(settings, "MS_CLIENT_SECRET", "segredo-de-teste")
    monkeypatch.setattr(settings, "MS_REDIRECT_URI", "http://localhost:8000/auth/microsoft/callback")
    monkeypatch.setattr(settings, "FRONTEND_URL", "http://localhost:5173")


def test_sso_ativo_false_com_envs_vazias(sso_desligado):
    assert settings.sso_ativo is False


def test_sso_ativo_true_com_as_cinco_preenchidas(sso_ligado):
    assert settings.sso_ativo is True


def test_sso_ativo_false_se_faltar_uma(sso_ligado, monkeypatch):
    monkeypatch.setattr(settings, "FRONTEND_URL", "")
    assert settings.sso_ativo is False


def test_status_reporta_desligado(client, sso_desligado):
    r = client.get("/auth/sso/status")
    assert r.status_code == 200
    assert r.json() == {"ativo": False}


def test_status_reporta_ligado(client, sso_ligado):
    r = client.get("/auth/sso/status")
    assert r.status_code == 200
    assert r.json() == {"ativo": True}


def test_status_e_publico(client, sso_ligado):
    """Sem Authorization header: o front consulta antes de existir sessao."""
    assert client.get("/auth/sso/status").status_code == 200


@pytest.fixture(autouse=True)
def _limpa_tickets():
    sso_tickets._tickets.clear()
    yield
    sso_tickets._tickets.clear()


def test_ticket_devolve_o_par_uma_vez_so():
    ticket = sso_tickets.emitir("acc-123", "ref-456")
    assert sso_tickets.resgatar(ticket) == ("acc-123", "ref-456")
    assert sso_tickets.resgatar(ticket) is None


def test_ticket_inexistente_devolve_none():
    assert sso_tickets.resgatar("nunca-existiu") is None


def test_ticket_expira_depois_do_ttl(monkeypatch):
    relogio = {"agora": 1000.0}
    monkeypatch.setattr(sso_tickets.time, "monotonic", lambda: relogio["agora"])
    ticket = sso_tickets.emitir("acc", "ref")
    relogio["agora"] += sso_tickets.TTL_SEGUNDOS + 1
    assert sso_tickets.resgatar(ticket) is None


def test_ticket_vale_dentro_do_ttl(monkeypatch):
    relogio = {"agora": 1000.0}
    monkeypatch.setattr(sso_tickets.time, "monotonic", lambda: relogio["agora"])
    ticket = sso_tickets.emitir("acc", "ref")
    relogio["agora"] += sso_tickets.TTL_SEGUNDOS - 1
    assert sso_tickets.resgatar(ticket) == ("acc", "ref")


def test_emitir_limpa_vencidos(monkeypatch):
    """Sem varredura, um redirect abandonado ficaria na memoria para sempre."""
    relogio = {"agora": 1000.0}
    monkeypatch.setattr(sso_tickets.time, "monotonic", lambda: relogio["agora"])
    sso_tickets.emitir("acc-velho", "ref-velho")
    relogio["agora"] += sso_tickets.TTL_SEGUNDOS + 1
    sso_tickets.emitir("acc-novo", "ref-novo")
    assert len(sso_tickets._tickets) == 1


def test_tickets_sao_diferentes_a_cada_emissao():
    assert sso_tickets.emitir("a", "b") != sso_tickets.emitir("a", "b")
