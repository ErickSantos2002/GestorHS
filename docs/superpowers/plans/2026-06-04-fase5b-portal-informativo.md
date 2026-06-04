# Fase 5B (Portal informativo) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Três páginas só-leitura no portal do cliente — Minha frota, Certificados, Minhas OS — com endpoints escopados ao cliente do token.

**Architecture:** Backend — 3 endpoints em `app/api/portal.py`, todos com `get_current_cliente` e `filter(<Modelo>.cliente == cli.cliente)`; certificados puxa o PDF via `equipamentos_cliente.os_atual` → `ordens.pdf_certificado` (left join). Frontend — 3 páginas substituindo os `EmBrevePage` da 5A, reusando o shell e o padrão de lista paginada.

**Tech Stack:** Backend FastAPI/SQLAlchemy/pytest; Frontend React 19/TS/Vite/Vitest.

**Spec:** `docs/superpowers/specs/2026-06-04-fase5b-portal-informativo-design.md`

**Comandos:** Backend Docker (`docker compose exec -T backend python -m pytest <args>`). Frontend `npm --prefix frontend run test|lint|build`. Git via `git -C /d/GitHub/GestorHS`. Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

**Branch:** antes da Task 1:
```bash
git -C /d/GitHub/GestorHS checkout -b feat/fase5b-portal
```

## Convenções (já estabelecidas)
- Backend: `app/api/portal.py` (5A) já tem `me`/`resumo` com `get_current_cliente` (retorna `UsuarioCliente`; `.cliente` = tenant), `_FASES_ATIVAS = (4,5,6,7)`. `EquipamentoCliente` tem props `status_calibracao`/`equipamento_descricao`; `Ordem` tem props `equipamento_descricao`/`equipamento_serie`/`fase_descricao`/`fase_cor`. Testes pytest/SQLite; fixtures `cliente_portal` (cria empresa `Cliente` cgc="11222333000144" + usuário `cliente1`/`portal123`), `fases_seed`.
- Frontend: `portal/api.ts` (5A) tem `portalApi.me/resumo`. Padrão de lista paginada (`{items,total}`, offset/limit 25, guarda `ativo`, `Spinner`, erro inline). Componentes `Table/TH/TD`, `Badge`, `Spinner`, `Input`, `Select`, `Button`. Lint `react-hooks/set-state-in-effect`: disable só na 1ª chamada síncrona de setState no efeito. Telas por `tsc`/`lint`/`build`.

---

### Task 1: Endpoints `/portal/minha-frota`, `/certificados`, `/minhas-os`

**Files:**
- Modify: `backend/app/schemas/portal.py`
- Modify: `backend/app/api/portal.py`
- Test: `backend/tests/test_portal.py` (estender)

- [ ] **Step 1: Escrever os testes falhando** — acrescente ao FIM de `backend/tests/test_portal.py`:

```python
from datetime import date, timedelta


def _ph(client):
    tok = client.post("/auth/login-portal", json={"documento": "11222333000144", "login": "cliente1", "senha": "portal123"}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _setup_informativo(db_session, cliente_id):
    from app.models import Cliente, Equipamento, EquipamentoCliente, Ordem
    hoje = date.today()
    eq = Equipamento(descricao="Bafômetro")
    outro = Cliente(nome="Outro Cli")
    db_session.add_all([eq, outro]); db_session.flush()
    os_cert = Ordem(cliente=cliente_id, fase=8, situacao="F", pdf_certificado="http://x/cert.pdf")
    db_session.add(os_cert); db_session.flush()
    db_session.add_all([
        EquipamentoCliente(cliente=cliente_id, equipamento=eq.id, serie="S-VEN", prox_calibragem=hoje - timedelta(days=5), ativo=True),
        EquipamentoCliente(cliente=cliente_id, equipamento=eq.id, serie="S-VND", prox_calibragem=hoje + timedelta(days=30), ativo=True),
        EquipamentoCliente(cliente=cliente_id, equipamento=eq.id, serie="S-OK", prox_calibragem=hoje + timedelta(days=200), ativo=True),
        EquipamentoCliente(cliente=cliente_id, equipamento=eq.id, serie="S-CERT", calib_cert="HF1", ult_calibragem=hoje, prox_calibragem=hoje + timedelta(days=300), ativo=True, os_atual=os_cert.id),
        EquipamentoCliente(cliente=outro.id, equipamento=eq.id, serie="OUTRO", prox_calibragem=hoje - timedelta(days=5), ativo=True),
        Ordem(cliente=cliente_id, fase=5, situacao="E"),
        Ordem(cliente=outro.id, fase=5, situacao="E"),
    ])
    db_session.commit()


def test_minha_frota(client, cliente_portal, fases_seed, db_session):
    _setup_informativo(db_session, cliente_portal.cliente)
    r = client.get("/portal/minha-frota", headers=_ph(client))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 4  # 4 ativos do cliente; o do "outro" não entra
    assert all(i["serie"] != "OUTRO" for i in body["items"])


def test_minha_frota_status_e_busca(client, cliente_portal, fases_seed, db_session):
    _setup_informativo(db_session, cliente_portal.cliente)
    r = client.get("/portal/minha-frota?status=vencido", headers=_ph(client))
    assert r.json()["total"] == 1 and r.json()["items"][0]["serie"] == "S-VEN"
    r2 = client.get("/portal/minha-frota?q=S-OK", headers=_ph(client))
    assert r2.json()["total"] == 1


def test_certificados(client, cliente_portal, fases_seed, db_session):
    _setup_informativo(db_session, cliente_portal.cliente)
    r = client.get("/portal/certificados", headers=_ph(client))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["calib_cert"] == "HF1"
    assert item["pdf"] == "http://x/cert.pdf"


def test_minhas_os(client, cliente_portal, fases_seed, db_session):
    _setup_informativo(db_session, cliente_portal.cliente)
    r = client.get("/portal/minhas-os", headers=_ph(client))
    assert r.status_code == 200
    assert r.json()["total"] == 2  # fase 8 (cert) + fase 5; não a do outro cliente


def test_minhas_os_em_andamento(client, cliente_portal, fases_seed, db_session):
    _setup_informativo(db_session, cliente_portal.cliente)
    r = client.get("/portal/minhas-os?em_andamento=true", headers=_ph(client))
    assert r.json()["total"] == 1  # só a fase 5


def test_portal_informativo_sem_token_401(client):
    assert client.get("/portal/minha-frota").status_code == 401
    assert client.get("/portal/certificados").status_code == 401
    assert client.get("/portal/minhas-os").status_code == 401
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_portal.py -q`
Expected: FAIL (404 — endpoints não existem).

- [ ] **Step 3: Adicionar os schemas em `backend/app/schemas/portal.py`**

Atualize o import do topo para `from pydantic import BaseModel, ConfigDict` e adicione `from datetime import date, datetime`. Acrescente ao fim:
```python
class PortalFrotaItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    equipamento_descricao: str | None = None
    serie: str | None = None
    patrimonio: str | None = None
    prox_calibragem: date | None = None
    status_calibracao: str


class PortalFrotaPage(BaseModel):
    items: list[PortalFrotaItem]
    total: int


class PortalCertItem(BaseModel):
    equipamento_cliente: int
    equipamento_descricao: str | None = None
    serie: str | None = None
    calib_cert: str | None = None
    ult_calibragem: date | None = None
    prox_calibragem: date | None = None
    pdf: str | None = None


class PortalCertPage(BaseModel):
    items: list[PortalCertItem]
    total: int


class PortalOSItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    equipamento_descricao: str | None = None
    equipamento_serie: str | None = None
    fase: int | None = None
    fase_descricao: str | None = None
    fase_cor: str | None = None
    tipo_servico: str | None = None
    data_chegada: datetime | None = None
    prox_calibragem: datetime | None = None
    situacao: str


class PortalOSPage(BaseModel):
    items: list[PortalOSItem]
    total: int
```

- [ ] **Step 4: Adicionar os endpoints em `backend/app/api/portal.py`**

Atualize os imports: `from datetime import date, timedelta`, `from fastapi import APIRouter, Depends, Query`, `from sqlalchemy import or_`, e o import de schemas para incluir os novos (`PortalFrotaItem, PortalFrotaPage, PortalCertItem, PortalCertPage, PortalOSItem, PortalOSPage`). Acrescente ao fim do arquivo:
```python
@router.get("/minha-frota", response_model=PortalFrotaPage)
def minha_frota(
    status: str | None = None,
    q: str | None = None,
    offset: int = 0,
    limit: int = Query(25, ge=1, le=100),
    cli: UsuarioCliente = Depends(get_current_cliente),
    db: Session = Depends(get_db),
):
    hoje = date.today()
    limite = hoje + timedelta(days=90)
    query = db.query(EquipamentoCliente).filter(
        EquipamentoCliente.cliente == cli.cliente,
        EquipamentoCliente.ativo.is_(True),
    )
    if status == "vencido":
        query = query.filter(EquipamentoCliente.prox_calibragem < hoje)
    elif status == "vencendo":
        query = query.filter(EquipamentoCliente.prox_calibragem >= hoje, EquipamentoCliente.prox_calibragem <= limite)
    elif status == "em_dia":
        query = query.filter(EquipamentoCliente.prox_calibragem > limite)
    elif status == "sem_data":
        query = query.filter(EquipamentoCliente.prox_calibragem.is_(None))
    if q:
        termo = f"%{q}%"
        query = query.filter(or_(EquipamentoCliente.serie.ilike(termo), EquipamentoCliente.patrimonio.ilike(termo)))
    total = query.count()
    items = query.order_by(EquipamentoCliente.id).offset(offset).limit(limit).all()
    return PortalFrotaPage(items=[PortalFrotaItem.model_validate(e) for e in items], total=total)


@router.get("/certificados", response_model=PortalCertPage)
def certificados(
    offset: int = 0,
    limit: int = Query(25, ge=1, le=100),
    cli: UsuarioCliente = Depends(get_current_cliente),
    db: Session = Depends(get_db),
):
    base = (
        db.query(EquipamentoCliente, Ordem.pdf_certificado)
        .outerjoin(Ordem, EquipamentoCliente.os_atual == Ordem.id)
        .filter(
            EquipamentoCliente.cliente == cli.cliente,
            EquipamentoCliente.calib_cert.isnot(None),
            EquipamentoCliente.calib_cert != "",
        )
    )
    total = base.count()
    linhas = base.order_by(EquipamentoCliente.ult_calibragem.desc()).offset(offset).limit(limit).all()
    items = [
        PortalCertItem(
            equipamento_cliente=ec.id,
            equipamento_descricao=ec.equipamento_descricao,
            serie=ec.serie,
            calib_cert=ec.calib_cert,
            ult_calibragem=ec.ult_calibragem,
            prox_calibragem=ec.prox_calibragem,
            pdf=pdf,
        )
        for ec, pdf in linhas
    ]
    return PortalCertPage(items=items, total=total)


@router.get("/minhas-os", response_model=PortalOSPage)
def minhas_os(
    em_andamento: bool = False,
    offset: int = 0,
    limit: int = Query(25, ge=1, le=100),
    cli: UsuarioCliente = Depends(get_current_cliente),
    db: Session = Depends(get_db),
):
    query = db.query(Ordem).filter(Ordem.cliente == cli.cliente)
    if em_andamento:
        query = query.filter(Ordem.fase.in_(_FASES_ATIVAS))
    total = query.count()
    items = query.order_by(Ordem.id.desc()).offset(offset).limit(limit).all()
    return PortalOSPage(items=[PortalOSItem.model_validate(o) for o in items], total=total)
```

- [ ] **Step 5: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_portal.py -q`
Expected: PASS (10 passed — 4 da 5A + 6 novos).

- [ ] **Step 6: Rodar a suíte backend inteira**

Run: `docker compose exec -T backend python -m pytest -q`
Expected: verde (~149).

- [ ] **Step 7: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/app/schemas/portal.py backend/app/api/portal.py backend/tests/test_portal.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): endpoints informativos do portal (minha-frota, certificados, minhas-os)"
```

---

### Task 2: Frontend — `portal/api.ts` (métodos informativos)

**Files:**
- Modify: `frontend/src/portal/api.ts`
- Test: `frontend/src/portal/api.test.ts` (estender)

- [ ] **Step 1: Escrever os testes falhando** — acrescente ao FIM do `describe('portal/api', ...)` em `frontend/src/portal/api.test.ts`:

```ts
  it('minhaFrota monta a query (status/q/offset/limit)', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ items: [], total: 0 }))
    vi.stubGlobal('fetch', f)
    await portalApi.minhaFrota({ status: 'vencido', q: 'S1', offset: 25, limit: 25 })
    const url = String(f.mock.calls[0][0])
    expect(url).toContain('/portal/minha-frota?')
    expect(url).toContain('status=vencido')
    expect(url).toContain('q=S1')
  })

  it('certificados bate em /portal/certificados', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ items: [], total: 0 }))
    vi.stubGlobal('fetch', f)
    await portalApi.certificados({})
    expect(String(f.mock.calls[0][0])).toContain('/portal/certificados')
  })

  it('minhasOs inclui em_andamento só quando true', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ items: [], total: 0 }))
    vi.stubGlobal('fetch', f)
    await portalApi.minhasOs({ em_andamento: true })
    expect(String(f.mock.calls[0][0])).toContain('em_andamento=true')
    await portalApi.minhasOs({})
    expect(String(f.mock.calls[1][0])).not.toContain('em_andamento')
  })
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm --prefix frontend run test -- portal/api`
Expected: FAIL (métodos ausentes).

- [ ] **Step 3: Estender `frontend/src/portal/api.ts`** — acrescente ao fim do arquivo (helpers + tipos) e os 3 métodos dentro do objeto `portalApi`:

```ts
export function formatData(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return isNaN(d.getTime()) ? '—' : d.toLocaleDateString('pt-BR')
}

export const STATUS_CALIB: Record<string, { label: string; tone: 'primary' | 'warning' | 'danger' | 'neutral' }> = {
  em_dia: { label: 'Em dia', tone: 'primary' },
  vencendo: { label: 'Vencendo', tone: 'warning' },
  vencido: { label: 'Vencido', tone: 'danger' },
  sem_data: { label: 'Sem data', tone: 'neutral' },
}

export const TIPO_LABEL: Record<string, string> = { C: 'Calibração', M: 'Manutenção', A: 'Ambas' }

export interface PortalFrotaItem {
  id: number
  equipamento_descricao: string | null
  serie: string | null
  patrimonio: string | null
  prox_calibragem: string | null
  status_calibracao: string
}
export interface PortalFrotaPage { items: PortalFrotaItem[]; total: number }

export interface PortalCertItem {
  equipamento_cliente: number
  equipamento_descricao: string | null
  serie: string | null
  calib_cert: string | null
  ult_calibragem: string | null
  prox_calibragem: string | null
  pdf: string | null
}
export interface PortalCertPage { items: PortalCertItem[]; total: number }

export interface PortalOSItem {
  id: number
  equipamento_descricao: string | null
  equipamento_serie: string | null
  fase: number | null
  fase_descricao: string | null
  fase_cor: string | null
  tipo_servico: string | null
  data_chegada: string | null
  prox_calibragem: string | null
  situacao: string
}
export interface PortalOSPage { items: PortalOSItem[]; total: number }
```
E dentro do objeto `portalApi` (após `resumo`):
```ts
  minhaFrota: (params: { status?: string; q?: string; offset?: number; limit?: number } = {}): Promise<PortalFrotaPage> => {
    const sp = new URLSearchParams()
    if (params.status) sp.set('status', params.status)
    if (params.q) sp.set('q', params.q)
    sp.set('offset', String(params.offset ?? 0))
    sp.set('limit', String(params.limit ?? 25))
    return apiJson<PortalFrotaPage>(`/portal/minha-frota?${sp.toString()}`)
  },
  certificados: (params: { offset?: number; limit?: number } = {}): Promise<PortalCertPage> => {
    const sp = new URLSearchParams()
    sp.set('offset', String(params.offset ?? 0))
    sp.set('limit', String(params.limit ?? 25))
    return apiJson<PortalCertPage>(`/portal/certificados?${sp.toString()}`)
  },
  minhasOs: (params: { em_andamento?: boolean; offset?: number; limit?: number } = {}): Promise<PortalOSPage> => {
    const sp = new URLSearchParams()
    if (params.em_andamento) sp.set('em_andamento', 'true')
    sp.set('offset', String(params.offset ?? 0))
    sp.set('limit', String(params.limit ?? 25))
    return apiJson<PortalOSPage>(`/portal/minhas-os?${sp.toString()}`)
  },
```

- [ ] **Step 4: Rodar e ver passar**

Run: `npm --prefix frontend run test -- portal/api`
Expected: PASS (6 passed — 3 da 5A + 3 novos).

- [ ] **Step 5: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/portal/api.ts frontend/src/portal/api.test.ts
git -C /d/GitHub/GestorHS commit -m "feat(frontend): portalApi minhaFrota/certificados/minhasOs + tipos"
```

---

### Task 3: Páginas do portal + rotas

**Files:**
- Create: `frontend/src/portal/PortalFrotaPage.tsx`
- Create: `frontend/src/portal/PortalCertificadosPage.tsx`
- Create: `frontend/src/portal/PortalOSPage.tsx`
- Modify: `frontend/src/portal/routes.tsx`
- Delete: `frontend/src/portal/EmBrevePage.tsx`

> UI — verificada por `lint` + `build`.

- [ ] **Step 1: Criar `frontend/src/portal/PortalFrotaPage.tsx`**

```tsx
import { useEffect, useState, type FormEvent } from 'react'
import { Table, TH, TD } from '../components/ui/Table'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { Spinner } from '../components/ui/Spinner'
import { Input } from '../components/ui/Input'
import { Select } from '../components/ui/Select'
import { ApiError } from '../lib/api'
import { portalApi, STATUS_CALIB, formatData, type PortalFrotaItem } from './api'

const LIMITE = 25

export function PortalFrotaPage() {
  const [status, setStatus] = useState('')
  const [termo, setTermo] = useState('')
  const [busca, setBusca] = useState('')
  const [offset, setOffset] = useState(0)
  const [itens, setItens] = useState<PortalFrotaItem[] | null>(null)
  const [total, setTotal] = useState(0)
  const [erro, setErro] = useState('')

  useEffect(() => {
    let ativo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setItens(null)
    setErro('')
    portalApi.minhaFrota({ status: status || undefined, q: busca || undefined, offset, limit: LIMITE })
      .then((p) => { if (!ativo) return; setItens(p.items); setTotal(p.total) })
      .catch((e) => { if (!ativo) return; setErro(e instanceof ApiError ? e.message : 'Falha ao carregar'); setItens([]) })
    return () => { ativo = false }
  }, [status, busca, offset])

  function onBuscar(e: FormEvent) { e.preventDefault(); setOffset(0); setBusca(termo.trim()) }
  const inicio = total === 0 ? 0 : offset + 1
  const fim = Math.min(offset + LIMITE, total)

  return (
    <div className="px-4 md:px-6 py-6 space-y-6">
      <h1 className="text-2xl font-extrabold text-slate-100">Minha frota</h1>
      <div className="flex flex-wrap gap-2 items-end">
        <div className="w-48">
          <Select id="status" label="Status" value={status} onChange={(e) => { setOffset(0); setStatus(e.target.value) }}>
            <option value="">Todos</option>
            <option value="em_dia">Em dia</option>
            <option value="vencendo">Vencendo</option>
            <option value="vencido">Vencido</option>
            <option value="sem_data">Sem data</option>
          </Select>
        </div>
        <form onSubmit={onBuscar} className="flex gap-2 items-end flex-1 min-w-60">
          <div className="flex-1"><Input id="busca" label="Busca" placeholder="Série ou patrimônio" value={termo} onChange={(e) => setTermo(e.target.value)} /></div>
          <Button type="submit" variant="secondary">Buscar</Button>
        </form>
      </div>
      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      {itens === null ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum aparelho encontrado.</p>
      ) : (
        <>
          <Table head={<><TH>Aparelho</TH><TH>Série / Patrimônio</TH><TH>Próx. calibração</TH><TH>Status</TH></>}>
            {itens.map((e) => {
              const s = STATUS_CALIB[e.status_calibracao] ?? STATUS_CALIB.sem_data
              return (
                <tr key={e.id} className="hover:bg-background-elevated transition-colors">
                  <TD>{e.equipamento_descricao ?? '—'}</TD>
                  <TD>{e.serie || e.patrimonio || '—'}</TD>
                  <TD>{formatData(e.prox_calibragem)}</TD>
                  <TD><Badge tone={s.tone}>{s.label}</Badge></TD>
                </tr>
              )
            })}
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

- [ ] **Step 2: Criar `frontend/src/portal/PortalCertificadosPage.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { Table, TH, TD } from '../components/ui/Table'
import { Button } from '../components/ui/Button'
import { Spinner } from '../components/ui/Spinner'
import { ApiError } from '../lib/api'
import { portalApi, formatData, type PortalCertItem } from './api'

const LIMITE = 25

export function PortalCertificadosPage() {
  const [offset, setOffset] = useState(0)
  const [itens, setItens] = useState<PortalCertItem[] | null>(null)
  const [total, setTotal] = useState(0)
  const [erro, setErro] = useState('')

  useEffect(() => {
    let ativo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setItens(null)
    setErro('')
    portalApi.certificados({ offset, limit: LIMITE })
      .then((p) => { if (!ativo) return; setItens(p.items); setTotal(p.total) })
      .catch((e) => { if (!ativo) return; setErro(e instanceof ApiError ? e.message : 'Falha ao carregar'); setItens([]) })
    return () => { ativo = false }
  }, [offset])

  const inicio = total === 0 ? 0 : offset + 1
  const fim = Math.min(offset + LIMITE, total)

  return (
    <div className="px-4 md:px-6 py-6 space-y-6">
      <h1 className="text-2xl font-extrabold text-slate-100">Certificados</h1>
      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      {itens === null ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum certificado disponível.</p>
      ) : (
        <>
          <Table head={<><TH>Aparelho</TH><TH>Série</TH><TH>Certificado</TH><TH>Última calibração</TH><TH>Próxima calibração</TH><TH>PDF</TH></>}>
            {itens.map((c) => (
              <tr key={c.equipamento_cliente} className="hover:bg-background-elevated transition-colors">
                <TD>{c.equipamento_descricao ?? '—'}</TD>
                <TD>{c.serie ?? '—'}</TD>
                <TD>{c.calib_cert ?? '—'}</TD>
                <TD>{formatData(c.ult_calibragem)}</TD>
                <TD>{formatData(c.prox_calibragem)}</TD>
                <TD>{c.pdf && c.pdf.startsWith('http')
                  ? <a href={c.pdf} target="_blank" rel="noreferrer" className="text-primary hover:underline">abrir</a>
                  : '—'}</TD>
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

- [ ] **Step 3: Criar `frontend/src/portal/PortalOSPage.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { Table, TH, TD } from '../components/ui/Table'
import { Button } from '../components/ui/Button'
import { Spinner } from '../components/ui/Spinner'
import { ApiError } from '../lib/api'
import { portalApi, TIPO_LABEL, formatData, type PortalOSItem } from './api'

const LIMITE = 25

export function PortalOSPage() {
  const [emAndamento, setEmAndamento] = useState(false)
  const [offset, setOffset] = useState(0)
  const [itens, setItens] = useState<PortalOSItem[] | null>(null)
  const [total, setTotal] = useState(0)
  const [erro, setErro] = useState('')

  useEffect(() => {
    let ativo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setItens(null)
    setErro('')
    portalApi.minhasOs({ em_andamento: emAndamento, offset, limit: LIMITE })
      .then((p) => { if (!ativo) return; setItens(p.items); setTotal(p.total) })
      .catch((e) => { if (!ativo) return; setErro(e instanceof ApiError ? e.message : 'Falha ao carregar'); setItens([]) })
    return () => { ativo = false }
  }, [emAndamento, offset])

  const inicio = total === 0 ? 0 : offset + 1
  const fim = Math.min(offset + LIMITE, total)

  return (
    <div className="px-4 md:px-6 py-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-2xl font-extrabold text-slate-100">Minhas OS</h1>
        <label className="flex items-center gap-2 text-sm text-slate-300">
          <input type="checkbox" checked={emAndamento} onChange={(e) => { setOffset(0); setEmAndamento(e.target.checked) }} className="accent-primary" />
          Em andamento
        </label>
      </div>
      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      {itens === null ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhuma OS encontrada.</p>
      ) : (
        <>
          <Table head={<><TH>OS</TH><TH>Aparelho</TH><TH>Fase</TH><TH>Tipo</TH><TH>Chegada</TH></>}>
            {itens.map((o) => (
              <tr key={o.id} className="hover:bg-background-elevated transition-colors">
                <TD>#{o.id}</TD>
                <TD>{o.equipamento_descricao ?? '—'}{o.equipamento_serie ? ` · ${o.equipamento_serie}` : ''}</TD>
                <TD>{o.fase_descricao ? (
                  <span className="inline-flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full" style={{ background: `#${o.fase_cor}` }} />
                    {o.fase_descricao}
                  </span>
                ) : '—'}</TD>
                <TD>{o.tipo_servico && TIPO_LABEL[o.tipo_servico] ? TIPO_LABEL[o.tipo_servico] : '—'}</TD>
                <TD>{formatData(o.data_chegada)}</TD>
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

- [ ] **Step 4: Atualizar `frontend/src/portal/routes.tsx`** — troque o import do `EmBrevePage` pelos das 3 páginas e os 3 `<Route>`:

Substitua `import { EmBrevePage } from './EmBrevePage'` por:
```tsx
import { PortalFrotaPage } from './PortalFrotaPage'
import { PortalCertificadosPage } from './PortalCertificadosPage'
import { PortalOSPage } from './PortalOSPage'
```
E troque as três rotas:
```tsx
                  <Route path="frota" element={<PortalFrotaPage />} />
                  <Route path="certificados" element={<PortalCertificadosPage />} />
                  <Route path="os" element={<PortalOSPage />} />
```

- [ ] **Step 5: Remover `frontend/src/portal/EmBrevePage.tsx`** (não é mais usado)

```bash
git -C /d/GitHub/GestorHS rm frontend/src/portal/EmBrevePage.tsx
```

- [ ] **Step 6: Verificar lint + build**

Run: `npm --prefix frontend run lint`
Expected: sem erros.
Run: `npm --prefix frontend run build`
Expected: limpo.

- [ ] **Step 7: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/portal/PortalFrotaPage.tsx frontend/src/portal/PortalCertificadosPage.tsx frontend/src/portal/PortalOSPage.tsx frontend/src/portal/routes.tsx
git -C /d/GitHub/GestorHS commit -m "feat(frontend): paginas Minha frota, Certificados e Minhas OS no portal"
```

---

### Task 4: Verificação final

**Files:** nenhum.

- [ ] **Step 1: Backend completo**

Run: `docker compose exec -T backend python -m pytest -q`
Expected: ~149 passed.

- [ ] **Step 2: Frontend completo**

Run: `npm --prefix frontend run test`
Expected: ~77 passed (74 + 3 novos do portal/api).

- [ ] **Step 3: Lint + build**

Run: `npm --prefix frontend run lint` (sem erros) e `npm --prefix frontend run build` (limpo).

- [ ] **Step 4: (sem commit — verificação)** Reporte os números. Se algo falhar, corrija na task correspondente.

---

## Notas para o executor
- Todos os endpoints do portal filtram por `cli.cliente` (do token) — nunca aceitam `cliente` por parâmetro (isolamento de tenant).
- `PortalFrotaItem`/`PortalOSItem` usam `model_validate` (from_attributes) sobre o modelo — os nomes dos campos batem com colunas/properties (`status_calibracao`, `equipamento_descricao`, `equipamento_serie`, `fase_descricao`, `fase_cor`). O de certificados é montado manualmente (vem da tupla `(EquipamentoCliente, pdf)` do join).
- `EquipamentoCliente.prox_calibragem`/`ult_calibragem` são `Date`; `Ordem.data_chegada`/`prox_calibragem` são `datetime` — por isso os tipos diferentes nos schemas.
- O PDF do certificado vem da OS (`equipamentos_cliente.os_atual` → `ordens.pdf_certificado`); o frontend só vira link quando é URL (`startsWith('http')`).
- Após a Task 4, o controlador faz o E2E não-destrutivo (logar como cliente de teste, abrir as 3 abas), reusando o fluxo da 5A (criar/remover o usuário-cliente de teste).
```
