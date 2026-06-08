# GestorHS — Detalhe da OS: redesign visual + lightbox de fotos

**Data:** 2026-06-08
**Status:** Aprovado para implementação
**Motivação:** A página de detalhe da OS (`OrdemDetailPage`) é funcional mas visualmente pobre — uma pilha de cartões `label/valor` sem hierarquia. Melhorar a aparência (mantendo o tema dark do GestorHS) e adicionar um visualizador de imagem (lightbox) para as fotos.

## Escopo
**Dentro:** redesign visual de `frontend/src/app/ordens/OrdemDetailPage.tsx` + novo componente `FotoLightbox`. Só apresentação — sem mudança de comportamento, backend ou banco.
**Fora:** fluxo de fechamento/laboratório (próxima etapa), portal, qualquer endpoint novo.

## Abordagem aprovada
"Cartões refinados + barra de fases" — eleva o layout em coluna única, sem reestruturar em dashboard.

## Componentes / mudanças

### Cabeçalho (hero)
- `OS #<id>` em destaque + badge da fase com a cor real (`fase_cor`).
- Linha de resumo: Cliente · Equipamento · Série.
- Ações à direita: ação principal (rótulo da transição, ex. "Encaminhar ao laboratório") em destaque, "Cancelar OS" (danger) e "Voltar" (secondary), com as mesmas regras de visibilidade atuais (`ativa && podeAgir && transicao`).

### Barra de progresso das fases (stepper)
- Sequência fixa: Recebido(4) → Laboratório(5) → Pós-Vendas(6) → Preparando Retorno(7) → Finalizada(8).
- Fases anteriores à atual = concluídas (preenchidas/check); fase atual = destacada (cor da fase); futuras = esmaecidas (`text-slate-600`, borda sutil).
- Estado especial **Cancelada(9)**: exibir um indicador vermelho ("Cancelada") no lugar do progresso normal.
- Derivar a posição pela `os.fase`. Componente interno (helper) na própria página ou pequeno componente.

### Cartões refinados
- Cada `<section>` mantém `rounded-2xl bg-background-surface border border-border`, mas o título ganha **ícone** + peso, e o conteúdo respira mais.
- **Recebimento:** acessórios como **chips** (mesmo estilo do `AbrirOSModal`: pílula `bg-primary/15 text-primary` para presentes); pilhas/bocais com ícone; condição de chegada como `Badge`/realce; data de chegada e caixa (link) como hoje.
- **Datas** e **Resultados da calibração:** leitura mais clara (valor com peso, "—" suave). Botões "Baixar/Enviar certificado" mantidos.
- Helper `Campo` pode ser refinado (label uppercase sutil, valor `text-slate-200`).

### Fotos + Lightbox
- Galeria: miniaturas `rounded-lg`, **hover** com leve escurecimento + ícone de lupa indicando que abre; "Excluir" aparece no hover (canto), gated `podeFotos`.
- **Clicar na miniatura abre `FotoLightbox`**.
- **`FotoLightbox`** (`frontend/src/app/ordens/FotoLightbox.tsx`): overlay full-screen (`fixed inset-0 z-50 bg-black/80 backdrop-blur`), imagem grande centralizada, legenda embaixo, contador (ex. "2/5"); navegação **‹ ›** (botões) entre as fotos da OS; fecha por **X**, **clique fora** e **Esc**; **setas do teclado** (←/→) navegam. Recebe a lista de fotos + índice inicial + `onClose`. Carrega a imagem autenticada via blob (reusar `buscarBlobUrl` de `ordens/api.ts`, como o `FotoImg` faz) — não usar `<img src>` direto (precisa do Bearer).

### Histórico
- Timeline vertical: linha à esquerda com bolinhas (dot) por evento; data menor, texto do evento. Mantém ordem atual.

## Ícones
- Reusar ícones de `components/ui/icons.tsx`. Se faltarem (ex. lupa/zoom, chevron ‹ ›, câmera, relógio), criar SVGs simples no mesmo padrão (`function IconX({ className }: IconProps)`, `stroke="currentColor"`, sem fill). O `IconSearch`/`IconCalendar`/`IconX`/`IconChevronDown` já existem (ver arquivo); criar `IconChevronLeft`/`IconChevronRight`/`IconZoom`/`IconClock`/`IconCamera` se necessário.

## Não-objetivos / restrições
- Não mudar `api.ts`, endpoints, nem o comportamento de envio/exclusão de foto, certificado, avançar/cancelar.
- Não introduzir dependência nova nem fonte/paleta diferente — usar tokens existentes.
- Não alterar componentes compartilhados de forma que quebre outras telas (se precisar, aditivo/retrocompatível).

## Verificação
- `tsc -b --noEmit` + `eslint` + `npm run build` verdes; `vitest` sem regressão (a página não tem teste unitário; lógica intacta).
- **Conferência visual por screenshot** (playwright-core headless): abrir a OS #10409 (ou outra com fotos), conferir hero/stepper/cards/galeria, e abrir o lightbox (navegação ‹ ›, Esc).

## Changelog
Entra como **v1.2.1** (melhoria): "Tela de detalhe da OS repaginada — barra de progresso das fases, seções mais legíveis e visualizador de imagem (lightbox) para as fotos."

## Critérios de aceite
- A página tem hero + barra de fases refletindo a fase atual (e estado Cancelada), seções com ícones, acessórios em chips, histórico em timeline.
- Clicar numa foto abre o lightbox; navega ‹ › e por teclado; fecha por X/fora/Esc; mostra legenda e contador.
- Comportamento (ações, fotos, certificado, modais) inalterado. tsc/lint/build verdes. Changelog v1.2.1.
