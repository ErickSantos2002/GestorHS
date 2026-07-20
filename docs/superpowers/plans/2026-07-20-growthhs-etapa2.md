# GrowthHS — Etapa 2: OS liberada do laboratório → card de Serviços — Plano

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans. Passos usam checkbox (`- [ ]`).

**Goal:** Quando o laboratório conclui uma OS (transição de fase 5→6), criar automaticamente um card no board de **Serviços** do GrowthHS, para o comercial faturar/entregar o serviço já pronto.

**Architecture:** Um módulo `app/api/growthhs_cards.py` no mesmo papel que o `espelhamento.py` já cumpre para o TaskHS (consulta o banco, monta o payload, agenda via `BackgroundTasks`). A montagem do payload em si fica pura em `app/core/growthhs_os.py`. A busca do elo Phoebus↔Módulo — hoje inline no script da Etapa 1 — é extraída para ser usada pelos dois.

**Tech Stack:** Python 3.12 · FastAPI · SQLAlchemy 2 · pytest.

**Contexto:** a base (cliente HTTP `hsgrowth_client`, payload `growthhs_payload`) já existe e está em produção desde a Etapa 1. Esta etapa só acrescenta o gatilho.

## Global Constraints

- Idioma PT-BR em nomes, mensagens e docstrings.
- **Best-effort absoluto:** falha na integração **nunca** pode impedir a OS de avançar nem reverter o commit. Mesmo molde do `agendar_espelhamento`.
- **Uma única chamada por OS**, só na transição 5→6. Não plugar em `abrir`, `cancelar` nem nas outras transições — o endpoint é *create-or-return*, reenviar não faz nada além de gastar request.
- **`due_date` precisa ser datetime COMPLETO** (`YYYY-MM-DDTHH:MM:SS`). Data pura devolve `422` — descoberto em produção em 18/07/2026.
- Reusar `montar_cliente` / `montar_contato` / `montar_device` de `app/core/growthhs_payload.py` (já tratam os limites de telefone do schema).
- `title` tem limite de **500** caracteres no schema do GrowthHS — truncar se necessário.
- Board: `settings.HSGROWTH_BOARD_SERVICOS`. `source = "gestorhs.os"`, `external_id = str(ordem.id)`.
- Sem env configurada, a integração é **no-op** (nasce desligada).
- Backend: `docker exec gestorhs-backend pytest -q` (NÃO há venv local).
- Commits Conventional Commits em PT-BR sem acentos, uma linha, sem trailer.

---

### Task 1: Constante `FASE_LABORATORIO` + busca do elo compartilhada

**Files:**
- Modify: `backend/app/core/os_workflow.py`
- Create: `backend/app/api/growthhs_cards.py`
- Modify: `backend/app/scripts/enviar_atrasados_growthhs.py`
- Test: `backend/tests/test_growthhs_elo.py`

**Interfaces:**
- `os_workflow.FASE_LABORATORIO = 5` (a fase existe no fluxo mas não tinha constante nomeada; o `CLAUDE.md` pede constantes em vez de números).
- `growthhs_cards.buscar_elo(db, ec) -> SimpleNamespace | None` — dado um `equipamento_cliente`, devolve o Phoebus em que ele está instalado, **já com a ponte de atributos** (`.serie` e `.descricao`), ou `None`. Só faz sentido quando `ec.equipamento == settings.EQUIPAMENTO_MODULO_ID`.
  - **A ponte é obrigatória:** `montar_device(elo=...)` espera `.descricao`, mas a linha ORM expõe `.equipamento_descricao`. Passar o ORM cru quebra com `AttributeError` — e só no caso interessante (módulo COM elo).
- `enviar_atrasados_growthhs.buscar_atrasados` passa a **chamar `buscar_elo`** em vez de ter a lógica inline (remover a duplicação).

- [ ] **Step 1: Escrever o teste que falha**

```python
# backend/tests/test_growthhs_elo.py
from datetime import date


def _equip(db_session, os_base, serie, equipamento=None):
    from app.models import EquipamentoCliente
    ec = EquipamentoCliente(cliente=os_base["cliente"],
                            equipamento=equipamento or os_base["equipamento"], serie=serie)
    db_session.add(ec); db_session.commit(); db_session.refresh(ec)
    return ec


def _instalar(db_session, modulo_id, phoebus_id):
    from app.models import InstalacaoModulo
    i = InstalacaoModulo(modulo=modulo_id, phoebus=phoebus_id,
                         entrou_em=date(2026, 7, 18), origem="teste")
    db_session.add(i); db_session.commit()
    return i


def test_fase_laboratorio_tem_constante():
    from app.core import os_workflow as wf
    assert wf.FASE_LABORATORIO == 5
    assert wf.PROXIMA[wf.FASE_LABORATORIO] == 6      # laboratorio -> pos-vendas


def test_elo_none_quando_nao_e_modulo(db_session, os_base):
    from app.api.growthhs_cards import buscar_elo
    ec = _equip(db_session, os_base, "SN-1")          # equipamento comum
    assert buscar_elo(db_session, ec) is None


def test_elo_none_quando_modulo_sem_instalacao(db_session, os_base):
    from app.api.growthhs_cards import buscar_elo
    from app.core.config import settings
    mod = _equip(db_session, os_base, "F001", equipamento=settings.EQUIPAMENTO_MODULO_ID)
    assert buscar_elo(db_session, mod) is None


def test_elo_traz_o_phoebus_com_a_ponte_de_atributos(db_session, os_base):
    """A ponte e obrigatoria: montar_device espera .descricao, o ORM expoe
    .equipamento_descricao. Sem ela, quebra com AttributeError."""
    from app.api.growthhs_cards import buscar_elo
    from app.core.config import settings
    pho = _equip(db_session, os_base, "WATFR01-00340")
    mod = _equip(db_session, os_base, "F005065", equipamento=settings.EQUIPAMENTO_MODULO_ID)
    _instalar(db_session, mod.id, pho.id)

    elo = buscar_elo(db_session, mod)
    assert elo is not None
    assert elo.serie == "WATFR01-00340"
    assert hasattr(elo, "descricao")          # o nome que montar_device consome
    # e o elo funciona de ponta a ponta no montar_device:
    from app.core.growthhs_payload import montar_device
    d = montar_device(mod, "Modulo de Calibracao", elo=elo)
    assert d["serial_number"] == "WATFR01-00340"
    assert d["alcohol_module"] == "F005065"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker exec gestorhs-backend pytest -q tests/test_growthhs_elo.py`
Expected: FAIL — `FASE_LABORATORIO` e `growthhs_cards` não existem.

- [ ] **Step 3: Implementar**

Em `backend/app/core/os_workflow.py`, junto das outras constantes:
```python
FASE_LABORATORIO = 5
```

Criar `backend/app/api/growthhs_cards.py` (por ora só com `buscar_elo`; o resto vem nas Tasks 2 e 3):
```python
"""Cards do GrowthHS disparados pelo fluxo da OS.

Mesmo papel que `espelhamento.py` cumpre para o TaskHS: consulta o banco, monta
o payload e agenda o envio — mantido fora dos routers para evitar import circular.
"""
from types import SimpleNamespace

from app.core.config import settings
from app.models import EquipamentoCliente, InstalacaoModulo


def buscar_elo(db, ec):
    """O Phoebus em que este modulo esta instalado, ou None.

    Devolve um objeto com `.serie` e `.descricao` — a PONTE obrigatoria para o
    `montar_device`, que espera esses nomes. A linha ORM de EquipamentoCliente
    expoe a descricao do catalogo como `.equipamento_descricao`, entao passar o
    ORM cru quebraria com AttributeError bem no caso interessante (modulo COM elo).
    """
    if ec is None or ec.equipamento != settings.EQUIPAMENTO_MODULO_ID:
        return None
    instalacao = (
        db.query(InstalacaoModulo)
        .filter(InstalacaoModulo.modulo == ec.id, InstalacaoModulo.saiu_em.is_(None))
        .first()
    )
    if instalacao is None:
        return None
    phoebus = db.get(EquipamentoCliente, instalacao.phoebus)
    if phoebus is None:
        return None
    return SimpleNamespace(serie=phoebus.serie, descricao=phoebus.equipamento_descricao)
```

Em `enviar_atrasados_growthhs.buscar_atrasados`, **substituir o bloco inline** de busca do elo por `elo = buscar_elo(db, ec)` (importando de `app.api.growthhs_cards`). Os testes existentes do script devem continuar passando sem alteração — se algum quebrar, é sinal de que a extração mudou comportamento.

- [ ] **Step 4: Rodar e ver passar**

Run: `docker exec gestorhs-backend pytest -q tests/test_growthhs_elo.py tests/test_enviar_atrasados_growthhs.py`
Expected: PASS — os novos e os do script (que exercitam o elo de ponta a ponta).

- [ ] **Step 5: Suíte completa + commit**

Run: `docker exec gestorhs-backend pytest -q`

```bash
git add backend/app/core/os_workflow.py backend/app/api/growthhs_cards.py backend/app/scripts/enviar_atrasados_growthhs.py backend/tests/test_growthhs_elo.py
git commit -m "refactor(growthhs): extrai busca do elo e nomeia a fase laboratorio"
```

---

### Task 2: Payload puro do card da OS — `core/growthhs_os.py`

**Files:**
- Create: `backend/app/core/growthhs_os.py`
- Test: `backend/tests/test_growthhs_os.py`

**Interfaces:**
- `montar_card_os(ordem, cliente, device, board_id, hoje) -> dict` — **puro**, recebe tudo já carregado:
  - `source = "gestorhs.os"`, `external_id = str(ordem.id)`, `board_id`
  - `title = f"OS #{id} · {cliente} · {equipamento} {série}"` — truncado em 500
  - `description` — resultado do laboratório: situação da calibração, nº do certificado e próxima calibração; omitir as partes que não existirem (sem "None" no texto)
  - `due_date = (hoje + 2 dias)` em **`YYYY-MM-DDT00:00:00`**
  - `client` / `contact` via as funções de `growthhs_payload`
  - `devices = [device]` (a OS é de um aparelho só)
  - `business_info = {"origem": "os liberada do laboratorio", "os_id": ..., "tipo_servico": ...}`
- `hoje` entra como parâmetro (não `date.today()` dentro) para o teste ser determinístico.

- [ ] **Step 1: Escrever o teste que falha**

Cobrir: `source`/`external_id`/`board_id`; título com os quatro pedaços; título **truncado em 500** quando o nome do cliente é gigante; `due_date` exatamente `hoje+2` **com `T00:00:00`** (o bug de 422 que já nos pegou); descrição incluindo situação/certificado/próxima calibração quando existem e **sem "None"** quando não existem; `devices` com exatamente 1 item; `contact` ausente quando o cliente não tem contato; `business_info` com `os_id`.

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker exec gestorhs-backend pytest -q tests/test_growthhs_os.py`
Expected: FAIL.

- [ ] **Step 3: Implementar e ver passar**

Run: `docker exec gestorhs-backend pytest -q tests/test_growthhs_os.py`
Expected: PASS.

- [ ] **Step 4: Suíte completa + commit**

```bash
git add backend/app/core/growthhs_os.py backend/tests/test_growthhs_os.py
git commit -m "feat(growthhs): payload do card de OS liberada do laboratorio"
```

---

### Task 3: O gatilho — `agendar_card_os` + hook no `avancar`

**Files:**
- Modify: `backend/app/api/growthhs_cards.py`
- Modify: `backend/app/api/ordens.py`
- Test: `backend/tests/test_growthhs_gatilho_os.py`

**Interfaces:**
- `growthhs_cards.agendar_card_os(db, background_tasks, ordem) -> None`:
  - **no-op** se `not hsgrowth_client.integracao_ativa()`;
  - busca o `equipamento_cliente` da OS e o elo (`buscar_elo`), monta o `device`;
  - monta o card com `montar_card_os` usando `settings.HSGROWTH_BOARD_SERVICOS`;
  - `background_tasks.add_task(hsgrowth_client.enviar_card, card)` — a variante **best-effort** (nunca levanta).
  - Qualquer exceção **na montagem** também é engolida com log: montar o payload não pode derrubar o `avancar`.
- Em `app/api/ordens.py::avancar`, **depois** do `_agendar_espelhamento(...)` já existente (portanto após o commit):
  ```python
  if origem == wf.FASE_LABORATORIO:
      agendar_card_os(db, background_tasks, ordem)
  ```

- [ ] **Step 1: Escrever o teste que falha**

Testes de API (mesmo padrão de `test_ordens_avancar.py`), com `agendar_card_os` monkeypatchado para contar chamadas:
- avançar de **5→6** chama o gatilho **uma vez**;
- avançar de **4→5**, **6→10**, **10→7** e **7→8** **não** chama;
- **cancelar** não chama;
- com a integração **desligada** (envs vazias), `agendar_card_os` não agenda nada (contar `background_tasks.add_task`);
- **se o gatilho levantar exceção, a OS ainda avança** (status 200 e fase mudou) — a garantia mais importante desta task.

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker exec gestorhs-backend pytest -q tests/test_growthhs_gatilho_os.py`
Expected: FAIL.

- [ ] **Step 3: Implementar e ver passar**

Run: `docker exec gestorhs-backend pytest -q tests/test_growthhs_gatilho_os.py tests/test_ordens_avancar.py`
Expected: PASS — inclusive os testes já existentes de avançar OS, que não podem regredir.

- [ ] **Step 4: Suíte completa + commit**

Run: `docker exec gestorhs-backend pytest -q`

```bash
git add backend/app/api/growthhs_cards.py backend/app/api/ordens.py backend/tests/test_growthhs_gatilho_os.py
git commit -m "feat(growthhs): cria card de servicos quando a OS sai do laboratorio"
```

---

### Task 4: Changelog + verificação

**Files:**
- Modify: `frontend/src/app/changelog/data.ts`

- [ ] **Step 1: Bump de versão**

Primeira entrada de `CHANGELOG` (conferir a versão atual e subir o minor — a última era `v1.19.0`):
```ts
{
  versao: '1.20.0',
  data: '20/07/2026',
  itens: [
    { tipo: 'novidade', texto: 'Quando o laboratório conclui uma OS, o sistema agora cria automaticamente um card no funil de Serviços do GrowthHS, com os dados do cliente, o aparelho e o resultado da calibração — para o comercial dar seguimento sem ninguém precisar avisar. Se a integração estiver fora do ar, a OS avança normalmente.' },
  ],
},
```

- [ ] **Step 2: Verificação completa**

Run backend: `docker exec gestorhs-backend pytest -q`
Run frontend: `cd frontend && npm run lint && npx tsc -b --noEmit && npm run build && npm test`
Expected: tudo verde.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/changelog/data.ts
git commit -m "docs(changelog): v1.20.0 — card de servicos ao sair do laboratorio"
```

---

## Self-Review (feita)

- **Cobertura da spec (Etapa 2):** gatilho em 5→6 pós-commit via BackgroundTasks (T3), toda OS sem exceção de tipo (T3), board de Serviços + `gestorhs.os` + `str(ordem.id)` (T2), título/descrição com o resultado do laboratório (T2), `due_date` = liberação + 2 dias (T2), `devices[]` com a regra do elo (T1+T2), best-effort (T3). ✔
- **Lições já pagas neste projeto, aplicadas:** `due_date` como datetime completo (custou um 422 em produção); limites de tamanho do schema (título em 500; telefone já tratado na base); a ponte de atributos do elo (custaria `AttributeError` só no caso com elo); constante em vez de número mágico para a fase. ✔
- **DRY:** a busca do elo deixa de estar duplicada — o script da Etapa 1 passa a usar a mesma função (T1). ✔
- **Sem placeholders:** T1 traz código e testes completos; T2 e T3 enumeram cada caso de teste e cada ponto obrigatório, com comandos e resultados esperados. ✔
- **Consistência:** `buscar_elo` (T1) → `montar_card_os` (T2) → `agendar_card_os` (T3) → hook (T3). O `hoje` injetado em T2 mantém o teste determinístico. ✔
