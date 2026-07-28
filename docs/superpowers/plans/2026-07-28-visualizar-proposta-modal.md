# Visualizar proposta em modal — Plano

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** Trocar a ação "Visualizar" da lista de Propostas de "abre em aba nova" para "abre numa modal grande com o PDF embutido".

**Architecture:** Novo `VisualizarPropostaModal` (espelho do `HistoricoModal`) que busca o Blob autenticado e embute o PDF num `<iframe>` dentro do `Modal size="5xl"`; a PropostasPage abre essa modal no lugar de `window.open`.

**Tech Stack:** Frontend React 19 · TS · Vitest.

## Global Constraints
- Domínio PT-BR; commits Conventional Commits sem acentos, uma linha, sem trailer. Escopos: `ui`, `propostas`, `changelog`.
- Só frontend, sem migração. Mini versão **v1.27.7**. Verificação: `npm run lint && npx tsc -b --noEmit && npm run build`.
- `git add` explícito (nunca `-A`). Falha unit pré-existente alheia (`ClienteEquipamentosTab`) — ignore.

---

## Task 1: VisualizarPropostaModal + trocar o handler + testes + changelog

**Files:** Create `frontend/src/app/propostas/VisualizarPropostaModal.tsx`. Modify `frontend/src/app/propostas/PropostasPage.tsx`, `frontend/src/app/changelog/data.ts`. Test: `PropostasPage.test.tsx` (ajustar).

- [ ] **Step 1: Teste (RED)** — ajustar `PropostasPage.test.tsx`:
  - O teste atual de "Visualizar" provavelmente afirma `window.open` — trocar para: clicar em **Visualizar** → aparece a modal (buscar pelo título `Proposta #<numero>` via `findByText`/role dialog), `propostasApi.baixarPdf` foi chamado com o id, e um `iframe`/`object` é renderizado com o object URL mockado. Mockar `propostasApi.baixarPdf` (resolve Blob) e `URL.createObjectURL` (→ `'blob:mock'`). Não deve chamar `window.open`.
  - (Reusar o setup de auth/provider e mock de `propostasApi` já presente no arquivo.)
- [ ] **Step 2: Rodar e ver falhar** — `cd frontend && npx vitest run src/app/propostas`.
- [ ] **Step 3: Implementar**
  - **LER** `frontend/src/app/propostas/HistoricoModal.tsx` e `frontend/src/components/ui/Modal.tsx` primeiro (padrão de shell, `Spinner`, estados de loading/erro, como a página monta a modal condicionalmente).
  - Criar `frontend/src/app/propostas/VisualizarPropostaModal.tsx`:
    ```tsx
    import { useEffect, useState } from 'react'
    import { Modal } from '../../components/ui/Modal'
    import { Spinner } from '../../components/ui/Spinner'   // confirmar caminho/nome real do Spinner (ver HistoricoModal)
    import { propostasApi } from './api'
    import { ApiError } from '../../lib/api'                // confirmar import real de ApiError

    export function VisualizarPropostaModal({ propostaId, propostaNumero, onClose }: {
      propostaId: number
      propostaNumero: number | null
      onClose: () => void
    }) {
      const [url, setUrl] = useState<string | null>(null)
      const [erro, setErro] = useState<string | null>(null)

      useEffect(() => {
        let objectUrl: string | null = null
        let cancelado = false
        propostasApi.baixarPdf(propostaId)
          .then((blob) => {
            if (cancelado) return
            objectUrl = URL.createObjectURL(blob)
            setUrl(objectUrl)
          })
          .catch((e) => { if (!cancelado) setErro(e instanceof ApiError ? e.message : 'Falha ao carregar o PDF') })
        return () => { cancelado = true; if (objectUrl) URL.revokeObjectURL(objectUrl) }
      }, [propostaId])

      return (
        <Modal open onClose={onClose} title={`Proposta${propostaNumero != null ? ` #${propostaNumero}` : ''}`} size="5xl">
          {erro ? (
            <p className="text-sm text-danger">{erro}</p>
          ) : !url ? (
            <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
          ) : (
            <iframe src={url} title={`Proposta ${propostaNumero ?? ''}`} className="w-full h-[75vh] rounded-lg border border-border bg-white" />
          )}
        </Modal>
      )
    }
    ```
    (Ajuste imports de `Spinner`/`ApiError` ao que o `HistoricoModal` usa de fato.)
  - `PropostasPage.tsx`:
    - Remover a função `visualizarPdf` (a de `window.open`) e o import não usado, se houver.
    - Adicionar estado: `const [visualizar, setVisualizar] = useState<{ id: number; numero: number } | null>(null)`.
    - Na ação **Visualizar** (o `IconButton` com `IconEye`), trocar o `onClick` para `() => setVisualizar({ id: p.id, numero: p.numero })` (remover o `disabled={busyId === p.id}` do Visualizar, já que não usa mais o busy).
    - Renderizar a modal junto das outras (perto do `{historico && <HistoricoModal .../>}`): `{visualizar && <VisualizarPropostaModal propostaId={visualizar.id} propostaNumero={visualizar.numero} onClose={() => setVisualizar(null)} />}`. Importar o componente.
- [ ] **Step 4: Rodar e ver passar** — `npx vitest run src/app/propostas && npx tsc -b --noEmit && npm run lint`.
- [ ] **Step 5: Changelog** — 1ª entrada de `frontend/src/app/changelog/data.ts`:
  ```ts
  {
    versao: '1.27.7',
    data: '28/07/2026',
    itens: [
      { tipo: 'melhoria', texto: 'A visualização da proposta agora abre em uma janela dentro do sistema (com o PDF na tela), no lugar de abrir uma aba separada do navegador.' },
    ],
  },
  ```
- [ ] **Step 6: Build** — `npm run build`.
- [ ] **Step 7: Commit** — `git add frontend/src/app/propostas/VisualizarPropostaModal.tsx frontend/src/app/propostas/PropostasPage.tsx frontend/src/app/propostas/PropostasPage.test.tsx frontend/src/app/changelog/data.ts` && `git commit -m "feat(propostas): visualizar pdf em modal no lugar de aba nova"`.

---

## Self-Review
- **Cobertura:** modal nova embutindo o PDF + troca do handler + cleanup do object URL + changelog. ✅
- **Sem regressão:** Baixar PDF e demais ícones intactos; backend intocado; object URL revogado no unmount.
- **Placeholder scan:** código real; só confirmar imports reais de `Spinner`/`ApiError`.
