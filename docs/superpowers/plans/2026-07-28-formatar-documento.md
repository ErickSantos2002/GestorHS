# Formatar CNPJ/CPF na interface — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Formatar CNPJ/CPF automaticamente em toda a interface — na exibição (`36.312.056/0005-52`) e na digitação (máscara + aceitar colado) — para CNPJ e CPF, sem mudar o dado (continua dígitos no banco).

**Architecture:** Um util novo `src/lib/documento.ts` no frontend (espelho da lógica do backend) aplicado em todos os pontos de exibição e nos campos de digitação; mais uma correção de 1 linha no PDF da proposta (documento do endereço de entrega, hoje cru).

**Tech Stack:** Frontend React 19 · TS · Vitest. Backend Python (só 1 linha em `proposta_pdf.py`).

## Global Constraints

- Domínio PT-BR; commits Conventional Commits em português **sem acentos** (ASCII), uma linha, sem trailer. Escopos: `ux`, `ui`, `propostas`, `changelog`.
- **Sem migração, sem mudar storage** — CNPJ/CPF continuam dígitos no banco. O backend já normaliza entrada (`schemas/clientes.py`) e já formata os PDFs (certificado + proposta), exceto o respingo da Task 4.
- `git add` explícito (nunca `git add -A`; untracked alheio: `backend/relatorios/`, `docs/proposta_comercial*.pdf`).
- Frontend: verificação `npm run lint && npx tsc -b --noEmit && npm run build`. Há falhas de teste unit pré-existentes alheias (ex.: `ClienteEquipamentosTab`) — não conserte, não introduza novas.
- Mini versão **v1.27.3**.

---

## Task 1: util `src/lib/documento.ts` + testes

**Files:** Create `frontend/src/lib/documento.ts`, `frontend/src/lib/documento.test.ts`.

**Interfaces produzidas (usadas nas Tasks 2 e 3):** `soDigitos`, `formatarDocumento`, `mascararCNPJ`, `mascararCPF`.

- [ ] **Step 1: Teste (RED)** — `frontend/src/lib/documento.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { soDigitos, formatarDocumento, mascararCNPJ, mascararCPF } from './documento'

describe('soDigitos', () => {
  it('remove nao-digitos', () => {
    expect(soDigitos('36.312.056/0005-52')).toBe('36312056000552')
    expect(soDigitos(null)).toBe('')
    expect(soDigitos(undefined)).toBe('')
  })
})

describe('formatarDocumento', () => {
  it('formata CNPJ (14) e CPF (11)', () => {
    expect(formatarDocumento('36312056000552')).toBe('36.312.056/0005-52')
    expect(formatarDocumento('12345678901')).toBe('123.456.789-01')
  })
  it('ja formatado -> reformata igual', () => {
    expect(formatarDocumento('36.312.056/0005-52')).toBe('36.312.056/0005-52')
  })
  it('tamanho estranho/vazio -> devolve os digitos', () => {
    expect(formatarDocumento('123')).toBe('123')
    expect(formatarDocumento('')).toBe('')
    expect(formatarDocumento(null)).toBe('')
  })
})

describe('mascaras progressivas', () => {
  it('mascararCNPJ progressivo e capado em 14', () => {
    expect(mascararCNPJ('36')).toBe('36')
    expect(mascararCNPJ('36312')).toBe('36.312')
    expect(mascararCNPJ('363120560005')).toBe('36.312.056/0005')
    expect(mascararCNPJ('3631205600055299')).toBe('36.312.056/0005-52') // capa em 14
  })
  it('mascararCPF progressivo e capado em 11', () => {
    expect(mascararCPF('123')).toBe('123')
    expect(mascararCPF('1234567')).toBe('123.456.7')
    expect(mascararCPF('123456789012')).toBe('123.456.789-01') // capa em 11
  })
})
```

- [ ] **Step 2: Rodar e ver falhar** — `cd frontend && npx vitest run src/lib/documento.test.ts` → FAIL.
- [ ] **Step 3: Implementar** — `frontend/src/lib/documento.ts`:

```ts
/** Utilitarios de CNPJ/CPF (documento). Storage e' sempre so digitos; formata nas pontas. */
export function soDigitos(v: string | null | undefined): string {
  return (v ?? '').replace(/\D/g, '')
}

/** Exibicao: 14 dig -> CNPJ, 11 dig -> CPF, qualquer outro tamanho -> os digitos como estao. */
export function formatarDocumento(v: string | null | undefined): string {
  const d = soDigitos(v)
  if (d.length === 14) return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8, 12)}-${d.slice(12)}`
  if (d.length === 11) return `${d.slice(0, 3)}.${d.slice(3, 6)}.${d.slice(6, 9)}-${d.slice(9)}`
  return d
}

/** Mascara progressiva de CNPJ para input (capa em 14 digitos). */
export function mascararCNPJ(v: string | null | undefined): string {
  const d = soDigitos(v).slice(0, 14)
  if (d.length > 12) return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8, 12)}-${d.slice(12)}`
  if (d.length > 8) return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8)}`
  if (d.length > 5) return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5)}`
  if (d.length > 2) return `${d.slice(0, 2)}.${d.slice(2)}`
  return d
}

/** Mascara progressiva de CPF para input (capa em 11 digitos). */
export function mascararCPF(v: string | null | undefined): string {
  const d = soDigitos(v).slice(0, 11)
  if (d.length > 9) return `${d.slice(0, 3)}.${d.slice(3, 6)}.${d.slice(6, 9)}-${d.slice(9)}`
  if (d.length > 6) return `${d.slice(0, 3)}.${d.slice(3, 6)}.${d.slice(6)}`
  if (d.length > 3) return `${d.slice(0, 3)}.${d.slice(3)}`
  return d
}
```

- [ ] **Step 4: Rodar e ver passar** — `npx vitest run src/lib/documento.test.ts`.
- [ ] **Step 5: Commit** — `git add frontend/src/lib/documento.ts frontend/src/lib/documento.test.ts && git commit -m "feat(ux): util de formatacao de cnpj/cpf"`

---

## Task 2: aplicar formatação na EXIBIÇÃO

**Files:** Modify `frontend/src/app/clientes/ClientesPage.tsx`, `frontend/src/app/propostas/PropostasPage.tsx`, `frontend/src/app/propostas/PropostaModal.tsx`. Sweep certificados/ordens/frota. Test: adicionar asserts nos testes de página existentes ou criar `*.test.tsx` focados.

**Interfaces consumidas:** `formatarDocumento` (Task 1).

- [ ] **Step 1: Teste (RED)** — num teste de página (reusar `PropostasPage.test.tsx`/`ClientesPage.test.tsx` se existirem, senão criar focado): renderizar a lista com um cliente de `cgc='36312056000552'` e afirmar que a tela mostra `36.312.056/0005-52` (não o número cru).
- [ ] **Step 2: Rodar e ver falhar.**
- [ ] **Step 3: Implementar** — importar `formatarDocumento` e envolver os renders:
  - `clientes/ClientesPage.tsx:83` → `<TD>{formatarDocumento(c.cgc || c.cpf) || '—'}</TD>`
  - `propostas/PropostasPage.tsx:150` → `<TD>{formatarDocumento(p.cliente_documento) || '—'}</TD>`
  - `propostas/PropostaModal.tsx:462` → `CNPJ/CPF: {formatarDocumento(clienteSelecionado.cgc || clienteSelecionado.cpf)}`
  - `propostas/PropostaModal.tsx:486` → `{(c.cgc || c.cpf) && <span ...>{formatarDocumento(c.cgc || c.cpf)}</span>}`
  - **Sweep:** `grep -rnE "cgc|cpf|documento" frontend/src --include=*.tsx | grep -v test` — para cada render read-only de documento em certificados/ordens/frota (que NÃO seja um input controlado, esses são da Task 3), aplicar `formatarDocumento`. Liste no report o que encontrou e o que envolveu.
- [ ] **Step 4: Rodar e ver passar** — `npx vitest run src/app/clientes src/app/propostas && npx tsc -b --noEmit`.
- [ ] **Step 5: Commit** — `git add <arquivos alterados + testes> && git commit -m "feat(ui): exibe cnpj/cpf formatado nas telas"`

---

## Task 3: máscara automática nos campos de DIGITAÇÃO

**Files:** Modify `frontend/src/app/clientes/ClienteFormFields.tsx`, `frontend/src/portal/PortalLoginPage.tsx`, `frontend/src/app/propostas/PropostaModal.tsx` (override), e os modais de certificado com campo `cnpj` (buscar). Test: `*.test.tsx` focados.

**Interfaces consumidas:** `soDigitos`, `formatarDocumento`, `mascararCNPJ`, `mascararCPF` (Task 1).

- [ ] **Step 1: Teste (RED)** — no teste do form de cliente: digitar/colar `36.312.056/0005-52` no campo CNPJ → o input mostra `36.312.056/0005-52` e o payload enviado (ou o estado) tem só dígitos `36312056000552`. Idem um teste do login do portal (colar formatado → normaliza pra dígitos no submit).
- [ ] **Step 2: Rodar e ver falhar.**
- [ ] **Step 3: Implementar** — padrão: **estado guarda dígitos, input exibe máscara**.
  - `clientes/ClienteFormFields.tsx:52` — trocar os dois `txt('CNPJ','cgc')`/`txt('CPF','cpf')` por inputs dedicados. Leia o helper `txt` (linhas ~30-34) e o componente `Input` para adaptar; a ideia:
    - CNPJ: `value={mascararCNPJ(form.cgc ?? '')}` · `onChange={(e) => set('cgc', soDigitos(e.target.value) || null)}`
    - CPF: `value={mascararCPF(form.cpf ?? '')}` · `onChange={(e) => set('cpf', soDigitos(e.target.value) || null)}`
    - Mantenha label/id/disabled iguais aos outros campos.
  - `portal/PortalLoginPage.tsx:66` — campo combinado: `value={formatarDocumento(documento)}` · `onChange={(e) => setDocumento(soDigitos(e.target.value))}`. O estado `documento` passa a ser dígitos; `login`/`definirSenha` já recebem `documento` (agora dígitos) — ok.
  - `propostas/PropostaModal.tsx` — override `documento` (input em ~:517): `value={mascararCNPJ(overrideDraft.documento ?? '')}`? Não — o override pode ser CPF ou CNPJ. Use `value={formatarDocumento(overrideDraft.documento ?? '')}` · `onChange={(e) => definirOverride('documento', soDigitos(e.target.value))}`. E o **default** do override (hoje `clienteSelecionado?.cgc || cpf`, ~:311) passa a `soDigitos(...)` (o input formata). Como o PDF/handler manda `documento` pro backend e o backend formata o PDF, mandar dígitos mantém o PDF formatado.
  - **Campos `cnpj` dos certificados** — `grep -rn "cnpj" frontend/src/app/certificados frontend/src/app/frota frontend/src/app/ordens --include=*.tsx | grep -iE "Input|value=|onChange"`. Para cada input de `cnpj` editável, mesmo padrão do override (`value={formatarDocumento(...)}` / `onChange={... soDigitos ...}`). Liste no report os que achou e alterou.
- [ ] **Step 4: Rodar e ver passar** — `npx vitest run src/app/clientes src/portal src/app/propostas && npx tsc -b --noEmit && npm run lint`.
- [ ] **Step 5: Commit** — `git add <arquivos + testes> && git commit -m "feat(ux): mascara automatica de cnpj/cpf nos campos"`

---

## Task 4: respingo backend (PDF proposta) + changelog v1.27.3 + verificação

**Files:** Modify `backend/app/core/proposta_pdf.py`, `frontend/src/app/changelog/data.ts`.

- [ ] **Step 1: Backend fix** — em `proposta_pdf.py:~489-490`, o documento do endereço de entrega:
  `linhas_entrega += f"CPF/CNPJ: {_fmt_documento(de.get('documento'))}<br>"` (usar o `_fmt_documento` já existente no módulo). Confirme a variável exata usada na linha (é `de_get('documento')` / `de.get('documento')` — ajuste ao código real).
- [ ] **Step 2: Teste backend (se houver teste de proposta_pdf)** — se existir `backend/tests/test_proposta_pdf.py`, adicionar/estender um caso com endereço de entrega com documento de 14 díg e afirmar que o HTML gerado contém a versão formatada. Se não houver harness fácil, registrar no report que a mudança é 1 linha reusando `_fmt_documento` (já testado indiretamente) e rodar `pytest -q` para não regredir.
- [ ] **Step 3: Changelog** — 1ª entrada de `frontend/src/app/changelog/data.ts`:
```ts
{
  versao: '1.27.3',
  data: '28/07/2026',
  itens: [
    { tipo: 'melhoria', texto: 'CNPJ e CPF agora aparecem formatados (36.312.056/0005-52) em todas as telas, e os campos de digitar aplicam a máscara automaticamente — inclusive quando você cola o número já formatado de outro lugar.' },
  ],
},
```
- [ ] **Step 4: Verificação** — Backend `cd backend && source .venv/bin/activate && pytest -q` (só as 4 de upload). Frontend `cd frontend && npm run lint && npx tsc -b --noEmit && npm run build`.
- [ ] **Step 5: Commit** — `git add backend/app/core/proposta_pdf.py frontend/src/app/changelog/data.ts && git commit -m "feat(propostas): formata documento de entrega no pdf + changelog v1.27.3"`

---

## Self-Review

- **Cobertura da spec:** util (T1) · exibição app-todo (T2 + sweep) · input máscara app-todo (T3 + sweep) · respingo PDF entrega (T4) · changelog (T4). ✅
- **Sem mudar dado/storage:** estado/input normalizam pra dígitos; backend já normaliza; nenhuma migração.
- **Placeholder scan:** sem TBD; código real. Sweeps têm instrução concreta (grep + critério) e pedem lista no report.
- **Nomes/tipos consistentes:** `soDigitos`/`formatarDocumento`/`mascararCNPJ`/`mascararCPF`.
