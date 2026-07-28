# Visualizar proposta em modal (no lugar de aba nova) — Design

**Data:** 2026-07-28
**Área:** frontend (`app/propostas/VisualizarPropostaModal.tsx` novo, `app/propostas/PropostasPage.tsx`).
**Tipo:** ajuste de UX (v1.27.6 abria o PDF em aba nova; passa a abrir numa modal embutida).

## Problema

Na v1.27.6 a ação **Visualizar** abre o PDF numa aba nova. O app é todo baseado em modais (HistoricoModal, PropostaModal…); uma modal com o PDF embutido é mais fluida (abre, olha, fecha, sem sair da página).

## Design

### `VisualizarPropostaModal.tsx` (novo) — espelha o padrão do `HistoricoModal`
- Props: `propostaId: number`, `propostaNumero: number | null`, `onClose: () => void`.
- Ao montar: busca o PDF autenticado (`propostasApi.baixarPdf(propostaId)` → Blob), gera `URL.createObjectURL(blob)`. Enquanto carrega, mostra `Spinner`; em erro, mensagem.
- Renderiza dentro de `<Modal open onClose title={`Proposta #${numero}`} size="5xl">` um `<iframe>` (ou `<object type="application/pdf">`) apontando pro object URL, ocupando ~`h-[75vh] w-full` (viewer nativo do navegador — permite imprimir/baixar de lá).
- **Cleanup:** `URL.revokeObjectURL` ao desmontar/fechar (useEffect cleanup), pra não vazar memória.

### `PropostasPage.tsx`
- Estado `visualizar: { id: number; numero: number } | null`.
- A ação **Visualizar** (👁) passa a `setVisualizar({ id: p.id, numero: p.numero })` no lugar da lógica de aba nova (`visualizarPdf` + `window.open` são removidos).
- Renderiza `{visualizar && <VisualizarPropostaModal propostaId={visualizar.id} propostaNumero={visualizar.numero} onClose={() => setVisualizar(null)} />}` (padrão do `HistoricoModal` na mesma página).
- **Baixar PDF** (⬇) continua igual; os demais ícones intactos.

## Fora de escopo
- Backend (o endpoint já serve inline). Visualizador customizado (usamos o nativo do navegador no iframe).

## Rollout
Só frontend, sem migração. Mini versão **v1.27.7**.

## Testes
- Clicar em **Visualizar** abre a modal (título "Proposta #<numero>"), chama `propostasApi.baixarPdf(id)` e renderiza um `iframe`/`object` cujo `src`/`data` é o object URL (mockar `baixarPdf` + `URL.createObjectURL`). Fechar chama `onClose` e não deixa a modal.
- Não deve mais chamar `window.open` no Visualizar.

## Arquivos
`app/propostas/VisualizarPropostaModal.tsx` (novo), `app/propostas/PropostasPage.tsx` (+ teste `PropostasPage.test.tsx` ajustado). Changelog v1.27.7.
