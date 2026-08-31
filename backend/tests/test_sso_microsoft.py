"""SSO Microsoft (Entra ID).

O backend/.env local está preenchido com as credenciais reais e o `settings`
lê esse arquivo no import — então todo teste que depende do estado do SSO
força os valores por monkeypatch, nunca confia no default.
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
    """Sem Authorization header: o front consulta antes de existir sessão."""
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
    """Conta sem caixa postal vem com mail=null; o UPN é o que sobra."""
    _fingir_graph(monkeypatch, _RespostaFake(200, {"mail": None, "userPrincipalName": "f@healthsafetytech.com"}))
    assert microsoft_client.email_do_usuario("tok") == "f@healthsafetytech.com"


def test_email_do_usuario_devolve_none_se_o_graph_recusa(monkeypatch):
    _fingir_graph(monkeypatch, _RespostaFake(401, {}))
    assert microsoft_client.email_do_usuario("tok-ruim") is None


def test_escopo_e_so_user_read():
    """Ler o e-mail é tudo o que o login precisa. Escopo a mais é permissão
    concedida que ninguém usa."""
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


def test_microsoft_falha_na_descoberta_nao_vira_500(client, sso_ligado, monkeypatch):
    """/auth/microsoft é navegação de página inteira: se a descoberta de
    autoridade do MSAL falhar (rede, Entra fora do ar), o usuário tem que ver
    a mensagem no /login, não o JSON de erro do FastAPI numa aba em branco."""

    def _explode(state):
        raise RuntimeError("descoberta OIDC fora do ar")

    monkeypatch.setattr(microsoft_client, "url_de_autorizacao", _explode)
    r = client.get("/auth/microsoft", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "http://localhost:5173/login?erro=falha_microsoft"


def test_app_e_memoizado_por_chave_de_envs(sso_ligado, monkeypatch):
    """Reinstanciar o ConfidentialClientApplication a cada chamada refaria a
    descoberta OIDC duas vezes por login. Mesma chave de envs -> mesma
    instância — sem bater na rede de verdade, o construtor fica fingido."""
    chamadas = []

    class _AppFake:
        def __init__(self, **kwargs):
            chamadas.append(kwargs)

    monkeypatch.setattr(microsoft_client, "ConfidentialClientApplication", _AppFake)
    microsoft_client._app_cache.clear()
    a1 = microsoft_client._app()
    a2 = microsoft_client._app()
    assert a1 is a2
    assert len(chamadas) == 1


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
    # cookie de state é de uso único: some também no caminho feliz.
    cookies_saida = r.headers.get_list("set-cookie")
    assert any("sso_state=" in c and ("Max-Age=0" in c or 'sso_state=""' in c) for c in cookies_saida)


def test_callback_normaliza_o_email(client, sso_ligado, usuario_admin, graph_diz, monkeypatch):
    """A Microsoft devolve com maiúsculas; o usuário está gravado minúsculo."""
    state = _iniciar_sso(client, monkeypatch)
    graph_diz("  Admin@HS.com ")
    r = client.get(f"/auth/microsoft/callback?code=abc&state={state}", follow_redirects=False)
    assert "/auth/callback?ticket=" in r.headers["location"]


def test_callback_sem_usuario_volta_para_o_login(client, sso_ligado, usuario_admin, graph_diz, monkeypatch, db_session):
    """Sem provisionamento automático: quem não tem conta não entra, e a base de
    usuários não muda."""
    state = _iniciar_sso(client, monkeypatch)
    graph_diz("estranho@healthsafetytech.com")
    antes = db_session.query(Usuario).count()
    r = client.get(f"/auth/microsoft/callback?code=abc&state={state}", follow_redirects=False)
    assert r.headers["location"] == "http://localhost:5173/login?erro=usuario_nao_encontrado"
    assert db_session.query(Usuario).count() == antes
    # cookie de state é de uso único: some também nos caminhos de erro.
    cookies_saida = r.headers.get_list("set-cookie")
    assert any("sso_state=" in c and ("Max-Age=0" in c or 'sso_state=""' in c) for c in cookies_saida)


def test_callback_usuario_inativo(client, sso_ligado, db_session, graph_diz, monkeypatch):
    from app.core.security import hash_senha

    db_session.add(Usuario(nome="Ex", email="ex@hs.com", senha=hash_senha("senha123"), ativo=False))
    db_session.commit()
    state = _iniciar_sso(client, monkeypatch)
    graph_diz("ex@hs.com")
    r = client.get(f"/auth/microsoft/callback?code=abc&state={state}", follow_redirects=False)
    assert r.headers["location"] == "http://localhost:5173/login?erro=usuario_inativo"


def test_callback_ignora_precisa_redefinir_senha(client, sso_ligado, db_session, graph_diz, monkeypatch):
    """A flag existe para forçar troca de senha própria; quem entra por SSO não
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
    """Timeout da Microsoft não pode virar 500 na cara do usuário."""
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
    """Login CSRF: um state que não confere com o cookie não pode ser aceito,
    mesmo com code presente — senão um atacante usa o próprio code dele para
    logar a vítima na conta errada."""
    _iniciar_sso(client, monkeypatch)
    r = client.get("/auth/microsoft/callback?code=abc&state=outro-valor-qualquer", follow_redirects=False)
    assert r.headers["location"] == "http://localhost:5173/login?erro=falha_microsoft"


def test_callback_sem_cookie_de_state(client, sso_ligado):
    """Sem ter passado por /auth/microsoft, não há cookie — o callback não
    pode confiar em nenhum state que venha na URL."""
    r = client.get("/auth/microsoft/callback?code=abc&state=qualquer", follow_redirects=False)
    assert r.headers["location"] == "http://localhost:5173/login?erro=falha_microsoft"


def test_callback_sem_parametro_state(client, sso_ligado, monkeypatch):
    """Cookie válido, mas a Microsoft (ou um atacante) não devolveu ?state=."""
    _iniciar_sso(client, monkeypatch)
    r = client.get("/auth/microsoft/callback?code=abc", follow_redirects=False)
    assert r.headers["location"] == "http://localhost:5173/login?erro=falha_microsoft"


def test_callback_access_denied_volta_sem_mensagem_de_erro(client, sso_ligado, monkeypatch):
    """Quando o próprio usuário cancela o consentimento na tela da Microsoft,
    ela devolve ?error=access_denied e sem ?code=. Isso não é uma falha do
    sistema — o retorno é silencioso, sem ?erro=."""
    state = _iniciar_sso(client, monkeypatch)
    r = client.get(f"/auth/microsoft/callback?error=access_denied&state={state}", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "http://localhost:5173/login"


def test_callback_outro_error_da_microsoft_ainda_cai_em_falha_microsoft(client, sso_ligado, monkeypatch):
    """Um `error` diferente de access_denied (ex.: consent_required,
    server_error) continua caindo na mensagem genérica de falha."""
    state = _iniciar_sso(client, monkeypatch)
    r = client.get(f"/auth/microsoft/callback?error=server_error&state={state}", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "http://localhost:5173/login?erro=falha_microsoft"


def test_callback_state_nao_ascii_nao_derruba_o_servidor(client, sso_ligado, monkeypatch):
    """secrets.compare_digest sobre str exige ASCII dos dois lados; um state
    fora do ASCII (ex.: enviado por um visitante qualquer, sem precisar do
    cookie certo) não pode virar 500 — o contrato do callback é terminar
    sempre em redirect."""
    _iniciar_sso(client, monkeypatch)
    r = client.get("/auth/microsoft/callback?code=abc&state=%C3%A7", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "http://localhost:5173/login?erro=falha_microsoft"


def test_refresh_com_via_sso_ignora_precisa_redefinir(client, db_session):
    """Quem entrou por SSO não usou senha nenhuma; a flag não pode expulsá-lo
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
    """O caminho de senha continua barrado no refresh — a flag só é ignorada
    para quem entrou por SSO."""
    from app.core.security import hash_senha

    usuario = Usuario(nome="Novo", email="novo5@hs.com", senha=hash_senha("senha123"), precisa_redefinir_senha=True)
    db_session.add(usuario)
    db_session.commit()
    refresh_token = criar_refresh_token(sub=str(usuario.id), tipo="usuario")
    r = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert r.status_code == 401


def test_exchange_devolve_os_tokens(client, sso_ligado, usuario_admin, graph_diz, monkeypatch):
    state = _iniciar_sso(client, monkeypatch)
    graph_diz("admin@hs.com")
    destino = client.get(f"/auth/microsoft/callback?code=abc&state={state}", follow_redirects=False).headers["location"]
    ticket = destino.split("ticket=")[1]

    r = client.post("/auth/sso/exchange", json={"ticket": ticket})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["token_type"] == "bearer"
    assert corpo["access_token"] and corpo["refresh_token"]


def test_tokens_do_sso_valem_no_me(client, sso_ligado, usuario_admin, graph_diz, monkeypatch):
    """A sessão nasce diferente mas é indistinguível da do login por senha."""
    state = _iniciar_sso(client, monkeypatch)
    graph_diz("admin@hs.com")
    destino = client.get(f"/auth/microsoft/callback?code=abc&state={state}", follow_redirects=False).headers["location"]
    tokens = client.post("/auth/sso/exchange", json={"ticket": destino.split("ticket=")[1]}).json()

    r = client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert r.status_code == 200 and r.json()["email"] == "admin@hs.com"

    r = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200 and r.json()["access_token"]


def test_exchange_do_mesmo_ticket_duas_vezes_da_400(client, sso_ligado, usuario_admin, graph_diz, monkeypatch):
    state = _iniciar_sso(client, monkeypatch)
    graph_diz("admin@hs.com")
    destino = client.get(f"/auth/microsoft/callback?code=abc&state={state}", follow_redirects=False).headers["location"]
    ticket = destino.split("ticket=")[1]
    assert client.post("/auth/sso/exchange", json={"ticket": ticket}).status_code == 200
    assert client.post("/auth/sso/exchange", json={"ticket": ticket}).status_code == 400


def test_exchange_ticket_invalido_e_400_e_nao_401(client, sso_ligado):
    """401 faria o api.ts limpar o storage e sair da página antes de mostrar a
    mensagem; com 400 o AuthCallbackPage consegue explicar o que houve."""
    r = client.post("/auth/sso/exchange", json={"ticket": "nao-existe"})
    assert r.status_code == 400
    assert r.json()["detail"]


def test_exchange_e_publico(client, sso_ligado):
    assert client.post("/auth/sso/exchange", json={"ticket": "x"}).status_code == 400
