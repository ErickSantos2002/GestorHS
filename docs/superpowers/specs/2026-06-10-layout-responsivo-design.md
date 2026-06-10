# GestorHS — Layout responsivo fluido (preencher a tela)

**Data:** 2026-06-10
**Status:** Aprovado para implementação
**Motivação:** Várias páginas (principalmente as de detalhe) usam largura fixa estreita (`max-w-3xl`/`4xl`), deixando o lado direito vazio em telas grandes, e usam tamanhos fixos que não acompanham bem o tamanho da tela/zoom. O laboratório relatou que isso atrapalha o uso. Queremos um layout **fluido e consistente** que preencha a área útil, distribua o conteúdo em colunas conforme o espaço, e reflua em telas pequenas/zoom.

**Contexto:** só frontend (React 19 + TS + Vite + Tailwind v4). Sem backend, sem migração. Parte de um lote de melhorias de UX (será lançado junto na v1.4.1).

## Decisões de design
- **Largura fluida** (decisão do usuário): o conteúdo ocupa toda a área útil com respiro lateral; em telas largas os blocos se distribuem em mais colunas em vez de esticar campo único; um teto alto (~1700px) evita linhas longas demais em ultrawide.
- **Responsividade por breakpoints** resolve o "flexível ao zoom/tela": mais colunas quando há espaço, menos quando não há. Sem tipografia fluida (`clamp()`) nesta etapa.
- **Primitivos compartilhados** em vez de largura por página: padroniza e evita retrabalho.
- **Não mexer** em cores/identidade, componentes (cards/tabelas/Modal) nem na lógica das páginas — só no enquadramento/layout.

## Escopo
**Dentro:**
- Novos primitivos `PageContainer` e `DetailGrid` (+ subcomponentes de coluna).
- Tornar responsivos os grids de campos fixos (`grid-cols-2`/`grid-cols-3`) das páginas de detalhe.
- Migrar as páginas de detalhe (Aparelho/Frota, OS, Cliente, Caixa) para `PageContainer` + `DetailGrid`.
- Migrar as páginas de lista e demais telas internas para `PageContainer` (padronização de padding/teto).

**Fora:**
- Mudança de cores/identidade visual; redesenho de componentes (cards, tabelas, Modal, Sidebar/Topbar).
- Tipografia fluida com `clamp()`.
- Portal do cliente (`/portal`) — fora deste lote (pode vir depois se incomodar).
- Backend/migração.

## Componentes (novos)

Arquivo: `frontend/src/components/ui/Page.tsx`

- **`PageContainer`** (`{ children, className? }`): wrapper padrão de página. Classes base:
  `mx-auto w-full max-w-[1700px] px-4 sm:px-6 lg:px-8 py-6 space-y-6`.
  Substitui o `px-4 md:px-6 py-6 space-y-6 max-w-Nxl` hoje repetido em cada página. Aceita `className` extra, mesclado com `cn(...)` de `frontend/src/lib/utils.ts`. Todos os subcomponentes usam `cn` para mesclar o `className`.
- **`DetailGrid`** (`{ children, className? }`): grade de detalhe.
  Base: `grid grid-cols-1 xl:grid-cols-3 gap-6 items-start`.
- **`DetailMain`** (`{ children, className? }`): coluna principal. Base: `xl:col-span-2 space-y-6 min-w-0`.
- **`DetailAside`** (`{ children, className? }`): coluna lateral. Base: `space-y-6 min-w-0`.

Racional: `min-w-0` evita overflow de conteúdo (tabelas/inputs) dentro do grid; `items-start` mantém as colunas alinhadas ao topo (não esticam uma à altura da outra).

Regra para grids de campos dentro de formulários/seções:
- `grid grid-cols-2 gap-3` → `grid grid-cols-1 sm:grid-cols-2 gap-3`
- `grid grid-cols-3 gap-3` → `grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3`

## Layout por página de detalhe

- **Aparelho (`EquipamentoClienteDetailPage`):** header full width; `DetailGrid` → `DetailMain` = formulário (Aparelho + Calibração + botão salvar); `DetailAside` = "Última calibração (resultado da OS)" + "Histórico de movimentação". No modo **novo** (não-editando, sem aside) usar coluna única estreita (sem grid) para não criar vazio.
- **OS (`OrdemDetailPage`):** hero (já full width) mantém; abaixo, `DetailGrid` → `DetailMain` = Recebimento + Fotos + Datas + Resultados da calibração; `DetailAside` = Certificados + Histórico (timeline).
- **Cliente (`ClienteDetailPage`):** header full width; `DetailGrid` → `DetailMain` = Identificação + Endereço + Contato (seções existentes); `DetailAside` = atalhos (ex.: Frota) + (quando editando e admin) Usuários do portal. No modo **novo** usar coluna única.
- **Caixa (`CaixaDetailPage`):** header full width; `DetailGrid` → `DetailMain` = dados/edição + tabela de OS; `DetailAside` = resumo (totais/clientes) + obs/ações.

Em todas: se a coluna lateral não tiver conteúdo (ex.: criação), cair para coluna única (sem grid) — mesma regra já usada hoje no Aparelho.

## Páginas de lista e demais telas
Trocar o wrapper `<div className="px-4 md:px-6 py-6 space-y-6 ...">` por `<PageContainer>` em: Ordens, Clientes, Frota, Cobrança, Solicitações, Cadastros, Certificados, Caixas (lista), Dashboard, Minha conta, Usuários. Baixo risco — só padroniza padding/teto; tabelas seguem full width dentro do container.

## Testes / verificação
- **tsc + eslint + build** verdes a cada página migrada.
- **Vitest:** a suíte atual (113 testes) continua passando; o `Page.tsx` é estrutural (sem lógica) — sem teste unitário dedicado (segue o padrão do projeto p/ componentes puros de layout; verificação é visual).
- **E2E visual (com o usuário):** abrir Aparelho, OS, Cliente, Caixa em tela cheia e conferir que preenchem a largura, reflui ao reduzir a janela/zoom, e nada quebra (overflow de tabela, inputs).

## Critérios de aceite
- Páginas de detalhe preenchem a área útil (sem grande vazio à direita) em monitor comum; em ultrawide respeitam o teto sem esticar texto.
- Reduzir a janela/zoom reflui o conteúdo para menos colunas até coluna única, sem quebra.
- Largura/padding consistentes entre todas as páginas (mesmo `PageContainer`).
- HTML/identidade visual e lógica inalterados; tsc/lint/build/vitest verdes. Changelog (v1.4.1) atualizado no fim do lote de UX.

## Fora do v1 desta etapa
Tipografia fluida (`clamp()`); responsividade do portal do cliente; redesenho de cards/tabelas; densidade configurável.
