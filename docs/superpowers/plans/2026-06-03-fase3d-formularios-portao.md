# Fase 3D (Formulários-portão — ações de escrita da OS) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ações de escrita da OS no frontend — abrir (da Frota), avançar (formulário-portão por fase) e cancelar — consumindo os endpoints da 3B, gateadas por função.

**Architecture:** Estende `ordens/api.ts` com `abrir`/`avancar`/`cancelar` + `TRANSICOES`; adiciona `podeAbrirOS` em `auth/roles.ts`; cria 3 modais (`AbrirOSModal`, `AvancarModal`, `CancelarModal`) e os liga ao detalhe da OS (avançar/cancelar, gateado pelo responsável da fase via `/fases`) e ao detalhe do aparelho na Frota (abrir). Backend é a autoridade (403/409/422 exibidos inline).

**Tech Stack:** React 19, TypeScript 6, Vite 8, Tailwind v4, react-router-dom 7, Vitest.

**Spec:** `docs/superpowers/specs/2026-06-03-fase3d-formularios-portao-design.md`

**Comandos** (raiz `d:\GitHub\GestorHS`): `npm --prefix frontend run test`, `npm --prefix frontend run lint`, `npm --prefix frontend run build`. Git via `git -C /d/GitHub/GestorHS`. Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

**Branch:** antes da Task 1:
```bash
git -C /d/GitHub/GestorHS checkout -b feat/fase3d-formularios-portao
```

## Convenções (já estabelecidas)
- `apiJson(path, {method, body})` lança `ApiError{status,message}` em resposta não-ok. Métodos de escrita retornam a OS (usam `apiJson`, não `apiVoid`).
- `Modal` (props `open`/`onClose`/`title`/`footer`/children): conteúdo via `<form id="x">`, botões no `footer` com `form="x"` (ver `CadastroSimples`). `Button` variants: primary/secondary/danger. `Select`/`Input` com `label`.
- Telas/modais: verificadas por `tsc -b`/`lint`/`build` (sem teste de componente). Só a lógica de api/roles tem Vitest.

---

### Task 1: Métodos de escrita em `ordens/api.ts` + `TRANSICOES`

**Files:**
- Modify: `frontend/src/app/ordens/api.ts`
- Test: `frontend/src/app/ordens/api.test.ts` (estender)

- [ ] **Step 1: Adicionar os testes falhando** — acrescente ao FIM do `describe('ordens/api', ...)` em `frontend/src/app/ordens/api.test.ts` (antes do `})` que fecha o describe):

```ts
  it('abrir faz POST /ordens com o corpo certo', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ id: 1 }, 201))
    vi.stubGlobal('fetch', f)
    await ordensApi.abrir({ equipamento_cliente: 7, tipo_servico: 'C', condicao_chegada: 'ok', acessorios: null })
    expect(String(f.mock.calls[0][0])).toContain('/ordens')
    expect(f.mock.calls[0][1]).toMatchObject({ method: 'POST' })
    const body = String(f.mock.calls[0][1].body)
    expect(body).toContain('equipamento_cliente')
    expect(body).toContain('tipo_servico')
  })

  it('avancar faz POST /ordens/{id}/avancar com obs/cod_retorno', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ id: 1 }))
    vi.stubGlobal('fetch', f)
    await ordensApi.avancar(5, { obs: 'x', cod_retorno: 'BR9' })
    expect(String(f.mock.calls[0][0])).toContain('/ordens/5/avancar')
    expect(f.mock.calls[0][1]).toMatchObject({ method: 'POST' })
    expect(String(f.mock.calls[0][1].body)).toContain('cod_retorno')
  })

  it('cancelar faz POST /ordens/{id}/cancelar com motivo', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ id: 1 }))
    vi.stubGlobal('fetch', f)
    await ordensApi.cancelar(9, { motivo: 'desistência' })
    expect(String(f.mock.calls[0][0])).toContain('/ordens/9/cancelar')
    expect(String(f.mock.calls[0][1].body)).toContain('motivo')
  })

  it('abrir propaga ApiError 409', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ detail: 'aparelho já possui OS ativa' }, 409))
    vi.stubGlobal('fetch', f)
    await expect(ordensApi.abrir({ equipamento_cliente: 7, tipo_servico: 'C' })).rejects.toMatchObject({ status: 409 })
  })
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm --prefix frontend run test -- ordens/api`
Expected: FAIL (abrir/avancar/cancelar não existem em ordensApi).

- [ ] **Step 3: Estender `frontend/src/app/ordens/api.ts`**

Adicione, logo após a definição de `OrdensParams` (antes de `export const ordensApi`):
```ts
export interface AbrirPayload {
  equipamento_cliente: number
  tipo_servico: TipoServico
  condicao_chegada?: string | null
  acessorios?: string | null
}

export interface AvancarPayload {
  obs?: string | null
  cod_retorno?: string | null
}

export const TRANSICOES: Record<number, { rotulo: string; pedeCodRetorno?: boolean }> = {
  4: { rotulo: 'Encaminhar ao laboratório' },
  5: { rotulo: 'Concluir laboratório' },
  6: { rotulo: 'Registrar aceite' },
  7: { rotulo: 'Postar retorno', pedeCodRetorno: true },
}
```
E dentro do objeto `ordensApi`, após o método `logs`, adicione:
```ts
  abrir: (payload: AbrirPayload): Promise<OrdemDetalhe> =>
    apiJson<OrdemDetalhe>('/ordens', { method: 'POST', body: JSON.stringify(payload) }),
  avancar: (id: number, payload: AvancarPayload): Promise<OrdemDetalhe> =>
    apiJson<OrdemDetalhe>(`/ordens/${id}/avancar`, { method: 'POST', body: JSON.stringify(payload) }),
  cancelar: (id: number, payload: { motivo: string }): Promise<OrdemDetalhe> =>
    apiJson<OrdemDetalhe>(`/ordens/${id}/cancelar`, { method: 'POST', body: JSON.stringify(payload) }),
```

- [ ] **Step 4: Rodar e ver passar**

Run: `npm --prefix frontend run test -- ordens/api`
Expected: PASS (9 testes — 5 da 3C + 4 novos).

- [ ] **Step 5: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/app/ordens/api.ts frontend/src/app/ordens/api.test.ts
git -C /d/GitHub/GestorHS commit -m "feat(frontend): ordensApi abrir/avancar/cancelar + TRANSICOES"
```

---

### Task 2: `podeAbrirOS` em `auth/roles.ts`

**Files:**
- Modify: `frontend/src/auth/roles.ts`
- Test: `frontend/src/auth/roles.test.ts`

- [ ] **Step 1: Escrever o teste falhando** — `frontend/src/auth/roles.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { podeAbrirOS } from './roles'
import { type User } from './AuthContext'

function u(funcao: string | null): User {
  return { id: 1, nome: 'x', login: 'x', funcao } as User
}

describe('auth/roles — podeAbrirOS', () => {
  it('admin pode', () => expect(podeAbrirOS(u('Administrador'))).toBe(true))
  it('Expedição pode', () => expect(podeAbrirOS(u('Expedição'))).toBe(true))
  it('Laboratório não pode', () => expect(podeAbrirOS(u('Laboratório'))).toBe(false))
  it('null não pode', () => expect(podeAbrirOS(null)).toBe(false))
})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm --prefix frontend run test -- auth/roles`
Expected: FAIL (podeAbrirOS não exportado).

> Se o `tsc`/o teste reclamar do shape de `User` no helper `u()`, ajuste os campos do objeto para o mínimo que o tipo `User` exige (veja `frontend/src/auth/AuthContext.tsx`), mantendo `funcao` como a chave testada. O `as User` cobre campos faltantes.

- [ ] **Step 3: Estender `frontend/src/auth/roles.ts`**

```ts
export const FUNCAO_EXPEDICAO = 'Expedição'

export function podeAbrirOS(user: User | null): boolean {
  return isAdmin(user) || user?.funcao === FUNCAO_EXPEDICAO
}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `npm --prefix frontend run test -- auth/roles`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/auth/roles.ts frontend/src/auth/roles.test.ts
git -C /d/GitHub/GestorHS commit -m "feat(frontend): helper podeAbrirOS (Expedicao ou admin)"
```

---

### Task 3: `AvancarModal` + `CancelarModal` + ações no detalhe da OS

**Files:**
- Create: `frontend/src/app/ordens/AvancarModal.tsx`
- Create: `frontend/src/app/ordens/CancelarModal.tsx`
- Modify: `frontend/src/app/ordens/OrdemDetailPage.tsx`

> UI — verificada por `lint` + `build`.

- [ ] **Step 1: Criar `frontend/src/app/ordens/AvancarModal.tsx`**

```tsx
import { useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { ApiError } from '../../lib/api'
import { ordensApi, type OrdemDetalhe } from './api'

export function AvancarModal({ os, rotulo, pedeCodRetorno, onClose, onConcluido }: {
  os: OrdemDetalhe
  rotulo: string
  pedeCodRetorno?: boolean
  onClose: () => void
  onConcluido: (os: OrdemDetalhe) => void
}) {
  const [obs, setObs] = useState('')
  const [codRetorno, setCodRetorno] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function submeter(e: FormEvent) {
    e.preventDefault()
    setErro('')
    if (pedeCodRetorno && !codRetorno.trim()) {
      setErro('Código de retorno é obrigatório.')
      return
    }
    setEnviando(true)
    try {
      const atualizada = await ordensApi.avancar(os.id, {
        obs: obs.trim() || null,
        cod_retorno: pedeCodRetorno ? codRetorno.trim() : null,
      })
      onConcluido(atualizada)
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao avançar')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={rotulo}
      footer={
        <>
          <button type="button" onClick={onClose} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">Cancelar</button>
          <button type="submit" form="form-avancar" disabled={enviando} className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all">Confirmar</button>
        </>
      }
    >
      <form id="form-avancar" className="space-y-4" onSubmit={submeter}>
        {pedeCodRetorno && (
          <Input id="cod-retorno" label="Código de retorno" value={codRetorno} onChange={(e) => setCodRetorno(e.target.value)} required />
        )}
        <div>
          <label htmlFor="obs" className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">Observação</label>
          <textarea id="obs" value={obs} onChange={(e) => setObs(e.target.value)} rows={3} className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-background-elevated text-slate-300 focus:outline-none focus:ring-2 focus:ring-primary/50" />
        </div>
        {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      </form>
    </Modal>
  )
}
```

- [ ] **Step 2: Criar `frontend/src/app/ordens/CancelarModal.tsx`**

```tsx
import { useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { ApiError } from '../../lib/api'
import { ordensApi, type OrdemDetalhe } from './api'

export function CancelarModal({ os, onClose, onConcluido }: {
  os: OrdemDetalhe
  onClose: () => void
  onConcluido: (os: OrdemDetalhe) => void
}) {
  const [motivo, setMotivo] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function submeter(e: FormEvent) {
    e.preventDefault()
    setErro('')
    if (!motivo.trim()) {
      setErro('Motivo é obrigatório.')
      return
    }
    setEnviando(true)
    try {
      const atualizada = await ordensApi.cancelar(os.id, { motivo: motivo.trim() })
      onConcluido(atualizada)
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao cancelar')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={`Cancelar OS #${os.id}`}
      footer={
        <>
          <button type="button" onClick={onClose} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">Voltar</button>
          <button type="submit" form="form-cancelar" disabled={enviando} className="flex-1 py-2.5 rounded-lg bg-danger text-white text-sm font-semibold hover:bg-danger-600 disabled:opacity-50 transition-all">Cancelar OS</button>
        </>
      }
    >
      <form id="form-cancelar" className="space-y-4" onSubmit={submeter}>
        <div>
          <label htmlFor="motivo" className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">Motivo</label>
          <textarea id="motivo" value={motivo} onChange={(e) => setMotivo(e.target.value)} rows={3} className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-background-elevated text-slate-300 focus:outline-none focus:ring-2 focus:ring-primary/50" />
        </div>
        {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      </form>
    </Modal>
  )
}
```

- [ ] **Step 3: Reescrever `frontend/src/app/ordens/OrdemDetailPage.tsx`** com o conteúdo completo abaixo (adiciona busca de fases, gating e botões/modais):

```tsx
import { useEffect, useState, type ReactNode } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Spinner } from '../../components/ui/Spinner'
import { ApiError } from '../../lib/api'
import { useAuth } from '../../auth/AuthContext'
import { isAdmin } from '../../auth/roles'
import { fasesApi, type Fase } from '../cadastros/api'
import { ordensApi, TIPO_SERVICO, TRANSICOES, formatData, type OrdemDetalhe, type LogOS } from './api'
import { AvancarModal } from './AvancarModal'
import { CancelarModal } from './CancelarModal'

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
  const { user } = useAuth()
  const osId = Number(id)
  const [os, setOs] = useState<OrdemDetalhe | null>(null)
  const [logs, setLogs] = useState<LogOS[]>([])
  const [fases, setFases] = useState<Fase[]>([])
  const [erro, setErro] = useState('')
  const [carregando, setCarregando] = useState(true)
  const [acao, setAcao] = useState<'avancar' | 'cancelar' | null>(null)

  useEffect(() => {
    let ativo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCarregando(true)
    setErro('')
    Promise.all([ordensApi.obter(osId), ordensApi.logs(osId), fasesApi.listar()])
      .then(([o, l, fs]) => {
        if (!ativo) return
        setOs(o)
        setLogs(l)
        setFases(fs)
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

  function aoConcluir(novaOS: OrdemDetalhe) {
    setOs(novaOS)
    setAcao(null)
    void ordensApi.logs(osId).then(setLogs).catch(() => {})
  }

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
  const faseAtual = fases.find((f) => f.id === os.fase)
  const responsavelNome = faseAtual?.funcao_nome ?? null
  const podeAgir = isAdmin(user) || (!!responsavelNome && user?.funcao === responsavelNome)
  const ativa = os.fase != null && os.fase >= 4 && os.fase <= 7
  const transicao = os.fase != null ? TRANSICOES[os.fase] : undefined

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
        <div className="flex gap-2">
          {ativa && podeAgir && transicao && <Button onClick={() => setAcao('avancar')}>{transicao.rotulo}</Button>}
          {ativa && podeAgir && <Button variant="danger" onClick={() => setAcao('cancelar')}>Cancelar OS</Button>}
          <Button variant="secondary" onClick={() => navigate('/app/ordens')}>Voltar</Button>
        </div>
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

      {acao === 'avancar' && transicao && (
        <AvancarModal os={os} rotulo={transicao.rotulo} pedeCodRetorno={transicao.pedeCodRetorno} onClose={() => setAcao(null)} onConcluido={aoConcluir} />
      )}
      {acao === 'cancelar' && <CancelarModal os={os} onClose={() => setAcao(null)} onConcluido={aoConcluir} />}
    </div>
  )
}
```

- [ ] **Step 4: Verificar lint + build**

Run: `npm --prefix frontend run lint`
Expected: sem erros.
Run: `npm --prefix frontend run build`
Expected: limpo.

- [ ] **Step 5: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/app/ordens/AvancarModal.tsx frontend/src/app/ordens/CancelarModal.tsx frontend/src/app/ordens/OrdemDetailPage.tsx
git -C /d/GitHub/GestorHS commit -m "feat(frontend): avancar/cancelar OS no detalhe (gateado por funcao)"
```

---

### Task 4: `AbrirOSModal` + botão "Abrir OS" na Frota

**Files:**
- Create: `frontend/src/app/ordens/AbrirOSModal.tsx`
- Modify: `frontend/src/app/frota/EquipamentoClienteDetailPage.tsx`

- [ ] **Step 1: Criar `frontend/src/app/ordens/AbrirOSModal.tsx`**

```tsx
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Modal } from '../../components/ui/Modal'
import { Select } from '../../components/ui/Select'
import { ApiError } from '../../lib/api'
import { ordensApi, type TipoServico } from './api'

export function AbrirOSModal({ equipamentoClienteId, osAtual, onClose }: {
  equipamentoClienteId: number
  osAtual: number | null
  onClose: () => void
}) {
  const navigate = useNavigate()
  const [tipo, setTipo] = useState<TipoServico>('C')
  const [condicao, setCondicao] = useState('')
  const [acessorios, setAcessorios] = useState('')
  const [erro, setErro] = useState('')
  const [osAtivaId, setOsAtivaId] = useState<number | null>(null)
  const [enviando, setEnviando] = useState(false)

  async function submeter(e: FormEvent) {
    e.preventDefault()
    setErro('')
    setOsAtivaId(null)
    setEnviando(true)
    try {
      const os = await ordensApi.abrir({
        equipamento_cliente: equipamentoClienteId,
        tipo_servico: tipo,
        condicao_chegada: condicao.trim() || null,
        acessorios: acessorios.trim() || null,
      })
      navigate(`/app/ordens/${os.id}`)
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setErro('Este aparelho já possui uma OS ativa.')
        setOsAtivaId(osAtual)
      } else {
        setErro(err instanceof ApiError ? err.message : 'Falha ao abrir OS')
      }
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Abrir OS"
      footer={
        <>
          <button type="button" onClick={onClose} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">Cancelar</button>
          <button type="submit" form="form-abrir-os" disabled={enviando} className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all">Abrir</button>
        </>
      }
    >
      <form id="form-abrir-os" className="space-y-4" onSubmit={submeter}>
        <Select id="tipo-servico" label="Tipo de serviço" value={tipo} onChange={(e) => setTipo(e.target.value as TipoServico)}>
          <option value="C">Calibração</option>
          <option value="M">Manutenção</option>
          <option value="A">Ambas</option>
        </Select>
        <div>
          <label htmlFor="condicao" className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">Condição de chegada</label>
          <textarea id="condicao" value={condicao} onChange={(e) => setCondicao(e.target.value)} rows={2} className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-background-elevated text-slate-300 focus:outline-none focus:ring-2 focus:ring-primary/50" />
        </div>
        <div>
          <label htmlFor="acessorios" className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">Acessórios</label>
          <textarea id="acessorios" value={acessorios} onChange={(e) => setAcessorios(e.target.value)} rows={2} className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-background-elevated text-slate-300 focus:outline-none focus:ring-2 focus:ring-primary/50" />
        </div>
        {erro && (
          <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger space-y-2">
            <p>{erro}</p>
            {osAtivaId && (
              <button type="button" onClick={() => navigate(`/app/ordens/${osAtivaId}`)} className="text-xs font-semibold text-primary hover:underline">Ver OS atual</button>
            )}
          </div>
        )}
      </form>
    </Modal>
  )
}
```

- [ ] **Step 2: Ligar na `frota/EquipamentoClienteDetailPage.tsx`** — quatro edições pontuais:

(a) No import de roles, troque:
```tsx
import { isAdmin } from '../../auth/roles'
```
por:
```tsx
import { isAdmin, podeAbrirOS } from '../../auth/roles'
import { AbrirOSModal } from '../ordens/AbrirOSModal'
```

(b) Logo após `const [enviando, setEnviando] = useState(false)`, adicione:
```tsx
  const [abrindoOS, setAbrindoOS] = useState(false)
```

(c) Substitua o grupo de botões do cabeçalho:
```tsx
        <div className="flex gap-2">
          {editando && podeEditar && <Button variant="danger" onClick={excluir}>Excluir</Button>}
          <Button variant="secondary" onClick={() => navigate('/app/frota')}>Voltar</Button>
        </div>
```
por:
```tsx
        <div className="flex gap-2">
          {editando && podeAbrirOS(user) && <Button onClick={() => setAbrindoOS(true)}>Abrir OS</Button>}
          {editando && podeEditar && <Button variant="danger" onClick={excluir}>Excluir</Button>}
          <Button variant="secondary" onClick={() => navigate('/app/frota')}>Voltar</Button>
        </div>
```

(d) Imediatamente antes do último `</div>` que fecha o componente (depois do bloco `{editando && (` do Histórico), adicione:
```tsx
      {abrindoOS && obj && (
        <AbrirOSModal equipamentoClienteId={obj.id} osAtual={obj.os_atual} onClose={() => setAbrindoOS(false)} />
      )}
```

- [ ] **Step 3: Verificar lint + build**

Run: `npm --prefix frontend run lint`
Expected: sem erros.
Run: `npm --prefix frontend run build`
Expected: limpo.

- [ ] **Step 4: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/app/ordens/AbrirOSModal.tsx frontend/src/app/frota/EquipamentoClienteDetailPage.tsx
git -C /d/GitHub/GestorHS commit -m "feat(frontend): abrir OS a partir do aparelho na Frota"
```

---

### Task 5: Verificação final (test + lint + build)

**Files:** nenhum (verificação).

- [ ] **Step 1: Suíte completa**

Run: `npm --prefix frontend run test`
Expected: todos verdes (os 54 da 3C + 8 novos desta fase ≈ 62).

- [ ] **Step 2: Lint**

Run: `npm --prefix frontend run lint`
Expected: sem erros nem warnings.

- [ ] **Step 3: Build**

Run: `npm --prefix frontend run build`
Expected: `tsc -b` + `vite build` limpos.

- [ ] **Step 4: (sem commit — verificação)** Reporte o nº de testes e avisos. Se algo falhar, corrija na task correspondente.

---

## Notas para o executor

- Modais seguem o padrão do `CadastroSimples`: `<form id="...">` no corpo + botões no `footer` com `form="..."` (submit fora do form). `textarea` é cru (não há componente Textarea no design system) — copie as classes exatamente do plano.
- O detalhe agora busca `/fases` (liberado a qualquer interno) para descobrir o responsável da fase atual. `podeAgir = admin || user.funcao === fase.funcao_nome`. Botões só com `ativa && podeAgir`.
- O `eslint-disable react-hooks/set-state-in-effect` no `OrdemDetailPage` fica só na linha do `setCarregando(true)` (igual à 3C).
- Nenhum campo de calibração rico é enviado em "Concluir laboratório" (3E cuida disso) — `AvancarModal` só manda `obs`/`cod_retorno`.
- Após a Task 5, o controlador roda o E2E manual contra o banco real (cria 1 OS de teste num aparelho sem OS ativa, percorre/cancela com marca "teste E2E 3D"), avisando antes de tocar no banco.
```
