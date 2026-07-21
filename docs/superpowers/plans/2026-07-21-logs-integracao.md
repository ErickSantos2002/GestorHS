# Logs de Integração — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar uma página interna (só Administrador) que registra, lista, filtra e permite reenviar todos os eventos das integrações de saída (TaskHS e GrowthHS) — sucesso, erro e pulado.

**Architecture:** Um helper `registrar_log_integracao(...)` é chamado no choke point dos dois clientes HTTP (`taskhs_client`/`hsgrowth_client`), que são o funil por onde passa todo envio. A linha guarda o payload enviado; o reenviar apenas re-posta esse payload pelo `enviar_card_sync` do cliente correspondente (idempotente). Backend FastAPI + tabela nova `logs_integracao`; frontend React com página nova sob `/app`.

**Tech Stack:** Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · React 19 · TS · Vite · Tailwind v4 · Vitest.

## Global Constraints

- Idioma do domínio é **PT-BR** (modelos, rotas, variáveis, mensagens). Código novo mantém o padrão.
- Commits: Conventional Commits em **português sem acentos (ASCII)**, uma linha, sem corpo, sem trailer de co-autor. Tipos: `feat`, `fix`, `docs`, `refactor`. Escopo comum aqui: `integracao`.
- Backend: um arquivo por modelo em `models/`, schemas em `schemas/`, routers em `api/` (registrar `include_router` em `main.py`), lógica pura em `core/` (sem I/O). Testes espelham o alvo (`test_<modulo>.py`), SQLite in-memory.
- Frontend: regra de função espelhada nos dois lados (backend `require_funcao` ↔ `src/auth/roles.ts`). Verificação antes de commitar frontend: `npm run lint && npx tsc -b --noEmit && npm run build`.
- Acesso da feature: **só `Administrador`** (ver e reenviar). Backend gateia com `require_funcao("Administrador")`; frontend usa `isAdmin`.
- Retenção: guardar tudo, **sem expurgo** no v1.
- Rodar testes backend: `cd backend && source .venv/bin/activate && pytest -q`.

**Fontes/tipos (mapa fixo usado em várias tasks):**
- `source` do payload → `integracao`/`tipo`:
  - taskhs (SOURCE `"gestorhs"`) → `tipo="os_espelho"`
  - growthhs `"gestorhs.os"` → `tipo="os_card"`
  - growthhs `"gestorhs.atrasados"` → `tipo="atrasados"`
  - growthhs `"gestorhs.calibracao"` → `tipo="vencendo"`
  - qualquer outro → `tipo="desconhecido"`

---

## File Structure

**Backend (cria):**
- `backend/app/models/log_integracao.py` — modelo `LogIntegracao` (tabela `logs_integracao`)
- `backend/alembic/versions/0018_log_integracao.py` — migração
- `backend/app/core/log_integracao.py` — puro: `classificar_tipo`, `referencia_os_do_payload`
- `backend/app/integrations/log_integracao.py` — writer `registrar_log_integracao` (I/O, sessão injetável)
- `backend/app/schemas/logs_integracao.py` — `LogIntegracaoOut`, `EstadoIntegracoes`, `LogsPage`, `ReenvioOut`
- `backend/app/api/logs_integracao.py` — router GET/POST
- Testes: `test_log_integracao_classificar.py`, `test_log_integracao_writer.py`, `test_taskhs_client_log.py`, `test_hsgrowth_client_log.py`, `test_growthhs_cards_log.py`, `test_logs_integracao_api.py`

**Backend (modifica):**
- `backend/app/models/__init__.py` — registrar `LogIntegracao`
- `backend/app/integrations/taskhs_client.py` — `_post` devolve `Response`; logar
- `backend/app/integrations/hsgrowth_client.py` — `_post` devolve `Response`; logar
- `backend/app/api/growthhs_cards.py` — logar pulo `sem_equipamento`
- `backend/app/main.py` — `include_router`

**Frontend (cria):**
- `frontend/src/app/integracao/api.ts` — tipos + cliente
- `frontend/src/app/integracao/LogsIntegracaoPage.tsx` — página
- `frontend/src/app/integracao/LogsIntegracaoPage.test.tsx` — testes

**Frontend (modifica):**
- `frontend/src/app/routes.tsx` — rota
- `frontend/src/layout/Sidebar.tsx` — item de menu `adminOnly`
- `frontend/src/auth/roles.ts` — comentário/uso de `isAdmin` (sem novo helper — acesso é exatamente Admin)

---

### Task 1: Modelo + migração `logs_integracao`

**Files:**
- Create: `backend/app/models/log_integracao.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/0018_log_integracao.py`
- Test: `backend/tests/test_log_integracao_writer.py` (só o teste de modelo aqui; writer vem na Task 3)

**Interfaces:**
- Produces: `LogIntegracao` (tabela `logs_integracao`) com colunas `id, criado_em, integracao, tipo, external_id, referencia_os, status, motivo, http_status, resposta, payload`.

- [ ] **Step 1: Escrever o teste que falha (modelo insere linha)**

```python
# backend/tests/test_log_integracao_writer.py
from app.models import LogIntegracao


def test_modelo_insere_linha(db_session):
    row = LogIntegracao(
        integracao="growthhs", tipo="os_card", external_id="10853",
        referencia_os=10853, status="sucesso", http_status=200,
        resposta="ok", payload={"source": "gestorhs.os", "external_id": "10853"},
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    assert row.id is not None
    assert row.criado_em is not None
    assert row.payload["external_id"] == "10853"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_log_integracao_writer.py::test_modelo_insere_linha -q`
Expected: FAIL com `ImportError: cannot import name 'LogIntegracao'`.

- [ ] **Step 3: Criar o modelo**

```python
# backend/app/models/log_integracao.py
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, func

from app.models.database import Base


class LogIntegracao(Base):
    """Um evento de integracao de saida (TaskHS/GrowthHS): sucesso, erro ou pulado.

    Guarda o payload enviado para permitir o reenvio (re-post do mesmo payload).
    Escrito best-effort pelo writer em app/integrations/log_integracao.py.
    """
    __tablename__ = "logs_integracao"

    id = Column(Integer, primary_key=True, index=True)
    criado_em = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    integracao = Column(String(20), nullable=False)      # taskhs | growthhs
    tipo = Column(String(30), nullable=False)            # os_card | os_espelho | vencendo | atrasados | desconhecido
    external_id = Column(String(100), nullable=True)
    referencia_os = Column(Integer, nullable=True, index=True)
    status = Column(String(20), nullable=False)          # sucesso | erro | pulado
    motivo = Column(String(50), nullable=True)           # desligado | sem_equipamento | ...
    http_status = Column(Integer, nullable=True)
    resposta = Column(Text, nullable=True)               # corpo/erro truncado
    payload = Column(JSON, nullable=True)                # payload enviado (base do reenvio)
```

- [ ] **Step 4: Registrar no `models/__init__.py`**

Adicionar o import (junto aos demais) e a entrada em `__all__`:

```python
from app.models.log_integracao import LogIntegracao
```
E no `__all__`, acrescentar `"LogIntegracao",` ao final da lista.

- [ ] **Step 5: Rodar e ver passar**

Run: `pytest tests/test_log_integracao_writer.py::test_modelo_insere_linha -q`
Expected: PASS.

- [ ] **Step 6: Criar a migração Alembic `0018`**

```python
# backend/alembic/versions/0018_log_integracao.py
"""logs de integracao: eventos de saida (taskhs/growthhs)"""
import sqlalchemy as sa
from alembic import op

revision = "0018_log_integracao"
down_revision = "0017_certificado_venda"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "logs_integracao",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("integracao", sa.String(length=20), nullable=False),
        sa.Column("tipo", sa.String(length=30), nullable=False),
        sa.Column("external_id", sa.String(length=100), nullable=True),
        sa.Column("referencia_os", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("motivo", sa.String(length=50), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("resposta", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_logs_integracao_id"), "logs_integracao", ["id"])
    op.create_index(op.f("ix_logs_integracao_criado_em"), "logs_integracao", ["criado_em"])
    op.create_index(op.f("ix_logs_integracao_referencia_os"), "logs_integracao", ["referencia_os"])


def downgrade() -> None:
    op.drop_index(op.f("ix_logs_integracao_referencia_os"), table_name="logs_integracao")
    op.drop_index(op.f("ix_logs_integracao_criado_em"), table_name="logs_integracao")
    op.drop_index(op.f("ix_logs_integracao_id"), table_name="logs_integracao")
    op.drop_table("logs_integracao")
```

- [ ] **Step 7: Commit**

```bash
cd backend && git add app/models/log_integracao.py app/models/__init__.py alembic/versions/0018_log_integracao.py tests/test_log_integracao_writer.py
git commit -m "feat(integracao): modelo e migracao de logs de integracao"
```

---

### Task 2: Classificador puro (`core/log_integracao.py`)

**Files:**
- Create: `backend/app/core/log_integracao.py`
- Test: `backend/tests/test_log_integracao_classificar.py`

**Interfaces:**
- Produces:
  - `classificar_tipo(integracao: str, source: str | None) -> str`
  - `referencia_os_do_payload(tipo: str, payload: dict | None) -> int | None`

- [ ] **Step 1: Escrever os testes que falham**

```python
# backend/tests/test_log_integracao_classificar.py
from app.core.log_integracao import classificar_tipo, referencia_os_do_payload


def test_classificar_tipo():
    assert classificar_tipo("taskhs", "gestorhs") == "os_espelho"
    assert classificar_tipo("growthhs", "gestorhs.os") == "os_card"
    assert classificar_tipo("growthhs", "gestorhs.atrasados") == "atrasados"
    assert classificar_tipo("growthhs", "gestorhs.calibracao") == "vencendo"
    assert classificar_tipo("growthhs", None) == "desconhecido"


def test_referencia_os_do_payload():
    assert referencia_os_do_payload("os_card", {"external_id": "10853"}) == 10853
    assert referencia_os_do_payload("os_espelho", {"external_id": "42"}) == 42
    assert referencia_os_do_payload("vencendo", {"external_id": "7794:2027-07-21"}) is None
    assert referencia_os_do_payload("os_card", {"external_id": "abc"}) is None
    assert referencia_os_do_payload("os_card", None) is None
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_log_integracao_classificar.py -q`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.core.log_integracao'`.

- [ ] **Step 3: Implementar o módulo puro**

```python
# backend/app/core/log_integracao.py
"""Classificacao pura dos eventos de integracao (sem I/O)."""

# source do payload -> tipo, por integracao
_TIPOS_GROWTHHS = {
    "gestorhs.os": "os_card",
    "gestorhs.atrasados": "atrasados",
    "gestorhs.calibracao": "vencendo",
}


def classificar_tipo(integracao: str, source: str | None) -> str:
    if integracao == "taskhs":
        return "os_espelho"
    if integracao == "growthhs" and source:
        return _TIPOS_GROWTHHS.get(source, "desconhecido")
    return "desconhecido"


def referencia_os_do_payload(tipo: str, payload: dict | None) -> int | None:
    """Para eventos de OS, a referencia e o proprio external_id (id da OS).
    Vencendo/atrasados nao referenciam OS."""
    if payload is None or tipo not in ("os_card", "os_espelho"):
        return None
    try:
        return int(payload.get("external_id"))
    except (TypeError, ValueError):
        return None
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_log_integracao_classificar.py -q`
Expected: PASS (2 testes).

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/core/log_integracao.py tests/test_log_integracao_classificar.py
git commit -m "feat(integracao): classificador puro de tipo e referencia de OS"
```

---

### Task 3: Writer `registrar_log_integracao` (sessão injetável, best-effort)

**Files:**
- Create: `backend/app/integrations/log_integracao.py`
- Test: `backend/tests/test_log_integracao_writer.py` (adiciona ao arquivo da Task 1)

**Interfaces:**
- Consumes: `classificar_tipo`, `referencia_os_do_payload` (Task 2); `LogIntegracao` (Task 1).
- Produces:
  ```python
  registrar_log_integracao(
      *, integracao: str, status: str, payload: dict | None = None,
      motivo: str | None = None, http_status: int | None = None,
      resposta: str | None = None, referencia_os: int | None = None,
      db: Session | None = None,
  ) -> None
  ```
  Nunca levanta. Se `db` for `None`, abre `SessionLocal()` próprio e fecha ao final. `resposta` é truncada em 2000 chars.

- [ ] **Step 1: Escrever os testes que falham (adicionar ao arquivo existente)**

```python
# backend/tests/test_log_integracao_writer.py  (acrescentar)
from app.integrations.log_integracao import registrar_log_integracao


def test_writer_grava_linha_com_db_injetado(db_session):
    registrar_log_integracao(
        integracao="growthhs", status="sucesso", http_status=200, resposta="ok",
        payload={"source": "gestorhs.os", "external_id": "10853"}, db=db_session,
    )
    from app.models import LogIntegracao
    row = db_session.query(LogIntegracao).one()
    assert row.integracao == "growthhs"
    assert row.tipo == "os_card"
    assert row.external_id == "10853"
    assert row.referencia_os == 10853
    assert row.status == "sucesso"


def test_writer_trunca_resposta(db_session):
    registrar_log_integracao(
        integracao="taskhs", status="erro", resposta="x" * 5000,
        payload={"source": "gestorhs", "external_id": "1"}, db=db_session,
    )
    from app.models import LogIntegracao
    row = db_session.query(LogIntegracao).one()
    assert len(row.resposta) == 2000


def test_writer_nunca_levanta(db_session):
    # payload nao-serializavel / status None nao pode propagar excecao
    registrar_log_integracao(integracao="growthhs", status="pulado",
                             motivo="desligado", payload=None, db=db_session)
    from app.models import LogIntegracao
    assert db_session.query(LogIntegracao).count() == 1
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_log_integracao_writer.py -q`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.integrations.log_integracao'`.

- [ ] **Step 3: Implementar o writer**

```python
# backend/app/integrations/log_integracao.py
"""Writer best-effort dos logs de integracao.

Chamado pelo choke point dos clientes (taskhs_client/hsgrowth_client). NUNCA
propaga: logar nao pode quebrar envio nem avanco de OS. Abre sessao propria
(SessionLocal) quando nenhuma e injetada — necessario porque o BackgroundTask
que envia nao tem sessao de request (a da request ja foi fechada)."""
import logging

from app.core.log_integracao import classificar_tipo, referencia_os_do_payload
from app.models.database import SessionLocal
from app.models.log_integracao import LogIntegracao

logger = logging.getLogger(__name__)


def registrar_log_integracao(*, integracao, status, payload=None, motivo=None,
                             http_status=None, resposta=None, referencia_os=None,
                             db=None) -> None:
    own = db is None
    try:
        if own:
            db = SessionLocal()
        source = (payload or {}).get("source")
        tipo = classificar_tipo(integracao, source)
        ref = referencia_os if referencia_os is not None else referencia_os_do_payload(tipo, payload)
        db.add(LogIntegracao(
            integracao=integracao,
            tipo=tipo,
            external_id=(payload or {}).get("external_id"),
            referencia_os=ref,
            status=status,
            motivo=motivo,
            http_status=http_status,
            resposta=(resposta[:2000] if resposta else None),
            payload=payload,
        ))
        db.commit()
    except Exception:
        logger.exception("falha ao registrar log de integracao (best-effort)")
        try:
            if db is not None:
                db.rollback()
        except Exception:
            pass
    finally:
        if own and db is not None:
            db.close()
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_log_integracao_writer.py -q`
Expected: PASS (4 testes — inclui o de modelo da Task 1).

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/integrations/log_integracao.py tests/test_log_integracao_writer.py
git commit -m "feat(integracao): writer best-effort de log com sessao injetavel"
```

---

### Task 4: Instrumentar `taskhs_client`

**Files:**
- Modify: `backend/app/integrations/taskhs_client.py`
- Test: `backend/tests/test_taskhs_client_log.py`

**Interfaces:**
- Consumes: `registrar_log_integracao` (Task 3).
- Produces (contrato novo do módulo):
  - `_post(payload: dict) -> httpx.Response` (levanta só em erro de rede)
  - `enviar_card(payload)` — best-effort; loga `sucesso`/`erro`/`pulado(desligado)`; nunca levanta
  - `enviar_card_sync(payload) -> None` — loga e **levanta** em status >= 400 (uso em scripts)

- [ ] **Step 1: Escrever os testes que falham**

```python
# backend/tests/test_taskhs_client_log.py
import httpx
import pytest

from app.integrations import taskhs_client
from app.core.config import settings


class _Resp:
    def __init__(self, status_code, text="ok"):
        self.status_code = status_code
        self.text = text


def _ativa(monkeypatch):
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "https://task.test")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "k")


def test_enviar_card_loga_sucesso(monkeypatch):
    _ativa(monkeypatch)
    chamadas = []
    monkeypatch.setattr(taskhs_client, "registrar_log_integracao",
                        lambda **kw: chamadas.append(kw))
    monkeypatch.setattr(taskhs_client, "_post", lambda p: _Resp(200))
    taskhs_client.enviar_card({"source": "gestorhs", "external_id": "1"})
    assert chamadas and chamadas[0]["integracao"] == "taskhs"
    assert chamadas[0]["status"] == "sucesso"
    assert chamadas[0]["http_status"] == 200


def test_enviar_card_loga_erro_http(monkeypatch):
    _ativa(monkeypatch)
    chamadas = []
    monkeypatch.setattr(taskhs_client, "registrar_log_integracao",
                        lambda **kw: chamadas.append(kw))
    monkeypatch.setattr(taskhs_client, "_post", lambda p: _Resp(422, "campo X invalido"))
    taskhs_client.enviar_card({"source": "gestorhs", "external_id": "1"})
    assert chamadas[0]["status"] == "erro"
    assert chamadas[0]["http_status"] == 422
    assert "campo X" in chamadas[0]["resposta"]


def test_enviar_card_loga_pulado_desligado(monkeypatch):
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "")
    chamadas = []
    monkeypatch.setattr(taskhs_client, "registrar_log_integracao",
                        lambda **kw: chamadas.append(kw))
    taskhs_client.enviar_card({"source": "gestorhs", "external_id": "1"})
    assert chamadas[0]["status"] == "pulado"
    assert chamadas[0]["motivo"] == "desligado"


def test_enviar_card_sync_levanta_em_erro(monkeypatch):
    _ativa(monkeypatch)
    monkeypatch.setattr(taskhs_client, "registrar_log_integracao", lambda **kw: None)
    monkeypatch.setattr(taskhs_client, "_post", lambda p: _Resp(500, "boom"))
    with pytest.raises(RuntimeError):
        taskhs_client.enviar_card_sync({"source": "gestorhs", "external_id": "1"})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_taskhs_client_log.py -q`
Expected: FAIL (o `enviar_card` atual não loga; `_post` faz `raise_for_status` internamente).

- [ ] **Step 3: Reescrever o cliente**

```python
# backend/app/integrations/taskhs_client.py
"""Cliente HTTP da integracao com o TaskHS (best-effort, gating por env)."""
import logging

import httpx

from app.core.config import settings
from app.integrations.log_integracao import registrar_log_integracao

logger = logging.getLogger(__name__)


def integracao_ativa() -> bool:
    return bool(settings.TASKHS_BASE_URL and settings.TASKHS_API_KEY)


def _post(payload: dict) -> httpx.Response:
    """POST cru; devolve a Response. Levanta so em erro de rede (nao de status)."""
    url = f"{settings.TASKHS_BASE_URL.rstrip('/')}/integration/cards"
    return httpx.post(
        url, json=payload,
        headers={"X-API-Key": settings.TASKHS_API_KEY},
        timeout=5,
    )


def enviar_card(payload: dict) -> None:
    """Alvo do BackgroundTask: no-op se desligada; nunca propaga (best-effort)."""
    if not integracao_ativa():
        registrar_log_integracao(integracao="taskhs", status="pulado",
                                 motivo="desligado", payload=payload)
        return
    try:
        resp = _post(payload)
    except Exception as e:
        registrar_log_integracao(integracao="taskhs", status="erro",
                                 payload=payload, resposta=str(e))
        logger.exception("falha de rede ao espelhar card no TaskHS (external_id=%s)",
                         payload.get("external_id"))
        return
    if resp.status_code >= 400:
        registrar_log_integracao(integracao="taskhs", status="erro", payload=payload,
                                 http_status=resp.status_code, resposta=resp.text)
        logger.warning("TaskHS respondeu %s (external_id=%s)",
                       resp.status_code, payload.get("external_id"))
        return
    registrar_log_integracao(integracao="taskhs", status="sucesso", payload=payload,
                             http_status=resp.status_code, resposta=resp.text)


def enviar_card_sync(payload: dict) -> None:
    """Envia PROPAGANDO erro (uso no script de backfill, que quer relatar falhas)."""
    resp = _post(payload)
    if resp.status_code >= 400:
        registrar_log_integracao(integracao="taskhs", status="erro", payload=payload,
                                 http_status=resp.status_code, resposta=resp.text)
        raise RuntimeError(f"TaskHS respondeu {resp.status_code}: {resp.text[:500]}")
    registrar_log_integracao(integracao="taskhs", status="sucesso", payload=payload,
                             http_status=resp.status_code, resposta=resp.text)
```

- [ ] **Step 4: Rodar e ver passar (mais a suíte do TaskHS que já existe)**

Run: `pytest tests/test_taskhs_client_log.py tests/test_taskhs_espelhamento.py -q` (o segundo arquivo pode ter outro nome — rode `pytest -k taskhs -q` para pegar todos)
Expected: PASS. Se algum teste antigo dependia de `_post` levantar em status, ajustar aquele teste para o novo contrato (o `enviar_card` best-effort não muda de comportamento observável — segue não propagando).

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/integrations/taskhs_client.py tests/test_taskhs_client_log.py
git commit -m "feat(integracao): taskhs_client registra sucesso erro e pulado"
```

---

### Task 5: Instrumentar `hsgrowth_client`

**Files:**
- Modify: `backend/app/integrations/hsgrowth_client.py`
- Test: `backend/tests/test_hsgrowth_client_log.py`

**Interfaces:**
- Consumes: `registrar_log_integracao` (Task 3).
- Produces:
  - `_post(payload: dict) -> httpx.Response` (levanta só em erro de rede)
  - `enviar_card(payload)` — best-effort; loga; nunca levanta
  - `enviar_card_sync(payload) -> dict` — loga; **levanta** em status >= 400; devolve `resp.json()` no sucesso (contrato preservado para os scripts de vencendo/atrasados)

- [ ] **Step 1: Escrever os testes que falham**

```python
# backend/tests/test_hsgrowth_client_log.py
import pytest

from app.integrations import hsgrowth_client
from app.core.config import settings


class _Resp:
    def __init__(self, status_code, payload=None, text="ok"):
        self.status_code = status_code
        self._payload = payload or {"created": True}
        self.text = text

    def json(self):
        return self._payload


def _ativa(monkeypatch):
    monkeypatch.setattr(settings, "HSGROWTH_BASE_URL", "https://growth.test")
    monkeypatch.setattr(settings, "HSGROWTH_API_KEY", "k")


def test_enviar_card_loga_sucesso(monkeypatch):
    _ativa(monkeypatch)
    chamadas = []
    monkeypatch.setattr(hsgrowth_client, "registrar_log_integracao",
                        lambda **kw: chamadas.append(kw))
    monkeypatch.setattr(hsgrowth_client, "_post", lambda p: _Resp(200))
    hsgrowth_client.enviar_card({"source": "gestorhs.os", "external_id": "10853"})
    assert chamadas[0]["integracao"] == "growthhs"
    assert chamadas[0]["status"] == "sucesso"


def test_enviar_card_loga_pulado_desligado(monkeypatch):
    monkeypatch.setattr(settings, "HSGROWTH_BASE_URL", "")
    monkeypatch.setattr(settings, "HSGROWTH_API_KEY", "")
    chamadas = []
    monkeypatch.setattr(hsgrowth_client, "registrar_log_integracao",
                        lambda **kw: chamadas.append(kw))
    hsgrowth_client.enviar_card({"source": "gestorhs.os", "external_id": "10853"})
    assert chamadas[0]["status"] == "pulado"
    assert chamadas[0]["motivo"] == "desligado"


def test_enviar_card_sync_devolve_json_e_loga(monkeypatch):
    _ativa(monkeypatch)
    monkeypatch.setattr(hsgrowth_client, "registrar_log_integracao", lambda **kw: None)
    monkeypatch.setattr(hsgrowth_client, "_post",
                        lambda p: _Resp(200, {"id": 1, "created": True}))
    out = hsgrowth_client.enviar_card_sync({"source": "gestorhs.os", "external_id": "10853"})
    assert out["created"] is True


def test_enviar_card_sync_levanta_em_erro(monkeypatch):
    _ativa(monkeypatch)
    monkeypatch.setattr(hsgrowth_client, "registrar_log_integracao", lambda **kw: None)
    monkeypatch.setattr(hsgrowth_client, "_post", lambda p: _Resp(422, text="campo Y"))
    with pytest.raises(RuntimeError):
        hsgrowth_client.enviar_card_sync({"source": "gestorhs.os", "external_id": "10853"})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_hsgrowth_client_log.py -q`
Expected: FAIL (o `enviar_card` atual não loga).

- [ ] **Step 3: Reescrever o cliente**

```python
# backend/app/integrations/hsgrowth_client.py
"""Cliente HTTP da integracao com o GrowthHS (best-effort, gating por env).

Endpoint create-or-return: chamar de novo com o mesmo (source, external_id)
devolve o card existente e NAO altera nada."""
import logging

import httpx

from app.core.config import settings
from app.integrations.log_integracao import registrar_log_integracao

logger = logging.getLogger(__name__)

_CAMINHO = "/api/v1/integration/service-cards"


def integracao_ativa() -> bool:
    return bool(settings.HSGROWTH_BASE_URL and settings.HSGROWTH_API_KEY)


def _post(payload: dict) -> httpx.Response:
    """POST cru; devolve a Response. Levanta so em erro de rede (nao de status)."""
    url = f"{settings.HSGROWTH_BASE_URL.rstrip('/')}{_CAMINHO}"
    return httpx.post(
        url, json=payload,
        headers={"X-API-Key": settings.HSGROWTH_API_KEY},
        timeout=10,
    )


def enviar_card(payload: dict) -> None:
    """Alvo do BackgroundTask: no-op se desligada; nunca propaga (best-effort)."""
    if not integracao_ativa():
        registrar_log_integracao(integracao="growthhs", status="pulado",
                                 motivo="desligado", payload=payload)
        return
    try:
        resp = _post(payload)
    except Exception as e:
        registrar_log_integracao(integracao="growthhs", status="erro",
                                 payload=payload, resposta=str(e))
        logger.exception("falha de rede ao criar card no GrowthHS (external_id=%s)",
                         payload.get("external_id"))
        return
    if resp.status_code >= 400:
        registrar_log_integracao(integracao="growthhs", status="erro", payload=payload,
                                 http_status=resp.status_code, resposta=resp.text)
        logger.warning("GrowthHS respondeu %s (external_id=%s)",
                       resp.status_code, payload.get("external_id"))
        return
    registrar_log_integracao(integracao="growthhs", status="sucesso", payload=payload,
                             http_status=resp.status_code, resposta=resp.text)


def enviar_card_sync(payload: dict) -> dict:
    """Envia PROPAGANDO erro (uso nos scripts). Devolve o JSON da resposta."""
    resp = _post(payload)
    if resp.status_code >= 400:
        registrar_log_integracao(integracao="growthhs", status="erro", payload=payload,
                                 http_status=resp.status_code, resposta=resp.text)
        raise RuntimeError(f"GrowthHS respondeu {resp.status_code}: {resp.text[:500]}")
    registrar_log_integracao(integracao="growthhs", status="sucesso", payload=payload,
                             http_status=resp.status_code, resposta=resp.text)
    return resp.json()
```

- [ ] **Step 4: Rodar e ver passar (mais a suíte GrowthHS existente)**

Run: `pytest tests/test_hsgrowth_client_log.py -q && pytest -k growthhs -q`
Expected: PASS. Se algum teste antigo esperava a mensagem exata do `RuntimeError` do `_post`, ajustar para o novo formato (`"GrowthHS respondeu {status}: ..."`).

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/integrations/hsgrowth_client.py tests/test_hsgrowth_client_log.py
git commit -m "feat(integracao): hsgrowth_client registra sucesso erro e pulado"
```

---

### Task 6: Logar pulo `sem_equipamento` em `agendar_card_os`

**Files:**
- Modify: `backend/app/api/growthhs_cards.py`
- Test: `backend/tests/test_growthhs_cards_log.py`

**Interfaces:**
- Consumes: `registrar_log_integracao` (Task 3).

- [ ] **Step 1: Escrever o teste que falha**

```python
# backend/tests/test_growthhs_cards_log.py
from types import SimpleNamespace

from app.api import growthhs_cards
from app.core.config import settings


class _BG:
    def add_task(self, *a, **k):
        pass


def test_pulo_sem_equipamento_loga(monkeypatch):
    monkeypatch.setattr(settings, "HSGROWTH_BASE_URL", "https://growth.test")
    monkeypatch.setattr(settings, "HSGROWTH_API_KEY", "k")
    chamadas = []
    monkeypatch.setattr(growthhs_cards, "registrar_log_integracao",
                        lambda **kw: chamadas.append(kw))
    ordem = SimpleNamespace(id=999, equipamento_rel=None)
    growthhs_cards.agendar_card_os(db=None, background_tasks=_BG(), ordem=ordem)
    assert chamadas and chamadas[0]["status"] == "pulado"
    assert chamadas[0]["motivo"] == "sem_equipamento"
    assert chamadas[0]["referencia_os"] == 999
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_growthhs_cards_log.py -q`
Expected: FAIL — hoje o ramo `ec is None` só faz `logger.warning` e retorna, sem registrar log.

- [ ] **Step 3: Instrumentar o ramo de pulo**

No topo de `backend/app/api/growthhs_cards.py`, adicionar o import:
```python
from app.integrations.log_integracao import registrar_log_integracao
```
No `agendar_card_os`, no ramo em que `ec is None`, antes do `return`:
```python
    ec = ordem.equipamento_rel
    if ec is None:
        logger.warning("OS sem equipamento vinculado, card do GrowthHS nao agendado (os=%s)", ordem.id)
        registrar_log_integracao(integracao="growthhs", status="pulado",
                                 motivo="sem_equipamento", referencia_os=ordem.id)
        return
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_growthhs_cards_log.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/api/growthhs_cards.py tests/test_growthhs_cards_log.py
git commit -m "feat(integracao): loga pulo por OS sem equipamento vinculado"
```

---

### Task 7: Schemas + endpoint `GET /logs-integracao` (lista, filtros, estado) + registro do router

**Files:**
- Create: `backend/app/schemas/logs_integracao.py`
- Create: `backend/app/api/logs_integracao.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_logs_integracao_api.py`

**Interfaces:**
- Consumes: `LogIntegracao` (Task 1); `integracao_ativa` de ambos os clientes; `require_funcao`, `get_current_usuario` de `deps`.
- Produces:
  - `GET /logs-integracao?integracao=&status=&tipo=&os=&q=&offset=&limit=` → `LogsPage{items, total, estado}`
  - Schema `EstadoIntegracoes{taskhs_ativo, growthhs_ativo}`

- [ ] **Step 1: Escrever os testes que falham**

```python
# backend/tests/test_logs_integracao_api.py
def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _seed(db_session):
    from app.models import LogIntegracao
    db_session.add_all([
        LogIntegracao(integracao="growthhs", tipo="os_card", external_id="10853",
                      referencia_os=10853, status="sucesso", http_status=200),
        LogIntegracao(integracao="growthhs", tipo="os_card", external_id="10854",
                      referencia_os=10854, status="erro", http_status=422, resposta="ruim"),
        LogIntegracao(integracao="taskhs", tipo="os_espelho", external_id="10853",
                      referencia_os=10853, status="pulado", motivo="desligado"),
    ])
    db_session.commit()


def test_lista_exige_admin(client, usuario_comum, db_session):
    h = _headers(client, "comum@hs.com", "senha123")
    assert client.get("/logs-integracao", headers=h).status_code == 403


def test_lista_retorna_tudo_e_estado(client, usuario_admin, db_session):
    _seed(db_session)
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.get("/logs-integracao", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert set(body["estado"].keys()) == {"taskhs_ativo", "growthhs_ativo"}


def test_filtra_por_status_e_integracao(client, usuario_admin, db_session):
    _seed(db_session)
    h = _headers(client, "admin@hs.com", "senha123")
    assert client.get("/logs-integracao?status=erro", headers=h).json()["total"] == 1
    assert client.get("/logs-integracao?integracao=taskhs", headers=h).json()["total"] == 1
    assert client.get("/logs-integracao?os=10853", headers=h).json()["total"] == 2
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_logs_integracao_api.py -q`
Expected: FAIL com 404 (rota inexistente) nas chamadas.

- [ ] **Step 3: Criar os schemas**

```python
# backend/app/schemas/logs_integracao.py
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class LogIntegracaoOut(BaseModel):
    id: int
    criado_em: Optional[datetime] = None
    integracao: str
    tipo: str
    external_id: Optional[str] = None
    referencia_os: Optional[int] = None
    status: str
    motivo: Optional[str] = None
    http_status: Optional[int] = None
    resposta: Optional[str] = None
    payload: Optional[dict] = None
    model_config = {"from_attributes": True}


class EstadoIntegracoes(BaseModel):
    taskhs_ativo: bool
    growthhs_ativo: bool


class LogsPage(BaseModel):
    items: list[LogIntegracaoOut]
    total: int
    estado: EstadoIntegracoes


class ReenvioOut(BaseModel):
    ok: bool
    mensagem: Optional[str] = None
```

- [ ] **Step 4: Criar o router (GET)**

```python
# backend/app/api/logs_integracao.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, LogIntegracao
from app.api.deps import require_funcao
from app.integrations import taskhs_client, hsgrowth_client
from app.schemas.logs_integracao import LogsPage, LogIntegracaoOut, EstadoIntegracoes

router = APIRouter(prefix="/logs-integracao", tags=["integracao"])
ADMIN = "Administrador"


@router.get("", response_model=LogsPage)
def listar(
    integracao: str | None = None,
    status: str | None = None,
    tipo: str | None = None,
    os: int | None = None,
    q: str | None = None,
    offset: int = 0,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_funcao(ADMIN)),
):
    query = db.query(LogIntegracao)
    if integracao:
        query = query.filter(LogIntegracao.integracao == integracao)
    if status:
        query = query.filter(LogIntegracao.status == status)
    if tipo:
        query = query.filter(LogIntegracao.tipo == tipo)
    if os is not None:
        query = query.filter(LogIntegracao.referencia_os == os)
    if q:
        termo = f"%{q}%"
        query = query.filter(or_(LogIntegracao.external_id.ilike(termo),
                                 LogIntegracao.resposta.ilike(termo)))
    total = query.count()
    items = query.order_by(LogIntegracao.id.desc()).offset(offset).limit(limit).all()
    estado = EstadoIntegracoes(
        taskhs_ativo=taskhs_client.integracao_ativa(),
        growthhs_ativo=hsgrowth_client.integracao_ativa(),
    )
    return LogsPage(items=[LogIntegracaoOut.model_validate(i) for i in items],
                    total=total, estado=estado)
```

- [ ] **Step 5: Registrar o router no `main.py`**

Em `backend/app/main.py`, o import dos routers é uma linha única no topo (`from app.api import auth, funcoes, ..., certificados_venda`). Acrescentar `logs_integracao` ao final dessa lista de imports. Depois, junto aos outros `app.include_router(...)` (após `app.include_router(certificados_gerais.router)`), adicionar:
```python
app.include_router(logs_integracao.router)
```

- [ ] **Step 6: Rodar e ver passar**

Run: `pytest tests/test_logs_integracao_api.py -q`
Expected: PASS (4 testes).

- [ ] **Step 7: Commit**

```bash
cd backend && git add app/schemas/logs_integracao.py app/api/logs_integracao.py app/main.py tests/test_logs_integracao_api.py
git commit -m "feat(integracao): endpoint de listagem de logs com filtros e estado"
```

---

### Task 8: Endpoint `POST /logs-integracao/{id}/reenviar`

**Files:**
- Modify: `backend/app/api/logs_integracao.py`
- Test: `backend/tests/test_logs_integracao_api.py` (acrescentar)

**Interfaces:**
- Consumes: `enviar_card_sync` de `taskhs_client`/`hsgrowth_client`; `LogIntegracao`.
- Produces: `POST /logs-integracao/{id}/reenviar` → `ReenvioOut{ok, mensagem}`. `409` se a linha não tiver `payload`.

- [ ] **Step 1: Escrever os testes que falham (acrescentar)**

```python
# backend/tests/test_logs_integracao_api.py  (acrescentar)
def test_reenviar_sem_payload_409(client, usuario_admin, db_session):
    from app.models import LogIntegracao
    row = LogIntegracao(integracao="growthhs", tipo="os_card", status="pulado",
                        motivo="sem_equipamento", referencia_os=1, payload=None)
    db_session.add(row); db_session.commit(); db_session.refresh(row)
    h = _headers(client, "admin@hs.com", "senha123")
    assert client.post(f"/logs-integracao/{row.id}/reenviar", headers=h).status_code == 409


def test_reenviar_ok(client, usuario_admin, db_session, monkeypatch):
    from app.models import LogIntegracao
    from app.api import logs_integracao
    row = LogIntegracao(integracao="growthhs", tipo="os_card", external_id="10853",
                        status="erro", payload={"source": "gestorhs.os", "external_id": "10853"})
    db_session.add(row); db_session.commit(); db_session.refresh(row)
    monkeypatch.setattr(logs_integracao.hsgrowth_client, "enviar_card_sync",
                        lambda payload: {"created": True})
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.post(f"/logs-integracao/{row.id}/reenviar", headers=h)
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_reenviar_exige_admin(client, usuario_comum, db_session):
    h = _headers(client, "comum@hs.com", "senha123")
    assert client.post("/logs-integracao/1/reenviar", headers=h).status_code == 403
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_logs_integracao_api.py -k reenviar -q`
Expected: FAIL com 404 (rota inexistente).

- [ ] **Step 3: Adicionar o endpoint ao router**

No topo de `logs_integracao.py`, incluir imports:
```python
from fastapi import HTTPException, status as http_status
from app.schemas.logs_integracao import ReenvioOut
```
E o endpoint:
```python
@router.post("/{log_id}/reenviar", response_model=ReenvioOut)
def reenviar(log_id: int, db: Session = Depends(get_db),
             _: Usuario = Depends(require_funcao(ADMIN))):
    row = db.query(LogIntegracao).filter(LogIntegracao.id == log_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="log nao encontrado")
    if not row.payload:
        raise HTTPException(status_code=http_status.HTTP_409_CONFLICT,
                            detail="linha sem payload, nao e reenviavel")
    cliente = taskhs_client if row.integracao == "taskhs" else hsgrowth_client
    try:
        cliente.enviar_card_sync(row.payload)  # loga a nova linha de resultado
        return ReenvioOut(ok=True, mensagem="reenviado")
    except Exception as e:
        return ReenvioOut(ok=False, mensagem=str(e)[:500])
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_logs_integracao_api.py -q`
Expected: PASS (todos).

- [ ] **Step 5: Rodar a suíte inteira do backend**

Run: `pytest -q`
Expected: sem novas falhas (as 4 falhas ambientais de `/data/uploads` e `.pytest_cache` já existiam — ignorar).

- [ ] **Step 6: Commit**

```bash
cd backend && git add app/api/logs_integracao.py tests/test_logs_integracao_api.py
git commit -m "feat(integracao): endpoint de reenvio de card por linha de log"
```

---

### Task 9: Frontend — cliente de API + página + testes

**Files:**
- Create: `frontend/src/app/integracao/api.ts`
- Create: `frontend/src/app/integracao/LogsIntegracaoPage.tsx`
- Create: `frontend/src/app/integracao/LogsIntegracaoPage.test.tsx`

**Interfaces:**
- Consumes: `apiJson` de `src/lib/api.ts`; `Badge`, `SearchBar`, `Select`, `Button`, `Page`, `Table`, `Spinner` de `src/components/ui/`.
- Produces: `logsIntegracaoApi.listar(params)`, `logsIntegracaoApi.reenviar(id)`; componente `LogsIntegracaoPage`.

- [ ] **Step 1: Escrever o cliente de API**

```typescript
// frontend/src/app/integracao/api.ts
import { apiJson } from '../../lib/api'

export type StatusLog = 'sucesso' | 'erro' | 'pulado'

export interface LogIntegracao {
  id: number
  criado_em: string | null
  integracao: string
  tipo: string
  external_id: string | null
  referencia_os: number | null
  status: StatusLog
  motivo: string | null
  http_status: number | null
  resposta: string | null
  payload: unknown | null
}

export interface EstadoIntegracoes {
  taskhs_ativo: boolean
  growthhs_ativo: boolean
}

export interface LogsPage {
  items: LogIntegracao[]
  total: number
  estado: EstadoIntegracoes
}

export interface FiltrosLogs {
  integracao?: string
  status?: string
  tipo?: string
  os?: string
  q?: string
  offset?: number
  limit?: number
}

export const logsIntegracaoApi = {
  listar(f: FiltrosLogs = {}): Promise<LogsPage> {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(f)) {
      if (v !== undefined && v !== '' && v !== null) qs.set(k, String(v))
    }
    const query = qs.toString()
    return apiJson<LogsPage>(`/logs-integracao${query ? `?${query}` : ''}`)
  },
  reenviar(id: number): Promise<{ ok: boolean; mensagem?: string }> {
    return apiJson(`/logs-integracao/${id}/reenviar`, { method: 'POST' })
  },
}

// Linha elegivel para reenvio: tem payload e nao foi sucesso.
export function podeReenviar(log: LogIntegracao): boolean {
  return log.payload != null && log.status !== 'sucesso'
}

export const TONE_STATUS: Record<StatusLog, 'primary' | 'danger' | 'neutral'> = {
  sucesso: 'primary',
  erro: 'danger',
  pulado: 'neutral',
}
```

- [ ] **Step 2: Escrever os testes que falham**

```tsx
// frontend/src/app/integracao/LogsIntegracaoPage.test.tsx
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { LogsIntegracaoPage } from './LogsIntegracaoPage'
import { logsIntegracaoApi, podeReenviar, type LogIntegracao } from './api'

const base: LogIntegracao = {
  id: 1, criado_em: '2026-07-21T10:00:00Z', integracao: 'growthhs', tipo: 'os_card',
  external_id: '10853', referencia_os: 10853, status: 'erro', motivo: null,
  http_status: 422, resposta: 'ruim', payload: { source: 'gestorhs.os' },
}

describe('podeReenviar', () => {
  it('so quando ha payload e nao foi sucesso', () => {
    expect(podeReenviar(base)).toBe(true)
    expect(podeReenviar({ ...base, status: 'sucesso' })).toBe(false)
    expect(podeReenviar({ ...base, payload: null })).toBe(false)
  })
})

describe('LogsIntegracaoPage', () => {
  beforeEach(() => {
    vi.spyOn(logsIntegracaoApi, 'listar').mockResolvedValue({
      items: [base], total: 1, estado: { taskhs_ativo: true, growthhs_ativo: false },
    })
  })

  it('mostra a linha, o estado desligado e o botao reenviar', async () => {
    render(<MemoryRouter><LogsIntegracaoPage /></MemoryRouter>)
    expect(await screen.findByText('10853')).toBeInTheDocument()
    expect(screen.getByText(/GrowthHS/i)).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: /reenviar/i })).toBeInTheDocument()
  })
})
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `cd frontend && npx vitest run src/app/integracao/LogsIntegracaoPage.test.tsx`
Expected: FAIL — `LogsIntegracaoPage` não existe.

- [ ] **Step 4: Implementar a página**

```tsx
// frontend/src/app/integracao/LogsIntegracaoPage.tsx
import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Page } from '../../components/ui/Page'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Spinner } from '../../components/ui/Spinner'
import { SearchBar } from '../../components/ui/SearchBar'
import { Select } from '../../components/ui/Select'
import {
  logsIntegracaoApi, podeReenviar, TONE_STATUS,
  type LogIntegracao, type EstadoIntegracoes,
} from './api'

export function LogsIntegracaoPage() {
  const [itens, setItens] = useState<LogIntegracao[]>([])
  const [estado, setEstado] = useState<EstadoIntegracoes | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [integracao, setIntegracao] = useState('')
  const [status, setStatus] = useState('')
  const [q, setQ] = useState('')
  const [reenviando, setReenviando] = useState<number | null>(null)
  const [aviso, setAviso] = useState('')

  const carregar = useCallback(async () => {
    setCarregando(true)
    try {
      const page = await logsIntegracaoApi.listar({ integracao, status, q })
      setItens(page.items)
      setEstado(page.estado)
    } finally {
      setCarregando(false)
    }
  }, [integracao, status, q])

  useEffect(() => { void carregar() }, [carregar])

  async function reenviar(log: LogIntegracao) {
    setReenviando(log.id); setAviso('')
    try {
      const r = await logsIntegracaoApi.reenviar(log.id)
      setAviso(r.ok ? `OS/card ${log.external_id ?? ''} reenviado` : `Falhou: ${r.mensagem ?? ''}`)
      await carregar()
    } finally {
      setReenviando(null)
    }
  }

  return (
    <Page title="Logs de Integração">
      {estado && (
        <div className="flex gap-2 mb-4">
          <Badge tone={estado.growthhs_ativo ? 'primary' : 'danger'}>
            GrowthHS: {estado.growthhs_ativo ? 'ativo' : 'desligado'}
          </Badge>
          <Badge tone={estado.taskhs_ativo ? 'primary' : 'danger'}>
            TaskHS: {estado.taskhs_ativo ? 'ativo' : 'desligado'}
          </Badge>
        </div>
      )}

      <div className="flex flex-wrap gap-2 mb-4">
        <Select value={integracao} onChange={(e) => setIntegracao(e.target.value)}>
          <option value="">Todas integrações</option>
          <option value="growthhs">GrowthHS</option>
          <option value="taskhs">TaskHS</option>
        </Select>
        <Select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Todos status</option>
          <option value="sucesso">Sucesso</option>
          <option value="erro">Erro</option>
          <option value="pulado">Pulado</option>
        </Select>
        <SearchBar value={q} onChange={setQ} placeholder="Buscar OS / external_id / erro" />
      </div>

      {aviso && <div className="mb-3 text-sm text-slate-600 dark:text-slate-300">{aviso}</div>}

      {carregando ? (
        <div className="flex justify-center py-16"><Spinner className="w-8 h-8" /></div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500">
                <th className="py-2 pr-4">Quando</th>
                <th className="py-2 pr-4">Integração</th>
                <th className="py-2 pr-4">Tipo</th>
                <th className="py-2 pr-4">OS</th>
                <th className="py-2 pr-4">Status</th>
                <th className="py-2 pr-4">Detalhe</th>
                <th className="py-2 pr-4"></th>
              </tr>
            </thead>
            <tbody>
              {itens.map((log) => (
                <tr key={log.id} className="border-t border-slate-100 dark:border-background-elevated align-top">
                  <td className="py-2 pr-4 whitespace-nowrap">{log.criado_em ? new Date(log.criado_em).toLocaleString('pt-BR') : '—'}</td>
                  <td className="py-2 pr-4">{log.integracao === 'growthhs' ? 'GrowthHS' : 'TaskHS'}</td>
                  <td className="py-2 pr-4">{log.tipo}</td>
                  <td className="py-2 pr-4">
                    {log.referencia_os
                      ? <Link className="text-primary" to={`/app/ordens/${log.referencia_os}`}>#{log.referencia_os}</Link>
                      : (log.external_id ?? '—')}
                  </td>
                  <td className="py-2 pr-4"><Badge tone={TONE_STATUS[log.status]}>{log.status}</Badge></td>
                  <td className="py-2 pr-4 max-w-md truncate" title={log.resposta ?? log.motivo ?? ''}>
                    {log.motivo ?? log.resposta ?? '—'}
                  </td>
                  <td className="py-2 pr-4">
                    {podeReenviar(log) && (
                      <Button variant="secondary" onClick={() => reenviar(log)} disabled={reenviando === log.id}>
                        {reenviando === log.id ? 'Reenviando…' : 'Reenviar'}
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
              {itens.length === 0 && (
                <tr><td colSpan={7} className="py-8 text-center text-slate-400">Nenhum log encontrado</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </Page>
  )
}
```

> Nota de adaptação: confira as props reais de `Page`, `SearchBar`, `Select` e `Button` nos arquivos em `src/components/ui/` e ajuste (ex.: se `SearchBar` recebe `onChange(valor)` vs `onChange(event)`, ou se `Button` usa `variant`/`tone`). Não invente props — siga a assinatura existente.

- [ ] **Step 5: Rodar e ver passar**

Run: `cd frontend && npx vitest run src/app/integracao/LogsIntegracaoPage.test.tsx`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd frontend && git add src/app/integracao/
git commit -m "feat(integracao): pagina de logs de integracao com filtros e reenvio"
```

---

### Task 10: Frontend — rota + item de sidebar (só Admin)

**Files:**
- Modify: `frontend/src/app/routes.tsx`
- Modify: `frontend/src/layout/Sidebar.tsx`
- Test: `frontend/src/layout/Sidebar.test.tsx` (acrescentar)

**Interfaces:**
- Consumes: `LogsIntegracaoPage` (Task 9).

- [ ] **Step 1: Escrever o teste que falha (sidebar esconde para não-admin)**

Acrescentar a `frontend/src/layout/Sidebar.test.tsx` um caso espelhando o de "Usuários":

```tsx
it('esconde "Logs de Integração" para não-admin', () => {
  // usar o mesmo setup de render/usuario não-admin já presente no arquivo
  expect(screen.queryByText('Logs de Integração')).toBeNull()
})

it('mostra "Logs de Integração" para Administrador', () => {
  // mesmo setup de admin já presente no arquivo
  expect(screen.getByText('Logs de Integração')).toBeInTheDocument()
})
```

> Adapte ao estilo exato do arquivo (helpers de render/usuário que ele já usa).

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd frontend && npx vitest run src/layout/Sidebar.test.tsx`
Expected: FAIL — o item ainda não existe.

- [ ] **Step 3: Adicionar o item no `Sidebar.tsx`**

Após o item `Solicitações`, no array de itens:
```tsx
  { label: 'Logs de Integração', icon: <IconIntegracao />, to: '/app/integracao', adminOnly: true },
```
Se não houver um ícone adequado, reutilize um existente já importado (ex.: `IconSolicitacoes` ou outro) para não criar dependência nova — troque `<IconIntegracao />` pelo escolhido.

- [ ] **Step 4: Adicionar a rota no `routes.tsx`**

Import no topo:
```tsx
import { LogsIntegracaoPage } from './integracao/LogsIntegracaoPage'
```
Rota dentro de `<Route element={<ComLayout />}>` (perto de `solicitacoes`):
```tsx
        <Route path="integracao" element={<LogsIntegracaoPage />} />
```

- [ ] **Step 5: Rodar e ver passar**

Run: `cd frontend && npx vitest run src/layout/Sidebar.test.tsx`
Expected: PASS.

- [ ] **Step 6: Verificação completa do frontend**

Run: `cd frontend && npm run lint && npx tsc -b --noEmit && npm run build`
Expected: sem erros.

- [ ] **Step 7: Commit**

```bash
cd frontend && git add src/app/routes.tsx src/layout/Sidebar.tsx src/layout/Sidebar.test.tsx
git commit -m "feat(integracao): rota e item de menu de logs so para admin"
```

---

### Task 11: Changelog + fechamento

**Files:**
- Modify: `frontend/src/app/changelog/data.ts`

- [ ] **Step 1: Adicionar entrada nova no changelog**

Abrir `frontend/src/app/changelog/data.ts` e acrescentar a entrada nova **no topo** (é a versão atual), seguindo o formato das entradas existentes (bump da versão conforme o padrão do arquivo — inspecionar a primeira entrada para o formato de `versao`/`data`/`itens`):
```
Página de Logs de Integração: acompanhe o que subiu (ou não) para o GrowthHS e o TaskHS, com filtros e botão de reenviar. Só Administrador.
```

- [ ] **Step 2: Verificação e commit**

Run: `cd frontend && npx tsc -b --noEmit`
Expected: sem erros.

```bash
cd frontend && git add src/app/changelog/data.ts
git commit -m "docs(changelog): pagina de logs de integracao"
```

---

## Self-Review (preenchido)

**Cobertura do spec:**
- Tabela + captura best-effort → Tasks 1-3. ✓
- Registro nos dois clientes (sucesso/erro/pulado-desligado) → Tasks 4-5. ✓
- Pulo por dado (sem_equipamento) → Task 6. ✓
- Endpoint lista + filtros + estado ativo/desligado + gating Admin → Task 7. ✓
- Endpoint reenviar (409 sem payload, nova linha via enviar_card_sync, gating) → Task 8. ✓
- Frontend: página, badges, faixa de estado, filtros, link pra OS, botão reenviar elegível → Task 9. ✓
- Rota + sidebar só Admin + espelho de regra → Task 10. ✓
- Changelog visível → Task 11. ✓
- Fora de escopo (expurgo, métricas, alertas, lote) → não implementados. ✓

**Consistência de tipos:** `registrar_log_integracao(**kwargs)` com as mesmas chaves em Tasks 3-6; `enviar_card_sync` devolve `dict` (growthhs) / `None` (taskhs) preservado; `LogsPage{items,total,estado}` idêntico entre schema (Task 7) e frontend (Task 9); `podeReenviar`/`TONE_STATUS` definidos em Task 9 e usados na página.

**Riscos anotados para o executor:**
- Testes antigos de `taskhs`/`growthhs` podem depender do contrato anterior de `_post` (que levantava em status). Ajustar aqueles testes ao novo contrato faz parte das Tasks 4/5 (Step 4).
- Props reais dos componentes de UID no frontend devem ser conferidas (nota na Task 9, Step 4).
