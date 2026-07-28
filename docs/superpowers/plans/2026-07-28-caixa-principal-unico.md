# Caixa: cliente principal do aparelho único — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer o card da caixa não mostrar "+N outro" quando há um único cliente, manter `cliente_principal` correto (auto-set do dono na caixa de 1 cliente) e blindar as integrações contra principal órfão; mais um script de backfill.

**Architecture:** Núcleo puro novo `app/core/caixa.py` com a lógica de contagem/validação, reutilizado pelo quadro, pela property do model, pelas integrações e por um helper `sincronizar_principal` chamado quando a composição da caixa muda. Backfill via script dry-run/`--aplicar`.

**Tech Stack:** Backend Python 3.12 · FastAPI · SQLAlchemy 2 · pytest.

## Global Constraints

- Domínio PT-BR; commits Conventional Commits em português **sem acentos** (ASCII), uma linha, sem trailer. Escopos: `caixa`, `changelog`.
- **Sem migração** (só lógica). Mini versão **v1.27.2**.
- Regra de negócio: **1 cliente na caixa → esse é o principal (automático); 2+ clientes → escolha manual (fica como está, no avanço Recebido→Lab). Nunca auto-mexer no principal de caixa com 2+ clientes.**
- `git add` explícito sempre (nunca `git add -A`; há untracked alheio: `backend/relatorios/`, `docs/proposta_comercial*.pdf`).
- Testes backend: SQLite in-memory (`conftest.py`). Há **4 falhas pré-existentes de upload** (`/data/uploads`) — alheias; não conserte, não introduza novas.
- `ATIVAS`/`eh_ativa` vêm de `app.core.os_workflow as wf`.

---

## Task 1: núcleo puro `core/caixa.py` + display robusto (quadro + property)

**Files:** Create `backend/app/core/caixa.py`, `backend/tests/test_caixa_core.py`. Modify `backend/app/api/caixas.py` (quadro), `backend/app/models/caixa.py` (property). Test `backend/tests/test_caixas_quadro_outros.py`.

**Interfaces produzidas (usadas nas Tasks 2 e 3):**
- `contar_outros(clientes) -> int`
- `principal_valido(principal, clientes) -> int | None`
- `cliente_unico(clientes) -> int | None`

- [ ] **Step 1: Teste (RED)** — `backend/tests/test_caixa_core.py` (funções puras):

```python
from app.core.caixa import contar_outros, principal_valido, cliente_unico

def test_contar_outros():
    assert contar_outros([]) == 0
    assert contar_outros([7]) == 0
    assert contar_outros([7, 7]) == 0            # mesmo cliente, 2 OS
    assert contar_outros([7, 9]) == 1
    assert contar_outros([7, 9, 9, None]) == 1   # ignora None e repetidos

def test_principal_valido():
    assert principal_valido(7, [7, 9]) == 7
    assert principal_valido(5, [7, 9]) is None   # stale
    assert principal_valido(None, [7]) is None

def test_cliente_unico():
    assert cliente_unico([7, 7]) == 7
    assert cliente_unico([]) is None
    assert cliente_unico([7, 9]) is None
    assert cliente_unico([None, 7, 7]) == 7
```

- [ ] **Step 2: Rodar e ver falhar** — `cd backend && source .venv/bin/activate && pytest tests/test_caixa_core.py -v` → FAIL (módulo inexistente).

- [ ] **Step 3: Implementar** — `backend/app/core/caixa.py`:

```python
"""Lógica pura de composição de clientes de uma caixa (sem I/O)."""
from collections.abc import Iterable


def _distintos(clientes: Iterable[int | None]) -> set[int]:
    return {c for c in clientes if c is not None}


def contar_outros(clientes: Iterable[int | None]) -> int:
    """Quantos clientes além do principal exibido no card (= distintos - 1)."""
    return max(0, len(_distintos(clientes)) - 1)


def principal_valido(principal: int | None, clientes: Iterable[int | None]) -> int | None:
    """O principal só vale se ainda estiver entre os clientes da caixa; senão None (fallback)."""
    if principal is not None and principal in _distintos(clientes):
        return principal
    return None


def cliente_unico(clientes: Iterable[int | None]) -> int | None:
    """O único cliente distinto, se houver exatamente um; senão None."""
    d = _distintos(clientes)
    return next(iter(d)) if len(d) == 1 else None
```

- [ ] **Step 4: Teste (RED) do display** — `backend/tests/test_caixas_quadro_outros.py`: monta caixa com 1 OS ativa e `cliente_principal=None` (e outra com principal apontando pra cliente que não está na caixa), chama `GET /ordens/quadro-caixas` (ou o endpoint do quadro de caixas — confira o path real em `api/caixas.py`, é `/caixas/quadro`) autenticado, e afirma que o item da caixa tem `outros_clientes == 0`; monta caixa com 2 OS de clientes diferentes e afirma `outros_clientes == 1`. Reuse fixtures do conftest (usuário interno + caixa/OS). Adicione também um teste do model direto: uma `Caixa` com 1 cliente e `cliente_principal=None` → `caixa.outros_clientes == 0`.

- [ ] **Step 5: Rodar e ver falhar** — `pytest tests/test_caixas_quadro_outros.py -v` → FAIL (hoje dá 1).

- [ ] **Step 6: Implementar display** —
  - `backend/app/api/caixas.py`, no laço do quadro (hoje linhas ~76-77):

```python
from app.core.caixa import contar_outros, principal_valido   # no topo do arquivo

# dentro do for cx / for ativas:
clientes_ids = [o.cliente for o in ativas]
pid = principal_valido(cx.cliente_principal, clientes_ids)
if pid is not None:
    principal_nome = cx.cliente_principal_nome
else:
    principal_nome = next((o.cliente_nome for o in ativas), None)
outros = contar_outros(clientes_ids)
```

  - `backend/app/models/caixa.py`, property `outros_clientes` (hoje linhas 40-45):

```python
@property
def outros_clientes(self) -> int:
    from app.core.caixa import contar_outros
    return contar_outros(o.cliente for o in self.ordens)
```

- [ ] **Step 7: Rodar e ver passar** — `pytest tests/test_caixa_core.py tests/test_caixas_quadro_outros.py -v && pytest -q` (só as 4 de upload falham).
- [ ] **Step 8: Commit** — `git add backend/app/core/caixa.py backend/tests/test_caixa_core.py backend/tests/test_caixas_quadro_outros.py backend/app/api/caixas.py backend/app/models/caixa.py backend/tests/conftest.py && git commit -m "fix(caixa): card nao mostra outro cliente quando ha um so aparelho"`

---

## Task 2: auto-set do principal + blindagem das integrações

**Files:** Modify `backend/app/api/caixas.py` (`sincronizar_principal` + wire em vincular/desvincular), `backend/app/api/ordens.py` (`abrir`), `backend/app/api/growthhs_cards.py` (`cliente_do_card`), `backend/app/api/espelhamento.py` (sort). Test `backend/tests/test_caixa_principal_sync.py`.

**Interfaces consumidas:** `cliente_unico`, `principal_valido` (Task 1).
**Interfaces produzidas:** `sincronizar_principal(db, cx) -> None` (em `app/api/caixas.py`).

- [ ] **Step 1: Teste (RED)** — `backend/tests/test_caixa_principal_sync.py`:
  - Abrir uma OS numa caixa nova (via `POST /ordens`) → recarregar a caixa → `caixa.cliente_principal == cliente_do_aparelho`.
  - Numa caixa com 2 OS de clientes A e B (principal = A), desvincular a OS de A (`DELETE`/endpoint de desvincular — confira o path em `api/caixas.py`) → `caixa.cliente_principal == B` (re-sincronizou).
  - Caixa com 2 clientes → `sincronizar_principal` não altera um principal já válido.
  - `cliente_do_card`: caixa com principal válido → retorna esse cliente; com principal stale (não está nas OS) → retorna o cliente da 1ª OS; principal NULL → 1ª OS. (Importar `from app.api.growthhs_cards import cliente_do_card`.)

- [ ] **Step 2: Rodar e ver falhar** — `pytest tests/test_caixa_principal_sync.py -v` → FAIL.

- [ ] **Step 3: Implementar**
  - `backend/app/api/caixas.py` — helper (usa `cliente_unico`; consulta as OS ativas por query, não pela relationship, pra ser confiável pós-flush):

```python
from app.core.caixa import cliente_unico   # no topo

def sincronizar_principal(db, cx) -> None:
    """Se a caixa tem exatamente 1 cliente ativo, ele vira o principal.
    0 ou 2+ clientes: nao mexe (2+ e escolha manual no avanco)."""
    clientes = [c for (c,) in db.query(Ordem.cliente)
                .filter(Ordem.caixa == cx.id, Ordem.fase.in_(wf.ATIVAS)).all()]
    unico = cliente_unico(clientes)
    if unico is not None:
        cx.cliente_principal = unico
```

  Chamar `sincronizar_principal(db, cx)` em `vincular_ordem` (após `ordem.caixa = cx.id` + flush) e em `desvincular_ordem` (após `ordem.caixa = None` + flush), antes do commit. Garanta que `Ordem` e `wf` estão importados no módulo.
  - `backend/app/api/ordens.py` — em `abrir`, após `cx.fase = fase_inicial` e o `db.flush()` (a OS já tem id e caixa setada), antes do `db.commit()`:

```python
from app.api.caixas import sincronizar_principal   # import no topo (cuidado com import circular — se houver, defina o helper em app/core? Nao: caixas.py importa de ordens? verifique. Se circular, mova sincronizar_principal para um modulo util sem deps de FastAPI.)

sincronizar_principal(db, cx)
```

  > ⚠️ Se `from app.api.caixas import sincronizar_principal` causar import circular com `ordens.py`, mova `sincronizar_principal` para `app/core/caixa.py` recebendo a lista de clientes já consultada (mantendo core puro: a query fica no chamador, o core só decide). Ex.: chamador monta `clientes = [...query...]` e faz `p = cliente_unico(clientes); if p: cx.cliente_principal = p`. Prefira essa forma se houver qualquer ciclo.
  - `backend/app/api/growthhs_cards.py` — `cliente_do_card`:

```python
from app.core.caixa import principal_valido

def cliente_do_card(caixa):
    """O cliente que as integracoes usam: o principal (se ainda na caixa), com fallback na 1a OS."""
    clientes = [o.cliente for o in caixa.ordens]
    if principal_valido(caixa.cliente_principal, clientes) is not None:
        return caixa.cliente_principal_rel
    return caixa.ordens[0].cliente_rel if caixa.ordens else None
```

  - `backend/app/api/espelhamento.py` — no `_montar_payload_caixa`, trocar o guard do sort por `principal_valido` (consistência; hoje já é inócuo):

```python
from app.core.caixa import principal_valido
pid = principal_valido(caixa.cliente_principal, [o.cliente for o in ordens])
if pid is not None:
    ordens.sort(key=lambda o: 0 if o.cliente == pid else 1)
```

- [ ] **Step 4: Rodar e ver passar** — `pytest tests/test_caixa_principal_sync.py -v && pytest -q`.
- [ ] **Step 5: Commit** — `git add backend/app/api/caixas.py backend/app/api/ordens.py backend/app/api/growthhs_cards.py backend/app/api/espelhamento.py backend/tests/test_caixa_principal_sync.py && git commit -m "fix(caixa): auto-define cliente principal do aparelho unico e blinda integracoes"`

---

## Task 3: script de backfill + changelog v1.27.2 + verificação

**Files:** Create `backend/app/scripts/sincronizar_principal_caixas.py`. Modify `frontend/src/app/changelog/data.ts`. Test opcional `backend/tests/test_script_sincronizar_principal.py` (se der pra testar a função de decisão sem I/O).

- [ ] **Step 1: Script** — `backend/app/scripts/sincronizar_principal_caixas.py`, espelhando o estilo dos outros scripts (`app/scripts/*.py`): **dry-run por padrão**, flag `--aplicar` para gravar. Percorre caixas em fase ativa; para cada uma monta `clientes = [OS ativas].cliente`; se `cliente_unico(clientes)` retorna um id **e** difere do `cliente_principal` atual, marca a mudança. Imprime tabela (`caixa_id | principal_atual -> novo | dono`) e um resumo (`N mudariam`). Só faz `db.commit()` quando `--aplicar`. Usa `SessionLocal`, `cliente_unico` do core, `wf.ATIVAS`. Sem `--aplicar`, **não escreve nada** (nem commit).

```python
# esqueleto — seguir o padrao dos scripts existentes p/ argparse e SessionLocal
import argparse
from app.models.database import SessionLocal
from app.models import Ordem, Caixa
from app.core.caixa import cliente_unico
from app.core import os_workflow as wf

def principal_alvo(db, cx):
    clientes = [c for (c,) in db.query(Ordem.cliente)
                .filter(Ordem.caixa == cx.id, Ordem.fase.in_(wf.ATIVAS)).all()]
    return cliente_unico(clientes)

def main(aplicar: bool):
    db = SessionLocal()
    try:
        mudancas = []
        for cx in db.query(Caixa).filter(Caixa.fase.in_(list(wf.ATIVAS))).all():
            alvo = principal_alvo(db, cx)
            if alvo is not None and cx.cliente_principal != alvo:
                mudancas.append((cx.id, cx.cliente_principal, alvo))
                if aplicar:
                    cx.cliente_principal = alvo
        for cid, antigo, novo in mudancas:
            print(f"CX {cid}: principal {antigo} -> {novo}")
        print(f"{len(mudancas)} caixa(s) {'ATUALIZADA(S)' if aplicar else 'mudariam (dry-run)'}")
        if aplicar:
            db.commit()
    finally:
        db.close()

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true", help="grava as mudancas (padrao: dry-run)")
    main(ap.parse_args().aplicar)
```

- [ ] **Step 2: Changelog** — 1ª entrada do array em `frontend/src/app/changelog/data.ts`:
```ts
{
  versao: '1.27.2',
  data: '28/07/2026',
  itens: [
    { tipo: 'correcao', texto: 'As caixas com um único aparelho não mostram mais "+1 outro" cliente. O cliente do aparelho passa a ser definido automaticamente como principal da caixa na abertura; a escolha manual do principal continua só para caixas com aparelhos de clientes diferentes.' },
  ],
},
```
- [ ] **Step 3: Backend** — `cd backend && source .venv/bin/activate && pytest -q` (só as 4 de upload). Rodar o script em dry-run pra sanidade: `python -m app.scripts.sincronizar_principal_caixas` (NÃO passar `--aplicar`; é contra o banco do `.env` — só imprime).
- [ ] **Step 4: Frontend** — `cd frontend && npm run lint && npx tsc -b --noEmit && npm run build`.
- [ ] **Step 5: Commit** — `git add backend/app/scripts/sincronizar_principal_caixas.py frontend/src/app/changelog/data.ts && git commit -m "feat(caixa): script de backfill do cliente principal + changelog v1.27.2"`

---

## Self-Review

- **Cobertura da spec:** núcleo puro (T1) · display quadro+property (T1) · auto-set abrir/vincular/desvincular (T2) · blindagem cliente_do_card+espelhamento (T2) · backfill dry-run/--aplicar (T3) · changelog (T3). ✅
- **Regra do 2+ respeitada:** `sincronizar_principal` e o backfill só agem quando `cliente_unico` retorna id (1 cliente); nunca mexem em 2+.
- **Placeholder scan:** sem TBD; código real. O único ponto aberto é o aviso de import circular na T2 (com caminho de contorno explícito).
- **Nomes/tipos consistentes:** `contar_outros`/`principal_valido`/`cliente_unico`/`sincronizar_principal`.
