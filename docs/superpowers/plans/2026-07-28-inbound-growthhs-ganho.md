# Integração inbound GrowthHS (ganho → Financeiro) — Plano

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** Expor um endpoint no GestorHS, autenticado por uma API key inbound que não expira, que o GrowthHS chama para mover uma caixa de Pós-Vendas(6) → Financeiro(10), com uma observação; mais um documento de integração.

**Architecture:** Nova config `GROWTHHS_INBOUND_API_KEY` + dependency de auth por `X-API-Key`; refactor extraindo o núcleo de avanço do `avancar_caixa` para reuso; endpoint dedicado que faz o 6→10 idempotente.

**Tech Stack:** Backend Python · FastAPI · SQLAlchemy 2 · pytest.

## Global Constraints
- Domínio PT-BR; commits Conventional Commits sem acentos, uma linha, sem trailer. Escopos: `integracao`, `caixa`, `config`, `docs`, `changelog`.
- **Sem migração** (`aceite`/`data_aceite` já existem; a chave é env). Integração nasce **desligada** (chave vazia). Versão **v1.28.0**.
- `git add` explícito (nunca `-A`). Testes SQLite in-memory; **4 falhas de upload pré-existentes** alheias — não conserte, não introduza novas.
- `wf` = `app.core.os_workflow`. `require_funcao`/`get_current_usuario` em `app.api.deps`.

---

## Task 1: config `GROWTHHS_INBOUND_API_KEY` + dependency de auth inbound

**Files:** Modify `backend/app/core/config.py`, `backend/app/api/deps.py`. Test `backend/tests/test_integracao_growthhs_auth.py`.

**Interfaces produzidas (Task 3):** `require_growthhs_inbound` (FastAPI dependency).

- [ ] **Step 1: Teste (RED)** — `backend/tests/test_integracao_growthhs_auth.py`: montar um app/rota mínima protegida por `require_growthhs_inbound` (ou testar via o endpoint da Task 3 se já existisse — aqui, testar a dependency isolada com um router de teste, OU adiar as asserts para a Task 3). Casos: chave configurada + header certo → 200; header ausente → 401; header errado → 401; `GROWTHHS_INBOUND_API_KEY` vazia → 503. Use `monkeypatch`/override de `settings.GROWTHHS_INBOUND_API_KEY` (ver como o conftest/outros testes ajustam settings).
- [ ] **Step 2: Rodar e ver falhar.**
- [ ] **Step 3: Implementar**
  - `config.py`: adicionar em `Settings`, junto das chaves de integração:
    ```python
    # Integracao INBOUND do GrowthHS (mover caixa Pos-Vendas -> Financeiro).
    # Vazio = desligada. Nao expira; revoga trocando o valor. Header X-API-Key.
    GROWTHHS_INBOUND_API_KEY: str = ""
    ```
  - `deps.py`: adicionar (importar `secrets`, `Header`, `settings`):
    ```python
    import secrets
    from fastapi import Header

    def require_growthhs_inbound(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
        configurada = settings.GROWTHHS_INBOUND_API_KEY
        if not configurada:
            raise HTTPException(status_code=503, detail="integracao inbound do GrowthHS desligada")
        if not x_api_key or not secrets.compare_digest(x_api_key, configurada):
            raise HTTPException(status_code=401, detail="api key invalida")
    ```
    (Confirme como `settings` e `HTTPException` são importados/usados no arquivo; siga o padrão.)
- [ ] **Step 4: Rodar e ver passar** — `pytest tests/test_integracao_growthhs_auth.py -v && pytest -q`.
- [ ] **Step 5: Commit** — `git add backend/app/core/config.py backend/app/api/deps.py backend/tests/test_integracao_growthhs_auth.py && git commit -m "feat(integracao): chave inbound e auth por api-key do growthhs"`

---

## Task 2: extrair `executar_avanco_caixa` (refactor sem mudar comportamento)

**Files:** Modify `backend/app/api/caixas.py`. Test: os testes existentes de avançar caixa devem continuar verdes (`backend/tests/test_caixas*.py`/`test_caixa*.py`).

**Interfaces produzidas (Task 3):** `executar_avanco_caixa(db, cx, *, origem, destino, ativas, usuario, obs, cod_retorno, background_tasks)`.

- [ ] **Step 1: Baseline** — rodar os testes de caixa e anotar que passam ANTES: `cd backend && source .venv/bin/activate && pytest -q -k "caixa"`.
- [ ] **Step 2: Implementar** — extrair as linhas ~216-247 do `avancar_caixa` (o bloco `if origem == 7 ...` + o fan-out `for o in ativas` + `cx.fase = destino; commit; refresh; agendar_espelhamento_caixa; if origem == Lab: agendar_card_caixa; return cx`) para uma função de módulo:
  ```python
  def executar_avanco_caixa(db, cx, *, origem, destino, ativas, usuario, obs, cod_retorno, background_tasks):
      """Aplica o efeito de avancar a caixa de `origem` para `destino` (fan-out por OS,
      log, espelhamento). Guards de entrada (funcao, pode_avancar, principal) ficam no chamador."""
      if origem == 7 and not (cod_retorno and cod_retorno.strip()):
          raise HTTPException(status_code=422, detail="cod_retorno é obrigatório para finalizar")
      for o in ativas:
          if origem == wf.FASE_LABORATORIO:
              if o.desfecho_lab == wf.DESFECHO_CONCLUIDO:
                  espelhar_calibracao(db, o)
          elif origem == 6:
              o.aceite = True
              o.data_aceite = agora()
          elif origem == 10:
              if not o.nota_fiscal:
                  raise HTTPException(status_code=409, detail="anexe a nota fiscal da caixa antes de confirmar o pagamento")
              o.pago = True
              o.data_pagamento = agora()
          elif origem == 7:
              o.cod_retorno = cod_retorno.strip()
              o.data_retorno = agora()
              o.situacao = "F"
          o.fase = destino
          texto = f"Caixa #{cx.id}: {origem} -> {destino}"
          if obs and obs.strip():
              texto = f"{texto} - {obs.strip()}"
          registrar_log(db, o, usuario, texto)
      cx.fase = destino
      db.commit()
      db.refresh(cx)
      agendar_espelhamento_caixa(db, background_tasks, cx)
      if origem == wf.FASE_LABORATORIO:
          agendar_card_caixa(db, background_tasks, cx)
      return cx
  ```
  E no `avancar_caixa`, substituir esse bloco por:
  ```python
      return executar_avanco_caixa(db, cx, origem=origem, destino=destino, ativas=ativas,
                                   usuario=usuario, obs=dados.obs, cod_retorno=dados.cod_retorno,
                                   background_tasks=background_tasks)
  ```
  Mantenha os guards anteriores (fase None, `exige_funcao_da_fase`, `pode_avancar_caixa`, principal do Recebido) exatamente como estão. **Nada de comportamento muda.**
- [ ] **Step 3: Rodar e ver passar** — `pytest -q -k "caixa"` (mesmo resultado do baseline) e `pytest -q` (só as 4 de upload).
- [ ] **Step 4: Commit** — `git add backend/app/api/caixas.py && git commit -m "refactor(caixa): extrai executar_avanco_caixa para reuso"`

---

## Task 3: endpoint inbound `POST /integracao/growthhs/caixas/{id}/ganho`

**Files:** Create `backend/app/api/integracao_growthhs.py`. Modify `backend/app/main.py` (registrar router). Test `backend/tests/test_integracao_growthhs_ganho.py`.

**Interfaces consumidas:** `require_growthhs_inbound` (T1), `executar_avanco_caixa` + `_ordens_ativas` (caixas.py, T2), `wf` (workflow).

- [ ] **Step 1: Teste (RED)** — `backend/tests/test_integracao_growthhs_ganho.py` (setar `settings.GROWTHHS_INBOUND_API_KEY` via monkeypatch; header `X-API-Key`):
  - Caixa em Pós-Vendas(6) + observação → 200, `movida:true`, `fase:10`; a caixa fica fase 10, as OS `aceite=True`, e existe um LogOS contendo a observação. (Criar a caixa em fase 6 via fixtures — ver `test_caixa*` para o helper de caixa/OS.)
  - Caixa já em Financeiro(10) → 200, `movida:false`, sem erro.
  - Caixa em Laboratório(5) → 409.
  - Caixa inexistente → 404.
  - Sem/`X-API-Key` errado → 401. Chave vazia → 503.
- [ ] **Step 2: Rodar e ver falhar.**
- [ ] **Step 3: Implementar** — `backend/app/api/integracao_growthhs.py`:
  ```python
  from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
  from pydantic import BaseModel
  from sqlalchemy.orm import Session
  from app.models.database import get_db
  from app.models import Caixa
  from app.api.deps import require_growthhs_inbound
  from app.api.caixas import executar_avanco_caixa, _ordens_ativas
  from app.core import os_workflow as wf

  router = APIRouter(prefix="/integracao/growthhs", tags=["integracao-growthhs"])
  FASE_POSVENDAS = 6

  class GanhoIn(BaseModel):
      observacao: str | None = None

  class GanhoOut(BaseModel):
      movida: bool
      caixa_id: int
      fase: int

  @router.post("/caixas/{caixa_id}/ganho", response_model=GanhoOut)
  def ganho(caixa_id: int, dados: GanhoIn, background_tasks: BackgroundTasks,
            db: Session = Depends(get_db), _: None = Depends(require_growthhs_inbound)):
      cx = db.query(Caixa).filter(Caixa.id == caixa_id).first()
      if cx is None:
          raise HTTPException(status_code=404, detail="caixa nao encontrada")
      if cx.fase in (wf.FASE_FINANCEIRO, 7, wf.FASE_FINALIZADA):  # 10/7/8: ja avancou
          return GanhoOut(movida=False, caixa_id=cx.id, fase=cx.fase)
      if cx.fase != FASE_POSVENDAS:
          raise HTTPException(status_code=409, detail="caixa nao esta em Pos-Vendas")
      obs = "via GrowthHS"
      if dados.observacao and dados.observacao.strip():
          obs = f"via GrowthHS: {dados.observacao.strip()}"
      executar_avanco_caixa(db, cx, origem=FASE_POSVENDAS, destino=wf.proxima_fase(FASE_POSVENDAS),
                            ativas=_ordens_ativas(cx), usuario=None, obs=obs, cod_retorno=None,
                            background_tasks=background_tasks)
      return GanhoOut(movida=True, caixa_id=cx.id, fase=cx.fase)
  ```
  (Confirme os imports reais de `get_db`/`Caixa`/`_ordens_ativas`; se `_ordens_ativas` for privado e inconveniente de importar, replique a expressão `[o for o in cx.ordens if wf.eh_ativa(o.fase)]`.)
  - `main.py`: `from app.api import integracao_growthhs` e `app.include_router(integracao_growthhs.router)` (seguir o padrão dos outros `include_router`).
- [ ] **Step 4: Rodar e ver passar** — `pytest tests/test_integracao_growthhs_ganho.py -v && pytest -q`.
- [ ] **Step 5: Commit** — `git add backend/app/api/integracao_growthhs.py backend/app/main.py backend/tests/test_integracao_growthhs_ganho.py && git commit -m "feat(integracao): endpoint growthhs move caixa de pos-vendas para financeiro"`

---

## Task 4: documento de integração + changelog v1.28.0 + verificação

**Files:** Create `docs/integracao-growthhs-inbound.md`. Modify `frontend/src/app/changelog/data.ts`.

- [ ] **Step 1: Doc** — `docs/integracao-growthhs-inbound.md`, em PT-BR, cobrindo (para a equipe do GrowthHS):
  - **Objetivo:** dar "ganho" no GrowthHS move a caixa de Pós-Vendas → Financeiro no GestorHS.
  - **Ligar a integração:** no GestorHS, definir a env `GROWTHHS_INBOUND_API_KEY` (segredo forte). Vazio = desligada.
  - **Endpoint:** `POST {BASE_URL_GESTORHS}/integracao/growthhs/caixas/{caixa_id}/ganho`.
  - **Autenticação:** header `X-API-Key: <a chave>`.
  - **`caixa_id`:** é o `external_id` que o GestorHS já mandou no card do GrowthHS (`external_id = caixa.id`).
  - **Corpo (JSON):** `{ "observacao": "Negócio fechado — Proposta #123, OC 456, R$ ..." }` (opcional; vai pro histórico da caixa).
  - **Respostas:** `200 {movida:true,caixa_id,fase:10}` (moveu) · `200 {movida:false,...}` (já estava em Financeiro/além — repetição é segura) · `409` (caixa não está em Pós-Vendas) · `404` (caixa não existe) · `401` (X-API-Key ausente/errada) · `503` (integração desligada).
  - **Idempotência:** pode repetir a chamada sem duplicar (a repetição em caixa já movida devolve `movida:false`).
  - **Exemplo `curl`** completo.
  - **Segurança:** a chave só faz essa transição; não expira; revogar trocando a env.
- [ ] **Step 2: Changelog** — 1ª entrada de `frontend/src/app/changelog/data.ts`:
  ```ts
  {
    versao: '1.28.0',
    data: '28/07/2026',
    itens: [
      { tipo: 'novidade', texto: 'Integração com o GrowthHS: quando o pós-vendas dá ganho no negócio pelo GrowthHS, a caixa é movida automaticamente de Pós-Vendas para Financeiro no GestorHS, com a observação do negócio registrada no histórico.' },
    ],
  },
  ```
- [ ] **Step 3: Verificação** — Backend `pytest -q` (só as 4 de upload). Frontend `cd frontend && npx tsc -b --noEmit && npm run build` (mudança só no changelog).
- [ ] **Step 4: Commit** — `git add docs/integracao-growthhs-inbound.md frontend/src/app/changelog/data.ts && git commit -m "docs(integracao): guia de integracao inbound growthhs + changelog v1.28.0"`

---

## Self-Review
- **Cobertura da spec:** chave+auth (T1) · refactor núcleo (T2) · endpoint idempotente 6→10 (T3) · doc + changelog (T4). ✅
- **Segurança:** chave só faz 6→10 em caixa de Pós-Vendas; empty=off; compare_digest; toda chamada logada.
- **Sem regressão:** T2 preserva comportamento (testes de caixa verdes); integração nasce desligada.
- **Placeholder scan:** código real; pontos a confirmar (imports de settings/get_db/_ordens_ativas) marcados.
