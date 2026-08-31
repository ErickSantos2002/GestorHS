"""SSO Microsoft (Entra ID).

O backend/.env local esta preenchido com as credenciais reais e o `settings`
le esse arquivo no import — entao todo teste que depende do estado do SSO
forca os valores por monkeypatch, nunca confia no default.
"""
import pytest

from app.core.config import settings
from app.core import sso_tickets
from app.integrations import microsoft_client


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


def test_resgatar_remove_o_ticket_mesmo_vencido(monkeypatch):
    """Fixa a ordem pop-antes-da-checagem: uma implementacao que checasse a
    validade antes de dar pop deixaria o ticket vencido no dict, e duas
    chamadas concorrentes poderiam ler o mesmo par."""
    relogio = {"agora": 1000.0}
    monkeypatch.setattr(sso_tickets.time, "monotonic", lambda: relogio["agora"])
    ticket = sso_tickets.emitir("acc", "ref")
    relogio["agora"] += sso_tickets.TTL_SEGUNDOS + 1

    assert sso_tickets.resgatar(ticket) is None
    assert ticket not in sso_tickets._tickets


def test_resgatar_remove_o_ticket_no_caso_feliz():
    ticket = sso_tickets.emitir("acc", "ref")
    assert sso_tickets.resgatar(ticket) == ("acc", "ref")
    assert ticket not in sso_tickets._tickets


class _RespostaFake:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class _ClientFake:
    """Substitui httpx.Client no modulo. Guarda o que recebeu para inspecao."""

    def __init__(self, resposta: _RespostaFake):
        self._resposta = resposta
        self.url = None
        self.headers = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def get(self, url, headers=None):
        self.url = url
        self.headers = headers
        return self._resposta


def _fingir_graph(monkeypatch, resposta: _RespostaFake) -> _ClientFake:
    fake = _ClientFake(resposta)
    monkeypatch.setattr(microsoft_client.httpx, "Client", lambda **_: fake)
    return fake


def test_email_do_usuario_le_o_campo_mail(monkeypatch):
    fake = _fingir_graph(monkeypatch, _RespostaFake(200, {"mail": "Fulano@HealthSafetyTech.com"}))
    assert microsoft_client.email_do_usuario("tok") == "Fulano@HealthSafetyTech.com"
    assert fake.headers == {"Authorization": "Bearer tok"}


def test_email_do_usuario_cai_para_upn_quando_mail_e_nulo(monkeypatch):
    """Conta sem caixa postal vem com mail=null; o UPN e' o que sobra."""
    _fingir_graph(monkeypatch, _RespostaFake(200, {"mail": None, "userPrincipalName": "f@healthsafetytech.com"}))
    assert microsoft_client.email_do_usuario("tok") == "f@healthsafetytech.com"


def test_email_do_usuario_devolve_none_se_o_graph_recusa(monkeypatch):
    _fingir_graph(monkeypatch, _RespostaFake(401, {}))
    assert microsoft_client.email_do_usuario("tok-ruim") is None


def test_escopo_e_so_user_read():
    """Ler o e-mail e' tudo o que o login precisa. Escopo a mais e' permissao
    concedida que ninguem usa."""
    assert microsoft_client.SCOPES == ["User.Read"]
