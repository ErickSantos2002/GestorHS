# Integração GestorHS → TaskHS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Espelhar cada Ordem de Serviço do GestorHS como um card no board `Serviço` do TaskHS, refletindo a fase como coluna, via a API de integração — best-effort e idempotente.

**Architecture:** Lógica pura em `app/core/taskhs.py` (mapa fase→lista + montagem de payload, sem I/O). Cliente HTTP isolado em `app/integrations/taskhs_client.py` (httpx, gating por env, best-effort). Wiring fino nos endpoints `abrir`/`avancar`/`cancelar` via `BackgroundTasks` após o commit. Script avulso para backfill das OS existentes.

**Tech Stack:** Python 3.12, FastAPI (`BackgroundTasks`), httpx 0.28, SQLAlchemy 2, pytest (SQLite in-memory).

## Global Constraints

- Domínio em **PT-BR** (nomes, mensagens).
- Integração **nasce desligada**: sem `TASKHS_API_KEY` (ou sem `TASKHS_BASE_URL`), tudo é no-op. Os testes do projeto rodam com integração desligada por default.
- **Best-effort**: falha de espelhamento nunca propaga para o request do usuário nem para o fluxo da OS.
- Constantes fixas: `SOURCE = "gestorhs"`, `BOARD = "Serviço"`.
- Mapa fase→lista (strings **exatas**, emoji incluso):
  - 4 → `🚚 Expedição (Abrindo caixa)`
  - 5 → `🔬Laboratório Calibração`
  - 6 → `Serviços 🪛`
  - 7 → `🚚 Expedição (Preparando para Envio)`
  - 8 → `📮Correios`
- Card: `priority="medium"` sempre; `archived=true` só no cancelamento; `due_date` = `prox_calibragem` (ou `null`).
- Commits seguem Conventional Commits em PT-BR **sem acentos**, uma linha, sem trailer de co-autor (ex.: `feat(integracao): ...`).

---

### Task 1: Lógica pura de payload — `app/core/taskhs.py`

**Files:**
- Create: `backend/app/core/taskhs.py`
- Test: `backend/tests/test_taskhs.py`

**Interfaces:**
- Consumes: nada (módulo puro; lê só atributos do objeto `ordem` passado).
- Produces:
  - `SOURCE: str`, `BOARD: str`, `FASE_PARA_LISTA: dict[int, str]`
  - `lista_da_fase(fase: int) -> str | None`
  - `montar_titulo(ordem) -> str`
  - `montar_payload(ordem, *, lista: str, arquivado: bool) -> dict`

O objeto `ordem` é lido apenas por atributos (`id`, `cliente_nome`, `equipamento_descricao`, `equipamento_serie`, `prox_calibragem`, `obs`) — os testes usam um stub `SimpleNamespace`, sem banco.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_taskhs.py`:

```python
from datetime import datetime, timezone
from types import SimpleNamespace

from app.core import taskhs


def _ordem(**kw):
    base = dict(
        id=1234, cliente_nome="Cliente X", equipamento_descricao="Bafômetro",
        equipamento_serie="SN-987", prox_calibragem=None, obs=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_lista_da_fase_cobre_ativas_e_finalizada():
    assert taskhs.lista_da_fase(4) == "🚚 Expedição (Abrindo caixa)"
    assert taskhs.lista_da_fase(5) == "🔬Laboratório Calibração"
    assert taskhs.lista_da_fase(6) == "Serviços 🪛"
    assert taskhs.lista_da_fase(7) == "🚚 Expedição (Preparando para Envio)"
    assert taskhs.lista_da_fase(8) == "📮Correios"


def test_lista_da_fase_cancelada_e_desconhecida_none():
    assert taskhs.lista_da_fase(9) is None
    assert taskhs.lista_da_fase(999) is None


def test_montar_titulo_completo():
    assert taskhs.montar_titulo(_ordem()) == "OS #1234 · Cliente X · Bafômetro"


def test_montar_titulo_sem_descricao_usa_serie():
    o = _ordem(equipamento_descricao=None)
    assert taskhs.montar_titulo(o) == "OS #1234 · Cliente X · SN-987"


def test_montar_titulo_so_id_quando_resto_vazio():
    o = _ordem(cliente_nome=None, equipamento_descricao=None, equipamento_serie=None)
    assert taskhs.montar_titulo(o) == "OS #1234"


def test_montar_payload_campos_basicos():
    p = taskhs.montar_payload(_ordem(obs="veio sem maleta"), lista="L", arquivado=False)
    assert p["source"] == "gestorhs"
    assert p["external_id"] == "1234"
    assert p["board"] == "Serviço"
    assert p["list"] == "L"
    assert p["title"] == "OS #1234 · Cliente X · Bafômetro"
    assert p["description"] == "veio sem maleta"
    assert p["priority"] == "medium"
    assert p["archived"] is False
    assert p["due_date"] is None


def test_montar_payload_due_date_de_prox_calibragem():
    o = _ordem(prox_calibragem=datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc))
    assert taskhs.montar_payload(o, lista="L", arquivado=False)["due_date"] == "2026-07-10"


def test_montar_payload_arquivado_true():
    assert taskhs.montar_payload(_ordem(), lista="L", arquivado=True)["archived"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T backend pytest tests/test_taskhs.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.core.taskhs'`).

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/core/taskhs.py`:

```python
"""Integração GestorHS → TaskHS: lógica pura (sem I/O).

Monta o payload do card a partir de uma OS e mapeia fase → nome de lista.
As strings de lista são exatas (emoji incluso) — o TaskHS resolve por nome.
"""

SOURCE = "gestorhs"
BOARD = "Serviço"

FASE_PARA_LISTA: dict[int, str] = {
    4: "🚚 Expedição (Abrindo caixa)",
    5: "🔬Laboratório Calibração",
    6: "Serviços 🪛",
    7: "🚚 Expedição (Preparando para Envio)",
    8: "📮Correios",
}


def lista_da_fase(fase: int) -> str | None:
    return FASE_PARA_LISTA.get(fase)


def montar_titulo(ordem) -> str:
    partes = [f"OS #{ordem.id}"]
    if ordem.cliente_nome:
        partes.append(ordem.cliente_nome)
    descricao = ordem.equipamento_descricao or ordem.equipamento_serie
    if descricao:
        partes.append(descricao)
    return " · ".join(partes)


def montar_payload(ordem, *, lista: str, arquivado: bool) -> dict:
    due_date = ordem.prox_calibragem.date().isoformat() if ordem.prox_calibragem else None
    return {
        "source": SOURCE,
        "external_id": str(ordem.id),
        "board": BOARD,
        "list": lista,
        "title": montar_titulo(ordem),
        "description": ordem.obs or None,
        "due_date": due_date,
        "priority": "medium",
        "archived": arquivado,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T backend pytest tests/test_taskhs.py -q`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/taskhs.py backend/tests/test_taskhs.py
git commit -m "feat(integracao): logica pura de payload do card TaskHS"
```

---

### Task 2: Config + cliente HTTP — `app/integrations/taskhs_client.py`

**Files:**
- Modify: `backend/app/core/config.py` (adicionar 2 settings)
- Create: `backend/app/integrations/__init__.py` (pacote novo, vazio)
- Create: `backend/app/integrations/taskhs_client.py`
- Test: `backend/tests/test_taskhs_client.py`

**Interfaces:**
- Consumes: `app.core.taskhs.montar_payload`; `app.core.config.settings`.
- Produces:
  - `integracao_ativa() -> bool`
  - `enviar_card(payload: dict) -> None` — alvo do BackgroundTask; **engole exceções** (best-effort).
  - `espelhar_os(ordem, *, lista: str, arquivado: bool = False) -> None` — monta payload e envia **propagando exceções** (usado pelo script de backfill).

- [ ] **Step 1: Add the config settings**

In `backend/app/core/config.py`, dentro de `class Settings`, logo após `UPLOAD_DIR`:

```python
    # Integração com o TaskHS (espelhar OS como cards). Vazio = desligada.
    TASKHS_BASE_URL: str = ""   # ex.: "https://taskhs.exemplo/api" (sem barra final)
    TASKHS_API_KEY: str = ""    # header X-API-Key
```

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_taskhs_client.py`:

```python
import httpx
import pytest
from types import SimpleNamespace

from app.core.config import settings
from app.integrations import taskhs_client


@pytest.fixture()
def ativa(monkeypatch):
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "http://taskhs.test/api")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "k-123")


def test_integracao_ativa_depende_das_envs(monkeypatch):
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "")
    assert taskhs_client.integracao_ativa() is False
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "http://x/api")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "k")
    assert taskhs_client.integracao_ativa() is True


def test_enviar_card_noop_sem_key(monkeypatch):
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "")
    chamou = []
    monkeypatch.setattr(httpx, "post", lambda *a, **k: chamou.append(1))
    taskhs_client.enviar_card({"external_id": "1"})
    assert chamou == []  # nem tentou


def test_enviar_card_faz_post_correto(monkeypatch, ativa):
    capturado = {}

    class FakeResp:
        def raise_for_status(self):
            return None

    def fake_post(url, json, headers, timeout):
        capturado.update(url=url, json=json, headers=headers, timeout=timeout)
        return FakeResp()

    monkeypatch.setattr(httpx, "post", fake_post)
    taskhs_client.enviar_card({"external_id": "1234"})
    assert capturado["url"] == "http://taskhs.test/api/integration/cards"
    assert capturado["headers"]["X-API-Key"] == "k-123"
    assert capturado["json"] == {"external_id": "1234"}
    assert capturado["timeout"] == 5


def test_enviar_card_engole_excecao(monkeypatch, ativa):
    def boom(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "post", boom)
    taskhs_client.enviar_card({"external_id": "1"})  # não deve levantar


def test_espelhar_os_monta_payload_e_propaga(monkeypatch, ativa):
    enviados = {}

    def fake_post(payload):
        enviados.update(payload)

    monkeypatch.setattr(taskhs_client, "_post", fake_post)
    ordem = SimpleNamespace(
        id=7, cliente_nome="Cli", equipamento_descricao="Baf",
        equipamento_serie="S1", prox_calibragem=None, obs=None,
    )
    taskhs_client.espelhar_os(ordem, lista="🔬Laboratório Calibração", arquivado=False)
    assert enviados["external_id"] == "7"
    assert enviados["list"] == "🔬Laboratório Calibração"
    assert enviados["archived"] is False
```

- [ ] **Step 3: Run test to verify it fails**

Run: `docker compose exec -T backend pytest tests/test_taskhs_client.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.integrations'`).

- [ ] **Step 4: Write minimal implementation**

Create `backend/app/integrations/__init__.py` (vazio).

Create `backend/app/integrations/taskhs_client.py`:

```python
"""Cliente HTTP da integração com o TaskHS (best-effort, gating por env)."""
import logging

import httpx

from app.core import taskhs
from app.core.config import settings

logger = logging.getLogger(__name__)


def integracao_ativa() -> bool:
    return bool(settings.TASKHS_BASE_URL and settings.TASKHS_API_KEY)


def _post(payload: dict) -> None:
    """Faz o POST e levanta em erro (httpx.HTTPStatusError / rede)."""
    url = f"{settings.TASKHS_BASE_URL.rstrip('/')}/integration/cards"
    resp = httpx.post(
        url, json=payload,
        headers={"X-API-Key": settings.TASKHS_API_KEY},
        timeout=5,
    )
    resp.raise_for_status()


def enviar_card(payload: dict) -> None:
    """Alvo do BackgroundTask: no-op se desligada; nunca propaga (best-effort)."""
    if not integracao_ativa():
        return
    try:
        _post(payload)
    except Exception:
        logger.exception(
            "falha ao espelhar card no TaskHS (external_id=%s) — reconcilia no proximo upsert",
            payload.get("external_id"),
        )


def espelhar_os(ordem, *, lista: str, arquivado: bool = False) -> None:
    """Monta o payload da OS e envia, PROPAGANDO erros (uso em script de backfill)."""
    _post(taskhs.montar_payload(ordem, lista=lista, arquivado=arquivado))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose exec -T backend pytest tests/test_taskhs_client.py -q`
Expected: PASS (5 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/config.py backend/app/integrations/ backend/tests/test_taskhs_client.py
git commit -m "feat(integracao): cliente HTTP best-effort para o TaskHS"
```

---

### Task 3: Wiring nos endpoints — `app/api/ordens.py`

**Files:**
- Modify: `backend/app/api/ordens.py` (imports; `abrir`, `avancar`, `cancelar`)
- Test: `backend/tests/test_ordens_taskhs.py`

**Interfaces:**
- Consumes: `app.core.taskhs.{lista_da_fase, montar_payload}`; `app.integrations.taskhs_client.{integracao_ativa, enviar_card}`; `fastapi.BackgroundTasks`.
- Produces: nada novo (efeito colateral: agenda `enviar_card(payload)` após commit).

Padrão em cada endpoint: depois do `db.commit()`/`db.refresh(ordem)`, se `integracao_ativa()`, monta o payload **no request** (objeto ainda anexado) e agenda só o `dict`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_ordens_taskhs.py`:

```python
import pytest

from app.core.config import settings
from app.integrations import taskhs_client


def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


@pytest.fixture()
def captura(monkeypatch):
    """Liga a integração e captura os payloads agendados (sem HTTP real)."""
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "http://taskhs.test/api")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "k-123")
    chamadas = []
    monkeypatch.setattr(taskhs_client, "enviar_card", lambda payload: chamadas.append(payload))
    return chamadas


def test_abrir_agenda_card_recebido(client, usuario_comum, fases_seed, os_base, caixa_base, captura):
    h = _headers(client, "comum", "senha123")
    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C",
        "caixa": caixa_base,
    }, headers=h)
    assert r.status_code == 201
    assert len(captura) == 1
    p = captura[0]
    assert p["external_id"] == str(r.json()["id"])
    assert p["list"] == "🚚 Expedição (Abrindo caixa)"
    assert p["archived"] is False


def test_abrir_sem_integracao_nao_agenda(client, usuario_comum, fases_seed, os_base, caixa_base, monkeypatch):
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "")
    chamadas = []
    monkeypatch.setattr(taskhs_client, "enviar_card", lambda payload: chamadas.append(payload))
    h = _headers(client, "comum", "senha123")
    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C",
        "caixa": caixa_base,
    }, headers=h)
    assert r.status_code == 201
    assert chamadas == []


def test_avancar_agenda_card_laboratorio(client, usuario_comum, fases_seed, os_base, caixa_base, captura):
    # avançar de Recebido(4)→Laboratório(5) exige a função da fase de origem = Expedição (usuario_comum)
    h = _headers(client, "comum", "senha123")
    oid = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C",
        "caixa": caixa_base,
    }, headers=h).json()["id"]
    captura.clear()  # ignora o card da abertura
    r = client.post(f"/ordens/{oid}/avancar", json={}, headers=h)
    assert r.status_code == 200
    assert len(captura) == 1
    assert captura[0]["list"] == "🔬Laboratório Calibração"


def test_cancelar_agenda_card_arquivado_na_lista_de_origem(client, usuario_comum, fases_seed, os_base, caixa_base, captura):
    h = _headers(client, "comum", "senha123")
    oid = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C",
        "caixa": caixa_base,
    }, headers=h).json()["id"]
    captura.clear()
    r = client.post(f"/ordens/{oid}/cancelar", json={"motivo": "desistencia"}, headers=h)
    assert r.status_code == 200
    assert len(captura) == 1
    p = captura[0]
    assert p["archived"] is True
    assert p["list"] == "🚚 Expedição (Abrindo caixa)"  # fase de origem (Recebido)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T backend pytest tests/test_ordens_taskhs.py -q`
Expected: FAIL (`captura` agenda nada — `enviar_card` não é chamado; asserts de `len(captura)==1` falham).

- [ ] **Step 3: Implement the wiring**

In `backend/app/api/ordens.py`:

3a. Imports — adicionar `BackgroundTasks` ao import do FastAPI e importar a integração. A linha 3 atual:
```python
from fastapi import APIRouter, Depends, HTTPException, status as http_status, Query
```
vira:
```python
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status as http_status, Query
```
E adicionar, junto aos imports de `app.core` (após a linha `from app.core.os_workflow import FASE_FINALIZADA`):
```python
from app.core import taskhs
from app.integrations import taskhs_client
```

3b. `abrir` — adicionar o parâmetro `background_tasks: BackgroundTasks` na assinatura e o espelhamento antes do `return ordem`. A assinatura atual:
```python
def abrir(dados: OrdemAbrirIn, db: Session = Depends(get_db),
          usuario: Usuario = Depends(require_funcao("Expedição", "Administrador"))):
```
vira:
```python
def abrir(dados: OrdemAbrirIn, background_tasks: BackgroundTasks, db: Session = Depends(get_db),
          usuario: Usuario = Depends(require_funcao("Expedição", "Administrador"))):
```
E antes de `return ordem` (atual linha 173), inserir:
```python
    if taskhs_client.integracao_ativa():
        payload = taskhs.montar_payload(ordem, lista=taskhs.lista_da_fase(ordem.fase), arquivado=False)
        background_tasks.add_task(taskhs_client.enviar_card, payload)
    return ordem
```

3c. `avancar` — assinatura atual:
```python
def avancar(ordem_id: int, dados: AvancarIn, db: Session = Depends(get_db),
            usuario: Usuario = Depends(get_current_usuario)):
```
vira:
```python
def avancar(ordem_id: int, dados: AvancarIn, background_tasks: BackgroundTasks,
            db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_usuario)):
```
E antes de `return ordem` (atual linha 216), inserir:
```python
    if taskhs_client.integracao_ativa():
        lista = taskhs.lista_da_fase(ordem.fase)
        if lista is not None:
            payload = taskhs.montar_payload(ordem, lista=lista, arquivado=False)
            background_tasks.add_task(taskhs_client.enviar_card, payload)
    return ordem
```

3d. `cancelar` — assinatura atual:
```python
def cancelar(ordem_id: int, dados: CancelarIn, db: Session = Depends(get_db),
             usuario: Usuario = Depends(get_current_usuario)):
```
vira:
```python
def cancelar(ordem_id: int, dados: CancelarIn, background_tasks: BackgroundTasks,
             db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_usuario)):
```
Capturar a fase de origem **antes** de sobrescrever para Cancelada. O corpo atual (a partir de "if not wf.eh_ativa"):
```python
    if not wf.eh_ativa(ordem.fase):
        raise HTTPException(status_code=409, detail="OS já encerrada")
    exige_funcao_da_fase(db, usuario, ordem.fase)
    ordem.fase = wf.FASE_CANCELADA
```
vira:
```python
    if not wf.eh_ativa(ordem.fase):
        raise HTTPException(status_code=409, detail="OS já encerrada")
    exige_funcao_da_fase(db, usuario, ordem.fase)
    origem = ordem.fase
    ordem.fase = wf.FASE_CANCELADA
```
E antes de `return ordem` (atual linha 233), inserir:
```python
    if taskhs_client.integracao_ativa():
        lista = taskhs.lista_da_fase(origem)
        if lista is not None:
            payload = taskhs.montar_payload(ordem, lista=lista, arquivado=True)
            background_tasks.add_task(taskhs_client.enviar_card, payload)
    return ordem
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T backend pytest tests/test_ordens_taskhs.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Run the full suite (no regression)**

Run: `docker compose exec -T backend pytest -q`
Expected: PASS (todos os testes existentes + os novos; nenhum agendamento em testes que não ligam a integração).

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/ordens.py backend/tests/test_ordens_taskhs.py
git commit -m "feat(integracao): espelha OS no TaskHS ao abrir avancar e cancelar"
```

---

### Task 4: Script de backfill — `app/scripts/sincronizar_taskhs.py`

**Files:**
- Create: `backend/app/scripts/sincronizar_taskhs.py`
- Test: `backend/tests/test_sincronizar_taskhs.py`

**Interfaces:**
- Consumes: `app.models.database.SessionLocal`; `app.models.Ordem`; `app.core.taskhs.lista_da_fase`; `app.integrations.taskhs_client.{integracao_ativa, espelhar_os}`.
- Produces: `sincronizar(db) -> tuple[int, int]` (retorna `(enviadas, total)`); `main() -> None` (entrypoint CLI).

Separar `sincronizar(db)` (testável com a Session de teste) do `main()` (abre `SessionLocal`, imprime).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_sincronizar_taskhs.py`:

```python
import pytest

from app.core.config import settings
from app.integrations import taskhs_client
from app.scripts import sincronizar_taskhs


def _abrir_os(db, os_base, fase):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"],
              fase=fase, tipo_servico="C", situacao="E")
    db.add(o); db.commit(); db.refresh(o)
    return o


def test_sincronizar_envia_so_fases_4_a_8(db_session, os_base, fases_seed, monkeypatch):
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "http://t/api")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "k")
    _abrir_os(db_session, os_base, 4)
    _abrir_os(db_session, os_base, 8)
    _abrir_os(db_session, os_base, 9)  # cancelada: ignorada
    enviados = []
    monkeypatch.setattr(taskhs_client, "espelhar_os",
                        lambda ordem, *, lista, arquivado=False: enviados.append((ordem.fase, lista)))
    enviadas, total = sincronizar_taskhs.sincronizar(db_session)
    assert enviadas == 2
    assert total == 2
    fases = sorted(f for f, _ in enviados)
    assert fases == [4, 8]


def test_sincronizar_desligada_levanta(db_session, monkeypatch):
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "")
    with pytest.raises(RuntimeError):
        sincronizar_taskhs.sincronizar(db_session)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T backend pytest tests/test_sincronizar_taskhs.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.scripts.sincronizar_taskhs'`).

- [ ] **Step 3: Write the implementation**

Create `backend/app/scripts/sincronizar_taskhs.py`:

```python
"""Backfill: espelha no TaskHS as OS já existentes (fases 4–8).

Uso: python -m app.scripts.sincronizar_taskhs
Idempotente — pode rodar quantas vezes quiser.
"""
from sqlalchemy.orm import Session

from app.core import taskhs
from app.integrations import taskhs_client
from app.models import Ordem
from app.models.database import SessionLocal

FASES_BACKFILL = [4, 5, 6, 7, 8]


def sincronizar(db: Session) -> tuple[int, int]:
    """Faz upsert de cada OS em fase 4–8. Retorna (enviadas, total)."""
    if not taskhs_client.integracao_ativa():
        raise RuntimeError(
            "Integração desligada: configure TASKHS_BASE_URL e TASKHS_API_KEY."
        )
    ordens = (
        db.query(Ordem)
        .filter(Ordem.fase.in_(FASES_BACKFILL))
        .order_by(Ordem.id)
        .all()
    )
    enviadas = 0
    for o in ordens:
        lista = taskhs.lista_da_fase(o.fase)
        if lista is None:
            continue
        try:
            taskhs_client.espelhar_os(o, lista=lista, arquivado=False)
            enviadas += 1
            print(f"OK   OS #{o.id} -> {lista}")
        except Exception as e:  # noqa: BLE001 — relatório, segue para a próxima
            print(f"ERRO OS #{o.id}: {e}")
    return enviadas, len(ordens)


def main() -> None:
    db = SessionLocal()
    try:
        enviadas, total = sincronizar(db)
        print(f"\n{enviadas}/{total} OS sincronizadas com o TaskHS.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T backend pytest tests/test_sincronizar_taskhs.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/scripts/sincronizar_taskhs.py backend/tests/test_sincronizar_taskhs.py
git commit -m "feat(integracao): script de backfill das OS existentes no TaskHS"
```

---

### Task 5: Verificação final + documentação

**Files:**
- Modify: `backend/.env.example` (se existir) — documentar as duas envs novas
- Modify: `CLAUDE.md` — nota curta sobre a integração TaskHS (seção Arquitetura)

- [ ] **Step 1: Rodar a suíte completa**

Run: `docker compose exec -T backend pytest -q`
Expected: PASS (tudo verde).

- [ ] **Step 2: Documentar as envs**

Se `backend/.env.example` existir, acrescentar:
```
# Integração com o TaskHS (opcional; vazio = desligada)
TASKHS_BASE_URL=
TASKHS_API_KEY=
```
Se não existir, pular este passo (o projeto usa `.env` direto).

- [ ] **Step 3: Nota no CLAUDE.md**

Em `CLAUDE.md`, na seção "Arquitetura", adicionar um parágrafo curto:
```markdown
### Integração com o TaskHS
A cada abrir/avançar/cancelar de OS, o GestorHS espelha a OS como um card no board
`Serviço` do TaskHS (`app/core/taskhs.py` puro + `app/integrations/taskhs_client.py`
I/O, disparado via `BackgroundTasks` best-effort). Nasce desligada: sem
`TASKHS_BASE_URL`/`TASKHS_API_KEY` é no-op. Backfill: `python -m app.scripts.sincronizar_taskhs`.
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md backend/.env.example
git commit -m "docs(integracao): documenta envs e arquitetura da integracao TaskHS"
```

---

## Notas de integração ponta-a-ponta (manual, fora dos testes)

Após implementar, validar de verdade contra o TaskHS local (porta 8000):

1. No `backend/.env` do GestorHS, setar `TASKHS_BASE_URL=http://host.docker.internal:8000/api`
   (o backend roda em container; `localhost` dentro do container não é o host) e
   `TASKHS_API_KEY=test-integration-key-123`. Reiniciar o container.
2. Abrir uma OS pela UI → conferir card na coluna `🚚 Expedição (Abrindo caixa)` do board `Serviço`.
3. Avançar a OS → card move para `🔬Laboratório Calibração`.
4. Cancelar uma OS → card arquivado (some do board).
5. Rodar `docker compose exec -T backend python -m app.scripts.sincronizar_taskhs` → popular OS existentes.
