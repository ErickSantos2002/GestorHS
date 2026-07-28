# Propostas: ações em ícones + visualizar sem baixar — Design

**Data:** 2026-07-28
**Área:** frontend (`app/propostas/PropostasPage.tsx`, `components/ui/icons.tsx`, `components/ui/IconButton.tsx`).
**Tipo:** melhoria de UI.

## Problema

As ações da lista de Propostas são **botões de texto** (PDF · Histórico · Editar · Duplicar · Excluir), destoando das páginas irmãs (Catálogo de Serviços/Produtos) que usam ações em **ícone** (`IconButton`). E não há como **visualizar** a proposta sem baixá-la.

## Design

### Ações viram `IconButton`/`IconButtonGroup` (mesmo padrão do Catálogo)
| Ação | Ícone | Tone | Gating |
|---|---|---|---|
| Visualizar _(nova)_ | `IconEye` | `ver` | todos |
| Baixar PDF | `IconDownload` _(novo)_ | `neutro` | todos |
| Histórico | `IconClock` | `neutro` | todos |
| Editar | `IconPencil` | `editar` | `podeEscrever` |
| Duplicar | `IconCopy` _(novo)_ | `neutro` | `podeEscrever` |
| Excluir | `IconTrash` | `excluir` | `podeEscrever` |

### Visualizar sem baixar
O endpoint `/propostas/{id}/pdf` já serve `Content-Disposition: inline` (via `download=0`) mas **exige JWT** (link cru dá 401). Então: abrir uma aba em branco **no clique** (gesto do usuário — evita bloqueio de pop-up), buscar o PDF autenticado (`propostasApi.baixarPdf` → Blob) e apontar a aba pro `URL.createObjectURL(blob)`. O navegador renderiza o PDF inline; nada é salvo. Em erro, fecha a aba e mostra a mensagem.

### Aditivos de design system
- `icons.tsx`: adicionar `IconDownload` e `IconCopy` (SVG stroke, no padrão dos existentes: `w-*`/`className` prop, `viewBox 24`).
- `IconButton.tsx`: adicionar prop opcional `disabled?: boolean` (aplica `disabled` no `<button>` + estilo `opacity-50 pointer-events-none`), para o estado "ocupado" (download/duplicar/excluir em andamento). Não quebra os usos atuais.

## Fora de escopo
- Visualizador embutido (modal com `<embed>`); usamos aba nova (mais simples, é o "sem baixar" pedido).
- Mudar o backend do PDF (já suporta inline).

## Rollout
Só frontend, **sem migração**. Mini versão **v1.27.6**.

## Testes
- **PropostasPage:** as ações renderizam como `IconButton` (por `aria-label`/`title`: Visualizar, Baixar PDF, Histórico, Editar, Duplicar, Excluir); Editar/Duplicar/Excluir só aparecem com `podeEscrever`. Clicar em **Visualizar** chama `propostasApi.baixarPdf(id)` e `window.open` (mockar `window.open` + `URL.createObjectURL`).
- **IconButton:** com `disabled`, o `onClick` não dispara e o botão fica desabilitado.

## Arquivos
`components/ui/icons.tsx` (2 ícones), `components/ui/IconButton.tsx` (disabled), `app/propostas/PropostasPage.tsx` (ações + visualizar) + testes. Changelog v1.27.6.
