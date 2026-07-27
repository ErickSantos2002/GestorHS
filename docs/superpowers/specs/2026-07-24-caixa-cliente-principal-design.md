# Caixa multi-cliente com Cliente Principal — Design

**Data:** 2026-07-24
**Área:** backend (`app/models/caixa.py`, `app/api/caixas.py`, `app/api/ordens.py`, `app/api/espelhamento.py`, `app/api/growthhs_cards.py`, `app/core/taskhs.py`, `app/core/growthhs_os.py`) + frontend (`src/app/caixas/`, `src/app/ordens/`) + migração Alembic
**Contexto:** ajuste da feature "Caixa como unidade de movimento" (v1.24.x, em produção). **Reverte a invariante "uma caixa = um cliente"** e a substitui por "uma caixa = um cliente principal (+ opcionalmente outros do mesmo grupo)".

## Problema

A invariante **"uma caixa = um cliente"** (imposta na v1.24) obriga a **dividir** uma caixa física que contém aparelhos de vários clientes em **N caixas** — uma por cliente. Isso gera **caixas demais**, sobrecarregando **laboratório e pós-vendas**, que passam a ter que gerar/gerir muito mais caixa do que o necessário. Na prática, esses "vários clientes" numa mesma caixa são o **mesmo grupo econômico** (matriz/filiais / uma entidade que centraliza a cobrança), então dividir é puro atrito sem ganho.

## Objetivo

Permitir **mais de um cliente na mesma caixa** de novo, mantendo as integrações (TaskHS, GrowthHS, NF) **sem ambiguidade** — cada caixa passa a ter um **cliente principal** (definido pela expedição ao sair do Recebido), e as integrações focam nele. Como os clientes de uma caixa são o mesmo grupo, **1 NF e 1 proposta sob o principal** ficam fiscal e comercialmente corretos.

## Não-objetivos

- **Não desfazer as caixas já divididas** pela remediação anterior (as 79 caixas do split de 24/07 seguem como estão; funcionam).
- **Não mudar os certificados por aparelho** — cada certificado continua indo para o **dono real do aparelho** (`ordem.cliente`), não para o principal.
- **Não fazer NF por-cliente-dentro-da-caixa** — como é o mesmo grupo, a NF é 1 só, sob o principal (decisão do produto: caso (a), mesmo dono).
- **Sem mudança no fluxo de fases** nem na trava do laboratório.

## Design

### Modelo de dados
- **`caixas.cliente_principal`** — coluna nova, FK `clientes.id`, nullable. O cliente que as integrações usam.
- **Migração** `0021_caixa_cliente_principal.py (down_revision 0020_propostas)`: adiciona a coluna + **backfill** — para cada caixa existente, `cliente_principal = o cliente das suas OS` (hoje todas são single-client por causa da invariante + remediação, então é o cliente único da caixa; para caixas sem OS, fica NULL).

### Remover a invariante de cliente único
- `app/api/caixas.py` `vincular_ordem`: remover a chamada `_exige_mesmo_cliente(cx, ordem.cliente)` (linha ~142). Vincular OS de qualquer cliente passa a ser permitido. (Manter/remover os helpers `_cliente_da_caixa`/`_exige_mesmo_cliente` conforme deixarem de ser usados.)
- `app/api/ordens.py` `abrir`: remover a checagem que rejeita OS de cliente diferente do da caixa (linhas ~155-157).
- A invariante "toda OS numa caixa" (v1.24) **permanece** — só a de cliente único é revertida.

### Regra do cliente principal no avanço Recebido(4) → Laboratório(5)
No `avancar_caixa` (`caixas.py`), quando `origem == FASE_RECEBIDO (4)`:
- Computar os **clientes distintos** das OS ativas da caixa.
- Se **1 cliente distinto**: definir `cx.cliente_principal` automaticamente (sem exigir input). — caso comum, zero fricção.
- Se **2+ clientes distintos**: exigir que `cliente_principal` já esteja definido (a expedição escolheu no modal); se não, **409** "defina o cliente principal antes de avançar". O `cliente_principal` escolhido **deve ser um dos clientes das OS ativas** da caixa (validar).
- O corpo do avançar (`CaixaAvancarIn`) ganha um campo opcional `cliente_principal: int | None` — usado só nessa transição para gravar o principal escolhido antes/junto do avanço.

**Frontend (expedição):** no `AvancarCaixaModal`/fluxo de avançar da caixa, quando a caixa está em Recebido **e tem 2+ clientes**, mostrar um **seletor "Cliente principal"** (dropdown com os clientes distintos das OS da caixa), obrigatório. Quando é 1 cliente só, não mostra nada (auto). O botão "Avançar caixa" na fase Recebido passa por esse seletor quando aplicável.

### Integrações focam no principal (com fallback)
Um helper único resolve o cliente do card: **`cliente_principal` se definido, senão o cliente da primeira OS** (fallback de robustez — não deveria acontecer pós-Recebido, mas nunca quebra o espelhamento).
- **GrowthHS** (`growthhs_cards.py` `agendar_card_caixa`, ~linha 97): `cliente = <principal ou fallback>` em vez de `ordens[0].cliente_rel`. `devices[]` continua com **todos** os aparelhos da caixa.
- **TaskHS** (`espelhamento.py` / `taskhs.py`): o cliente/contato/endereço do card (cabeçalho, obs de pós-vendas/preparando) usa o **principal**. Seções por-aparelho (laboratório) inalteradas.
- **NF por caixa** (`notas_fiscais.py`): mecanismo inalterado (1 NF fan-out para todas as OS ativas); passa a representar a NF do **principal**. Sem mudança de código obrigatória (o número/arquivo já é único da caixa); a associação conceitual ao principal vem do card.

### Certificados — inalterados
Cada `OSCertificado` continua sendo do `ordem.cliente` (dono real do aparelho). A frota/espelhamento de calibração continua por-aparelho. **Nada muda aqui.**

### Exibição
- No **quadro** (`/caixas/quadro`) e no **detalhe da caixa**, o nome exibido passa a ser o do **cliente principal** (em vez do primeiro OS). Quando a caixa tem **2+ clientes distintos**, mostrar um **"+ N outros"** discreto ao lado do nome.
- Expor `cliente_principal` (id + nome) nos schemas de saída da caixa (`CaixaOut`/`CaixaDetalhe`/`CaixaQuadroItem`).

## Rollout
Produção (caixa em uso). **Forward + backfill** na migração (define o principal das caixas existentes = cliente atual). Baixo risco: single-client existentes recebem o principal óbvio; nada quebra. Mudança fecha como **v1.26.0** (muda regra de negócio central da caixa). Push + rebuild + `alembic upgrade head` (rodado pelo Erick).

## Testes
- **Backend:** vincular/abrir OS de cliente diferente na mesma caixa **passa** (invariante removida). Avançar Recebido→Lab: 1 cliente → auto-define principal; 2+ clientes sem principal → 409; 2+ com principal válido → avança; principal fora dos clientes da caixa → 409. Espelhamento (TaskHS/GrowthHS) usa o principal (e cai no fallback se principal nulo). Migração backfill (conceitual — via inspeção, o suite não roda migração).
- **Frontend:** o seletor de cliente principal aparece só com 2+ clientes na fase Recebido; avançar sem escolher (multi) é bloqueado; quadro/detalhe mostram o principal + "+ N outros".

## Arquivos afetados (mapa)
- **Migração:** `alembic/versions/0021_caixa_cliente_principal.py (down_revision 0020_propostas)`.
- **Model:** `models/caixa.py` (+`cliente_principal` + relationship + property `cliente_principal_nome`).
- **Backend:** `api/caixas.py` (remove invariante, regra no avançar, quadro/detalhe expõem principal), `api/ordens.py` (remove checagem no abrir), `api/espelhamento.py` + `core/taskhs.py` (cliente do card = principal), `api/growthhs_cards.py` + `core/growthhs_os.py` (idem), `schemas/caixas.py` + `schemas/caixa_acoes.py` (`cliente_principal` na saída e no `CaixaAvancarIn`).
- **Frontend:** `caixas/AvancarCaixaModal.tsx` (seletor de principal), `caixas/CaixaDetailPage.tsx` + `ordens/OrdensPage.tsx` (exibição principal + "+ N outros"), `caixas/api.ts` (tipos).
- **Changelog:** v1.26.0.
