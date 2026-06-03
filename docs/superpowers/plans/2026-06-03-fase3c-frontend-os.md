# Fase 3C (Frontend de OS — visualização + config) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Interface só-leitura do módulo de Ordens de Serviço (kanban + lista + detalhe) e a tela admin de config função→fase + CRUD de funções.

**Architecture:** Novo módulo `frontend/src/app/ordens/` (api + páginas) no padrão de `app/frota/`; `OrdensPage` com toggle Quadro|Lista numa rota só; `OrdemDetailPage` só-leitura com timeline de logs. Config admin via duas abas novas (`Funções`, `Fases`) na `CadastrosPage` existente. Lógica de API testada com Vitest; telas verificadas por `tsc`/`lint`/`build` + E2E manual (padrão do projeto).

**Tech Stack:** React 19, TypeScript 6, Vite 8, Tailwind v4, react-router-dom 7, Vitest.

**Spec:** `docs/superpowers/specs/2026-06-03-fase3c-frontend-os-design.md`

**Comandos** (da raiz `d:\GitHub\GestorHS`): `npm --prefix frontend run test` (vitest), `npm --prefix frontend run lint`, `npm --prefix frontend run build` (`tsc -b && vite build`). Git via `git -C /d/GitHub/GestorHS`. Trailer de commit: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

**Branch:** antes da Task 1:
```bash
git -C /d/GitHub/GestorHS checkout -b feat/fase3c-frontend-os
```

## Convenções (já estabelecidas — siga-as)
- Módulo de domínio: `api.ts` com tipos + objeto-cliente usando `apiJson` de `lib/api`. Páginas com `Table/TH/TD`, `Button`, `Badge` (tones primary/warning/danger/info/neutral), `Spinner`, `Input`, `Select` (prop `label` opcional), `Modal`; `cn()` de `lib/utils`; `useAuth`/`isAdmin`; `useNavigate`/`useSearchParams`. Padrão de lista: `useEffect` com guarda `let ativo`, paginação `offset`/`limit=25`, "X–Y de N".
- O lint tem a regra `react-hooks/set-state-in-effect`: para `setState` síncrono no corpo do `useEffect`, ponha `// eslint-disable-next-line react-hooks/set-state-in-effect` SOMENTE na linha exata sinalizada (1ª chamada de setState). O guard `if (!ativo) return` dentro dos `.then` não precisa de disable.
- Datas vêm como ISO (timestamptz). Formate com o helper `formatData` (Task 1).

---

### Task 1: `ordens/api.ts` + testes da API

**Files:**
- Create: `frontend/src/app/ordens/api.ts`
- Test: `frontend/src/app/ordens/api.test.ts`

- [ ] **Step 1: Escrever os testes falhando** — `frontend/src/app/ordens/api.test.ts`:

```ts
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ordensApi } from './api'
import { setTokens } from '../../lib/auth-storage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('ordens/api', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    setTokens({ access_token: 't', refresh_token: 'r' })
  })

  it('listar monta a query string (fase/cliente/tipo/q/offset/limit)', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ items: [], total: 0 }))
    vi.stubGlobal('fetch', f)
    await ordensApi.listar({ fase: 5, cliente: 12, tipo: 'C', q: 'abc', offset: 25, limit: 25 })
    const url = String(f.mock.calls[0][0])
    expect(url).toContain('/ordens?')
    expect(url).toContain('fase=5')
    expect(url).toContain('cliente=12')
    expect(url).toContain('tipo=C')
    expect(url).toContain('q=abc')
    expect(url).toContain('offset=25')
  })

  it('listar omite chaves ausentes mas sempre manda offset/limit', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ items: [], total: 0 }))
    vi.stubGlobal('fetch', f)
    await ordensApi.listar({})
    const url = String(f.mock.calls[0][0])
    expect(url).not.toContain('fase=')
    expect(url).not.toContain('cliente=')
    expect(url).toContain('offset=0')
    expect(url).toContain('limit=25')
  })

  it('quadro bate em /ordens/quadro (com e sem cliente)', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse([]))
    vi.stubGlobal('fetch', f)
    await ordensApi.quadro({})
    expect(String(f.mock.calls[0][0])).toContain('/ordens/quadro')
    await ordensApi.quadro({ cliente: 7 })
    expect(String(f.mock.calls[1][0])).toContain('/ordens/quadro?cliente=7')
  })

  it('obter e logs nos paths certos', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({}))
    vi.stubGlobal('fetch', f)
    await ordensApi.obter(42)
    expect(String(f.mock.calls[0][0])).toContain('/ordens/42')
    await ordensApi.logs(42)
    expect(String(f.mock.calls[1][0])).toContain('/ordens/42/logs')
  })

  it('propaga ApiError em resposta não-ok', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ detail: 'x' }, 404))
    vi.stubGlobal('fetch', f)
    await expect(ordensApi.obter(99)).rejects.toMatchObject({ status: 404 })
  })
})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm --prefix frontend run test -- ordens/api`
Expected: FAIL (Cannot find module './api').

- [ ] **Step 3: Criar `frontend/src/app/ordens/api.ts`**

```ts
import { apiJson } from '../../lib/api'

export type TipoServico = 'C' | 'M' | 'A'

export const TIPO_SERVICO: Record<TipoServico, { label: string; tone: 'primary' | 'warning' | 'neutral' }> = {
  C: { label: 'Calibração', tone: 'primary' },
  M: { label: 'Manutenção', tone: 'warning' },
  A: { label: 'Ambas', tone: 'neutral' },
}

export const FASES_FILTRO: { id: number; label: string }[] = [
  { id: 4, label: 'Recebido' },
  { id: 5, label: 'Laboratório' },
  { id: 6, label: 'Pós-Vendas' },
  { id: 7, label: 'Preparando Retorno' },
  { id: 8, label: 'Finalizada' },
  { id: 9, label: 'Cancelada' },
]

export function formatData(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return isNaN(d.getTime()) ? '—' : d.toLocaleDateString('pt-BR')
}

export interface OrdemListItem {
  id: number
  cliente: number
  cliente_nome: string | null
  equipamento_cliente: number | null
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

export interface OrdemPage {
  items: OrdemListItem[]
  total: number
}

export interface QuadroColuna {
  fase: number
  descricao: string
  cor: string
  ordens: OrdemListItem[]
}

export interface OrdemDetalhe extends OrdemListItem {
  condicao_chegada: string | null
  acessorios: string | null
  aceite: boolean
  recebido: boolean
  etiqueta: string | null
  cod_retorno: string | null
  obs: string | null
  data_calibracao: string | null
  data_retorno: string | null
  data_aceite: string | null
  calib_cert: string | null
  calib_temp: string | null
  calib_pressao: string | null
  calib_teste_media: string | null
  calib_situacao: string | null
  pdf_certificado: string | null
}

export interface LogOS {
  id: number
  os: number
  usuario: number | null
  autor: string
  datalog: string | null
  texto: string | null
}

export interface OrdensParams {
  fase?: number
  cliente?: number
  tipo?: string
  q?: string
  offset?: number
  limit?: number
}

export const ordensApi = {
  listar: (params: OrdensParams = {}): Promise<OrdemPage> => {
    const sp = new URLSearchParams()
    if (params.fase != null) sp.set('fase', String(params.fase))
    if (params.cliente != null) sp.set('cliente', String(params.cliente))
    if (params.tipo) sp.set('tipo', params.tipo)
    if (params.q) sp.set('q', params.q)
    sp.set('offset', String(params.offset ?? 0))
    sp.set('limit', String(params.limit ?? 25))
    return apiJson<OrdemPage>(`/ordens?${sp.toString()}`)
  },
  quadro: (params: { cliente?: number } = {}): Promise<QuadroColuna[]> => {
    const sp = new URLSearchParams()
    if (params.cliente != null) sp.set('cliente', String(params.cliente))
    const qs = sp.toString()
    return apiJson<QuadroColuna[]>(`/ordens/quadro${qs ? `?${qs}` : ''}`)
  },
  obter: (id: number): Promise<OrdemDetalhe> => apiJson<OrdemDetalhe>(`/ordens/${id}`),
  logs: (id: number): Promise<LogOS[]> => apiJson<LogOS[]>(`/ordens/${id}/logs`),
}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `npm --prefix frontend run test -- ordens/api`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/app/ordens/api.ts frontend/src/app/ordens/api.test.ts
git -C /d/GitHub/GestorHS commit -m "feat(frontend): api client da OS (ordensApi) + testes"
```

---

### Task 2: `funcoesApi` + `fasesApi` em cadastros/api.ts

**Files:**
- Modify: `frontend/src/app/cadastros/api.ts`
- Test: `frontend/src/app/cadastros/fases-funcoes.api.test.ts`

- [ ] **Step 1: Escrever os testes falhando** — `frontend/src/app/cadastros/fases-funcoes.api.test.ts`:

```ts
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { funcoesApi, fasesApi } from './api'
import { setTokens } from '../../lib/auth-storage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('cadastros/api — funcoes e fases', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    setTokens({ access_token: 't', refresh_token: 'r' })
  })

  it('funcoesApi.criar faz POST /funcoes', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ id: 1, descricao: 'X' }, 201))
    vi.stubGlobal('fetch', f)
    await funcoesApi.criar({ descricao: 'X' })
    expect(String(f.mock.calls[0][0])).toContain('/funcoes')
    expect(f.mock.calls[0][1]).toMatchObject({ method: 'POST' })
  })

  it('funcoesApi.excluir propaga 409', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ detail: 'registro em uso' }, 409))
    vi.stubGlobal('fetch', f)
    await expect(funcoesApi.excluir(3)).rejects.toMatchObject({ status: 409 })
  })

  it('fasesApi.listar faz GET /fases', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse([]))
    vi.stubGlobal('fetch', f)
    await fasesApi.listar()
    expect(String(f.mock.calls[0][0])).toContain('/fases')
  })

  it('fasesApi.atualizar faz PATCH /fases/{id} com funcao_responsavel', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ id: 4, descricao: 'Recebido', cor: '3b82f6', funcao_responsavel: 2, funcao_nome: 'Expedição' }))
    vi.stubGlobal('fetch', f)
    await fasesApi.atualizar(4, { funcao_responsavel: 2 })
    expect(String(f.mock.calls[0][0])).toContain('/fases/4')
    expect(f.mock.calls[0][1]).toMatchObject({ method: 'PATCH' })
    expect(String(f.mock.calls[0][1].body)).toContain('funcao_responsavel')
  })
})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm --prefix frontend run test -- cadastros/fases-funcoes`
Expected: FAIL (funcoesApi/fasesApi não exportados).

- [ ] **Step 3: Adicionar ao FIM de `frontend/src/app/cadastros/api.ts`**

```ts
export interface Funcao {
  id: number
  descricao: string
}

export const funcoesApi = crudClient<Funcao, { descricao: string }, { descricao?: string }>('/funcoes')

export interface Fase {
  id: number
  descricao: string
  cor: string
  funcao_responsavel: number | null
  funcao_nome: string | null
}

export const fasesApi = {
  listar: (): Promise<Fase[]> => apiJson<Fase[]>('/fases'),
  atualizar: (id: number, payload: { funcao_responsavel: number | null }): Promise<Fase> =>
    apiJson<Fase>(`/fases/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
}
```

> `crudClient` e `apiJson` já estão no topo do arquivo. `funcoesApi` adere ao formato `SimpleClient<Funcao>` exigido por `CadastroSimples`.

- [ ] **Step 4: Rodar e ver passar**

Run: `npm --prefix frontend run test -- cadastros/fases-funcoes`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/app/cadastros/api.ts frontend/src/app/cadastros/fases-funcoes.api.test.ts
git -C /d/GitHub/GestorHS commit -m "feat(frontend): funcoesApi (CRUD) + fasesApi (config funcao->fase)"
```

---

### Task 3: Nav "Ordens" + `OrdensPage` (quadro + lista) + rota

**Files:**
- Modify: `frontend/src/components/ui/icons.tsx` (adicionar `IconOrdens`)
- Modify: `frontend/src/layout/Sidebar.tsx` (NAV_ITEM)
- Create: `frontend/src/app/ordens/OrdensPage.tsx`
- Modify: `frontend/src/app/routes.tsx`

> Telas seguem o padrão do projeto: verificadas por `tsc`/`lint`/`build` (sem teste de componente).

- [ ] **Step 1: Adicionar `IconOrdens` em `frontend/src/components/ui/icons.tsx`** (ao lado dos outros ícones):

```tsx
export function IconOrdens({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
    </svg>
  )
}
```

- [ ] **Step 2: Adicionar o item de nav em `frontend/src/layout/Sidebar.tsx`**

Importe `IconOrdens` no import de `../components/ui/icons` e adicione ao `NAV_ITEMS` (depois de Frota, sem `adminOnly`):
```tsx
  { label: 'Ordens', icon: <IconOrdens />, to: '/app/ordens' },
```

- [ ] **Step 3: Criar `frontend/src/app/ordens/OrdensPage.tsx`**

```tsx
import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Spinner } from '../../components/ui/Spinner'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { cn } from '../../lib/utils'
import { ApiError } from '../../lib/api'
import { ordensApi, TIPO_SERVICO, FASES_FILTRO, formatData, type OrdemListItem, type QuadroColuna } from './api'

const LIMITE = 25
type Vista = 'quadro' | 'lista'

function tipoBadge(tipo: string | null) {
  if (!tipo || !(tipo in TIPO_SERVICO)) return null
  const t = TIPO_SERVICO[tipo as keyof typeof TIPO_SERVICO]
  return <Badge tone={t.tone}>{t.label}</Badge>
}

export function OrdensPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const clienteParam = searchParams.get('cliente')
  const clienteId = clienteParam ? Number(clienteParam) : undefined
  const [vista, setVista] = useState<Vista>('quadro')

  return (
    <div className="px-4 md:px-6 py-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-extrabold text-slate-100">Ordens de Serviço</h1>
        <div className="flex gap-2">
          {(['quadro', 'lista'] as Vista[]).map((v) => (
            <button
              key={v}
              onClick={() => setVista(v)}
              className={cn(
                'text-xs px-3 py-1.5 rounded-full font-medium transition-all',
                vista === v ? 'bg-primary/15 text-primary' : 'text-slate-500 hover:text-slate-300 hover:bg-background-elevated',
              )}
            >
              {v === 'quadro' ? 'Quadro' : 'Lista'}
            </button>
          ))}
        </div>
      </div>

      {clienteId && (
        <div className="flex items-center gap-2 text-sm">
          <span className="rounded-full bg-primary/10 text-primary px-3 py-1 font-medium">Cliente #{clienteId}</span>
          <button onClick={() => navigate('/app/ordens')} className="text-xs text-slate-400 hover:text-slate-200">limpar</button>
        </div>
      )}

      {vista === 'quadro' ? (
        <Quadro clienteId={clienteId} onAbrir={(id) => navigate(`/app/ordens/${id}`)} />
      ) : (
        <Lista clienteId={clienteId} onAbrir={(id) => navigate(`/app/ordens/${id}`)} />
      )}
    </div>
  )
}

function Quadro({ clienteId, onAbrir }: { clienteId?: number; onAbrir: (id: number) => void }) {
  const [colunas, setColunas] = useState<QuadroColuna[] | null>(null)
  const [erro, setErro] = useState('')

  useEffect(() => {
    let ativo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setColunas(null)
    setErro('')
    ordensApi
      .quadro({ cliente: clienteId })
      .then((c) => {
        if (ativo) setColunas(c)
      })
      .catch((e) => {
        if (!ativo) return
        setErro(e instanceof ApiError ? e.message : 'Falha ao carregar')
        setColunas([])
      })
    return () => {
      ativo = false
    }
  }, [clienteId])

  if (erro) return <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>
  if (colunas === null) return <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>

  return (
    <div className="flex gap-4 overflow-x-auto pb-2">
      {colunas.map((col) => (
        <div key={col.fase} className="w-72 shrink-0 rounded-2xl bg-background-surface border border-border">
          <div className="flex items-center justify-between px-4 py-3 border-b border-border">
            <span className="inline-flex items-center gap-2 text-sm font-semibold text-slate-100">
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: `#${col.cor}` }} />
              {col.descricao}
            </span>
            <span className="text-xs text-slate-500">{col.ordens.length}</span>
          </div>
          <div className="p-3 space-y-2 max-h-[70vh] overflow-y-auto">
            {col.ordens.length === 0 ? (
              <p className="text-xs text-slate-600 px-1">—</p>
            ) : (
              col.ordens.map((o) => (
                <button
                  key={o.id}
                  onClick={() => onAbrir(o.id)}
                  className="w-full text-left rounded-xl bg-background-elevated border border-border p-3 hover:border-primary/40 transition-colors"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-semibold text-slate-100">OS #{o.id}</span>
                    {tipoBadge(o.tipo_servico)}
                  </div>
                  <p className="text-xs text-slate-300 mt-1 truncate">{o.cliente_nome ?? '—'}</p>
                  <p className="text-xs text-slate-500 truncate">
                    {o.equipamento_descricao ?? '—'}
                    {o.equipamento_serie ? ` · ${o.equipamento_serie}` : ''}
                  </p>
                  <p className="text-[11px] text-slate-600 mt-1">chegou {formatData(o.data_chegada)}</p>
                </button>
              ))
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

function Lista({ clienteId, onAbrir }: { clienteId?: number; onAbrir: (id: number) => void }) {
  const [fase, setFase] = useState('')
  const [tipo, setTipo] = useState('')
  const [termo, setTermo] = useState('')
  const [busca, setBusca] = useState('')
  const [offset, setOffset] = useState(0)
  const [itens, setItens] = useState<OrdemListItem[] | null>(null)
  const [total, setTotal] = useState(0)
  const [erro, setErro] = useState('')

  useEffect(() => {
    let ativo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setItens(null)
    setErro('')
    ordensApi
      .listar({ fase: fase ? Number(fase) : undefined, cliente: clienteId, tipo: tipo || undefined, q: busca || undefined, offset, limit: LIMITE })
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
  }, [fase, tipo, busca, clienteId, offset])

  function onBuscar(e: FormEvent) {
    e.preventDefault()
    setOffset(0)
    setBusca(termo.trim())
  }

  const inicio = total === 0 ? 0 : offset + 1
  const fim = Math.min(offset + LIMITE, total)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 items-end">
        <div className="w-44">
          <Select id="fase" label="Fase" value={fase} onChange={(e) => { setOffset(0); setFase(e.target.value) }}>
            <option value="">Todas</option>
            {FASES_FILTRO.map((f) => <option key={f.id} value={f.id}>{f.label}</option>)}
          </Select>
        </div>
        <div className="w-40">
          <Select id="tipo" label="Tipo" value={tipo} onChange={(e) => { setOffset(0); setTipo(e.target.value) }}>
            <option value="">Todos</option>
            <option value="C">Calibração</option>
            <option value="M">Manutenção</option>
            <option value="A">Ambas</option>
          </Select>
        </div>
        <form onSubmit={onBuscar} className="flex gap-2 items-end flex-1 min-w-60">
          <div className="flex-1">
            <Input id="busca" label="Busca" placeholder="Nº da OS, etiqueta ou cliente" value={termo} onChange={(e) => setTermo(e.target.value)} />
          </div>
          <Button type="submit" variant="secondary">Buscar</Button>
        </form>
      </div>

      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}

      {itens === null ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhuma OS encontrada.</p>
      ) : (
        <>
          <Table head={<><TH>OS</TH><TH>Cliente</TH><TH>Equipamento</TH><TH>Fase</TH><TH>Tipo</TH><TH>Chegada</TH><TH>Situação</TH></>}>
            {itens.map((o) => (
              <tr key={o.id} className="hover:bg-background-elevated transition-colors cursor-pointer" onClick={() => onAbrir(o.id)}>
                <TD>#{o.id}</TD>
                <TD>{o.cliente_nome ?? '—'}</TD>
                <TD>{o.equipamento_descricao ?? '—'}</TD>
                <TD>
                  {o.fase_descricao ? (
                    <span className="inline-flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full" style={{ background: `#${o.fase_cor}` }} />
                      {o.fase_descricao}
                    </span>
                  ) : '—'}
                </TD>
                <TD>{tipoBadge(o.tipo_servico) ?? '—'}</TD>
                <TD>{formatData(o.data_chegada)}</TD>
                <TD>{o.situacao}</TD>
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

Importe e adicione (perto das rotas de frota):
```tsx
import { OrdensPage } from './ordens/OrdensPage'
```
```tsx
        <Route path="ordens" element={<OrdensPage />} />
```

- [ ] **Step 5: Verificar lint + build**

Run: `npm --prefix frontend run lint`
Expected: sem erros.
Run: `npm --prefix frontend run build`
Expected: `tsc -b` sem erros + build conclui.

- [ ] **Step 6: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/components/ui/icons.tsx frontend/src/layout/Sidebar.tsx frontend/src/app/ordens/OrdensPage.tsx frontend/src/app/routes.tsx
git -C /d/GitHub/GestorHS commit -m "feat(frontend): pagina de OS (kanban + lista) + nav Ordens"
```

---

### Task 4: `OrdemDetailPage` (detalhe só-leitura) + rota

**Files:**
- Create: `frontend/src/app/ordens/OrdemDetailPage.tsx`
- Modify: `frontend/src/app/routes.tsx`

- [ ] **Step 1: Criar `frontend/src/app/ordens/OrdemDetailPage.tsx`**

```tsx
import { useEffect, useState, type ReactNode } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Spinner } from '../../components/ui/Spinner'
import { ApiError } from '../../lib/api'
import { ordensApi, TIPO_SERVICO, formatData, type OrdemDetalhe, type LogOS } from './api'

function Campo({ label, valor }: { label: string; valor: ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="text-sm text-slate-200">{valor ?? '—'}</dd>
    </div>
  )
}

export function OrdemDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const osId = Number(id)
  const [os, setOs] = useState<OrdemDetalhe | null>(null)
  const [logs, setLogs] = useState<LogOS[]>([])
  const [erro, setErro] = useState('')
  const [carregando, setCarregando] = useState(true)

  useEffect(() => {
    let ativo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCarregando(true)
    setErro('')
    Promise.all([ordensApi.obter(osId), ordensApi.logs(osId)])
      .then(([o, l]) => {
        if (!ativo) return
        setOs(o)
        setLogs(l)
      })
      .catch((e) => {
        if (!ativo) return
        setErro(e instanceof ApiError && e.status === 404 ? 'OS não encontrada' : 'Falha ao carregar')
      })
      .finally(() => {
        if (ativo) setCarregando(false)
      })
    return () => {
      ativo = false
    }
  }, [osId])

  if (carregando) return <div className="flex justify-center py-16"><Spinner className="w-8 h-8" /></div>
  if (erro || !os)
    return (
      <div className="px-4 md:px-6 py-6 space-y-4">
        <p className="text-sm text-danger">{erro || 'OS não encontrada'}</p>
        <Button variant="secondary" onClick={() => navigate('/app/ordens')}>Voltar</Button>
      </div>
    )

  const tipo = os.tipo_servico && os.tipo_servico in TIPO_SERVICO ? TIPO_SERVICO[os.tipo_servico as keyof typeof TIPO_SERVICO].label : '—'
  const temCalib = os.calib_cert || os.calib_temp || os.calib_pressao || os.calib_teste_media || os.calib_situacao || os.pdf_certificado

  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-extrabold text-slate-100">OS #{os.id}</h1>
          {os.fase_descricao && (
            <Badge tone="neutral">
              <span className="inline-flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full" style={{ background: `#${os.fase_cor}` }} />
                {os.fase_descricao}
              </span>
            </Badge>
          )}
        </div>
        <Button variant="secondary" onClick={() => navigate('/app/ordens')}>Voltar</Button>
      </div>

      <section className="rounded-2xl bg-background-surface border border-border p-5 grid grid-cols-2 md:grid-cols-4 gap-4">
        <Campo label="Cliente" valor={os.cliente_nome} />
        <Campo label="Equipamento" valor={os.equipamento_descricao} />
        <Campo label="Série" valor={os.equipamento_serie} />
        <Campo label="Situação" valor={os.situacao} />
      </section>

      <section className="rounded-2xl bg-background-surface border border-border p-5 space-y-3">
        <h2 className="text-sm font-semibold text-slate-100">Recebimento</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Campo label="Tipo de serviço" valor={tipo} />
          <Campo label="Condição de chegada" valor={os.condicao_chegada} />
          <Campo label="Acessórios" valor={os.acessorios} />
          <Campo label="Data de chegada" valor={formatData(os.data_chegada)} />
        </div>
      </section>

      <section className="rounded-2xl bg-background-surface border border-border p-5 space-y-3">
        <h2 className="text-sm font-semibold text-slate-100">Datas</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Campo label="Calibração" valor={formatData(os.data_calibracao)} />
          <Campo label="Aceite" valor={formatData(os.data_aceite)} />
          <Campo label="Retorno (postagem)" valor={formatData(os.data_retorno)} />
          <Campo label="Próxima calibração" valor={formatData(os.prox_calibragem)} />
        </div>
      </section>

      <section className="rounded-2xl bg-background-surface border border-border p-5 space-y-3">
        <h2 className="text-sm font-semibold text-slate-100">Resultados da calibração</h2>
        {temCalib ? (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <Campo label="Certificado" valor={os.calib_cert} />
            <Campo label="Temperatura" valor={os.calib_temp} />
            <Campo label="Pressão" valor={os.calib_pressao} />
            <Campo label="Média dos testes" valor={os.calib_teste_media} />
            <Campo label="Situação" valor={os.calib_situacao} />
            <Campo label="PDF" valor={os.pdf_certificado} />
          </div>
        ) : (
          <p className="text-sm text-slate-500">Sem resultados de calibração ainda.</p>
        )}
      </section>

      <section className="rounded-2xl bg-background-surface border border-border p-5 space-y-3">
        <h2 className="text-sm font-semibold text-slate-100">Histórico</h2>
        {logs.length === 0 ? (
          <p className="text-sm text-slate-500">Sem eventos.</p>
        ) : (
          <ol className="space-y-2">
            {logs.map((l) => (
              <li key={l.id} className="flex gap-3 text-sm">
                <span className="text-xs text-slate-500 shrink-0 w-28">{formatData(l.datalog)}</span>
                <span className="text-slate-200">{l.texto ?? '—'}</span>
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  )
}
```

- [ ] **Step 2: Registrar a rota em `frontend/src/app/routes.tsx`**

```tsx
import { OrdemDetailPage } from './ordens/OrdemDetailPage'
```
```tsx
        <Route path="ordens/:id" element={<OrdemDetailPage />} />
```

- [ ] **Step 3: Verificar lint + build**

Run: `npm --prefix frontend run lint`
Expected: sem erros.
Run: `npm --prefix frontend run build`
Expected: sem erros.

- [ ] **Step 4: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/app/ordens/OrdemDetailPage.tsx frontend/src/app/routes.tsx
git -C /d/GitHub/GestorHS commit -m "feat(frontend): pagina de detalhe da OS (so-leitura + timeline de logs)"
```

---

### Task 5: Abas Funções e Fases na CadastrosPage

**Files:**
- Create: `frontend/src/app/cadastros/FasesPanel.tsx`
- Modify: `frontend/src/app/cadastros/CadastrosPage.tsx`

- [ ] **Step 1: Criar `frontend/src/app/cadastros/FasesPanel.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { Table, TH, TD } from '../../components/ui/Table'
import { Select } from '../../components/ui/Select'
import { Spinner } from '../../components/ui/Spinner'
import { ApiError } from '../../lib/api'
import { fasesApi, funcoesApi, type Fase, type Funcao } from './api'

export function FasesPanel() {
  const [fases, setFases] = useState<Fase[] | null>(null)
  const [funcoes, setFuncoes] = useState<Funcao[]>([])
  const [erro, setErro] = useState('')

  useEffect(() => {
    let ativo = true
    Promise.all([fasesApi.listar(), funcoesApi.listar()])
      .then(([fs, fns]) => {
        if (!ativo) return
        setFases(fs)
        setFuncoes(fns)
      })
      .catch((e) => {
        if (!ativo) return
        setErro(e instanceof ApiError ? e.message : 'Falha ao carregar')
        setFases([])
      })
    return () => {
      ativo = false
    }
  }, [])

  async function mudar(fase: Fase, valor: string) {
    setErro('')
    const funcao_responsavel = valor ? Number(valor) : null
    try {
      const atualizada = await fasesApi.atualizar(fase.id, { funcao_responsavel })
      setFases((prev) => prev?.map((f) => (f.id === atualizada.id ? atualizada : f)) ?? prev)
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao salvar')
    }
  }

  if (fases === null) return <div className="flex justify-center py-10"><Spinner className="w-7 h-7" /></div>

  return (
    <div className="space-y-4">
      <h2 className="text-sm font-semibold text-slate-100">Fases — responsável por fase</h2>
      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      <Table head={<><TH>Fase</TH><TH>Responsável</TH></>}>
        {fases.map((f) => (
          <tr key={f.id} className="hover:bg-background-elevated transition-colors">
            <TD>
              <span className="inline-flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: `#${f.cor}` }} />
                {f.descricao}
              </span>
            </TD>
            <TD>
              <Select id={`fase-${f.id}`} value={f.funcao_responsavel ?? ''} onChange={(e) => mudar(f, e.target.value)}>
                <option value="">— sem responsável —</option>
                {funcoes.map((fn) => <option key={fn.id} value={fn.id}>{fn.descricao}</option>)}
              </Select>
            </TD>
          </tr>
        ))}
      </Table>
    </div>
  )
}
```

- [ ] **Step 2: Adicionar as abas em `frontend/src/app/cadastros/CadastrosPage.tsx`**

Atualize os imports:
```tsx
import { CadastroSimples } from './CadastroSimples'
import { GruposPanel } from './GruposPanel'
import { CategoriasPanel } from './CategoriasPanel'
import { EquipamentosPanel } from './EquipamentosPanel'
import { FasesPanel } from './FasesPanel'
import { setoresApi, marcasApi, funcoesApi, type Setor, type Marca, type Funcao } from './api'
```
Atualize o array de abas:
```tsx
const ABAS = ['Setores', 'Marcas', 'Grupos', 'Categorias', 'Equipamentos', 'Funções', 'Fases'] as const
```
Adicione os dois ramos de render (dentro do bloco que escolhe o painel pela `aba`):
```tsx
        {aba === 'Funções' && <CadastroSimples<Funcao> titulo="Funções" client={funcoesApi} />}
        {aba === 'Fases' && <FasesPanel />}
```

- [ ] **Step 3: Verificar lint + build**

Run: `npm --prefix frontend run lint`
Expected: sem erros.
Run: `npm --prefix frontend run build`
Expected: sem erros.

- [ ] **Step 4: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/app/cadastros/FasesPanel.tsx frontend/src/app/cadastros/CadastrosPage.tsx
git -C /d/GitHub/GestorHS commit -m "feat(frontend): abas Funcoes e Fases (config funcao->fase) em Cadastros"
```

---

### Task 6: Verificação final (test + lint + build)

**Files:** nenhum (verificação).

- [ ] **Step 1: Suíte de testes completa**

Run: `npm --prefix frontend run test`
Expected: todos verdes (os testes anteriores do frontend + os 9 novos desta fase).

- [ ] **Step 2: Lint**

Run: `npm --prefix frontend run lint`
Expected: sem erros nem warnings.

- [ ] **Step 3: Build**

Run: `npm --prefix frontend run build`
Expected: `tsc -b` limpo + `vite build` conclui sem erro.

- [ ] **Step 4: (sem commit — etapa de verificação)**

Reporte o número de testes e qualquer aviso. Se algo falhar, corrija na task correspondente.

---

## Notas para o executor

- Telas (Tasks 3–5) seguem o padrão do projeto: **sem teste de componente**; a verificação é `tsc -b`/`lint`/`build` limpos + E2E manual depois. Só a lógica de API (Tasks 1–2) tem Vitest.
- A regra `react-hooks/set-state-in-effect`: o `// eslint-disable-next-line` vai SOMENTE na 1ª chamada de setState síncrona no corpo do efeito (já marcada no código acima). Não adicione disables onde não há aviso.
- `Select` aceita `label` opcional — no `FasesPanel` ele é usado sem label (dentro da célula da tabela).
- Cores das fases vêm como hex de 6 dígitos sem `#` (ex.: `3b82f6`) — por isso `style={{ background: \`#${cor}\` }}`.
- Nada de escrita de OS (abrir/avançar/cancelar) nesta fase — isso é 3D.
- Após a Task 6, o controlador roda o E2E manual (Playwright/navegador) contra o banco real antes de finalizar a branch.
```
