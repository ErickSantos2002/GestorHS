# Proposta: campo Introdução no formulário — Plano

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** Adicionar o textarea "Introdução" na PropostaModal, logo abaixo dos dados do cliente, ligado ao `form.intro` que já existe end-to-end (form/payload/backend/PDF prontos).

**Architecture:** Só um `<textarea>` rotulado novo na `PropostaModal`, bindado a `form.intro` via `setField('intro', ...)`. Sem backend/migração.

**Tech Stack:** Frontend React 19 · TS · Vitest.

## Global Constraints
- Domínio PT-BR; commits Conventional Commits sem acentos, uma linha, sem trailer. Escopos: `propostas`, `ui`, `changelog`.
- Frontend puro, sem migração. Mini versão **v1.27.8**. Verificação: `npm run lint && npx tsc -b --noEmit && npm run build`.
- `git add` explícito (nunca `-A`). Falha unit pré-existente alheia (`ClienteEquipamentosTab`) — ignore.
- **NÃO** mexer no payload (já envia `intro` via `...form`), nem no backend/PDF (já prontos). Só a UI.

---

## Task 1: textarea Introdução na PropostaModal + teste + changelog

**Files:** Modify `frontend/src/app/propostas/PropostaModal.tsx`, `frontend/src/app/changelog/data.ts`. Test: `PropostaModal.test.tsx` (estender).

- [ ] **Step 1: Teste (RED)** — em `PropostaModal.test.tsx` (reusar setup existente de auth/provider + mock `propostasApi`):
  - Selecionar/ter um cliente, digitar um texto no campo "Introdução" (por `getByLabelText(/introdução/i)` — ver como os outros campos são achados no teste) e submeter; afirmar que `propostasApi.criar` (ou `atualizar`) foi chamado com `intro: '<texto digitado>'` no payload.
  - Um teste de pré-preenchimento: ao abrir editando uma proposta cujo mock tem `intro: 'Endereço Confirmado.'`, o textarea "Introdução" mostra esse texto. (Ver como o teste monta a proposta existente / `propostasApi.obter`.)
- [ ] **Step 2: Rodar e ver falhar** — `cd frontend && npx vitest run src/app/propostas/PropostaModal.test.tsx`.
- [ ] **Step 3: Implementar**
  - Em `frontend/src/app/propostas/PropostaModal.tsx`, inserir o campo **logo após a seção de dados do cliente** — depois do `</Secao>` do cliente (por volta da linha 558, onde termina o bloco Cliente/aos cuidados/endereço de entrega) e **antes** do comentário `{/* ── Aparelhos ── */}` (~linha 560). Deve ficar **sempre visível** (não gatear por `form.cliente`).
  - Usar o **componente de textarea multi-linha que o modal já usa** para `observacoes`/`assinatura` — LEIA como esses campos são renderizados (procure `observacoes`/`assinatura` no JSX) e espelhe (mesmo componente `Textarea`/`<textarea className={inputClass}>`, mesma classe de label). Bind:
    - `label="Introdução"`
    - `value={form.intro ?? ''}`
    - `onChange={(e) => setField('intro', e.target.value)}`
    - `placeholder` opcional discreto (ex.: "Texto de introdução da proposta (opcional)").
  - Envolver numa `<Secao titulo="Introdução">` **ou** deixar como textarea rotulado solto — escolha o que combina com o estilo ao redor (as outras áreas usam `<Secao>`; se usar, o label do textarea pode ser dispensado em favor do título da seção). Não adicionar nada ao payload nem tocar em outros campos.
- [ ] **Step 4: Rodar e ver passar** — `npx vitest run src/app/propostas && npx tsc -b --noEmit && npm run lint`.
- [ ] **Step 5: Changelog** — 1ª entrada de `frontend/src/app/changelog/data.ts`:
  ```ts
  {
    versao: '1.27.8',
    data: '28/07/2026',
    itens: [
      { tipo: 'melhoria', texto: 'A proposta agora tem um campo de Introdução (logo abaixo dos dados do cliente) para o pós-vendas escrever observações — por exemplo, confirmar o endereço de entrega. O texto sai na seção "Introdução" do PDF.' },
    ],
  },
  ```
- [ ] **Step 6: Build** — `npm run build`.
- [ ] **Step 7: Commit** — `git add frontend/src/app/propostas/PropostaModal.tsx frontend/src/app/propostas/PropostaModal.test.tsx frontend/src/app/changelog/data.ts` && `git commit -m "feat(propostas): campo introducao no formulario da proposta"`.

---

## Self-Review
- **Cobertura:** textarea Introdução visível abaixo dos dados do cliente + bind ao `form.intro` existente + teste (envia + pré-preenche) + changelog. ✅
- **Sem regressão:** payload/backend/PDF intocados; campo já era enviado via `...form`.
- **Placeholder scan:** código real; a única escolha aberta (Secao vs label solto) tem critério (combinar com o entorno).
