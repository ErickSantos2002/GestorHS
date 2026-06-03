# Fase 4 (Alertas & Cobrança) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Worklist priorizada de cobrança (clientes com aparelhos vencidos/vencendo, agrupada e ordenada por urgência) + registrar contato.

**Architecture:** Backend — router `alertas` com `GET /alertas` (agregação SQL por cliente sobre `equipamentos_cliente` ativos) e `POST /alertas/{cliente_id}/contato` (grava `ult_aviso` em lote). Frontend — página `CobrancaPage` que lista, busca, oculta recém-contatados, faz drill-down para a Frota e registra contato (Comercial/Admin).

**Tech Stack:** Backend FastAPI/SQLAlchemy/pytest; Frontend React 19/TS/Vite/Vitest.

**Spec:** `docs/superpowers/specs/2026-06-03-fase4-alertas-cobranca-design.md`

**Comandos:** Backend Docker (`docker compose exec -T backend python -m pytest <args>`). Frontend `npm --prefix frontend run test|lint|build`. Git via `git -C /d/GitHub/GestorHS`. Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

**Branch:** antes da Task 1:
```bash
git -C /d/GitHub/GestorHS checkout -b feat/fase4-alertas-cobranca
```

## Convenções (já estabelecidas)
- Backend: router em `app/api/` + `app.include_router` em `main.py`; `get_current_usuario` (read) e `require_funcao(*descricoes)` (write). `agora()` em `app/api/ordens_acoes.py` (`datetime.now(timezone.utc)`). Modelos `EquipamentoCliente`/`Cliente` já existem. Testes pytest/SQLite; fixtures `usuario_admin`, `usuario_comum` (Expedição), `usuario_lab`, `usuario_comercial` (Comercial Pós-Vendas); helper local `_headers`.
- Frontend: módulo `app/<dominio>/api.ts` com `apiJson`; páginas no padrão lista (guarda `ativo`, paginação `offset`/`limit=25`); `useAuth`/roles; nav em `Sidebar.tsx`; rotas em `app/routes.tsx`. Lint `react-hooks/set-state-in-effect`: disable só na 1ª chamada de setState síncrona no efeito.

---

### Task 1: `GET /alertas` (worklist agregada) + schemas

**Files:**
- Create: `backend/app/schemas/alertas.py`
- Create: `backend/app/api/alertas.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_alertas.py`

- [ ] **Step 1: Escrever os testes falhando** — `backend/tests/test_alertas.py`:

```python
from datetime import date, timedelta


def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _setup(db_session):
    from app.models import Cliente, Equipamento, EquipamentoCliente
    hoje = date.today()
    cliA = Cliente(nome="Alfa Ltda")
    cliB = Cliente(nome="Beta SA")
    cliC = Cliente(nome="Gama ME")
    eq = Equipamento(descricao="Bafômetro")
    db_session.add_all([cliA, cliB, cliC, eq])
    db_session.flush()

    def ec(cli, prox, ativo=True):
        return EquipamentoCliente(cliente=cli, equipamento=eq.id, prox_calibragem=prox, ativo=ativo)

    db_session.add_all([
        ec(cliA.id, hoje - timedelta(days=10)),            # vencido
        ec(cliA.id, hoje - timedelta(days=5)),             # vencido
        ec(cliA.id, hoje + timedelta(days=30)),            # vencendo
        ec(cliA.id, hoje + timedelta(days=200)),           # em_dia (ignorado)
        ec(cliA.id, hoje - timedelta(days=1), ativo=False),# inativo (ignorado)
        ec(cliB.id, hoje - timedelta(days=2)),             # vencido
        ec(cliC.id, hoje + timedelta(days=300)),           # em_dia só -> C não aparece
    ])
    db_session.commit()
    return {"A": cliA.id, "B": cliB.id, "C": cliC.id}


def test_lista_agrupa_e_ordena(client, usuario_comum, db_session):
    ids = _setup(db_session)
    r = client.get("/alertas", headers=_headers(client, "comum", "senha123"))
    assert r.status_code == 200
    body = r.json()
    clientes = [i["cliente"] for i in body["items"]]
    assert ids["C"] not in clientes
    assert clientes[0] == ids["A"] and clientes[1] == ids["B"]  # A (2 vencidos) antes de B
    a = body["items"][0]
    assert a["vencidos"] == 2 and a["vencendo"] == 1
    assert body["total"] == 2


def test_busca_por_cliente(client, usuario_comum, db_session):
    ids = _setup(db_session)
    r = client.get("/alertas?q=Beta", headers=_headers(client, "comum", "senha123"))
    assert r.json()["total"] == 1 and r.json()["items"][0]["cliente"] == ids["B"]


def test_ocultar_recentes(client, usuario_comum, db_session):
    from app.models import EquipamentoCliente
    from app.api.ordens_acoes import agora
    ids = _setup(db_session)
    for ec in db_session.query(EquipamentoCliente).filter(EquipamentoCliente.cliente == ids["A"]).all():
        ec.ult_aviso = agora()
    db_session.commit()
    r = client.get("/alertas?ocultar_recentes=true", headers=_headers(client, "comum", "senha123"))
    clientes = [i["cliente"] for i in r.json()["items"]]
    assert ids["A"] not in clientes
    assert ids["B"] in clientes
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_alertas.py -q`
Expected: FAIL (404 — rota /alertas não existe).

- [ ] **Step 3: Criar `backend/app/schemas/alertas.py`**

```python
from datetime import date, datetime
from pydantic import BaseModel


class AlertaItem(BaseModel):
    cliente: int
    cliente_nome: str | None = None
    vencidos: int
    vencendo: int
    prox_antiga: date | None = None
    ult_contato: datetime | None = None


class AlertaPage(BaseModel):
    items: list[AlertaItem]
    total: int


class ContatoOut(BaseModel):
    cliente: int
    atualizados: int
    ult_contato: datetime | None = None
```

- [ ] **Step 4: Criar `backend/app/api/alertas.py`**

```python
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, case, or_
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, EquipamentoCliente, Cliente
from app.api.deps import get_current_usuario
from app.schemas.alertas import AlertaItem, AlertaPage

router = APIRouter(prefix="/alertas", tags=["alertas"])


@router.get("", response_model=AlertaPage)
def listar(
    q: str | None = None,
    ocultar_recentes: bool = False,
    offset: int = 0,
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_usuario),
):
    hoje = date.today()
    limite = hoje + timedelta(days=90)
    vencidos = func.sum(case((EquipamentoCliente.prox_calibragem < hoje, 1), else_=0)).label("vencidos")
    vencendo = func.sum(case((EquipamentoCliente.prox_calibragem >= hoje, 1), else_=0)).label("vencendo")
    prox_antiga = func.min(EquipamentoCliente.prox_calibragem).label("prox_antiga")
    ult_contato = func.max(EquipamentoCliente.ult_aviso).label("ult_contato")

    base = (
        db.query(
            EquipamentoCliente.cliente.label("cliente"),
            Cliente.nome.label("cliente_nome"),
            vencidos, vencendo, prox_antiga, ult_contato,
        )
        .join(Cliente, EquipamentoCliente.cliente == Cliente.id)
        .filter(
            EquipamentoCliente.ativo.is_(True),
            EquipamentoCliente.prox_calibragem.isnot(None),
            EquipamentoCliente.prox_calibragem <= limite,
        )
        .group_by(EquipamentoCliente.cliente, Cliente.nome)
    )
    if q:
        base = base.filter(Cliente.nome.ilike(f"%{q}%"))
    if ocultar_recentes:
        corte = datetime.now(timezone.utc) - timedelta(days=30)
        base = base.having(or_(
            func.max(EquipamentoCliente.ult_aviso).is_(None),
            func.max(EquipamentoCliente.ult_aviso) < corte,
        ))
    base = base.order_by(vencidos.desc(), prox_antiga.asc())

    linhas = base.all()
    total = len(linhas)
    pagina = linhas[offset: offset + limit]
    items = [
        AlertaItem(
            cliente=r.cliente, cliente_nome=r.cliente_nome,
            vencidos=int(r.vencidos or 0), vencendo=int(r.vencendo or 0),
            prox_antiga=r.prox_antiga, ult_contato=r.ult_contato,
        )
        for r in pagina
    ]
    return AlertaPage(items=items, total=total)
```

- [ ] **Step 5: Registrar o router em `backend/app/main.py`**

```python
from app.api import alertas
app.include_router(alertas.router)
```

- [ ] **Step 6: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_alertas.py -q`
Expected: PASS (3 passed).

- [ ] **Step 7: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/app/schemas/alertas.py backend/app/api/alertas.py backend/app/main.py backend/tests/test_alertas.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): GET /alertas (worklist de cobranca agregada por cliente)"
```

---

### Task 2: `POST /alertas/{cliente_id}/contato`

**Files:**
- Modify: `backend/app/api/alertas.py`
- Test: `backend/tests/test_alertas.py` (estender)

- [ ] **Step 1: Escrever os testes falhando** — acrescente ao FIM de `backend/tests/test_alertas.py` (reusa `_setup`/`_headers`):

```python
def test_registrar_contato_comercial(client, usuario_comercial, db_session):
    ids = _setup(db_session)
    r = client.post(f"/alertas/{ids['A']}/contato", headers=_headers(client, "comercial", "senha123"))
    assert r.status_code == 200
    assert r.json()["atualizados"] == 3   # 2 vencidos + 1 vencendo (não em_dia/inativo)
    assert r.json()["ult_contato"] is not None


def test_registrar_contato_admin(client, usuario_admin, db_session):
    ids = _setup(db_session)
    r = client.post(f"/alertas/{ids['B']}/contato", headers=_headers(client, "admin", "senha123"))
    assert r.json()["atualizados"] == 1


def test_registrar_contato_403(client, usuario_lab, db_session):
    ids = _setup(db_session)
    r = client.post(f"/alertas/{ids['A']}/contato", headers=_headers(client, "lab", "senha123"))
    assert r.status_code == 403


def test_registrar_contato_404(client, usuario_comercial, db_session):
    r = client.post("/alertas/99999/contato", headers=_headers(client, "comercial", "senha123"))
    assert r.status_code == 404


def test_contato_reflete_em_ult_contato(client, usuario_comercial, db_session):
    ids = _setup(db_session)
    h = _headers(client, "comercial", "senha123")
    client.post(f"/alertas/{ids['A']}/contato", headers=h)
    item = next(i for i in client.get("/alertas", headers=h).json()["items"] if i["cliente"] == ids["A"])
    assert item["ult_contato"] is not None
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_alertas.py -q`
Expected: FAIL (405/404 — POST não existe).

- [ ] **Step 3: Adicionar o endpoint em `backend/app/api/alertas.py`**

Atualize os imports (acrescente `HTTPException`, `require_funcao`, `agora`, `ContatoOut`):
```python
from fastapi import APIRouter, Depends, Query, HTTPException
from app.api.deps import get_current_usuario, require_funcao
from app.api.ordens_acoes import agora
from app.schemas.alertas import AlertaItem, AlertaPage, ContatoOut
```
E adicione o endpoint:
```python
@router.post("/{cliente_id}/contato", response_model=ContatoOut)
def registrar_contato(
    cliente_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_funcao("Comercial Pós-Vendas", "Administrador")),
):
    if db.query(Cliente).filter(Cliente.id == cliente_id).first() is None:
        raise HTTPException(status_code=404, detail="cliente não encontrado")
    hoje = date.today()
    limite = hoje + timedelta(days=90)
    agora_dt = agora()
    elegiveis = (
        db.query(EquipamentoCliente)
        .filter(
            EquipamentoCliente.cliente == cliente_id,
            EquipamentoCliente.ativo.is_(True),
            EquipamentoCliente.prox_calibragem.isnot(None),
            EquipamentoCliente.prox_calibragem <= limite,
        )
        .all()
    )
    for ec in elegiveis:
        ec.ult_aviso = agora_dt
    db.commit()
    n = len(elegiveis)
    return ContatoOut(cliente=cliente_id, atualizados=n, ult_contato=agora_dt if n else None)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_alertas.py -q`
Expected: PASS (8 passed).

- [ ] **Step 5: Rodar a suíte backend inteira**

Run: `docker compose exec -T backend python -m pytest -q`
Expected: verde (129 + 8 = 137).

- [ ] **Step 6: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/app/api/alertas.py backend/tests/test_alertas.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): POST /alertas/{cliente}/contato (registrar contato em lote)"
```

---

### Task 3: Frontend — API de alertas + permissão

**Files:**
- Create: `frontend/src/app/alertas/api.ts`
- Modify: `frontend/src/auth/roles.ts`
- Test: `frontend/src/app/alertas/api.test.ts`
- Test: `frontend/src/auth/roles.test.ts` (estender)

- [ ] **Step 1: Escrever os testes falhando**

`frontend/src/app/alertas/api.test.ts`:
```ts
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { alertasApi } from './api'
import { setTokens } from '../../lib/auth-storage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('alertas/api', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    setTokens({ access_token: 't', refresh_token: 'r' })
  })

  it('listar monta a query (q/ocultar_recentes/offset/limit)', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ items: [], total: 0 }))
    vi.stubGlobal('fetch', f)
    await alertasApi.listar({ q: 'beta', ocultar_recentes: true, offset: 25, limit: 25 })
    const url = String(f.mock.calls[0][0])
    expect(url).toContain('/alertas?')
    expect(url).toContain('q=beta')
    expect(url).toContain('ocultar_recentes=true')
    expect(url).toContain('offset=25')
  })

  it('listar omite ocultar_recentes quando false', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ items: [], total: 0 }))
    vi.stubGlobal('fetch', f)
    await alertasApi.listar({})
    expect(String(f.mock.calls[0][0])).not.toContain('ocultar_recentes')
  })

  it('registrarContato faz POST /alertas/{id}/contato', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ cliente: 5, atualizados: 2, ult_contato: null }))
    vi.stubGlobal('fetch', f)
    await alertasApi.registrarContato(5)
    expect(String(f.mock.calls[0][0])).toContain('/alertas/5/contato')
    expect(f.mock.calls[0][1]).toMatchObject({ method: 'POST' })
  })

  it('propaga ApiError', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ detail: 'x' }, 403))
    vi.stubGlobal('fetch', f)
    await expect(alertasApi.registrarContato(5)).rejects.toMatchObject({ status: 403 })
  })
})
```
Em `frontend/src/auth/roles.test.ts`, acrescente ao fim do describe (reusa o helper `u()` já presente no arquivo; se não houver, crie `function u(funcao){ return { id:1, nome:'x', login:'x', funcao } as User }`):
```ts
  it('podeRegistrarContato: admin e Comercial sim, outros não', () => {
    expect(podeRegistrarContato(u('Administrador'))).toBe(true)
    expect(podeRegistrarContato(u('Comercial Pós-Vendas'))).toBe(true)
    expect(podeRegistrarContato(u('Laboratório'))).toBe(false)
    expect(podeRegistrarContato(null)).toBe(false)
  })
```
E adicione `podeRegistrarContato` ao import no topo do `roles.test.ts` (junto de `podeAbrirOS`).

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm --prefix frontend run test -- alertas/api auth/roles`
Expected: FAIL (módulo/função ausentes).

- [ ] **Step 3: Criar `frontend/src/app/alertas/api.ts`**

```ts
import { apiJson } from '../../lib/api'

export function formatData(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return isNaN(d.getTime()) ? '—' : d.toLocaleDateString('pt-BR')
}

export interface AlertaItem {
  cliente: number
  cliente_nome: string | null
  vencidos: number
  vencendo: number
  prox_antiga: string | null
  ult_contato: string | null
}

export interface AlertaPage {
  items: AlertaItem[]
  total: number
}

export interface ContatoOut {
  cliente: number
  atualizados: number
  ult_contato: string | null
}

export interface AlertasParams {
  q?: string
  ocultar_recentes?: boolean
  offset?: number
  limit?: number
}

export const alertasApi = {
  listar: (params: AlertasParams = {}): Promise<AlertaPage> => {
    const sp = new URLSearchParams()
    if (params.q) sp.set('q', params.q)
    if (params.ocultar_recentes) sp.set('ocultar_recentes', 'true')
    sp.set('offset', String(params.offset ?? 0))
    sp.set('limit', String(params.limit ?? 25))
    return apiJson<AlertaPage>(`/alertas?${sp.toString()}`)
  },
  registrarContato: (clienteId: number): Promise<ContatoOut> =>
    apiJson<ContatoOut>(`/alertas/${clienteId}/contato`, { method: 'POST' }),
}
```

- [ ] **Step 4: Estender `frontend/src/auth/roles.ts`** (no fim):

```ts
export const FUNCAO_COMERCIAL = 'Comercial Pós-Vendas'

export function podeRegistrarContato(user: User | null): boolean {
  return isAdmin(user) || user?.funcao === FUNCAO_COMERCIAL
}
```

- [ ] **Step 5: Rodar e ver passar**

Run: `npm --prefix frontend run test -- alertas/api auth/roles`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/app/alertas/api.ts frontend/src/auth/roles.ts frontend/src/app/alertas/api.test.ts frontend/src/auth/roles.test.ts
git -C /d/GitHub/GestorHS commit -m "feat(frontend): alertasApi + podeRegistrarContato"
```

---

### Task 4: Nav "Cobrança" + `CobrancaPage` + rota

**Files:**
- Modify: `frontend/src/components/ui/icons.tsx` (`IconCobranca`)
- Modify: `frontend/src/layout/Sidebar.tsx`
- Create: `frontend/src/app/alertas/CobrancaPage.tsx`
- Modify: `frontend/src/app/routes.tsx`

> UI — verificada por `lint` + `build`.

- [ ] **Step 1: Adicionar `IconCobranca` em `frontend/src/components/ui/icons.tsx`**

```tsx
export function IconCobranca({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.4-1.4A2 2 0 0118 14.2V11a6 6 0 00-4-5.66V5a2 2 0 10-4 0v.34A6 6 0 006 11v3.2a2 2 0 01-.6 1.4L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
    </svg>
  )
}
```

- [ ] **Step 2: Adicionar o item de nav em `frontend/src/layout/Sidebar.tsx`**

Importe `IconCobranca` no import de `../components/ui/icons` e adicione ao `NAV_ITEMS` (depois de Ordens, sem `adminOnly`):
```tsx
  { label: 'Cobrança', icon: <IconCobranca />, to: '/app/cobranca' },
```

- [ ] **Step 3: Criar `frontend/src/app/alertas/CobrancaPage.tsx`**

```tsx
import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Spinner } from '../../components/ui/Spinner'
import { Input } from '../../components/ui/Input'
import { ApiError } from '../../lib/api'
import { useAuth } from '../../auth/AuthContext'
import { podeRegistrarContato } from '../../auth/roles'
import { alertasApi, formatData, type AlertaItem } from './api'

const LIMITE = 25

export function CobrancaPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const podeContato = podeRegistrarContato(user)
  const [termo, setTermo] = useState('')
  const [busca, setBusca] = useState('')
  const [ocultar, setOcultar] = useState(false)
  const [offset, setOffset] = useState(0)
  const [itens, setItens] = useState<AlertaItem[] | null>(null)
  const [total, setTotal] = useState(0)
  const [erro, setErro] = useState('')

  useEffect(() => {
    let ativo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setItens(null)
    setErro('')
    alertasApi
      .listar({ q: busca || undefined, ocultar_recentes: ocultar, offset, limit: LIMITE })
      .then((p) => {
        if (!ativo) return
        setItens(p.items)
        setTotal(p.total)
      })
      .catch((e) => {
        if (!ativo) return
        setErro(e instanceof ApiError ? e.message : 'Falha ao carregar')
        setItens([])
      })
    return () => {
      ativo = false
    }
  }, [busca, ocultar, offset])

  function onBuscar(e: FormEvent) {
    e.preventDefault()
    setOffset(0)
    setBusca(termo.trim())
  }

  async function contato(item: AlertaItem) {
    setErro('')
    try {
      const r = await alertasApi.registrarContato(item.cliente)
      setItens((prev) => prev?.map((i) => (i.cliente === item.cliente ? { ...i, ult_contato: r.ult_contato } : i)) ?? prev)
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao registrar contato')
    }
  }

  const inicio = total === 0 ? 0 : offset + 1
  const fim = Math.min(offset + LIMITE, total)

  return (
    <div className="px-4 md:px-6 py-6 space-y-6">
      <h1 className="text-2xl font-extrabold text-slate-100">Cobrança</h1>

      <div className="flex flex-wrap gap-3 items-end">
        <form onSubmit={onBuscar} className="flex gap-2 items-end flex-1 min-w-60">
          <div className="flex-1"><Input id="busca" label="Buscar cliente" value={termo} onChange={(e) => setTermo(e.target.value)} /></div>
          <Button type="submit" variant="secondary">Buscar</Button>
        </form>
        <label className="flex items-center gap-2 text-sm text-slate-300">
          <input type="checkbox" checked={ocultar} onChange={(e) => { setOffset(0); setOcultar(e.target.checked) }} className="accent-primary" />
          Ocultar contatados (30 dias)
        </label>
      </div>

      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}

      {itens === null ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum cliente com pendências.</p>
      ) : (
        <>
          <Table head={<><TH>Cliente</TH><TH>Vencidos</TH><TH>Vencendo</TH><TH>Venc. mais antigo</TH><TH>Último contato</TH><TH>Ações</TH></>}>
            {itens.map((i) => (
              <tr key={i.cliente} className="hover:bg-background-elevated transition-colors">
                <TD>{i.cliente_nome ?? `#${i.cliente}`}</TD>
                <TD>{i.vencidos > 0 ? <Badge tone="danger">{String(i.vencidos)}</Badge> : '—'}</TD>
                <TD>{i.vencendo > 0 ? <Badge tone="warning">{String(i.vencendo)}</Badge> : '—'}</TD>
                <TD>{formatData(i.prox_antiga)}</TD>
                <TD>{formatData(i.ult_contato)}</TD>
                <TD>
                  <div className="flex gap-3">
                    <button onClick={() => navigate(`/app/frota?cliente=${i.cliente}`)} className="text-xs text-primary hover:underline">Ver frota</button>
                    {podeContato && <button onClick={() => contato(i)} className="text-xs text-primary hover:underline">Registrar contato</button>}
                  </div>
                </TD>
              </tr>
            ))}
          </Table>
          <div className="flex items-center justify-between text-sm text-slate-400">
            <span>{inicio}–{fim} de {total}</span>
            <div className="flex gap-2">
              <Button variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - LIMITE))}>Anterior</Button>
              <Button variant="secondary" disabled={fim >= total} onClick={() => setOffset(offset + LIMITE)}>Próxima</Button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Registrar a rota em `frontend/src/app/routes.tsx`**

```tsx
import { CobrancaPage } from './alertas/CobrancaPage'
```
```tsx
        <Route path="cobranca" element={<CobrancaPage />} />
```

- [ ] **Step 5: Verificar lint + build**

Run: `npm --prefix frontend run lint`
Expected: sem erros.
Run: `npm --prefix frontend run build`
Expected: limpo.

- [ ] **Step 6: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/components/ui/icons.tsx frontend/src/layout/Sidebar.tsx frontend/src/app/alertas/CobrancaPage.tsx frontend/src/app/routes.tsx
git -C /d/GitHub/GestorHS commit -m "feat(frontend): pagina Cobranca (worklist + registrar contato) + nav"
```

---

### Task 5: Verificação final

**Files:** nenhum.

- [ ] **Step 1: Backend completo**

Run: `docker compose exec -T backend python -m pytest -q`
Expected: ~137 passed.

- [ ] **Step 2: Frontend completo**

Run: `npm --prefix frontend run test`
Expected: ~68 passed (64 da Fase 3 + 4 novos do alertas/roles).

- [ ] **Step 3: Lint + build**

Run: `npm --prefix frontend run lint` (sem erros) e `npm --prefix frontend run build` (limpo).

- [ ] **Step 4: (sem commit — verificação)** Reporte os números. Se algo falhar, corrija na task correspondente.

---

## Notas para o executor
- A agregação conta `vencendo` como `prox >= hoje` porque o filtro já restringe `prox <= hoje+90` (a janela). `total` é o nº de clientes com pendência (contado em Python sobre as linhas agregadas; a paginação fatia em memória — o volume de clientes com pendência é pequeno).
- `ocultar_recentes` usa `HAVING max(ult_aviso) < hoje-30d OR IS NULL`. Em SQLite o `ult_aviso` (DateTime tz) compara via ISO; o teste seta `ult_aviso = agora()` (recente) e espera que o cliente suma.
- `registrar_contato` marca os MESMOS elegíveis da worklist (ativos, vencido/vencendo); não toca em_dia/inativo. `require_funcao("Comercial Pós-Vendas", "Administrador")`.
- Drill-down "Ver frota" reusa a Frota (`/app/frota?cliente=ID`), sem código novo de listagem.
- Após a Task 5, o controlador roda o E2E não-destrutivo (lista de cobrança, busca, ocultar recentes, "Ver frota"); "Registrar contato" só com pedido explícito (escrita de `ult_aviso`).
```
