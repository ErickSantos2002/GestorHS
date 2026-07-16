# Caixas: remover "Vincular OS" e fechar OS por seleção — Plano

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans. Passos usam checkbox (`- [ ]`).

**Goal:** Remover o botão "Vincular OS existente" da caixa e permitir selecionar as OS em Preparando Retorno e fechá-las juntas (ou uma só) com um único código de retorno, direto da tela da caixa.

**Architecture:** Só frontend. Lógica pura (quais OS são fecháveis + laço de fechamento com tolerância a falha parcial) extraída para `app/ordens/api.ts` e testada isolada. A UI em `CaixaDetailPage.tsx` usa esses helpers + o `ordensApi.avancar` existente. Sem endpoint/migração.

**Tech Stack:** React 19 · TS · Vite 8 · Tailwind v4 · Vitest + Testing Library.

## Global Constraints

- Idioma PT-BR em nomes/rotas/textos.
- Fase "Preparando Retorno" é gateada de forma semântica: `TRANSICOES[fase]?.pedeCodRetorno === true` (fase 7 é a única). NÃO hard-codar `7`.
- Reusar `ordensApi.avancar(osId, { cod_retorno, obs })` — sem novo endpoint. Fechamento é um laço de N chamadas; falha parcial é aceitável e reportada.
- Ações de fechar/selecionar atrás de `podeEscrever` (`podeAbrirOS` = Admin/Expedição). Backend valida a função real da fase 7.
- Manter `caixasApi.vincularOrdem` (o modal "Mover OS" usa).
- Verificação: `npm run lint && npx tsc -b --noEmit && npm run build && npm test`.
- Commits Conventional Commits em PT-BR sem acentos, uma linha, sem trailer.

---

### Task 1: Helpers puros `podeFecharOS` + `fecharOrdens` (ordens/api.ts)

**Files:**
- Modify: `frontend/src/app/ordens/api.ts`
- Test: `frontend/src/app/ordens/api.fecharOrdens.test.ts`

**Interfaces:**
- `podeFecharOS(fase: number | null): boolean` — true sse `fase != null && TRANSICOES[fase]?.pedeCodRetorno === true`.
- `fecharOrdens(ids, cod_retorno, obs, avancar): Promise<{ sucessos: number[]; falhas: { id: number; motivo: string }[] }>` — laço sequencial; cada `avancar(id, { cod_retorno, obs })`; erro por-id capturado (motivo = `ApiError.message` ou 'Falha'), nunca interrompe os demais.
- Consumes: `TRANSICOES`, `AvancarPayload`, `ApiError`.

- [ ] **Step 1: Escrever o teste que falha**

```ts
// frontend/src/app/ordens/api.fecharOrdens.test.ts
import { describe, it, expect, vi } from 'vitest'
import { podeFecharOS, fecharOrdens } from './api'
import { ApiError } from '../../lib/api'

describe('podeFecharOS', () => {
  it('só a fase que pede código de retorno (Preparando Retorno) é fechável', () => {
    expect(podeFecharOS(7)).toBe(true)   // Preparando Retorno
    expect(podeFecharOS(5)).toBe(false)  // Laboratório
    expect(podeFecharOS(8)).toBe(false)  // Finalizada
    expect(podeFecharOS(null)).toBe(false)
  })
})

describe('fecharOrdens', () => {
  it('chama avancar uma vez por id com o mesmo código e conta sucessos', async () => {
    const avancar = vi.fn().mockResolvedValue({})
    const r = await fecharOrdens([10, 11, 12], 'BR123', 'lote', avancar)
    expect(avancar).toHaveBeenCalledTimes(3)
    expect(avancar).toHaveBeenCalledWith(10, { cod_retorno: 'BR123', obs: 'lote' })
    expect(r.sucessos).toEqual([10, 11, 12])
    expect(r.falhas).toEqual([])
  })

  it('falha parcial não interrompe as demais e é reportada', async () => {
    const avancar = vi.fn()
      .mockResolvedValueOnce({})
      .mockRejectedValueOnce(new ApiError(403, 'Acesso negado para sua função nesta fase'))
      .mockResolvedValueOnce({})
    const r = await fecharOrdens([1, 2, 3], 'BR9', null, avancar)
    expect(avancar).toHaveBeenCalledTimes(3)
    expect(r.sucessos).toEqual([1, 3])
    expect(r.falhas).toEqual([{ id: 2, motivo: 'Acesso negado para sua função nesta fase' }])
  })
})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd frontend && npx vitest run src/app/ordens/api.fecharOrdens.test.ts`
Expected: FAIL — `podeFecharOS`/`fecharOrdens` não existem.

- [ ] **Step 3: Implementar os helpers**

Em `frontend/src/app/ordens/api.ts`, após a definição de `TRANSICOES` (e podendo referenciar `AvancarPayload`/`ApiError`, já importado no arquivo):

```ts
/** Uma OS pode ser fechada direto da caixa quando está em Preparando Retorno —
 *  semanticamente, a fase cuja transição pede código de retorno (única: fase 7). */
export function podeFecharOS(fase: number | null): boolean {
  return fase != null && TRANSICOES[fase]?.pedeCodRetorno === true
}

/** Fecha várias OS aplicando o MESMO código de retorno. Laço sequencial, tolerante a
 *  falha parcial: um erro por OS é capturado e reportado, sem impedir as demais. */
export async function fecharOrdens(
  ids: number[],
  cod_retorno: string,
  obs: string | null,
  avancar: (id: number, payload: AvancarPayload) => Promise<unknown>,
): Promise<{ sucessos: number[]; falhas: { id: number; motivo: string }[] }> {
  const sucessos: number[] = []
  const falhas: { id: number; motivo: string }[] = []
  for (const id of ids) {
    try {
      await avancar(id, { cod_retorno, obs })
      sucessos.push(id)
    } catch (e) {
      falhas.push({ id, motivo: e instanceof ApiError ? e.message : 'Falha ao fechar' })
    }
  }
  return { sucessos, falhas }
}
```

Confirmar que `ApiError` já está importado em `api.ts` (é — usado em `buscarBlobUrl`). `AvancarPayload` é definido no próprio arquivo.

- [ ] **Step 4: Rodar e ver passar**

Run: `cd frontend && npx vitest run src/app/ordens/api.fecharOrdens.test.ts`
Expected: PASS (3 testes).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/ordens/api.ts frontend/src/app/ordens/api.fecharOrdens.test.ts
git commit -m "feat(caixas): helpers puros podeFecharOS e fecharOrdens"
```

---

### Task 2: `FecharOrdensModal` + mudanças na `CaixaDetailPage`

**Files:**
- Create: `frontend/src/app/caixas/FecharOrdensModal.tsx`
- Modify: `frontend/src/app/caixas/CaixaDetailPage.tsx`
- Test: `frontend/src/app/caixas/CaixaDetailPage.test.tsx`

**Interfaces:**
- `FecharOrdensModal({ quantidade, onClose, onConfirmar })`:
  - `quantidade: number`, `onClose: () => void`, `onConfirmar: (cod_retorno: string, obs: string | null) => Promise<void>`.
  - Campo "Código de retorno" (obrigatório) + "Observação" (opcional). Bloqueia confirmar se código vazio. Mostra "Fechando…" enquanto aguarda `onConfirmar`. Se `onConfirmar` rejeitar, mostra erro.
- `CaixaDetailPage`: consome `podeFecharOS`, `fecharOrdens`, `TRANSICOES` (rótulo) e `ordensApi.avancar`.

- [ ] **Step 1: Escrever o teste de componente que falha**

```tsx
// frontend/src/app/caixas/CaixaDetailPage.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

vi.mock('../../auth/AuthContext', () => ({ useAuth: () => ({ user: { funcao: 'Administrador' } }) }))

const obter = vi.fn()
const avancar = vi.fn()
vi.mock('./api', async (orig) => {
  const real = await orig<typeof import('./api')>()
  return { ...real, caixasApi: { ...real.caixasApi, obter } }
})
vi.mock('../ordens/api', async (orig) => {
  const real = await orig<typeof import('../ordens/api')>()
  return { ...real, ordensApi: { ...real.ordensApi, avancar } }
})

import { CaixaDetailPage } from './CaixaDetailPage'

const CAIXA = {
  id: 3, data: '2026-07-16', obs: null, total_os: 2, clientes: ['ACME'],
  ordens: [
    { id: 10, cliente: 1, cliente_nome: 'ACME', equipamento_descricao: 'Bafômetro', equipamento_serie: 'S1', fase: 7, fase_descricao: 'Preparando Retorno', fase_cor: 'abc' },
    { id: 11, cliente: 1, cliente_nome: 'ACME', equipamento_descricao: 'Bafômetro', equipamento_serie: 'S2', fase: 5, fase_descricao: 'Laboratório', fase_cor: 'def' },
  ],
}

function tela() {
  return render(
    <MemoryRouter initialEntries={['/app/caixas/3']}>
      <Routes><Route path="/app/caixas/:id" element={<CaixaDetailPage />} /></Routes>
    </MemoryRouter>,
  )
}

describe('CaixaDetailPage — fechar OS por seleção', () => {
  beforeEach(() => { obter.mockReset(); avancar.mockReset(); obter.mockResolvedValue({ ...CAIXA }); avancar.mockResolvedValue({}) })

  it('removeu o botão "Vincular OS existente"', async () => {
    tela()
    await screen.findByText('Caixa #3')
    expect(screen.queryByText('Vincular OS existente')).toBeNull()
  })

  it('só a OS em Preparando Retorno tem checkbox; fechar chama avancar com o código', async () => {
    tela()
    await screen.findByText('Caixa #3')
    const checks = screen.getAllByRole('checkbox')
    // 1 no cabeçalho (marcar todas) + 1 na linha elegível (OS #10). A OS #11 (fase 5) não tem.
    const daLinha = checks.filter((c) => (c as HTMLInputElement).dataset.os === '10')
    expect(daLinha).toHaveLength(1)
    fireEvent.click(daLinha[0])

    fireEvent.click(screen.getByText(/Fechar OS selecionadas \(1\)/))
    fireEvent.change(screen.getByLabelText('Código de retorno'), { target: { value: 'BR777' } })
    fireEvent.click(screen.getByRole('button', { name: /Confirmar/ }))

    await waitFor(() => expect(avancar).toHaveBeenCalledWith(10, { cod_retorno: 'BR777', obs: null }))
    expect(avancar).toHaveBeenCalledTimes(1)
  })
})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd frontend && npx vitest run src/app/caixas/CaixaDetailPage.test.tsx`
Expected: FAIL — botão de fechar/checkbox não existem; "Vincular OS existente" ainda presente.

- [ ] **Step 3: Criar `FecharOrdensModal.tsx`**

```tsx
import { useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { Button } from '../../components/ui/Button'

export function FecharOrdensModal({ quantidade, onClose, onConfirmar }: {
  quantidade: number
  onClose: () => void
  onConfirmar: (cod_retorno: string, obs: string | null) => Promise<void>
}) {
  const [cod, setCod] = useState('')
  const [obs, setObs] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function submeter(e: FormEvent) {
    e.preventDefault()
    if (!cod.trim()) { setErro('Código de retorno é obrigatório.'); return }
    setEnviando(true); setErro('')
    try {
      await onConfirmar(cod.trim(), obs.trim() || null)
    } catch (err) {
      setErro(err instanceof Error ? err.message : 'Falha ao fechar')
      setEnviando(false)
    }
  }

  const inputClass = 'w-full px-3 py-2 text-sm rounded-lg border border-border bg-background-elevated text-slate-300 focus:outline-none focus:ring-2 focus:ring-primary/50'

  return (
    <Modal
      open
      onClose={onClose}
      title={`Fechar ${quantidade} OS`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button type="submit" form="form-fechar-ordens" disabled={enviando}>
            {enviando ? 'Fechando…' : 'Confirmar'}
          </Button>
        </>
      }
    >
      <form id="form-fechar-ordens" className="space-y-4" onSubmit={submeter}>
        <p className="text-sm text-slate-400">
          O mesmo código de retorno será aplicado às {quantidade} OS selecionadas.
        </p>
        <Input id="cod-retorno" label="Código de retorno" value={cod} onChange={(e) => setCod(e.target.value)} required />
        <div>
          <label htmlFor="obs-fechar" className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">Observação</label>
          <textarea id="obs-fechar" value={obs} onChange={(e) => setObs(e.target.value)} rows={2} className={inputClass} />
        </div>
        {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      </form>
    </Modal>
  )
}
```

- [ ] **Step 4: Change 1 — remover "Vincular OS existente" em `CaixaDetailPage.tsx`**

- Remover o botão "Vincular OS existente" (o `<Button variant="secondary" onClick={... setVincularAberto(true)}>` no bloco de ações).
- Remover o bloco `{vincularAberto && (<Modal … title="Vincular OS existente" …>)}`.
- Remover o estado e handler exclusivos: `vincularAberto`, `osVincular`, `erroVincular`, `vinculando`, e a função `confirmarVincular`.
- **Não** remover `caixasApi.vincularOrdem` nem o modal/handler "Mover OS" (`confirmarMover` usa `vincularOrdem`).

- [ ] **Step 5: Change 2 — seleção + fechar em `CaixaDetailPage.tsx`**

Imports (adicionar): `import { FecharOrdensModal } from './FecharOrdensModal'` e, de `../ordens/api`, `ordensApi, podeFecharOS, fecharOrdens, TRANSICOES`.

Estado novo:
```tsx
const [selecionadas, setSelecionadas] = useState<Set<number>>(new Set())
const [fecharAberto, setFecharAberto] = useState(false)

const elegiveis = caixa ? caixa.ordens.filter((o) => podeFecharOS(o.fase)) : []
function toggle(id: number) {
  setSelecionadas((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n })
}
function toggleTodas() {
  setSelecionadas((s) => s.size === elegiveis.length ? new Set() : new Set(elegiveis.map((o) => o.id)))
}
async function confirmarFechar(cod: string, obs: string | null) {
  const ids = [...selecionadas]
  const { sucessos, falhas } = await fecharOrdens(ids, cod, obs, ordensApi.avancar)
  setFecharAberto(false)
  setSelecionadas(new Set())
  setErroAcao(falhas.length
    ? `${sucessos.length} OS fechada(s); ${falhas.length} falhou/falharam: ${falhas.map((f) => `#${f.id} (${f.motivo})`).join(', ')}`
    : '')
  carregar()
}
```
(nota: `selecionadas` pode conter ids que saíram da fase 7 após um `carregar()`; ao recarregar, limpamos a seleção, então não há resíduo.)

No bloco de ações do lote (onde ficava o "Vincular"), adicionar o botão de fechar:
```tsx
{podeEscrever && (
  <div className="flex gap-2 flex-wrap">
    <Button onClick={abrirPicker}>Abrir OS</Button>
    <Button
      variant="secondary"
      disabled={selecionadas.size === 0}
      onClick={() => setFecharAberto(true)}
    >
      Fechar OS selecionadas ({selecionadas.size})
    </Button>
  </div>
)}
```

Na tabela, adicionar a coluna de seleção como PRIMEIRA coluna (só para `podeEscrever`):
- No `head`, antes de `<TH>OS</TH>`:
```tsx
{podeEscrever && (
  <TH>
    <input
      type="checkbox"
      aria-label="Selecionar todas as OS em Preparando Retorno"
      className="accent-primary"
      checked={elegiveis.length > 0 && selecionadas.size === elegiveis.length}
      onChange={toggleTodas}
      disabled={elegiveis.length === 0}
    />
  </TH>
)}
```
- Em cada `<tr>`, antes do `<TD>` da OS:
```tsx
{podeEscrever && (
  <TD>
    {podeFecharOS(o.fase) && (
      <input
        type="checkbox"
        data-os={o.id}
        aria-label={`Selecionar OS #${o.id}`}
        className="accent-primary"
        checked={selecionadas.has(o.id)}
        onChange={() => toggle(o.id)}
      />
    )}
  </TD>
)}
```

Renderizar o modal (perto dos outros modais):
```tsx
{fecharAberto && (
  <FecharOrdensModal
    quantidade={selecionadas.size}
    onClose={() => setFecharAberto(false)}
    onConfirmar={confirmarFechar}
  />
)}
```

- [ ] **Step 6: Rodar e ver passar**

Run: `cd frontend && npx vitest run src/app/caixas/CaixaDetailPage.test.tsx`
Expected: PASS (2 testes).

- [ ] **Step 7: Verificação do módulo**

Run: `cd frontend && npm run lint && npx tsc -b --noEmit`
Expected: lint limpo (sem variáveis órfãs do que foi removido no Change 1), tipos OK.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/app/caixas/FecharOrdensModal.tsx frontend/src/app/caixas/CaixaDetailPage.tsx frontend/src/app/caixas/CaixaDetailPage.test.tsx
git commit -m "feat(caixas): fechar OS por selecao e remove vincular OS existente"
```

---

### Task 3: Changelog + verificação completa

**Files:**
- Modify: `frontend/src/app/changelog/data.ts`

- [ ] **Step 1: Bump v1.17.0**

Primeira entrada de `CHANGELOG`:
```ts
{
  versao: '1.17.0',
  data: '16/07/2026',
  itens: [
    { tipo: 'novidade', texto: 'Na tela de uma Caixa, agora dá para fechar as OS direto por ali: marque as OS que estão em "Preparando Retorno" e clique em "Fechar OS selecionadas" para finalizá-las juntas com o mesmo código de retorno (ou marque só uma). Útil quando a caixa toda volta com o mesmo rastreio; as que ficam para manutenção é só não marcar.' },
    { tipo: 'melhoria', texto: 'Removido o botão "Vincular OS existente" de dentro da caixa — a caixa já é escolhida na abertura da OS.' },
  ],
},
```

- [ ] **Step 2: Verificação completa**

Run: `cd frontend && npm run lint && npx tsc -b --noEmit && npm run build && npm test`
Expected: lint/tsc/build limpos, todos os testes verdes.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/changelog/data.ts
git commit -m "docs(changelog): v1.17.0 — fechar OS por selecao na caixa"
```

---

## Self-Review (feita)

- **Cobertura da spec:** remover "Vincular OS existente" (T2 step 4), seleção só em fase 7 (T2 step 5, via `podeFecharOS`), fechar juntas/uma com um código (T2 + `fecharOrdens`), falha parcial reportada (T1 test + T2 handler), permissão `podeEscrever` (T2), changelog (T3). ✔
- **Sem número mágico:** a fase é gateada por `TRANSICOES[fase]?.pedeCodRetorno`, não por `=== 7`. ✔
- **Sem placeholders:** todo passo com código concreto/edição precisa; as remoções do Change 1 nomeiam exatamente estado/handler/blocos. ✔
- **Consistência de tipos:** `fecharOrdens`/`podeFecharOS` definidos em T1 e consumidos em T2; `FecharOrdensModal.onConfirmar` = `(cod, obs) => Promise<void>` casa com `confirmarFechar`. ✔
- **Não remover demais:** `caixasApi.vincularOrdem` e "Mover OS" preservados (usados por `confirmarMover`). ✔
