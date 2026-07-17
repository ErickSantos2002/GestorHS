# Integração GestorHS → TaskHS v2 (list_id + obs)

**Data:** 2026-07-17
**Origem:** atualização do contrato em [docs/integration.md](../../integration.md) (seção "Mudou na v2").

## Contexto

O TaskHS mudou o contrato da API de integração de **v1 → v2**:

1. O card deixa de ser endereçado por `board` + `list` (nomes) e passa a usar **`list_id`** (inteiro). A lista tem que existir — `404` se o id não existir ou estiver arquivada. Some a criação silenciosa de quadro/lista por nome.
2. A integração **não escreve mais na `description`** (virou campo livre do usuário no TaskHS). Os dados de cada etapa vão em **`obs1…obs6`** — uma observação por fase, nomeada e ligada nas Configurações do quadro.
3. Some a env `INTEGRATION_OWNER_ID` (era do lado TaskHS; não existe no GestorHS).

O GestorHS já espelha cada OS como card no board **Serviço**, com uma descrição rica montada por fase. Esta mudança adapta o GestorHS ao contrato v2 preservando toda a informação atual, apenas redistribuindo as 6 seções para as 6 obs.

## Mapa fase → list_id (produção)

Ids reais do quadro Serviço no TaskHS. A etapa da fase 6 muda de "Serviços 🪛" para **"LIBERADOS DO LABORATÓRIO"**:

| Fase (GestorHS) | Lista no TaskHS | `list_id` |
|---|---|---|
| 4 Recebido | 🚚 Expedição (Abrindo caixa) | 21 |
| 5 Laboratório | 🔬Laboratório Calibração | 22 |
| 6 Pós-Vendas/Serviços | 🔬LIBERADOS DO LABORATÓRIO | 27 |
| 10 Financeiro | 💰Financeiro | 30 |
| 7 Preparando Retorno | 🚚 Expedição (Preparando para Envio) | 34 |
| 8 Correios (Finalizada) | 📮Correios | 35 |

Fase 9 (Cancelada) e fases desconhecidas → `None` (não têm lista; cancelamento é `archived=true` na lista de origem).

## Mapa seção → obs

As 6 seções `_sec_*` existentes casam 1:1 com as 6 obs:

| obs | Seção | Observação |
|---|---|---|
| obs1 | Recebido | Recebe também o **cabeçalho** (Cliente/Aparelho/Serviço) no topo |
| obs2 | Laboratório | Inclui o **link público do certificado** |
| obs3 | Pós-Vendas | |
| obs4 | Financeiro | Inclui número/link da nota fiscal |
| obs5 | Preparando Retorno | Endereço de envio |
| obs6 | Finalizada | Rastreio/postagem |

O payload manda **sempre as 6 chaves** (`null` nas vazias), seguindo a recomendação "envie o estado completo" — assim uma obs de fase que regride é limpa.

## Decisões

- **Ids hardcoded** em `taskhs.py` (como os nomes já eram). Um só TaskHS de produção; em dev a integração fica desligada por env.
- **Corpo das obs sem título interno** (o `📋 Recebido` etc. sai) — a obs já é nomeada no TaskHS. Preserva o conteúdo rico (linhas `- …`, links).
- **`description` omitida sempre** — a integração para de tocar na descrição. Cards antigos mantêm a descrição rica "congelada" até edição manual (filosofia v2: usuário é dono da descrição).
- **Changelog:** leva bump em `data.ts` mesmo sendo backend (muda como o card aparece no TaskHS para a equipe interna).

## Componentes

### `backend/app/core/taskhs.py` (puro)

- Remove `BOARD`.
- `FASE_PARA_LIST_ID: dict[int, int] = {4: 21, 5: 22, 6: 27, 10: 30, 7: 34, 8: 35}`.
- `lista_da_fase()` → **`list_id_da_fase(fase) -> int | None`**.
- `_bloco(linhas)` perde o parâmetro de título; `_sec_*` devolvem só o corpo.
- Novo **`montar_obs(ordem, *, certificados, nota_fiscal_url=None) -> dict`** com as 6 chaves `obs1…obs6` (valor ou `None`); cabeçalho dobrado no topo da `obs1`.
- Remove `montar_descricao`.
- `montar_payload(ordem, *, list_id, arquivado, obs) -> dict`: `source, external_id, list_id, title, obs1…obs6, due_date, priority, archived`. Sem `board`/`list`/`description`.

### `backend/app/api/espelhamento.py` (fonte única do payload)

- Helper `_montar_payload_os(db, ordem, *, list_id, arquivado)`: junta certificados + nota fiscal → `montar_obs` → `montar_payload`.
- `agendar_espelhamento(db, bg, ordem, *, list_id, arquivado)` (param `lista` → `list_id`): agenda `enviar_card` (async, best-effort).
- Novo `espelhar_os_sync(db, ordem, *, list_id, arquivado)`: mesmo payload, envio síncrono que **propaga** erro (backfill).

### `backend/app/integrations/taskhs_client.py` (I/O puro)

- Mantém `integracao_ativa`, `_post`, `enviar_card` (best-effort).
- Ganha `enviar_card_sync(payload)` que propaga erro.
- Remove `espelhar_os` (não monta mais payload aqui — some o import de `taskhs`).

### Callers de fase

- [ordens.py](../../../backend/app/api/ordens.py) e [notas_fiscais.py](../../../backend/app/api/notas_fiscais.py): `taskhs.lista_da_fase(...)` → `taskhs.list_id_da_fase(...)`, param `list_id`.

### `backend/app/scripts/sincronizar_taskhs.py` (backfill)

- Usa `list_id_da_fase` + `espelhamento.espelhar_os_sync(db, ...)`.
- Passa a mandar as obs ricas (com link de certificado) — hoje manda só `ordem.obs` cru.

### Changelog

- Nova entrada em [frontend/src/app/changelog/data.ts](../../../frontend/src/app/changelog/data.ts) (bump de versão) descrevendo a migração da integração TaskHS para `list_id` + `obs`.

## Testes (SQLite in-memory, `test_<modulo>.py`)

- **test_taskhs.py**: `list_id_da_fase` (ints; 9 e desconhecida → `None`); `montar_payload` nova assinatura/chaves (`list_id`, `obs1…obs6`, sem `board`/`list`/`description`).
- **test_taskhs_descricao.py** → testa `montar_obs`: cada seção na obs certa, corpo sem título interno, cabeçalho na obs1, link do certificado na obs2, regras por fase (fase futura → `None`), nota fiscal, telefone primeiro-não-vazio, linhas vazias omitidas.
- **test_ordens_taskhs.py** e **test_sincronizar_taskhs.py**: asserções de payload (list_id/obs) e caminho `espelhar_os_sync`.
- **test_taskhs_client.py**: remove testes de `espelhar_os`; cobre `enviar_card_sync`.

Verificação final: `pytest -q` (backend). Sem frontend runtime (só changelog), sem migração Alembic, envs `TASKHS_*` já existem.

## Fora de escopo

- Sincronização reversa (TaskHS → GestorHS).
- Descoberta automática de `list_id` (é config manual, ids fixos).
- Mexer em membros/etiquetas/comentários/checklists/anexos do card.
