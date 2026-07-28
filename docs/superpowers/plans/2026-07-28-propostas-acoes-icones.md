# Propostas: ações em ícones + visualizar — Plano

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** Trocar as ações da lista de Propostas por ícones (`IconButton`, igual ao Catálogo) e adicionar uma ação "Visualizar" que abre o PDF numa aba nova sem baixar.

**Architecture:** Reusar o design system `IconButton`/`IconButtonGroup`; adicionar 2 ícones (`IconDownload`, `IconCopy`) e um `disabled?` opcional no `IconButton`; "Visualizar" busca o Blob autenticado e abre numa aba pré-aberta no clique.

**Tech Stack:** Frontend React 19 · TS · Vitest.

## Global Constraints
- Domínio PT-BR; commits Conventional Commits sem acentos, uma linha, sem trailer. Escopos: `ui`, `ux`, `propostas`, `changelog`.
- Sem migração, só frontend. Mini versão **v1.27.6**.
- `git add` explícito (nunca `-A`). Verificação: `npm run lint && npx tsc -b --noEmit && npm run build`. Falha unit pré-existente alheia (`ClienteEquipamentosTab`) — não conserte, não introduza novas.
- Não quebrar usos atuais de `IconButton` (tones `editar`/`ver`/`excluir`/`neutro`/`ok`; API `label`/`tone`/`onClick`/`children`/`className`).

---

## Task 1: ícones + IconButton disabled + ações em ícone na PropostasPage + Visualizar

**Files:** Modify `frontend/src/components/ui/icons.tsx`, `frontend/src/components/ui/IconButton.tsx`, `frontend/src/app/propostas/PropostasPage.tsx`, `frontend/src/app/changelog/data.ts`. Tests: `PropostasPage.test.tsx` (estender), `IconButton.test.tsx` (criar se não houver).

- [ ] **Step 1: Testes (RED)**
  - **PropostasPage.test.tsx** (estender o existente): renderizar a lista com 1 proposta e um usuário COM `podeEscrever` e afirmar que existem controles com `aria-label`/`title`: "Visualizar", "Baixar PDF", "Histórico", "Editar", "Duplicar", "Excluir" (buscar por `getByRole('button', { name: /visualizar/i })` etc.). Com usuário SEM escrita (ex.: função sem acesso), afirmar que "Editar"/"Duplicar"/"Excluir" NÃO aparecem, mas "Visualizar"/"Baixar PDF"/"Histórico" sim. Um teste de **Visualizar**: mockar `propostasApi.baixarPdf` (resolve um Blob), `window.open` (retorna um objeto stub com `location`), e `URL.createObjectURL` (retorna uma string) — clicar em "Visualizar" e afirmar que `baixarPdf` foi chamado com o id e `window.open` foi chamado. (Ver como o teste atual monta o provider de auth/usuário e o mock do `propostasApi`.)
  - **IconButton.test.tsx:** com `disabled`, `fireEvent.click` NÃO dispara o `onClick` e o botão tem `disabled`.
- [ ] **Step 2: Rodar e ver falhar** — `cd frontend && npx vitest run src/app/propostas src/components/ui/IconButton.test.tsx`.
- [ ] **Step 3: Implementar**
  - `components/ui/icons.tsx` — adicionar `IconDownload` e `IconCopy` seguindo o padrão exato dos ícones existentes (ex.: assinatura `export function IconX({ className }: { className?: string })`, `<svg viewBox="0 0 24 24" ... className={className}>` com paths stroke). `IconDownload`: seta pra baixo + linha da base. `IconCopy`: dois retângulos sobrepostos.
  - `components/ui/IconButton.tsx` — adicionar `disabled?: boolean` à assinatura; passar `disabled` ao `<button>` e, quando `true`, concatenar classes `opacity-50 pointer-events-none` (via `cn`). Não muda a aparência quando `disabled` é `undefined`/`false`.
  - `app/propostas/PropostasPage.tsx`:
    - Importar `IconButton`, `IconButtonGroup` de `../../components/ui/IconButton` e `IconEye, IconDownload, IconClock, IconPencil, IconCopy, IconTrash` de `../../components/ui/icons`.
    - Trocar a célula de ações (hoje os `<Button variant="ghost" ...>` PDF/Histórico/Editar/Duplicar/Excluir, ~linhas 155-161) por um `<IconButtonGroup>` com os `IconButton` conforme o mapeamento:
      - Visualizar → `tone="ver"` `label="Visualizar"` `IconEye`, `onClick={() => visualizarPdf(p)}`, `disabled={busyId === p.id}`.
      - Baixar PDF → `tone="neutro"` `label="Baixar PDF"` `IconDownload`, `onClick={() => baixarPdf(p)}`, `disabled={busyId === p.id}`.
      - Histórico → `tone="neutro"` `label="Histórico"` `IconClock`, `onClick={() => setHistorico({ id: p.id, numero: p.numero })}`.
      - (Se `podeEscrever`) Editar → `tone="editar"` `IconPencil` `onClick={() => setModalId(p.id)}`.
      - (Se `podeEscrever`) Duplicar → `tone="neutro"` `IconCopy` `onClick={() => duplicar(p.id)}` `disabled={busyId === p.id}`.
      - (Se `podeEscrever`) Excluir → `tone="excluir"` `IconTrash` `onClick={() => excluir(p)}` `disabled={busyId === p.id}`.
    - Adicionar a função `visualizarPdf` (espelha `baixarPdf`, mas abre em aba):
      ```tsx
      async function visualizarPdf(p: Proposta) {
        const win = window.open('', '_blank')
        setBusyId(p.id)
        setErro(null)
        try {
          const blob = await propostasApi.baixarPdf(p.id)
          const url = URL.createObjectURL(blob)
          if (win) win.location.href = url
          else window.open(url, '_blank')
        } catch (e) {
          if (win) win.close()
          setErro(e instanceof ApiError ? e.message : 'Falha ao abrir o PDF')
        } finally {
          setBusyId(null)
        }
      }
      ```
      (Confirme os nomes reais de `busyId`/`setBusyId`, `setErro`, `ApiError`, `propostasApi` no arquivo — já são usados por `baixarPdf`.)
- [ ] **Step 4: Rodar e ver passar** — `npx vitest run src/app/propostas src/components/ui/IconButton.test.tsx && npx tsc -b --noEmit && npm run lint`.
- [ ] **Step 5: Changelog** — 1ª entrada de `frontend/src/app/changelog/data.ts`:
  ```ts
  {
    versao: '1.27.6',
    data: '28/07/2026',
    itens: [
      { tipo: 'melhoria', texto: 'As ações da lista de Propostas agora são ícones, no mesmo padrão das outras telas, e há uma ação para visualizar a proposta em PDF numa nova aba sem precisar baixar.' },
    ],
  },
  ```
- [ ] **Step 6: Build** — `npm run build`.
- [ ] **Step 7: Commit** — `git add frontend/src/components/ui/icons.tsx frontend/src/components/ui/IconButton.tsx frontend/src/app/propostas/PropostasPage.tsx frontend/src/app/changelog/data.ts <arquivos de teste>` && `git commit -m "feat(propostas): acoes em icone e visualizar pdf sem baixar"`. Se preferir, separar o changelog em `docs(changelog): v1.27.6 - ...`.

---

## Self-Review
- **Cobertura:** 2 ícones + IconButton disabled + 6 ações em ícone (1 nova) + visualizar em aba + changelog. ✅
- **Sem regressão:** IconButton mantém API atual; `disabled` é opt-in. Backend intocado.
- **Pop-up:** aba aberta no gesto do clique, antes do await.
