# Caixa multi-cliente com Cliente Principal — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir mais de um cliente na mesma caixa, com um `cliente_principal` (definido pela expedição ao sair do Recebido) que as integrações (TaskHS, GrowthHS, NF) passam a usar.

**Architecture:** Reverte a invariante "uma caixa = um cliente" (remove as 2 travas). Adiciona `caixas.cliente_principal`. No avanço Recebido→Laboratório, o principal é auto-definido se há 1 cliente só, ou exigido (seletor da expedição) se há 2+. O espelhamento passa a resolver o cliente do card como `principal-ou-fallback(1ª OS)`. Certificados por aparelho não mudam.

**Tech Stack:** Backend Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · pytest (SQLite in-memory). Frontend React 19 · TS · Vite · Vitest.

## Global Constraints

- **Domínio PT-BR**; commits Conventional Commits em português **sem acentos** (ASCII), uma linha, **sem trailer de co-autor**. Escopos: `caixa`, `integr`, `ux`, `ui`, `changelog`.
- **Testes backend**: SQLite in-memory (`conftest.py`); frontend Vitest. Há **4 falhas pré-existentes de upload** (`/data/uploads` PermissionError) — alheias, não conserte, não introduza novas.
- **Não mudar certificados por aparelho** (continuam de `ordem.cliente`), nem a trava do laboratório, nem "toda OS numa caixa".
- **Migração**: `revision="0021_caixa_cliente_principal"`, `down_revision="0020_propostas"`.
- **Changelog**: v1.26.0.
- **Produção**: caixa em uso. Migração faz backfill (`cliente_principal` = cliente atual das caixas existentes). Deploy = push + rebuild + `alembic upgrade head` (Erick).
- **git add explícito** sempre (nunca `git add -A`; há `backend/relatorios/` + PDFs untracked que NÃO entram).

---

## Estrutura de arquivos

**Backend — criar:** `alembic/versions/0021_caixa_cliente_principal.py`.
**Backend — modificar:** `models/caixa.py`, `schemas/caixas.py`, `schemas/caixa_acoes.py`, `api/caixas.py`, `api/ordens.py`, `api/espelhamento.py`, `api/growthhs_cards.py`. Test: `tests/test_caixa_avancar.py`, `tests/test_caixa_multicliente.py` (novo).
**Frontend — criar:** `src/app/caixas/ClientePrincipalModal.tsx`. **Modificar:** `src/app/caixas/api.ts`, `src/app/caixas/CaixaDetailPage.tsx`, `src/app/ordens/OrdensPage.tsx`, `src/app/changelog/data.ts`.

---

## Task 1: Migração 0021 (coluna + backfill)

**Files:** Create `backend/alembic/versions/0021_caixa_cliente_principal.py`

**Interfaces:** Produces coluna `caixas.cliente_principal` (Integer, FK `clientes.id`, nullable) com backfill.

- [ ] **Step 1: Escrever a migração**

```python
"""caixa multi-cliente: caixas.cliente_principal + backfill"""
import sqlalchemy as sa
from alembic import op

revision = "0021_caixa_cliente_principal"
down_revision = "0020_propostas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("caixas", sa.Column("cliente_principal", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_caixas_cliente_principal", "caixas", "clientes",
                          ["cliente_principal"], ["id"])
    # Backfill: cliente_principal = o cliente das OS da caixa (hoje single-client).
    # Usa o menor id de OS da caixa como representante (determinístico).
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE caixas SET cliente_principal = sub.cliente
        FROM (
            SELECT o.caixa AS caixa_id, o.cliente AS cliente
            FROM ordens o
            JOIN (SELECT caixa, MIN(id) AS min_id FROM ordens WHERE caixa IS NOT NULL GROUP BY caixa) m
              ON o.caixa = m.caixa AND o.id = m.min_id
        ) sub
        WHERE caixas.id = sub.caixa_id
    """))


def downgrade() -> None:
    op.drop_constraint("fk_caixas_cliente_principal", "caixas", type_="foreignkey")
    op.drop_column("caixas", "cliente_principal")
```

- [ ] **Step 2: Rodar baseline** — `cd backend && source .venv/bin/activate && pytest -q` (a suíte constrói tabelas pelos modelos; a migração não roda nos testes — este passo só confirma que nada quebrou; espera 718 passed / 4 pré-existentes).
- [ ] **Step 3: Commit** — `git add backend/alembic/versions/0021_caixa_cliente_principal.py && git commit -m "feat(caixa): migracao cliente_principal na caixa"`

---

## Task 2: Model — `Caixa.cliente_principal`

**Files:** Modify `backend/app/models/caixa.py`. Test `backend/tests/test_caixa_multicliente.py` (novo).

**Interfaces:** Produces `Caixa.cliente_principal` (int|None), `Caixa.cliente_principal_rel` (Cliente), `Caixa.cliente_principal_nome` (str|None).

- [ ] **Step 1: Teste (RED)**

```python
# backend/tests/test_caixa_multicliente.py
def test_caixa_cliente_principal(db_session):
    from app.models import Cliente, Caixa
    cli = Cliente(nome="ACME"); db_session.add(cli); db_session.flush()
    cx = Caixa(fase=4, cliente_principal=cli.id); db_session.add(cx); db_session.flush()
    db_session.refresh(cx)
    assert cx.cliente_principal == cli.id
    assert cx.cliente_principal_nome == "ACME"
```

- [ ] **Step 2: Rodar e ver falhar** — `pytest tests/test_caixa_multicliente.py -k cliente_principal -v` → FAIL.
- [ ] **Step 3: Implementar** — em `backend/app/models/caixa.py`:
  - No import: `from sqlalchemy import Column, Integer, String, Date, ForeignKey`.
  - Após a coluna `fase`: `cliente_principal = Column(Integer, ForeignKey("clientes.id"), nullable=True)`.
  - Após `fase_rel`: `cliente_principal_rel = relationship("Cliente", lazy="joined", foreign_keys=[cliente_principal])`.
  - Nova property:
    ```python
    @property
    def cliente_principal_nome(self):
        return self.cliente_principal_rel.nome if self.cliente_principal_rel else None
    ```
- [ ] **Step 4: Rodar e ver passar** — `pytest tests/test_caixa_multicliente.py -k cliente_principal -v` → PASS.
- [ ] **Step 5: Commit** — `git add backend/app/models/caixa.py backend/tests/test_caixa_multicliente.py && git commit -m "feat(caixa): cliente_principal no model da caixa"`

---

## Task 3: Remover a invariante de cliente único

**Files:** Modify `backend/app/api/caixas.py:33-43,142`, `backend/app/api/ordens.py:155-157`. Test `backend/tests/test_caixa_multicliente.py`.

**Interfaces:** Produces `vincular_ordem` e `abrir` aceitam OS de cliente diferente na mesma caixa (sem 409).

- [ ] **Step 1: Teste (RED)** — vincular OS de outro cliente na caixa agora **passa**.

```python
def test_vincular_os_de_outro_cliente_agora_permite(client_exp, caixa_com_os_cliente_a, os_cliente_b):
    r = client_exp.post(f"/caixas/{caixa_com_os_cliente_a}/ordens", json={"ordem_id": os_cliente_b})
    assert r.status_code == 200  # antes era 409
```

> Reusar as fixtures `caixa_com_os_cliente_a`/`os_cliente_b`/`client_exp` já existentes no conftest (criadas na feature da caixa).

- [ ] **Step 2: Rodar e ver falhar** — `pytest tests/test_caixa_multicliente.py -k outro_cliente -v` → FAIL (409 ainda).
- [ ] **Step 3: Implementar**
  - `backend/app/api/caixas.py`: remover a linha `_exige_mesmo_cliente(cx, ordem.cliente)` (linha 142); trocar o comentário da linha seguinte para `ordem.caixa = cx.id  # vincula/move (multi-cliente permitido; principal define as integracoes)`. Remover as funções `_cliente_da_caixa` (33-37) e `_exige_mesmo_cliente` (40-43) — ficam órfãs (grep confirma nenhum outro uso).
  - `backend/app/api/ordens.py`: remover o bloco que rejeita cliente diferente no `abrir` (linhas 155-157):
    ```python
    outra = db.query(Ordem).filter(Ordem.caixa == cx.id).first()
    if outra is not None and outra.cliente != ec.cliente:
        raise HTTPException(status_code=409, detail="caixa é de outro cliente")
    ```
    (remover as 3 linhas; a caixa 404 acima permanece.)
  - Ajustar/remover o teste antigo que exigia o 409 (procure `test_vincular_ordem_de_outro_cliente_falha` / `abrir_os_com_caixa_de_outro_cliente_falha` em `tests/` e remova/inverta — agora o comportamento é permitir).
- [ ] **Step 4: Rodar e ver passar** — `pytest tests/test_caixa_multicliente.py -v && pytest -q` → PASS (corrigir os testes antigos que esperavam 409).
- [ ] **Step 5: Commit** — `git add backend/app/api/caixas.py backend/app/api/ordens.py backend/tests/ && git commit -m "feat(caixa): remove invariante de cliente unico na caixa"`

---

## Task 4: Regra do cliente principal no avanço Recebido→Lab

**Files:** Modify `backend/app/schemas/caixa_acoes.py`, `backend/app/api/caixas.py` (`avancar_caixa`). Test `backend/tests/test_caixa_multicliente.py`.

**Interfaces:** Consumes `wf.FASE_RECEBIDO`. Produces `CaixaAvancarIn.cliente_principal: int | None`; o `avancar_caixa` em Recebido(4) auto-define o principal (1 cliente) ou exige/valida (2+).

- [ ] **Step 1: Testes (RED)**

```python
def test_avancar_recebido_um_cliente_auto_define_principal(client_exp, caixa_recebido_um_cliente):
    r = client_exp.post(f"/caixas/{caixa_recebido_um_cliente}/avancar", json={})
    assert r.status_code == 200
    assert r.json()["cliente_principal"] is not None

def test_avancar_recebido_multi_sem_principal_bloqueia(client_exp, caixa_recebido_dois_clientes):
    r = client_exp.post(f"/caixas/{caixa_recebido_dois_clientes}/avancar", json={})
    assert r.status_code == 409
    assert "principal" in r.json()["detail"].lower()

def test_avancar_recebido_multi_com_principal_valido(client_exp, caixa_recebido_dois_clientes, cliente_a_id):
    r = client_exp.post(f"/caixas/{caixa_recebido_dois_clientes}/avancar", json={"cliente_principal": cliente_a_id})
    assert r.status_code == 200
    assert r.json()["cliente_principal"] == cliente_a_id

def test_avancar_recebido_principal_fora_da_caixa_falha(client_exp, caixa_recebido_dois_clientes, cliente_externo_id):
    r = client_exp.post(f"/caixas/{caixa_recebido_dois_clientes}/avancar", json={"cliente_principal": cliente_externo_id})
    assert r.status_code == 409
```

> Fixtures novas no conftest: `caixa_recebido_um_cliente` (fase 4, 1 OS), `caixa_recebido_dois_clientes` (fase 4, 2 OS de clientes distintos, `cliente_a_id`/segundo), `cliente_externo_id` (cliente sem OS na caixa). Reusar `client_exp` e o wiring de `fases_seed` (fase 4 → Expedição) já existentes. `CaixaDetalhe` precisa expor `cliente_principal` (Task 6) — se rodar T4 antes da T6, asserte via `GET /caixas/{id}` após a Task 6, ou adicione `cliente_principal` ao schema já nesta task. **Recomendo fazer a Task 6 (schema) antes desta na execução**, ou incluir o campo no schema aqui.

- [ ] **Step 2: Rodar e ver falhar** — `pytest tests/test_caixa_multicliente.py -k recebido -v` → FAIL.
- [ ] **Step 3: Implementar** — em `backend/app/schemas/caixa_acoes.py`, adicionar ao `CaixaAvancarIn`:
  ```python
  cliente_principal: int | None = None   # usado so no avanco Recebido(4)->Lab(5)
  ```
  Em `backend/app/api/caixas.py` `avancar_caixa`, logo após `ativas = _ordens_ativas(cx)` e o gate `pode_avancar_caixa` (após a linha 188), adicionar:
  ```python
  if origem == wf.FASE_RECEBIDO:
      clientes_distintos = {o.cliente for o in ativas}
      if dados.cliente_principal is not None:
          if dados.cliente_principal not in clientes_distintos:
              raise HTTPException(status_code=409, detail="cliente principal deve ser um cliente da caixa")
          cx.cliente_principal = dados.cliente_principal
      if cx.cliente_principal is None:
          if len(clientes_distintos) == 1:
              cx.cliente_principal = next(iter(clientes_distintos))
          elif len(clientes_distintos) > 1:
              raise HTTPException(status_code=409, detail="defina o cliente principal antes de avancar")
  ```
  (`wf.FASE_RECEBIDO` já disponível via `from app.core import os_workflow as wf`.)
- [ ] **Step 4: Rodar e ver passar** — `pytest tests/test_caixa_multicliente.py -k recebido -v && pytest -q` → PASS.
- [ ] **Step 5: Commit** — `git add backend/app/schemas/caixa_acoes.py backend/app/api/caixas.py backend/tests/ && git commit -m "feat(caixa): define cliente principal ao sair do recebido"`

---

## Task 5: Espelhamento foca no cliente principal (com fallback)

**Files:** Modify `backend/app/api/espelhamento.py`, `backend/app/api/growthhs_cards.py`. Test `backend/tests/test_caixa_multicliente.py`.

**Interfaces:** Produces helper `cliente_do_card(caixa) -> Cliente | None` (principal, senão 1ª OS). GrowthHS usa o principal; TaskHS ordena as OS principal-primeiro (a lógica existente "primeiro cliente nomeado" passa a pegar o principal).

- [ ] **Step 1: Teste (RED)** — o card do GrowthHS usa o cliente principal, não o 1º OS.

```python
def test_card_caixa_usa_cliente_principal(monkeypatch, db_session, caixa_multi_com_principal_b):
    # caixa com OS do cliente A (1a) e B, cliente_principal = B
    import app.api.growthhs_cards as gc
    enviados = []
    monkeypatch.setattr(gc.hsgrowth_client, "integracao_ativa", lambda: True)
    monkeypatch.setattr(gc.hsgrowth_client, "enviar_card", lambda card: enviados.append(card))
    from fastapi import BackgroundTasks
    bt = BackgroundTasks()
    gc.agendar_card_caixa(db_session, bt, caixa_multi_com_principal_b)
    for t in bt.tasks: t.func(*t.args, **t.kwargs)
    assert enviados and enviados[0]["client"]["name"] == "CLIENTE B"
```

> Fixture `caixa_multi_com_principal_b`: caixa liberada do lab com 2 OS (cliente A criado primeiro, cliente B), `cliente_principal` = B, cada OS com `equipamento_rel`. (Espelhar as fixtures de card já usadas em `test_growthhs_caixa`/`test_caixa_avancar`.)

- [ ] **Step 2: Rodar e ver falhar** — `pytest tests/test_caixa_multicliente.py -k usa_cliente_principal -v` → FAIL (usa A, o 1º).
- [ ] **Step 3: Implementar**
  - Em `backend/app/api/growthhs_cards.py`, adicionar helper e trocar a linha 97:
    ```python
    def cliente_do_card(caixa):
        """O cliente que as integracoes usam: o principal, com fallback na 1a OS."""
        if caixa.cliente_principal_rel is not None:
            return caixa.cliente_principal_rel
        return caixa.ordens[0].cliente_rel if caixa.ordens else None
    ```
    e no `agendar_card_caixa`: trocar `cliente = ordens[0].cliente_rel` por `cliente = cliente_do_card(caixa)`.
  - Em `backend/app/api/espelhamento.py`, no `_montar_payload_caixa`, após montar a lista `ordens`, ordená-la principal-primeiro (assim o `montar_obs_caixa`/`montar_titulo_caixa` do taskhs, que pegam o "primeiro cliente nomeado", passam a usar o principal):
    ```python
    if caixa.cliente_principal is not None:
        ordens.sort(key=lambda o: 0 if o.cliente == caixa.cliente_principal else 1)
    ```
    (sort estável — mantém a ordem relativa dentro do principal e dos demais.)
- [ ] **Step 4: Rodar e ver passar** — `pytest tests/test_caixa_multicliente.py -k usa_cliente_principal -v && pytest -q` → PASS.
- [ ] **Step 5: Commit** — `git add backend/app/api/growthhs_cards.py backend/app/api/espelhamento.py backend/tests/ && git commit -m "feat(integr): card e taskhs focam no cliente principal da caixa"`

---

## Task 6: Schemas expõem cliente principal + "+N outros"

**Files:** Modify `backend/app/schemas/caixas.py`, `backend/app/api/caixas.py` (`quadro_caixas`, e garantir refresh). Test `backend/tests/test_caixa_multicliente.py`.

**Interfaces:** Produces `CaixaOut.cliente_principal` (int|None) + `CaixaOut.cliente_principal_nome` (str|None) + `CaixaOut.outros_clientes` (int, nº de clientes distintos além do principal); `CaixaQuadroItem.cliente_principal_nome` + `outros_clientes`.

- [ ] **Step 1: Teste (RED)** — `GET /caixas/{id}` e `/caixas/quadro` trazem `cliente_principal_nome` e `outros_clientes`.

```python
def test_detalhe_expoe_principal_e_outros(client_exp, caixa_recebido_dois_clientes, cliente_a_id):
    client_exp.post(f"/caixas/{caixa_recebido_dois_clientes}/avancar", json={"cliente_principal": cliente_a_id})
    body = client_exp.get(f"/caixas/{caixa_recebido_dois_clientes}").json()
    assert body["cliente_principal"] == cliente_a_id
    assert body["cliente_principal_nome"]
    assert body["outros_clientes"] == 1
```

- [ ] **Step 2: Rodar e ver falhar** → FAIL.
- [ ] **Step 3: Implementar**
  - `backend/app/schemas/caixas.py` `CaixaOut`: adicionar
    ```python
    cliente_principal: int | None = None
    cliente_principal_nome: str | None = None
    outros_clientes: int = 0
    ```
    `outros_clientes` não é atributo do model — computar via property no model **ou** via `@computed_field`. Mais simples: adicionar property no model `Caixa`:
    ```python
    @property
    def outros_clientes(self) -> int:
        ativas = {o.cliente for o in self.ordens if o.cliente is not None}
        if self.cliente_principal is not None:
            ativas.discard(self.cliente_principal)
        return len(ativas)
    ```
    (Assim `CaixaOut.model_validate(caixa)` pega `cliente_principal`, `cliente_principal_nome` e `outros_clientes` direto do ORM.)
  - `CaixaQuadroItem`: adicionar `cliente_principal_nome: str | None = None` e `outros_clientes: int = 0`. Manter `cliente_nome` (compat).
  - `backend/app/api/caixas.py` `quadro_caixas`: no loop, montar o item com o principal:
    ```python
    principal_nome = cx.cliente_principal_nome or next((o.cliente_nome for o in ativas), None)
    outros = len({o.cliente for o in ativas if o.cliente != cx.cliente_principal})
    itens.append(CaixaQuadroItem(
        id=cx.id, cliente_nome=principal_nome, cliente_principal_nome=principal_nome,
        total_os=len(ativas), prontos=prontos, pendentes=len(ativas) - prontos,
        outros_clientes=outros))
    ```
- [ ] **Step 4: Rodar e ver passar** → PASS; `pytest -q`.
- [ ] **Step 5: Commit** — `git add backend/app/schemas/caixas.py backend/app/models/caixa.py backend/app/api/caixas.py backend/tests/ && git commit -m "feat(caixa): schemas expoem cliente principal e outros clientes"`

---

## Task 7: Frontend — tipos (api.ts)

**Files:** Modify `frontend/src/app/caixas/api.ts`. Test `frontend/src/app/caixas/api.test.ts`.

**Interfaces:** Produces `CaixaAvancarPayload.cliente_principal?: number | null`; `CaixaListItem/CaixaDetalhe` e `CaixaQuadroItem` ganham `cliente_principal_nome?: string | null` e `outros_clientes?: number`; `OrdemResumoCaixa` já tem `cliente`/`cliente_nome`.

- [ ] **Step 1: Teste (RED)** — `avancar` aceita `cliente_principal`.

```ts
it('avancar envia cliente_principal', async () => {
  const spy = vi.spyOn(api, 'apiJson').mockResolvedValue({} as any)
  await caixasApi.avancar(7, { cliente_principal: 3, obs: null, cod_retorno: null })
  expect(spy).toHaveBeenCalledWith('/caixas/7/avancar', expect.objectContaining({ method: 'POST' }))
  expect(JSON.parse((spy.mock.calls[0][1] as any).body).cliente_principal).toBe(3)
})
```

- [ ] **Step 2: Rodar e ver falhar** — `cd frontend && npx vitest run src/app/caixas/api.test.ts` → FAIL (tipo).
- [ ] **Step 3: Implementar** — em `caixas/api.ts`:
  - `CaixaAvancarPayload`: `export interface CaixaAvancarPayload { obs?: string | null; cod_retorno?: string | null; cliente_principal?: number | null }`.
  - `CaixaListItem` (e por herança `CaixaDetalhe`): adicionar `cliente_principal?: number | null; cliente_principal_nome?: string | null; outros_clientes?: number`.
  - `CaixaQuadroItem`: adicionar `cliente_principal_nome?: string | null; outros_clientes?: number`.
- [ ] **Step 4: Rodar e ver passar** — `npx vitest run src/app/caixas/api.test.ts && npx tsc -b --noEmit`.
- [ ] **Step 5: Commit** — `git add frontend/src/app/caixas/api.ts frontend/src/app/caixas/api.test.ts && git commit -m "feat(ui): tipos de cliente principal na api da caixa"`

---

## Task 8: Frontend — seletor de cliente principal no avanço Recebido

**Files:** Create `frontend/src/app/caixas/ClientePrincipalModal.tsx`. Modify `frontend/src/app/caixas/CaixaDetailPage.tsx`. Test `frontend/src/app/caixas/CaixaDetailPage.test.tsx`.

**Interfaces:** Consumes `caixasApi.avancar`, `CaixaDetalhe.ordens`. Produces: quando `caixa.fase === 4` (Recebido) e há **2+ clientes distintos**, o "Avançar caixa" abre `ClientePrincipalModal` (dropdown dos clientes distintos, obrigatório) → `caixasApi.avancar(id, { cliente_principal, obs:null, cod_retorno:null })`. Com 1 cliente, segue direto (`avancarCaixaDireto`).

- [ ] **Step 1: Teste (RED)** — caixa fase 4 com 2 clientes: clicar avançar mostra o seletor; caixa fase 4 com 1 cliente: avança direto.

```tsx
it('pede cliente principal ao avancar caixa recebido multi-cliente', async () => {
  vi.spyOn(caixasApi, 'obter').mockResolvedValue({
    id: 7, fase: 4, ordens: [
      { id: 1, cliente: 10, cliente_nome: 'A', fase: 4, desfecho_lab: 'pendente' },
      { id: 2, cliente: 20, cliente_nome: 'B', fase: 4, desfecho_lab: 'pendente' }],
  } as any)
  render(<MemoryRouter initialEntries={['/app/caixas/7']}><Routes><Route path="/app/caixas/:id" element={<CaixaDetailPage />} /></Routes></MemoryRouter>)
  const btn = await screen.findByRole('button', { name: /avançar caixa/i })
  fireEvent.click(btn)
  expect(await screen.findByText(/cliente principal/i)).toBeInTheDocument()
})
```

- [ ] **Step 2: Rodar e ver falhar** — `npx vitest run src/app/caixas/CaixaDetailPage.test.tsx` → FAIL.
- [ ] **Step 3: Implementar**
  - `ClientePrincipalModal.tsx` (espelha o estilo do `AvancarCaixaModal`): recebe `clientes: {id:number; nome:string}[]`, `onConfirmar(clienteId:number)`, `onClose`. Um `<select>`/lista obrigatória; botão Confirmar desabilitado até escolher. Título "Cliente principal".
  - `CaixaDetailPage.tsx`: computar `clientesDistintos` das OS ativas da caixa (`caixa.ordens` filtradas por fase ativa → `[{id: o.cliente, nome: o.cliente_nome}]` únicos por id). No `clicarAvancarCaixa` (~linha 143): **se `caixa.fase === 4` e `clientesDistintos.length > 1`** → abrir `ClientePrincipalModal` (novo estado `principalAberto`); no confirmar → `await caixasApi.avancar(caixaId, { cliente_principal, obs:null, cod_retorno:null })` + `carregar()`. Senão, comportamento atual (`pedeCodRetorno` → AvancarCaixaModal; senão `avancarCaixaDireto`).
- [ ] **Step 4: Rodar e ver passar** — `npx vitest run src/app/caixas/CaixaDetailPage.test.tsx && npx tsc -b --noEmit && npx eslint src/app/caixas/`.
- [ ] **Step 5: Commit** — `git add frontend/src/app/caixas/ClientePrincipalModal.tsx frontend/src/app/caixas/CaixaDetailPage.tsx frontend/src/app/caixas/CaixaDetailPage.test.tsx && git commit -m "feat(ux): expedicao escolhe cliente principal ao avancar recebido"`

---

## Task 9: Frontend — exibir principal + "+N outros"

**Files:** Modify `frontend/src/app/ordens/OrdensPage.tsx` (quadro de caixas), `frontend/src/app/caixas/CaixaDetailPage.tsx` (cabeçalho). Test nos respectivos `.test.tsx`.

**Interfaces:** Consumes `CaixaQuadroItem.cliente_principal_nome`/`outros_clientes`; `CaixaDetalhe.cliente_principal_nome`/`outros_clientes`.

- [ ] **Step 1: Teste (RED)** — o card do quadro mostra o nome do principal + "+1 outro" quando `outros_clientes === 1`.

```tsx
it('mostra + N outros no card da caixa multi-cliente', async () => {
  vi.spyOn(caixasApi, 'quadro').mockResolvedValue([
    { fase: 4, descricao: 'Recebido', cor: 'abc', total: 1,
      caixas: [{ id: 7, cliente_nome: 'ACME', cliente_principal_nome: 'ACME', total_os: 3, prontos: 0, pendentes: 3, outros_clientes: 1 }] },
  ] as any)
  render(<MemoryRouter><OrdensPage /></MemoryRouter>)
  expect(await screen.findByText(/\+1 outro/i)).toBeInTheDocument()
})
```

- [ ] **Step 2: Rodar e ver falhar** → FAIL.
- [ ] **Step 3: Implementar**
  - `OrdensPage.tsx` (card da caixa no `Quadro`): usar `cx.cliente_principal_nome ?? cx.cliente_nome` como nome; se `cx.outros_clientes && cx.outros_clientes > 0`, renderizar um selo discreto `+{cx.outros_clientes} outro{cx.outros_clientes > 1 ? 's' : ''}` (`text-xs text-slate-500`).
  - `CaixaDetailPage.tsx` (cabeçalho): idem — mostrar `caixa.cliente_principal_nome` e, se `caixa.outros_clientes > 0`, o selo "+N outros".
- [ ] **Step 4: Rodar e ver passar** — `npx vitest run src/app/ordens/ src/app/caixas/ && npx tsc -b --noEmit && npx eslint src/app/ordens/ src/app/caixas/`.
- [ ] **Step 5: Commit** — `git add frontend/src/app/ordens/OrdensPage.tsx frontend/src/app/caixas/CaixaDetailPage.tsx frontend/src/app/ordens/ frontend/src/app/caixas/ && git commit -m "feat(ux): quadro e detalhe mostram cliente principal e + N outros"`

---

## Task 10: Verificação final + changelog

**Files:** Modify `frontend/src/app/changelog/data.ts`.

- [ ] **Step 1: Changelog** — 1ª entrada do array `CHANGELOG`:
```ts
{
  versao: '1.26.0',
  data: '24/07/2026',
  itens: [
    { tipo: 'novidade', texto: 'Uma caixa agora pode ter aparelhos de mais de um cliente do mesmo grupo. Ao encaminhar do Recebido para o Laboratório, a expedição escolhe o cliente principal (quando há mais de um), que passa a ser usado nas propostas, cards e nota fiscal.' },
  ],
},
```
- [ ] **Step 2: Backend** — `cd backend && source .venv/bin/activate && pytest -q` (só as 4 pré-existentes de upload).
- [ ] **Step 3: Frontend** — `cd frontend && npm run lint && npx tsc -b --noEmit && npm run build`.
- [ ] **Step 4: Commit** — `git add frontend/src/app/changelog/data.ts && git commit -m "docs(changelog): v1.26.0 - caixa multi-cliente com cliente principal"`

---

## Self-Review

- **Cobertura da spec:** coluna+backfill (T1) · model (T2) · remove invariante (T3) · regra do principal no avanço Recebido (T4) · integrações focam no principal c/ fallback (T5) · schemas expõem principal + outros (T6) · frontend tipos/seletor/exibição (T7-T9) · changelog v1.26 (T10). ✅
- **Certificados intactos, trava do lab intacta, "toda OS numa caixa" intacta** — nenhuma task toca nisso. ✅
- **Ordem de execução:** recomendo **T6 (schema) antes da T4** OU incluir `cliente_principal` no `CaixaOut` já na T4, pois os testes da T4 asseram `cliente_principal` na resposta. Anotado na T4.
- **Placeholder scan:** sem TBD/TODO; os testes têm código real; a migração e os trechos de código são literais.
- **Nomes/tipos consistentes:** `cliente_principal` (coluna/campo), `cliente_principal_nome`, `outros_clientes`, `cliente_do_card`, `CaixaAvancarPayload.cliente_principal` — usados igual em backend e frontend.
