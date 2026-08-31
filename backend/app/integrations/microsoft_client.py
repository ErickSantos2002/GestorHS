"""Login com Microsoft (Entra ID): so o suficiente para saber quem entrou.

Sincrono e com erro que sobe, como o enderecos_client — o usuario esta parado
num redirect esperando a resposta (o taskhs_client e' best-effort e engole
tudo; nao e' o caso aqui). Nada da Microsoft e' guardado: o access_token do
Graph vive dentro do callback e morre no fim dele.
"""
import httpx
from msal import ConfidentialClientApplication

from app.core.config import settings

SCOPES = ["User.Read"]
_GRAPH_ME = "https://graph.microsoft.com/v1.0/me"
_TIMEOUT = 10.0


# Memoizado por chave nos valores das envs: instanciar o ConfidentialClientApplication
# faz descoberta OIDC da autoridade, então reinstanciar a cada chamada exercitava o
# caminho de falha duas vezes por login (uma em /auth/microsoft, outra no callback).
# A chave inclui as quatro envs (não só as usadas na instanciação) para o cache trocar
# de entrada sozinho quando um teste troca qualquer uma por monkeypatch.
_app_cache: dict[tuple[str, str, str, str], ConfidentialClientApplication] = {}


def _app() -> ConfidentialClientApplication:
    chave = (settings.MS_CLIENT_ID, settings.MS_TENANT_ID, settings.MS_CLIENT_SECRET, settings.MS_REDIRECT_URI)
    app = _app_cache.get(chave)
    if app is None:
        app = ConfidentialClientApplication(
            client_id=settings.MS_CLIENT_ID,
            client_credential=settings.MS_CLIENT_SECRET,
            authority=f"https://login.microsoftonline.com/{settings.MS_TENANT_ID}",
        )
        _app_cache[chave] = app
    return app


def url_de_autorizacao(state: str) -> str:
    """Para onde mandar o navegador. O `state` volta intacto no callback e e'
    conferido contra o cookie — sem ele, um atacante pode fazer o navegador da
    vitima consumir um `code` alheio (login CSRF)."""
    return _app().get_authorization_request_url(
        SCOPES, redirect_uri=settings.MS_REDIRECT_URI, state=state
    )


def trocar_code_por_token(code: str) -> str | None:
    """access_token do Graph, ou None se a Microsoft recusou o code."""
    resultado = _app().acquire_token_by_authorization_code(
        code, scopes=SCOPES, redirect_uri=settings.MS_REDIRECT_URI
    )
    return resultado.get("access_token")


def email_do_usuario(access_token: str) -> str | None:
    """E-mail da conta que autenticou. `mail` e' nulo em conta sem caixa
    postal, e ai o userPrincipalName e' o identificador."""
    with httpx.Client(timeout=_TIMEOUT) as c:
        resposta = c.get(_GRAPH_ME, headers={"Authorization": f"Bearer {access_token}"})
    if resposta.status_code != 200:
        return None
    dados = resposta.json()
    return dados.get("mail") or dados.get("userPrincipalName")
