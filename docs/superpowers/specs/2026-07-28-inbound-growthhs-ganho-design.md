# Integração inbound: GrowthHS move caixa Pós-Vendas → Financeiro — Design

**Data:** 2026-07-28
**Área:** backend (`core/config.py`, `api/deps.py`, novo `api/integracao_growthhs.py`, refactor em `api/caixas.py`, `main.py`) + doc de integração.
**Tipo:** nova integração inbound (a via inversa das atuais).

## Problema

Hoje o GestorHS **empurra** para GrowthHS/TaskHS. O pós-vendas usa o **GrowthHS** para negociar com o cliente; quando dá **ganho** no negócio, precisa mover a caixa de **Pós-Vendas(6) → Financeiro(10)** no GestorHS. Queremos que o **GrowthHS chame o GestorHS** (via API key que não expira) para fazer essa transição.

## Contexto

- `wf.proxima_fase(6) == 10` — mover para Financeiro = avançar a caixa uma fase. O `avancar_caixa` já faz o efeito do 6→10 (por OS: `aceite=True`/`data_aceite`, `fase=10`; loga; `cx.fase=10`; espelha o card). Não recria card (o `agendar_card_caixa` só roda no Lab). Colunas `aceite`/`data_aceite` já existem → **sem migração**.
- Chaves atuais são **outbound** (`TASKHS_API_KEY`, `HSGROWTH_API_KEY`, header `X-API-Key`, "vazio = desligada"). Não há auth **inbound** por API-key ainda.
- O card do GrowthHS guarda `external_id = str(caixa.id)` → o GrowthHS sabe o `caixa_id`.

## Design

### 1. Config — chave inbound
Nova `GROWTHHS_INBOUND_API_KEY: str = ""` em `Settings` (env, **não expira**, **vazio = integração inbound desligada**, revoga trocando o valor). Distinta das chaves outbound.

### 2. Auth por API-key (dependency nova em `api/deps.py`)
`require_growthhs_inbound` — lê o header **`X-API-Key`**:
- Se `settings.GROWTHHS_INBOUND_API_KEY` vazio → **503** (integração desligada).
- Header ausente ou diferente (comparação **tempo-constante**, `secrets.compare_digest`) → **401**.
- Igual → passa. **Não** injeta usuário (a chave é a autorização).

### 3. Refactor: extrair o núcleo de avanço em `api/caixas.py`
Extrair o fan-out + efeitos por fase + log + `cx.fase` + espelhamento (hoje linhas ~216-247 do `avancar_caixa`) numa função `executar_avanco_caixa(db, cx, *, origem, destino, ativas, usuario, obs, cod_retorno, background_tasks)`. O `avancar_caixa` mantém seus guards (função da fase, `pode_avancar`, principal do Recebido, cod_retorno) e chama o núcleo. **Comportamento idêntico** (travado por teste). Assim o endpoint inbound reusa exatamente o mesmo caminho do 6→10.

### 4. Endpoint inbound — `POST /integracao/growthhs/caixas/{caixa_id}/ganho`
- Auth: `Depends(require_growthhs_inbound)` (sem usuário/JWT).
- Corpo: `{ "observacao": string | null }` (texto do pós-vendas: valor do negócio, proposta, OC etc. — vai pro log).
- Lógica (idempotente):
  - `cx.fase == 6` (Pós-Vendas) → `executar_avanco_caixa(origem=6, destino=10, usuario=None, obs=observacao, cod_retorno=None)`. Loga como "Movida para Financeiro via GrowthHS" + a observação. Resposta **200** `{ movida: true, caixa_id, fase: 10 }`.
  - `cx.fase in (10, 7, 8)` (já em Financeiro ou além) → **no-op**, resposta **200** `{ movida: false, caixa_id, fase }` (repetição segura).
  - `cx.fase in (4, 5)`, `9` (cancelada) ou `None` → **409** `{ detail: "caixa nao esta em Pos-Vendas" }`.
  - Caixa inexistente → **404**.
- Registrar router em `main.py`.

### Segurança (blast radius mínimo)
A chave só autoriza **essa transição** (6→10), só em caixa que está em Pós-Vendas. Não move fase arbitrária, não lê/edita outros dados. Empty-by-default; revogável; comparação tempo-constante; toda chamada logada (auditoria).

## Fora de escopo
- Lado do GrowthHS (configurar a chamada) — feito por eles depois, guiado pelo doc.
- Endpoint de avanço genérico; outras transições.

## Rollout
Backend, **sem migração**. A integração nasce **desligada** (chave vazia). Versão **v1.28.0**. + **doc de integração** (`docs/integracao-growthhs-inbound.md`).

## Testes
- **Auth:** sem header → 401; header errado → 401; chave vazia (desligada) → 503; chave certa → passa.
- **Refactor:** os testes atuais de `avancar_caixa` continuam verdes (comportamento preservado).
- **Endpoint:** caixa em Pós-Vendas(6) → vira Financeiro(10), `aceite=True`, log contém a observação, `movida:true`; caixa já em 10 → `movida:false` no-op 200; caixa em Lab(5) → 409; caixa inexistente → 404; chave inválida → 401.

## Arquivos
`core/config.py` (chave), `api/deps.py` (dependency), `api/caixas.py` (extrair núcleo), `api/integracao_growthhs.py` (novo endpoint + schema), `main.py` (router), testes. Doc `docs/integracao-growthhs-inbound.md`. Changelog v1.28.0.
