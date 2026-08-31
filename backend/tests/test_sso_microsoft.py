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


from app.core.security import criar_refresh_token, decodificar_token
from app.models import Usuario


@pytest.fixture()
def graph_diz(monkeypatch):
    """Encurta o caminho todo da Microsoft: devolve o e-mail que voce pedir."""

    def _configurar(email: str | None, token: str | None = "tok-do-graph"):
        monkeypatch.setattr(microsoft_client, "trocar_code_por_token", lambda code: token)
        monkeypatch.setattr(microsoft_client, "email_do_usuario", lambda tok: email)

    return _configurar


def _iniciar_sso(client, monkeypatch) -> str:
    """Chama /auth/microsoft para o cookie de state ser gravado e devolve o state."""
    monkeypatch.setattr(
        microsoft_client, "url_de_autorizacao", lambda state: "https://login.microsoftonline.com/xyz"
    )
    client.get("/auth/microsoft", follow_redirects=False)
    return client.cookies["sso_state"]


def test_microsoft_redireciona_para_a_microsoft(client, sso_ligado, monkeypatch):
    monkeypatch.setattr(
        microsoft_client, "url_de_autorizacao", lambda state: "https://login.microsoftonline.com/xyz"
    )
    r = client.get("/auth/microsoft", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "https://login.microsoftonline.com/xyz"


def test_microsoft_grava_cookie_de_state(client, sso_ligado, monkeypatch):
    monkeypatch.setattr(
        microsoft_client, "url_de_autorizacao", lambda state: "https://login.microsoftonline.com/xyz"
    )
    r = client.get("/auth/microsoft", follow_redirects=False)
    assert "sso_state" in r.cookies
    assert len(r.cookies["sso_state"]) > 20


def test_microsoft_503_com_sso_desligado(client, sso_desligado):
    assert client.get("/auth/microsoft", follow_redirects=False).status_code == 503


def test_callback_feliz_redireciona_com_ticket(client, sso_ligado, usuario_admin, graph_diz, monkeypatch):
    state = _iniciar_sso(client, monkeypatch)
    graph_diz("admin@hs.com")
    r = client.get(f"/auth/microsoft/callback?code=abc&state={state}", follow_redirects=False)
    assert r.status_code == 302
    destino = r.headers["location"]
    assert destino.startswith("http://localhost:5173/auth/callback?ticket=")
    ticket = destino.split("ticket=")[1]
    par = sso_tickets.resgatar(ticket)
    assert par is not None
    access, _ = par
    payload = decodificar_token(access)
    assert payload["sub"] == str(usuario_admin.id)
    assert payload["tipo"] == "usuario"


def test_callback_normaliza_o_email(client, sso_ligado, usuario_admin, graph_diz, monkeypatch):
    """A Microsoft devolve com maiusculas; o usuario esta gravado minusculo."""
    state = _iniciar_sso(client, monkeypatch)
    graph_diz("  Admin@HS.com ")
    r = client.get(f"/auth/microsoft/callback?code=abc&state={state}", follow_redirects=False)
    assert "/auth/callback?ticket=" in r.headers["location"]


def test_callback_sem_usuario_volta_para_o_login(client, sso_ligado, usuario_admin, graph_diz, monkeypatch, db_session):
    """Sem provisionamento automatico: quem nao tem conta nao entra, e a base de
    usuarios nao muda."""
    state = _iniciar_sso(client, monkeypatch)
    graph_diz("estranho@healthsafetytech.com")
    antes = db_session.query(Usuario).count()
    r = client.get(f"/auth/microsoft/callback?code=abc&state={state}", follow_redirects=False)
    assert r.headers["location"] == "http://localhost:5173/login?erro=usuario_nao_encontrado"
    assert db_session.query(Usuario).count() == antes


def test_callback_usuario_inativo(client, sso_ligado, db_session, graph_diz, monkeypatch):
    from app.core.security import hash_senha

    db_session.add(Usuario(nome="Ex", email="ex@hs.com", senha=hash_senha("senha123"), ativo=False))
    db_session.commit()
    state = _iniciar_sso(client, monkeypatch)
    graph_diz("ex@hs.com")
    r = client.get(f"/auth/microsoft/callback?code=abc&state={state}", follow_redirects=False)
    assert r.headers["location"] == "http://localhost:5173/login?erro=usuario_inativo"


def test_callback_ignora_precisa_redefinir_senha(client, sso_ligado, db_session, graph_diz, monkeypatch):
    """A flag existe para forcar troca de senha propria; quem entra por SSO nao
    usou senha nenhuma. O /auth/login continua bloqueando — outro teste cobre."""
    from app.core.security import hash_senha

    db_session.add(
        Usuario(nome="Novo", email="novo@hs.com", senha=hash_senha("senha123"), precisa_redefinir_senha=True)
    )
    db_session.commit()
    state = _iniciar_sso(client, monkeypatch)
    graph_diz("novo@hs.com")
    r = client.get(f"/auth/microsoft/callback?code=abc&state={state}", follow_redirects=False)
    assert "/auth/callback?ticket=" in r.headers["location"]


def test_login_por_senha_ainda_bloqueia_precisa_redefinir(client, db_session):
    from app.core.security import hash_senha

    db_session.add(
        Usuario(nome="Novo", email="novo2@hs.com", senha=hash_senha("senha123"), precisa_redefinir_senha=True)
    )
    db_session.commit()
    r = client.post("/auth/login", json={"email": "novo2@hs.com", "senha": "senha123"})
    assert r.status_code == 200
    assert r.json()["precisa_redefinir"] is True
    assert r.json()["access_token"] is None


def test_callback_sem_code(client, sso_ligado, monkeypatch):
    state = _iniciar_sso(client, monkeypatch)
    r = client.get(f"/auth/microsoft/callback?state={state}", follow_redirects=False)
    assert r.headers["location"] == "http://localhost:5173/login?erro=falha_microsoft"


def test_callback_code_recusado_pela_microsoft(client, sso_ligado, graph_diz, monkeypatch):
    state = _iniciar_sso(client, monkeypatch)
    graph_diz(None, token=None)
    r = client.get(f"/auth/microsoft/callback?code=ruim&state={state}", follow_redirects=False)
    assert r.headers["location"] == "http://localhost:5173/login?erro=falha_microsoft"


def test_callback_graph_fora_do_ar(client, sso_ligado, monkeypatch):
    """Timeout da Microsoft nao pode virar 500 na cara do usuario."""
    import httpx

    state = _iniciar_sso(client, monkeypatch)
    monkeypatch.setattr(microsoft_client, "trocar_code_por_token", lambda code: "tok")

    def _explode(_):
        raise httpx.ConnectTimeout("sem rede")

    monkeypatch.setattr(microsoft_client, "email_do_usuario", _explode)
    r = client.get(f"/auth/microsoft/callback?code=abc&state={state}", follow_redirects=False)
    assert r.headers["location"] == "http://localhost:5173/login?erro=falha_microsoft"


def test_callback_503_com_sso_desligado(client, sso_desligado):
    assert client.get("/auth/microsoft/callback?code=abc", follow_redirects=False).status_code == 503


def test_callback_state_nao_bate_com_cookie(client, sso_ligado, monkeypatch):
    """Login CSRF: um state que nao confere com o cookie nao pode ser aceito,
    mesmo com code presente — senao um atacante usa o proprio code dele para
    logar a vitima na conta errada."""
    _iniciar_sso(client, monkeypatch)
    r = client.get("/auth/microsoft/callback?code=abc&state=outro-valor-qualquer", follow_redirects=False)
    assert r.headers["location"] == "http://localhost:5173/login?erro=falha_microsoft"


def test_callback_sem_cookie_de_state(client, sso_ligado):
    """Sem ter passado por /auth/microsoft, nao ha cookie — o callback nao
    pode confiar em nenhum state que venha na URL."""
    r = client.get("/auth/microsoft/callback?code=abc&state=qualquer", follow_redirects=False)
    assert r.headers["location"] == "http://localhost:5173/login?erro=falha_microsoft"


def test_callback_sem_parametro_state(client, sso_ligado, monkeypatch):
    """Cookie valido, mas a Microsoft (ou um atacante) nao devolveu ?state=."""
    _iniciar_sso(client, monkeypatch)
    r = client.get("/auth/microsoft/callback?code=abc", follow_redirects=False)
    assert r.headers["location"] == "http://localhost:5173/login?erro=falha_microsoft"


def test_refresh_com_via_sso_ignora_precisa_redefinir(client, db_session):
    """Quem entrou por SSO nao usou senha nenhuma; a flag nao pode expulsa-lo
    no primeiro refresh."""
    from app.core.security import hash_senha

    usuario = Usuario(nome="Novo", email="novo3@hs.com", senha=hash_senha("senha123"), precisa_redefinir_senha=True)
    db_session.add(usuario)
    db_session.commit()
    refresh_token = criar_refresh_token(sub=str(usuario.id), tipo="usuario", via="sso")
    r = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert r.status_code == 200
    assert r.json()["access_token"] is not None


def test_refresh_preserva_via_sso_no_token_novo(client, db_session):
    """Sem preservar o `via`, o problema voltaria no segundo refresh."""
    from app.core.security import hash_senha

    usuario = Usuario(nome="Novo", email="novo4@hs.com", senha=hash_senha("senha123"), precisa_redefinir_senha=True)
    db_session.add(usuario)
    db_session.commit()
    refresh_token = criar_refresh_token(sub=str(usuario.id), tipo="usuario", via="sso")
    r = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert r.status_code == 200
    novo_refresh = r.json()["refresh_token"]
    assert decodificar_token(novo_refresh)["via"] == "sso"


def test_refresh_sem_via_sso_ainda_bloqueia_precisa_redefinir(client, db_session):
    """O caminho de senha continua barrado no refresh — a flag so e' ignorada
    para quem entrou por SSO."""
    from app.core.security import hash_senha

    usuario = Usuario(nome="Novo", email="novo5@hs.com", senha=hash_senha("senha123"), precisa_redefinir_senha=True)
    db_session.add(usuario)
    db_session.commit()
    refresh_token = criar_refresh_token(sub=str(usuario.id), tipo="usuario")
    r = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert r.status_code == 401
