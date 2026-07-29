# Caixa: número da proposta + link no card do TaskHS — Plano

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** O GrowthHS manda o número da proposta no `ganho`; o GestorHS guarda na caixa e mostra um link público de download da proposta na seção Pós-Vendas do card do TaskHS (igual ao link de certificado).

**Architecture:** Coluna `caixas.numero_proposta` (migração 0023) + campo no `GanhoIn`; novo `proposta_link.py` (HMAC) + endpoint público que serve o PDF; o espelhamento resolve o link e o `taskhs` o embute na seção Pós-Vendas.

**Tech Stack:** Backend Python · FastAPI · SQLAlchemy 2 · Alembic · pytest.

## Global Constraints
- Domínio PT-BR; commits Conventional Commits sem acentos, uma linha, sem trailer. Escopos: `integracao`, `caixa`, `taskhs`, `docs`, `changelog`.
- **Migração 0023** (down_revision `0022_proposta_faturada`). Versão **v1.30.0**.
- `git add` explícito (nunca `-A`). Testes SQLite in-memory (models criam tabelas; migração é pra prod); **4 falhas upload pré-existentes** alheias — não conserte, não introduza novas.
- Espelhar o padrão existente: `certificado_link.py`/`publico.py` (link+endpoint) e `espelhamento`/`taskhs` (resolução de `..._url`).

---

## Task 1: coluna `caixas.numero_proposta` + migração 0023 + campo no ganho

**Files:** Modify `backend/app/models/caixa.py`, `backend/app/api/integracao_growthhs.py`. Create `backend/alembic/versions/0023_caixa_numero_proposta.py`. Test `backend/tests/test_integracao_growthhs_ganho.py` (estender).

- [ ] **Step 1: Teste (RED)** — estender `test_integracao_growthhs_ganho.py` (usa `settings.GROWTHHS_INBOUND_API_KEY` + header `X-API-Key`):
  - Ganho em caixa Pós-Vendas com `{"observacao": "...", "numero_proposta": 123}` → 200; recarregar a caixa e afirmar `caixa.numero_proposta == 123`.
  - Ganho numa caixa **já avançada** (no-op) com `numero_proposta` → grava o número mesmo assim (movida:false, mas `numero_proposta` atualizado).
  - Sem `numero_proposta` → fica `None` (não quebra).
- [ ] **Step 2: Rodar e ver falhar** — `cd backend && source .venv/bin/activate && pytest tests/test_integracao_growthhs_ganho.py -v`.
- [ ] **Step 3: Implementar**
  - `models/caixa.py`: `numero_proposta = Column(Integer, nullable=True)` (perto de `cliente_principal`; `Integer` já importado).
  - `alembic/versions/0023_caixa_numero_proposta.py` (espelhar 0022):
    ```python
    """caixa: coluna numero_proposta (numero da proposta vinda do GrowthHS)"""
    import sqlalchemy as sa
    from alembic import op

    revision = "0023_caixa_numero_proposta"
    down_revision = "0022_proposta_faturada"
    branch_labels = None
    depends_on = None

    def upgrade() -> None:
        op.add_column("caixas", sa.Column("numero_proposta", sa.Integer(), nullable=True))

    def downgrade() -> None:
        op.drop_column("caixas", "numero_proposta")
    ```
  - `api/integracao_growthhs.py`: em `GanhoIn` add `numero_proposta: int | None = None`. No `ganho`, gravar o número quando presente, tanto no no-op quanto no avanço:
    - No bloco no-op (fase já avançada), antes do `return GanhoOut(movida=False...)`: `if dados.numero_proposta is not None: cx.numero_proposta = dados.numero_proposta; db.commit()`.
    - No caminho de avanço (fase 6), antes de `executar_avanco_caixa`: `if dados.numero_proposta is not None: cx.numero_proposta = dados.numero_proposta` (o commit já acontece dentro do `executar_avanco_caixa`).
    - (O 409/404 continua sem gravar.)
- [ ] **Step 4: Rodar e ver passar** — `pytest tests/test_integracao_growthhs_ganho.py -v && pytest -q` (só as 4 de upload).
- [ ] **Step 5: Commit** — `git add backend/app/models/caixa.py backend/alembic/versions/0023_caixa_numero_proposta.py backend/app/api/integracao_growthhs.py backend/tests/test_integracao_growthhs_ganho.py && git commit -m "feat(integracao): guarda numero da proposta na caixa via ganho + migracao 0023"`

---

## Task 2: link público da proposta (`proposta_link.py` + endpoint em `publico.py`)

**Files:** Create `backend/app/core/proposta_link.py`. Modify `backend/app/api/publico.py`. Test `backend/tests/test_publico_proposta.py`.

**Interfaces produzidas (Task 3):** `proposta_link.link_proposta(proposta_id) -> str | None`, `proposta_link.assinar/verificar`.

- [ ] **Step 1: Teste (RED)** — `backend/tests/test_publico_proposta.py`:
  - `link_proposta(id)` com `CERT_PUBLIC_BASE_URL` setado → URL contém `/publico/proposta/{id}?t=`; base vazia → None.
  - `GET /publico/proposta/{id}?t=<token valido>` → 200, `content-type application/pdf` (mockar/gerar `proposta_pdf.gerar_pdf` — se pesado, mockar via monkeypatch para devolver `b"%PDF..."`). Token inválido → 403. Proposta inexistente (`gerar_pdf` levanta `ValueError`) → 404.
  - (Ver `test_publico_certificado*.py` / `test_certificado_link.py` para o idioma de setar `CERT_PUBLIC_BASE_URL` e mockar a geração de PDF.)
- [ ] **Step 2: Rodar e ver falhar.**
- [ ] **Step 3: Implementar**
  - `core/proposta_link.py` (espelha `certificado_link.py`):
    ```python
    """Link publico assinado para download do PDF da proposta (sem login)."""
    from app.core import assinatura
    from app.core.config import settings

    def _mensagem(proposta_id: int) -> str:
        return f"proposta:{proposta_id}"

    def assinar(proposta_id: int) -> str:
        return assinatura.assinar(_mensagem(proposta_id))

    def verificar(proposta_id: int, token: str | None) -> bool:
        return assinatura.verificar(_mensagem(proposta_id), token)

    def link_proposta(proposta_id: int) -> str | None:
        base = settings.CERT_PUBLIC_BASE_URL
        if not base:
            return None
        return f"{base.rstrip('/')}/publico/proposta/{proposta_id}?t={assinar(proposta_id)}"
    ```
  - `api/publico.py` — add o endpoint (importar `proposta_link` e `proposta_pdf`; seguir o padrão do `baixar_certificado_publico`):
    ```python
    @router.get("/proposta/{proposta_id}")
    def baixar_proposta_publica(proposta_id: int, t: str = "", db: Session = Depends(get_db)):
        if not proposta_link.verificar(proposta_id, t):
            raise HTTPException(status_code=403, detail="link invalido")
        try:
            conteudo = proposta_pdf.gerar_pdf(db, proposta_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="proposta nao encontrada")
        return Response(content=conteudo, media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="proposta-{proposta_id}.pdf"'})
    ```
    (Confirme os imports reais: `Response`, `get_db`, e de onde vem `proposta_pdf.gerar_pdf`.)
- [ ] **Step 4: Rodar e ver passar** — `pytest tests/test_publico_proposta.py -v && pytest -q`.
- [ ] **Step 5: Commit** — `git add backend/app/core/proposta_link.py backend/app/api/publico.py backend/tests/test_publico_proposta.py && git commit -m "feat(propostas): link publico de download da proposta por token"`

---

## Task 3: link da proposta na seção Pós-Vendas do card do TaskHS

**Files:** Modify `backend/app/core/taskhs.py`, `backend/app/api/espelhamento.py`. Test `backend/tests/test_taskhs*.py` (estender) ou novo `test_taskhs_proposta_link.py`.

**Interfaces consumidas:** `proposta_link.link_proposta` (T2), `caixa.numero_proposta` (T1).

- [ ] **Step 1: Teste (RED)** — testar a montagem da obs do card (nível puro, sem I/O): montar uma caixa com `numero_proposta=123` + uma proposta com `numero=123`, e afirmar que a seção Pós-Vendas (`_sec_posvendas` / `montar_obs_caixa`) contém `Proposta #123` e uma URL `/publico/proposta/`. E que sem `numero_proposta` a linha não aparece. (Ver os testes de `taskhs`/`montar_obs_caixa` existentes para o padrão; `_sec_posvendas` é pura.)
- [ ] **Step 2: Rodar e ver falhar.**
- [ ] **Step 3: Implementar**
  - `taskhs.py` — `_sec_posvendas` passa a aceitar `numero_proposta`/`proposta_url` e, quando há `numero_proposta`, acrescenta a linha:
    `Proposta #{numero_proposta}` + (`: {proposta_url}` se `proposta_url`). Manter o resto da seção como está (LER `_sec_posvendas` atual primeiro).
    `montar_obs_caixa(caixa, ordens, *, certificados_por_os, nota_fiscal_url=None, proposta_url=None)` → passar `numero_proposta=caixa.numero_proposta` e `proposta_url` para `_sec_posvendas`.
  - `api/espelhamento.py` — em `_montar_payload_caixa`, resolver `proposta_url` (perto de onde resolve `nf_url`):
    ```python
    from app.core import proposta_link
    from app.models import Proposta
    proposta_url = None
    if caixa.numero_proposta is not None:
        p = db.query(Proposta).filter(Proposta.numero == caixa.numero_proposta, Proposta.is_deleted.is_(False)).first()
        if p is not None:
            proposta_url = proposta_link.link_proposta(p.id)
    obs = taskhs.montar_obs_caixa(caixa, ordens, certificados_por_os=certificados_por_os, nota_fiscal_url=nf_url, proposta_url=proposta_url)
    ```
    (Confirme os imports reais de `Proposta`/`proposta_link`.)
- [ ] **Step 4: Rodar e ver passar** — `pytest tests/ -k "taskhs or espelh or proposta" -v && pytest -q`.
- [ ] **Step 5: Commit** — `git add backend/app/core/taskhs.py backend/app/api/espelhamento.py backend/tests/<arquivo de teste> && git commit -m "feat(taskhs): link da proposta na secao pos-vendas do card"`

---

## Task 4: doc de integração + changelog v1.30.0 + verificação

**Files:** Modify `docs/integracao-growthhs-inbound.md`, `frontend/src/app/changelog/data.ts`.
- [ ] **Step 1: Doc** — atualizar `docs/integracao-growthhs-inbound.md`: o corpo do `ganho` agora aceita `{ "observacao": "...", "numero_proposta": 123 }`; explicar que `numero_proposta` é o **número da proposta do GestorHS** (o `#N` da tela de Propostas), fica guardado na caixa e vira um link de download no card do TaskHS. Atualizar o exemplo `curl`.
- [ ] **Step 2: Changelog** — 1ª entrada de `frontend/src/app/changelog/data.ts`:
  ```ts
  {
    versao: '1.30.0',
    data: '29/07/2026',
    itens: [
      { tipo: 'novidade', texto: 'Ao dar ganho no GrowthHS, o número da proposta é guardado na caixa e vira um link para baixar o PDF da proposta direto no card do TaskHS (na etapa de Pós-Vendas), do mesmo jeito que já acontece com os certificados.' },
    ],
  },
  ```
- [ ] **Step 3: Verificação** — Backend `pytest -q` (só as 4 de upload). Frontend `cd frontend && npx tsc -b --noEmit && npm run build` (só changelog).
- [ ] **Step 4: Commit** — `git add docs/integracao-growthhs-inbound.md frontend/src/app/changelog/data.ts && git commit -m "docs(integracao): numero_proposta no ganho + changelog v1.30.0"`

---

## Self-Review
- **Cobertura:** coluna+migração+campo no ganho (T1) · link público (T2) · link no card Pós-Vendas (T3) · doc+changelog (T4). ✅
- **Espelha padrões:** certificado_link/publico (link) e espelhamento/taskhs (resolução de url).
- **Migração 0023** aplicar em prod após deploy. Número guardado no avanço e no no-op.
