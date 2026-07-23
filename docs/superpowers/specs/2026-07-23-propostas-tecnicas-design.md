# Propostas Técnicas — Design

**Data:** 2026-07-23
**Área:** backend (`app/models/`, `app/schemas/`, `app/api/`, `app/core/` PDF) + frontend (`src/app/propostas/`, `src/app/cadastros/`) + migração Alembic
**Base:** portada do módulo **Proposal** do `hsgrowth-sistema` (feature madura), adaptada ao GestorHS.

## Problema

O time comercial monta as propostas hoje no **Tiny (ERP)**, rotuladas como "Proposta Comercial".
Elas deveriam ser **Propostas Técnicas** e ser **da Health Safety** (personalizáveis). Já se tentou
trazer para o CRM **GrowthHS**, mas lá não funcionou bem: o GrowthHS **não tem os dados de aparelho**
(frota, série, modelo, status de calibração) — que o **GestorHS tem**. Por isso a proposta migra para
o GestorHS, onde a seleção de aparelhos sai da frota real.

## Objetivo

Uma página **Propostas** no GestorHS onde o comercial:
1. escolhe um **cliente** (cadastro existente);
2. vê a **frota do cliente** (`equipamento_cliente`) com o **farol de vencimento** e **marca** os aparelhos da proposta;
3. adiciona **itens** de dois catálogos novos (**Serviços** e **Produtos**, com SKU/preço);
4. escolhe um **modelo de bloco técnico** ("Outros itens") e o edita;
5. **gera o PDF** "Proposta Técnica Nº X", que fica **salvo** e listado, com **histórico** de alterações.

A implementação **porta o Proposal do GrowthHS** (modelo, itens-snapshot, histórico, construtor, PDF),
removendo o que é específico do GrowthHS e plugando a frota do GestorHS.

## Não-objetivos (desta entrega)

- **Sem status/workflow** (`rascunho`/`enviada`/`aceita`) — decisão do produto. A proposta é salva e
  editável, sem coluna de status. (No GrowthHS existe `internal_status` + "marcador" derivado de cards —
  **removidos**.)
- **Sem conexão com o fluxo de OS/Caixa** — a proposta é standalone. (Conectar "aceite" ao fluxo é evolução futura.)
- **Sem vínculo com "cards de serviço"** — todo o N:N `ProposalServiceCard`, `prefill_from_card` e
  auto-anexo de PDF em card do GrowthHS **não são portados** (o GestorHS não tem esse board).
- **Sem gestão de templates por UI/banco** nesta entrega — os modelos do bloco técnico são **builders no
  frontend** (como no GrowthHS). Templates editáveis por UI ficam como evolução.
- **Sem continuidade da numeração do Tiny** — a numeração **recomeça** (sequência própria).
- **Sem migração/importação** dos catálogos do Tiny — o time **recadastra** Serviços/Produtos à mão
  (por isso Serviço precisa de SKU, para bater com os SKUs já usados).

## Decisão de arquitetura

**Portar do GrowthHS, adaptar a origem dos aparelhos.** O modelo, o histórico (snapshot + PDF por
versão), o construtor e o builder de HTML do PDF vêm do GrowthHS quase diretos. Três adaptações:
1. **Aparelhos = frota real** (`equipamento_cliente` + `status_calibracao`) em vez de texto derivado de
   um JSON de card. A proposta passa a guardar uma **lista estruturada de aparelhos**.
2. **PDF via Playwright** (motor que o GestorHS já usa em `core/certificado_pdf.py`, com filtro
   anti-SSRF) em vez do WeasyPrint do GrowthHS. Porta-se o **HTML-builder** (f-strings), troca-se só o
   renderer. Título "Proposta Técnica".
3. **Sem os acoplamentos ao board de cards** do GrowthHS (ver não-objetivos).

---

## Modelo de dados

### Catálogos (dois cadastros novos, **tabelas separadas** — decisão do produto)
- **`servico`** — `id`, `sku` (unique), `nome`, `descricao` (Text), `unidade` (str, ex. "Unid"),
  `preco` (Numeric 12,2, NOT NULL), `codigo_servico` (CNAE, str, opt), `ativo` (bool default True).
  É a **fonte dos itens** de serviço da proposta.
- **`produto`** — `id`, `sku` (unique), `nome`, `descricao`, `unidade`, `preco` (Numeric 12,2, NOT NULL),
  `ncm` (str, opt), `ativo`. Itens **físicos avulsos** (bocal, maleta), sem vínculo com cliente.

### `proposta` (portada de `proposals`, enxugada)
- `id`; `numero` (Integer unique, index) — **sequência própria** (não é o id), `next_numero()` =
  `max(numero)+1` com **retry anti-corrida** (IntegrityError, até 5 tentativas), portado do GrowthHS.
- `cliente` (FK `clientes.id`), `contato` (opcional — "aos cuidados de"), `vendedor` (str, = nome do
  usuário logado, **imutável**), `data` (Date).
- `intro` (Text), `outros_itens` (Text — **HTML** do editor rico), `observacoes` (Text), `assinatura` (str).
- `desconto` (Numeric 12,2 NOT NULL default 0), `frete` (Numeric 12,2 NOT NULL default 0).
- `forma_envio` (str), `forma_frete` (str, CIF/FOB), `transportador` (str), `condicao_pagamento` (str),
  `validade_dias` (Integer), `data_entrega` (Date), `descricao_entrega` (str).
- `endereco_entrega_diferente` (bool default False), `endereco_entrega` (JSON).
- `cliente_override` (JSON) — edição dos dados do cliente **só nesta proposta** (nome/doc/endereço/
  cidade/UF/email/telefone/contato), sem alterar o cadastro. **Portado do GrowthHS.**
- `pdf` (str, basename do PDF salvo, via `storage`).
- **Soft-delete** (`deleted_at`, `is_deleted`) e timestamps (`created_at`/`updated_at`), portados.

### `proposta_item` (portada de `proposal_items` — **snapshot**)
- `id`, `proposta` (FK CASCADE), `descricao` (NOT NULL), `sku` (str), `quantidade` (Numeric 12,4
  default 1), `unidade` (str), `preco_un` (Numeric 12,2 default 0), `total` (Numeric 12,2) —
  **calculado no servidor** = `quantidade × preco_un`. Sem FK viva ao catálogo (cópia editável).

### `proposta_aparelho` (**novo — o delta do GestorHS**)
Aparelhos selecionados da frota. `id`, `proposta` (FK CASCADE), `equipamento_cliente` (FK
`equipamentos_cliente.id`, `SET NULL`), e **snapshot** `serie`/`modelo`/`patrimonio`/`prox_calibragem`
(para o documento não mudar se a frota mudar depois). Alimenta os builders do bloco técnico.

### `proposta_versao` (portada de `proposal_versions` — **HISTÓRICO**)
- `id`, `proposta` (FK CASCADE), `numero_versao` (Integer), `snapshot` (JSON — **estado completo
  anterior**), `pdf_path` (str), `alterado_por` (str, **nome** do usuário).
- **Mecânica portada:** no `update()`, ANTES de aplicar as mudanças, arquiva o estado **anterior**
  (snapshot JSON + PDF renderizado da versão) — best-effort (try/except não bloqueia a edição).
  `numero_versao = len(versoes)+1`.
- **Adaptação para "o que mudou":** o GrowthHS guarda snapshot completo (não diff). Como o Erick quer
  ver **campo a campo o que mudou**, o **diff é calculado na exibição** (compara versão N × N+1) e
  renderizado como "Frete: 200 → 250", "Item adicionado: Calibração ×2", "Aparelho removido: WAO8U0198".
  Guarda-se snapshot completo (robusto, + PDF por versão); o diff é derivado na tela.

**Reaproveitado (não cria nada):** `Cliente`, `EquipamentoCliente` (frota), `status_calibracao()`
(farol vencido/vencendo/em dia/sem data), `core/certificado_pdf.html_para_pdf` (Playwright anti-SSRF),
`core/storage` (salvar o PDF).

---

## O construtor (fluxo do comercial)

Um **modal único** com seções verticais (portado do `ProposalModal` do GrowthHS, ~10 seções), adaptado:

1. **Cliente** — busca no cadastro existente; puxa nome/CNPJ/endereço/contato. Botão de **override**
   (editar os dados só nesta proposta, com badge "editado nesta proposta"). Checkbox "endereço de
   entrega diferente" (com busca de CEP).
2. **Aparelhos (novo)** — ao escolher o cliente, lista a **frota** (`equipamento_cliente`) com o
   **farol de vencimento** (`status_calibracao`: vencido/vencendo/em dia/sem data). O comercial **marca**
   os aparelhos → viram `proposta_aparelho`.
3. **Identificação** — Nº (read-only "automático"), Vendedor (read-only = usuário), Data.
4. **Itens** — tabela editável (descrição, SKU, qtd, un, preço un, total). Busca por linha contra os
   catálogos **Serviço** e **Produto** (lupa); ao selecionar, copia nome/sku/preço (cópia editável).
   "Adicionar item" cria linha vazia. Itens são **manuais** nesta entrega (sem auto-gerar a partir dos
   aparelhos — mantém simples; automação fica como evolução).
5. **Outros itens (bloco técnico)** — editor de **texto rico** + seletor de **modelo** ("Demais
   aparelhos" / "Aparelho Phoebus", portados de `proposalDefaults.ts`). Ao escolher o modelo, o HTML é
   **pré-preenchido com os aparelhos marcados** (série/modelo/módulo) — inclusive **detecção Phoebus**
   reaproveitando o elo módulo→Phoebus que o GestorHS já tem. O comercial ajusta o texto livremente.
6. **Totais** — Total dos itens (auto) + Desconto + Frete → **Total da Proposta**
   (`total_itens + frete − desconto`), recalculado no cliente e reconferido no servidor.
7. **Transportador / Condições comerciais / Condições gerais** — forma de envio/frete/transportador,
   condição de pagamento, validade (default 30 dias), data/descrição de entrega.
8. **Observações e Assinatura** — default "Atenciosamente, {usuário}".

**Lista de propostas** (página): número, data, cliente, CNPJ, valor, ações — **Ver PDF**, **Editar**
(reabre o modal), **Baixar PDF**, **Histórico**, **Duplicar** (nova conveniência: clona a proposta para
outro cliente/edição), **Excluir** (soft-delete). Busca por cliente/número.

**Histórico** (modal) — lista as versões (`#vN`, data-hora, "Alterado por", total) com o **diff
campo-a-campo** renderizado e botões ver/baixar o **PDF daquela versão**.

## Geração de PDF

Porta o **HTML-builder** do GrowthHS (`_build_html`, f-strings + CSS inline: cabeçalho H&S com logo,
"Para/Aos cuidados de", box de endereço, itens, "Outros itens" sanitizado, totais, condições,
assinatura), com dois ajustes:
- **Renderer = `core/certificado_pdf.html_para_pdf`** (Playwright, anti-SSRF) em vez de WeasyPrint.
- **Título "Proposta Técnica Nº X"** (não "Comercial").
- Dados fixos da empresa (CNPJ/endereço/logo) embutidos, como no GrowthHS. `cliente_override` tem
  prioridade na renderização. Sanitização do HTML do editor (remove script/style/iframe/img/on*=)
  portada. O PDF é salvo via `storage` e referenciado em `proposta.pdf`.

## Numeração
Sequência própria `proposta.numero`, `max+1` com retry anti-corrida (portado). Recomeça (começa em 1).

## Permissões, rotas e navegação
- **Página Propostas** e os cadastros de **Serviços/Produtos** — função **Comercial Pós-Vendas** +
  **Administrador** (tanto usar quanto gerenciar o catálogo). Espelhar no
  `frontend/src/auth/roles.ts` e no `require_funcao` do backend.
- Rotas backend em `app/api/propostas.py`, `app/api/servicos.py`, `app/api/produtos.py`
  (registrar em `main.py`). Rotas específicas (`/prefill`, `/{id}/pdf`, `/{id}/versoes`) **antes** de
  `/{id}` para não colidir (lição do GrowthHS).
- Frontend: módulo `src/app/propostas/` (lista + modal construtor + histórico) e as telas de cadastro.
- **Nova dependência de frontend:** um **editor de texto rico** para "Outros itens" (o GrowthHS usa
  `react-quill`) — avaliar `react-quill` ou equivalente compatível com React 19.

## Testes
- **Backend:** numeração sequencial + retry; cálculo de totais (itens + frete − desconto); snapshot de
  item (preço congelado); versionamento no update (arquiva estado anterior + PDF); soft-delete;
  montagem do HTML do PDF (título "Proposta Técnica", override do cliente, sanitização); seleção de
  aparelhos da frota → `proposta_aparelho`; farol de vencimento na listagem da frota.
- **Frontend (Vitest):** o construtor recalcula totais; a busca de item copia preço do catálogo; marcar
  aparelho da frota alimenta o template; a lista mostra ações; o histórico renderiza o diff campo-a-campo.

## Mapa de arquivos (alto nível)
- **Migração:** `alembic/versions/00NN_propostas.py` (servico, produto, proposta, proposta_item,
  proposta_aparelho, proposta_versao).
- **Models:** `models/servico.py`, `produto.py`, `proposta.py` (+ item/aparelho/versao).
- **Schemas/serviço:** `schemas/proposta.py`, `core/proposta_pdf.py` (HTML-builder), lógica de
  serviço/numeração/versão (portadas de `proposal_service.py`/`proposal_repository.py`).
- **API:** `api/propostas.py`, `api/servicos.py`, `api/produtos.py`.
- **Frontend:** `src/app/propostas/` (Lista, ConstrutorModal, HistoricoModal, api.ts),
  cadastros de Serviços/Produtos, entrada no menu, `roles.ts`.
- **Changelog:** bump ao fechar.

## Evoluções futuras (fora desta entrega)
- Templates do bloco técnico **editáveis por UI/banco** (hoje builders no frontend).
- **Status/workflow** da proposta (rascunho→enviada→aceita) e conexão do **aceite** ao fluxo de OS/Caixa.
- Auto-gerar itens a partir dos aparelhos marcados.
- Importar catálogo do Tiny.
