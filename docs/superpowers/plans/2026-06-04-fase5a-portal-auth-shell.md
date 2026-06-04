# Fase 5A (Portal do cliente — Auth & Shell) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fundação do portal do cliente — login multi-tenant por documento (CNPJ/CPF), contexto de auth próprio, shell e home com resumo, com isolamento de tenant.

**Architecture:** Backend — `/auth/login-portal` resolve o documento → cliente; router `/portal` (`me`/`resumo`) sempre escopado pelo `cliente` do token. Frontend — `PortalAuthProvider` independente (reusa `lib/api`/`auth-storage`), `App.tsx` reestruturado para isolar a auth do `/app` da do `/portal`, login + shell + home.

**Tech Stack:** Backend FastAPI/SQLAlchemy/pytest; Frontend React 19/TS/Vite/Vitest/react-router 7.

**Spec:** `docs/superpowers/specs/2026-06-04-fase5a-portal-auth-shell-design.md`

**Comandos:** Backend Docker (`docker compose exec -T backend python -m pytest <args>`). Frontend `npm --prefix frontend run test|lint|build`. Git via `git -C /d/GitHub/GestorHS`. Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

**Branch:** antes da Task 1:
```bash
git -C /d/GitHub/GestorHS checkout -b feat/fase5a-portal
```

## Convenções (já estabelecidas)
- Backend: `_autenticar(registro, senha)` em `auth.py` (anti-enumeração). `get_current_cliente` (deps) valida `tipo=="cliente"` + claim `cliente`. Router novo + `app.include_router` em `main.py`. Testes pytest/SQLite; fixture `cliente_portal` (conftest) cria o usuário-cliente de teste.
- Frontend: `AuthContext.tsx` é o modelo; `lib/api` (`apiJson`/`apiFetch`/`setOnUnauthorized`), `lib/auth-storage` (`getTokens`/`setTokens`/`clearTokens`, tipo `Tokens`). Componentes `Input`/`Spinner`; `cn()`. Telas por `tsc`/`lint`/`build`.

---

### Task 1: Login do portal por documento (CNPJ/CPF)

**Files:**
- Modify: `backend/app/schemas/auth.py` (`PortalLoginRequest`)
- Modify: `backend/app/api/auth.py` (`login_portal`)
- Modify: `backend/tests/conftest.py` (fixture `cliente_portal`)
- Modify: `backend/tests/test_auth.py` (testes do login-portal)

- [ ] **Step 1: Atualizar a fixture `cliente_portal` em `backend/tests/conftest.py`** — substitua a fixture atual por (passa a criar também a empresa `Cliente` com CNPJ):

```python
@pytest.fixture()
def cliente_portal(db_session):
    from app.models import Cliente
    empresa = Cliente(nome="Cliente Teste", cgc="11222333000144")
    db_session.add(empresa)
    db_session.flush()
    c = UsuarioCliente(
        cliente=empresa.id,
        nome="Cliente Teste",
        login="cliente1",
        senha=hash_senha("portal123"),
        precisa_redefinir_senha=False,
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c
```

- [ ] **Step 2: Reescrever os testes de login-portal em `backend/tests/test_auth.py`**

Substitua os testes existentes `test_login_portal_sucesso`, `test_login_portal_senha_errada_401`, `test_token_portal_nao_acessa_me_de_usuario`, `test_login_portal_cliente_errado_401` e `test_cliente_token_com_tenant_adulterado_e_negado` por estas versões (usam `documento` no lugar de `cliente`):

```python
def test_login_portal_sucesso(client, cliente_portal):
    r = client.post("/auth/login-portal", json={"documento": "11.222.333/0001-44", "login": "cliente1", "senha": "portal123"})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["token_type"] == "bearer"
    assert corpo["access_token"] and corpo["refresh_token"]


def test_login_portal_documento_sem_pontuacao(client, cliente_portal):
    r = client.post("/auth/login-portal", json={"documento": "11222333000144", "login": "cliente1", "senha": "portal123"})
    assert r.status_code == 200


def test_login_portal_senha_errada_401(client, cliente_portal):
    r = client.post("/auth/login-portal", json={"documento": "11222333000144", "login": "cliente1", "senha": "errada"})
    assert r.status_code == 401


def test_login_portal_documento_inexistente_401(client, cliente_portal):
    r = client.post("/auth/login-portal", json={"documento": "00000000000000", "login": "cliente1", "senha": "portal123"})
    assert r.status_code == 401


def test_login_portal_login_errado_401(client, cliente_portal):
    r = client.post("/auth/login-portal", json={"documento": "11222333000144", "login": "naoexiste", "senha": "portal123"})
    assert r.status_code == 401


def test_token_portal_nao_acessa_me_de_usuario(client, cliente_portal):
    tokens = client.post("/auth/login-portal", json={"documento": "11222333000144", "login": "cliente1", "senha": "portal123"}).json()
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert r.status_code == 401


def test_login_portal_emite_claim_cliente_correto(client, cliente_portal):
    from app.core.security import decodificar_token
    tok = client.post("/auth/login-portal", json={"documento": "11222333000144", "login": "cliente1", "senha": "portal123"}).json()
    assert decodificar_token(tok["access_token"]).get("cliente") == cliente_portal.cliente
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_auth.py -q`
Expected: FAIL (o schema ainda exige `cliente`, os testes mandam `documento`).

- [ ] **Step 4: Atualizar `PortalLoginRequest` em `backend/app/schemas/auth.py`**

```python
class PortalLoginRequest(BaseModel):
    documento: str
    login: str
    senha: str
```

- [ ] **Step 5: Atualizar `login_portal` em `backend/app/api/auth.py`**

Adicione `from sqlalchemy import or_` no topo e importe `Cliente` (junte ao import de modelos: `from app.models import Usuario, UsuarioCliente, Cliente`). Substitua o corpo de `login_portal`:
```python
@router.post("/login-portal", response_model=Token)
def login_portal(dados: PortalLoginRequest, db: Session = Depends(get_db)):
    doc = "".join(c for c in dados.documento if c.isdigit())
    empresa = (
        db.query(Cliente).filter(or_(Cliente.cgc == doc, Cliente.cpf == doc)).first()
        if doc else None
    )
    if empresa is None:
        _autenticar(None, dados.senha)  # timing/401 anti-enumeração (não revela se o documento existe)
    cli = (
        db.query(UsuarioCliente)
        .filter(UsuarioCliente.cliente == empresa.id, UsuarioCliente.login == dados.login)
        .first()
    )
    _autenticar(cli, dados.senha)
    return Token(
        access_token=criar_access_token(sub=str(cli.id), tipo="cliente", cliente=cli.cliente),
        refresh_token=criar_refresh_token(sub=str(cli.id), tipo="cliente", cliente=cli.cliente),
    )
```
> `_autenticar(None, ...)` levanta 401 (não retorna), então o `cli = ...` abaixo só roda quando a empresa existe.

- [ ] **Step 6: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_auth.py -q`
Expected: PASS (todos, incl. os novos do portal).

- [ ] **Step 7: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/app/schemas/auth.py backend/app/api/auth.py backend/tests/conftest.py backend/tests/test_auth.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): login do portal por documento (CNPJ/CPF)"
```

---

### Task 2: Router `/portal` (`me` + `resumo`)

**Files:**
- Create: `backend/app/schemas/portal.py`
- Create: `backend/app/api/portal.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_portal.py`

- [ ] **Step 1: Escrever os testes falhando** — `backend/tests/test_portal.py`:

```python
from datetime import date, timedelta


def _portal_headers(client):
    tok = client.post("/auth/login-portal", json={"documento": "11222333000144", "login": "cliente1", "senha": "portal123"}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def test_portal_me(client, cliente_portal):
    r = client.get("/portal/me", headers=_portal_headers(client))
    assert r.status_code == 200
    body = r.json()
    assert body["login"] == "cliente1"
    assert body["cliente"] == cliente_portal.cliente
    assert body["cliente_nome"] == "Cliente Teste"


def test_portal_me_sem_token_401(client):
    assert client.get("/portal/me").status_code == 401


def test_portal_me_token_de_usuario_401(client, usuario_admin):
    tokens = client.post("/auth/login", json={"login": "admin", "senha": "senha123"}).json()
    r = client.get("/portal/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert r.status_code == 401


def test_portal_resumo_escopado(client, cliente_portal, db_session):
    from app.models import Cliente, Equipamento, EquipamentoCliente, Ordem
    hoje = date.today()
    eq = Equipamento(descricao="Baf")
    outro = Cliente(nome="Outro")
    db_session.add_all([eq, outro]); db_session.flush()
    db_session.add_all([
        EquipamentoCliente(cliente=cliente_portal.cliente, equipamento=eq.id, prox_calibragem=hoje - timedelta(days=5), ativo=True),  # vencido
        EquipamentoCliente(cliente=cliente_portal.cliente, equipamento=eq.id, prox_calibragem=hoje + timedelta(days=200), ativo=True),  # em dia
        EquipamentoCliente(cliente=outro.id, equipamento=eq.id, prox_calibragem=hoje - timedelta(days=5), ativo=True),  # de outro cliente
        Ordem(cliente=cliente_portal.cliente, fase=5, situacao="E"),       # OS em andamento
        Ordem(cliente=cliente_portal.cliente, fase=8, situacao="F"),       # finalizada (não conta)
        Ordem(cliente=outro.id, fase=5, situacao="E"),                     # de outro cliente
    ])
    db_session.commit()
    r = client.get("/portal/resumo", headers=_portal_headers(client))
    assert r.status_code == 200
    body = r.json()
    assert body["aparelhos"] == 2
    assert body["vencidos"] == 1
    assert body["os_andamento"] == 1
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_portal.py -q`
Expected: FAIL (404 — /portal não existe).

- [ ] **Step 3: Criar `backend/app/schemas/portal.py`**

```python
from pydantic import BaseModel


class PortalMeOut(BaseModel):
    id: int
    login: str
    nome: str | None = None
    cliente: int
    cliente_nome: str | None = None


class PortalResumoOut(BaseModel):
    aparelhos: int
    vencidos: int
    os_andamento: int
```

- [ ] **Step 4: Criar `backend/app/api/portal.py`**

```python
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import UsuarioCliente, Cliente, EquipamentoCliente, Ordem
from app.api.deps import get_current_cliente
from app.schemas.portal import PortalMeOut, PortalResumoOut

router = APIRouter(prefix="/portal", tags=["portal"])
_FASES_ATIVAS = (4, 5, 6, 7)


@router.get("/me", response_model=PortalMeOut)
def me(cli: UsuarioCliente = Depends(get_current_cliente), db: Session = Depends(get_db)):
    empresa = db.query(Cliente).filter(Cliente.id == cli.cliente).first()
    return PortalMeOut(
        id=cli.id, login=cli.login, nome=cli.nome, cliente=cli.cliente,
        cliente_nome=empresa.nome if empresa else None,
    )


@router.get("/resumo", response_model=PortalResumoOut)
def resumo(cli: UsuarioCliente = Depends(get_current_cliente), db: Session = Depends(get_db)):
    hoje = date.today()
    base = db.query(EquipamentoCliente).filter(
        EquipamentoCliente.cliente == cli.cliente,
        EquipamentoCliente.ativo.is_(True),
    )
    aparelhos = base.count()
    vencidos = base.filter(EquipamentoCliente.prox_calibragem < hoje).count()
    os_andamento = (
        db.query(Ordem)
        .filter(Ordem.cliente == cli.cliente, Ordem.fase.in_(_FASES_ATIVAS))
        .count()
    )
    return PortalResumoOut(aparelhos=aparelhos, vencidos=vencidos, os_andamento=os_andamento)
```

- [ ] **Step 5: Registrar o router em `backend/app/main.py`**

```python
from app.api import portal
app.include_router(portal.router)
```

- [ ] **Step 6: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_portal.py -q`
Expected: PASS (4 passed).

- [ ] **Step 7: Rodar a suíte backend inteira**

Run: `docker compose exec -T backend python -m pytest -q`
Expected: verde (137 + Task1 (líquido +3) + Task2 (4) ≈ 144).

- [ ] **Step 8: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/app/schemas/portal.py backend/app/api/portal.py backend/app/main.py backend/tests/test_portal.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): GET /portal/me e /portal/resumo (escopados por tenant)"
```

---

### Task 3: Frontend — `portal/api.ts` + `PortalAuthProvider` + testes

**Files:**
- Create: `frontend/src/portal/api.ts`
- Create: `frontend/src/portal/PortalAuthContext.tsx`
- Create: `frontend/src/portal/PortalProtectedRoute.tsx`
- Test: `frontend/src/portal/api.test.ts`
- Test: `frontend/src/portal/PortalAuthContext.test.tsx`

- [ ] **Step 1: Escrever os testes falhando**

`frontend/src/portal/api.test.ts`:
```ts
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { portalApi } from './api'
import { setTokens } from '../lib/auth-storage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('portal/api', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    setTokens({ access_token: 't', refresh_token: 'r' })
  })

  it('me bate em /portal/me', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ id: 1, login: 'x', cliente: 5 }))
    vi.stubGlobal('fetch', f)
    await portalApi.me()
    expect(String(f.mock.calls[0][0])).toContain('/portal/me')
  })

  it('resumo bate em /portal/resumo', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ aparelhos: 0, vencidos: 0, os_andamento: 0 }))
    vi.stubGlobal('fetch', f)
    await portalApi.resumo()
    expect(String(f.mock.calls[0][0])).toContain('/portal/resumo')
  })

  it('propaga ApiError', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ detail: 'x' }, 401))
    vi.stubGlobal('fetch', f)
    await expect(portalApi.me()).rejects.toMatchObject({ status: 401 })
  })
})
```
`frontend/src/portal/PortalAuthContext.test.tsx`:
```tsx
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { PortalAuthProvider, usePortalAuth } from './PortalAuthContext'
import { getTokens, setTokens } from '../lib/auth-storage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

function Sonda() {
  const { cliente, loading, login, logout } = usePortalAuth()
  return (
    <div>
      <span data-testid="estado">{loading ? 'loading' : cliente ? cliente.cliente_nome ?? 'sem-nome' : 'deslogado'}</span>
      <button onClick={() => void login('11222333000144', 'cliente1', 'portal123')}>entrar</button>
      <button onClick={() => logout()}>sair</button>
    </div>
  )
}

describe('PortalAuthProvider', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('sem token, fica deslogado', async () => {
    render(<PortalAuthProvider><Sonda /></PortalAuthProvider>)
    await waitFor(() => expect(screen.getByTestId('estado').textContent).toBe('deslogado'))
  })

  it('login guarda token e carrega o cliente; logout limpa', async () => {
    const f = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ access_token: 'a', refresh_token: 'r' }))  // login-portal
      .mockResolvedValueOnce(jsonResponse({ id: 1, login: 'cliente1', cliente: 5, cliente_nome: 'Empresa X' }))  // /portal/me
    vi.stubGlobal('fetch', f)
    const { default: userEvent } = await import('@testing-library/user-event')
    render(<PortalAuthProvider><Sonda /></PortalAuthProvider>)
    await waitFor(() => expect(screen.getByTestId('estado').textContent).toBe('deslogado'))
    await userEvent.click(screen.getByText('entrar'))
    await waitFor(() => expect(screen.getByTestId('estado').textContent).toBe('Empresa X'))
    expect(getTokens()).not.toBeNull()
    await userEvent.click(screen.getByText('sair'))
    await waitFor(() => expect(screen.getByTestId('estado').textContent).toBe('deslogado'))
    expect(getTokens()).toBeNull()
  })
})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm --prefix frontend run test -- portal/`
Expected: FAIL (módulos ausentes).

- [ ] **Step 3: Criar `frontend/src/portal/api.ts`**

```ts
import { apiJson } from '../lib/api'

export interface PortalMe {
  id: number
  login: string
  nome: string | null
  cliente: number
  cliente_nome: string | null
}

export interface PortalResumo {
  aparelhos: number
  vencidos: number
  os_andamento: number
}

export const portalApi = {
  me: (): Promise<PortalMe> => apiJson<PortalMe>('/portal/me'),
  resumo: (): Promise<PortalResumo> => apiJson<PortalResumo>('/portal/resumo'),
}
```

- [ ] **Step 4: Criar `frontend/src/portal/PortalAuthContext.tsx`**

```tsx
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { apiJson, setOnUnauthorized } from '../lib/api'
import { clearTokens, getTokens, setTokens, type Tokens } from '../lib/auth-storage'
import { portalApi, type PortalMe } from './api'

interface PortalAuthValue {
  cliente: PortalMe | null
  loading: boolean
  login: (documento: string, login: string, senha: string) => Promise<void>
  logout: () => void
}

const PortalAuthContext = createContext<PortalAuthValue | null>(null)

export function PortalAuthProvider({ children }: { children: ReactNode }) {
  const [cliente, setCliente] = useState<PortalMe | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setOnUnauthorized(() => setCliente(null))
    return () => setOnUnauthorized(null)
  }, [])

  useEffect(() => {
    let ativo = true
    async function hidratar() {
      if (!getTokens()) {
        if (ativo) setLoading(false)
        return
      }
      try {
        const me = await portalApi.me()
        if (ativo) setCliente(me)
      } catch {
        clearTokens()
        if (ativo) setCliente(null)
      } finally {
        if (ativo) setLoading(false)
      }
    }
    void hidratar()
    return () => {
      ativo = false
    }
  }, [])

  async function login(documento: string, loginCliente: string, senha: string) {
    const tokens = await apiJson<Tokens>('/auth/login-portal', {
      method: 'POST',
      body: JSON.stringify({ documento, login: loginCliente, senha }),
    })
    setTokens(tokens)
    const me = await portalApi.me()
    setCliente(me)
  }

  function logout() {
    clearTokens()
    setCliente(null)
  }

  return <PortalAuthContext.Provider value={{ cliente, loading, login, logout }}>{children}</PortalAuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function usePortalAuth(): PortalAuthValue {
  const ctx = useContext(PortalAuthContext)
  if (!ctx) throw new Error('usePortalAuth deve ser usado dentro de <PortalAuthProvider>')
  return ctx
}
```

- [ ] **Step 5: Criar `frontend/src/portal/PortalProtectedRoute.tsx`**

```tsx
import { type ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { usePortalAuth } from './PortalAuthContext'
import { Spinner } from '../components/ui/Spinner'

export function PortalProtectedRoute({ children }: { children: ReactNode }) {
  const { cliente, loading } = usePortalAuth()
  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <Spinner className="w-8 h-8" />
      </div>
    )
  }
  if (!cliente) return <Navigate to="/portal/login" replace />
  return <>{children}</>
}
```

- [ ] **Step 6: Rodar e ver passar**

Run: `npm --prefix frontend run test -- portal/`
Expected: PASS (5 passed).

- [ ] **Step 7: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/portal/api.ts frontend/src/portal/PortalAuthContext.tsx frontend/src/portal/PortalProtectedRoute.tsx frontend/src/portal/api.test.ts frontend/src/portal/PortalAuthContext.test.tsx
git -C /d/GitHub/GestorHS commit -m "feat(frontend): PortalAuthProvider + portalApi + rota protegida do portal"
```

---

### Task 4: Login + shell + home do portal + reestruturação do App.tsx

**Files:**
- Create: `frontend/src/portal/PortalLoginPage.tsx`
- Create: `frontend/src/portal/PortalLayout.tsx`
- Create: `frontend/src/portal/PortalHomePage.tsx`
- Create: `frontend/src/portal/EmBrevePage.tsx`
- Modify: `frontend/src/portal/routes.tsx`
- Modify: `frontend/src/App.tsx`

> UI — verificada por `lint` + `build`.

- [ ] **Step 1: Criar `frontend/src/portal/PortalLoginPage.tsx`**

```tsx
import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { usePortalAuth } from './PortalAuthContext'
import { ApiError } from '../lib/api'
import { Input } from '../components/ui/Input'
import { Spinner } from '../components/ui/Spinner'
import { IconAlertCircle } from '../components/ui/icons'

export function PortalLoginPage() {
  const { login, cliente, loading } = usePortalAuth()
  const navigate = useNavigate()
  const [documento, setDocumento] = useState('')
  const [usuario, setUsuario] = useState('')
  const [senha, setSenha] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  if (loading) {
    return <div className="flex h-screen items-center justify-center bg-background"><Spinner className="w-8 h-8" /></div>
  }
  if (cliente) return <Navigate to="/portal" replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setErro('')
    setEnviando(true)
    try {
      await login(documento, usuario, senha)
      navigate('/portal', { replace: true })
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) setErro('Conta bloqueada — contate a Health Safety.')
      else if (err instanceof ApiError && err.status === 401) setErro('Credenciais inválidas.')
      else setErro('Falha ao entrar. Tente novamente.')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-primary/15 flex items-center justify-center mb-3 shadow-sm">
            <span className="text-xl font-extrabold text-primary">G</span>
          </div>
          <h1 className="text-2xl font-extrabold text-slate-100 tracking-tight">Portal do Cliente</h1>
          <p className="text-sm text-slate-500 mt-1">Health Safety</p>
        </div>
        <div className="rounded-2xl bg-background-surface border border-border shadow-sm p-6">
          <form className="space-y-4" onSubmit={onSubmit}>
            <Input id="documento" label="CNPJ ou CPF" value={documento} onChange={(e) => setDocumento(e.target.value)} autoFocus />
            <Input id="login" label="Login" value={usuario} onChange={(e) => setUsuario(e.target.value)} autoComplete="username" />
            <Input id="senha" label="Senha" type="password" value={senha} onChange={(e) => setSenha(e.target.value)} autoComplete="current-password" />
            {erro && (
              <div className="flex items-center gap-2 rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">
                <IconAlertCircle className="w-4 h-4 shrink-0" />
                {erro}
              </div>
            )}
            <button type="submit" disabled={enviando} className="w-full py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2">
              {enviando && <Spinner className="w-4 h-4 text-white" />}
              Entrar
            </button>
          </form>
        </div>
        <p className="text-center text-xs text-slate-400 mt-6">GestorHS · Health Safety</p>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Criar `frontend/src/portal/PortalLayout.tsx`**

```tsx
import { type ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { cn } from '../lib/utils'
import { usePortalAuth } from './PortalAuthContext'

const NAV = [
  { label: 'Início', to: '/portal' },
  { label: 'Minha frota', to: '/portal/frota' },
  { label: 'Certificados', to: '/portal/certificados' },
  { label: 'Minhas OS', to: '/portal/os' },
]

export function PortalLayout({ children }: { children: ReactNode }) {
  const { cliente, logout } = usePortalAuth()
  const location = useLocation()
  return (
    <div className="min-h-screen bg-background">
      <header className="h-16 border-b border-border bg-background-sidebar flex items-center justify-between px-4 md:px-6">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-primary/15 flex items-center justify-center shrink-0">
            <span className="text-sm font-bold text-primary">G</span>
          </div>
          <span className="font-bold text-slate-100 tracking-tight truncate max-w-[40vw]">{cliente?.cliente_nome ?? 'Portal'}</span>
        </div>
        <button onClick={logout} className="text-sm text-slate-400 hover:text-slate-100 transition-colors">Sair</button>
      </header>
      <nav className="border-b border-border bg-background-surface px-2 md:px-6 flex gap-1 overflow-x-auto">
        {NAV.map((item) => {
          const active = item.to === '/portal' ? location.pathname === '/portal' : location.pathname.startsWith(item.to)
          return (
            <Link key={item.to} to={item.to} className={cn('px-3 py-3 text-sm font-medium whitespace-nowrap border-b-2 transition-colors',
              active ? 'border-primary text-primary' : 'border-transparent text-slate-400 hover:text-slate-200')}>
              {item.label}
            </Link>
          )
        })}
      </nav>
      <main>{children}</main>
    </div>
  )
}
```

- [ ] **Step 3: Criar `frontend/src/portal/EmBrevePage.tsx`**

```tsx
export function EmBrevePage() {
  return (
    <div className="px-4 md:px-6 py-10">
      <p className="text-sm text-slate-500">Disponível em breve.</p>
    </div>
  )
}
```

- [ ] **Step 4: Criar `frontend/src/portal/PortalHomePage.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { Spinner } from '../components/ui/Spinner'
import { ApiError } from '../lib/api'
import { usePortalAuth } from './PortalAuthContext'
import { portalApi, type PortalResumo } from './api'

function Cartao({ titulo, valor, destaque }: { titulo: string; valor: number; destaque?: boolean }) {
  return (
    <div className="rounded-2xl bg-background-surface border border-border p-5">
      <p className="text-xs text-slate-500 uppercase tracking-wide">{titulo}</p>
      <p className={destaque ? 'text-3xl font-extrabold text-danger mt-1' : 'text-3xl font-extrabold text-slate-100 mt-1'}>{valor}</p>
    </div>
  )
}

export function PortalHomePage() {
  const { cliente } = usePortalAuth()
  const [resumo, setResumo] = useState<PortalResumo | null>(null)
  const [erro, setErro] = useState('')

  useEffect(() => {
    let ativo = true
    portalApi.resumo()
      .then((r) => { if (ativo) setResumo(r) })
      .catch((e) => { if (ativo) setErro(e instanceof ApiError ? e.message : 'Falha ao carregar') })
    return () => { ativo = false }
  }, [])

  return (
    <div className="px-4 md:px-6 py-6 space-y-6">
      <h1 className="text-2xl font-extrabold text-slate-100">Olá, {cliente?.cliente_nome ?? 'cliente'}</h1>
      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      {resumo === null && !erro ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : resumo ? (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 max-w-2xl">
          <Cartao titulo="Aparelhos" valor={resumo.aparelhos} />
          <Cartao titulo="Vencidos" valor={resumo.vencidos} destaque={resumo.vencidos > 0} />
          <Cartao titulo="OS em andamento" valor={resumo.os_andamento} />
        </div>
      ) : null}
    </div>
  )
}
```

- [ ] **Step 5: Reescrever `frontend/src/portal/routes.tsx`**

```tsx
import { Routes, Route, Navigate } from 'react-router-dom'
import { PortalAuthProvider } from './PortalAuthContext'
import { PortalProtectedRoute } from './PortalProtectedRoute'
import { PortalLoginPage } from './PortalLoginPage'
import { PortalLayout } from './PortalLayout'
import { PortalHomePage } from './PortalHomePage'
import { EmBrevePage } from './EmBrevePage'

export default function PortalRoutes() {
  return (
    <PortalAuthProvider>
      <Routes>
        <Route path="login" element={<PortalLoginPage />} />
        <Route
          path="*"
          element={
            <PortalProtectedRoute>
              <PortalLayout>
                <Routes>
                  <Route index element={<PortalHomePage />} />
                  <Route path="frota" element={<EmBrevePage />} />
                  <Route path="certificados" element={<EmBrevePage />} />
                  <Route path="os" element={<EmBrevePage />} />
                  <Route path="*" element={<Navigate to="/portal" replace />} />
                </Routes>
              </PortalLayout>
            </PortalProtectedRoute>
          }
        />
      </Routes>
    </PortalAuthProvider>
  )
}
```

- [ ] **Step 6: Reestruturar `frontend/src/App.tsx`** — `AuthProvider` deixa de envolver o portal (senão o `/auth/me` limparia o token do cliente). Substitua o conteúdo por:

```tsx
import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { LoginPage } from './app/pages/LoginPage'
import { Spinner } from './components/ui/Spinner'

const AppRoutes = lazy(() => import('./app/routes'))
const PortalRoutes = lazy(() => import('./portal/routes'))

function FullScreenSpinner() {
  return (
    <div className="flex h-screen items-center justify-center bg-background">
      <Spinner className="w-8 h-8" />
    </div>
  )
}

function AppAuthLayout() {
  return (
    <AuthProvider>
      <Outlet />
    </AuthProvider>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<FullScreenSpinner />}>
        <Routes>
          <Route path="/" element={<Navigate to="/app" replace />} />
          <Route element={<AppAuthLayout />}>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/app/*" element={<ProtectedRoute><AppRoutes /></ProtectedRoute>} />
          </Route>
          <Route path="/portal/*" element={<PortalRoutes />} />
          <Route path="*" element={<Navigate to="/app" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}
```

- [ ] **Step 7: Verificar lint + build**

Run: `npm --prefix frontend run lint`
Expected: sem erros.
Run: `npm --prefix frontend run build`
Expected: limpo.

- [ ] **Step 8: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/portal/PortalLoginPage.tsx frontend/src/portal/PortalLayout.tsx frontend/src/portal/PortalHomePage.tsx frontend/src/portal/EmBrevePage.tsx frontend/src/portal/routes.tsx frontend/src/App.tsx
git -C /d/GitHub/GestorHS commit -m "feat(frontend): login, shell e home do portal + isola auth /app e /portal no App"
```

---

### Task 5: Verificação final

**Files:** nenhum.

- [ ] **Step 1: Backend completo**

Run: `docker compose exec -T backend python -m pytest -q`
Expected: ~144 passed.

- [ ] **Step 2: Frontend completo**

Run: `npm --prefix frontend run test`
Expected: ~74 passed (69 + 5 do portal).

- [ ] **Step 3: Lint + build**

Run: `npm --prefix frontend run lint` (sem erros) e `npm --prefix frontend run build` (limpo).

- [ ] **Step 4: (sem commit — verificação)** Reporte os números. Se algo falhar, corrija na task correspondente.

---

## Notas para o executor
- `App.tsx` foi reestruturado de propósito: a `AuthProvider` do `/app` NÃO pode envolver o `/portal`, senão sua hidratação via `/auth/me` (401 para token de cliente) limparia o token do portal. Cada árvore tem seu provider; o `setOnUnauthorized` global fica com a árvore montada (só uma por vez via lazy).
- Toda rota de `/portal/*` no backend usa `get_current_cliente` e filtra pelo `cliente` do token — nunca por parâmetro (isolamento).
- O login resolve o documento por dígitos (aceita CNPJ/CPF com ou sem pontuação) contra `cgc`/`cpf`; documento inexistente cai no mesmo 401 anti-enumeração.
- Após a Task 5, o controlador faz o E2E: cria um `UsuarioCliente` de teste num cliente real com CNPJ conhecido (`docker compose exec`), loga em `/portal/login` e confere a home/contadores; depois remove o usuário de teste se desejar.
```
