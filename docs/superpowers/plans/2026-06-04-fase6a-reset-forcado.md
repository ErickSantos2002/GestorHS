# Fase 6A (Reset forçado de senha no 1º login) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Login com `precisa_redefinir_senha` deixa de ser 403 e passa a um fluxo "defina sua nova senha" (internos e portal); admin passa a dar senhas temporárias.

**Architecture:** Backend — login verifica a senha e, se correta + flag, retorna `{precisa_redefinir:true}` (sem tokens); `definir-senha`/`definir-senha-portal` reautenticam e gravam a nova senha (login automático); `redefinir-senha` do admin grava senha temporária. Frontend — passo "definir senha" no login do `/app` e do `/portal`.

**Tech Stack:** Backend FastAPI/SQLAlchemy/pytest; Frontend React 19/TS/Vite/Vitest.

**Spec:** `docs/superpowers/specs/2026-06-04-fase6a-reset-forcado-design.md`

**Comandos:** Backend Docker (`docker compose exec -T backend python -m pytest <args>`). Frontend `npm --prefix frontend run test|lint|build`. Git via `git -C /d/GitHub/GestorHS`. Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

**Branch:** antes da Task 1:
```bash
git -C /d/GitHub/GestorHS checkout -b feat/fase6a-reset-forcado
```

## Convenções (já estabelecidas)
- Backend: `app/api/auth.py` (`_DUMMY_HASH`, `verificar_senha`, `criar_access_token`/`criar_refresh_token`, `Cliente`/`or_` já importados na 5A). `app/core/security.py` (`hash_senha`/`verificar_senha`; hash vazio → False). Schemas em `app/schemas/auth.py`. Testes pytest/SQLite; fixtures `usuario_admin` (admin/senha123), `cliente_portal` (empresa cgc="11222333000144" + usuário cliente1/portal123).
- Frontend: `auth/AuthContext.tsx` (`login`→POST /auth/login + setTokens + /auth/me), `app/pages/LoginPage.tsx`; `portal/PortalAuthContext.tsx`, `portal/PortalLoginPage.tsx`. `lib/api` (`apiJson`), `lib/auth-storage` (`Tokens`, `setTokens`). Testes Vitest mock-fetch.

---

### Task 1: Login sinaliza "precisa redefinir" (equipe + portal)

**Files:**
- Modify: `backend/app/schemas/auth.py` (`LoginOut`)
- Modify: `backend/app/api/auth.py` (`_verificar_credenciais`, `login`, `login_portal`)
- Test: `backend/tests/test_auth.py`

- [ ] **Step 1: Atualizar/adicionar testes em `backend/tests/test_auth.py`**

(a) Substitua `test_login_senha_legada_exige_redefinicao` (conta legada tem hash vazio → agora 401, não 403):
```python
def test_login_legado_hash_vazio_401(client, db_session):
    from app.models import Usuario
    db_session.add(Usuario(nome="Velho", login="velho", senha="", precisa_redefinir_senha=True))
    db_session.commit()
    r = client.post("/auth/login", json={"login": "velho", "senha": "qualquer"})
    assert r.status_code == 401
```
(b) Acrescente ao fim do arquivo:
```python
def test_login_precisa_redefinir_sinaliza(client, db_session):
    from app.models import Usuario
    from app.core.security import hash_senha
    db_session.add(Usuario(nome="Temp", login="temp", senha=hash_senha("provisoria1"), precisa_redefinir_senha=True))
    db_session.commit()
    r = client.post("/auth/login", json={"login": "temp", "senha": "provisoria1"})
    assert r.status_code == 200
    body = r.json()
    assert body["precisa_redefinir"] is True
    assert body.get("access_token") in (None, "")


def test_login_normal_nao_pede_redefinir(client, usuario_admin):
    r = client.post("/auth/login", json={"login": "admin", "senha": "senha123"})
    assert r.status_code == 200
    body = r.json()
    assert body.get("precisa_redefinir") in (False, None)
    assert body["access_token"]


def test_login_portal_precisa_redefinir(client, cliente_portal, db_session):
    from app.models import UsuarioCliente
    from app.core.security import hash_senha
    cli = db_session.query(UsuarioCliente).filter(UsuarioCliente.id == cliente_portal.id).first()
    cli.precisa_redefinir_senha = True
    cli.senha = hash_senha("provisoria1")
    db_session.commit()
    r = client.post("/auth/login-portal", json={"documento": "11222333000144", "login": "cliente1", "senha": "provisoria1"})
    assert r.status_code == 200 and r.json()["precisa_redefinir"] is True
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_auth.py -q`
Expected: FAIL (legado dá 403, não há `precisa_redefinir`).

- [ ] **Step 3: Adicionar `LoginOut` em `backend/app/schemas/auth.py`**

```python
class LoginOut(BaseModel):
    precisa_redefinir: bool = False
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
```

- [ ] **Step 4: Refatorar `backend/app/api/auth.py`** — adicione o helper e troque `login`/`login_portal`. Importe `LoginOut` no import de schemas.

```python
def _verificar_credenciais(registro, senha: str) -> None:
    """401 se inexistente (com timing achatado) ou senha incorreta. Não bloqueia por precisa_redefinir."""
    if registro is None:
        verificar_senha(senha, _DUMMY_HASH)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")
    if not verificar_senha(senha, registro.senha):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")


@router.post("/login", response_model=LoginOut)
def login(dados: LoginRequest, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.login == dados.login).first()
    _verificar_credenciais(usuario, dados.senha)
    if usuario.precisa_redefinir_senha:
        return LoginOut(precisa_redefinir=True)
    return LoginOut(
        access_token=criar_access_token(sub=str(usuario.id), tipo="usuario"),
        refresh_token=criar_refresh_token(sub=str(usuario.id), tipo="usuario"),
    )


@router.post("/login-portal", response_model=LoginOut)
def login_portal(dados: PortalLoginRequest, db: Session = Depends(get_db)):
    doc = "".join(c for c in dados.documento if c.isdigit())
    empresa = db.query(Cliente).filter(or_(Cliente.cgc == doc, Cliente.cpf == doc)).first() if doc else None
    if empresa is None:
        _verificar_credenciais(None, dados.senha)
    cli = (
        db.query(UsuarioCliente)
        .filter(UsuarioCliente.cliente == empresa.id, UsuarioCliente.login == dados.login)
        .first()
    )
    _verificar_credenciais(cli, dados.senha)
    if cli.precisa_redefinir_senha:
        return LoginOut(precisa_redefinir=True)
    return LoginOut(
        access_token=criar_access_token(sub=str(cli.id), tipo="cliente", cliente=cli.cliente),
        refresh_token=criar_refresh_token(sub=str(cli.id), tipo="cliente", cliente=cli.cliente),
    )
```
> A função antiga `_autenticar` deixa de ser usada por `login`/`login_portal`. Mantenha-a no arquivo apenas se outro endpoint a usar; caso contrário, pode removê-la (confira que nada mais a referencia).

- [ ] **Step 5: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_auth.py -q`
Expected: PASS (incl. os novos; os testes de login normal/portal seguem verdes pois `LoginOut` traz `access_token`).

- [ ] **Step 6: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/app/schemas/auth.py backend/app/api/auth.py backend/tests/test_auth.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): login sinaliza precisa_redefinir (sem 403) — equipe e portal"
```

---

### Task 2: Endpoints `definir-senha` e `definir-senha-portal`

**Files:**
- Modify: `backend/app/schemas/auth.py` (`DefinirSenhaIn`, `DefinirSenhaPortalIn`)
- Modify: `backend/app/api/auth.py`
- Test: `backend/tests/test_auth.py` (estender)

- [ ] **Step 1: Escrever os testes falhando** — acrescente ao FIM de `backend/tests/test_auth.py`:

```python
def test_definir_senha_fluxo(client, db_session):
    from app.models import Usuario
    from app.core.security import hash_senha
    db_session.add(Usuario(nome="Temp", login="temp2", senha=hash_senha("provisoria1"), precisa_redefinir_senha=True))
    db_session.commit()
    r = client.post("/auth/definir-senha", json={"login": "temp2", "senha_atual": "provisoria1", "nova_senha": "novasenha123"})
    assert r.status_code == 200 and r.json()["access_token"]
    # login normal com a nova senha funciona e não pede redefinir
    r2 = client.post("/auth/login", json={"login": "temp2", "senha": "novasenha123"})
    assert r2.status_code == 200 and r2.json()["access_token"] and not r2.json().get("precisa_redefinir")


def test_definir_senha_atual_errada_401(client, db_session):
    from app.models import Usuario
    from app.core.security import hash_senha
    db_session.add(Usuario(nome="Temp", login="temp3", senha=hash_senha("provisoria1"), precisa_redefinir_senha=True))
    db_session.commit()
    r = client.post("/auth/definir-senha", json={"login": "temp3", "senha_atual": "errada", "nova_senha": "novasenha123"})
    assert r.status_code == 401


def test_definir_senha_conta_sem_flag_400(client, usuario_admin):
    r = client.post("/auth/definir-senha", json={"login": "admin", "senha_atual": "senha123", "nova_senha": "novasenha123"})
    assert r.status_code == 400


def test_definir_senha_portal_fluxo(client, cliente_portal, db_session):
    from app.models import UsuarioCliente
    from app.core.security import hash_senha
    cli = db_session.query(UsuarioCliente).filter(UsuarioCliente.id == cliente_portal.id).first()
    cli.precisa_redefinir_senha = True
    cli.senha = hash_senha("provisoria1")
    db_session.commit()
    r = client.post("/auth/definir-senha-portal", json={"documento": "11222333000144", "login": "cliente1", "senha_atual": "provisoria1", "nova_senha": "novasenha123"})
    assert r.status_code == 200 and r.json()["access_token"]
    r2 = client.post("/auth/login-portal", json={"documento": "11222333000144", "login": "cliente1", "senha": "novasenha123"})
    assert r2.status_code == 200 and r2.json()["access_token"] and not r2.json().get("precisa_redefinir")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_auth.py -q`
Expected: FAIL (404 — endpoints não existem).

- [ ] **Step 3: Adicionar schemas em `backend/app/schemas/auth.py`** (usa `Field` já importado):

```python
class DefinirSenhaIn(BaseModel):
    login: str
    senha_atual: str
    nova_senha: str = Field(min_length=8)


class DefinirSenhaPortalIn(BaseModel):
    documento: str
    login: str
    senha_atual: str
    nova_senha: str = Field(min_length=8)
```

- [ ] **Step 4: Adicionar os endpoints em `backend/app/api/auth.py`** — importe `DefinirSenhaIn, DefinirSenhaPortalIn` no import de schemas; acrescente:

```python
@router.post("/definir-senha", response_model=Token)
def definir_senha(dados: DefinirSenhaIn, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.login == dados.login).first()
    _verificar_credenciais(usuario, dados.senha_atual)
    if not usuario.precisa_redefinir_senha:
        raise HTTPException(status_code=400, detail="conta não requer redefinição")
    usuario.senha = hash_senha(dados.nova_senha)
    usuario.precisa_redefinir_senha = False
    db.commit()
    return Token(
        access_token=criar_access_token(sub=str(usuario.id), tipo="usuario"),
        refresh_token=criar_refresh_token(sub=str(usuario.id), tipo="usuario"),
    )


@router.post("/definir-senha-portal", response_model=Token)
def definir_senha_portal(dados: DefinirSenhaPortalIn, db: Session = Depends(get_db)):
    doc = "".join(c for c in dados.documento if c.isdigit())
    empresa = db.query(Cliente).filter(or_(Cliente.cgc == doc, Cliente.cpf == doc)).first() if doc else None
    if empresa is None:
        _verificar_credenciais(None, dados.senha_atual)
    cli = (
        db.query(UsuarioCliente)
        .filter(UsuarioCliente.cliente == empresa.id, UsuarioCliente.login == dados.login)
        .first()
    )
    _verificar_credenciais(cli, dados.senha_atual)
    if not cli.precisa_redefinir_senha:
        raise HTTPException(status_code=400, detail="conta não requer redefinição")
    cli.senha = hash_senha(dados.nova_senha)
    cli.precisa_redefinir_senha = False
    db.commit()
    return Token(
        access_token=criar_access_token(sub=str(cli.id), tipo="cliente", cliente=cli.cliente),
        refresh_token=criar_refresh_token(sub=str(cli.id), tipo="cliente", cliente=cli.cliente),
    )
```
> `hash_senha` já está importado no topo de `auth.py`.

- [ ] **Step 5: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_auth.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/app/schemas/auth.py backend/app/api/auth.py backend/tests/test_auth.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): definir-senha e definir-senha-portal (reset forcado)"
```

---

### Task 3: `redefinir-senha` do admin grava senha temporária

**Files:**
- Modify: `backend/app/api/usuarios.py`
- Test: `backend/tests/test_acesso.py` (ajustar o teste de redefinir-senha)

- [ ] **Step 1: Localizar e ajustar o teste existente** — em `backend/tests/test_acesso.py`, encontre o teste de `redefinir-senha` (busque por `redefinir-senha`). Ele provavelmente loga após o reset esperando tokens. Ajuste-o para o novo comportamento (após o reset, o login sinaliza `precisa_redefinir`) e adicione a verificação do flag. Versão de referência (substitua o teste correspondente):
```python
def test_redefinir_senha_admin_deixa_temporaria(client, usuario_admin, db_session):
    from app.models import Usuario
    from app.core.security import hash_senha
    h = {"Authorization": f"Bearer {client.post('/auth/login', json={'login':'admin','senha':'senha123'}).json()['access_token']}"}
    alvo = Usuario(nome="Alvo", login="alvo", senha=hash_senha("antiga123"), precisa_redefinir_senha=False)
    db_session.add(alvo); db_session.commit(); db_session.refresh(alvo)
    r = client.post(f"/usuarios/{alvo.id}/redefinir-senha", json={"nova_senha": "temp12345"}, headers=h)
    assert r.status_code == 204
    db_session.refresh(alvo)
    assert alvo.precisa_redefinir_senha is True
    # login com a temporária sinaliza precisa_redefinir
    login = client.post("/auth/login", json={"login": "alvo", "senha": "temp12345"}).json()
    assert login["precisa_redefinir"] is True
```
> Se o teste atual tiver outro nome/assert, troque-o por este (mesma cobertura, comportamento novo). Rode `docker compose exec -T backend python -m pytest tests/test_acesso.py -q` para ver o estado atual.

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_acesso.py -q`
Expected: FAIL (redefinir-senha ainda zera o flag).

- [ ] **Step 3: Ajustar `redefinir_senha` em `backend/app/api/usuarios.py`** — troque a linha que zera o flag:
```python
    u.senha = hash_senha(dados.nova_senha)
    u.precisa_redefinir_senha = True
    db.commit()
```

- [ ] **Step 4: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_acesso.py -q`
Expected: PASS.

- [ ] **Step 5: Rodar a suíte backend inteira**

Run: `docker compose exec -T backend python -m pytest -q`
Expected: verde (~168). Se algum outro teste assumia o flag limpo após redefinir, ajuste-o.

- [ ] **Step 6: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/app/api/usuarios.py backend/tests/test_acesso.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): redefinir-senha do admin grava senha temporaria (forca troca)"
```

---

### Task 4: Frontend `/app` — definir senha no login

**Files:**
- Modify: `frontend/src/auth/AuthContext.tsx`
- Modify: `frontend/src/app/pages/LoginPage.tsx`
- Test: `frontend/src/auth/AuthContext.test.tsx` (estender)

- [ ] **Step 1: Escrever os testes falhando** — acrescente ao FIM do describe em `frontend/src/auth/AuthContext.test.tsx` (novo Probe que expõe o resultado do login e o definirSenha):

```tsx
function ProbeReset() {
  const { user, login, definirSenha } = useAuth()
  return (
    <div>
      <span data-testid="user2">{user ? user.login : 'anon'}</span>
      <span data-testid="res" />
      <button onClick={async () => { const r = await login('temp', 'prov'); document.querySelector('[data-testid=res]')!.textContent = String(r.precisa_redefinir) }}>login</button>
      <button onClick={() => definirSenha('temp', 'prov', 'novasenha123')}>definir</button>
    </div>
  )
}

describe('AuthContext — reset forçado', () => {
  beforeEach(() => { localStorage.clear(); vi.restoreAllMocks() })

  it('login com precisa_redefinir não autentica', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ precisa_redefinir: true })))
    render(<AuthProvider><ProbeReset /></AuthProvider>)
    await act(async () => { screen.getByText('login').click() })
    await waitFor(() => expect(screen.getByTestId('res').textContent).toBe('true'))
    expect(screen.getByTestId('user2').textContent).toBe('anon')
  })

  it('definirSenha guarda tokens e carrega o usuário', async () => {
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(jsonResponse({ access_token: 'a', refresh_token: 'r' }))  // definir-senha
      .mockResolvedValueOnce(jsonResponse(ME)))  // /auth/me
    render(<AuthProvider><ProbeReset /></AuthProvider>)
    await act(async () => { screen.getByText('definir').click() })
    await waitFor(() => expect(screen.getByTestId('user2').textContent).toBe('erick'))
    expect(getTokens()?.access_token).toBe('a')
  })
})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm --prefix frontend run test -- auth/AuthContext`
Expected: FAIL (`definirSenha` inexistente; `login` não retorna `{precisa_redefinir}`).

- [ ] **Step 3: Atualizar `frontend/src/auth/AuthContext.tsx`** — exporte `LoginResult`, faça `login` retornar e adicione `definirSenha`. Substitua a interface e as funções:

No topo (após `User`):
```tsx
export interface LoginResult {
  precisa_redefinir: boolean
}

interface LoginRespBody {
  precisa_redefinir?: boolean
  access_token?: string
  refresh_token?: string
}
```
Na `interface AuthContextValue`, troque a assinatura de `login` e acrescente `definirSenha`:
```tsx
  login: (login: string, senha: string) => Promise<LoginResult>
  definirSenha: (login: string, senhaAtual: string, novaSenha: string) => Promise<void>
```
Substitua a função `login` e adicione `definirSenha`:
```tsx
  async function login(login: string, senha: string): Promise<LoginResult> {
    const r = await apiJson<LoginRespBody>('/auth/login', { method: 'POST', body: JSON.stringify({ login, senha }) })
    if (r.precisa_redefinir) return { precisa_redefinir: true }
    setTokens({ access_token: r.access_token as string, refresh_token: r.refresh_token as string })
    const me = await apiJson<User>('/auth/me')
    setUser(me)
    return { precisa_redefinir: false }
  }

  async function definirSenha(login: string, senhaAtual: string, novaSenha: string) {
    const tokens = await apiJson<Tokens>('/auth/definir-senha', {
      method: 'POST',
      body: JSON.stringify({ login, senha_atual: senhaAtual, nova_senha: novaSenha }),
    })
    setTokens(tokens)
    const me = await apiJson<User>('/auth/me')
    setUser(me)
  }
```
E inclua `definirSenha` no `value` do provider: `value={{ user, loading, login, logout, definirSenha }}`.

- [ ] **Step 4: Rodar e ver passar**

Run: `npm --prefix frontend run test -- auth/AuthContext`
Expected: PASS (os testes antigos seguem verdes — login normal não muda forma).

- [ ] **Step 5: Reescrever `frontend/src/app/pages/LoginPage.tsx`** (passo "definir"):

```tsx
import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { ApiError } from '../../lib/api'
import { Input } from '../../components/ui/Input'
import { Spinner } from '../../components/ui/Spinner'
import { IconAlertCircle } from '../../components/ui/icons'

export function LoginPage() {
  const { login, definirSenha, user, loading } = useAuth()
  const navigate = useNavigate()
  const [usuario, setUsuario] = useState('')
  const [senha, setSenha] = useState('')
  const [etapa, setEtapa] = useState<'login' | 'definir'>('login')
  const [novaSenha, setNovaSenha] = useState('')
  const [confirma, setConfirma] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  if (loading) {
    return <div className="flex h-screen items-center justify-center bg-background"><Spinner className="w-8 h-8" /></div>
  }
  if (user) return <Navigate to="/app" replace />

  async function onLogin(e: FormEvent) {
    e.preventDefault()
    setErro(''); setEnviando(true)
    try {
      const r = await login(usuario, senha)
      if (r.precisa_redefinir) { setNovaSenha(''); setConfirma(''); setEtapa('definir') }
      else navigate('/app', { replace: true })
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao entrar. Tente novamente.')
    } finally { setEnviando(false) }
  }

  async function onDefinir(e: FormEvent) {
    e.preventDefault()
    setErro('')
    if (novaSenha.length < 8) { setErro('A nova senha deve ter ao menos 8 caracteres.'); return }
    if (novaSenha !== confirma) { setErro('As senhas não conferem.'); return }
    setEnviando(true)
    try {
      await definirSenha(usuario, senha, novaSenha)
      navigate('/app', { replace: true })
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao definir a senha.')
    } finally { setEnviando(false) }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-primary/15 flex items-center justify-center mb-3 shadow-sm">
            <span className="text-xl font-extrabold text-primary">G</span>
          </div>
          <h1 className="text-2xl font-extrabold text-slate-100 tracking-tight">GestorHS</h1>
          <p className="text-sm text-slate-500 mt-1">{etapa === 'login' ? 'Faça login para continuar' : 'Defina sua nova senha'}</p>
        </div>
        <div className="rounded-2xl bg-background-surface border border-border shadow-sm p-6">
          {etapa === 'login' ? (
            <form className="space-y-4" onSubmit={onLogin}>
              <Input id="login" label="Usuário" value={usuario} onChange={(e) => setUsuario(e.target.value)} autoComplete="username" autoFocus />
              <Input id="senha" label="Senha" type="password" value={senha} onChange={(e) => setSenha(e.target.value)} autoComplete="current-password" />
              {erro && (
                <div className="flex items-center gap-2 rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">
                  <IconAlertCircle className="w-4 h-4 shrink-0" />{erro}
                </div>
              )}
              <button type="submit" disabled={enviando} className="w-full py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2">
                {enviando && <Spinner className="w-4 h-4 text-white" />}Entrar
              </button>
            </form>
          ) : (
            <form className="space-y-4" onSubmit={onDefinir}>
              <p className="text-sm text-slate-400">Sua senha é temporária. Defina uma nova para continuar.</p>
              <Input id="nova" label="Nova senha" type="password" value={novaSenha} onChange={(e) => setNovaSenha(e.target.value)} autoComplete="new-password" autoFocus />
              <Input id="confirma" label="Confirmar nova senha" type="password" value={confirma} onChange={(e) => setConfirma(e.target.value)} autoComplete="new-password" />
              {erro && (
                <div className="flex items-center gap-2 rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">
                  <IconAlertCircle className="w-4 h-4 shrink-0" />{erro}
                </div>
              )}
              <button type="submit" disabled={enviando} className="w-full py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2">
                {enviando && <Spinner className="w-4 h-4 text-white" />}Definir senha
              </button>
              <button type="button" onClick={() => { setEtapa('login'); setErro('') }} className="w-full text-xs text-slate-400 hover:text-slate-200">voltar ao login</button>
            </form>
          )}
        </div>
        <p className="text-center text-xs text-slate-400 mt-6">GestorHS · Health Safety</p>
      </div>
    </div>
  )
}
```

- [ ] **Step 6: Verificar lint + build**

Run: `npm --prefix frontend run lint` (sem erros) e `npm --prefix frontend run build` (limpo).

- [ ] **Step 7: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/auth/AuthContext.tsx frontend/src/app/pages/LoginPage.tsx frontend/src/auth/AuthContext.test.tsx
git -C /d/GitHub/GestorHS commit -m "feat(frontend): passo definir senha no login do /app"
```

---

### Task 5: Frontend `/portal` — definir senha no login

**Files:**
- Modify: `frontend/src/portal/PortalAuthContext.tsx`
- Modify: `frontend/src/portal/PortalLoginPage.tsx`
- Test: `frontend/src/portal/PortalAuthContext.test.tsx` (estender)

- [ ] **Step 1: Escrever os testes falhando** — acrescente ao FIM do describe em `frontend/src/portal/PortalAuthContext.test.tsx`:

```tsx
function SondaReset() {
  const { cliente, login, definirSenha } = usePortalAuth()
  return (
    <div>
      <span data-testid="cli2">{cliente ? (cliente.cliente_nome ?? 'sem-nome') : 'deslogado'}</span>
      <span data-testid="res2" />
      <button onClick={async () => { const r = await login('11222333000144', 'cliente1', 'prov'); document.querySelector('[data-testid=res2]')!.textContent = String(r.precisa_redefinir) }}>login</button>
      <button onClick={() => definirSenha('11222333000144', 'cliente1', 'prov', 'novasenha123')}>definir</button>
    </div>
  )
}

describe('PortalAuthProvider — reset forçado', () => {
  beforeEach(() => { localStorage.clear(); vi.restoreAllMocks() })

  it('login com precisa_redefinir não autentica', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ precisa_redefinir: true })))
    const { default: userEvent } = await import('@testing-library/user-event')
    render(<PortalAuthProvider><SondaReset /></PortalAuthProvider>)
    await userEvent.click(screen.getByText('login'))
    await waitFor(() => expect(screen.getByTestId('res2').textContent).toBe('true'))
    expect(screen.getByTestId('cli2').textContent).toBe('deslogado')
  })

  it('definirSenha guarda tokens e carrega o cliente', async () => {
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(jsonResponse({ access_token: 'a', refresh_token: 'r' }))  // definir-senha-portal
      .mockResolvedValueOnce(jsonResponse({ id: 1, login: 'cliente1', cliente: 5, cliente_nome: 'Empresa X' })))  // /portal/me
    const { default: userEvent } = await import('@testing-library/user-event')
    render(<PortalAuthProvider><SondaReset /></PortalAuthProvider>)
    await userEvent.click(screen.getByText('definir'))
    await waitFor(() => expect(screen.getByTestId('cli2').textContent).toBe('Empresa X'))
  })
})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm --prefix frontend run test -- portal/PortalAuthContext`
Expected: FAIL.

- [ ] **Step 3: Atualizar `frontend/src/portal/PortalAuthContext.tsx`** — `login` retorna `LoginResult`; adicione `definirSenha`.

Após a interface `PortalMe`/imports, adicione:
```tsx
export interface LoginResult {
  precisa_redefinir: boolean
}

interface LoginRespBody {
  precisa_redefinir?: boolean
  access_token?: string
  refresh_token?: string
}
```
Na interface `PortalAuthValue`, troque `login` e acrescente `definirSenha`:
```tsx
  login: (documento: string, login: string, senha: string) => Promise<LoginResult>
  definirSenha: (documento: string, login: string, senhaAtual: string, novaSenha: string) => Promise<void>
```
Substitua `login` e adicione `definirSenha`:
```tsx
  async function login(documento: string, loginCliente: string, senha: string): Promise<LoginResult> {
    const r = await apiJson<LoginRespBody>('/auth/login-portal', {
      method: 'POST',
      body: JSON.stringify({ documento, login: loginCliente, senha }),
    })
    if (r.precisa_redefinir) return { precisa_redefinir: true }
    setTokens({ access_token: r.access_token as string, refresh_token: r.refresh_token as string })
    const me = await portalApi.me()
    setCliente(me)
    return { precisa_redefinir: false }
  }

  async function definirSenha(documento: string, loginCliente: string, senhaAtual: string, novaSenha: string) {
    const tokens = await apiJson<Tokens>('/auth/definir-senha-portal', {
      method: 'POST',
      body: JSON.stringify({ documento, login: loginCliente, senha_atual: senhaAtual, nova_senha: novaSenha }),
    })
    setTokens(tokens)
    const me = await portalApi.me()
    setCliente(me)
  }
```
Inclua `definirSenha` no `value` do provider.

- [ ] **Step 4: Rodar e ver passar**

Run: `npm --prefix frontend run test -- portal/PortalAuthContext`
Expected: PASS.

- [ ] **Step 5: Reescrever `frontend/src/portal/PortalLoginPage.tsx`** (passo "definir"):

```tsx
import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { usePortalAuth } from './PortalAuthContext'
import { ApiError } from '../lib/api'
import { Input } from '../components/ui/Input'
import { Spinner } from '../components/ui/Spinner'
import { IconAlertCircle } from '../components/ui/icons'

export function PortalLoginPage() {
  const { login, definirSenha, cliente, loading } = usePortalAuth()
  const navigate = useNavigate()
  const [documento, setDocumento] = useState('')
  const [usuario, setUsuario] = useState('')
  const [senha, setSenha] = useState('')
  const [etapa, setEtapa] = useState<'login' | 'definir'>('login')
  const [novaSenha, setNovaSenha] = useState('')
  const [confirma, setConfirma] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  if (loading) {
    return <div className="flex h-screen items-center justify-center bg-background"><Spinner className="w-8 h-8" /></div>
  }
  if (cliente) return <Navigate to="/portal" replace />

  async function onLogin(e: FormEvent) {
    e.preventDefault()
    setErro(''); setEnviando(true)
    try {
      const r = await login(documento, usuario, senha)
      if (r.precisa_redefinir) { setNovaSenha(''); setConfirma(''); setEtapa('definir') }
      else navigate('/portal', { replace: true })
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) setErro('Credenciais inválidas.')
      else setErro('Falha ao entrar. Tente novamente.')
    } finally { setEnviando(false) }
  }

  async function onDefinir(e: FormEvent) {
    e.preventDefault()
    setErro('')
    if (novaSenha.length < 8) { setErro('A nova senha deve ter ao menos 8 caracteres.'); return }
    if (novaSenha !== confirma) { setErro('As senhas não conferem.'); return }
    setEnviando(true)
    try {
      await definirSenha(documento, usuario, senha, novaSenha)
      navigate('/portal', { replace: true })
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao definir a senha.')
    } finally { setEnviando(false) }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-primary/15 flex items-center justify-center mb-3 shadow-sm">
            <span className="text-xl font-extrabold text-primary">G</span>
          </div>
          <h1 className="text-2xl font-extrabold text-slate-100 tracking-tight">Portal do Cliente</h1>
          <p className="text-sm text-slate-500 mt-1">{etapa === 'login' ? 'Health Safety' : 'Defina sua nova senha'}</p>
        </div>
        <div className="rounded-2xl bg-background-surface border border-border shadow-sm p-6">
          {etapa === 'login' ? (
            <form className="space-y-4" onSubmit={onLogin}>
              <Input id="documento" label="CNPJ ou CPF" value={documento} onChange={(e) => setDocumento(e.target.value)} autoFocus />
              <Input id="login" label="Login" value={usuario} onChange={(e) => setUsuario(e.target.value)} autoComplete="username" />
              <Input id="senha" label="Senha" type="password" value={senha} onChange={(e) => setSenha(e.target.value)} autoComplete="current-password" />
              {erro && (
                <div className="flex items-center gap-2 rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">
                  <IconAlertCircle className="w-4 h-4 shrink-0" />{erro}
                </div>
              )}
              <button type="submit" disabled={enviando} className="w-full py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2">
                {enviando && <Spinner className="w-4 h-4 text-white" />}Entrar
              </button>
            </form>
          ) : (
            <form className="space-y-4" onSubmit={onDefinir}>
              <p className="text-sm text-slate-400">Sua senha é temporária. Defina uma nova para continuar.</p>
              <Input id="nova" label="Nova senha" type="password" value={novaSenha} onChange={(e) => setNovaSenha(e.target.value)} autoComplete="new-password" autoFocus />
              <Input id="confirma" label="Confirmar nova senha" type="password" value={confirma} onChange={(e) => setConfirma(e.target.value)} autoComplete="new-password" />
              {erro && (
                <div className="flex items-center gap-2 rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">
                  <IconAlertCircle className="w-4 h-4 shrink-0" />{erro}
                </div>
              )}
              <button type="submit" disabled={enviando} className="w-full py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2">
                {enviando && <Spinner className="w-4 h-4 text-white" />}Definir senha
              </button>
              <button type="button" onClick={() => { setEtapa('login'); setErro('') }} className="w-full text-xs text-slate-400 hover:text-slate-200">voltar ao login</button>
            </form>
          )}
        </div>
        <p className="text-center text-xs text-slate-400 mt-6">GestorHS · Health Safety</p>
      </div>
    </div>
  )
}
```

- [ ] **Step 6: Verificar lint + build**

Run: `npm --prefix frontend run lint` (sem erros) e `npm --prefix frontend run build` (limpo).

- [ ] **Step 7: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/portal/PortalAuthContext.tsx frontend/src/portal/PortalLoginPage.tsx frontend/src/portal/PortalAuthContext.test.tsx
git -C /d/GitHub/GestorHS commit -m "feat(frontend): passo definir senha no login do /portal"
```

---

### Task 6: Verificação final

**Files:** nenhum.

- [ ] **Step 1: Backend completo**

Run: `docker compose exec -T backend python -m pytest -q`
Expected: ~168 passed.

- [ ] **Step 2: Frontend completo**

Run: `npm --prefix frontend run test`
Expected: ~86 passed.

- [ ] **Step 3: Lint + build**

Run: `npm --prefix frontend run lint` (sem erros) e `npm --prefix frontend run build` (limpo).

- [ ] **Step 4: (sem commit — verificação)** Reporte os números. Se algo falhar, corrija na task correspondente.

---

## Notas para o executor
- O login agora verifica a senha ANTES de qualquer sinal — contas legadas com hash vazio dão 401 (não conseguem nem iniciar o reset até o admin dar uma temporária; portal será via 6B). O `precisa_redefinir` só aparece com a senha temporária correta.
- `LoginOut` carrega tokens opcionais; o login normal continua trazendo `access_token` (testes antigos seguem verdes). O frontend distingue por `precisa_redefinir`.
- `redefinir-senha` do admin agora SEMPRE deixa a conta temporária (`precisa_redefinir_senha=true`) — confira se algum teste fora do test_acesso assumia o contrário (a suíte inteira na Task 3 Step 5 pega isso).
- Após a Task 6, o controlador faz o E2E: cria usuário interno de teste + dá temporária via redefinir-senha; loga → "defina sua senha" → entra; idem no portal com um usuario_cliente de teste (flag + temporária); remove os usuários de teste ao fim.
```
