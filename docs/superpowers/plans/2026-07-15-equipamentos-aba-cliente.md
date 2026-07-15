# Equipamentos como aba na página do cliente — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans para implementar tarefa a tarefa. Passos usam checkbox (`- [ ]`).

**Goal:** Transformar `clientes/:id` num layout com abas **Dados | Equipamentos**, permitindo navegar entre dados do cliente, lista de equipamentos dele e o detalhe de um aparelho sem sair da página, reusando a tela de detalhe existente.

**Architecture:** Rotas aninhadas (React Router). `clientes/:id` vira `ClienteLayout` (cabeçalho + abas + `<Outlet/>`). Filhos: índice = `ClienteDadosTab` (form), `equipamentos` = `ClienteEquipamentosTab` (lista simples), `equipamentos/novo` e `equipamentos/:aparelho` = `EquipamentoClienteDetailPage` reusada em modo `embutido`. `clientes/novo` continua standalone. O form do cliente é extraído para `ClienteFormFields` (usado pelo novo e pela aba Dados).

**Tech Stack:** React 19 · TS · React Router · Vitest + Testing Library · Tailwind v4.

## Global Constraints

- Idioma do domínio **PT-BR** em nomes, rotas e textos.
- Permissões inalteradas: **Novo aparelho / Excluir / Transferir** = `isAdmin`; **Abrir OS** = `podeAbrirOS`; edição de campos read-only para não-admin.
- Verificação de frontend antes de fechar: `npm run lint && npx tsc -b --noEmit && npm run build` e `npm test`.
- Não duplicar a tela de detalhe do aparelho — ela é reusada via prop `embutido`.
- Não alterar a página global `/app/equipamentos` nem o link de aparelho vindo da OS.
- Commits Conventional Commits em PT-BR sem acentos, uma linha, sem trailer de co-autor.

---

### Task 1: `ClienteEquipamentosTab` — lista simples do cliente

**Files:**
- Create: `frontend/src/app/clientes/ClienteEquipamentosTab.tsx`
- Test: `frontend/src/app/clientes/ClienteEquipamentosTab.test.tsx`

**Interfaces:**
- Consumes: `equipamentosClienteApi.listar({ cliente })` de `../frota/api` (retorna `{ items: FrotaItem[]; total }`), `STATUS_CALIBRACAO`, `Table/TH/TD`, `Button`, `Badge`, `Spinner`, `isAdmin`, `useAuth`.
- Produces: `export function ClienteEquipamentosTab()` — lê o cliente do path via `useParams().id`; renderiza a lista; row → `navigate(String(item.id))` (relativo, resolve para `equipamentos/:aparelho`); "Novo aparelho" (admin) → `navigate('novo')`.

- [ ] **Step 1: Escrever o teste que falha**

```tsx
// ClienteEquipamentosTab.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

let mockUser: { funcao: string | null } | null = { funcao: 'Administrador' }
vi.mock('../../auth/AuthContext', () => ({ useAuth: () => ({ user: mockUser }) }))

const listar = vi.fn()
vi.mock('../frota/api', async (orig) => {
  const real = await orig<typeof import('../frota/api')>()
  return { ...real, equipamentosClienteApi: { listar } }
})

import { ClienteEquipamentosTab } from './ClienteEquipamentosTab'

function renderTab() {
  return render(
    <MemoryRouter initialEntries={['/app/clientes/5/equipamentos']}>
      <Routes>
        <Route path="/app/clientes/:id/equipamentos" element={<ClienteEquipamentosTab />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ClienteEquipamentosTab', () => {
  beforeEach(() => {
    mockUser = { funcao: 'Administrador' }
    listar.mockReset()
  })

  it('lista os aparelhos do cliente', async () => {
    listar.mockResolvedValue({ items: [
      { id: 1, cliente: 5, cliente_nome: 'ACME', equipamento: 9, equipamento_descricao: 'Bafômetro X',
        serie: 'SN-1', patrimonio: null, prox_calibragem: '2026-08-01', ativo: true, status: 'A', status_calibracao: 'em_dia' },
    ], total: 1 })
    renderTab()
    expect(await screen.findByText('Bafômetro X')).toBeInTheDocument()
    expect(listar).toHaveBeenCalledWith({ cliente: 5 })
  })

  it('mostra vazio quando não há aparelhos', async () => {
    listar.mockResolvedValue({ items: [], total: 0 })
    renderTab()
    expect(await screen.findByText(/Nenhum aparelho/i)).toBeInTheDocument()
  })

  it('esconde "Novo aparelho" para não-admin', async () => {
    mockUser = { funcao: 'Expedição' }
    listar.mockResolvedValue({ items: [], total: 0 })
    renderTab()
    await screen.findByText(/Nenhum aparelho/i)
    expect(screen.queryByText('Novo aparelho')).toBeNull()
  })
})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd frontend && npx vitest run src/app/clientes/ClienteEquipamentosTab.test.tsx`
Expected: FAIL — módulo `./ClienteEquipamentosTab` não existe.

- [ ] **Step 3: Implementar o componente**

```tsx
// ClienteEquipamentosTab.tsx
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Spinner } from '../../components/ui/Spinner'
import { ApiError } from '../../lib/api'
import { useAuth } from '../../auth/AuthContext'
import { isAdmin } from '../../auth/roles'
import { equipamentosClienteApi, STATUS_CALIBRACAO, type FrotaItem } from '../frota/api'

export function ClienteEquipamentosTab() {
  const { id } = useParams()
  const clienteId = Number(id)
  const navigate = useNavigate()
  const { user } = useAuth()
  const [itens, setItens] = useState<FrotaItem[] | null>(null)
  const [erro, setErro] = useState('')

  useEffect(() => {
    let ativo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setItens(null)
    setErro('')
    equipamentosClienteApi
      .listar({ cliente: clienteId })
      .then((p) => { if (ativo) setItens(p.items) })
      .catch((e) => {
        if (!ativo) return
        setErro(e instanceof ApiError ? e.message : 'Falha ao carregar')
        setItens([])
      })
    return () => { ativo = false }
  }, [clienteId])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-100">Equipamentos do cliente</h2>
        {isAdmin(user) && <Button onClick={() => navigate('novo')}>Novo aparelho</Button>}
      </div>

      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}

      {itens === null ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum aparelho cadastrado para este cliente.</p>
      ) : (
        <Table head={<><TH>Aparelho</TH><TH>Série / Patrimônio</TH><TH>Próx. calibração</TH><TH>Status</TH></>}>
          {itens.map((e) => {
            const s = STATUS_CALIBRACAO[e.status_calibracao]
            return (
              <tr key={e.id} className="hover:bg-background-elevated transition-colors cursor-pointer" onClick={() => navigate(String(e.id))}>
                <TD>{e.equipamento_descricao ?? '—'}</TD>
                <TD>{e.serie || e.patrimonio || '—'}</TD>
                <TD>{e.prox_calibragem ?? '—'}</TD>
                <TD><Badge tone={s.tone}>{s.label}</Badge></TD>
              </tr>
            )
          })}
        </Table>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `cd frontend && npx vitest run src/app/clientes/ClienteEquipamentosTab.test.tsx`
Expected: PASS (3 testes).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/clientes/ClienteEquipamentosTab.tsx frontend/src/app/clientes/ClienteEquipamentosTab.test.tsx
git commit -m "feat(frota): aba de equipamentos do cliente (lista)"
```

---

### Task 2: Extrair `ClienteFormFields` (refactor puro)

**Files:**
- Create: `frontend/src/app/clientes/ClienteFormFields.tsx`
- Modify: `frontend/src/app/clientes/ClienteDetailPage.tsx` (passa a usar o novo componente)

**Interfaces:**
- Produces: `export function ClienteFormFields(props)` com:
  ```ts
  interface ClienteFormFieldsProps {
    form: ClientePayload
    set: <K extends keyof ClientePayload>(chave: K, valor: ClientePayload[K]) => void
    grupos: Grupo[]
    readOnly: boolean
    podeEditar: boolean
    enviando: boolean
    labelSubmit: string   // "Salvar alterações" | "Criar cliente"
    onSubmit: (e: FormEvent) => void
  }
  ```
  Renderiza o `<form onSubmit>` com as seções Identificação / Endereço / Contatos / Observações e o botão de submit (quando `podeEditar`). É o mesmo JSX de `formConteudo` + `<form>` que hoje vive em `ClienteDetailPage`.
- Consumes: `ClientePayload` de `./api`, `Grupo` de `../cadastros/api`, `Input`, `Select`.

- [ ] **Step 1: Criar `ClienteFormFields.tsx`**

Mover para cá o helper `txt`, o componente local `Secao`, e todo o JSX de `formConteudo` (linhas ~112–172 de `ClienteDetailPage.tsx`) embrulhado em `<form className="space-y-6" onSubmit={onSubmit}>`. Assinatura conforme o bloco Interfaces. Sem lógica de fetch/salvar — puramente apresentacional.

```tsx
// ClienteFormFields.tsx (esqueleto — mover o JSX existente para dentro)
import type { FormEvent, ReactNode } from 'react'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import type { ClientePayload } from './api'
import type { Grupo } from '../cadastros/api'

function Secao({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <div className="rounded-2xl bg-background-surface border border-border p-5 space-y-4">
      <h2 className="text-sm font-semibold text-slate-100">{titulo}</h2>
      {children}
    </div>
  )
}

interface ClienteFormFieldsProps {
  form: ClientePayload
  set: <K extends keyof ClientePayload>(chave: K, valor: ClientePayload[K]) => void
  grupos: Grupo[]
  readOnly: boolean
  podeEditar: boolean
  enviando: boolean
  labelSubmit: string
  onSubmit: (e: FormEvent) => void
}

export function ClienteFormFields({ form, set, grupos, readOnly: ro, podeEditar, enviando, labelSubmit, onSubmit }: ClienteFormFieldsProps) {
  const txt = (label: string, chave: keyof ClientePayload) => (
    <Input id={`c-${chave}`} label={label} value={(form[chave] as string | null) ?? ''}
      onChange={(e) => set(chave, (e.target.value || null) as ClientePayload[typeof chave])} disabled={ro} />
  )
  return (
    <form className="space-y-6" onSubmit={onSubmit}>
      {/* … mover aqui as 4 <Secao> exatamente como estão em ClienteDetailPage … */}
      {podeEditar && (
        <button type="submit" disabled={enviando} className="w-full py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-60 transition-all">
          {labelSubmit}
        </button>
      )}
    </form>
  )
}
```

- [ ] **Step 2: `ClienteDetailPage` passa a usar `ClienteFormFields`**

Substituir, no `ClienteDetailPage`, o `formConteudo`/`<form>` inline por `<ClienteFormFields ... />`, mantendo estado, fetch e `salvar` como estão. `labelSubmit={editando ? 'Salvar alterações' : 'Criar cliente'}`. Remover o `Secao` e o `txt` locais que sobraram. Nenhuma mudança de comportamento.

- [ ] **Step 3: Verificar sem regressão**

Run: `cd frontend && npx tsc -b --noEmit && npm test`
Expected: tipos OK; suíte verde (inclui `clientes/api.test.ts`).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/clientes/ClienteFormFields.tsx frontend/src/app/clientes/ClienteDetailPage.tsx
git commit -m "refactor(clientes): extrai ClienteFormFields do detalhe do cliente"
```

---

### Task 3: `ClienteLayout` + `ClienteDadosTab` e rotas aninhadas

**Files:**
- Create: `frontend/src/app/clientes/ClienteLayout.tsx`
- Create: `frontend/src/app/clientes/ClienteDadosTab.tsx`
- Modify: `frontend/src/app/routes.tsx`
- Test: `frontend/src/app/clientes/ClienteLayout.test.tsx`

**Interfaces:**
- `ClienteLayout` (rota `clientes/:id`): busca `clientesApi.obter(id)`; guarda `cliente` + função `recarregar` num state; renderiza cabeçalho (título = `cliente.nome`, botões **Excluir** (admin) e **Voltar** → `/app/clientes`), barra de abas com dois `NavLink` (`.` = Dados, `equipamentos` = Equipamentos, `end` no de Dados) e `<Outlet context={{ cliente, recarregar } satisfies ClienteCtx} />`. Exporta `type ClienteCtx = { cliente: Cliente; recarregar: () => void }` e um hook `useCliente()` = `useOutletContext<ClienteCtx>()`.
- `ClienteDadosTab` (rota índice): `const { cliente } = useCliente()`; estado de form seed do `cliente`; `salvar` via `clientesApi.atualizar` (chama `recarregar` no sucesso); renderiza `<ClienteFormFields labelSubmit="Salvar alterações" .../>` na `DetailMain` e `FuncionariosSection`/`UsuariosPortalSection` na `DetailAside` (como hoje no aside do editando).
- Consumes: `ClienteFormFields` (Task 2), `clientesApi`, `gruposApi`, `Button`, `PageContainer/DetailGrid/DetailMain/DetailAside`, `NavLink/Outlet/useOutletContext`, `cn`.

- [ ] **Step 1: Escrever o teste de roteamento que falha**

```tsx
// ClienteLayout.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

vi.mock('../../auth/AuthContext', () => ({ useAuth: () => ({ user: { funcao: 'Administrador' } }) }))

const obter = vi.fn()
const atualizar = vi.fn()
vi.mock('./api', async (orig) => {
  const real = await orig<typeof import('./api')>()
  return { ...real, clientesApi: { ...real.clientesApi, obter, atualizar } }
})
vi.mock('../cadastros/api', () => ({ gruposApi: { listar: () => Promise.resolve([]) } }))
vi.mock('./FuncionariosSection', () => ({ FuncionariosSection: () => <div>funcionarios</div> }))
vi.mock('./UsuariosPortalSection', () => ({ UsuariosPortalSection: () => <div>portal</div> }))
const listar = vi.fn().mockResolvedValue({ items: [], total: 0 })
vi.mock('../frota/api', async (orig) => {
  const real = await orig<typeof import('../frota/api')>()
  return { ...real, equipamentosClienteApi: { listar } }
})

import { ClienteLayout, ClienteCtx } from './ClienteLayout'
import { ClienteDadosTab } from './ClienteDadosTab'
import { ClienteEquipamentosTab } from './ClienteEquipamentosTab'

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/app/clientes/:id" element={<ClienteLayout />}>
          <Route index element={<ClienteDadosTab />} />
          <Route path="equipamentos" element={<ClienteEquipamentosTab />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

describe('ClienteLayout (abas por URL)', () => {
  beforeEach(() => {
    obter.mockResolvedValue({ id: 5, nome: 'ACME', ativo: true })
  })

  it('na raiz mostra a aba Dados (form do cliente)', async () => {
    renderAt('/app/clientes/5')
    expect(await screen.findByText('ACME')).toBeInTheDocument()
    expect(await screen.findByText('Salvar alterações')).toBeInTheDocument()
  })

  it('em /equipamentos mostra a lista, não o form', async () => {
    renderAt('/app/clientes/5/equipamentos')
    expect(await screen.findByText(/Nenhum aparelho/i)).toBeInTheDocument()
    expect(screen.queryByText('Salvar alterações')).toBeNull()
  })
})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd frontend && npx vitest run src/app/clientes/ClienteLayout.test.tsx`
Expected: FAIL — `./ClienteLayout` / `./ClienteDadosTab` não existem.

- [ ] **Step 3: Implementar `ClienteLayout.tsx`**

```tsx
import { useCallback, useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate, useOutletContext, useParams } from 'react-router-dom'
import { Button } from '../../components/ui/Button'
import { Spinner } from '../../components/ui/Spinner'
import { ApiError } from '../../lib/api'
import { useAuth } from '../../auth/AuthContext'
import { isAdmin } from '../../auth/roles'
import { cn } from '../../lib/utils'
import { PageContainer } from '../../components/ui/Page'
import { clientesApi, type Cliente } from './api'

export type ClienteCtx = { cliente: Cliente; recarregar: () => void }
export function useCliente() { return useOutletContext<ClienteCtx>() }

const abaCls = ({ isActive }: { isActive: boolean }) =>
  cn('text-xs px-3 py-1.5 rounded-full font-medium transition-all',
    isActive ? 'bg-primary/15 text-primary' : 'text-slate-500 hover:text-slate-300 hover:bg-background-elevated')

export function ClienteLayout() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const [cliente, setCliente] = useState<Cliente | null>(null)
  const [erro, setErro] = useState('')
  const [recarga, setRecarga] = useState(0)
  const recarregar = useCallback(() => setRecarga((n) => n + 1), [])

  useEffect(() => {
    let ativo = true
    setErro('')
    clientesApi.obter(Number(id))
      .then((c) => { if (ativo) setCliente(c) })
      .catch((e) => { if (ativo) setErro(e instanceof ApiError ? e.message : 'Falha ao carregar') })
    return () => { ativo = false }
  }, [id, recarga])

  async function excluir() {
    if (!window.confirm('Excluir este cliente?')) return
    setErro('')
    try {
      await clientesApi.excluir(Number(id))
      navigate('/app/clientes', { replace: true })
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao excluir')
    }
  }

  if (erro && !cliente) {
    return <PageContainer><div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div></PageContainer>
  }
  if (!cliente) {
    return <div className="flex justify-center py-16"><Spinner className="w-8 h-8" /></div>
  }

  return (
    <PageContainer>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-extrabold text-slate-100">{cliente.nome || 'Cliente'}</h1>
        <div className="flex gap-2">
          {isAdmin(user) && <Button variant="danger" onClick={excluir}>Excluir</Button>}
          <Button variant="secondary" onClick={() => navigate('/app/clientes')}>Voltar</Button>
        </div>
      </div>

      <div className="flex gap-2">
        <NavLink to="." end className={abaCls}>Dados</NavLink>
        <NavLink to="equipamentos" className={abaCls}>Equipamentos</NavLink>
      </div>

      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}

      <Outlet context={{ cliente, recarregar } satisfies ClienteCtx} />
    </PageContainer>
  )
}
```

- [ ] **Step 4: Implementar `ClienteDadosTab.tsx`**

Estado do form seed do `cliente` do contexto (mesmo mapeamento de campos do `ClienteDetailPage` de hoje). `salvar` → `clientesApi.atualizar(cliente.id, form)` e no sucesso `recarregar()`. Layout `DetailGrid` com `ClienteFormFields` no `DetailMain` e `FuncionariosSection`/`UsuariosPortalSection` no `DetailAside`.

```tsx
import { useEffect, useState, type FormEvent } from 'react'
import { ApiError } from '../../lib/api'
import { useAuth } from '../../auth/AuthContext'
import { isAdmin } from '../../auth/roles'
import { clientesApi, type ClientePayload } from './api'
import { gruposApi, type Grupo } from '../cadastros/api'
import { ClienteFormFields } from './ClienteFormFields'
import { FuncionariosSection } from './FuncionariosSection'
import { UsuariosPortalSection } from './UsuariosPortalSection'
import { DetailGrid, DetailMain, DetailAside } from '../../components/ui/Page'
import { useCliente } from './ClienteLayout'

export function ClienteDadosTab() {
  const { cliente, recarregar } = useCliente()
  const { user } = useAuth()
  const podeEditar = isAdmin(user)
  const [grupos, setGrupos] = useState<Grupo[]>([])
  const [form, setForm] = useState<ClientePayload>(() => paraForm(cliente))
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  useEffect(() => { void gruposApi.listar().then(setGrupos).catch(() => setGrupos([])) }, [])
  // re-seed se o cliente recarregar
  useEffect(() => { setForm(paraForm(cliente)) }, [cliente])

  function set<K extends keyof ClientePayload>(chave: K, valor: ClientePayload[K]) {
    setForm((f) => ({ ...f, [chave]: valor }))
  }
  async function salvar(e: FormEvent) {
    e.preventDefault(); setErro(''); setEnviando(true)
    try { await clientesApi.atualizar(cliente.id, form); recarregar() }
    catch (err) { setErro(err instanceof ApiError ? err.message : 'Falha ao salvar') }
    finally { setEnviando(false) }
  }

  return (
    <>
      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      <DetailGrid>
        <DetailMain>
          <ClienteFormFields form={form} set={set} grupos={grupos} readOnly={!podeEditar}
            podeEditar={podeEditar} enviando={enviando} labelSubmit="Salvar alterações" onSubmit={salvar} />
        </DetailMain>
        <DetailAside>
          <FuncionariosSection clienteId={cliente.id} podeEditar={podeEditar} />
          {podeEditar && <UsuariosPortalSection clienteId={cliente.id} />}
        </DetailAside>
      </DetailGrid>
    </>
  )
}

function paraForm(c: import('./api').Cliente): ClientePayload {
  return {
    nome: c.nome ?? '', grupo: c.grupo, cgc: c.cgc, cpf: c.cpf, endereco: c.endereco, numero: c.numero,
    complemento: c.complemento, bairro: c.bairro, municipio: c.municipio, estado: c.estado, cep: c.cep,
    contato: c.contato, email: c.email, telefones: c.telefones, celular: c.celular, whatsapp: c.whatsapp,
    whatsapp1: c.whatsapp1, whatsapp2: c.whatsapp2, insc_mun: c.insc_mun, insc_est: c.insc_est, obs: c.obs, ativo: c.ativo,
  }
}
```

- [ ] **Step 5: Rewire das rotas em `routes.tsx`**

Importar `ClienteLayout`, `ClienteDadosTab`, `ClienteEquipamentosTab`. Trocar a linha `clientes/:id` folha por rota com filhos. Manter `clientes/novo` no `ClienteDetailPage`.

```tsx
// substituir  <Route path="clientes/:id" element={<ClienteDetailPage />} />  por:
<Route path="clientes/:id" element={<ClienteLayout />}>
  <Route index element={<ClienteDadosTab />} />
  <Route path="equipamentos" element={<ClienteEquipamentosTab />} />
</Route>
```

(As rotas `equipamentos/novo` e `equipamentos/:aparelho` entram na Task 4.)

- [ ] **Step 6: Trocar o botão "Equipamentos" pela navegação da aba nos callers**

Em `ClienteDetailPage.tsx`: **remover** o botão "Equipamentos" (linha ~180) — ele não faz sentido no cadastro novo (única rota que ainda usa esse componente).
Em `alertas/CobrancaPage.tsx:102` e `solicitacoes/SolicitacoesPage.tsx:79`: trocar `navigate(\`/app/equipamentos?cliente=${...}\`)` por `navigate(\`/app/clientes/${...}/equipamentos\`)`.

- [ ] **Step 7: Rodar testes**

Run: `cd frontend && npx vitest run src/app/clientes/ClienteLayout.test.tsx && npx tsc -b --noEmit`
Expected: PASS (2 testes) e tipos OK.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/app/clientes/ClienteLayout.tsx frontend/src/app/clientes/ClienteDadosTab.tsx frontend/src/app/clientes/ClienteLayout.test.tsx frontend/src/app/routes.tsx frontend/src/app/clientes/ClienteDetailPage.tsx frontend/src/app/alertas/CobrancaPage.tsx frontend/src/app/solicitacoes/SolicitacoesPage.tsx
git commit -m "feat(clientes): pagina do cliente com abas Dados e Equipamentos"
```

---

### Task 4: Modo `embutido` no detalhe do aparelho + rotas aninhadas do detalhe

**Files:**
- Modify: `frontend/src/app/frota/EquipamentoClienteDetailPage.tsx`
- Modify: `frontend/src/app/routes.tsx`
- Test: `frontend/src/app/frota/EquipamentoClienteDetailPage.embutido.test.tsx`

**Interfaces:**
- `EquipamentoClienteDetailPage({ embutido }: { embutido?: boolean })`.
  - Resolução de ids (sem fallback cruzado):
    - `embutido`: `aparelhoId = params.aparelho` (na rota `.../novo` é `undefined` → cria); `clienteId = Number(params.id)`.
    - global (hoje): `aparelhoId = params.id`; `clienteId = Number(searchParams.get('cliente')) || 0`.
  - `editando = aparelhoId !== undefined`.
  - Alvo do "Voltar" e dos `navigate` de criar/excluir/erro:
    - `voltarBase = embutido ? \`/app/clientes/${clienteId}/equipamentos\` : '/app/equipamentos'`.
    - Voltar → `voltarBase`; criar novo → `\`${voltarBase}/${novo.id}\``; excluir → `voltarBase`.
- Rotas: `<EquipamentoClienteDetailPage embutido />` sob `clientes/:id`.

- [ ] **Step 1: Escrever o teste que falha (alvo do "Voltar" muda por modo)**

```tsx
// EquipamentoClienteDetailPage.embutido.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

vi.mock('../../auth/AuthContext', () => ({ useAuth: () => ({ user: { funcao: 'Administrador' } }) }))
const obter = vi.fn()
vi.mock('./api', async (orig) => {
  const real = await orig<typeof import('./api')>()
  return { ...real, equipamentosClienteApi: {
    obter,
    historico: () => Promise.resolve([]), ordens: () => Promise.resolve([]),
    certificados: () => Promise.resolve([]), transferencias: () => Promise.resolve([]),
  } }
})
vi.mock('../cadastros/api', () => ({ equipamentosApi: { listar: () => Promise.resolve([]) } }))

import { EquipamentoClienteDetailPage } from './EquipamentoClienteDetailPage'

function tela() {
  return render(
    <MemoryRouter initialEntries={['/app/clientes/5/equipamentos/9']}>
      <Routes>
        <Route path="/app/clientes/:id/equipamentos/:aparelho" element={<EquipamentoClienteDetailPage embutido />} />
        <Route path="/app/clientes/:id/equipamentos" element={<div>lista do cliente</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('EquipamentoClienteDetailPage (embutido)', () => {
  beforeEach(() => {
    obter.mockResolvedValue({ id: 9, cliente: 5, cliente_nome: 'ACME', equipamento: 1, equipamento_descricao: 'Bafômetro X',
      modulo: 0, serie: 'SN', patrimonio: null, datacompra: null, ult_calibragem: null, prox_calibragem: null,
      ativo: true, status: 'A', status_calibracao: 'em_dia', os_atual: null,
      calib_cert: null, calib_temp: null, calib_pressao: null, calib_teste1: null, calib_teste2: null, calib_teste3: null, calib_teste_media: null, calib_situacao: null })
  })

  it('carrega o aparelho da rota aninhada (params.aparelho)', async () => {
    tela()
    expect(await screen.findByText('Bafômetro X')).toBeInTheDocument()
    expect(obter).toHaveBeenCalledWith(9)
  })

  it('"Voltar" leva para a aba de equipamentos do cliente', async () => {
    const { getByText } = tela()
    await screen.findByText('Bafômetro X')
    getByText('Voltar').click()
    expect(await screen.findByText('lista do cliente')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd frontend && npx vitest run src/app/frota/EquipamentoClienteDetailPage.embutido.test.tsx`
Expected: FAIL — hoje o componente lê `params.id` (=5, o cliente) como aparelho e o "Voltar" vai para `/app/equipamentos`.

- [ ] **Step 3: Adaptar o componente**

No `EquipamentoClienteDetailPage`, adicionar a prop e trocar a resolução de ids e os alvos de navegação:

```tsx
export function EquipamentoClienteDetailPage({ embutido = false }: { embutido?: boolean } = {}) {
  const params = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  // ...
  const aparelhoId = embutido ? params.aparelho : params.id
  const editando = aparelhoId !== undefined
  const clienteId = embutido ? Number(params.id) : (searchParams.get('cliente') ? Number(searchParams.get('cliente')) : 0)
  const voltarBase = embutido ? `/app/clientes/${clienteId}/equipamentos` : '/app/equipamentos'
```

Substituir os usos de `Number(id)` por `Number(aparelhoId)` (obter/historico/ordens/certificados/transferencias e o `useEffect` dep), e os literais de navegação:
- `navigate('/app/equipamentos')` (Voltar, excluir, fallback "Ir para os Equipamentos") → `navigate(voltarBase)`.
- criar: `navigate(\`/app/equipamentos/${novo.id}\`, { replace: true })` → `navigate(\`${voltarBase}/${novo.id}\`, { replace: true })`.
Manter o `<Link to={\`/app/clientes/${obj.cliente}\`}>` (contexto do cliente) como está.

- [ ] **Step 4: Adicionar as rotas aninhadas do detalhe em `routes.tsx`**

Dentro do `<Route path="clientes/:id" element={<ClienteLayout />}>`, após a rota `equipamentos`:

```tsx
<Route path="equipamentos/novo" element={<EquipamentoClienteDetailPage embutido />} />
<Route path="equipamentos/:aparelho" element={<EquipamentoClienteDetailPage embutido />} />
```

- [ ] **Step 5: Rodar e ver passar**

Run: `cd frontend && npx vitest run src/app/frota/EquipamentoClienteDetailPage.embutido.test.tsx && npx tsc -b --noEmit`
Expected: PASS (2 testes) e tipos OK.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/frota/EquipamentoClienteDetailPage.tsx frontend/src/app/frota/EquipamentoClienteDetailPage.embutido.test.tsx frontend/src/app/routes.tsx
git commit -m "feat(frota): detalhe do aparelho embutido na pagina do cliente"
```

---

### Task 5: Changelog + verificação completa

**Files:**
- Modify: `frontend/src/app/changelog/data.ts`

- [ ] **Step 1: Adicionar entrada de versão (bump)**

Adicionar como primeira entrada de `CHANGELOG` (a versão atual). Manter a numeração seguindo a última (após v1.14.1 → **v1.15.0**, mudança visível ao usuário):

```ts
{
  versao: '1.15.0',
  data: '15/07/2026',
  itens: [
    { tipo: 'melhoria', texto: 'A página de um cliente agora tem abas Dados e Equipamentos. Em "Equipamentos" você vê a lista de aparelhos daquele cliente e abre o detalhe de cada um sem sair da página, facilitando ir e voltar entre os dados do cliente e os equipamentos dele.' },
  ],
},
```

- [ ] **Step 2: Verificação completa**

Run: `cd frontend && npm run lint && npx tsc -b --noEmit && npm run build && npm test`
Expected: lint limpo, tipos OK, build OK, todos os testes verdes.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/changelog/data.ts
git commit -m "docs(changelog): v1.15.0 — equipamentos como aba na pagina do cliente"
```

---

## Self-Review (feita)

- **Cobertura da spec:** layout com abas (Task 3), lista simples (Task 1), reuso do detalhe via `embutido` (Task 4), rotas aninhadas e resolução de params sem ambiguidade (Tasks 3–4), callers atualizados (Task 3 step 6), changelog (Task 5). ✔
- **Sem placeholders:** todo passo tem código/edição concreta e comando com resultado esperado. O único "mover o JSX" (Task 2) referencia linhas exatas do arquivo existente. ✔
- **Consistência de tipos:** `ClienteCtx`/`useCliente` definidos na Task 3 e consumidos por `ClienteDadosTab`; `ClienteFormFieldsProps` definido na Task 2 e usado na Task 3; `embutido` definido na Task 4 e usado nas rotas. Nomes de params (`:id` cliente, `:aparelho` aparelho) consistentes entre spec, componente e rotas. ✔
