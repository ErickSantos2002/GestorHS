# Proposta: marcar como Faturada — Plano

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** Financeiro marca uma proposta como Faturada (selo + ação na lista); só o Administrador desfaz. Sem travar edição.

**Architecture:** Coluna `faturada` (+ `faturada_em`/`faturada_por`) na proposta (migração 0022); 2 endpoints gateados (`faturar`=Fin+Admin, `desfaturar`=Admin); selo + ação em ícone na PropostasPage.

**Tech Stack:** Backend Python · FastAPI · SQLAlchemy 2 · Alembic · pytest. Frontend React · TS · Vitest.

## Global Constraints
- Domínio PT-BR; commits Conventional Commits sem acentos, uma linha, sem trailer. Escopos: `propostas`, `acesso`, `ui`, `changelog`.
- **Migração 0022** (down_revision `0021_caixa_cliente_principal`). Versão **v1.29.0**. Espelhar auth nos dois lados (regra do CLAUDE.md).
- `git add` explícito (nunca `-A`). Testes SQLite in-memory criam tabelas dos models (a migração é só pra prod); **4 falhas upload pré-existentes** alheias — não conserte, não introduza novas. Falha unit frontend `ClienteEquipamentosTab` pré-existente — ignore.

---

## Task 1: backend — coluna + migração 0022 + schema + endpoints faturar/desfaturar

**Files:** Modify `backend/app/models/proposta.py`, `backend/app/schemas/proposta.py`, `backend/app/api/propostas.py`. Create `backend/alembic/versions/0022_proposta_faturada.py`. Test `backend/tests/test_propostas_faturar.py`.

- [ ] **Step 1: Teste (RED)** — `backend/tests/test_propostas_faturar.py` (reusar fixtures: criar proposta + clients autenticados por função — ver `test_propostas.py`/conftest para o padrão de usuário por função):
  - Financeiro `POST /propostas/{id}/faturar` → 200, resposta `faturada=True`, `faturada_por` = nome do usuário; no banco a proposta está faturada.
  - Comercial (Comercial Pós-Vendas) faturar → 403 (só Financeiro/Admin).
  - Admin `POST /propostas/{id}/desfaturar` (proposta faturada) → 200, `faturada=False`, `faturada_em`/`faturada_por` limpos.
  - Financeiro desfaturar → 403 (só Admin).
  - Idempotência: faturar 2x → segue `faturada=True`; desfaturar proposta não-faturada → 200 no-op.
  - `GET`/listar retorna `faturada` no `PropostaOut`.
- [ ] **Step 2: Rodar e ver falhar** — `cd backend && source .venv/bin/activate && pytest tests/test_propostas_faturar.py -v`.
- [ ] **Step 3: Implementar**
  - `models/proposta.py` — adicionar (perto de `assinatura`/antes de `deleted_at`):
    ```python
    faturada = Column(Boolean, nullable=False, default=False, server_default=sa.text("false"))
    faturada_em = Column(DateTime(timezone=True), nullable=True)
    faturada_por = Column(String(255), nullable=True)
    ```
    (Confirme os imports: `Boolean`, `DateTime`, `String` já usados; `sa`/`text` — se `server_default=sa.text("false")` exigir import, use o que o arquivo já tem, ou `default=False` + o `server_default` na migração apenas.)
  - `alembic/versions/0022_proposta_faturada.py` (espelhar o padrão do `0021`):
    ```python
    """proposta: coluna faturada (+ faturada_em/por)"""
    import sqlalchemy as sa
    from alembic import op

    revision = "0022_proposta_faturada"
    down_revision = "0021_caixa_cliente_principal"
    branch_labels = None
    depends_on = None

    def upgrade() -> None:
        op.add_column("propostas", sa.Column("faturada", sa.Boolean(), nullable=False, server_default=sa.text("false")))
        op.add_column("propostas", sa.Column("faturada_em", sa.DateTime(timezone=True), nullable=True))
        op.add_column("propostas", sa.Column("faturada_por", sa.String(length=255), nullable=True))

    def downgrade() -> None:
        op.drop_column("propostas", "faturada_por")
        op.drop_column("propostas", "faturada_em")
        op.drop_column("propostas", "faturada")
    ```
  - `schemas/proposta.py` — adicionar em `PropostaOut` (NÃO em PropostaBase/Create): `faturada: bool = False`, `faturada_em: Optional[datetime] = None`, `faturada_por: Optional[str] = None`.
  - `api/propostas.py` — adicionar gates e endpoints (perto do `duplicar`/`atualizar`):
    ```python
    _faturar_gate = require_funcao("Financeiro", "Administrador")
    _desfaturar_gate = require_funcao("Administrador")

    @router.post("/{proposta_id}/faturar", response_model=PropostaOut)
    def faturar(proposta_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(_faturar_gate)):
        p = _proposta_ou_404(db, proposta_id)
        if not p.faturada:
            p.faturada = True
            p.faturada_em = agora()          # confirmar helper de 'agora' usado no modulo/ordens_acoes
            p.faturada_por = usuario.nome
            db.commit(); db.refresh(p)
        return p

    @router.post("/{proposta_id}/desfaturar", response_model=PropostaOut)
    def desfaturar(proposta_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(_desfaturar_gate)):
        p = _proposta_ou_404(db, proposta_id)
        if p.faturada:
            p.faturada = False
            p.faturada_em = None
            p.faturada_por = None
            db.commit(); db.refresh(p)
        return p
    ```
    (Confirme como obter `agora()`/timestamp no módulo — importe do mesmo lugar que outros endpoints; `_proposta_ou_404` já existe.)
- [ ] **Step 4: Rodar e ver passar** — `pytest tests/test_propostas_faturar.py -v && pytest -q` (só as 4 de upload).
- [ ] **Step 5: Commit** — `git add backend/app/models/proposta.py backend/alembic/versions/0022_proposta_faturada.py backend/app/schemas/proposta.py backend/app/api/propostas.py backend/tests/test_propostas_faturar.py && git commit -m "feat(propostas): marcar e desfazer faturada (financeiro/admin) + migracao 0022"`

---

## Task 2: frontend — roles + api + selo/ação na lista

**Files:** Modify `frontend/src/auth/roles.ts`, `frontend/src/app/propostas/api.ts`, `frontend/src/app/propostas/PropostasPage.tsx`. Tests: `roles.test.ts`, `PropostasPage.test.tsx`.

**Interfaces consumidas:** `POST /propostas/{id}/faturar` e `/desfaturar` (T1).

- [ ] **Step 1: Testes (RED)**
  - `roles.test.ts`: `podeFaturarProposta({funcao:'Financeiro'})` → true; `({funcao:'Comercial Pós-Vendas'})` → false; Admin → true. `podeDesfaturarProposta`: Admin → true; Financeiro → false.
  - `PropostasPage.test.tsx`: com uma proposta `faturada:true`, a lista mostra o selo "Faturada"; com um usuário Financeiro e proposta não-faturada, existe a ação "Marcar como Faturada" e clicá-la chama `propostasApi.faturar(id)`; o "Desfazer faturamento" só aparece para Admin (com proposta faturada). (Reusar setup do arquivo.)
- [ ] **Step 2: Rodar e ver falhar** — `cd frontend && npx vitest run src/auth src/app/propostas`.
- [ ] **Step 3: Implementar**
  - `auth/roles.ts`:
    ```ts
    export function podeFaturarProposta(user: User | null): boolean {
      return isAdmin(user) || user?.funcao === FUNCAO_FINANCEIRO
    }
    export function podeDesfaturarProposta(user: User | null): boolean {
      return isAdmin(user)
    }
    ```
  - `app/propostas/api.ts`: no tipo `Proposta`, add `faturada: boolean`, `faturada_em: string | null`, `faturada_por: string | null`. No `propostasApi`: `faturar: (id) => apiJson<Proposta>(\`/propostas/\${id}/faturar\`, { method: 'POST' })` e `desfaturar: (id) => apiJson<Proposta>(\`/propostas/\${id}/desfaturar\`, { method: 'POST' })` (confirmar o helper HTTP usado — `apiJson`/`apiFetch`).
  - `app/propostas/PropostasPage.tsx`:
    - Importar `podeFaturarProposta, podeDesfaturarProposta` e `IconCheck` (e `IconX` se usar), e `Badge`.
    - Selo: quando `p.faturada`, mostrar `<Badge tone="ok">Faturada</Badge>` (numa célula de status ou perto do número/ações — escolha um lugar limpo na tabela).
    - Ação no `IconButtonGroup`: se `!p.faturada && podeFaturarProposta(user)` → `IconButton label="Marcar como Faturada" tone="ok"` `IconCheck` `onClick={() => faturar(p)}`; se `p.faturada && podeDesfaturarProposta(user)` → `IconButton label="Desfazer faturamento" tone="neutro"` (IconX) `onClick={() => desfaturar(p)}`.
    - Handlers `faturar(p)`/`desfaturar(p)` espelham `duplicar` (set busy, chama a api, recarrega a lista, trata erro).
- [ ] **Step 4: Rodar e ver passar** — `npx vitest run src/auth src/app/propostas && npx tsc -b --noEmit && npm run lint`.
- [ ] **Step 5: Commit** — `git add frontend/src/auth/roles.ts frontend/src/app/propostas/api.ts frontend/src/app/propostas/PropostasPage.tsx frontend/src/auth/roles.test.ts frontend/src/app/propostas/PropostasPage.test.tsx && git commit -m "feat(propostas): selo e acao de faturar na lista"`

---

## Task 3: changelog v1.29.0 + verificação

**Files:** Modify `frontend/src/app/changelog/data.ts`.
- [ ] **Step 1: Changelog** — 1ª entrada:
  ```ts
  {
    versao: '1.29.0',
    data: '28/07/2026',
    itens: [
      { tipo: 'novidade', texto: 'O Financeiro agora pode marcar uma proposta como Faturada direto na lista de Propostas. A proposta faturada ganha um selo; desfazer o faturamento é exclusivo do Administrador.' },
    ],
  },
  ```
- [ ] **Step 2: Backend** — `cd backend && source .venv/bin/activate && pytest -q` (só as 4 de upload).
- [ ] **Step 3: Frontend** — `cd frontend && npm run lint && npx tsc -b --noEmit && npm run build`.
- [ ] **Step 4: Commit** — `git add frontend/src/app/changelog/data.ts && git commit -m "docs(changelog): v1.29.0 - marcar proposta como faturada"`

---

## Self-Review
- **Cobertura:** coluna+migração (T1) · endpoints gateados Fin/Admin+Admin (T1) · schema expõe faturada (T1) · roles+api+selo+ação (T2) · changelog (T3). ✅
- **Espelhamento auth:** `faturar` Fin+Admin / `desfaturar` Admin nos dois lados.
- **Sem travar edição** (só o desfazer é restrito). Migração 0022 aplicar em prod após deploy.
