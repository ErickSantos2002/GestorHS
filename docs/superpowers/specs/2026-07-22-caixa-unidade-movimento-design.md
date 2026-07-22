# Caixa como unidade de movimento (no lugar da OS) — Design

**Data:** 2026-07-22
**Área:** backend (`app/core/os_workflow.py`, `app/models/`, `app/api/`, `app/core/taskhs.py`, `app/core/growthhs_os.py`, `app/api/espelhamento.py`, `app/api/growthhs_cards.py`) + frontend (`src/app/ordens/`, `src/app/caixas/`, `src/auth/roles.ts`) + migração Alembic
**Contexto:** sistema em produção desde 20/07/2026 — mudança **forward-only**, aplicada por merge + migration em janela tranquila (fim do dia).

## Problema

Dentro do GestorHS o movimento **por OS** (uma OS = um aparelho) funciona bem. Fora dele, não:
no TaskHS e no GrowthHS o mundo pensa **por cliente/lote**. Uma caixa de 10 aparelhos do mesmo
cliente é **uma** proposta, **um** contato de pós-vendas e **uma** nota fiscal — mas o Gestor
espelha **10 cards**, um por OS. Pós-vendas e financeiro têm que vincular e repetir informação
card a card. Antes disso não doía porque quem "andava" nos sistemas externos era a **Caixa**.

A raiz: a **unidade de movimento** é a OS individual, quando deveria ser a **Caixa**.

## Objetivo

Fazer a **Caixa** ser a unidade que anda pelas fases — no Gestor (página de Ordens) e,
por consequência, nos sistemas externos (1 card por caixa). O trabalho técnico continua
**por aparelho** (cada um calibra e gera seu certificado); o que muda é que ninguém anda
sozinho: a caixa anda inteira quando todos os aparelhos dela terminaram o laboratório.

Isso **formaliza uma regra que a operação já pratica** ("só passa pra pós-vendas quando a
caixa toda está concluída") — não impõe fluxo novo.

## Não-objetivos

- **Sem backfill / sem conserto retroativo.** O que já foi espelhado por-OS (go-live 20/07)
  fica como está. A mudança vale para caixas novas, daqui pra frente.
- **Sem PDF de laudo de "sem conserto" nesta entrega.** Só o **estado** por aparelho +
  destravar a caixa. O PDF do laudo fica para uma release seguinte (o estado já nasce pronto
  para ele, sem retrabalho).
- **Sem reescrever `ordem.fase`.** A OS mantém `fase`; ela apenas passa a espelhar a da caixa.
  Nada rio abaixo (certificados, portal, dashboard, conteúdo de card) muda de fonte.
- **Sem callback dos sistemas externos.** Segue best-effort de mão única, como hoje.

## Decisão de arquitetura — "Caixa dirige, OS espelha"

Avaliadas 3 abordagens; escolhida a de **menor blast radius** num sistema recém-nascido:

1. **Caixa dirige, OS espelha (escolhida).** A fase mora na caixa; `ordem.fase` continua e é
   mantida sempre igual à da caixa. Progresso individual do laboratório vira um campo novo na OS.
2. **Só a Caixa tem fase (OS perde `fase`).** Mais limpo conceitualmente, mas exige cirurgia em
   tudo que lê `ordem.fase` (certificados, portal, dashboard). Caro e arriscado agora. Rejeitada.
3. **Fase da caixa por agregação (sem coluna).** A fase da caixa seria deduzida das OS. Espalha a
   regra por muitos pontos e fica ambígua se as OS divergirem. Frágil. Rejeitada.

---

## Modelo de dados

### `caixas` (coluna nova)
- **`fase`** — FK para `fases`. Unidade de movimento. Nasce em **Recebido(4)** ao receber a caixa.

### `ordens` (colunas novas)
- **`desfecho_lab`** — enum/string: `pendente` (default) · `concluido` · `sem_conserto`.
  Progresso **individual** do aparelho dentro do laboratório.
- **`desfecho_lab_obs`** — texto, justificativa obrigatória quando `sem_conserto`.

### Invariantes garantidas pelo sistema (travas novas)
1. **Toda OS tem caixa.** Abrir OS sem `caixa` passa a ser rejeitado (hoje é permitido).
2. **Uma caixa = um cliente.** Vincular OS de cliente diferente ao da caixa é rejeitado. É o que
   deixa o card externo ter 1 cliente / 1 contato / 1 NF sem ambiguidade. (Hoje o modelo permite
   vários clientes numa caixa.)
3. **Todas as OS de uma caixa estão na mesma fase** — decorre da sincronia `ordem.fase = caixa.fase`.

## Máquina de estados e a trava

O grafo linear de fases **não muda** (`os_workflow.py`): `Recebido(4) → Laboratório(5) →
Pós-Vendas(6) → Financeiro(10) → Preparando(7) → Finalizada(8)`, com `Cancelada(9)`. O que muda
é **quem** percorre o grafo: a **Caixa**.

- **Avançar é ação na Caixa.** Ao avançar, a caixa muda de fase e **todas as suas OS avançam junto**
  na mesma transação (`ordem.fase = caixa.fase`). Ponto único de sincronia.
- **Trava por aparelho só em Laboratório(5) → Pós-Vendas(6):** só libera quando **nenhuma** OS
  ativa da caixa está `desfecho_lab = pendente` (todas `concluido` ou `sem_conserto`).
- **Demais transições são nível caixa** — sem checagem por aparelho (ali o trabalho já é por lote:
  proposta, NF, envio).
- **A caixa é "sagrada": espera todos.** Um aparelho lento segura o lote (é tudo do mesmo cliente).
  O escape não é cancelar e sim `sem_conserto`: o aparelho continua na caixa, sai da trava e volta
  pro cliente com laudo (depois).
- **Cancelada(9):** aplicada à **caixa** (cancela as OS junto). Não há cancelamento de um aparelho
  isolado — para "esse não tem conserto" existe `sem_conserto`.
- **Autorização por transição** (`require_funcao`) preservada, aplicada à caixa: Expedição move
  Recebido→Lab e Preparando→Finalizada, Laboratório move Lab→Pós-Vendas, etc. Espelhar em
  `frontend/src/auth/roles.ts`.

## Integrações externas (TaskHS e GrowthHS) — por caixa

Chave e disparo:
- **`external_id` passa de `str(ordem.id)` para `str(caixa.id)`** nos dois. Um card por caixa.
- Disparo nos mesmos gatilhos (abrir/avançar/cancelar), agora a partir da **caixa** (ponto único,
  já que avançar é ação na caixa). `app/api/espelhamento.py` e `app/api/growthhs_cards.py` passam
  a receber a caixa.
- **TaskHS:** `list_id` segue `caixa.fase` (`FASE_PARA_LIST_ID` inalterado — só muda a fonte).
- **GrowthHS:** o card sai quando a **caixa** é liberada do laboratório (todos com desfecho).

Conteúdo — as funções puras passam a receber `caixa + ordens` e **agregam**:
- **`taskhs.py`** (`montar_titulo`/`montar_obs`/`montar_payload`):
  - Título: `CX <id> · <cliente> · N aparelhos`.
  - **obs1 (Recebido):** cabeçalho do cliente (um só) + **lista dos aparelhos** (série/patrimônio).
  - **obs2 (Laboratório):** **lista por aparelho** — "Aparelho X: calibrado, cert nº…, link…" /
    "Aparelho Y: **sem conserto** — <motivo>".
  - **obs3/obs4/obs5/obs6:** já são por lote (1 contato, 1 NF, 1 endereço, 1 rastreio) — **é aqui
    que o retrabalho morre**.
- **`growthhs_os.py`** (`montar_card_os`): `devices: []` deixa de ter 1 item e lista **todos os
  aparelhos da caixa** (o schema do GrowthHS já aceita — hoje mandávamos 1 só). `client`/`contact`
  uma vez. `business_info` referencia a caixa.
- **Elo Phoebus inalterado:** `montar_device`/`buscar_elo` continua **por aparelho**, agora dentro
  de um loop sobre as OS da caixa (monta N devices). Nenhuma regra de elo muda.

## Frontend

**Quadro por caixa** (`OrdensPage.tsx`):
- Colunas continuam sendo as **fases**. A **unidade do card** passa de OS para **Caixa**.
- Card da caixa: `CX <id>`, cliente, `N aparelhos` e, na coluna **Laboratório**, um progresso da
  trava — `3/5 prontos` (concluídos + sem conserto).
- Clicar → detalhe da caixa (`CaixaDetailPage`, já existente, incrementada).
- A **Lista** passa a filtrar/exibir por caixa de forma coerente (mantendo acesso à OS individual).

**Detalhe da caixa = posto de trabalho** (`CaixaDetailPage.tsx`):
- Lista os aparelhos/OS com seu `desfecho_lab` (pendente / concluído / sem conserto).
- Abrir a **OS individual** (`OrdemDetailPage`) para o trabalho técnico (receber, calibrar, gerar
  certificado) — segue existindo.
- **Marcar "sem conserto"** é ação na OS individual dentro do lab (marca desfecho + justificativa,
  sai da trava).
- **Botão "Avançar caixa"** aqui, com **trava visível**: em Laboratório fica bloqueado enquanto
  houver aparelho pendente, com aviso ("faltam N aparelhos"). Nas demais fases avança direto.

**Avançar / Cancelar migram da OS para a Caixa** (`AvancarModal`/`CancelarModal`): a OS individual
**perde o botão de avançar** — quem anda é a caixa.

**Cadastro** (`AbrirOSModal.tsx`): passa a **exigir caixa** (hoje opcional) — trava da invariante 1.

## Rollout / transição (forward-only)

- **Sem migração de dados externos.** Cards por-OS já criados ficam como estão e envelhecem; como
  a chave muda (`caixa.id` ≠ `ordem.id`), não há conflito nem duplicação com os novos cards por-caixa.
- **OS em voo** (abertas nos ~2 dias antes do deploy, com card por-OS ativo): **escoam no modelo
  antigo**; o modelo-caixa vale para o que entrar depois do deploy. Evita migrar card em voo.
- **Migração Alembic** (`NNNN_caixa_unidade_movimento.py`): adiciona `caixas.fase`,
  `ordens.desfecho_lab`, `ordens.desfecho_lab_obs`. Backfill de coerência para as caixas/OS
  **ativas** existentes: `caixa.fase` recebe a fase das OS da caixa; `desfecho_lab` das OS ativas
  cuja fase já passou do laboratório nasce `concluido`, as demais nascem `pendente`. Comparar por
  **posição lógica** (`os_workflow.posicao()` / `ORDEM_FASES`), **nunca pelo ID cru** — Financeiro é
  ID 10, numericamente maior que Preparando(7)/Finalizada(8). Marcar `pendente` a mais é
  conservador (o operador reconfirma), então em dúvida cai em `pendente`.
- **Trabalho todo numa branch** `feat/caixa-unidade-movimento`, local; **merge + migration no fim
  do dia**, fora do horário de uso, para não atrapalhar quem está operando.

## Testes

- **Backend (`core/`, puro):** transições da caixa; a trava Lab→Pós-Vendas (bloqueia com pendente,
  libera com todos concluído/sem_conserto/mix); sincronia `ordem.fase = caixa.fase`; invariantes
  (OS sem caixa rejeitada; cliente divergente rejeitado). Agregação em `taskhs.py`/`growthhs_os.py`
  (N aparelhos, obs2 lista por aparelho, sem conserto no texto, `devices[]` com N itens).
- **Frontend (Vitest):** quadro renderiza caixas com "N/M prontos"; botão avançar bloqueado com
  pendente; marcar sem conserto muda o progresso; AbrirOSModal exige caixa.

## Arquivos afetados (mapa)

- **Migração:** `alembic/versions/NNNN_caixa_unidade_movimento.py` (novo).
- **Modelos:** `models/caixa.py` (+`fase`), `models/ordem.py` (+`desfecho_lab`, `+desfecho_lab_obs`).
- **Workflow/serviço:** `core/os_workflow.py` (helpers da trava, puro), avançar/cancelar da caixa
  em `api/caixas.py` + `api/ordens_acoes.py`.
- **Integrações:** `core/taskhs.py`, `core/growthhs_os.py` (agregação); `api/espelhamento.py`,
  `api/growthhs_cards.py` (disparo por caixa).
- **Auth:** `api/deps.py` + `frontend/src/auth/roles.ts` (gating por transição na caixa).
- **Frontend:** `ordens/OrdensPage.tsx`, `ordens/AbrirOSModal.tsx`, `ordens/AvancarModal.tsx`,
  `ordens/CancelarModal.tsx`, `ordens/OrdemDetailPage.tsx`, `caixas/CaixaDetailPage.tsx`.
- **Changelog:** `frontend/src/app/changelog/data.ts` (bump ao fechar a release).
