# Caixa de módulo/phoebus sem integração — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Caixa que contenha módulo (catálogo 47) ou phoebus (catálogo 36) para de gerar card no TaskHS e no GrowthHS; todo o resto continua igual.

**Architecture:** Um predicado puro novo (`core/fluxo_modulo.py`) responde "essa OS/caixa é de módulo?". Os gates ficam no ponto de estrangulamento de cada integração — `api/espelhamento.py` (TaskHS, cobre os call sites de `caixas.py`, `ordens.py` e `notas_fiscais.py`) e `api/growthhs_cards.py` (GrowthHS) — mais um check próprio no script `reenviar_os_taskhs.py`, que fura a camada e chama o client direto. Cada bloqueio grava um log de integração `status="pulado"`, `motivo="caixa_de_modulo"`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, pytest (SQLite in-memory).

**Spec:** [docs/superpowers/specs/2026-07-30-caixa-modulo-sem-integracao-design.md](../specs/2026-07-30-caixa-modulo-sem-integracao-design.md)

## Global Constraints

- **Idioma do domínio é PT-BR.** Nomes de função, variável e mensagem em português, sem acentos em identificadores.
- **Ids de catálogo vêm de `settings`,** nunca hard-coded: `settings.EQUIPAMENTO_PHOEBUS_ID` (36) e `settings.EQUIPAMENTO_MODULO_ID` (47). O `49` (Módulo EBS) e o `37` (EBS) **não** entram.
- **Escopo do bloqueio:** só o card **de caixa/OS**. As cargas por cliente (`enviar_atrasados_growthhs`, `enviar_vencendo_growthhs`) e a integração **inbound** do GrowthHS não são tocadas.
- **Vale daqui pra frente.** Nenhum passo deste plano mexe em card que já está nos boards — eles congelam por consequência do gate.
- **Conjunto de OS avaliado:** ordens com `fase != 9`, com fallback para a lista completa quando toda a caixa está cancelada (é o critério que `_montar_payload_caixa` já usa).
- **Bloqueio é no-op silencioso:** nunca levanta exceção, nunca muda status HTTP, nunca aparece na tela.
- **Frontend não muda** (exceto o changelog na Task 6).
- **Commits:** Conventional Commits em português **sem acentos**, assunto de **uma linha**, sem corpo e **sem trailer de co-autor**.
- **Branch:** todo o trabalho vai em `feat/caixa-modulo-sem-integracao`. **Nunca `git add -A`** — sempre listar os caminhos (há outro agente trabalhando neste repo). Confira `git branch --show-current` antes de cada commit. **Não fazer push nem merge** sem o Erick pedir.
- **Baseline de testes:** esta máquina tem 5 falhas pré-existentes em `pytest -q`. Rode `pytest -q` **antes de começar** e guarde o número; só trate como regressão o que passar disso.
- **Ambiente:** `cd backend && source .venv/bin/activate` antes de rodar pytest.

---

### Task 0: Preparar branch e baseline

**Files:** nenhum.

- [ ] **Step 1: Criar a branch**

```bash
cd /home/ericks/github/GestorHS
git branch --show-current          # confirme que está em main antes de criar
git checkout -b feat/caixa-modulo-sem-integracao
```

- [ ] **Step 2: Registrar o baseline de testes**

```bash
cd backend && source .venv/bin/activate && pytest -q 2>&1 | tail -5
```

Anote a linha final (ex.: `5 failed, 812 passed`). Esse é o baseline; guarde o número de `failed` para comparar no fim.

---

### Task 1: Camada pura — predicado `fluxo_modulo`, `ordens_do_card` e id de catálogo na OS

**Files:**
- Create: `backend/app/core/fluxo_modulo.py`
- Modify: `backend/app/core/caixa.py` (novo `ordens_do_card`; ajustar o docstring do módulo)
- Modify: `backend/app/models/ordem.py` (junto das properties `equipamento_serie`/`equipamento_descricao`, ~linha 76-82)
- Test: `backend/tests/test_fluxo_modulo.py` (novo)
- Test: `backend/tests/test_caixa_core.py` (acrescenta casos de `ordens_do_card`)

**Interfaces:**
- Consumes: `settings.EQUIPAMENTO_PHOEBUS_ID`, `settings.EQUIPAMENTO_MODULO_ID` de `app.core.config`.
- Produces:
  - `app.core.fluxo_modulo.equipamentos_de_modulo() -> set[int]`
  - `app.core.fluxo_modulo.os_de_modulo(ordem) -> bool`
  - `app.core.fluxo_modulo.caixa_de_modulo(ordens) -> bool` (recebe um **iterável de ordens já filtrado**, não a caixa)
  - `app.core.caixa.ordens_do_card(caixa) -> list` — as OS que representam a caixa nas integrações (fase ≠ 9, fallback na lista completa). **Fonte única do critério**, consumida por `api/espelhamento.py` (Task 2) e `api/growthhs_cards.py` (Task 5); sem ela, o mesmo filtro apareceria duplicado nas duas integrações.
  - `Ordem.equipamento_catalogo -> int | None`

- [ ] **Step 1: Escrever o teste que falha**

Crie `backend/tests/test_fluxo_modulo.py`:

```python
from types import SimpleNamespace

from app.core import fluxo_modulo
from app.core.config import settings


def _os(catalogo):
    """OS fake: o predicado só olha `equipamento_catalogo`."""
    return SimpleNamespace(id=1, equipamento_catalogo=catalogo)


def test_os_de_modulo_reconhece_modulo_e_phoebus():
    assert fluxo_modulo.os_de_modulo(_os(settings.EQUIPAMENTO_MODULO_ID)) is True
    assert fluxo_modulo.os_de_modulo(_os(settings.EQUIPAMENTO_PHOEBUS_ID)) is True


def test_os_de_modulo_ignora_equipamento_comum():
    assert fluxo_modulo.os_de_modulo(_os(1)) is False


def test_os_de_modulo_sem_equipamento_nao_bloqueia():
    assert fluxo_modulo.os_de_modulo(_os(None)) is False


def test_os_de_modulo_modulo_ebs_nao_bloqueia():
    """Decisao de escopo: o Modulo de Calibracao para EBS (catalogo 49) e o EBS (37)
    NAO entram na regra. Este teste trava a decisao."""
    assert fluxo_modulo.os_de_modulo(_os(49)) is False
    assert fluxo_modulo.os_de_modulo(_os(37)) is False


def test_caixa_de_modulo_qualquer_os_contamina():
    ordens = [_os(1), _os(settings.EQUIPAMENTO_MODULO_ID), _os(1)]
    assert fluxo_modulo.caixa_de_modulo(ordens) is True


def test_caixa_de_modulo_so_comuns_nao_bloqueia():
    assert fluxo_modulo.caixa_de_modulo([_os(1), _os(2)]) is False


def test_caixa_de_modulo_lista_vazia_nao_bloqueia():
    assert fluxo_modulo.caixa_de_modulo([]) is False


def test_equipamentos_de_modulo_le_settings_na_chamada(monkeypatch):
    """O conjunto e' lido a cada chamada — um set de modulo congelaria o valor no
    import e furaria o monkeypatch (e qualquer override por env)."""
    monkeypatch.setattr(settings, "EQUIPAMENTO_MODULO_ID", 999)
    assert 999 in fluxo_modulo.equipamentos_de_modulo()
    assert fluxo_modulo.os_de_modulo(_os(999)) is True


def test_equipamento_catalogo_na_ordem(db_session, os_base):
    """A property e' a ponte entre a OS e o predicado: id de catalogo do equipamento."""
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"],
              equipamento_cliente=os_base["equipamento_cliente"],
              fase=4, situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    assert o.equipamento_catalogo == os_base["equipamento"]


def test_equipamento_catalogo_none_sem_equipamento(db_session, os_base):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=None, fase=4, situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    assert o.equipamento_catalogo is None
```

E acrescente ao fim de `backend/tests/test_caixa_core.py`:

```python
def test_ordens_do_card_exclui_canceladas():
    from types import SimpleNamespace
    from app.core.caixa import ordens_do_card
    ativa, cancelada = SimpleNamespace(id=1, fase=6), SimpleNamespace(id=2, fase=9)
    cx = SimpleNamespace(ordens=[ativa, cancelada])
    assert ordens_do_card(cx) == [ativa]


def test_ordens_do_card_caixa_toda_cancelada_cai_na_lista_completa():
    """Sem o fallback, uma caixa 100% cancelada devolveria lista vazia e o card
    ficaria sem nenhuma OS."""
    from types import SimpleNamespace
    from app.core.caixa import ordens_do_card
    a, b = SimpleNamespace(id=1, fase=9), SimpleNamespace(id=2, fase=9)
    cx = SimpleNamespace(ordens=[a, b])
    assert ordens_do_card(cx) == [a, b]


def test_ordens_do_card_caixa_vazia():
    from types import SimpleNamespace
    from app.core.caixa import ordens_do_card
    assert ordens_do_card(SimpleNamespace(ordens=[])) == []
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_fluxo_modulo.py tests/test_caixa_core.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.fluxo_modulo'` nos primeiros e `ImportError: cannot import name 'ordens_do_card'` nos três novos de `test_caixa_core.py`.

- [ ] **Step 3: Criar o módulo puro**

Crie `backend/app/core/fluxo_modulo.py`:

```python
"""Modulo e Phoebus seguem um fluxo de servico proprio.

Caixa que contenha um deles NAO vira card no TaskHS nem no GrowthHS. Este modulo
responde a pergunta e nada mais — logica pura, sem I/O, para ser consumida pelos
dois pontos de estrangulamento (`api/espelhamento.py` e `api/growthhs_cards.py`).

Fora do escopo de proposito: as cargas por CLIENTE do GrowthHS (atrasados,
vencendo) continuam mandando modulo, porque o modulo e' o item que de fato
calibra e o elo com o Phoebus foi construido para aparecer nesses payloads.
"""

from app.core.config import settings


def equipamentos_de_modulo() -> set[int]:
    """Ids de catalogo que bloqueiam o card: Phoebus (36) e Modulo PHOEBUS (47).

    Lido a cada chamada em vez de num set de modulo: uma constante de modulo
    congelaria o valor no momento do import, furando override por env e
    monkeypatch em teste. O Modulo para EBS (49) e o EBS (37) NAO entram.
    """
    return {settings.EQUIPAMENTO_PHOEBUS_ID, settings.EQUIPAMENTO_MODULO_ID}


def os_de_modulo(ordem) -> bool:
    """True se o equipamento da OS e' modulo ou phoebus.

    `getattr` com default protege os fakes (SimpleNamespace) que os testes
    das integracoes montam sem a property; OS real sempre tem. OS sem
    equipamento vinculado devolve None, que nao esta no conjunto -> False.
    """
    return getattr(ordem, "equipamento_catalogo", None) in equipamentos_de_modulo()


def caixa_de_modulo(ordens) -> bool:
    """True se QUALQUER OS da lista e' de modulo/phoebus (caixa mista bloqueia).

    Recebe a lista de ordens JA FILTRADA pelo chamador (nao a caixa), para que o
    critério de "quais OS contam" fique visivel no ponto de uso.
    """
    return any(os_de_modulo(o) for o in ordens)
```

- [ ] **Step 4: Adicionar `ordens_do_card` em `core/caixa.py`**

Em `backend/app/core/caixa.py`, troque o docstring do módulo (que hoje diz só "composição de clientes") e adicione a função ao fim do arquivo:

```python
"""Lógica pura de composição de uma caixa: clientes e as ordens que a representam
nas integrações (sem I/O)."""
```

```python
def ordens_do_card(caixa) -> list:
    """As OS que representam a caixa nas integracoes (TaskHS e GrowthHS).

    Exclui canceladas (fase 9), com fallback na lista completa quando a caixa toda
    foi cancelada — senao o card ficaria sem nenhuma OS. Fonte unica do criterio:
    o gate de modulo e a montagem do payload precisam concordar, e duplicar o
    filtro nas duas integracoes seria pedir para elas divergirem.
    """
    return [o for o in caixa.ordens if o.fase not in (9,)] or list(caixa.ordens)
```

- [ ] **Step 5: Adicionar a property na `Ordem`**

Em `backend/app/models/ordem.py`, logo depois da property `equipamento_descricao`:

```python
    @property
    def equipamento_catalogo(self):
        """Id de catalogo do equipamento da OS (36 = Phoebus, 47 = Modulo PHOEBUS).
        Ponte entre a OS e `core.fluxo_modulo`."""
        return self.equipamento_rel.equipamento if self.equipamento_rel else None
```

- [ ] **Step 6: Rodar e confirmar que passa**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_fluxo_modulo.py tests/test_caixa_core.py -q`
Expected: PASS (10 novos em `test_fluxo_modulo.py` + 3 novos em `test_caixa_core.py`, mais os que já existiam lá)

- [ ] **Step 7: Commit**

```bash
cd /home/ericks/github/GestorHS
git branch --show-current   # feat/caixa-modulo-sem-integracao
git add backend/app/core/fluxo_modulo.py backend/app/core/caixa.py backend/app/models/ordem.py backend/tests/test_fluxo_modulo.py backend/tests/test_caixa_core.py
git commit -m "feat(integracoes): predicado de caixa de modulo/phoebus"
```

---

### Task 2: Gate da CAIXA no TaskHS

**Files:**
- Modify: `backend/app/api/espelhamento.py` (gate em `agendar_espelhamento_caixa`; `_montar_payload_caixa` passa a usar `ordens_do_card`)
- Test: `backend/tests/test_taskhs_bloqueio_modulo.py` (novo)

**Interfaces:**
- Consumes: `fluxo_modulo.caixa_de_modulo(ordens)` e `app.core.caixa.ordens_do_card(caixa)`, ambos da Task 1.
- Produces: nada consumido por outras tasks.

- [ ] **Step 1: Escrever o teste que falha**

Crie `backend/tests/test_taskhs_bloqueio_modulo.py`:

```python
"""Caixa com modulo/phoebus nao vira card no TaskHS — nem ao avancar, nem ao cancelar."""
import pytest

from app.core.config import settings
from app.integrations import taskhs_client


@pytest.fixture()
def captura(monkeypatch):
    """Liga a integracao e captura os payloads agendados (sem HTTP real)."""
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "http://taskhs.test/api")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "k-123")
    chamadas = []
    monkeypatch.setattr(taskhs_client, "enviar_card", lambda payload: chamadas.append(payload))
    return chamadas


def _caixa_com(db, *, catalogo_id, fase=4, desfecho="pendente", fase_os=None):
    """Caixa na fase informada com 1 OS de um equipamento do catalogo `catalogo_id`.

    O id do catalogo e' explicito (nao autoincrement) porque a regra depende dele.
    """
    from app.models import Caixa, Cliente, Equipamento, EquipamentoCliente, Ordem
    cli = Cliente(nome="Cliente Bloqueio")
    eq = Equipamento(id=catalogo_id, descricao=f"Equipamento {catalogo_id}")
    db.add_all([cli, eq]); db.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie=f"SER-{catalogo_id}")
    cx = Caixa(obs="Caixa bloqueio", fase=fase)
    db.add_all([ec, cx]); db.flush()
    o = Ordem(cliente=cli.id, equipamento_cliente=ec.id,
              fase=fase_os if fase_os is not None else fase,
              situacao="E", caixa=cx.id, desfecho_lab=desfecho)
    db.add(o); db.commit(); db.refresh(cx)
    return cx.id, o.id


def test_avancar_caixa_de_modulo_nao_espelha(client_exp, db_session, captura):
    cx_id, _ = _caixa_com(db_session, catalogo_id=settings.EQUIPAMENTO_MODULO_ID)
    r = client_exp.post(f"/caixas/{cx_id}/avancar", json={})
    assert r.status_code == 200
    assert captura == []


def test_avancar_caixa_de_phoebus_nao_espelha(client_exp, db_session, captura):
    cx_id, _ = _caixa_com(db_session, catalogo_id=settings.EQUIPAMENTO_PHOEBUS_ID)
    r = client_exp.post(f"/caixas/{cx_id}/avancar", json={})
    assert r.status_code == 200
    assert captura == []


def test_avancar_caixa_comum_continua_espelhando(client_exp, db_session, captura):
    """Controle positivo: sem o gate mordendo quem nao e' modulo, o teste acima
    passaria mesmo com a integracao quebrada."""
    cx_id, _ = _caixa_com(db_session, catalogo_id=1)
    r = client_exp.post(f"/caixas/{cx_id}/avancar", json={})
    assert r.status_code == 200
    assert len(captura) == 1
    assert captura[0]["external_id"] == str(cx_id)


def test_avancar_caixa_mista_nao_espelha(client_exp, db_session, captura):
    """Caixa mista: uma OS de modulo contamina a caixa inteira."""
    from app.models import Cliente, Equipamento, EquipamentoCliente, Ordem
    cx_id, _ = _caixa_com(db_session, catalogo_id=1)
    cli = db_session.query(Cliente).first()
    eq_mod = Equipamento(id=settings.EQUIPAMENTO_MODULO_ID, descricao="Modulo")
    db_session.add(eq_mod); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq_mod.id, serie="SER-MOD")
    db_session.add(ec); db_session.flush()
    db_session.add(Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=4,
                         situacao="E", caixa=cx_id))
    db_session.commit()
    r = client_exp.post(f"/caixas/{cx_id}/avancar", json={})
    assert r.status_code == 200
    assert captura == []


def test_caixa_cujo_modulo_esta_cancelado_volta_a_espelhar(client_exp, db_session, captura):
    """OS de modulo CANCELADA (fase 9) nao conta — a caixa volta a gerar card."""
    from app.models import Cliente, Equipamento, EquipamentoCliente, Ordem
    cx_id, _ = _caixa_com(db_session, catalogo_id=1)
    cli = db_session.query(Cliente).first()
    eq_mod = Equipamento(id=settings.EQUIPAMENTO_MODULO_ID, descricao="Modulo")
    db_session.add(eq_mod); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq_mod.id, serie="SER-MOD")
    db_session.add(ec); db_session.flush()
    db_session.add(Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=9,
                         situacao="C", caixa=cx_id))
    db_session.commit()
    r = client_exp.post(f"/caixas/{cx_id}/avancar", json={})
    assert r.status_code == 200
    assert len(captura) == 1


def test_cancelar_caixa_de_modulo_nao_arquiva_card(client_exp, db_session, captura):
    cx_id, _ = _caixa_com(db_session, catalogo_id=settings.EQUIPAMENTO_MODULO_ID)
    r = client_exp.post(f"/caixas/{cx_id}/cancelar", json={"motivo": "teste"})
    assert r.status_code == 200
    assert captura == []


def test_bloqueio_registra_log_pulado(client_exp, db_session, captura, monkeypatch):
    from app.api import espelhamento
    logs = []
    monkeypatch.setattr(espelhamento, "registrar_log_integracao",
                        lambda **kw: logs.append(kw))
    cx_id, _ = _caixa_com(db_session, catalogo_id=settings.EQUIPAMENTO_MODULO_ID)
    client_exp.post(f"/caixas/{cx_id}/avancar", json={})
    assert logs and logs[0]["status"] == "pulado"
    assert logs[0]["motivo"] == "caixa_de_modulo"
    assert logs[0]["integracao"] == "taskhs"
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_taskhs_bloqueio_modulo.py -q`
Expected: FAIL — os testes de bloqueio falham porque o card ainda é enviado (`captura` tem 1 payload); o de log falha com `AttributeError` em `registrar_log_integracao` (ainda não importado no módulo).

- [ ] **Step 3: Aplicar o gate e usar `ordens_do_card`**

Em `backend/app/api/espelhamento.py`, o import de `app.core.caixa` já existe (`from app.core.caixa import principal_valido`) — acrescente a função nova nele e adicione os outros dois imports:

```python
from app.core import fluxo_modulo
from app.core.caixa import ordens_do_card, principal_valido
from app.integrations.log_integracao import registrar_log_integracao
```

Em `_montar_payload_caixa`, troque a primeira linha do corpo que monta `ordens`:

```python
    ordens = ordens_do_card(caixa)
```

(era `ordens = [o for o in caixa.ordens if o.fase not in (9,)] or list(caixa.ordens)`)

Em `agendar_espelhamento_caixa`, depois do gate de `list_id`/integração ativa:

```python
def agendar_espelhamento_caixa(db, background_tasks, caixa, *, origem=None, arquivado=False):
    """Agenda o upsert no TaskHS do card da CAIXA (async, best-effort). No-op se
    sem list_id (fase sem mapeamento), integração desligada ou caixa de módulo."""
    fase = origem if origem is not None else caixa.fase
    list_id = taskhs.list_id_da_fase(fase) if fase is not None else None
    if list_id is None or not taskhs_client.integracao_ativa():
        return
    ordens = ordens_do_card(caixa)
    if fluxo_modulo.caixa_de_modulo(ordens):
        # Módulo/phoebus tem fluxo próprio, fora do board. Bloquear ANTES de montar
        # o payload também congela card antigo: criar, mover e arquivar são o mesmo
        # caminho, então nada mexe no que já foi enviado.
        registrar_log_integracao(integracao="taskhs", status="pulado",
                                 motivo="caixa_de_modulo",
                                 referencia_os=ordens[0].id if ordens else None)
        return
    payload = _montar_payload_caixa(db, caixa, list_id=list_id, arquivado=arquivado)
    background_tasks.add_task(taskhs_client.enviar_card, payload)
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_taskhs_bloqueio_modulo.py -q`
Expected: PASS (7 testes)

- [ ] **Step 5: Confirmar que não quebrou o espelhamento existente**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_taskhs_caixa.py tests/test_ordens_taskhs.py tests/test_caixa_avancar.py tests/test_caixa_multicliente.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd /home/ericks/github/GestorHS
git branch --show-current
git add backend/app/api/espelhamento.py backend/tests/test_taskhs_bloqueio_modulo.py
git commit -m "feat(integracoes): caixa de modulo nao gera card no taskhs"
```

---

### Task 3: Gate por OS no TaskHS + backfill contando pulados

**Files:**
- Modify: `backend/app/api/espelhamento.py` (`agendar_espelhamento`, `espelhar_os_sync`)
- Modify: `backend/app/scripts/sincronizar_taskhs.py` (conta pulados)
- Modify: `backend/tests/test_sincronizar_taskhs.py` (o stub existente precisa devolver `True`)
- Test: `backend/tests/test_taskhs_bloqueio_modulo.py` (acrescenta casos)

**Interfaces:**
- Consumes: `fluxo_modulo.os_de_modulo(ordem)` da Task 1.
- Produces: `espelhamento.espelhar_os_sync(db, ordem, *, list_id, arquivado) -> bool` — `True` enviado, `False` pulado por ser módulo. Consumido por `scripts/sincronizar_taskhs.sincronizar`.

- [ ] **Step 1: Escrever os testes que falham**

Acrescente ao fim de `backend/tests/test_taskhs_bloqueio_modulo.py`:

```python
def test_upload_nota_fiscal_em_os_de_modulo_nao_espelha(client, usuario_financeiro,
                                                       fases_seed, db_session,
                                                       upload_tmp, captura):
    """O caminho por OS (upload de NF) tambem e' gateado — sem porta dos fundos."""
    import io
    cx_id, os_id = _caixa_com(db_session, catalogo_id=settings.EQUIPAMENTO_MODULO_ID,
                              fase=10, fase_os=10)
    tok = client.post("/auth/login",
                      json={"email": "financeiro@hs.com", "senha": "senha123"}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    r = client.post(f"/ordens/{os_id}/nota-fiscal",
                    files={"file": ("nf.pdf", io.BytesIO(b"%PDF-1.4 x"), "application/pdf")},
                    data={"numero": "123"}, headers=h)
    assert r.status_code == 200
    assert captura == []


def test_espelhar_os_sync_devolve_false_para_modulo(db_session, captura, monkeypatch):
    """O backfill precisa saber que pulou, senao relata como enviada uma OS que
    nunca saiu."""
    from app.api import espelhamento
    from app.integrations import taskhs_client as tc
    enviados = []
    monkeypatch.setattr(tc, "enviar_card_sync", lambda p: enviados.append(p))
    _, os_mod = _caixa_com(db_session, catalogo_id=settings.EQUIPAMENTO_MODULO_ID)
    from app.models import Ordem
    ordem = db_session.get(Ordem, os_mod)
    assert espelhamento.espelhar_os_sync(db_session, ordem, list_id=196,
                                         arquivado=False) is False
    assert enviados == []


def test_espelhar_os_sync_devolve_true_para_comum(db_session, captura, monkeypatch):
    from app.api import espelhamento
    from app.integrations import taskhs_client as tc
    enviados = []
    monkeypatch.setattr(tc, "enviar_card_sync", lambda p: enviados.append(p))
    _, os_comum = _caixa_com(db_session, catalogo_id=1)
    from app.models import Ordem
    ordem = db_session.get(Ordem, os_comum)
    assert espelhamento.espelhar_os_sync(db_session, ordem, list_id=196,
                                         arquivado=False) is True
    assert len(enviados) == 1
```

E crie o teste do backfill em `backend/tests/test_sincronizar_taskhs.py` (acrescente ao fim):

```python
def test_sincronizar_nao_conta_os_de_modulo_como_enviada(db_session, fases_seed, monkeypatch):
    """OS de modulo e' pulada; o relatorio nao pode contar como enviada."""
    from app.api import espelhamento
    from app.models import Cliente, Equipamento, EquipamentoCliente, Ordem
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "http://t/api")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "k")
    cli = Cliente(nome="C")
    eq_mod = Equipamento(id=settings.EQUIPAMENTO_MODULO_ID, descricao="Modulo")
    eq_com = Equipamento(id=1, descricao="Bafometro")
    db_session.add_all([cli, eq_mod, eq_com]); db_session.flush()
    ec_mod = EquipamentoCliente(cliente=cli.id, equipamento=eq_mod.id, serie="M1")
    ec_com = EquipamentoCliente(cliente=cli.id, equipamento=eq_com.id, serie="B1")
    db_session.add_all([ec_mod, ec_com]); db_session.flush()
    db_session.add_all([
        Ordem(cliente=cli.id, equipamento_cliente=ec_mod.id, fase=4, situacao="E"),
        Ordem(cliente=cli.id, equipamento_cliente=ec_com.id, fase=4, situacao="E"),
    ])
    db_session.commit()
    enviados = []
    monkeypatch.setattr("app.integrations.taskhs_client.enviar_card_sync",
                        lambda p: enviados.append(p))
    enviadas, total = sincronizar_taskhs.sincronizar(db_session)
    assert total == 2
    assert enviadas == 1
    assert len(enviados) == 1
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_taskhs_bloqueio_modulo.py tests/test_sincronizar_taskhs.py -q`
Expected: FAIL — `espelhar_os_sync` devolve `None` (não `False`/`True`), o upload de NF ainda espelha, e o backfill conta 2 enviadas.

- [ ] **Step 3: Aplicar os gates por OS**

Em `backend/app/api/espelhamento.py`:

```python
def agendar_espelhamento(db, background_tasks, ordem, *, list_id, arquivado):
    """Agenda o upsert no TaskHS (async, best-effort). No-op se sem list_id,
    integração desligada ou OS de módulo/phoebus."""
    if list_id is None or not taskhs_client.integracao_ativa():
        return
    if fluxo_modulo.os_de_modulo(ordem):
        registrar_log_integracao(integracao="taskhs", status="pulado",
                                 motivo="caixa_de_modulo", referencia_os=ordem.id)
        return
    payload = _montar_payload_os(db, ordem, list_id=list_id, arquivado=arquivado)
    background_tasks.add_task(taskhs_client.enviar_card, payload)


def espelhar_os_sync(db, ordem, *, list_id, arquivado) -> bool:
    """Monta o payload e envia sincronamente, PROPAGANDO erro (uso no backfill).
    Devolve True se enviou, False se pulou por ser módulo/phoebus — o backfill
    relata o número real de OS enviadas."""
    if fluxo_modulo.os_de_modulo(ordem):
        registrar_log_integracao(integracao="taskhs", status="pulado",
                                 motivo="caixa_de_modulo", referencia_os=ordem.id)
        return False
    payload = _montar_payload_os(db, ordem, list_id=list_id, arquivado=arquivado)
    taskhs_client.enviar_card_sync(payload)
    return True
```

- [ ] **Step 4: Fazer o backfill contar o retorno**

Em `backend/app/scripts/sincronizar_taskhs.py`, no corpo do laço, troque o bloco `try`:

```python
        try:
            if espelhamento.espelhar_os_sync(db, o, list_id=list_id, arquivado=False):
                enviadas += 1
                print(f"OK   OS #{o.id} -> lista {list_id}")
            else:
                print(f"PULA OS #{o.id}: modulo/phoebus tem fluxo proprio")
        except Exception as e:  # noqa: BLE001 — relatório, segue para a próxima
            print(f"ERRO OS #{o.id}: {e}")
```

- [ ] **Step 5: Ajustar o stub do teste existente**

Em `backend/tests/test_sincronizar_taskhs.py`, o stub de `test_sincronizar_envia_so_fases_4_a_8` devolve `None`, que agora é lido como "pulou". Faça devolver `True`:

```python
    monkeypatch.setattr(espelhamento, "espelhar_os_sync",
                        lambda db, ordem, *, list_id, arquivado=False: (
                            enviados.append((ordem.fase, list_id)) or True))
```

- [ ] **Step 6: Rodar e confirmar que passa**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_taskhs_bloqueio_modulo.py tests/test_sincronizar_taskhs.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
cd /home/ericks/github/GestorHS
git branch --show-current
git add backend/app/api/espelhamento.py backend/app/scripts/sincronizar_taskhs.py backend/tests/test_taskhs_bloqueio_modulo.py backend/tests/test_sincronizar_taskhs.py
git commit -m "feat(integracoes): gate de modulo no caminho por os do taskhs"
```

---

### Task 4: Gate no script `reenviar_os_taskhs`

**Files:**
- Modify: `backend/app/scripts/reenviar_os_taskhs.py`
- Test: `backend/tests/test_reenviar_os_taskhs.py` (novo)

**Interfaces:**
- Consumes: `fluxo_modulo.os_de_modulo(ordem)` da Task 1.
- Produces: nada consumido por outras tasks.

**Por que este script precisa de check próprio:** ele monta o payload com `espelhamento._montar_payload_os` e chama `taskhs_client.enviar_card_sync` **direto**, sem passar por `espelhar_os_sync` — então o gate da Task 3 não o cobre.

- [ ] **Step 1: Escrever o teste que falha**

Crie `backend/tests/test_reenviar_os_taskhs.py`:

```python
"""O reenvio manual tambem respeita o bloqueio de modulo/phoebus."""
from app.core.config import settings
from app.scripts import reenviar_os_taskhs


def _os_com(db, catalogo_id, fase=4):
    from app.models import Cliente, Equipamento, EquipamentoCliente, Ordem
    cli = Cliente(nome="C")
    eq = Equipamento(id=catalogo_id, descricao=f"Eq {catalogo_id}")
    db.add_all([cli, eq]); db.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie=f"S{catalogo_id}")
    db.add(ec); db.flush()
    o = Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=fase, situacao="E")
    db.add(o); db.commit(); db.refresh(o)
    return o.id


def test_reenviar_pula_os_de_modulo(db_session, fases_seed, monkeypatch, capsys):
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "http://t/api")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "k")
    enviados = []
    monkeypatch.setattr("app.integrations.taskhs_client.enviar_card_sync",
                        lambda p: enviados.append(p))
    os_id = _os_com(db_session, settings.EQUIPAMENTO_MODULO_ID)
    ok, total = reenviar_os_taskhs.reenviar(db_session, [os_id], enviar=True)
    assert enviados == []
    assert ok == 0
    assert "PULA" in capsys.readouterr().out


def test_reenviar_envia_os_comum(db_session, fases_seed, monkeypatch):
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "http://t/api")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "k")
    enviados = []
    monkeypatch.setattr("app.integrations.taskhs_client.enviar_card_sync",
                        lambda p: enviados.append(p))
    os_id = _os_com(db_session, 1)
    ok, total = reenviar_os_taskhs.reenviar(db_session, [os_id], enviar=True)
    assert len(enviados) == 1
    assert ok == 1
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_reenviar_os_taskhs.py -q`
Expected: FAIL — a OS de módulo é enviada (`enviados` tem 1 payload, `ok == 1`).

- [ ] **Step 3: Aplicar o check**

Em `backend/app/scripts/reenviar_os_taskhs.py`, importe o predicado no topo:

```python
from app.core import fluxo_modulo
```

E no laço, logo depois do check de `list_id` (que imprime `PULA ... nao tem lista`):

```python
        if fluxo_modulo.os_de_modulo(ordem):
            print(f"PULA OS #{oid}: modulo/phoebus tem fluxo proprio, nao vai pro board")
            continue
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_reenviar_os_taskhs.py -q`
Expected: PASS (2 testes)

- [ ] **Step 5: Commit**

```bash
cd /home/ericks/github/GestorHS
git branch --show-current
git add backend/app/scripts/reenviar_os_taskhs.py backend/tests/test_reenviar_os_taskhs.py
git commit -m "feat(integracoes): reenvio manual pula os de modulo"
```

---

### Task 5: Gate no GrowthHS

**Files:**
- Modify: `backend/app/api/growthhs_cards.py` (`agendar_card_caixa`, `agendar_card_os`)
- Test: `backend/tests/test_growthhs_bloqueio_modulo.py` (novo)

**Interfaces:**
- Consumes: `fluxo_modulo.os_de_modulo`, `fluxo_modulo.caixa_de_modulo` da Task 1.
- Produces: nada consumido por outras tasks.

**Observação:** `agendar_card_os` não tem call site em produção (só testes o exercitam), mas é gateado junto para não voltar já furado. `growthhs_cards.py` já importa `registrar_log_integracao`.

- [ ] **Step 1: Escrever o teste que falha**

Crie `backend/tests/test_growthhs_bloqueio_modulo.py`:

```python
"""Caixa com modulo/phoebus nao vira card de caixa no GrowthHS.

Fora do escopo (e NAO testado aqui como bloqueio): as cargas por CLIENTE
(atrasados/vencendo) continuam mandando modulo — ver a spec.
"""
from types import SimpleNamespace

import pytest

from app.api import growthhs_cards
from app.core.config import settings
from app.integrations import hsgrowth_client


class _BG:
    def __init__(self):
        self.tarefas = []

    def add_task(self, fn, *a, **k):
        self.tarefas.append((fn, a, k))


@pytest.fixture()
def growth_ligado(monkeypatch):
    monkeypatch.setattr(settings, "HSGROWTH_BASE_URL", "https://growth.test")
    monkeypatch.setattr(settings, "HSGROWTH_API_KEY", "k")


def _caixa_com(db, catalogo_id):
    from app.models import Caixa, Cliente, Equipamento, EquipamentoCliente, Ordem
    cli = Cliente(nome="Cliente Growth", cgc="11222333000144")
    eq = Equipamento(id=catalogo_id, descricao=f"Eq {catalogo_id}")
    db.add_all([cli, eq]); db.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie=f"S{catalogo_id}")
    cx = Caixa(obs="Caixa growth", fase=6)
    db.add_all([ec, cx]); db.flush()
    o = Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=6, situacao="E",
              caixa=cx.id, desfecho_lab="liberado")
    db.add(o); db.commit(); db.refresh(cx)
    return cx


def test_card_caixa_de_modulo_nao_agenda(db_session, growth_ligado, monkeypatch):
    enviados = []
    monkeypatch.setattr(hsgrowth_client, "enviar_card", lambda c: enviados.append(c))
    cx = _caixa_com(db_session, settings.EQUIPAMENTO_MODULO_ID)
    bg = _BG()
    growthhs_cards.agendar_card_caixa(db_session, bg, cx)
    assert bg.tarefas == []
    assert enviados == []


def test_card_caixa_de_phoebus_nao_agenda(db_session, growth_ligado, monkeypatch):
    monkeypatch.setattr(hsgrowth_client, "enviar_card", lambda c: None)
    cx = _caixa_com(db_session, settings.EQUIPAMENTO_PHOEBUS_ID)
    bg = _BG()
    growthhs_cards.agendar_card_caixa(db_session, bg, cx)
    assert bg.tarefas == []


def test_card_caixa_comum_continua_agendando(db_session, growth_ligado, monkeypatch):
    """Controle positivo."""
    monkeypatch.setattr(hsgrowth_client, "enviar_card", lambda c: None)
    cx = _caixa_com(db_session, 1)
    bg = _BG()
    growthhs_cards.agendar_card_caixa(db_session, bg, cx)
    assert len(bg.tarefas) == 1


def test_bloqueio_de_caixa_registra_log(db_session, growth_ligado, monkeypatch):
    logs = []
    monkeypatch.setattr(growthhs_cards, "registrar_log_integracao",
                        lambda **kw: logs.append(kw))
    cx = _caixa_com(db_session, settings.EQUIPAMENTO_MODULO_ID)
    growthhs_cards.agendar_card_caixa(db_session, _BG(), cx)
    assert logs and logs[0]["status"] == "pulado"
    assert logs[0]["motivo"] == "caixa_de_modulo"
    assert logs[0]["integracao"] == "growthhs"


def test_card_os_de_modulo_nao_agenda(growth_ligado, monkeypatch):
    """`agendar_card_os` nao tem call site em producao hoje, mas e' gateado para
    nao voltar furado."""
    logs = []
    monkeypatch.setattr(growthhs_cards, "registrar_log_integracao",
                        lambda **kw: logs.append(kw))
    ordem = SimpleNamespace(
        id=77,
        equipamento_rel=SimpleNamespace(equipamento=settings.EQUIPAMENTO_MODULO_ID),
        equipamento_catalogo=settings.EQUIPAMENTO_MODULO_ID,
    )
    bg = _BG()
    growthhs_cards.agendar_card_os(db=None, background_tasks=bg, ordem=ordem)
    assert bg.tarefas == []
    assert logs and logs[0]["motivo"] == "caixa_de_modulo"
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_growthhs_bloqueio_modulo.py -q`
Expected: FAIL — os cards de módulo continuam sendo agendados (`bg.tarefas` tem 1 item).

- [ ] **Step 3: Aplicar os gates**

Em `backend/app/api/growthhs_cards.py`, o import de `app.core.caixa` já existe (`from app.core.caixa import principal_valido`) — acrescente a função nova nele e importe o predicado:

```python
from app.core import fluxo_modulo
from app.core.caixa import ordens_do_card, principal_valido
```

Em `agendar_card_os`, logo depois do check de integração ativa e **antes** do check de `equipamento_rel is None`:

```python
    if fluxo_modulo.os_de_modulo(ordem):
        registrar_log_integracao(integracao="growthhs", status="pulado",
                                 motivo="caixa_de_modulo", referencia_os=ordem.id)
        return
```

Em `agendar_card_caixa`, logo depois do check de integração ativa:

```python
def agendar_card_caixa(db, background_tasks, caixa) -> None:
    """Agenda o card de CAIXA liberada do laboratorio no board Servicos do GrowthHS.

    Espelho de `agendar_card_os`, mas com um device por OS da caixa (equipamentos
    sem vinculo sao pulados individualmente, sem no-op da caixa inteira). No-op
    se a integracao estiver desligada, se a caixa for de modulo/phoebus (fluxo
    proprio, fora do board) ou se nenhuma OS da caixa tiver equipamento.
    """
    if not hsgrowth_client.integracao_ativa():
        return
    do_card = ordens_do_card(caixa)
    if fluxo_modulo.caixa_de_modulo(do_card):
        registrar_log_integracao(integracao="growthhs", status="pulado",
                                 motivo="caixa_de_modulo",
                                 referencia_os=do_card[0].id if do_card else None)
        return
    ordens = [o for o in caixa.ordens if o.equipamento_rel is not None]
    ...
```

O resto do corpo fica igual.

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_growthhs_bloqueio_modulo.py -q`
Expected: PASS (5 testes)

- [ ] **Step 5: Confirmar que o GrowthHS existente não quebrou**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_growthhs_gatilho_os.py tests/test_growthhs_cards_log.py tests/test_growthhs_caixa.py tests/test_enviar_atrasados_growthhs.py tests/test_enviar_vencendo_growthhs.py -q`
Expected: PASS — em especial as duas últimas, que provam que as cargas por cliente continuam mandando módulo.

- [ ] **Step 6: Commit**

```bash
cd /home/ericks/github/GestorHS
git branch --show-current
git add backend/app/api/growthhs_cards.py backend/tests/test_growthhs_bloqueio_modulo.py
git commit -m "feat(integracoes): caixa de modulo nao gera card no growthhs"
```

---

### Task 6: Verificação completa e changelog

**Files:**
- Modify: `frontend/src/app/changelog/data.ts` (nova entrada no topo)

- [ ] **Step 1: Rodar a suíte inteira do backend**

Run: `cd backend && source .venv/bin/activate && pytest -q 2>&1 | tail -5`
Expected: mesmo número de `failed` do baseline da Task 0 (5 falhas pré-existentes nesta máquina), com os novos testes passando. Qualquer falha **nova** é regressão — pare e investigue antes de seguir.

- [ ] **Step 2: Conferir que nenhum número de catálogo ficou solto**

Run: `cd backend && grep -rn "\b36\b\|\b47\b" app/core/fluxo_modulo.py app/api/espelhamento.py app/api/growthhs_cards.py app/scripts/reenviar_os_taskhs.py`
Expected: nenhuma linha de código com `36`/`47` literal (só comentários, se houver). Os ids vêm de `settings`.

- [ ] **Step 3: Adicionar a entrada no changelog**

Em `frontend/src/app/changelog/data.ts`, como **primeira** entrada de `CHANGELOG` (antes da `1.32.0`):

```ts
  {
    versao: '1.33.0',
    data: '30/07/2026',
    itens: [
      { tipo: 'melhoria', texto: 'Caixa que contém módulo ou Phoebus não gera mais card no TaskHS nem no GrowthHS — esses equipamentos seguem um fluxo próprio, fora dos boards. Vale para os próximos envios; os cards que já estavam nos boards continuam onde estão.' },
    ],
  },
```

- [ ] **Step 4: Verificar o frontend**

Run: `cd frontend && npm run lint && npx tsc -b --noEmit && npm run build`
Expected: sem erro.

- [ ] **Step 5: Commit**

```bash
cd /home/ericks/github/GestorHS
git branch --show-current
git add frontend/src/app/changelog/data.ts
git commit -m "docs(changelog): v1.33.0 — caixa de modulo fora do taskhs e do growthhs"
```

- [ ] **Step 6: Resumo para o Erick**

Não faça push nem merge. Reporte: número de falhas antes/depois (`pytest -q`), lista de arquivos tocados, e os 5 pontos gateados (3 em `espelhamento.py`, 2 em `growthhs_cards.py`, 1 no script `reenviar_os_taskhs.py` — 6 no total contando o script).

---

## Notas de execução

- **Ordem importa.** Task 1 produz a camada pura (`fluxo_modulo` + `ordens_do_card`) que todas as outras consomem. Tasks 2, 4 e 5 são independentes entre si depois da 1; a Task 3 depende da 2, porque as duas mexem em `espelhamento.py` (a 2 adiciona os imports que a 3 usa).
- **Se um teste de endpoint falhar por autorização**, confira a função exigida pela fase: fase 4 → Expedição (`client_exp`), fase 5 → Laboratório (`client_lab`). O fixture `usuario_financeiro` cobre o upload de NF.
- **`Equipamento(id=...)` explícito** nos testes é intencional: a regra depende do id de catálogo, e o autoincrement do SQLite não dá 36/47.
