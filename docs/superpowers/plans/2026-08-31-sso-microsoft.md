# SSO Microsoft (Entra ID) — plano de implementação

> **Para executores agênticos:** SUB-SKILL OBRIGATÓRIA: use
> `superpowers:subagent-driven-development` (recomendado) ou
> `superpowers:executing-plans` para executar este plano tarefa a tarefa.
> Os passos usam checkbox (`- [ ]`) para acompanhamento.

**Goal:** Adicionar "Entrar com Microsoft" ao login interno do GestorHS (`/login` → `/app`), reusando os mesmos tokens do login por senha.

**Architecture:** O backend ganha quatro endpoints públicos em `/auth`. O callback do Entra ID troca o `code` por um token do Graph, lê só o e-mail, acha o `Usuario` por e-mail e guarda o par access+refresh sob um **ticket opaco de uso único (60 s, em memória)**; o front troca esse ticket por um `POST` e persiste a sessão como sempre. Nenhum token da Microsoft é guardado, ninguém é provisionado automaticamente e o login por senha continua intacto.

**Tech Stack:** FastAPI (endpoints síncronos), `msal` (ConfidentialClientApplication), `httpx` (Graph), SQLAlchemy 2, pytest; React 19 + TS + Vite + Tailwind v4, react-router-dom, vitest + testing-library.

**Spec:** [`docs/superpowers/specs/2026-08-31-sso-microsoft-design.md`](../specs/2026-08-31-sso-microsoft-design.md)

## Global Constraints

- **Idioma:** o domínio é PT-BR. Nomes de funções, variáveis, rotas e mensagens em português, como o resto do repo.
- **Sem `/api` no caminho.** O router é `APIRouter(prefix="/auth")` e o `main.py` não monta prefixo. A redirect URI é `https://gestorhsapi.healthsafetytech.com/auth/microsoft/callback` — copiar do TaskHS, que tem `/api`, é o erro mais fácil de cometer.
- **Endpoints síncronos (`def`, não `async def`).** Todo o `app/api/auth.py` é síncrono e o FastAPI já roda isso no threadpool. Nada de `asyncio.to_thread`.
- **Escopo do Graph:** `["User.Read"]`, e só. Nenhum token da Microsoft persistido em lugar nenhum.
- **`requirements.txt` não usa pins.** Adicionar `msal` sem versão, como as outras 15 linhas. (A spec diz "pinado"; o repo não pina nada — a consistência com o arquivo vence.)
- **Os quatro endpoints novos são públicos.** Nenhum deles pode depender de `get_current_usuario`.
- **`precisa_redefinir_senha` NÃO bloqueia o SSO.** Decisão registrada na spec. O `/auth/login` continua bloqueando.
- **Erro de ticket é 400, nunca 401.** O `api.ts` trata 401 como sessão expirada (tenta refresh, limpa o storage, chama `onUnauthorized`) e a página de callback nunca mostraria a mensagem.
- **⚠️ Gotcha dos testes:** o `backend/.env` **já está preenchido** com as credenciais reais, e `settings` lê o `.env` no import. Então `settings.sso_ativo` é `True` durante os testes locais. Todo teste que depende do estado do SSO tem que forçar o valor por `monkeypatch` — nunca assuma o default.
- **Segredo:** `MS_CLIENT_SECRET` vive só no `backend/.env` (gitignorado) e no Easypanel. Nunca em arquivo versionado, nunca em log, nunca numa mensagem de commit.

---

### Task 1: Configuração e endpoint de status

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/api/auth.py`
- Test: `backend/tests/test_sso_microsoft.py` (criar)

**Interfaces:**
- Consumes: nada (primeira tarefa).
- Produces: `settings.MS_CLIENT_ID`, `settings.MS_TENANT_ID`, `settings.MS_CLIENT_SECRET`, `settings.MS_REDIRECT_URI`, `settings.FRONTEND_URL` (todas `str`, default `""`); `settings.sso_ativo -> bool`; `GET /auth/sso/status` → `{"ativo": bool}`.

- [ ] **Step 1: Escrever os testes que falham**

Criar `backend/tests/test_sso_microsoft.py`:

```python
"""SSO Microsoft (Entra ID).

O backend/.env local esta preenchido com as credenciais reais e o `settings`
le esse arquivo no import — entao todo teste que depende do estado do SSO
forca os valores por monkeypatch, nunca confia no default.
"""
import pytest

from app.core.config import settings


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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_sso_microsoft.py -v`
Expected: FAIL — `AttributeError` em `settings.sso_ativo` e 404 em `/auth/sso/status`.

- [ ] **Step 3: Adicionar as envs e a property no `config.py`**

Em `backend/app/core/config.py`, dentro de `class Settings`, logo depois do bloco `GROWTHHS_INBOUND_API_KEY`:

```python
    # SSO Microsoft (Entra ID). Vazio = desligado (mesmo gating por env do
    # TaskHS/GrowthHS): o botao some da tela de login e GET /auth/microsoft
    # responde 503. App Registration proprio do GestorHS, single tenant.
    MS_CLIENT_ID: str = ""
    MS_TENANT_ID: str = ""
    MS_CLIENT_SECRET: str = ""
    MS_REDIRECT_URI: str = ""
    # Base do front para onde o callback redireciona. Sem barra final.
    FRONTEND_URL: str = ""
```

E, depois do último campo da classe (antes de `class Config`):

```python
    @property
    def sso_ativo(self) -> bool:
        """As cinco preenchidas. FRONTEND_URL entra porque sem ela o callback
        nao tem para onde redirecionar — SSO 'meio configurado' seria pior que
        desligado."""
        return all(
            [
                self.MS_CLIENT_ID,
                self.MS_TENANT_ID,
                self.MS_CLIENT_SECRET,
                self.MS_REDIRECT_URI,
                self.FRONTEND_URL,
            ]
        )
```

- [ ] **Step 4: Adicionar o endpoint de status**

Em `backend/app/api/auth.py`, acrescentar o import (junto dos outros `from app.core...`):

```python
from app.core.config import settings
```

E no fim do arquivo:

```python
@router.get("/sso/status")
def sso_status():
    """Publico: o front pergunta antes de haver sessao, para decidir se mostra
    o botao 'Entrar com Microsoft'. Uma env so, em um lugar so — um
    VITE_SSO_ATIVO no build duplicaria a configuracao em duas pontas que podem
    discordar."""
    return {"ativo": settings.sso_ativo}
```

- [ ] **Step 5: Rodar e ver passar**

Run: `pytest tests/test_sso_microsoft.py -v`
Expected: PASS (6 testes).

- [ ] **Step 6: Rodar a suíte inteira**

Run: `pytest -q`
Expected: PASS — nenhuma regressão.

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/config.py backend/app/api/auth.py backend/tests/test_sso_microsoft.py backend/.env.example
git commit -m "feat(auth): envs do SSO Microsoft e GET /auth/sso/status"
```

(O `.env.example` já foi preenchido antes do plano; entra neste commit.)

---

### Task 2: Store de tickets opacos

**Files:**
- Create: `backend/app/core/sso_tickets.py`
- Test: `backend/tests/test_sso_microsoft.py` (acrescentar)

**Interfaces:**
- Consumes: nada.
- Produces: `sso_tickets.emitir(access_token: str, refresh_token: str) -> str`; `sso_tickets.resgatar(ticket: str) -> tuple[str, str] | None`; `sso_tickets.TTL_SEGUNDOS: int`.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar em `backend/tests/test_sso_microsoft.py` (e o import no topo: `from app.core import sso_tickets`):

```python
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_sso_microsoft.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.sso_tickets'`.

- [ ] **Step 3: Escrever o módulo**

Criar `backend/app/core/sso_tickets.py`:

```python
"""Tickets opacos de uso unico para o retorno do SSO Microsoft.

O callback nao pode devolver os tokens na URL: query string entra no historico
do navegador, no Referer da proxima requisicao e em qualquer log de proxy no
caminho — e o que vazaria aqui e' um refresh token de 7 dias. Entao o callback
guarda o par aqui e manda so o ticket, que o front troca num POST.

ASSUME PROCESSO UNICO. O estado e' um dict em memoria: com mais de um worker o
exchange cai num processo que nao emitiu o ticket e o login falha de forma
intermitente. Se o deploy ganhar --workers > 1, a correcao e' estado
compartilhado (Redis ou tabela com TTL). Reiniciar o backend descarta tickets
pendentes — quem estava no meio do redirect clica de novo.
"""
import secrets
import time

TTL_SEGUNDOS = 60

# ticket -> (access_token, refresh_token, expira_em)
_tickets: dict[str, tuple[str, str, float]] = {}


def _limpar_vencidos(agora: float) -> None:
    for chave in [k for k, (_, _, expira) in _tickets.items() if expira <= agora]:
        _tickets.pop(chave, None)


def emitir(access_token: str, refresh_token: str) -> str:
    """Guarda o par e devolve o ticket que vai na URL de retorno."""
    agora = time.monotonic()
    _limpar_vencidos(agora)
    ticket = secrets.token_urlsafe(32)
    _tickets[ticket] = (access_token, refresh_token, agora + TTL_SEGUNDOS)
    return ticket


def resgatar(ticket: str) -> tuple[str, str] | None:
    """Uso unico: o pop acontece antes da checagem de validade, entao um ticket
    vencido tambem sai do dict ao ser tentado."""
    registro = _tickets.pop(ticket, None)
    if registro is None:
        return None
    access_token, refresh_token, expira_em = registro
    if expira_em <= time.monotonic():
        return None
    return access_token, refresh_token
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_sso_microsoft.py -v`
Expected: PASS (12 testes no arquivo).

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/sso_tickets.py backend/tests/test_sso_microsoft.py
git commit -m "feat(auth): store de tickets opacos de uso unico para o SSO"
```

---

### Task 3: Cliente da Microsoft

**Files:**
- Create: `backend/app/integrations/microsoft_client.py`
- Modify: `backend/requirements.txt`
- Test: `backend/tests/test_sso_microsoft.py` (acrescentar)

**Interfaces:**
- Consumes: `settings.MS_CLIENT_ID`, `MS_TENANT_ID`, `MS_CLIENT_SECRET`, `MS_REDIRECT_URI` (Task 1).
- Produces: `microsoft_client.url_de_autorizacao() -> str`; `microsoft_client.trocar_code_por_token(code: str) -> str | None`; `microsoft_client.email_do_usuario(access_token: str) -> str | None`; `microsoft_client.SCOPES: list[str]`.

- [ ] **Step 1: Instalar a dependência**

```bash
cd backend && source .venv/bin/activate && pip install msal
```

E acrescentar `msal` ao fim de `backend/requirements.txt`, sem versão (o arquivo não pina nada).

- [ ] **Step 2: Escrever os testes que falham**

Acrescentar em `backend/tests/test_sso_microsoft.py` (import no topo: `from app.integrations import microsoft_client`):

```python
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
```

> Nota: `url_de_autorizacao` e `trocar_code_por_token` **não** são testadas
> aqui. Instanciar `ConfidentialClientApplication` dispara descoberta de
> metadados na rede, e teste que depende de rede não vale o preço. As duas são
> exercitadas na Task 4, com o módulo inteiro monkeypatchado no nível do
> endpoint.

- [ ] **Step 3: Rodar e ver falhar**

Run: `pytest tests/test_sso_microsoft.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.integrations.microsoft_client'`.

- [ ] **Step 4: Escrever o cliente**

Criar `backend/app/integrations/microsoft_client.py`:

```python
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


def _app() -> ConfidentialClientApplication:
    return ConfidentialClientApplication(
        client_id=settings.MS_CLIENT_ID,
        client_credential=settings.MS_CLIENT_SECRET,
        authority=f"https://login.microsoftonline.com/{settings.MS_TENANT_ID}",
    )


def url_de_autorizacao() -> str:
    """Para onde mandar o navegador do usuario."""
    return _app().get_authorization_request_url(SCOPES, redirect_uri=settings.MS_REDIRECT_URI)


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
```

- [ ] **Step 5: Rodar e ver passar**

Run: `pytest tests/test_sso_microsoft.py -v`
Expected: PASS (17 testes).

- [ ] **Step 6: Commit**

```bash
git add backend/app/integrations/microsoft_client.py backend/requirements.txt backend/tests/test_sso_microsoft.py
git commit -m "feat(auth): cliente do Entra ID (autorizacao, code->token, e-mail no Graph)"
```

---

### Task 4: Endpoints de autorização e callback

**Files:**
- Modify: `backend/app/api/auth.py`
- Test: `backend/tests/test_sso_microsoft.py` (acrescentar)

**Interfaces:**
- Consumes: `settings.sso_ativo`, `settings.FRONTEND_URL` (Task 1); `sso_tickets.emitir` (Task 2); `microsoft_client.url_de_autorizacao`, `trocar_code_por_token`, `email_do_usuario` (Task 3); `criar_access_token`, `criar_refresh_token` e `emails.normalizar`, já importados no arquivo.
- Produces: `GET /auth/microsoft` (302 ou 503); `GET /auth/microsoft/callback?code=…` (302 sempre, para `/auth/callback?ticket=…` ou `/login?erro=…`).

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar em `backend/tests/test_sso_microsoft.py`:

```python
from app.models import Usuario


@pytest.fixture()
def graph_diz(monkeypatch):
    """Encurta o caminho todo da Microsoft: devolve o e-mail que voce pedir."""

    def _configurar(email: str | None, token: str | None = "tok-do-graph"):
        monkeypatch.setattr(microsoft_client, "trocar_code_por_token", lambda code: token)
        monkeypatch.setattr(microsoft_client, "email_do_usuario", lambda tok: email)

    return _configurar


def test_microsoft_redireciona_para_a_microsoft(client, sso_ligado, monkeypatch):
    monkeypatch.setattr(microsoft_client, "url_de_autorizacao", lambda: "https://login.microsoftonline.com/xyz")
    r = client.get("/auth/microsoft", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "https://login.microsoftonline.com/xyz"


def test_microsoft_503_com_sso_desligado(client, sso_desligado):
    assert client.get("/auth/microsoft", follow_redirects=False).status_code == 503


def test_callback_feliz_redireciona_com_ticket(client, sso_ligado, usuario_admin, graph_diz):
    graph_diz("admin@hs.com")
    r = client.get("/auth/microsoft/callback?code=abc", follow_redirects=False)
    assert r.status_code == 302
    destino = r.headers["location"]
    assert destino.startswith("http://localhost:5173/auth/callback?ticket=")
    ticket = destino.split("ticket=")[1]
    assert sso_tickets.resgatar(ticket) is not None


def test_callback_normaliza_o_email(client, sso_ligado, usuario_admin, graph_diz):
    """A Microsoft devolve com maiusculas; o usuario esta gravado minusculo."""
    graph_diz("  Admin@HS.com ")
    r = client.get("/auth/microsoft/callback?code=abc", follow_redirects=False)
    assert "/auth/callback?ticket=" in r.headers["location"]


def test_callback_sem_usuario_volta_para_o_login(client, sso_ligado, usuario_admin, graph_diz):
    """Sem provisionamento automatico: quem nao tem conta nao entra."""
    graph_diz("estranho@healthsafetytech.com")
    r = client.get("/auth/microsoft/callback?code=abc", follow_redirects=False)
    assert r.headers["location"] == "http://localhost:5173/login?erro=usuario_nao_encontrado"


def test_callback_usuario_inativo(client, sso_ligado, db_session, graph_diz):
    from app.core.security import hash_senha

    db_session.add(Usuario(nome="Ex", email="ex@hs.com", senha=hash_senha("senha123"), ativo=False))
    db_session.commit()
    graph_diz("ex@hs.com")
    r = client.get("/auth/microsoft/callback?code=abc", follow_redirects=False)
    assert r.headers["location"] == "http://localhost:5173/login?erro=usuario_inativo"


def test_callback_ignora_precisa_redefinir_senha(client, sso_ligado, db_session, graph_diz):
    """A flag existe para forcar troca de senha propria; quem entra por SSO nao
    usou senha nenhuma. O /auth/login continua bloqueando — outro teste cobre."""
    from app.core.security import hash_senha

    db_session.add(
        Usuario(nome="Novo", email="novo@hs.com", senha=hash_senha("senha123"), precisa_redefinir_senha=True)
    )
    db_session.commit()
    graph_diz("novo@hs.com")
    r = client.get("/auth/microsoft/callback?code=abc", follow_redirects=False)
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


def test_callback_sem_code(client, sso_ligado):
    r = client.get("/auth/microsoft/callback", follow_redirects=False)
    assert r.headers["location"] == "http://localhost:5173/login?erro=falha_microsoft"


def test_callback_code_recusado_pela_microsoft(client, sso_ligado, graph_diz):
    graph_diz(None, token=None)
    r = client.get("/auth/microsoft/callback?code=ruim", follow_redirects=False)
    assert r.headers["location"] == "http://localhost:5173/login?erro=falha_microsoft"


def test_callback_graph_fora_do_ar(client, sso_ligado, monkeypatch):
    """Timeout da Microsoft nao pode virar 500 na cara do usuario."""
    import httpx

    monkeypatch.setattr(microsoft_client, "trocar_code_por_token", lambda code: "tok")

    def _explode(_):
        raise httpx.ConnectTimeout("sem rede")

    monkeypatch.setattr(microsoft_client, "email_do_usuario", _explode)
    r = client.get("/auth/microsoft/callback?code=abc", follow_redirects=False)
    assert r.headers["location"] == "http://localhost:5173/login?erro=falha_microsoft"


def test_callback_503_com_sso_desligado(client, sso_desligado):
    assert client.get("/auth/microsoft/callback?code=abc", follow_redirects=False).status_code == 503
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_sso_microsoft.py -v`
Expected: FAIL — 404 nos dois endpoints novos.

- [ ] **Step 3: Escrever os endpoints**

Em `backend/app/api/auth.py`, acrescentar aos imports do topo:

```python
import logging
from urllib.parse import urlencode

from fastapi.responses import RedirectResponse

from app.core import sso_tickets
from app.integrations import microsoft_client

logger = logging.getLogger(__name__)
```

E, antes do `sso_status` (fim do arquivo):

```python
def _voltar_para_login(erro: str) -> RedirectResponse:
    return RedirectResponse(
        f"{settings.FRONTEND_URL}/login?{urlencode({'erro': erro})}", status_code=302
    )


@router.get("/microsoft")
def microsoft_autorizar():
    """Publico e de navegacao inteira: o botao no front e' uma ancora, nao um
    fetch — XHR nao segue redirect cross-origin."""
    if not settings.sso_ativo:
        raise HTTPException(status_code=503, detail="SSO Microsoft não configurado.")
    return RedirectResponse(microsoft_client.url_de_autorizacao(), status_code=302)


@router.get("/microsoft/callback")
def microsoft_callback(code: str | None = None, db: Session = Depends(get_db)):
    """Para onde a Microsoft devolve o navegador. Termina sempre em redirect:
    ou para /auth/callback com o ticket, ou para /login com ?erro=."""
    if not settings.sso_ativo:
        raise HTTPException(status_code=503, detail="SSO Microsoft não configurado.")
    if not code:
        return _voltar_para_login("falha_microsoft")

    try:
        token_ms = microsoft_client.trocar_code_por_token(code)
        email = emails.normalizar(microsoft_client.email_do_usuario(token_ms)) if token_ms else ""
    except Exception:
        # Rede, timeout, resposta estranha: o usuario ve a mensagem no login em
        # vez de um 500. O detalhe fica no log — e nunca inclui o token.
        logger.exception("Falha no callback do SSO Microsoft")
        return _voltar_para_login("falha_microsoft")

    if not email:
        return _voltar_para_login("falha_microsoft")

    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if usuario is None:
        # Sem provisionamento automatico: o cadastro continua na tela de
        # Usuarios, senao o tenant inteiro ganharia conta ao logar.
        return _voltar_para_login("usuario_nao_encontrado")
    if not usuario.ativo:
        return _voltar_para_login("usuario_inativo")

    # precisa_redefinir_senha NAO e' checado aqui de proposito: a flag forca a
    # troca de uma senha propria, e quem entra por SSO nao usou senha nenhuma.
    ticket = sso_tickets.emitir(
        criar_access_token(sub=str(usuario.id), tipo="usuario"),
        criar_refresh_token(sub=str(usuario.id), tipo="usuario"),
    )
    return RedirectResponse(
        f"{settings.FRONTEND_URL}/auth/callback?{urlencode({'ticket': ticket})}", status_code=302
    )
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_sso_microsoft.py -v`
Expected: PASS (29 testes).

- [ ] **Step 5: Rodar a suíte inteira**

Run: `pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/auth.py backend/tests/test_sso_microsoft.py
git commit -m "feat(auth): GET /auth/microsoft e callback do Entra ID"
```

---

### Task 5: Troca do ticket pelos tokens

**Files:**
- Modify: `backend/app/schemas/auth.py`
- Modify: `backend/app/api/auth.py`
- Test: `backend/tests/test_sso_microsoft.py` (acrescentar)

**Interfaces:**
- Consumes: `sso_tickets.resgatar` (Task 2); o callback da Task 4 para o teste ponta a ponta; schema `Token` (já existe: `access_token`, `refresh_token`, `token_type="bearer"`).
- Produces: `POST /auth/sso/exchange` com corpo `{"ticket": str}` → `Token` (200) ou 400.

- [ ] **Step 1: Escrever os testes que falham**

```python
def test_exchange_devolve_os_tokens(client, sso_ligado, usuario_admin, graph_diz):
    graph_diz("admin@hs.com")
    destino = client.get("/auth/microsoft/callback?code=abc", follow_redirects=False).headers["location"]
    ticket = destino.split("ticket=")[1]

    r = client.post("/auth/sso/exchange", json={"ticket": ticket})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["token_type"] == "bearer"
    assert corpo["access_token"] and corpo["refresh_token"]


def test_tokens_do_sso_valem_no_me(client, sso_ligado, usuario_admin, graph_diz):
    """A sessao nasce diferente mas e' indistinguivel da do login por senha."""
    graph_diz("admin@hs.com")
    destino = client.get("/auth/microsoft/callback?code=abc", follow_redirects=False).headers["location"]
    tokens = client.post("/auth/sso/exchange", json={"ticket": destino.split("ticket=")[1]}).json()

    r = client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert r.status_code == 200 and r.json()["email"] == "admin@hs.com"

    r = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200 and r.json()["access_token"]


def test_exchange_do_mesmo_ticket_duas_vezes_da_400(client, sso_ligado, usuario_admin, graph_diz):
    graph_diz("admin@hs.com")
    destino = client.get("/auth/microsoft/callback?code=abc", follow_redirects=False).headers["location"]
    ticket = destino.split("ticket=")[1]
    assert client.post("/auth/sso/exchange", json={"ticket": ticket}).status_code == 200
    assert client.post("/auth/sso/exchange", json={"ticket": ticket}).status_code == 400


def test_exchange_ticket_invalido_e_400_e_nao_401(client, sso_ligado):
    """401 faria o api.ts limpar o storage e sair da pagina antes de mostrar a
    mensagem; com 400 o AuthCallbackPage consegue explicar o que houve."""
    r = client.post("/auth/sso/exchange", json={"ticket": "nao-existe"})
    assert r.status_code == 400
    assert r.json()["detail"]


def test_exchange_e_publico(client, sso_ligado):
    assert client.post("/auth/sso/exchange", json={"ticket": "x"}).status_code == 400
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_sso_microsoft.py -v`
Expected: FAIL — 404 em `/auth/sso/exchange`.

- [ ] **Step 3: Adicionar o schema**

Em `backend/app/schemas/auth.py`, no fim:

```python
class SsoExchangeIn(BaseModel):
    ticket: str
```

- [ ] **Step 4: Adicionar o endpoint**

Em `backend/app/api/auth.py`: acrescentar `SsoExchangeIn` à linha de import dos schemas, e escrever, antes do `sso_status`:

```python
@router.post("/sso/exchange", response_model=Token)
def sso_exchange(dados: SsoExchangeIn):
    """Troca o ticket do redirect pelos tokens de verdade. Responde `Token` (e
    nao `LoginOut`): o SSO nunca devolve precisa_redefinir."""
    par = sso_tickets.resgatar(dados.ticket)
    if par is None:
        # 400 e nao 401 de proposito — ver o teste que fixa isso.
        raise HTTPException(status_code=400, detail="Link de acesso inválido ou expirado. Entre de novo.")
    access_token, refresh_token = par
    return Token(access_token=access_token, refresh_token=refresh_token)
```

- [ ] **Step 5: Rodar e ver passar**

Run: `pytest tests/test_sso_microsoft.py -v && pytest -q`
Expected: PASS (34 no arquivo, suíte inteira verde).

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/auth.py backend/app/schemas/auth.py backend/tests/test_sso_microsoft.py
git commit -m "feat(auth): POST /auth/sso/exchange troca o ticket pelos tokens"
```

---

### Task 6: Base para o front (`apiUrl` e `entrarComTokens`)

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/auth/AuthContext.tsx`
- Test: `frontend/src/auth/AuthContext.test.tsx` (acrescentar)

**Interfaces:**
- Consumes: `BASE_URL` (privado do `api.ts`), `setTokens` (`lib/auth-storage`), `apiJson`.
- Produces: `apiUrl(path: string): string` exportado de `lib/api`; `entrarComTokens(tokens: Tokens): Promise<void>` no valor do `AuthContext`.

- [ ] **Step 1: Escrever o teste que falha**

O arquivo já tem um componente `Probe` que expõe o contexto por botões e um
`renderProbe()`; o teste entra nesse mesmo formato. Acrescentar um botão ao
`Probe` existente:

```tsx
function Probe() {
  const { user, loading, login, logout, entrarComTokens } = useAuth()
  return (
    <div>
      <span data-testid="loading">{String(loading)}</span>
      <span data-testid="user">{user ? user.email : 'anon'}</span>
      <button onClick={() => login('erick@hs.com', 'senha')}>entrar</button>
      <button onClick={() => entrarComTokens({ access_token: 'sso-acc', refresh_token: 'sso-ref' })}>
        entrar por token
      </button>
      <button onClick={() => logout()}>sair</button>
    </div>
  )
}
```

E o caso novo, no fim do `describe('AuthContext', ...)`:

```tsx
  it('entrarComTokens persiste o par e hidrata o usuário', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(ME)))
    renderProbe()
    await waitFor(() => expect(screen.getByTestId('loading').textContent).toBe('false'))

    await act(async () => {
      screen.getByText('entrar por token').click()
    })

    await waitFor(() => expect(screen.getByTestId('user').textContent).toBe('erick@hs.com'))
    expect(getTokens()).toEqual({ access_token: 'sso-acc', refresh_token: 'sso-ref' })
  })
```

`act` e `getTokens` já estão importados no arquivo — não duplicar os imports.

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd frontend && npx vitest run src/auth/AuthContext.test.tsx`
Expected: FAIL — `entrarComTokens is not a function`.

- [ ] **Step 3: Exportar `apiUrl`**

Em `frontend/src/lib/api.ts`, logo depois da definição de `BASE_URL`:

```ts
/** URL absoluta da API. O botao do SSO e' uma ancora e precisa do mesmo
 *  BASE_URL que o apiFetch usa — que em producao vem do /config.js em runtime.
 *  Duplicar essa cascata numa segunda funcao seria pedir para as duas discordarem. */
export function apiUrl(path: string): string {
  return `${BASE_URL}${path}`
}
```

- [ ] **Step 4: Adicionar `entrarComTokens` ao contexto**

Em `frontend/src/auth/AuthContext.tsx` — na interface:

```ts
  entrarComTokens: (tokens: Tokens) => Promise<void>
```

na função:

```tsx
  async function entrarComTokens(tokens: Tokens) {
    setTokens(tokens)
    const me = await apiJson<User>('/auth/me')
    setUser(me)
  }
```

e no `value` do provider: `{{ user, loading, login, logout, definirSenha, entrarComTokens }}`.

- [ ] **Step 5: Rodar e ver passar**

Run: `npx vitest run src/auth/AuthContext.test.tsx`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/auth/AuthContext.tsx frontend/src/auth/AuthContext.test.tsx
git commit -m "feat(front): apiUrl exportado e entrarComTokens no AuthContext"
```

---

### Task 7: Página de callback

**Files:**
- Create: `frontend/src/app/pages/AuthCallbackPage.tsx`
- Create: `frontend/src/app/pages/AuthCallbackPage.test.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `entrarComTokens` (Task 6); `apiJson`, `ApiError`; `POST /auth/sso/exchange` (Task 5).
- Produces: componente `AuthCallbackPage` exportado nomeado; rota pública `/auth/callback`.

- [ ] **Step 1: Escrever os testes que falham**

Criar `frontend/src/app/pages/AuthCallbackPage.test.tsx`:

```tsx
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const entrarComTokens = vi.fn()
const navigate = vi.fn()
const apiJson = vi.fn()

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ entrarComTokens }),
}))

vi.mock('../../lib/api', async () => {
  const real = await vi.importActual<typeof import('../../lib/api')>('../../lib/api')
  return { ...real, apiJson: (...args: unknown[]) => apiJson(...args) }
})

vi.mock('react-router-dom', async () => {
  const real = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...real, useNavigate: () => navigate }
})

import { AuthCallbackPage } from './AuthCallbackPage'
import { ApiError } from '../../lib/api'

function montar(query: string) {
  return render(
    <MemoryRouter initialEntries={[`/auth/callback${query}`]}>
      <AuthCallbackPage />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  entrarComTokens.mockResolvedValue(undefined)
})

describe('AuthCallbackPage', () => {
  it('troca o ticket, entra e vai para /app', async () => {
    apiJson.mockResolvedValue({ access_token: 'acc', refresh_token: 'ref' })
    montar('?ticket=abc123')

    await waitFor(() =>
      expect(apiJson).toHaveBeenCalledWith('/auth/sso/exchange', {
        method: 'POST',
        body: JSON.stringify({ ticket: 'abc123' }),
      }),
    )
    await waitFor(() => expect(entrarComTokens).toHaveBeenCalledWith({ access_token: 'acc', refresh_token: 'ref' }))
    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/app', { replace: true }))
  })

  it('mostra a mensagem do backend quando o ticket ja foi usado', async () => {
    apiJson.mockRejectedValue(new ApiError(400, 'Link de acesso inválido ou expirado. Entre de novo.'))
    montar('?ticket=usado')

    expect(await screen.findByText(/Link de acesso inválido ou expirado/)).toBeInTheDocument()
    expect(screen.getByText('Voltar para o login')).toBeInTheDocument()
    expect(navigate).not.toHaveBeenCalled()
  })

  it('reclama quando volta sem ticket', async () => {
    montar('')
    expect(await screen.findByText(/Link de retorno inválido/)).toBeInTheDocument()
    expect(apiJson).not.toHaveBeenCalled()
  })

  it('troca o ticket uma vez so', async () => {
    // O ticket e' de uso unico e o StrictMode roda o efeito duas vezes em dev:
    // a segunda chamada tomaria 400 e derrubaria um login que deu certo.
    apiJson.mockResolvedValue({ access_token: 'acc', refresh_token: 'ref' })
    const { rerender } = montar('?ticket=abc123')
    rerender(
      <MemoryRouter initialEntries={['/auth/callback?ticket=abc123']}>
        <AuthCallbackPage />
      </MemoryRouter>,
    )
    await waitFor(() => expect(entrarComTokens).toHaveBeenCalled())
    expect(apiJson).toHaveBeenCalledTimes(1)
  })
})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npx vitest run src/app/pages/AuthCallbackPage.test.tsx`
Expected: FAIL — módulo `./AuthCallbackPage` não existe.

- [ ] **Step 3: Escrever a página**

Criar `frontend/src/app/pages/AuthCallbackPage.tsx`:

```tsx
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { apiJson, ApiError } from '../../lib/api'
import { Spinner } from '../../components/ui/Spinner'
import { IconAlertCircle } from '../../components/ui/icons'
import type { Tokens } from '../../lib/auth-storage'
import logo from '../../assets/logo.png'

export function AuthCallbackPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const { entrarComTokens } = useAuth()
  const [erro, setErro] = useState('')
  const jaTrocou = useRef(false)

  useEffect(() => {
    // O ticket e' de uso unico e o StrictMode roda este efeito duas vezes em
    // dev — a segunda chamada tomaria 400 e derrubaria um login que deu certo.
    if (jaTrocou.current) return
    jaTrocou.current = true

    const ticket = params.get('ticket')
    if (!ticket) {
      setErro('Link de retorno inválido. Entre novamente.')
      return
    }

    void (async () => {
      try {
        const tokens = await apiJson<Tokens>('/auth/sso/exchange', {
          method: 'POST',
          body: JSON.stringify({ ticket }),
        })
        await entrarComTokens(tokens)
        navigate('/app', { replace: true })
      } catch (err) {
        setErro(
          err instanceof ApiError ? err.message : 'Não foi possível concluir o login. Tente novamente.',
        )
      }
    })()
  }, [params, navigate, entrarComTokens])

  if (!erro) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-3 bg-background">
        <Spinner className="w-8 h-8" />
        <p className="text-sm text-slate-400">Entrando…</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <img src={logo} alt="Health Safety" className="h-16 w-auto mb-3" />
          <h1 className="text-2xl font-extrabold text-slate-100 tracking-tight">GestorHS</h1>
        </div>
        <div className="rounded-2xl bg-background-surface border border-border shadow-sm p-6 space-y-4">
          <div className="flex items-center gap-2 rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">
            <IconAlertCircle className="w-4 h-4 shrink-0" />
            {erro}
          </div>
          <Link
            to="/login"
            className="block w-full py-2.5 rounded-lg bg-primary text-white text-sm font-semibold text-center hover:bg-primary-600 transition-all"
          >
            Voltar para o login
          </Link>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Registrar a rota**

Em `frontend/src/App.tsx`: importar `import { AuthCallbackPage } from './app/pages/AuthCallbackPage'` e acrescentar a rota **dentro do `AppAuthLayout`** — ela precisa do `AuthProvider` e não pode ficar sob o `ProtectedRoute`:

```tsx
          <Route element={<AppAuthLayout />}>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/auth/callback" element={<AuthCallbackPage />} />
            <Route path="/app/*" element={<ProtectedRoute><AppRoutes /></ProtectedRoute>} />
          </Route>
```

- [ ] **Step 5: Rodar e ver passar**

Run: `npx vitest run src/app/pages/AuthCallbackPage.test.tsx`
Expected: PASS (4 testes).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/pages/AuthCallbackPage.tsx frontend/src/app/pages/AuthCallbackPage.test.tsx frontend/src/App.tsx
git commit -m "feat(front): pagina /auth/callback que troca o ticket do SSO"
```

---

### Task 8: Botão no login e verificação final

**Files:**
- Modify: `frontend/src/app/pages/LoginPage.tsx`
- Create: `frontend/src/app/pages/LoginPage.test.tsx`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: `apiUrl` (Task 6); `GET /auth/sso/status` (Task 1); `GET /auth/microsoft` (Task 4).
- Produces: nada para tarefas seguintes — é a última.

- [ ] **Step 1: Escrever os testes que falham**

Criar `frontend/src/app/pages/LoginPage.test.tsx`:

```tsx
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const login = vi.fn()
const apiJson = vi.fn()

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ login, definirSenha: vi.fn(), user: null, loading: false }),
}))

vi.mock('../../lib/api', async () => {
  const real = await vi.importActual<typeof import('../../lib/api')>('../../lib/api')
  return { ...real, apiJson: (...args: unknown[]) => apiJson(...args), apiUrl: (p: string) => `http://api.teste${p}` }
})

import { LoginPage } from './LoginPage'

function montar(query = '') {
  return render(
    <MemoryRouter initialEntries={[`/login${query}`]}>
      <LoginPage />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  apiJson.mockResolvedValue({ ativo: true })
})

describe('LoginPage — SSO', () => {
  it('mostra o botao da Microsoft como ancora para o backend', async () => {
    montar()
    const botao = await screen.findByText('Entrar com Microsoft')
    expect(botao.closest('a')).toHaveAttribute('href', 'http://api.teste/auth/microsoft')
  })

  it('esconde o botao quando o SSO esta desligado', async () => {
    apiJson.mockResolvedValue({ ativo: false })
    montar()
    await waitFor(() => expect(apiJson).toHaveBeenCalledWith('/auth/sso/status'))
    expect(screen.queryByText('Entrar com Microsoft')).toBeNull()
  })

  it('esconde o botao se o status falhar', async () => {
    apiJson.mockRejectedValue(new Error('sem rede'))
    montar()
    await waitFor(() => expect(apiJson).toHaveBeenCalled())
    expect(screen.queryByText('Entrar com Microsoft')).toBeNull()
  })

  it('mostra a mensagem de usuario nao encontrado vinda do callback', async () => {
    montar('?erro=usuario_nao_encontrado')
    expect(
      await screen.findByText(/Nenhuma conta GestorHS para este e-mail Microsoft/),
    ).toBeInTheDocument()
  })

  it('mostra a mensagem de usuario inativo', async () => {
    montar('?erro=usuario_inativo')
    expect(await screen.findByText(/Usuário desativado/)).toBeInTheDocument()
  })

  it('ignora ?erro= desconhecido', async () => {
    montar('?erro=chute')
    await waitFor(() => expect(apiJson).toHaveBeenCalled())
    expect(screen.getByText('Entrar')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npx vitest run src/app/pages/LoginPage.test.tsx`
Expected: FAIL — não existe "Entrar com Microsoft" na tela.

- [ ] **Step 3: Ler o `?erro=` e consultar o status**

Em `frontend/src/app/pages/LoginPage.tsx` — trocar o import do react-router por
`import { Navigate, useNavigate, useSearchParams } from 'react-router-dom'`,
acrescentar `useEffect` ao import do react e `apiUrl, apiJson` ao import de
`../../lib/api`. Antes do componente:

```tsx
const MENSAGENS_SSO: Record<string, string> = {
  usuario_nao_encontrado: 'Nenhuma conta GestorHS para este e-mail Microsoft. Fale com o administrador.',
  usuario_inativo: 'Usuário desativado. Fale com o administrador.',
  falha_microsoft: 'Falha na autenticação com a Microsoft. Tente novamente.',
}
```

E dentro do componente, junto dos outros `useState` (o `erro` já existe — trocar a inicialização):

```tsx
  const [params] = useSearchParams()
  const [erro, setErro] = useState(MENSAGENS_SSO[params.get('erro') ?? ''] ?? '')
  const [ssoAtivo, setSsoAtivo] = useState(false)

  useEffect(() => {
    // O backend e' a fonte unica: um VITE_SSO_ATIVO no build duplicaria a
    // configuracao em duas pontas que podem discordar. Falhou, esconde.
    void apiJson<{ ativo: boolean }>('/auth/sso/status')
      .then((r) => setSsoAtivo(r.ativo))
      .catch(() => setSsoAtivo(false))
  }, [])
```

> Atenção aos hooks: as chamadas de `useState`/`useEffect` têm que ficar
> **acima** dos `if (loading)` e `if (user)` que retornam cedo.

- [ ] **Step 4: Acrescentar o divisor e o botão**

Dentro do `<form>` de login, logo **depois** do `<button type="submit">Entrar</button>`:

```tsx
              {ssoAtivo && (
                <>
                  <div className="flex items-center gap-3 pt-2">
                    <span className="h-px flex-1 bg-border" />
                    <span className="text-xs text-slate-500">ou</span>
                    <span className="h-px flex-1 bg-border" />
                  </div>
                  <a
                    href={apiUrl('/auth/microsoft')}
                    className="w-full py-2.5 rounded-lg bg-background-surface border border-border text-sm font-semibold text-slate-200 hover:bg-white/5 active:scale-[0.98] transition-all flex items-center justify-center gap-2"
                  >
                    <svg className="w-4 h-4" viewBox="0 0 21 21" aria-hidden="true">
                      <rect x="1" y="1" width="9" height="9" fill="#f25022" />
                      <rect x="11" y="1" width="9" height="9" fill="#7fba00" />
                      <rect x="1" y="11" width="9" height="9" fill="#00a4ef" />
                      <rect x="11" y="11" width="9" height="9" fill="#ffb900" />
                    </svg>
                    Entrar com Microsoft
                  </a>
                </>
              )}
```

É uma **âncora**, não um `<button onClick>`: o fluxo é navegação de página inteira até a Microsoft, e XHR não segue redirect cross-origin.

- [ ] **Step 5: Rodar e ver passar**

Run: `npx vitest run src/app/pages/LoginPage.test.tsx`
Expected: PASS (6 testes).

- [ ] **Step 6: Verificação completa do front**

Run: `cd frontend && npm run lint && npx tsc -b --noEmit && npm run build && npx vitest run`
Expected: tudo verde.

- [ ] **Step 7: Verificação completa do back**

Run: `cd backend && source .venv/bin/activate && pytest -q`
Expected: tudo verde.

- [ ] **Step 8: Documentar no `CLAUDE.md`**

Na seção que descreve as duas aplicações, trocar a linha do interno por:

```markdown
- **Interno** (`/app`) — equipe da Health Safety; login por e-mail + senha **ou "Entrar com Microsoft"** (SSO Entra ID, `MS_*` no `.env`; vazio = desligado e o botão some). Só entra quem já tem `Usuario` cadastrado — não há provisionamento automático.
```

- [ ] **Step 9: Commit**

```bash
git add frontend/src/app/pages/LoginPage.tsx frontend/src/app/pages/LoginPage.test.tsx CLAUDE.md
git commit -m "feat(front): botao Entrar com Microsoft e mensagens de erro do SSO"
```

---

## Verificação manual (depois do deploy)

Só dá para fazer com o App Registration ativo. O `backend/.env` local aponta para `localhost:8000`, redirect já cadastrada no Azure.

1. `uvicorn app.main:app --reload` + `npm run dev`, abrir `http://localhost:5173/login` → o botão "Entrar com Microsoft" aparece.
2. Clicar → autenticar com a conta corporativa → voltar logado no `/app`, nome certo no cabeçalho.
3. Entrar com uma conta Microsoft sem `Usuario` no GestorHS → volta ao login com "Nenhuma conta GestorHS para este e-mail".
4. Desativar um usuário na tela de Usuários e tentar → "Usuário desativado".
5. Login por e-mail e senha continua funcionando.
6. Recarregar `/auth/callback?ticket=<o mesmo de antes>` → mensagem de link inválido, **sem** piscar para o `/login`.
7. Deploy: no Easypanel, preencher as cinco envs com os valores de **produção** (`MS_REDIRECT_URI` e `FRONTEND_URL` diferentes do local — estão comentados no `.env`).

## Notas relacionadas

- Spec: [`2026-08-31-sso-microsoft-design.md`](../specs/2026-08-31-sso-microsoft-design.md)
- `2026-08-28-sso-microsoft-design.md` (repo TaskHS) — a implementação irmã.
- [Fundação de auth do backend](2026-06-01-backend-fundacao-auth.md) — o login por senha e os tokens que o SSO reusa sem tocar.
