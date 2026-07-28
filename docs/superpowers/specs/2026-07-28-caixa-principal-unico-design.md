# Caixa: cliente principal do aparelho único — Design

**Data:** 2026-07-28
**Área:** backend (`app/core/caixa.py` novo, `app/api/caixas.py`, `app/models/caixa.py`, `app/api/ordens.py`, `app/api/growthhs_cards.py`, `app/api/espelhamento.py`, script) + changelog
**Tipo:** correção de bug (display) + endurecimento de dados/integrações + backfill.

## Problema

O card da caixa mostra **"+1 outro"** mesmo em caixas com **1 aparelho só**. Auditoria em produção (325 caixas ativas): 320 corretas, **5 com phantom** — 3 com `cliente_principal` **NULL** (caixas novas em Recebido) e 2 com principal **stale** (aponta pra cliente que não é mais o dono do aparelho, após remanejamento). Não há hoje nenhuma caixa 2+ clientes.

Duas causas:
1. `cliente_principal` só é definido no avanço Recebido→Lab; caixa recém-aberta fica NULL. Regra desejada: **1 aparelho → o dono é o principal automaticamente; escolher só quando 2+ clientes.**
2. A conta de "outros" ([caixas.py:77](../../../backend/app/api/caixas.py) e a property [caixa.py:41](../../../backend/app/models/caixa.py)) faz `o.cliente != cliente_principal` — com principal NULL/stale, conta o próprio dono como "outro".

Impacto: as 3 NULL são **só visuais** (fallback pra 1ª OS já resolve card/NF/integração). As 2 stale são **mais que visual** — `cliente_do_card` ([growthhs_cards.py:45](../../../backend/app/api/growthhs_cards.py)) usa o principal **direto, sem checar se ainda está na caixa**, então um card do GrowthHS iria pro cliente errado.

## Objetivo

Fazer o card refletir a realidade (sem phantom), manter `cliente_principal` correto no dado, e blindar as integrações contra principal órfão. Manter a escolha manual do principal só para caixas com 2+ clientes.

## Design

### 1. Núcleo puro — `app/core/caixa.py` (sem I/O)
- `contar_outros(clientes: Iterable[int | None]) -> int` → `max(0, len({c for c in clientes if c is not None}) - 1)`.
- `principal_valido(principal: int | None, clientes: Iterable[int | None]) -> int | None` → devolve `principal` se estiver no conjunto de clientes (não-None), senão `None` (sinaliza fallback).
- `cliente_unico(clientes: Iterable[int | None]) -> int | None` → o único cliente se houver exatamente um distinto, senão `None`.

### 2. Display robusto
- **Quadro** ([caixas.py:76-77](../../../backend/app/api/caixas.py)): `outros = contar_outros(o.cliente for o in ativas)`; headline usa o principal válido — se `principal_valido(cx.cliente_principal, clientes_ativos)` é None, cai pro nome da 1ª OS (já é o comportamento do `or next(...)`, mas passa a ignorar principal stale).
- **Property do model** ([caixa.py:41](../../../backend/app/models/caixa.py)): `outros_clientes = contar_outros(o.cliente for o in self.ordens)`.

### 3. Auto-set do principal — `sincronizar_principal(db, cx)`
Helper que consulta os clientes das OS **ativas** da caixa (`SELECT DISTINCT ... WHERE caixa=cx.id AND fase IN ATIVAS`) e, se `cliente_unico` retornar um id, faz `cx.cliente_principal = esse id`. Se 0 ou 2+ clientes, **não mexe** (2+ é escolha manual no avanço). Chamado em:
- `abrir` ([ordens.py](../../../backend/app/api/ordens.py)) após o flush, antes do commit.
- `vincular_ordem` e `desvincular_ordem` ([caixas.py](../../../backend/app/api/caixas.py)) — é o desvincular que gera stale ao remover a OS do principal.

### 4. Blindagem das integrações
- `cliente_do_card` ([growthhs_cards.py:43-47](../../../backend/app/api/growthhs_cards.py)): usa `principal_valido` — só retorna `cliente_principal_rel` se o principal estiver entre os clientes da caixa; senão fallback na 1ª OS.
- Sort do espelhamento ([espelhamento.py:43-44](../../../backend/app/api/espelhamento.py)): idem via `principal_valido` (hoje já é inócuo com stale, mas fica consistente).

### 5. Backfill — `app/scripts/sincronizar_principal_caixas.py`
Script **dry-run por padrão** (imprime as caixas que mudariam: id, principal atual → novo, dono), `--aplicar` para gravar. Percorre caixas em fase ativa, e para as de **1 cliente** onde o principal está NULL ou ≠ o dono, seta o principal = dono. Idempotente (as 320 corretas não mudam). O Erick roda depois de conferir o dry-run.

## Fora de escopo
- Caixas 2+ clientes com principal stale (não existem hoje; o fallback do display/integração já cobre; re-escolha é no avanço).
- Inconsistência pré-existente ativa-vs-todas as OS na property do model (mantém o conjunto atual de cada call site; só corrige a fórmula).

## Rollout
Produção, **sem migração** (só lógica). Deploy = push + rebuild. Backfill = script read-write que o Erick roda após dry-run. Mini versão **v1.27.2**.

## Testes
- **core/caixa.py:** `contar_outros` (0/1/1-mesmo-cliente→0, 2→1); `principal_valido` (válido, stale→None, None→None); `cliente_unico` (1, 0, 2→None).
- **Quadro/property:** 1 cliente com principal NULL → `outros_clientes == 0`; com principal stale → 0 e headline = dono; 2 clientes → 1.
- **sincronizar_principal:** abrir caixa nova → principal = dono; desvincular deixando 1 cliente → principal re-sincroniza; 2 clientes → não mexe.
- **cliente_do_card:** principal válido → principal; NULL/stale → 1ª OS.

## Arquivos
Backend: `core/caixa.py` (novo), `api/caixas.py`, `models/caixa.py`, `api/ordens.py`, `api/growthhs_cards.py`, `api/espelhamento.py`, `scripts/sincronizar_principal_caixas.py` (novo). Testes espelhando. Changelog v1.27.2.
