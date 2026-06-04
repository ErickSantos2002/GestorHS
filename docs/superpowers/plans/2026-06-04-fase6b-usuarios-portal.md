# Fase 6B (Gestão de usuários do portal) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Admin gerencia os logins do portal (`usuarios_cliente`) no detalhe do cliente — criar/editar/excluir/redefinir senha (sempre temporária).

**Architecture:** Backend — CRUD aninhado de `usuarios_cliente` (`/clientes/{id}/usuarios-portal` + `/usuarios-portal/{id}`), admin-only, senha gravada como temporária (precisa_redefinir_senha=true), nunca exposta. Frontend — `UsuariosPortalSection` no `ClienteDetailPage` (só admin), espelhando `FuncionariosSection`.

**Tech Stack:** Backend FastAPI/SQLAlchemy/pytest; Frontend React 19/TS/Vite/Vitest.

**Spec:** `docs/superpowers/specs/2026-06-04-fase6b-usuarios-portal-design.md`

**Comandos:** Backend Docker (`docker compose exec -T backend python -m pytest <args>`). Frontend `npm --prefix frontend run test|lint|build`. Git via `git -C /d/GitHub/GestorHS`. Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

**Branch:** antes da Task 1:
```bash
git -C /d/GitHub/GestorHS checkout -b feat/fase6b-usuarios-portal
```

## Convenções (já estabelecidas)
- Backend: `app/api/funcionarios.py` é o padrão (router sem prefixo, `_exige_cliente`, `require_funcao("Administrador")`, registrado em `main.py`). `UsuarioCliente` tem UNIQUE `(cliente, login)`. `hash_senha` em `app/core/security.py`. Testes pytest/SQLite; fixtures `usuario_admin` (admin/senha123), `usuario_comum` (comum/senha123, Expedição).
- Frontend: `clientes/api.ts` (`apiJson`/`apiVoid`, `funcionariosApi`); `FuncionariosSection.tsx` é o padrão (lista + modal criar/editar + excluir); `ClienteDetailPage` renderiza a seção no modo edição (linha ~183). Componentes `Table/Badge/Button/Spinner/Modal/Input`. `isAdmin`.

---

### Task 1: Backend — CRUD de usuários do portal

**Files:**
- Create: `backend/app/schemas/usuarios_cliente.py`
- Create: `backend/app/api/usuarios_cliente.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_usuarios_portal.py`

- [ ] **Step 1: Escrever os testes falhando** — `backend/tests/test_usuarios_portal.py`:

```python
def _hdr(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _cliente(db_session, cgc="11222333000144"):
    from app.models import Cliente
    c = Cliente(nome="ACME", cgc=cgc)
    db_session.add(c); db_session.commit(); db_session.refresh(c)
    return c


def test_criar_usuario_portal(client, usuario_admin, db_session):
    c = _cliente(db_session)
    h = _hdr(client, "admin", "senha123")
    r = client.post(f"/clientes/{c.id}/usuarios-portal", json={"login": "contato", "nome": "Contato", "email": "c@x.com", "senha": "temp12345"}, headers=h)
    assert r.status_code == 201
    body = r.json()
    assert body["login"] == "contato" and body["precisa_redefinir_senha"] is True
    assert "senha" not in body
    # a senha grava e o login-portal sinaliza precisa_redefinir (integração 6A)
    login = client.post("/auth/login-portal", json={"documento": "11222333000144", "login": "contato", "senha": "temp12345"}).json()
    assert login["precisa_redefinir"] is True


def test_criar_login_duplicado_409(client, usuario_admin, db_session):
    c = _cliente(db_session)
    h = _hdr(client, "admin", "senha123")
    p = {"login": "contato", "senha": "temp12345"}
    assert client.post(f"/clientes/{c.id}/usuarios-portal", json=p, headers=h).status_code == 201
    assert client.post(f"/clientes/{c.id}/usuarios-portal", json=p, headers=h).status_code == 409


def test_mesmo_login_clientes_diferentes_ok(client, usuario_admin, db_session):
    from app.models import Cliente
    c1 = _cliente(db_session)
    c2 = Cliente(nome="Beta", cgc="99888777000166"); db_session.add(c2); db_session.commit(); db_session.refresh(c2)
    h = _hdr(client, "admin", "senha123")
    assert client.post(f"/clientes/{c1.id}/usuarios-portal", json={"login": "contato", "senha": "temp12345"}, headers=h).status_code == 201
    assert client.post(f"/clientes/{c2.id}/usuarios-portal", json={"login": "contato", "senha": "temp12345"}, headers=h).status_code == 201


def test_listar_404_cliente(client, usuario_admin):
    assert client.get("/clientes/99999/usuarios-portal", headers=_hdr(client, "admin", "senha123")).status_code == 404


def test_patch_login_duplicado_409(client, usuario_admin, db_session):
    c = _cliente(db_session)
    h = _hdr(client, "admin", "senha123")
    a = client.post(f"/clientes/{c.id}/usuarios-portal", json={"login": "a", "senha": "temp12345"}, headers=h).json()
    client.post(f"/clientes/{c.id}/usuarios-portal", json={"login": "b", "senha": "temp12345"}, headers=h)
    assert client.patch(f"/usuarios-portal/{a['id']}", json={"login": "b"}, headers=h).status_code == 409
    assert client.patch(f"/usuarios-portal/{a['id']}", json={"nome": "Novo"}, headers=h).json()["nome"] == "Novo"


def test_redefinir_senha_portal(client, usuario_admin, db_session):
    from app.models import UsuarioCliente
    c = _cliente(db_session)
    h = _hdr(client, "admin", "senha123")
    uid = client.post(f"/clientes/{c.id}/usuarios-portal", json={"login": "a", "senha": "temp12345"}, headers=h).json()["id"]
    assert client.post(f"/usuarios-portal/{uid}/redefinir-senha", json={"nova_senha": "outra12345"}, headers=h).status_code == 204
    uc = db_session.get(UsuarioCliente, uid); db_session.refresh(uc)
    assert uc.precisa_redefinir_senha is True


def test_excluir_portal(client, usuario_admin, db_session):
    c = _cliente(db_session)
    h = _hdr(client, "admin", "senha123")
    uid = client.post(f"/clientes/{c.id}/usuarios-portal", json={"login": "a", "senha": "temp12345"}, headers=h).json()["id"]
    assert client.delete(f"/usuarios-portal/{uid}", headers=h).status_code == 204
    assert client.get(f"/clientes/{c.id}/usuarios-portal", headers=h).json() == []


def test_usuarios_portal_exige_admin(client, usuario_admin, usuario_comum, db_session):
    c = _cliente(db_session)
    h = _hdr(client, "comum", "senha123")
    assert client.get(f"/clientes/{c.id}/usuarios-portal", headers=h).status_code == 403
    assert client.post(f"/clientes/{c.id}/usuarios-portal", json={"login": "x", "senha": "temp12345"}, headers=h).status_code == 403
    assert client.delete("/usuarios-portal/1", headers=h).status_code == 403
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_usuarios_portal.py -q`
Expected: FAIL (404/405 — rotas não existem).

- [ ] **Step 3: Criar `backend/app/schemas/usuarios_cliente.py`**

```python
from pydantic import BaseModel, ConfigDict, Field


class UsuarioPortalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cliente: int
    login: str
    nome: str | None = None
    email: str | None = None
    precisa_redefinir_senha: bool


class UsuarioPortalCreate(BaseModel):
    login: str
    nome: str | None = None
    email: str | None = None
    senha: str = Field(min_length=8)


class UsuarioPortalUpdate(BaseModel):
    login: str | None = None
    nome: str | None = None
    email: str | None = None


class RedefinirSenhaClienteIn(BaseModel):
    nova_senha: str = Field(min_length=8)
```

- [ ] **Step 4: Criar `backend/app/api/usuarios_cliente.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Cliente, UsuarioCliente
from app.api.deps import require_funcao
from app.core.security import hash_senha
from app.schemas.usuarios_cliente import (
    UsuarioPortalOut, UsuarioPortalCreate, UsuarioPortalUpdate, RedefinirSenhaClienteIn,
)

router = APIRouter(tags=["usuarios-portal"])
ADMIN = "Administrador"


def _exige_cliente(db: Session, cliente_id: int) -> None:
    if db.query(Cliente).filter(Cliente.id == cliente_id).first() is None:
        raise HTTPException(status_code=404, detail="cliente não encontrado")


@router.get("/clientes/{cliente_id}/usuarios-portal", response_model=list[UsuarioPortalOut])
def listar(cliente_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    _exige_cliente(db, cliente_id)
    return db.query(UsuarioCliente).filter(UsuarioCliente.cliente == cliente_id).order_by(UsuarioCliente.id).all()


@router.post("/clientes/{cliente_id}/usuarios-portal", response_model=UsuarioPortalOut, status_code=status.HTTP_201_CREATED)
def criar(cliente_id: int, dados: UsuarioPortalCreate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    _exige_cliente(db, cliente_id)
    existe = (
        db.query(UsuarioCliente)
        .filter(UsuarioCliente.cliente == cliente_id, UsuarioCliente.login == dados.login)
        .first()
    )
    if existe is not None:
        raise HTTPException(status_code=409, detail="login já em uso para este cliente")
    obj = UsuarioCliente(
        cliente=cliente_id, login=dados.login, nome=dados.nome, email=dados.email,
        senha=hash_senha(dados.senha), precisa_redefinir_senha=True,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/usuarios-portal/{item_id}", response_model=UsuarioPortalOut)
def atualizar(item_id: int, dados: UsuarioPortalUpdate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(UsuarioCliente).filter(UsuarioCliente.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    campos = dados.model_dump(exclude_unset=True)
    if "login" in campos and campos["login"] != obj.login:
        dup = (
            db.query(UsuarioCliente)
            .filter(UsuarioCliente.cliente == obj.cliente, UsuarioCliente.login == campos["login"])
            .first()
        )
        if dup is not None:
            raise HTTPException(status_code=409, detail="login já em uso para este cliente")
    for chave, valor in campos.items():
        setattr(obj, chave, valor)
    db.commit()
    db.refresh(obj)
    return obj


@router.post("/usuarios-portal/{item_id}/redefinir-senha", status_code=status.HTTP_204_NO_CONTENT)
def redefinir_senha(item_id: int, dados: RedefinirSenhaClienteIn, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(UsuarioCliente).filter(UsuarioCliente.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    obj.senha = hash_senha(dados.nova_senha)
    obj.precisa_redefinir_senha = True
    db.commit()


@router.delete("/usuarios-portal/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(UsuarioCliente).filter(UsuarioCliente.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    db.delete(obj)
    db.commit()
```

- [ ] **Step 5: Registrar o router em `backend/app/main.py`**

```python
from app.api import usuarios_cliente
app.include_router(usuarios_cliente.router)
```

- [ ] **Step 6: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_usuarios_portal.py -q`
Expected: PASS (8 passed).

- [ ] **Step 7: Rodar a suíte backend inteira**

Run: `docker compose exec -T backend python -m pytest -q`
Expected: verde (~175).

- [ ] **Step 8: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/app/schemas/usuarios_cliente.py backend/app/api/usuarios_cliente.py backend/app/main.py backend/tests/test_usuarios_portal.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): CRUD de usuarios do portal (admin, senha temporaria)"
```

---

### Task 2: Frontend — `usuariosPortalApi`

**Files:**
- Modify: `frontend/src/app/clientes/api.ts`
- Test: `frontend/src/app/clientes/usuarios-portal.api.test.ts`

- [ ] **Step 1: Escrever os testes falhando** — `frontend/src/app/clientes/usuarios-portal.api.test.ts`:

```ts
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { usuariosPortalApi } from './api'
import { setTokens } from '../../lib/auth-storage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('clientes/api — usuariosPortalApi', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    setTokens({ access_token: 't', refresh_token: 'r' })
  })

  it('listarPorCliente faz GET /clientes/{id}/usuarios-portal', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse([]))
    vi.stubGlobal('fetch', f)
    await usuariosPortalApi.listarPorCliente(7)
    expect(String(f.mock.calls[0][0])).toContain('/clientes/7/usuarios-portal')
  })

  it('criar faz POST /clientes/{id}/usuarios-portal', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ id: 1 }, 201))
    vi.stubGlobal('fetch', f)
    await usuariosPortalApi.criar(7, { login: 'a', nome: null, email: null, senha: 'temp12345' })
    expect(String(f.mock.calls[0][0])).toContain('/clientes/7/usuarios-portal')
    expect(f.mock.calls[0][1]).toMatchObject({ method: 'POST' })
  })

  it('redefinirSenha faz POST /usuarios-portal/{id}/redefinir-senha', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({}, 204))
    vi.stubGlobal('fetch', f)
    await usuariosPortalApi.redefinirSenha(3, 'nova12345')
    expect(String(f.mock.calls[0][0])).toContain('/usuarios-portal/3/redefinir-senha')
    expect(String(f.mock.calls[0][1].body)).toContain('nova_senha')
  })

  it('criar propaga ApiError 409', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ detail: 'login já em uso' }, 409))
    vi.stubGlobal('fetch', f)
    await expect(usuariosPortalApi.criar(7, { login: 'a', nome: null, email: null, senha: 'temp12345' })).rejects.toMatchObject({ status: 409 })
  })
})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm --prefix frontend run test -- usuarios-portal.api`
Expected: FAIL (`usuariosPortalApi` ausente).

- [ ] **Step 3: Estender `frontend/src/app/clientes/api.ts`** — acrescente ao fim:

```ts
export interface UsuarioPortal {
  id: number
  cliente: number
  login: string
  nome: string | null
  email: string | null
  precisa_redefinir_senha: boolean
}

export interface UsuarioPortalPayload {
  login: string
  nome: string | null
  email: string | null
  senha: string
}

export const usuariosPortalApi = {
  listarPorCliente: (clienteId: number): Promise<UsuarioPortal[]> =>
    apiJson<UsuarioPortal[]>(`/clientes/${clienteId}/usuarios-portal`),
  criar: (clienteId: number, payload: UsuarioPortalPayload): Promise<UsuarioPortal> =>
    apiJson<UsuarioPortal>(`/clientes/${clienteId}/usuarios-portal`, { method: 'POST', body: JSON.stringify(payload) }),
  atualizar: (id: number, payload: { login?: string; nome?: string | null; email?: string | null }): Promise<UsuarioPortal> =>
    apiJson<UsuarioPortal>(`/usuarios-portal/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  redefinirSenha: (id: number, novaSenha: string): Promise<void> =>
    apiVoid(`/usuarios-portal/${id}/redefinir-senha`, { method: 'POST', body: JSON.stringify({ nova_senha: novaSenha }) }),
  excluir: (id: number): Promise<void> => apiVoid(`/usuarios-portal/${id}`, { method: 'DELETE' }),
}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `npm --prefix frontend run test -- usuarios-portal.api`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/app/clientes/api.ts frontend/src/app/clientes/usuarios-portal.api.test.ts
git -C /d/GitHub/GestorHS commit -m "feat(frontend): usuariosPortalApi (CRUD + redefinir senha)"
```

---

### Task 3: Frontend — `UsuariosPortalSection` no detalhe do cliente

**Files:**
- Create: `frontend/src/app/clientes/UsuariosPortalSection.tsx`
- Modify: `frontend/src/app/clientes/ClienteDetailPage.tsx`

> UI — verificada por `lint` + `build`.

- [ ] **Step 1: Criar `frontend/src/app/clientes/UsuariosPortalSection.tsx`**

```tsx
import { useEffect, useState, type FormEvent } from 'react'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Spinner } from '../../components/ui/Spinner'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { ApiError } from '../../lib/api'
import { usuariosPortalApi, type UsuarioPortal, type UsuarioPortalPayload } from './api'

const VAZIO: UsuarioPortalPayload = { login: '', nome: null, email: null, senha: '' }

export function UsuariosPortalSection({ clienteId }: { clienteId: number }) {
  const [itens, setItens] = useState<UsuarioPortal[] | null>(null)
  const [erro, setErro] = useState('')
  const [aberto, setAberto] = useState(false)
  const [editandoId, setEditandoId] = useState<number | null>(null)
  const [form, setForm] = useState<UsuarioPortalPayload>(VAZIO)
  const [erroForm, setErroForm] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [resetandoId, setResetandoId] = useState<number | null>(null)
  const [novaSenha, setNovaSenha] = useState('')

  async function carregar() {
    setErro('')
    try {
      setItens(await usuariosPortalApi.listarPorCliente(clienteId))
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao carregar')
      setItens([])
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void carregar()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clienteId])

  function set<K extends keyof UsuarioPortalPayload>(chave: K, valor: UsuarioPortalPayload[K]) {
    setForm((f) => ({ ...f, [chave]: valor }))
  }
  function abrirNovo() {
    setEditandoId(null); setForm(VAZIO); setErroForm(''); setAberto(true)
  }
  function abrirEdicao(u: UsuarioPortal) {
    setEditandoId(u.id)
    setForm({ login: u.login, nome: u.nome, email: u.email, senha: '' })
    setErroForm(''); setAberto(true)
  }

  async function salvar(e: FormEvent) {
    e.preventDefault(); setErroForm(''); setEnviando(true)
    try {
      if (editandoId !== null) await usuariosPortalApi.atualizar(editandoId, { login: form.login, nome: form.nome, email: form.email })
      else await usuariosPortalApi.criar(clienteId, form)
      setAberto(false); await carregar()
    } catch (err) {
      setErroForm(err instanceof ApiError ? err.message : 'Falha ao salvar')
    } finally {
      setEnviando(false)
    }
  }

  async function salvarReset(e: FormEvent) {
    e.preventDefault(); setErroForm(''); setEnviando(true)
    try {
      if (resetandoId !== null) await usuariosPortalApi.redefinirSenha(resetandoId, novaSenha)
      setResetandoId(null); setNovaSenha(''); await carregar()
    } catch (err) {
      setErroForm(err instanceof ApiError ? err.message : 'Falha ao redefinir')
    } finally {
      setEnviando(false)
    }
  }

  async function excluir(u: UsuarioPortal) {
    if (!window.confirm(`Excluir o acesso "${u.login}"?`)) return
    try { await usuariosPortalApi.excluir(u.id); await carregar() }
    catch (err) { setErro(err instanceof ApiError ? err.message : 'Falha ao excluir') }
  }

  return (
    <div className="rounded-2xl bg-background-surface border border-border p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-100">Usuários do portal</h2>
        <Button onClick={abrirNovo}>Novo acesso</Button>
      </div>
      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      {itens === null ? (
        <div className="flex justify-center py-8"><Spinner className="w-6 h-6" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum acesso ao portal.</p>
      ) : (
        <Table head={<><TH>Login</TH><TH>Nome</TH><TH>E-mail</TH><TH>Status</TH><TH>Ações</TH></>}>
          {itens.map((u) => (
            <tr key={u.id} className="hover:bg-background-elevated transition-colors">
              <TD>{u.login}</TD>
              <TD>{u.nome ?? '—'}</TD>
              <TD>{u.email ?? '—'}</TD>
              <TD>{u.precisa_redefinir_senha ? <Badge tone="warning">Senha temporária</Badge> : <Badge tone="primary">Ativa</Badge>}</TD>
              <TD>
                <div className="flex gap-3">
                  <button onClick={() => abrirEdicao(u)} className="text-xs text-primary hover:underline">Editar</button>
                  <button onClick={() => { setResetandoId(u.id); setNovaSenha(''); setErroForm('') }} className="text-xs text-primary hover:underline">Redefinir senha</button>
                  <button onClick={() => excluir(u)} className="text-xs text-danger hover:underline">Excluir</button>
                </div>
              </TD>
            </tr>
          ))}
        </Table>
      )}

      {aberto && (
        <Modal
          open
          onClose={() => setAberto(false)}
          title={editandoId !== null ? 'Editar acesso' : 'Novo acesso'}
          footer={
            <>
              <button type="button" onClick={() => setAberto(false)} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">Cancelar</button>
              <button type="submit" form="form-up" disabled={enviando} className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all">Salvar</button>
            </>
          }
        >
          <form id="form-up" className="space-y-4" onSubmit={salvar}>
            <Input id="up-login" label="Login" value={form.login} onChange={(e) => set('login', e.target.value)} required />
            <Input id="up-nome" label="Nome" value={form.nome ?? ''} onChange={(e) => set('nome', e.target.value || null)} />
            <Input id="up-email" label="E-mail" type="email" value={form.email ?? ''} onChange={(e) => set('email', e.target.value || null)} />
            {editandoId === null && (
              <Input id="up-senha" label="Senha temporária" type="password" value={form.senha} onChange={(e) => set('senha', e.target.value)} required />
            )}
            {erroForm && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erroForm}</div>}
          </form>
        </Modal>
      )}

      {resetandoId !== null && (
        <Modal
          open
          onClose={() => setResetandoId(null)}
          title="Redefinir senha"
          footer={
            <>
              <button type="button" onClick={() => setResetandoId(null)} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">Cancelar</button>
              <button type="submit" form="form-rs" disabled={enviando} className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all">Redefinir</button>
            </>
          }
        >
          <form id="form-rs" className="space-y-4" onSubmit={salvarReset}>
            <p className="text-sm text-slate-400">A nova senha é temporária — o cliente define a definitiva no próximo acesso.</p>
            <Input id="rs-senha" label="Nova senha temporária" type="password" value={novaSenha} onChange={(e) => setNovaSenha(e.target.value)} required />
            {erroForm && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erroForm}</div>}
          </form>
        </Modal>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Plugar no `frontend/src/app/clientes/ClienteDetailPage.tsx`** — importe e renderize após a `FuncionariosSection`.

Adicione o import (junto do import de `FuncionariosSection`):
```tsx
import { UsuariosPortalSection } from './UsuariosPortalSection'
```
Logo após a linha `{editando && <FuncionariosSection clienteId={Number(id)} podeEditar={podeEditar} />}`, adicione:
```tsx
      {editando && podeEditar && <UsuariosPortalSection clienteId={Number(id)} />}
```

- [ ] **Step 3: Verificar lint + build**

Run: `npm --prefix frontend run lint` (sem erros) e `npm --prefix frontend run build` (limpo).

- [ ] **Step 4: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/app/clientes/UsuariosPortalSection.tsx frontend/src/app/clientes/ClienteDetailPage.tsx
git -C /d/GitHub/GestorHS commit -m "feat(frontend): secao Usuarios do portal no detalhe do cliente (admin)"
```

---

### Task 4: Verificação final

**Files:** nenhum.

- [ ] **Step 1: Backend completo**

Run: `docker compose exec -T backend python -m pytest -q`
Expected: ~175 passed.

- [ ] **Step 2: Frontend completo**

Run: `npm --prefix frontend run test`
Expected: ~90 passed (86 + 4 novos).

- [ ] **Step 3: Lint + build**

Run: `npm --prefix frontend run lint` (sem erros) e `npm --prefix frontend run build` (limpo).

- [ ] **Step 4: (sem commit — verificação)** Reporte os números. Se algo falhar, corrija na task correspondente.

---

## Notas para o executor
- Todas as rotas de `usuarios-portal` são `require_funcao("Administrador")` (credenciais). A senha entra como hash + `precisa_redefinir_senha=True` (temporária) e NUNCA é retornada (`UsuarioPortalOut` não tem `senha`).
- `login` único por `(cliente, login)` — o check é explícito (409) antes do insert/patch; o mesmo login em clientes diferentes é permitido.
- A `UsuariosPortalSection` só é renderizada para admin (`editando && podeEditar` no ClienteDetailPage). No editar, a senha não é alterada (use "Redefinir senha").
- Após a Task 4, o controlador faz o E2E: no detalhe de um cliente (admin), criar um acesso com senha temporária, logar no portal com ele (cai no reset forçado da 6A), e excluir o acesso de teste ao fim.
```
