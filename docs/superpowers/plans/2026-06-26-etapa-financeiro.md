# Etapa Financeiro na OS — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Inserir a etapa "Financeiro" (ID 10) entre Pós-Vendas e Preparando Retorno, com função responsável própria, que ao avançar marca a OS como paga.

**Architecture:** O workflow linear ganha a fase 10 via o mapa `PROXIMA` e uma "ordem lógica" (`posicao`) para comparações de antes/depois (o ID 10 é numericamente maior que 7/8). Migração 0010 cria a coluna `data_pagamento`, a função `Financeiro` e a fase 10. O `avancar` ganha a transição 10→7 (marca pago). TaskHS mapeia a coluna `💰 Financeiro` e a descrição ganha uma seção. Frontend ganha o rótulo do botão, a fase ativa e a função.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, pytest (SQLite in-memory, Docker); React/TS frontend.

## Global Constraints

- Backend roda em Docker: testes com `docker compose exec -T backend pytest ... -q`. Frontend: `cd frontend && npx tsc -b --noEmit && npm run build`.
- Fase nova: `FASE_FINANCEIRO = 10`, entre Pós-Vendas(6) e Preparando Retorno(7).
- `PROXIMA = {4: 5, 5: 6, 6: 10, 10: 7, 7: 8}`; `ATIVAS = (4, 5, 6, 10, 7)`.
- Ordem lógica: `ORDEM_FASES = {4: 0, 5: 1, 6: 2, 10: 3, 7: 4, 8: 5}`; `posicao(fase) = ORDEM_FASES.get(fase, 99)`.
- Avançar 10→7: `pago=True`, `data_pagamento=agora()`, log `"Pagamento confirmado"`.
- Função responsável: `Financeiro`. Rótulo do botão: `Confirmar pagamento`. Cor da fase: `a855f7`. Lista TaskHS: `💰 Financeiro`.
- Migração 0010: `down_revision = "0009_transferencias_equipamento"`.
- NÃO rodar `alembic` nos testes (SQLite cria as tabelas a partir dos modelos); a migração é aplicada em produção à parte.
- Commits: Conventional Commits PT-BR **sem acentos**, uma linha, sem trailer de co-autor.

---

### Task 1: Workflow + modelo + migração + fixtures + filtros de fase ativa

**Files:**
- Modify: `backend/app/core/os_workflow.py`
- Modify: `backend/app/models/ordem.py`
- Modify: `backend/app/api/dashboard.py`, `backend/app/api/portal.py` (trocar `_FASES_ATIVAS` hard-coded por `wf.ATIVAS`)
- Create: `backend/alembic/versions/0010_etapa_financeiro.py`
- Modify: `backend/tests/conftest.py` (fixtures), `backend/tests/test_os_workflow.py` (atualizar)

**Interfaces:**
- Produces: `wf.FASE_FINANCEIRO = 10`; `wf.PROXIMA`, `wf.ATIVAS` atualizados; `wf.ORDEM_FASES`, `wf.posicao(fase) -> int`; `Ordem.data_pagamento`; fixture `usuario_financeiro`; `fases_seed` retorna chave `"fin"`.

- [ ] **Step 1: Update the workflow unit tests (failing)**

Replace `backend/tests/test_os_workflow.py` with:

```python
from app.core import os_workflow as wf


def test_proxima_fase():
    assert wf.proxima_fase(4) == 5
    assert wf.proxima_fase(5) == 6
    assert wf.proxima_fase(6) == 10   # Pós-Vendas -> Financeiro
    assert wf.proxima_fase(10) == 7   # Financeiro -> Preparando Retorno
    assert wf.proxima_fase(7) == 8
    assert wf.proxima_fase(8) is None
    assert wf.proxima_fase(9) is None


def test_eh_ativa():
    assert all(wf.eh_ativa(f) for f in (4, 5, 6, 10, 7))
    assert not wf.eh_ativa(8)
    assert not wf.eh_ativa(9)


def test_posicao_ordena_logicamente():
    assert wf.posicao(4) < wf.posicao(5) < wf.posicao(6) < wf.posicao(10) < wf.posicao(7) < wf.posicao(8)
    assert wf.posicao(9) == 99      # cancelada/desconhecida -> fim
    assert wf.posicao(999) == 99


def test_constantes():
    assert wf.FASE_RECEBIDO == 4
    assert wf.FASE_FINANCEIRO == 10
    assert wf.FASE_FINALIZADA == 8
    assert wf.FASE_CANCELADA == 9
```

- [ ] **Step 2: Run to verify it fails**

Run: `docker compose exec -T backend pytest tests/test_os_workflow.py -q`
Expected: FAIL (`proxima_fase(6)` ainda devolve 7; `FASE_FINANCEIRO`/`posicao` inexistentes).

- [ ] **Step 3: Implement the workflow**

Replace `backend/app/core/os_workflow.py` with:

```python
"""Grafo de transições da Ordem de Serviço (linear). Puro, sem I/O."""

FASE_RECEBIDO = 4
FASE_FINANCEIRO = 10
FASE_FINALIZADA = 8
FASE_CANCELADA = 9

# fase atual -> próxima fase (linear). Financeiro(10) entra entre Pós-Vendas(6) e Preparando Retorno(7).
PROXIMA = {4: 5, 5: 6, 6: 10, 10: 7, 7: 8}
ATIVAS = (4, 5, 6, 10, 7)

# Ordem lógica das fases (o ID 10 é numericamente maior que 7/8; use isto, não o ID cru).
ORDEM_FASES = {4: 0, 5: 1, 6: 2, 10: 3, 7: 4, 8: 5}


def proxima_fase(fase: int) -> int | None:
    return PROXIMA.get(fase)


def eh_ativa(fase: int) -> bool:
    return fase in ATIVAS


def posicao(fase: int) -> int:
    """Posição lógica da fase na sequência (fora do mapa -> fim)."""
    return ORDEM_FASES.get(fase, 99)
```

- [ ] **Step 4: Add the model column**

In `backend/app/models/ordem.py`, after the `data_aceite` column (the `# adicionadas em 0002` block), add:

```python
    data_pagamento = Column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 5: Replace hard-coded active-phase tuples**

In `backend/app/api/dashboard.py`: remove `_FASES_ATIVAS = (4, 5, 6, 7)` and add `from app.core import os_workflow as wf` (near the other imports). Replace the two uses `_FASES_ATIVAS` with `wf.ATIVAS`.

In `backend/app/api/portal.py`: same — remove `_FASES_ATIVAS = (4, 5, 6, 7)`, add `from app.core import os_workflow as wf`, replace the two uses with `wf.ATIVAS`.

- [ ] **Step 6: Create the migration**

Create `backend/alembic/versions/0010_etapa_financeiro.py`:

```python
"""etapa financeiro: coluna data_pagamento + funcao Financeiro + fase 10

Revision ID: 0010_etapa_financeiro
Revises: 0009_transferencias_equipamento
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_etapa_financeiro"
down_revision = "0009_transferencias_equipamento"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ordens", sa.Column("data_pagamento", sa.DateTime(timezone=True), nullable=True))
    conn = op.get_bind()
    conn.execute(sa.text(
        "INSERT INTO funcoes (descricao) VALUES ('Financeiro') ON CONFLICT (descricao) DO NOTHING"
    ))
    fid = conn.execute(sa.text("SELECT id FROM funcoes WHERE descricao = 'Financeiro'")).scalar()
    conn.execute(
        sa.text(
            "INSERT INTO fases (id, descricao, cor, funcao_responsavel) "
            "VALUES (10, 'Financeiro', 'a855f7', :fid) ON CONFLICT (id) DO NOTHING"
        ),
        {"fid": fid},
    )


def downgrade():
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM fases WHERE id = 10"))
    conn.execute(sa.text("DELETE FROM funcoes WHERE descricao = 'Financeiro'"))
    op.drop_column("ordens", "data_pagamento")
```

- [ ] **Step 7: Update conftest fixtures**

In `backend/tests/conftest.py`, in `fases_seed`, add the Financeiro função and fase 10, and return its id. Change the fixture body to:

```python
@pytest.fixture()
def fases_seed(db_session):
    from app.models import Fase
    exp = _get_or_create_funcao(db_session, "Expedição")
    lab = _get_or_create_funcao(db_session, "Laboratório")
    com = _get_or_create_funcao(db_session, "Comercial Pós-Vendas")
    fin = _get_or_create_funcao(db_session, "Financeiro")
    db_session.add_all([
        Fase(id=4, descricao="Recebido", cor="3b82f6", funcao_responsavel=exp.id),
        Fase(id=5, descricao="Laboratório", cor="6366f1", funcao_responsavel=lab.id),
        Fase(id=6, descricao="Pós-Vendas", cor="f59e0b", funcao_responsavel=com.id),
        Fase(id=10, descricao="Financeiro", cor="a855f7", funcao_responsavel=fin.id),
        Fase(id=7, descricao="Preparando Retorno", cor="14b8a6", funcao_responsavel=exp.id),
        Fase(id=8, descricao="Finalizada", cor="10b981", funcao_responsavel=None),
        Fase(id=9, descricao="Cancelada", cor="ef4444", funcao_responsavel=None),
    ])
    db_session.commit()
    return {"exp": exp.id, "lab": lab.id, "com": com.id, "fin": fin.id}
```

And add a new fixture (after `usuario_lab`):

```python
@pytest.fixture()
def usuario_financeiro(db_session):
    f = _get_or_create_funcao(db_session, "Financeiro")
    u = Usuario(nome="Fin", login="fin", senha=hash_senha("senha123"),
                email="fin@hs.com", funcao_id=f.id, precisa_redefinir_senha=False)
    db_session.add(u); db_session.commit(); db_session.refresh(u)
    return u
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `docker compose exec -T backend pytest tests/test_os_workflow.py -q`
Expected: PASS (4 passed).

- [ ] **Step 9: Commit**

```bash
git add backend/app/core/os_workflow.py backend/app/models/ordem.py backend/app/api/dashboard.py backend/app/api/portal.py backend/alembic/versions/0010_etapa_financeiro.py backend/tests/conftest.py backend/tests/test_os_workflow.py
git commit -m "feat(os): fase Financeiro no workflow + coluna data_pagamento e migracao"
```

---

### Task 2: Transição Financeiro → marca pago (`avancar`)

**Files:**
- Modify: `backend/app/api/ordens.py` (`avancar`)
- Modify: `backend/tests/test_ordens_avancar.py`

**Interfaces:**
- Consumes: `wf.proxima_fase`, `agora()`, fixtures `usuario_financeiro`, `fases_seed`.
- Produces: avançar de uma OS na fase 10 marca `pago=True` + `data_pagamento`.

- [ ] **Step 1: Update the happy-path test + add the new tests (failing)**

In `backend/tests/test_ordens_avancar.py`, replace `test_cadeia_feliz_completa` with the version below (agora passa pelo Financeiro), and append the two new tests:

```python
def test_cadeia_feliz_completa(client, usuario_admin, usuario_comum, usuario_lab, usuario_comercial, usuario_financeiro, fases_seed, os_base, db_session):
    he = _headers(client, "comum", "senha123")       # Expedição
    hl = _headers(client, "lab", "senha123")          # Laboratório
    hc = _headers(client, "comercial", "senha123")    # Comercial
    hf = _headers(client, "fin", "senha123")          # Financeiro
    o = _abrir(client, he, os_base["equipamento_cliente"])
    oid = o["id"]
    # 4 -> 5 (Expedição)
    r = client.post(f"/ordens/{oid}/avancar", json={"obs": "ao lab"}, headers=he)
    assert r.status_code == 200 and r.json()["fase"] == 5
    from app.models import CertificadoModelo
    db_session.add(CertificadoModelo(equipamento=os_base["equipamento"], tipo="C", texto="<p>[serie]</p>"))
    db_session.commit()
    client.post(f"/ordens/{oid}/gerar-certificado", json={"calib_cert": "C-1"}, headers=hl)
    # 5 -> 6 (Laboratório)
    r = client.post(f"/ordens/{oid}/avancar", json={"prox_calibragem": "2027-06-09"}, headers=hl)
    assert r.json()["fase"] == 6
    # 6 -> 10 (Comercial) seta aceite, agora cai no Financeiro
    r = client.post(f"/ordens/{oid}/avancar", json={}, headers=hc)
    assert r.json()["fase"] == 10 and r.json()["aceite"] is True and r.json()["data_aceite"] is not None
    # 10 -> 7 (Financeiro) marca pago
    r = client.post(f"/ordens/{oid}/avancar", json={}, headers=hf)
    assert r.json()["fase"] == 7
    from app.models import Ordem
    o_db = db_session.get(Ordem, oid)
    db_session.refresh(o_db)
    assert o_db.pago is True and o_db.data_pagamento is not None
    # 7 -> 8 (Expedição) exige cod_retorno
    r = client.post(f"/ordens/{oid}/avancar", json={"cod_retorno": "BR123"}, headers=he)
    assert r.json()["fase"] == 8 and r.json()["situacao"] == "F" and r.json()["cod_retorno"] == "BR123"
    # logs: abertura + 5 avanços = 6
    assert len(client.get(f"/ordens/{oid}/logs", headers=he).json()) == 6


def test_financeiro_marca_pago(client, usuario_financeiro, fases_seed, os_base, db_session):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"], fase=10, situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    hf = _headers(client, "fin", "senha123")
    r = client.post(f"/ordens/{o.id}/avancar", json={}, headers=hf)
    assert r.status_code == 200 and r.json()["fase"] == 7
    db_session.refresh(o)
    assert o.pago is True and o.data_pagamento is not None


def test_financeiro_exige_funcao_financeiro_403(client, usuario_lab, fases_seed, os_base, db_session):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"], fase=10, situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    hl = _headers(client, "lab", "senha123")
    assert client.post(f"/ordens/{o.id}/avancar", json={}, headers=hl).status_code == 403
```

- [ ] **Step 2: Run to verify failure**

Run: `docker compose exec -T backend pytest tests/test_ordens_avancar.py -q`
Expected: FAIL (`test_financeiro_marca_pago`: avançar a fase 10 não marca `pago`; `test_cadeia_feliz_completa`: fase após 6 ainda é 7 → agora deve ser 10).

- [ ] **Step 3: Add the avancar branch**

In `backend/app/api/ordens.py`, in `avancar`, the branch for `origem == 6` comment becomes `# Pós-Vendas -> Financeiro`, and add a new `elif origem == 10` branch. The current block:

```python
    elif origem == 6:                     # Pós-Vendas -> Preparando Retorno
        ordem.aceite = True
        ordem.data_aceite = agora()
        texto = "Aceite registrado"
    elif origem == 7:                     # Preparando Retorno -> Finalizada
```
becomes:
```python
    elif origem == 6:                     # Pós-Vendas -> Financeiro
        ordem.aceite = True
        ordem.data_aceite = agora()
        texto = "Aceite registrado"
    elif origem == 10:                    # Financeiro -> Preparando Retorno
        ordem.pago = True
        ordem.data_pagamento = agora()
        texto = "Pagamento confirmado"
    elif origem == 7:                     # Preparando Retorno -> Finalizada
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T backend pytest tests/test_ordens_avancar.py -q`
Expected: PASS (todos, incluindo a cadeia feliz e os dois novos).

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/ordens.py backend/tests/test_ordens_avancar.py
git commit -m "feat(os): avancar Financeiro marca a OS como paga"
```

---

### Task 3: TaskHS — lista e descrição do card

**Files:**
- Modify: `backend/app/core/taskhs.py`
- Modify: `backend/tests/test_taskhs.py`, `backend/tests/test_taskhs_descricao.py`

**Interfaces:**
- Consumes: `wf.posicao`, `wf.FASE_PARA_LISTA`.
- Produces: `lista_da_fase(10) == "💰 Financeiro"`; seção `💰 Financeiro` na descrição; seções de fase usam `posicao`.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_taskhs.py`, add:

```python
def test_lista_da_fase_financeiro():
    from app.core import taskhs
    assert taskhs.lista_da_fase(10) == "💰 Financeiro"
```

In `backend/tests/test_taskhs_descricao.py`, update the `_ordem` base dict to include the payment fields (add these keys to `base`):

```python
        pago=True, data_pagamento=_dt(2026, 6, 26),
```

Then append:

```python
def test_secao_financeiro_confirmado():
    d = taskhs.montar_descricao(_ordem(fase=7), certificados=[])
    assert "💰 Financeiro" in d
    assert "Pagamento: confirmado em 26/06/2026" in d


def test_financeiro_pendente_e_preparando_oculto_durante_financeiro():
    # Em Financeiro (fase 10): mostra pagamento pendente, NAO mostra Preparando Retorno
    o = _ordem(fase=10, pago=False, data_pagamento=None, cod_retorno=None, data_retorno=None)
    d = taskhs.montar_descricao(o, certificados=[])
    assert "💰 Financeiro" in d
    assert "Pagamento: pendente" in d
    assert "🚚 Preparando Retorno" not in d


def test_financeiro_oculto_antes_da_fase():
    o = _ordem(fase=6, pago=False, data_pagamento=None, cod_retorno=None, data_retorno=None)
    d = taskhs.montar_descricao(o, certificados=[])
    assert "💰 Financeiro" not in d
```

- [ ] **Step 2: Run to verify failure**

Run: `docker compose exec -T backend pytest tests/test_taskhs.py tests/test_taskhs_descricao.py -q`
Expected: FAIL (`lista_da_fase(10)` é None; sem seção Financeiro; em fase 10 o Preparando ainda aparece por causa do `>=` numérico).

- [ ] **Step 3: Implement in `backend/app/core/taskhs.py`**

Add the import at the top (after the module docstring):

```python
from app.core import os_workflow as wf
```

Add the list entry to `FASE_PARA_LISTA`:

```python
    10: "💰 Financeiro",
```
(insert the `10:` line between the `6:` and `7:` entries to keep logical order)

Change the two phase-gated sections to use `posicao`:

```python
def _sec_posvendas(ordem) -> str | None:
    if wf.posicao(ordem.fase) < wf.posicao(6):
        return None
    ...

def _sec_preparando(ordem) -> str | None:
    if wf.posicao(ordem.fase) < wf.posicao(7):
        return None
    ...
```

Add the new section function (after `_sec_posvendas`):

```python
def _sec_financeiro(ordem) -> str | None:
    if wf.posicao(ordem.fase) < wf.posicao(10):
        return None
    if ordem.pago:
        linha = f"Pagamento: confirmado em {_fmt(ordem.data_pagamento)}" if ordem.data_pagamento else "Pagamento: confirmado"
    else:
        linha = "Pagamento: pendente"
    return _bloco("💰 Financeiro", [linha])
```

In `montar_descricao`, change the `_sec_recebido` gate to `posicao` and insert the Financeiro section between Pós-Vendas and Preparando:

```python
def montar_descricao(ordem, *, certificados: list[dict]) -> str | None:
    cabecalho = "\n".join(_cabecalho(ordem)) or None
    secoes = [
        _sec_recebido(ordem) if wf.posicao(ordem.fase) >= wf.posicao(4) else None,
        _sec_laboratorio(ordem, certificados),
        _sec_posvendas(ordem),
        _sec_financeiro(ordem),
        _sec_preparando(ordem),
        _sec_finalizada(ordem),
    ]
    blocos = [b for b in [cabecalho, *secoes] if b]
    return "\n\n".join(blocos) if blocos else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T backend pytest tests/test_taskhs.py tests/test_taskhs_descricao.py -q`
Expected: PASS (existentes + novos).

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/taskhs.py backend/tests/test_taskhs.py backend/tests/test_taskhs_descricao.py
git commit -m "feat(integracao): coluna e secao Financeiro no card do TaskHS"
```

---

### Task 4: Frontend + changelog + verificação final

**Files:**
- Modify: `frontend/src/app/ordens/api.ts`
- Modify: `frontend/src/auth/roles.ts`
- Modify: `frontend/src/app/changelog/data.ts`

- [ ] **Step 1: Frontend constants**

In `frontend/src/app/ordens/api.ts`:
- In `TRANSICOES`, add the entry for fase 10 (insert between `6:` and `7:`):
  ```ts
  10: { rotulo: 'Confirmar pagamento' },
  ```
- Change `FASES_ATIVAS`:
  ```ts
  export const FASES_ATIVAS = [4, 5, 6, 10, 7]
  ```

In `frontend/src/auth/roles.ts`, add after `FUNCAO_COMERCIAL`:
```ts
export const FUNCAO_FINANCEIRO = 'Financeiro'
```

- [ ] **Step 2: Changelog v1.11.0**

In `frontend/src/app/changelog/data.ts`, insert as the **first** entry of `CHANGELOG`:
```ts
  {
    versao: '1.11.0',
    data: '26/06/2026',
    itens: [
      { tipo: 'novidade', texto: 'As Ordens de Serviço agora passam por uma etapa "Financeiro" entre Pós-Vendas e Preparando Retorno. O setor financeiro confirma o pagamento (botão "Confirmar pagamento") antes de a OS ser liberada para envio; a OS fica marcada como paga com a data. A nova coluna aparece no quadro de Ordens e o cartão no TaskHS reflete a etapa.' },
    ],
  },
```

- [ ] **Step 3: Verify the frontend**

Run: `cd frontend && npx tsc -b --noEmit && npm run build`
Expected: tsc sem erros, build OK.

- [ ] **Step 4: Run the full backend suite (no regression)**

Run: `docker compose exec -T backend pytest -q`
Expected: PASS (toda a suíte verde).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/ordens/api.ts frontend/src/auth/roles.ts frontend/src/app/changelog/data.ts
git commit -m "feat(ux): etapa Financeiro no front e changelog v1.11.0"
```

---

## Notas de aplicação (produção, fora dos testes)

1. Aplicar a migração: `docker compose exec -T backend alembic upgrade head` (cria a coluna `data_pagamento`, a função `Financeiro` e a fase 10). **Requer consentimento — DDL/seed em produção.**
2. Criar/atribuir um usuário com a função **Financeiro** (Admin sempre consegue avançar a etapa, mas o setor precisa do próprio acesso).
3. Validar E2E: abrir OS → avançar até Pós-Vendas → avançar (cai em Financeiro, coluna nova no quadro e card `💰 Financeiro` no TaskHS) → logar como Financeiro → "Confirmar pagamento" → OS vai para Preparando Retorno marcada como paga.
