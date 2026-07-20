# GrowthHS Etapa 3 — Job diário dos 50 dias · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Um script diário que cria, no board de Cobrança do GrowthHS, um card por aparelho cuja calibração vence nos próximos 50 dias — agendado por cron.

**Architecture:** Mesma separação das Etapas 1 e 2: um módulo **puro** em `core/` monta o card (sem I/O, testável isolado) e um **script** em `scripts/` faz a consulta ao banco, o laço best-effort e o relatório. Reaproveita integralmente `core/growthhs_payload.py` (client/contact/device), `api/growthhs_cards.buscar_elo` (a ponte Phoebus↔Módulo) e `integrations/hsgrowth_client.enviar_card_sync`. Nada de novo na camada HTTP.

**Tech Stack:** Python 3.12 · SQLAlchemy 2 · pytest (SQLite in-memory) · cron via `docker exec`.

## Global Constraints

Valores exatos, copiados da spec `docs/superpowers/specs/2026-07-18-integracao-growthhs-design.md`:

- `source` = `"gestorhs.calibracao"` (constante `SOURCE_VENCENDO`)
- `external_id` = `f"{equipamento_cliente.id}:{prox_calibragem:%Y-%m-%d}"` — **por aparelho + ciclo**, nunca por cliente
- `board_id` = `settings.HSGROWTH_BOARD_COBRANCA` (2)
- `title` = `f"Calibração vencendo · {cliente} · {equipamento} {série}"`
- `due_date` = a própria `prox_calibragem`, em **datetime completo** `f"{data.isoformat()}T00:00:00"` — data pura devolve 422 (Pydantic v2 recusa; confirmado com 422 real em 18/07/2026)
- Janela: `prox_calibragem BETWEEN hoje AND hoje + dias` — **não inclui vencidos** (`< hoje`); esse backlog é da Etapa 1
- Exclusões: `ativo = true`, `equipamento NOT IN (36, 37)`, `cliente != 2`, e `os_atual IS NULL`
- Constantes de exclusão vêm de `settings` (`EQUIPAMENTO_PHOEBUS_ID`, `EQUIPAMENTO_EBS_ID`, `CLIENTE_ESTOQUE_HS_ID`) — **nunca** hard-coded
- Tabela do modelo: `EquipamentoCliente` (`__tablename__ = "equipamentos_cliente"`) — sempre via ORM
- Mensagens de commit em PT-BR **sem acentos**, uma linha

### Decisão deliberada: aqui o padrão é ENVIAR

A Etapa 1 (`enviar_atrasados_growthhs`) exige `--enviar` explícito. **A Etapa 3 faz o contrário: envia por padrão e simula com `--dry-run`.** Isto é intencional, não uma inconsistência a "corrigir":

- A chave da Etapa 1 é `{cliente}:{data_da_carga}` — rodar em duas datas cria cards **duplicados** e irrecuperáveis, então o default seguro é não enviar.
- A chave da Etapa 3 é `{ec_id}:{prox_calibragem}` — **não muda com a data da execução**. Rodar de novo devolve `created: false` e não cria nada. Repetir é inofensivo por construção.
- É um job de **cron**: um default que não envia transformaria o agendamento num no-op silencioso — o pior modo de falha possível para esta etapa.

### Contexto de volume (medido em produção em 20/07/2026)

Na janela de 50 dias: 416 aparelhos, 7 com OS em andamento → **409 cards na primeira rodada**, 202 clientes. Depois disso, ~10–13/dia entrando na borda. A flag `--dias` permite rampar a primeira rodada (`--dias 7`, depois 20, depois 50) se o comercial não absorver 409 de uma vez. Isso é decisão de operação, não de código.

---

### Task 1: Módulo puro — montagem do card de vencendo

**Files:**
- Create: `backend/app/core/growthhs_vencendo.py`
- Test: `backend/tests/test_growthhs_vencendo.py`

**Interfaces:**
- Consumes: `montar_cliente`, `montar_contato`, `montar_device` de `app.core.growthhs_payload` (já existem, não alterar).
  `montar_device(ec, equipamento_desc: str, elo=None) -> dict` — quando `elo` é dado, usa a série do Phoebus e põe a do módulo em `alcohol_module`.
- Produces: `SOURCE_VENCENDO: str` e
  `montar_card_vencendo(linha: dict, hoje: date, board_id: int) -> dict`.
  `linha` é `{cliente_id, cliente, ec, equipamento_desc, elo}` — **o mesmo formato de linha da Etapa 1**, para que os dois scripts compartilhem `buscar_elo`. A diferença é que aqui a função recebe **uma linha** (um card por aparelho), não um grupo.

- [ ] **Step 1: Escrever o teste que falha**

Criar `backend/tests/test_growthhs_vencendo.py`:

```python
from datetime import date
from types import SimpleNamespace as NS

from app.core.growthhs_vencendo import SOURCE_VENCENDO, montar_card_vencendo


def _cliente(**kw):
    base = dict(id=512, nome="ACME Ltda", cgc="12345678000199", cpf=None,
                email="fin@acme.com", contato="Marcos", celular="11987654321",
                whatsapp=None, telefones="1133334444", endereco="Rua X", numero=220,
                bairro="Centro", municipio="Sao Paulo", estado="SP")
    base.update(kw)
    return NS(**base)


def _linha(cliente=None, ec_id=77, serie="SN-1", prox=date(2026, 8, 20),
           equipamento_desc="HS PASS - IBLOW", elo=None):
    cliente = cliente or _cliente()
    return {
        "cliente_id": cliente.id,
        "cliente": cliente,
        "ec": NS(id=ec_id, serie=serie, prox_calibragem=prox),
        "equipamento_desc": equipamento_desc,
        "elo": elo,
    }


def test_source_fixo():
    card = montar_card_vencendo(_linha(), date(2026, 7, 20), board_id=2)
    assert card["source"] == "gestorhs.calibracao"
    assert SOURCE_VENCENDO == "gestorhs.calibracao"


def test_external_id_e_por_aparelho_mais_ciclo():
    """A chave NAO pode depender da data da execucao: e' isso que torna o job
    diario idempotente. Rodar em dias diferentes gera o MESMO external_id."""
    linha = _linha(ec_id=77, prox=date(2026, 8, 20))
    card_seg = montar_card_vencendo(linha, date(2026, 7, 20), board_id=2)
    card_ter = montar_card_vencendo(linha, date(2026, 7, 21), board_id=2)
    assert card_seg["external_id"] == "77:2026-08-20"
    assert card_ter["external_id"] == "77:2026-08-20"


def test_titulo_traz_cliente_equipamento_e_serie():
    card = montar_card_vencendo(
        _linha(serie="F005065", equipamento_desc="HS PASS - IBLOW"),
        date(2026, 7, 20), board_id=2,
    )
    assert card["title"] == "Calibração vencendo · ACME Ltda · HS PASS - IBLOW F005065"


def test_due_date_e_datetime_completo():
    """Data pura devolve 422 (Pydantic v2 do GrowthHS: `Optional[datetime]`)."""
    card = montar_card_vencendo(_linha(prox=date(2026, 8, 20)), date(2026, 7, 20), board_id=2)
    assert card["due_date"] == "2026-08-20T00:00:00"


def test_um_unico_device_por_card():
    card = montar_card_vencendo(_linha(serie="SN-9"), date(2026, 7, 20), board_id=2)
    assert len(card["devices"]) == 1
    assert card["devices"][0]["serial_number"] == "SN-9"


def test_device_usa_o_elo_quando_presente():
    """Modulo com Phoebus vinculado: o cliente reconhece o APARELHO, entao a serie
    do card e' a do Phoebus e a do modulo vai em `alcohol_module`."""
    elo = NS(serie="WATFR01-00340", descricao="Phoebus")
    card = montar_card_vencendo(_linha(serie="F005065", elo=elo), date(2026, 7, 20), board_id=2)
    dev = card["devices"][0]
    assert dev["serial_number"] == "WATFR01-00340"
    assert dev["alcohol_module"] == "F005065"


def test_descricao_traz_dias_restantes_e_data():
    card = montar_card_vencendo(_linha(prox=date(2026, 8, 20)), date(2026, 7, 20), board_id=2)
    assert "31" in card["description"]
    assert "20/08/2026" in card["description"]


def test_contact_ausente_quando_cliente_sem_contato():
    card = montar_card_vencendo(_linha(cliente=_cliente(contato=None)),
                                date(2026, 7, 20), board_id=2)
    assert card["contact"] is None


def test_client_montado_com_external_id_do_id_interno():
    card = montar_card_vencendo(_linha(cliente=_cliente(id=1, nome="ACME Ltda")),
                                date(2026, 7, 20), board_id=2)
    assert card["client"]["external_id"] == "1"
    assert card["client"]["name"] == "ACME Ltda"


def test_business_info():
    card = montar_card_vencendo(_linha(ec_id=77, prox=date(2026, 8, 20)),
                                date(2026, 7, 20), board_id=2)
    assert card["business_info"] == {
        "origem": "calibracao vencendo",
        "cliente_id": 512,
        "equipamento_cliente_id": 77,
        "dias_para_vencer": 31,
    }


def test_board_id_repassado():
    card = montar_card_vencendo(_linha(), date(2026, 7, 20), board_id=7)
    assert card["board_id"] == 7
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Run: `docker exec gestorhs-backend pytest -q tests/test_growthhs_vencendo.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.growthhs_vencendo'`

- [ ] **Step 3: Implementar o módulo**

Criar `backend/app/core/growthhs_vencendo.py`:

```python
"""Montagem do card de calibração VENCENDO (janela dos 50 dias) do GrowthHS.

Sem I/O: recebe uma linha já lida do banco e devolve o dict pronto para o cliente
de integração — mesma convenção de `core/growthhs_payload.py` e
`core/growthhs_atrasados.py`.

Diferença deliberada para a Etapa 1 (atrasados): lá o card é POR CLIENTE, aqui é
POR APARELHO. A Etapa 1 é um retrato único, tirado uma vez; agrupar por cliente é
seguro. Esta etapa tem janela ROLANTE — se a chave fosse por cliente, o segundo
aparelho a entrar na janela depois do card já existir devolveria o card antigo
(`created: false`) e nunca apareceria, sem erro nenhum.
"""
from datetime import date

from app.core.growthhs_payload import montar_cliente, montar_contato, montar_device

SOURCE_VENCENDO = "gestorhs.calibracao"


def montar_card_vencendo(linha: dict, hoje: date, board_id: int) -> dict:
    """Monta o corpo do POST em `/api/v1/integration/service-cards` para UM aparelho
    com calibração a vencer.

    `linha` é `{cliente_id, cliente, ec, equipamento_desc, elo}` — o mesmo formato da
    Etapa 1, para que ambos os scripts compartilhem `buscar_elo`.
    """
    cliente = linha["cliente"]
    ec = linha["ec"]
    equipamento_desc = linha["equipamento_desc"] or ""
    prox = ec.prox_calibragem
    nome = getattr(cliente, "nome", None) or ""
    serie = getattr(ec, "serie", None) or ""
    dias = (prox - hoje).days

    return {
        "source": SOURCE_VENCENDO,
        # A chave NAO leva a data da execucao — e' o que torna o job diario
        # idempotente: rodar de novo devolve `created: false` e nao duplica.
        "external_id": f"{ec.id}:{prox:%Y-%m-%d}",
        "board_id": board_id,
        "title": f"Calibração vencendo · {nome} · {equipamento_desc} {serie}".rstrip(),
        "description": (
            f"Calibração vence em {dias} dia(s), em {prox.strftime('%d/%m/%Y')} — "
            f"{equipamento_desc} série {serie}"
        ),
        # datetime COMPLETO: `due_date` e' `Optional[datetime]` no schema do GrowthHS
        # e o Pydantic v2 recusa "YYYY-MM-DD". Confirmado com 422 real em 18/07/2026.
        "due_date": f"{prox.isoformat()}T00:00:00",
        "client": montar_cliente(cliente),
        "contact": montar_contato(cliente),
        "devices": [montar_device(ec, equipamento_desc, elo=linha.get("elo"))],
        "business_info": {
            "origem": "calibracao vencendo",
            "cliente_id": linha["cliente_id"],
            "equipamento_cliente_id": ec.id,
            "dias_para_vencer": dias,
        },
    }
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `docker exec gestorhs-backend pytest -q tests/test_growthhs_vencendo.py`
Expected: PASS — 11 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/growthhs_vencendo.py backend/tests/test_growthhs_vencendo.py
git commit -m "feat(growthhs): monta card de calibracao vencendo por aparelho"
```

---

### Task 2: Script diário — seleção, envio best-effort e relatório

**Files:**
- Create: `backend/app/scripts/enviar_vencendo_growthhs.py`
- Test: `backend/tests/test_enviar_vencendo_growthhs.py`

**Interfaces:**
- Consumes: `montar_card_vencendo`, `SOURCE_VENCENDO` (Task 1);
  `buscar_elo(db, ec)` de `app.api.growthhs_cards` — devolve um `SimpleNamespace(serie, descricao)` do Phoebus vinculado, ou `None`.
  **Atenção:** `montar_device` espera `.serie`/`.descricao`; o ORM `EquipamentoCliente` expõe `.equipamento_descricao`. Passar a linha do ORM direto quebra com `AttributeError` só nos módulos QUE TÊM elo. Use `buscar_elo`, que já faz essa ponte.
  `enviar_card_sync(payload) -> dict` e `integracao_ativa() -> bool` de `app.integrations.hsgrowth_client`.
- Produces: `buscar_vencendo(db, dias: int) -> list[dict]` e
  `processar(db, *, dias: int, enviar: bool, limite: int | None = None) -> dict`.

- [ ] **Step 1: Escrever o teste que falha**

Criar `backend/tests/test_enviar_vencendo_growthhs.py`:

```python
from datetime import date, timedelta

import pytest

from app.core.config import settings
from app.models import Cliente, Equipamento, EquipamentoCliente
from app.scripts.enviar_vencendo_growthhs import buscar_vencendo, processar

HOJE = date.today()


@pytest.fixture
def cliente(db_session):
    c = Cliente(nome="ACME Ltda")
    db_session.add(c); db_session.commit(); db_session.refresh(c)
    return c


@pytest.fixture
def equipamentos(db_session):
    """O conftest liga `PRAGMA foreign_keys=ON`, entao `equipamentos_cliente.equipamento`
    PRECISA apontar para uma linha real de `equipamentos` — inclusive os IDs de exclusao
    (Phoebus 36 / EBS 37), que sao criados aqui com ID explicito para os testes de filtro."""
    linhas = {
        "modulo": Equipamento(id=settings.EQUIPAMENTO_MODULO_ID, descricao="Modulo de calibracao"),
        "phoebus": Equipamento(id=settings.EQUIPAMENTO_PHOEBUS_ID, descricao="Phoebus"),
        "ebs": Equipamento(id=settings.EQUIPAMENTO_EBS_ID, descricao="EBS"),
    }
    db_session.add_all(linhas.values()); db_session.commit()
    return {nome: eq.id for nome, eq in linhas.items()}


def _ec(db_session, cliente_id, *, dias, equipamento=None, ativo=True, os_atual=None):
    ec = EquipamentoCliente(
        cliente=cliente_id,
        equipamento=equipamento if equipamento is not None else settings.EQUIPAMENTO_MODULO_ID,
        serie=f"SN-{dias}",
        prox_calibragem=HOJE + timedelta(days=dias), ativo=ativo, os_atual=os_atual,
    )
    db_session.add(ec); db_session.commit(); db_session.refresh(ec)
    return ec


def _ids(linhas):
    return {linha["ec"].id for linha in linhas}


def test_pega_dentro_da_janela(db_session, cliente, equipamentos):
    dentro = _ec(db_session, cliente.id, dias=10)
    assert dentro.id in _ids(buscar_vencendo(db_session, 50))


def test_inclui_as_duas_bordas(db_session, cliente, equipamentos):
    """Janela FECHADA nos dois lados: vence hoje entra, vence no ultimo dia entra."""
    hoje_mesmo = _ec(db_session, cliente.id, dias=0)
    ultimo = _ec(db_session, cliente.id, dias=50)
    ids = _ids(buscar_vencendo(db_session, 50))
    assert hoje_mesmo.id in ids
    assert ultimo.id in ids


def test_ignora_vencidos(db_session, cliente, equipamentos):
    """Vencido e' backlog da Etapa 1 — incluir aqui geraria milhares de cards
    num formato diferente do que a Etapa 1 ja criou."""
    vencido = _ec(db_session, cliente.id, dias=-1)
    assert vencido.id not in _ids(buscar_vencendo(db_session, 50))


def test_ignora_fora_da_janela(db_session, cliente, equipamentos):
    longe = _ec(db_session, cliente.id, dias=51)
    assert longe.id not in _ids(buscar_vencendo(db_session, 50))


def test_ignora_com_os_em_andamento(db_session, cliente, equipamentos):
    """Se o cliente ja mandou o aparelho, 'entre em contato' e' ruido."""
    em_os = _ec(db_session, cliente.id, dias=10, os_atual=12345)
    assert em_os.id not in _ids(buscar_vencendo(db_session, 50))


def test_ignora_inativo(db_session, cliente, equipamentos):
    inativo = _ec(db_session, cliente.id, dias=10, ativo=False)
    assert inativo.id not in _ids(buscar_vencendo(db_session, 50))


def test_ignora_phoebus_e_ebs(db_session, cliente, equipamentos):
    """Sao hospedeiros: nao sao calibrados, quem calibra e' o modulo dentro deles."""
    ph = _ec(db_session, cliente.id, dias=10, equipamento=settings.EQUIPAMENTO_PHOEBUS_ID)
    ebs = _ec(db_session, cliente.id, dias=11, equipamento=settings.EQUIPAMENTO_EBS_ID)
    ids = _ids(buscar_vencendo(db_session, 50))
    assert ph.id not in ids
    assert ebs.id not in ids


def test_ignora_cliente_de_estoque_interno(db_session, equipamentos):
    estoque = Cliente(id=settings.CLIENTE_ESTOQUE_HS_ID, nome="Estoque HS")
    db_session.add(estoque); db_session.commit()
    ec = _ec(db_session, settings.CLIENTE_ESTOQUE_HS_ID, dias=10)
    assert ec.id not in _ids(buscar_vencendo(db_session, 50))


def test_dias_menor_encolhe_a_janela(db_session, cliente, equipamentos):
    perto = _ec(db_session, cliente.id, dias=5)
    longe = _ec(db_session, cliente.id, dias=40)
    ids = _ids(buscar_vencendo(db_session, 7))
    assert perto.id in ids
    assert longe.id not in ids


def test_dry_run_nao_envia_mas_monta(db_session, cliente, equipamentos, monkeypatch):
    """A montagem acontece SEMPRE — e' assim que o dry-run valida o payload."""
    _ec(db_session, cliente.id, dias=10)
    chamadas = []
    monkeypatch.setattr("app.scripts.enviar_vencendo_growthhs.enviar_card_sync",
                        lambda card: chamadas.append(card) or {"created": True})
    r = processar(db_session, dias=50, enviar=False)
    assert chamadas == []
    assert r["candidatos"] == 1
    assert r["criados"] == 0


def test_envia_e_conta_criados_e_existentes(db_session, cliente, equipamentos, monkeypatch):
    _ec(db_session, cliente.id, dias=10)
    _ec(db_session, cliente.id, dias=11)
    respostas = [{"created": True}, {"created": False}]
    monkeypatch.setattr("app.scripts.enviar_vencendo_growthhs.enviar_card_sync",
                        lambda card: respostas.pop(0))
    r = processar(db_session, dias=50, enviar=True)
    assert r["criados"] == 1
    assert r["existentes"] == 1
    assert r["falhas"] == 0


def test_falha_num_aparelho_nao_aborta_os_outros(db_session, cliente, equipamentos, monkeypatch):
    """Best-effort POR APARELHO: um 422 num card nao pode derrubar a rodada."""
    _ec(db_session, cliente.id, dias=10)
    _ec(db_session, cliente.id, dias=11)
    _ec(db_session, cliente.id, dias=12)

    def falha_no_segundo(card):
        falha_no_segundo.n += 1
        if falha_no_segundo.n == 2:
            raise RuntimeError("GrowthHS respondeu 422: campo invalido")
        return {"created": True}
    falha_no_segundo.n = 0

    monkeypatch.setattr("app.scripts.enviar_vencendo_growthhs.enviar_card_sync",
                        falha_no_segundo)
    r = processar(db_session, dias=50, enviar=True)
    assert r["criados"] == 2
    assert r["falhas"] == 1
    assert len(r["pendencias"]) == 1
    assert "422" in r["pendencias"][0]["motivo"]


def test_limite_corta_a_rodada(db_session, cliente, equipamentos, monkeypatch):
    for d in (10, 11, 12):
        _ec(db_session, cliente.id, dias=d)
    monkeypatch.setattr("app.scripts.enviar_vencendo_growthhs.enviar_card_sync",
                        lambda card: {"created": True})
    r = processar(db_session, dias=50, enviar=True, limite=2)
    assert r["candidatos"] == 2
    assert r["criados"] == 2
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Run: `docker exec gestorhs-backend pytest -q tests/test_enviar_vencendo_growthhs.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.scripts.enviar_vencendo_growthhs'`

- [ ] **Step 3: Implementar o script**

Criar `backend/app/scripts/enviar_vencendo_growthhs.py`:

```python
"""Job DIARIO: cria um card no board Cobranca do GrowthHS para cada aparelho cuja
calibracao vence nos proximos N dias (padrao 50).

Uso: python -m app.scripts.enviar_vencendo_growthhs [--dias 50] [--dry-run]
     [--limite N] [--pendencias CAMINHO.csv]

Agendado por cron (ver docs/operacao-growthhs-cron.md).

PADRAO E' ENVIAR — ao contrario de `enviar_atrasados_growthhs`, que exige
`--enviar`. Nao e' inconsistencia: a chave daquele script leva a data da carga, entao
repetir cria duplicata irrecuperavel; a chave DESTE e' `{ec_id}:{prox_calibragem}`,
que nao muda com o dia da execucao — rodar de novo devolve `created: false` e nao
cria nada. Alem disso e' um job de cron: um default que nao envia viraria um
agendamento no-op silencioso, o pior modo de falha possivel aqui.

O job e' BURRO e SEM ESTADO: roda todo dia sobre a janela inteira e nao precisa
lembrar o que ja mandou, porque a criacao e' idempotente.
"""
import argparse
import csv
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.api.growthhs_cards import buscar_elo
from app.core.config import settings
from app.core.growthhs_vencendo import montar_card_vencendo
from app.integrations.hsgrowth_client import enviar_card_sync, integracao_ativa
from app.models import EquipamentoCliente
from app.models.database import SessionLocal

# backend/app/scripts/<arquivo>.py -> raiz do repo. O script roda a partir de
# `backend/`; resolver contra o CWD colocaria o CSV em `backend/docs/` (nao existe).
_RAIZ_REPO = Path(__file__).resolve().parents[3]

DIAS_PADRAO = 50


def buscar_vencendo(db: Session, dias: int) -> list[dict]:
    """Uma linha por aparelho com calibracao a vencer na janela `[hoje, hoje+dias]`.

    Cada linha: `{cliente_id, cliente, ec, equipamento_desc, elo}` — mesmo formato da
    Etapa 1, de proposito, para compartilhar `buscar_elo`.

    NAO inclui vencidos (`prox_calibragem < hoje`): esse backlog e' da Etapa 1.
    Exclui hospedeiros (Phoebus/EBS), o cliente de estoque interno da HS e aparelhos
    com OS em andamento (`os_atual` preenchido) — se o cliente ja mandou o aparelho,
    "entre em contato" e' ruido.
    """
    hoje = date.today()
    ecs = (
        db.query(EquipamentoCliente)
        .filter(
            EquipamentoCliente.ativo.is_(True),
            EquipamentoCliente.prox_calibragem.isnot(None),
            EquipamentoCliente.prox_calibragem >= hoje,
            EquipamentoCliente.prox_calibragem <= hoje + timedelta(days=dias),
            EquipamentoCliente.os_atual.is_(None),
            EquipamentoCliente.equipamento.notin_(
                [settings.EQUIPAMENTO_PHOEBUS_ID, settings.EQUIPAMENTO_EBS_ID]
            ),
            EquipamentoCliente.cliente != settings.CLIENTE_ESTOQUE_HS_ID,
        )
        .order_by(EquipamentoCliente.prox_calibragem, EquipamentoCliente.id)
        .all()
    )

    return [
        {
            "cliente_id": ec.cliente,
            "cliente": ec.cliente_rel,
            "ec": ec,
            "equipamento_desc": ec.equipamento_descricao,
            "elo": buscar_elo(db, ec),
        }
        for ec in ecs
    ]


def processar(db: Session, *, dias: int, enviar: bool, limite: Optional[int] = None) -> dict:
    """Busca a janela e manda um card por aparelho.

    Best-effort POR APARELHO: uma excecao num card e' contada em `falhas`, registrada
    em `pendencias` e o laco SEGUE para o proximo — nunca aborta a rodada inteira.
    """
    linhas = buscar_vencendo(db, dias)
    if limite is not None:
        linhas = linhas[:limite]

    hoje = date.today()
    criados = existentes = falhas = 0
    pendencias: list[dict] = []

    for linha in linhas:
        ec = linha["ec"]
        # Monta SEMPRE, inclusive em dry-run: e' assim que a simulacao cumpre o que
        # promete — validar que o payload de todo aparelho consegue ser construido.
        try:
            card = montar_card_vencendo(linha, hoje, settings.HSGROWTH_BOARD_COBRANCA)
        except Exception as exc:  # noqa: BLE001 — melhor esforco por aparelho
            falhas += 1
            pendencias.append({
                "equipamento_cliente_id": ec.id,
                "cliente_id": linha["cliente_id"],
                "serie": getattr(ec, "serie", "") or "",
                "prox_calibragem": ec.prox_calibragem.isoformat(),
                "motivo": f"falha ao montar o card: {exc}",
            })
            continue

        if not enviar:
            continue      # dry-run: montou (validou) e para aqui, sem request

        try:
            resposta = enviar_card_sync(card)
        except Exception as exc:  # noqa: BLE001 — segue para o proximo aparelho
            falhas += 1
            pendencias.append({
                "equipamento_cliente_id": ec.id,
                "cliente_id": linha["cliente_id"],
                "serie": getattr(ec, "serie", "") or "",
                "prox_calibragem": ec.prox_calibragem.isoformat(),
                "motivo": str(exc),
            })
            continue

        if resposta.get("created"):
            criados += 1
        else:
            existentes += 1

    return {
        "candidatos": len(linhas),
        "criados": criados,
        "existentes": existentes,
        "falhas": falhas,
        "pendencias": pendencias,
    }


def _escrever_csv_pendencias(caminho: str, pendencias: list[dict]) -> None:
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "equipamento_cliente_id", "cliente_id", "serie", "prox_calibragem", "motivo",
        ])
        writer.writeheader()
        for p in pendencias:
            writer.writerow(p)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Job diario: cards de calibracao vencendo no board Cobranca do GrowthHS."
    )
    parser.add_argument("--dias", type=int, default=DIAS_PADRAO,
                        help=f"Tamanho da janela em dias (padrao {DIAS_PADRAO})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simula: monta tudo e imprime o resumo, sem NENHUM request.")
    parser.add_argument("--limite", type=int, default=None,
                        help="Processa so os N primeiros aparelhos — para um teste controlado")
    parser.add_argument("--pendencias", default=None, help="Caminho do CSV de falhas")
    args = parser.parse_args()

    enviar = not args.dry_run

    if enviar and not integracao_ativa():
        print("ERRO: integracao com o GrowthHS esta DESLIGADA "
              "(configure HSGROWTH_BASE_URL e HSGROWTH_API_KEY) — abortando. "
              "Nada foi lido nem enviado.")
        raise SystemExit(1)

    caminho_pendencias = args.pendencias or str(
        _RAIZ_REPO / "docs" / f"pendencias-vencendo-growthhs-{date.today().isoformat()}.csv"
    )
    # Cria o diretorio ANTES de qualquer envio: um caminho invalido precisa falhar
    # rapido, nao depois de ja ter criado cards em producao.
    os.makedirs(os.path.dirname(caminho_pendencias) or ".", exist_ok=True)

    db = SessionLocal()
    try:
        r = processar(db, dias=args.dias, enviar=enviar)
    finally:
        db.close()

    _escrever_csv_pendencias(caminho_pendencias, r["pendencias"])

    print(f"Janela: {date.today()} -> {date.today() + timedelta(days=args.dias)} "
          f"({args.dias} dias)")
    print(f"Aparelhos na janela: {r['candidatos']}")
    if enviar:
        print(f"Criados: {r['criados']} / Ja existentes: {r['existentes']} / "
              f"Falhas: {r['falhas']}")
    else:
        print("MODO DRY-RUN — NADA FOI ENVIADO. Rode sem --dry-run para valer.")
    print(f"Pendencias/falhas gravadas em: {caminho_pendencias}")

    # Saida !=0 quando houve falha, para o cron conseguir alertar.
    if r["falhas"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `docker exec gestorhs-backend pytest -q tests/test_enviar_vencendo_growthhs.py`
Expected: PASS — 13 passed

- [ ] **Step 5: Rodar a suíte inteira (nada quebrou)**

Run: `docker exec gestorhs-backend pytest -q`
Expected: PASS — todos, sem falhas

- [ ] **Step 6: Commit**

```bash
git add backend/app/scripts/enviar_vencendo_growthhs.py backend/tests/test_enviar_vencendo_growthhs.py
git commit -m "feat(growthhs): job diario dos aparelhos vencendo em 50 dias"
```

---

### Task 3: Documentação de operação (cron) e CLAUDE.md

**Files:**
- Create: `docs/operacao-growthhs-cron.md`
- Modify: `CLAUDE.md` (seção "Comandos" → Backend)

**Interfaces:**
- Consumes: o CLI da Task 2 (`--dias`, `--dry-run`, `--limite`, `--pendencias`).
- Produces: nada em código.

- [ ] **Step 1: Escrever o documento de operação**

Criar `docs/operacao-growthhs-cron.md`:

```markdown
# Operação — job diário do GrowthHS (calibração vencendo)

Cria um card no board **Cobrança** (2) do GrowthHS para cada aparelho cuja calibração
vence nos próximos 50 dias. Um card por **aparelho + ciclo**.

## Antes da primeira rodada

A janela já está cheia: a primeira execução cria **~409 cards de uma vez** (medido em
20/07/2026), enquanto o regime normal é ~10–13/dia. Confira antes de abrir a torneira:

    docker exec gestorhs-backend python -m app.scripts.enviar_vencendo_growthhs --dry-run

Se o comercial não absorver 409 de uma vez, rampe com `--dias`: rode `--dias 7` no
primeiro dia, `--dias 20` alguns dias depois, e só então deixe o cron no padrão de 50.
Rodar de novo **não duplica** — a chave é `{equipamento_cliente_id}:{prox_calibragem}`,
que não muda com a data da execução.

## O agendamento

Uma vez por dia, às 08:00. No host (crontab do usuário que roda o Docker):

    0 8 * * * docker exec gestorhs-backend python -m app.scripts.enviar_vencendo_growthhs >> /var/log/growthhs-vencendo.log 2>&1

O script sai com código **≠ 0** quando houve alguma falha, então qualquer monitor de cron
consegue alertar.

## Flags

| Flag | Para quê |
|---|---|
| `--dias N` | Tamanho da janela (padrão 50). Use para rampar a primeira rodada. |
| `--dry-run` | Monta tudo e mostra o resumo **sem enviar nada**. |
| `--limite N` | Processa só os N primeiros aparelhos — teste controlado. |
| `--pendencias CAMINHO` | Onde gravar o CSV de falhas (padrão: `docs/pendencias-vencendo-growthhs-<data>.csv`). |

> ⚠️ Aqui o padrão é **enviar** (`--dry-run` para simular) — o contrário de
> `enviar_atrasados_growthhs`, que exige `--enviar`. É proposital: a chave deste job não
> depende da data da execução, então repetir é inofensivo; e um job de cron que não envia
> por padrão seria um agendamento silenciosamente inútil.

## Quando algo falha

O laço é best-effort **por aparelho**: uma falha num card não derruba a rodada. As falhas
vão para o CSV de pendências com o motivo (incluindo o corpo da resposta do GrowthHS, que
é onde o 422 diz qual campo reprovou). Como o job é idempotente, basta corrigir a causa e
esperar a próxima execução — ela reprocessa a janela inteira.

## O que o job NÃO faz

- **Não pega vencidos** (`prox_calibragem < hoje`) — esse backlog foi a carga única da
  Etapa 1, em formato por cliente.
- **Não atualiza** cards existentes. O endpoint do GrowthHS é *create-or-return*, não
  upsert: o card é um retrato do momento em que foi criado.
- **Não pula** aparelho que já tem card de outro ciclo — ciclo novo, card novo, de propósito.
```

- [ ] **Step 2: Registrar o comando no CLAUDE.md**

Em `CLAUDE.md`, no bloco de comandos do Backend, logo após as duas linhas de
`enviar_atrasados_growthhs`, acrescentar:

```
python -m app.scripts.enviar_vencendo_growthhs --dry-run                   # SIMULA o job diario dos 50 dias
python -m app.scripts.enviar_vencendo_growthhs                             # job diario real (agendado por cron)
```

E, logo abaixo do aviso já existente sobre `enviar_atrasados_growthhs`, acrescentar:

```
> ℹ️ **`enviar_vencendo_growthhs` ENVIA por padrao** (use `--dry-run` para simular) — o
> inverso do script de atrasados. A chave e `{equipamento_cliente_id}:{prox_calibragem}`,
> que nao muda com a data da execucao, entao repetir nao duplica. Operacao e agendamento
> em [docs/operacao-growthhs-cron.md](docs/operacao-growthhs-cron.md).
```

- [ ] **Step 3: Conferir que os links do documento resolvem**

Run: `ls docs/operacao-growthhs-cron.md && grep -c "enviar_vencendo_growthhs" CLAUDE.md`
Expected: o arquivo existe e o grep retorna 3

- [ ] **Step 4: Commit**

```bash
git add docs/operacao-growthhs-cron.md CLAUDE.md
git commit -m "docs(growthhs): operacao e cron do job diario dos 50 dias"
```

---

## Fora do escopo deste plano

- **Instalar o cron no host** — é a única parte que não é código, e exige `sudo` no
  Konsole. O documento da Task 3 traz a linha pronta; o Erick agenda.
- **Rodar a primeira carga** — decisão de operação (rampa ou 409 de uma vez), tomada
  depois do `--dry-run`.
- **Entrada no changelog** — este job não tem efeito visível na interface do GestorHS.
