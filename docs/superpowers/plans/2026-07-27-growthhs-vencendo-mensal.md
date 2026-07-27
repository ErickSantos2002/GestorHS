# Job de calibração vencendo mensal e por cliente — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trocar o job de calibração vencendo do GrowthHS de **diário/um card por aparelho** para **mensal (dia 1, 8h) / um card por cliente por mês de vencimento**, varrendo mês corrente + mês seguinte.

**Architecture:** A separação atual é mantida — regra pura em `app/core/` (montagem do card, cálculo de horário), seleção e laço em `app/scripts/enviar_vencendo_growthhs.py`, I/O em `app/integrations/hsgrowth_client.py` (intocado), agendamento em `app/tarefas/vencendo.py`. A idempotência sai inteira da chave `external_id = {cliente_id}:{YYYY-MM}`: como toda rodada varre dois meses e o de trás já tem card, o GrowthHS devolve `created: false` e nada duplica. Nenhum estado novo é persistido e não há migração de banco.

**Tech Stack:** Python 3.12 · SQLAlchemy 2 · pytest (SQLite in-memory via `backend/tests/conftest.py`) · httpx (já encapsulado no client).

## Global Constraints

- Todo o trabalho é dentro de `backend/`. Ativar a venv antes: `source .venv/bin/activate`. Rodar testes com `pytest -q` a partir de `backend/`.
- **Idioma:** domínio em PT-BR (nomes de função, variáveis, mensagens). Docstrings e comentários em português. Arquivos de código do projeto usam ASCII nos comentários novos quando o arquivo já é ASCII, e acentos quando o arquivo já tem acentos — siga o arquivo que estiver editando.
- **Commits:** Conventional Commits em **português sem acentos**, assunto de **uma linha só**, sem corpo e sem trailer de co-autor. Escopo `growthhs`. Ex.: `feat(growthhs): card mensal por cliente no lugar de um por aparelho`.
- **Não commitar nada fora do que a tarefa tocou.** Há outro agente trabalhando neste repo: use `git add <arquivos>` explícito, **nunca `git add -A`**, e confira `git branch --show-current` antes de cada commit.
- `source` do card continua `gestorhs.calibracao`; board continua `settings.HSGROWTH_BOARD_COBRANCA`.
- **Nenhuma migração Alembic** nesta entrega.
- O padrão do script continua **ENVIAR** (`--dry-run` para simular).

## File Structure

| Arquivo | Responsabilidade depois da mudança |
|---|---|
| `app/core/agendamento.py` | Só a regra mensal: "próximo dia 1 às H no fuso de SP". A regra diária sai. |
| `app/core/growthhs_vencendo.py` | Montagem pura do card **por cliente** a partir de uma lista de linhas de um mesmo cliente + a competência. |
| `app/scripts/enviar_vencendo_growthhs.py` | Seleção por competência, agrupamento por cliente, laço best-effort por cliente, relatório e CLI. |
| `app/tarefas/vencendo.py` | Worker: dorme até o dia 1, calcula `[mês corrente, mês seguinte]`, chama `processar`. |
| `app/core/config.py` | Remove `JOB_VENCENDO_DIAS`. |
| `docs/operacao-growthhs-job-mensal.md` | Documento de operação (renomeado e reescrito). |

---

### Task 1: Regra de agendamento mensal

**Files:**
- Modify: `backend/app/core/agendamento.py` (arquivo inteiro — remove a regra diária, adiciona a mensal)
- Test: `backend/tests/test_agendamento.py` (reescrito)

**Interfaces:**
- Consumes: nada.
- Produces: `proxima_execucao_mensal(agora: datetime, hora: int, minuto: int = 0) -> datetime` e `segundos_ate_proxima_mensal(agora: datetime, hora: int, minuto: int = 0) -> float`. `TZ_SP` continua exportado. `proxima_execucao` e `segundos_ate_proxima` **deixam de existir**.

> Por que remover a versão diária: depois desta entrega nada em produção a usa, e manter função morta viva porque "o teste dela usa" é manter código morto. O git guarda a versão anterior.
>
> Por que não parametrizar o dia do mês: só existe um caso de uso (dia 1). Um parâmetro `dia` traria de graça o problema de meses com 28/29/30 dias sem ninguém precisar dele.

- [ ] **Step 1: Escrever os testes que falham**

Substitua **todo** o conteúdo de `backend/tests/test_agendamento.py` por:

```python
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.agendamento import TZ_SP, proxima_execucao_mensal, segundos_ate_proxima_mensal

UTC = ZoneInfo("UTC")


def _sp(ano, mes, dia, hora, minuto=0):
    return datetime(ano, mes, dia, hora, minuto, tzinfo=TZ_SP)


def test_no_meio_do_mes_agenda_para_o_dia_1_seguinte():
    agora = _sp(2026, 7, 20, 10, 0)
    assert proxima_execucao_mensal(agora, 8) == _sp(2026, 8, 1, 8)


def test_no_dia_1_antes_da_hora_agenda_para_hoje():
    agora = _sp(2026, 8, 1, 6, 30)
    assert proxima_execucao_mensal(agora, 8) == _sp(2026, 8, 1, 8)


def test_no_dia_1_depois_da_hora_agenda_para_o_mes_seguinte():
    agora = _sp(2026, 8, 1, 9, 15)
    assert proxima_execucao_mensal(agora, 8) == _sp(2026, 9, 1, 8)


def test_exatamente_no_horario_agenda_para_o_mes_seguinte():
    """Um restart as 08:00:00 do dia 1 nao pode redisparar a rodada no mesmo instante."""
    agora = _sp(2026, 8, 1, 8, 0)
    assert proxima_execucao_mensal(agora, 8) == _sp(2026, 9, 1, 8)


def test_vira_o_ano():
    agora = _sp(2026, 12, 15, 10, 0)
    assert proxima_execucao_mensal(agora, 8) == _sp(2027, 1, 1, 8)


def test_atravessa_fevereiro():
    """Fevereiro tem 28/29 dias; o alvo e' sempre o dia 1, entao a virada nao depende
    do tamanho do mes — este teste trava isso contra uma implementacao com timedelta."""
    assert proxima_execucao_mensal(_sp(2026, 1, 20, 10, 0), 8) == _sp(2026, 2, 1, 8)
    assert proxima_execucao_mensal(_sp(2026, 2, 15, 10, 0), 8) == _sp(2026, 3, 1, 8)
    assert proxima_execucao_mensal(_sp(2028, 2, 29, 10, 0), 8) == _sp(2028, 3, 1, 8)


def test_horario_e_o_de_sao_paulo_nao_utc():
    """O container roda em UTC. 23:00 UTC = 20:00 em SP, entao o disparo e' as 8h de
    SP do dia 1, que sao 11:00 UTC."""
    agora = datetime(2026, 7, 31, 23, 0, tzinfo=UTC)
    alvo = proxima_execucao_mensal(agora, 8)
    assert alvo == _sp(2026, 8, 1, 8)
    assert alvo.astimezone(UTC).hour == 11


def test_segundos_bate_com_a_diferenca():
    agora = _sp(2026, 8, 1, 6, 0)
    assert segundos_ate_proxima_mensal(agora, 8) == 2 * 3600


def test_segundos_nunca_negativo():
    for hora_agora in range(24):
        agora = _sp(2026, 8, 1, hora_agora, 30)
        assert segundos_ate_proxima_mensal(agora, 8) > 0
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_agendamento.py -q`
Expected: FAIL — `ImportError: cannot import name 'proxima_execucao_mensal'`.

- [ ] **Step 3: Implementar**

Substitua **todo** o conteúdo de `backend/app/core/agendamento.py` por:

```python
"""Calculo de quando disparar o job mensal. Puro, sem I/O e sem dormir.

Separado do laco que de fato espera para que a regra de horario — a parte com
armadilha — possa ser testada sem relogio nem sleep.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

# O container roda em UTC; o horario do job e' o de operacao da Health Safety.
# Fixar o fuso aqui evita que "08:00" vire 05:00 da manha para quem trabalha.
TZ_SP = ZoneInfo("America/Sao_Paulo")


def proxima_execucao_mensal(agora: datetime, hora: int, minuto: int = 0) -> datetime:
    """O proximo dia 1 as `hora:minuto` no fuso de Sao Paulo, sempre no FUTURO.

    `agora` pode vir em qualquer fuso (o app roda em UTC) — e' convertido antes de
    comparar. Quando o horario ja passou, ou e' exatamente agora, vai para o mes
    seguinte: um restart exatamente as 08:00:00 do dia 1 nao deve disparar a rodada
    de novo no mesmo instante.

    O alvo e' sempre o dia 1, entao avancar o mes nunca cai em data invalida — e a
    conta nao depende de quantos dias o mes tem (nada de somar 30 dias).
    """
    agora_sp = agora.astimezone(TZ_SP)
    alvo = agora_sp.replace(day=1, hour=hora, minute=minuto, second=0, microsecond=0)
    if alvo <= agora_sp:
        if alvo.month == 12:
            alvo = alvo.replace(year=alvo.year + 1, month=1)
        else:
            alvo = alvo.replace(month=alvo.month + 1)
    return alvo


def segundos_ate_proxima_mensal(agora: datetime, hora: int, minuto: int = 0) -> float:
    """Quantos segundos dormir ate o proximo disparo. Sempre > 0."""
    return (proxima_execucao_mensal(agora, hora, minuto)
            - agora.astimezone(TZ_SP)).total_seconds()
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_agendamento.py -q`
Expected: PASS (9 testes).

> `pytest -q` inteiro ainda vai falhar neste ponto — `app/tarefas/vencendo.py` importa `segundos_ate_proxima`, que acabou de sair. Isso é esperado e é corrigido na Task 6. Rode só o arquivo desta task.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/agendamento.py backend/tests/test_agendamento.py
git commit -m "refactor(growthhs): agendamento passa a calcular o proximo dia 1 no lugar do proximo dia"
```

---

### Task 2: Montagem do card por cliente

**Files:**
- Modify: `backend/app/core/growthhs_vencendo.py` (arquivo inteiro)
- Test: `backend/tests/test_growthhs_vencendo.py` (reescrito)

**Interfaces:**
- Consumes: `montar_cliente`, `montar_contato`, `montar_device` de `app.core.growthhs_payload` (inalterados).
- Produces: `montar_card_vencendo(linhas: list[dict], competencia: date, board_id: int) -> dict`. `SOURCE_VENCENDO` continua `"gestorhs.calibracao"`.
  - `linhas` é uma lista de dicts `{cliente_id, cliente, ec, equipamento_desc, elo}` **de um mesmo cliente**, no formato que `buscar_vencendo` já devolve hoje. A função ordena internamente por `(prox_calibragem, ec.id)`, então não depende do chamador ter ordenado.
  - `competencia` é um `date` no dia 1 do mês.

- [ ] **Step 1: Escrever os testes que falham**

Substitua **todo** o conteúdo de `backend/tests/test_growthhs_vencendo.py` por:

```python
from datetime import date
from types import SimpleNamespace as NS

from app.core.growthhs_vencendo import SOURCE_VENCENDO, montar_card_vencendo

AGOSTO = date(2026, 8, 1)


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
    card = montar_card_vencendo([_linha()], AGOSTO, board_id=2)
    assert card["source"] == "gestorhs.calibracao"
    assert SOURCE_VENCENDO == "gestorhs.calibracao"


def test_external_id_e_por_cliente_mais_competencia():
    """A chave NAO depende da data da execucao NEM do aparelho: e' o que faz a rodada
    do mes seguinte devolver `created: false` para a competencia ja varrida."""
    card = montar_card_vencendo(
        [_linha(ec_id=77, prox=date(2026, 8, 3)),
         _linha(ec_id=78, prox=date(2026, 8, 20))], AGOSTO, board_id=2)
    assert card["external_id"] == "512:2026-08"


def test_external_id_muda_com_a_competencia():
    setembro = montar_card_vencendo([_linha(prox=date(2026, 9, 4))],
                                    date(2026, 9, 1), board_id=2)
    assert setembro["external_id"] == "512:2026-09"


def test_titulo_traz_cliente_quantidade_e_mes_por_extenso():
    card = montar_card_vencendo(
        [_linha(ec_id=77, prox=date(2026, 8, 3)),
         _linha(ec_id=78, prox=date(2026, 8, 20))], AGOSTO, board_id=2)
    assert card["title"] == "Calibração vencendo · ACME Ltda · 2 aparelhos · agosto/2026"


def test_titulo_no_singular_com_um_aparelho():
    card = montar_card_vencendo([_linha()], AGOSTO, board_id=2)
    assert card["title"] == "Calibração vencendo · ACME Ltda · 1 aparelho · agosto/2026"


def test_descricao_lista_os_aparelhos_na_ordem_de_vencimento():
    card = montar_card_vencendo(
        [_linha(ec_id=78, serie="SN-B", prox=date(2026, 8, 20)),
         _linha(ec_id=77, serie="SN-A", prox=date(2026, 8, 3))], AGOSTO, board_id=2)
    assert card["description"] == (
        "2 aparelhos deste cliente com calibração vencendo em agosto/2026:\n\n"
        "- HS PASS - IBLOW série SN-A — vence 03/08/2026\n"
        "- HS PASS - IBLOW série SN-B — vence 20/08/2026"
    )


def test_descricao_do_modulo_com_elo_mostra_o_phoebus_e_o_modulo():
    """O cliente reconhece o APARELHO, nao o numero do modulo — mesmo criterio do
    `montar_device`."""
    elo = NS(serie="WATFR01-00340", descricao="Phoebus")
    card = montar_card_vencendo([_linha(serie="F005065", elo=elo, prox=date(2026, 8, 9))],
                                AGOSTO, board_id=2)
    assert ("- Phoebus série WATFR01-00340 (módulo F005065) — vence 09/08/2026"
            in card["description"])


def test_descricao_sem_serie_nao_deixa_serie_orfa():
    card = montar_card_vencendo([_linha(serie=None, prox=date(2026, 8, 9))],
                                AGOSTO, board_id=2)
    assert "- HS PASS - IBLOW — vence 09/08/2026" in card["description"]
    assert "série " not in card["description"]


def test_descricao_nao_traz_dias_restantes():
    """O card vive o mes inteiro: 'em 12 dias' envelheceria mentindo."""
    card = montar_card_vencendo([_linha(prox=date(2026, 8, 20))], AGOSTO, board_id=2)
    assert "dia(s)" not in card["description"]
    assert "vence em" not in card["description"]


def test_due_date_e_o_vencimento_mais_proximo_do_grupo():
    """Prazo do card = prazo do aparelho mais urgente. Datetime COMPLETO: data pura
    devolve 422 (Pydantic v2 do GrowthHS: `Optional[datetime]`)."""
    card = montar_card_vencendo(
        [_linha(ec_id=78, prox=date(2026, 8, 20)),
         _linha(ec_id=77, prox=date(2026, 8, 3))], AGOSTO, board_id=2)
    assert card["due_date"] == "2026-08-03T00:00:00"


def test_devices_traz_todos_os_aparelhos_do_grupo():
    card = montar_card_vencendo(
        [_linha(ec_id=77, serie="SN-A", prox=date(2026, 8, 3)),
         _linha(ec_id=78, serie="SN-B", prox=date(2026, 8, 20))], AGOSTO, board_id=2)
    assert [d["serial_number"] for d in card["devices"]] == ["SN-A", "SN-B"]


def test_device_usa_o_elo_quando_presente():
    elo = NS(serie="WATFR01-00340", descricao="Phoebus")
    card = montar_card_vencendo([_linha(serie="F005065", elo=elo)], AGOSTO, board_id=2)
    dev = card["devices"][0]
    assert dev["serial_number"] == "WATFR01-00340"
    assert dev["alcohol_module"] == "F005065"


def test_contact_ausente_quando_cliente_sem_contato():
    card = montar_card_vencendo([_linha(cliente=_cliente(contato=None))],
                                AGOSTO, board_id=2)
    assert card["contact"] is None


def test_client_montado_com_external_id_do_id_interno():
    card = montar_card_vencendo([_linha(cliente=_cliente(id=1, nome="ACME Ltda"))],
                                AGOSTO, board_id=2)
    assert card["client"]["external_id"] == "1"
    assert card["client"]["name"] == "ACME Ltda"


def test_business_info():
    card = montar_card_vencendo(
        [_linha(ec_id=78, prox=date(2026, 8, 20)),
         _linha(ec_id=77, prox=date(2026, 8, 3))], AGOSTO, board_id=2)
    assert card["business_info"] == {
        "origem": "calibracao vencendo",
        "cliente_id": 512,
        "competencia": "2026-08",
        "qtd_aparelhos": 2,
        "equipamento_cliente_ids": [77, 78],
    }


def test_board_id_repassado():
    card = montar_card_vencendo([_linha()], AGOSTO, board_id=7)
    assert card["board_id"] == 7
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_growthhs_vencendo.py -q`
Expected: FAIL — a assinatura atual recebe uma linha só e um `hoje`; os erros serão `TypeError`/`AttributeError` e asserts quebrados.

- [ ] **Step 3: Implementar**

Substitua **todo** o conteúdo de `backend/app/core/growthhs_vencendo.py` por:

```python
"""Montagem do card de calibração VENCENDO do GrowthHS — um card por CLIENTE por mês.

Sem I/O: recebe linhas já lidas do banco e devolve o dict pronto para o cliente de
integração — mesma convenção de `core/growthhs_payload.py` e `core/growthhs_atrasados.py`.

Por que por cliente e não por aparelho: o comercial cobra todos os aparelhos do
cliente na primeira ligação; um card por aparelho obrigava a repetir o mesmo
fechamento em N cards. O agrupamento só é seguro porque a varredura virou MENSAL —
com a janela rolante diária de antes, o segundo aparelho a entrar na janela depois do
card já existir devolveria `created: false` e sumiria sem erro nenhum.
"""
from datetime import date

from app.core.growthhs_payload import montar_cliente, montar_contato, montar_device

SOURCE_VENCENDO = "gestorhs.calibracao"

# Nome do mês em PT-BR sem depender de `locale`, que varia com o que está instalado
# na imagem — em produção a imagem sobe pelo Dockerfile, onde não há garantia de
# locale pt_BR gerado.
MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho",
         "julho", "agosto", "setembro", "outubro", "novembro", "dezembro")


def _competencia_extenso(competencia: date) -> str:
    return f"{MESES[competencia.month - 1]}/{competencia.year}"


def _linha_descricao(linha: dict) -> str:
    """Uma linha da lista de aparelhos do card.

    Com elo, mostra o Phoebus e o módulo entre parênteses — mesmo critério do
    `montar_device`, pelo mesmo motivo: o cliente reconhece o aparelho, não o número
    do módulo.
    """
    ec = linha["ec"]
    elo = linha.get("elo")
    if elo is not None:
        descricao, serie, modulo = elo.descricao, elo.serie, ec.serie
    else:
        descricao, serie, modulo = linha["equipamento_desc"], ec.serie, None

    texto = (descricao or "").strip() or "Aparelho"
    if serie:
        texto += f" série {serie}"
    if modulo:
        texto += f" (módulo {modulo})"
    return f"- {texto} — vence {ec.prox_calibragem.strftime('%d/%m/%Y')}"


def montar_card_vencendo(linhas: list[dict], competencia: date, board_id: int) -> dict:
    """Monta o corpo do POST em `/api/v1/integration/service-cards` para TODOS os
    aparelhos de UM cliente que vencem na competência.

    `linhas` são dicts `{cliente_id, cliente, ec, equipamento_desc, elo}` de um mesmo
    cliente — o formato que `buscar_vencendo` devolve. `competencia` é um `date` no
    dia 1 do mês.
    """
    linhas = sorted(linhas, key=lambda l: (l["ec"].prox_calibragem, l["ec"].id))
    primeira = linhas[0]
    cliente = primeira["cliente"]
    cliente_id = primeira["cliente_id"]
    nome = getattr(cliente, "nome", None) or ""
    quantos = len(linhas)
    palavra = "aparelho" if quantos == 1 else "aparelhos"
    mes = _competencia_extenso(competencia)
    lista = "\n".join(_linha_descricao(linha) for linha in linhas)

    return {
        "source": SOURCE_VENCENDO,
        # A chave nao leva a data da execucao NEM o aparelho: e' o que torna a rodada
        # mensal idempotente. Como toda rodada varre mes corrente + seguinte, o mes de
        # tras ja tem card e volta `created: false`.
        "external_id": f"{cliente_id}:{competencia:%Y-%m}",
        "board_id": board_id,
        "title": f"Calibração vencendo · {nome} · {quantos} {palavra} · {mes}",
        "description": (
            f"{quantos} {palavra} deste cliente com calibração vencendo em {mes}:"
            f"\n\n{lista}"
        ),
        # O prazo do card e' o do aparelho MAIS URGENTE do grupo — quando a cobranca
        # precisa ter acontecido. datetime COMPLETO: `due_date` e' `Optional[datetime]`
        # no schema do GrowthHS e o Pydantic v2 recusa "YYYY-MM-DD" (422 real em 18/07/2026).
        "due_date": f"{linhas[0]['ec'].prox_calibragem.isoformat()}T00:00:00",
        "client": montar_cliente(cliente),
        "contact": montar_contato(cliente),
        "devices": [
            montar_device(l["ec"], l["equipamento_desc"], elo=l.get("elo")) for l in linhas
        ],
        "business_info": {
            "origem": "calibracao vencendo",
            "cliente_id": cliente_id,
            "competencia": f"{competencia:%Y-%m}",
            "qtd_aparelhos": quantos,
            "equipamento_cliente_ids": [l["ec"].id for l in linhas],
        },
    }
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_growthhs_vencendo.py -q`
Expected: PASS (17 testes).

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/growthhs_vencendo.py backend/tests/test_growthhs_vencendo.py
git commit -m "feat(growthhs): card de calibracao vencendo passa a ser por cliente e competencia"
```

---

### Task 3: Seleção por competência e agrupamento por cliente

**Files:**
- Modify: `backend/app/scripts/enviar_vencendo_growthhs.py` (`buscar_vencendo`; funções novas `_limites_da_competencia`, `agrupar_por_cliente`, `buscar_excluidos_por_os`)
- Test: `backend/tests/test_enviar_vencendo_growthhs.py` (parte de seleção)

**Interfaces:**
- Consumes: nada das tasks anteriores.
- Produces:
  - `buscar_vencendo(db: Session, competencia: date) -> list[dict]` — linhas `{cliente_id, cliente, ec, equipamento_desc, elo}`.
  - `agrupar_por_cliente(linhas: list[dict]) -> list[list[dict]]` — pura.
  - `buscar_excluidos_por_os(db: Session, competencia: date) -> list[dict]` — mesmas linhas, dos aparelhos com `os_atual` preenchido.
  - `_limites_da_competencia(competencia: date) -> tuple[date, date]`.
- A constante `DIAS_PADRAO` **sai**.

- [ ] **Step 1: Escrever os testes que falham**

Substitua **todo** o conteúdo de `backend/tests/test_enviar_vencendo_growthhs.py` pelo bloco abaixo. Os testes de `processar` e de `main` saem agora e **voltam nas Tasks 4 e 5**, já reescritos — assim cada task termina com o arquivo inteiro verde, em vez de arrastar falhas conhecidas entre commits.

```python
from datetime import date, timedelta

import pytest

from app.core.config import settings
from app.models import Cliente, Equipamento, EquipamentoCliente
from app.scripts.enviar_vencendo_growthhs import (
    agrupar_por_cliente,
    buscar_excluidos_por_os,
    buscar_vencendo,
    competencias_padrao,
)

HOJE = date.today()
# Competencia de teste: o mes que vem inteiro esta SEMPRE no futuro em relacao a
# `date.today()`, entao o `max(hoje, primeiro dia do mes)` do filtro nunca corta nada
# e o teste nao muda de resultado conforme o dia em que roda.
MES_QUE_VEM = (HOJE.replace(day=1) + timedelta(days=32)).replace(day=1)
MES_SEGUINTE = (MES_QUE_VEM + timedelta(days=32)).replace(day=1)
ULTIMO_DIA_DO_MES_QUE_VEM = MES_SEGUINTE - timedelta(days=1)


@pytest.fixture
def cliente(db_session):
    c = Cliente(nome="ACME Ltda")
    db_session.add(c); db_session.commit(); db_session.refresh(c)
    return c


@pytest.fixture
def outro_cliente(db_session):
    c = Cliente(nome="Beta SA")
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


def _ec(db_session, cliente_id, *, vence, equipamento=None, ativo=True, os_atual=None):
    ec = EquipamentoCliente(
        cliente=cliente_id,
        equipamento=equipamento if equipamento is not None else settings.EQUIPAMENTO_MODULO_ID,
        serie=f"SN-{vence.isoformat()}",
        prox_calibragem=vence, ativo=ativo, os_atual=os_atual,
    )
    db_session.add(ec); db_session.commit(); db_session.refresh(ec)
    return ec


def _ids(linhas):
    return {linha["ec"].id for linha in linhas}


def _dia(n):
    """Dia `n` do mes de teste."""
    return MES_QUE_VEM.replace(day=n)


# ---------------------------------------------------------------------------
# Selecao por competencia
# ---------------------------------------------------------------------------

def test_pega_dentro_da_competencia(db_session, cliente, equipamentos):
    dentro = _ec(db_session, cliente.id, vence=_dia(10))
    assert dentro.id in _ids(buscar_vencendo(db_session, MES_QUE_VEM))


def test_inclui_as_duas_bordas_do_mes(db_session, cliente, equipamentos):
    """Janela FECHADA nos dois lados: dia 1 entra, ultimo dia do mes entra."""
    primeiro = _ec(db_session, cliente.id, vence=_dia(1))
    ultimo = _ec(db_session, cliente.id, vence=ULTIMO_DIA_DO_MES_QUE_VEM)
    ids = _ids(buscar_vencendo(db_session, MES_QUE_VEM))
    assert primeiro.id in ids
    assert ultimo.id in ids


def test_ignora_o_mes_seguinte(db_session, cliente, equipamentos):
    """Cada competencia e' um card diferente; misturar meses quebraria a chave."""
    proximo = _ec(db_session, cliente.id, vence=MES_SEGUINTE)
    assert proximo.id not in _ids(buscar_vencendo(db_session, MES_QUE_VEM))


def test_ignora_vencidos(db_session, cliente, equipamentos):
    """Vencido e' backlog da Etapa 1 — incluir aqui geraria milhares de cards
    num formato diferente do que a Etapa 1 ja criou."""
    vencido = _ec(db_session, cliente.id, vence=HOJE - timedelta(days=1))
    assert vencido.id not in _ids(buscar_vencendo(db_session, HOJE.replace(day=1)))


def test_ignora_com_os_em_andamento(db_session, cliente, equipamentos):
    """Se o cliente ja mandou o aparelho, 'entre em contato' e' ruido."""
    em_os = _ec(db_session, cliente.id, vence=_dia(10), os_atual=12345)
    assert em_os.id not in _ids(buscar_vencendo(db_session, MES_QUE_VEM))


def test_ignora_inativo(db_session, cliente, equipamentos):
    inativo = _ec(db_session, cliente.id, vence=_dia(10), ativo=False)
    assert inativo.id not in _ids(buscar_vencendo(db_session, MES_QUE_VEM))


def test_ignora_phoebus_e_ebs(db_session, cliente, equipamentos):
    """Sao hospedeiros: nao sao calibrados, quem calibra e' o modulo dentro deles."""
    ph = _ec(db_session, cliente.id, vence=_dia(10),
             equipamento=settings.EQUIPAMENTO_PHOEBUS_ID)
    ebs = _ec(db_session, cliente.id, vence=_dia(11),
              equipamento=settings.EQUIPAMENTO_EBS_ID)
    ids = _ids(buscar_vencendo(db_session, MES_QUE_VEM))
    assert ph.id not in ids
    assert ebs.id not in ids


def test_ignora_cliente_de_estoque_interno(db_session, equipamentos):
    estoque = Cliente(id=settings.CLIENTE_ESTOQUE_HS_ID, nome="Estoque HS")
    db_session.add(estoque); db_session.commit()
    ec = _ec(db_session, settings.CLIENTE_ESTOQUE_HS_ID, vence=_dia(10))
    assert ec.id not in _ids(buscar_vencendo(db_session, MES_QUE_VEM))


# ---------------------------------------------------------------------------
# Agrupamento (puro)
# ---------------------------------------------------------------------------

def test_agrupa_por_cliente_e_ordena_por_vencimento(db_session, cliente, outro_cliente,
                                                    equipamentos):
    a2 = _ec(db_session, cliente.id, vence=_dia(20))
    a1 = _ec(db_session, cliente.id, vence=_dia(3))
    b1 = _ec(db_session, outro_cliente.id, vence=_dia(9))

    grupos = agrupar_por_cliente(buscar_vencendo(db_session, MES_QUE_VEM))

    assert [[l["ec"].id for l in g] for g in grupos] == [[a1.id, a2.id], [b1.id]]


def test_agrupar_lista_vazia():
    assert agrupar_por_cliente([]) == []


# ---------------------------------------------------------------------------
# Excluidos por OS — so entram no relatorio, nunca viram card
# ---------------------------------------------------------------------------

def test_excluidos_por_os_lista_quem_ficou_de_fora(db_session, cliente, equipamentos):
    em_os = _ec(db_session, cliente.id, vence=_dia(10), os_atual=10902)
    _ec(db_session, cliente.id, vence=_dia(11))
    excluidos = buscar_excluidos_por_os(db_session, MES_QUE_VEM)
    assert _ids(excluidos) == {em_os.id}


def test_excluidos_respeita_os_demais_filtros(db_session, cliente, equipamentos):
    inativo_em_os = _ec(db_session, cliente.id, vence=_dia(10), os_atual=1, ativo=False)
    assert inativo_em_os.id not in _ids(buscar_excluidos_por_os(db_session, MES_QUE_VEM))


# ---------------------------------------------------------------------------
# Competencias padrao
# ---------------------------------------------------------------------------

def test_competencias_padrao_sao_o_mes_corrente_e_o_seguinte():
    assert competencias_padrao(date(2026, 8, 14)) == [date(2026, 8, 1), date(2026, 9, 1)]


def test_competencias_padrao_viram_o_ano():
    assert competencias_padrao(date(2026, 12, 3)) == [date(2026, 12, 1), date(2027, 1, 1)]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_enviar_vencendo_growthhs.py -q`
Expected: FAIL — `ImportError: cannot import name 'agrupar_por_cliente'`.

- [ ] **Step 3: Implementar**

Em `backend/app/scripts/enviar_vencendo_growthhs.py`, remova a constante `DIAS_PADRAO = 50` e substitua a função `buscar_vencendo` inteira (da linha `def buscar_vencendo` até o `]` que fecha o return) por:

```python
def _limites_da_competencia(competencia: date) -> tuple[date, date]:
    """Primeiro e ultimo dia do mes da competencia.

    O inicio nunca e' anterior a hoje: se alguem rodar a mao no meio do mes, nao faz
    sentido "avisar" de um aparelho que ja venceu — isso e' backlog da Etapa 1.
    Na rodada automatica (dia 1) o `max` nao corta nada.
    """
    primeiro = competencia.replace(day=1)
    # Primeiro dia do mes seguinte menos um dia — nao depende de o mes ter 28/29/30/31.
    if primeiro.month == 12:
        proximo = primeiro.replace(year=primeiro.year + 1, month=1)
    else:
        proximo = primeiro.replace(month=primeiro.month + 1)
    return max(date.today(), primeiro), proximo - timedelta(days=1)


def _filtros_base(competencia: date):
    """Os filtros comuns a quem VIRA card e a quem foi EXCLUIDO por OS.

    Uma copia divergente destes filtros faria o relatorio de excluidos mentir — por
    isso mora num lugar so.
    """
    inicio, fim = _limites_da_competencia(competencia)
    return [
        EquipamentoCliente.ativo.is_(True),
        EquipamentoCliente.prox_calibragem.isnot(None),
        EquipamentoCliente.prox_calibragem >= inicio,
        EquipamentoCliente.prox_calibragem <= fim,
        EquipamentoCliente.equipamento.notin_(
            [settings.EQUIPAMENTO_PHOEBUS_ID, settings.EQUIPAMENTO_EBS_ID]
        ),
        EquipamentoCliente.cliente != settings.CLIENTE_ESTOQUE_HS_ID,
    ]


def _linhas(db: Session, ecs) -> list[dict]:
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


def buscar_vencendo(db: Session, competencia: date) -> list[dict]:
    """Uma linha por aparelho com calibracao vencendo NO MES da competencia.

    Cada linha: `{cliente_id, cliente, ec, equipamento_desc, elo}` — mesmo formato da
    Etapa 1, de proposito, para compartilhar `buscar_elo`.

    NAO inclui vencidos (`prox_calibragem < hoje`): esse backlog e' da Etapa 1.
    Exclui hospedeiros (Phoebus/EBS), o cliente de estoque interno da HS e aparelhos
    com OS em andamento (`os_atual` preenchido) — se o cliente ja mandou o aparelho,
    "entre em contato" e' ruido.
    """
    ecs = (
        db.query(EquipamentoCliente)
        .filter(*_filtros_base(competencia), EquipamentoCliente.os_atual.is_(None))
        .order_by(EquipamentoCliente.cliente,
                  EquipamentoCliente.prox_calibragem,
                  EquipamentoCliente.id)
        .all()
    )
    return _linhas(db, ecs)


def buscar_excluidos_por_os(db: Session, competencia: date) -> list[dict]:
    """Quem venceria na competencia mas ficou de fora por ter OS em andamento.

    So alimenta o relatorio — nao vira card. Existe porque a rodada e' uma FOTO UNICA
    do dia 1: quem estiver em OS naquele instante nao e' avisado naquele mes, e sem
    isso a omissao seria silenciosa.
    """
    ecs = (
        db.query(EquipamentoCliente)
        .filter(*_filtros_base(competencia), EquipamentoCliente.os_atual.isnot(None))
        .order_by(EquipamentoCliente.cliente,
                  EquipamentoCliente.prox_calibragem,
                  EquipamentoCliente.id)
        .all()
    )
    return _linhas(db, ecs)


def agrupar_por_cliente(linhas: list[dict]) -> list[list[dict]]:
    """Um grupo por cliente, ordenado por cliente e, dentro do grupo, por vencimento.

    Separado da query de proposito: e' regra pura e da' para testar sem banco.
    """
    grupos: dict[int, list[dict]] = {}
    for linha in linhas:
        grupos.setdefault(linha["cliente_id"], []).append(linha)
    return [
        sorted(grupo, key=lambda l: (l["ec"].prox_calibragem, l["ec"].id))
        for _, grupo in sorted(grupos.items())
    ]


def competencias_padrao(hoje: date) -> list[date]:
    """Mes corrente + mes seguinte — a janela de toda rodada.

    Sao dois meses porque o comercial precisa enxergar 2 meses a' frente. Na pratica
    so o mes de tras ja tem card (volta `created: false`), entao cada rodada cria de
    fato o mes novo da ponta. Nao ha env para isso: quem precisar de outra janela usa
    `--competencia` na mao.
    """
    corrente = hoje.replace(day=1)
    if corrente.month == 12:
        seguinte = corrente.replace(year=corrente.year + 1, month=1)
    else:
        seguinte = corrente.replace(month=corrente.month + 1)
    return [corrente, seguinte]
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_enviar_vencendo_growthhs.py -q`
Expected: PASS (14 testes).

- [ ] **Step 5: Commit**

```bash
git add backend/app/scripts/enviar_vencendo_growthhs.py backend/tests/test_enviar_vencendo_growthhs.py
git commit -m "feat(growthhs): selecao de vencendo passa a ser por competencia e agrupada por cliente"
```

---

### Task 4: Laço `processar` best-effort por cliente

**Files:**
- Modify: `backend/app/scripts/enviar_vencendo_growthhs.py` (`processar`, `_escrever_csv_pendencias`, helpers de relatório)
- Test: `backend/tests/test_enviar_vencendo_growthhs.py` (bloco de `processar`)

**Interfaces:**
- Consumes: `montar_card_vencendo(linhas, competencia, board_id)` (Task 2); `buscar_vencendo`, `buscar_excluidos_por_os`, `agrupar_por_cliente` (Task 3).
- Produces: `processar(db: Session, *, competencias: list[date], enviar: bool, limite: Optional[int] = None) -> dict` com as chaves `clientes`, `aparelhos`, `criados`, `existentes`, `falhas`, `pendencias`, `excluidos`. E `CAMPOS_RELATORIO: list[str]` (cabeçalho do CSV).

> `falhas` conta **clientes**, não aparelhos: a unidade de envio virou o cliente. `pendencias` continua com uma linha **por aparelho**, para o operador ver exatamente quem não foi comunicado.

- [ ] **Step 1: Escrever os testes que falham**

Acrescente `processar` ao import de `app.scripts.enviar_vencendo_growthhs` no topo do arquivo (a lista fica `agrupar_por_cliente, buscar_excluidos_por_os, buscar_vencendo, competencias_padrao, processar`) e **acrescente ao final** de `backend/tests/test_enviar_vencendo_growthhs.py`:

```python
# ---------------------------------------------------------------------------
# processar — best-effort POR CLIENTE
# ---------------------------------------------------------------------------

def _fake_envio(monkeypatch, resposta):
    enviados = []

    def enviar(card):
        enviados.append(card)
        return resposta(card) if callable(resposta) else resposta

    monkeypatch.setattr("app.scripts.enviar_vencendo_growthhs.enviar_card_sync", enviar)
    return enviados


def test_dry_run_nao_envia_mas_monta(db_session, cliente, equipamentos, monkeypatch):
    """A montagem acontece SEMPRE — e' assim que o dry-run valida o payload."""
    _ec(db_session, cliente.id, vence=_dia(10))
    enviados = _fake_envio(monkeypatch, {"created": True})
    r = processar(db_session, competencias=[MES_QUE_VEM], enviar=False)
    assert enviados == []
    assert r["clientes"] == 1
    assert r["aparelhos"] == 1
    assert r["criados"] == 0


def test_um_card_por_cliente_com_todos_os_aparelhos(db_session, cliente, outro_cliente,
                                                    equipamentos, monkeypatch):
    """O motivo da mudanca: 3 aparelhos do mesmo cliente = 1 card, nao 3."""
    for dia in (3, 10, 20):
        _ec(db_session, cliente.id, vence=_dia(dia))
    _ec(db_session, outro_cliente.id, vence=_dia(9))

    enviados = _fake_envio(monkeypatch, {"created": True})
    r = processar(db_session, competencias=[MES_QUE_VEM], enviar=True)

    assert len(enviados) == 2
    assert r["clientes"] == 2 and r["aparelhos"] == 4 and r["criados"] == 2
    por_chave = {c["external_id"]: c for c in enviados}
    assert len(por_chave[f"{cliente.id}:{MES_QUE_VEM:%Y-%m}"]["devices"]) == 3
    assert len(por_chave[f"{outro_cliente.id}:{MES_QUE_VEM:%Y-%m}"]["devices"]) == 1


def test_duas_competencias_geram_um_card_por_mes(db_session, cliente, equipamentos,
                                                 monkeypatch):
    """A rodada varre mes corrente + seguinte: o mesmo cliente ganha um card por mes,
    com chaves diferentes."""
    _ec(db_session, cliente.id, vence=_dia(10))
    _ec(db_session, cliente.id, vence=MES_SEGUINTE.replace(day=5))

    enviados = _fake_envio(monkeypatch, {"created": True})
    r = processar(db_session, competencias=[MES_QUE_VEM, MES_SEGUINTE], enviar=True)

    assert r["criados"] == 2
    assert {c["external_id"] for c in enviados} == {
        f"{cliente.id}:{MES_QUE_VEM:%Y-%m}",
        f"{cliente.id}:{MES_SEGUINTE:%Y-%m}",
    }


def test_competencia_ja_varrida_conta_como_existente(db_session, cliente, equipamentos,
                                                     monkeypatch):
    """`created: false` e' o mecanismo que faz a 2a rodada em diante subir so o mes
    novo da ponta — nao pode ser contado como criado nem como falha."""
    _ec(db_session, cliente.id, vence=_dia(10))
    _fake_envio(monkeypatch, {"created": False})
    r = processar(db_session, competencias=[MES_QUE_VEM], enviar=True)
    assert r["criados"] == 0
    assert r["existentes"] == 1
    assert r["falhas"] == 0


def test_falha_num_cliente_nao_aborta_os_outros(db_session, cliente, outro_cliente,
                                                equipamentos, monkeypatch):
    """Best-effort POR CLIENTE: um 422 num card nao pode derrubar a rodada."""
    _ec(db_session, cliente.id, vence=_dia(3))
    _ec(db_session, cliente.id, vence=_dia(4))
    _ec(db_session, outro_cliente.id, vence=_dia(9))

    def falha_no_primeiro(card):
        if card["external_id"].startswith(f"{cliente.id}:"):
            raise RuntimeError("GrowthHS respondeu 422: campo invalido")
        return {"created": True}

    _fake_envio(monkeypatch, falha_no_primeiro)
    r = processar(db_session, competencias=[MES_QUE_VEM], enviar=True)

    assert r["criados"] == 1
    assert r["falhas"] == 1                      # falha conta CLIENTE
    assert len(r["pendencias"]) == 2             # pendencia lista APARELHO
    assert all(p["tipo"] == "falha" for p in r["pendencias"])
    assert all("422" in p["motivo"] for p in r["pendencias"])
    assert {p["cliente_id"] for p in r["pendencias"]} == {cliente.id}


def test_excluidos_por_os_entram_no_relatorio_sem_virar_falha(db_session, cliente,
                                                              equipamentos, monkeypatch):
    em_os = _ec(db_session, cliente.id, vence=_dia(10), os_atual=10902)
    _ec(db_session, cliente.id, vence=_dia(11))
    _fake_envio(monkeypatch, {"created": True})

    r = processar(db_session, competencias=[MES_QUE_VEM], enviar=True)

    assert r["falhas"] == 0
    assert len(r["excluidos"]) == 1
    linha = r["excluidos"][0]
    assert linha["tipo"] == "excluido"
    assert linha["equipamento_cliente_id"] == em_os.id
    assert "10902" in linha["motivo"]
    assert linha["competencia"] == f"{MES_QUE_VEM:%Y-%m}"


def test_limite_corta_por_cliente(db_session, cliente, outro_cliente, equipamentos,
                                  monkeypatch):
    _ec(db_session, cliente.id, vence=_dia(3))
    _ec(db_session, cliente.id, vence=_dia(4))
    _ec(db_session, outro_cliente.id, vence=_dia(9))
    _fake_envio(monkeypatch, {"created": True})

    r = processar(db_session, competencias=[MES_QUE_VEM], enviar=True, limite=1)

    assert r["clientes"] == 1
    assert r["aparelhos"] == 2       # o limite corta CLIENTES, nao aparelhos
    assert r["criados"] == 1
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_enviar_vencendo_growthhs.py -q`
Expected: FAIL — `processar()` ainda tem a assinatura `dias=`, então `TypeError: processar() got an unexpected keyword argument 'competencias'` nos 7 testes novos.

- [ ] **Step 3: Implementar**

Em `backend/app/scripts/enviar_vencendo_growthhs.py`, substitua as funções `processar` e `_escrever_csv_pendencias` por:

```python
CAMPOS_RELATORIO = [
    "tipo", "competencia", "cliente_id", "equipamento_cliente_id",
    "serie", "prox_calibragem", "motivo",
]


def _linha_relatorio(linha: dict, competencia: date, tipo: str, motivo: str) -> dict:
    ec = linha["ec"]
    return {
        "tipo": tipo,
        "competencia": f"{competencia:%Y-%m}",
        "cliente_id": linha["cliente_id"],
        "equipamento_cliente_id": ec.id,
        "serie": getattr(ec, "serie", "") or "",
        "prox_calibragem": ec.prox_calibragem.isoformat(),
        "motivo": motivo,
    }


def processar(db: Session, *, competencias: list[date], enviar: bool,
              limite: Optional[int] = None) -> dict:
    """Manda um card por CLIENTE por competencia.

    Best-effort POR CLIENTE: uma excecao num card e' contada em `falhas`, cada
    aparelho daquele cliente vira uma linha em `pendencias` e o laco SEGUE para o
    proximo — nunca aborta a rodada inteira.

    `falhas` conta CLIENTES (a unidade de envio); `pendencias` lista APARELHOS, que e'
    o que o operador precisa para saber quem nao foi comunicado.
    """
    clientes = aparelhos = criados = existentes = falhas = 0
    pendencias: list[dict] = []
    excluidos: list[dict] = []

    for competencia in competencias:
        for linha in buscar_excluidos_por_os(db, competencia):
            excluidos.append(_linha_relatorio(
                linha, competencia, "excluido",
                f"OS em andamento (os_atual={linha['ec'].os_atual})",
            ))

        grupos = agrupar_por_cliente(buscar_vencendo(db, competencia))
        if limite is not None:
            grupos = grupos[:limite]

        for grupo in grupos:
            clientes += 1
            aparelhos += len(grupo)

            # Monta SEMPRE, inclusive em dry-run: e' assim que a simulacao cumpre o
            # que promete — validar que o payload de todo cliente consegue ser construido.
            try:
                card = montar_card_vencendo(grupo, competencia,
                                            settings.HSGROWTH_BOARD_COBRANCA)
            except Exception as exc:  # noqa: BLE001 — melhor esforco por cliente
                falhas += 1
                pendencias.extend(
                    _linha_relatorio(l, competencia, "falha",
                                     f"falha ao montar o card: {exc}") for l in grupo
                )
                continue

            if not enviar:
                continue      # dry-run: montou (validou) e para aqui, sem request

            try:
                resposta = enviar_card_sync(card)
            except Exception as exc:  # noqa: BLE001 — segue para o proximo cliente
                falhas += 1
                pendencias.extend(
                    _linha_relatorio(l, competencia, "falha", str(exc)) for l in grupo
                )
                continue

            if resposta.get("created"):
                criados += 1
            else:
                existentes += 1

    return {
        "clientes": clientes,
        "aparelhos": aparelhos,
        "criados": criados,
        "existentes": existentes,
        "falhas": falhas,
        "pendencias": pendencias,
        "excluidos": excluidos,
    }


def _escrever_csv_relatorio(caminho: str, linhas: list[dict]) -> None:
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CAMPOS_RELATORIO)
        writer.writeheader()
        for linha in linhas:
            writer.writerow(linha)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_enviar_vencendo_growthhs.py -q`
Expected: PASS (21 testes).

- [ ] **Step 5: Commit**

```bash
git add backend/app/scripts/enviar_vencendo_growthhs.py backend/tests/test_enviar_vencendo_growthhs.py
git commit -m "feat(growthhs): laco do job vencendo passa a ser best-effort por cliente"
```

---

### Task 5: CLI com `--competencia` e relatório de excluídos

**Files:**
- Modify: `backend/app/scripts/enviar_vencendo_growthhs.py` (docstring do módulo, `main`)
- Test: `backend/tests/test_enviar_vencendo_growthhs.py` (bloco de `main`)

**Interfaces:**
- Consumes: `processar(competencias=..., enviar=..., limite=...)` (Task 4), `competencias_padrao(hoje)` (Task 3), `CAMPOS_RELATORIO` e `_escrever_csv_relatorio` (Task 4).
- Produces: `main()` com `--competencia YYYY-MM` (repetível), `--dry-run`, `--limite N`, `--pendencias CAMINHO`. `--dias` **deixa de existir**.

- [ ] **Step 1: Escrever os testes que falham**

Acrescente `import sys` ao topo de `backend/tests/test_enviar_vencendo_growthhs.py` (primeira linha, antes do `from datetime import ...`) e **acrescente ao final** do arquivo:

```python
# ---------------------------------------------------------------------------
# main() — a COSTURA entre o argparse e o processar()
#
# `test_limite_corta_por_cliente` chama processar() direto e sempre passou, mas o
# main() esquecia de repassar `limite=args.limite`: quem rodasse `--limite 5` para um
# teste controlado enviaria a rodada INTEIRA (409 cards em 20/07/2026),
# irreversivelmente. Os testes daqui exercitam main() de ponta a ponta.
# ---------------------------------------------------------------------------

def _rodar_main(monkeypatch, tmp_path, argv, db_session):
    import app.scripts.enviar_vencendo_growthhs as mod

    recebido = {}
    real_processar = mod.processar

    def espiao(db, **kw):
        recebido.update(kw)
        return real_processar(db_session, **kw)

    monkeypatch.setattr(mod, "processar", espiao)
    monkeypatch.setattr(mod, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)
    monkeypatch.setattr(mod, "integracao_ativa", lambda: True)
    monkeypatch.setattr(mod, "enviar_card_sync", lambda card: {"created": True})
    monkeypatch.setattr(sys, "argv", ["enviar_vencendo_growthhs",
                                      "--pendencias", str(tmp_path / "p.csv"), *argv])
    mod.main()
    return recebido


def test_main_repassa_o_limite(db_session, cliente, equipamentos, monkeypatch, tmp_path):
    _ec(db_session, cliente.id, vence=_dia(10))
    recebido = _rodar_main(monkeypatch, tmp_path, ["--dry-run", "--limite", "2"], db_session)
    assert recebido["limite"] == 2


def test_main_repassa_competencias_e_dry_run(db_session, cliente, equipamentos,
                                             monkeypatch, tmp_path):
    _ec(db_session, cliente.id, vence=_dia(10))
    recebido = _rodar_main(
        monkeypatch, tmp_path,
        ["--dry-run", "--competencia", "2026-08", "--competencia", "2026-09"], db_session)
    assert recebido["competencias"] == [date(2026, 8, 1), date(2026, 9, 1)]
    assert recebido["enviar"] is False


def test_main_sem_competencia_usa_mes_corrente_e_seguinte(db_session, cliente,
                                                          equipamentos, monkeypatch,
                                                          tmp_path):
    _ec(db_session, cliente.id, vence=_dia(10))
    recebido = _rodar_main(monkeypatch, tmp_path, ["--dry-run"], db_session)
    assert recebido["competencias"] == competencias_padrao(date.today())


def test_main_recusa_competencia_malformada(db_session, monkeypatch, tmp_path):
    """Erro de digitacao tem que morrer no argparse, nao virar uma rodada vazia
    silenciosa."""
    import app.scripts.enviar_vencendo_growthhs as mod
    monkeypatch.setattr(mod, "integracao_ativa", lambda: True)
    monkeypatch.setattr(sys, "argv", ["enviar_vencendo_growthhs", "--dry-run",
                                      "--pendencias", str(tmp_path / "p.csv"),
                                      "--competencia", "agosto"])
    with pytest.raises(SystemExit) as saida:
        mod.main()
    assert saida.value.code == 2      # argparse


def test_main_envia_por_padrao_sem_dry_run(db_session, cliente, equipamentos,
                                           monkeypatch, tmp_path):
    """O default deste script e' ENVIAR — o inverso do de atrasados, de proposito."""
    _ec(db_session, cliente.id, vence=_dia(10))
    recebido = _rodar_main(monkeypatch, tmp_path, [], db_session)
    assert recebido["enviar"] is True
    assert recebido["limite"] is None


def test_main_imprime_falhas_no_stdout(db_session, cliente, equipamentos,
                                       monkeypatch, tmp_path, capsys):
    """Em producao a imagem sobe pelo Dockerfile sem bind mount, entao o CSV pode ser
    efemero. O stdout vai para o log do servico e e' o unico canal que sobrevive
    sempre — se as falhas sairem so no CSV, o job fica cego quando algo quebra."""
    import app.scripts.enviar_vencendo_growthhs as mod
    ec = _ec(db_session, cliente.id, vence=_dia(10))

    def sempre_falha(card):
        raise RuntimeError("GrowthHS respondeu 422: campo invalido")

    monkeypatch.setattr(mod, "enviar_card_sync", sempre_falha)
    monkeypatch.setattr(mod, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)
    monkeypatch.setattr(mod, "integracao_ativa", lambda: True)
    monkeypatch.setattr(sys, "argv", ["enviar_vencendo_growthhs",
                                      "--pendencias", str(tmp_path / "p.csv")])

    with pytest.raises(SystemExit) as saida:
        mod.main()

    assert saida.value.code == 1          # o operador precisa conseguir alertar
    impresso = capsys.readouterr().out
    assert f"aparelho={ec.id}" in impresso
    assert "422" in impresso


def test_main_grava_falhas_e_excluidos_no_mesmo_csv(db_session, cliente, equipamentos,
                                                    monkeypatch, tmp_path):
    import csv as csv_mod

    import app.scripts.enviar_vencendo_growthhs as mod
    _ec(db_session, cliente.id, vence=_dia(10), os_atual=10902)
    _ec(db_session, cliente.id, vence=_dia(11))

    caminho = tmp_path / "p.csv"
    monkeypatch.setattr(mod, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)
    monkeypatch.setattr(mod, "integracao_ativa", lambda: True)
    monkeypatch.setattr(mod, "enviar_card_sync", lambda card: {"created": True})
    monkeypatch.setattr(sys, "argv", ["enviar_vencendo_growthhs",
                                      "--pendencias", str(caminho),
                                      "--competencia", f"{MES_QUE_VEM:%Y-%m}"])
    mod.main()      # sem falha => sem SystemExit

    with open(caminho, encoding="utf-8") as f:
        linhas = list(csv_mod.DictReader(f))
    assert [l["tipo"] for l in linhas] == ["excluido"]
    assert linhas[0]["competencia"] == f"{MES_QUE_VEM:%Y-%m}"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_enviar_vencendo_growthhs.py -q -k main`
Expected: FAIL — `main()` ainda monta `--dias` e chama `processar(dias=...)`.

- [ ] **Step 3: Implementar**

Em `backend/app/scripts/enviar_vencendo_growthhs.py`:

**3a.** Troque o import `from datetime import date, timedelta` por (o `datetime` é usado pelo `strptime` do `_competencia`, logo abaixo):

```python
from datetime import date, datetime, timedelta
```

**3b.** Substitua a docstring do módulo (as linhas 1–18 do arquivo, do primeiro `"""` até o `"""` de fechamento) por:

```python
"""Job MENSAL: cria um card no board Cobranca do GrowthHS para cada CLIENTE com
aparelhos cuja calibracao vence na competencia — um card por cliente por mes.

Uso: python -m app.scripts.enviar_vencendo_growthhs [--competencia YYYY-MM ...]
     [--dry-run] [--limite N] [--pendencias CAMINHO.csv]

Roda sozinho dentro da API todo dia 1 as 8h (ver app/tarefas/vencendo.py e
docs/operacao-growthhs-job-mensal.md). Sem --competencia, cobre o mes corrente e o
seguinte.

PADRAO E' ENVIAR — ao contrario de `enviar_atrasados_growthhs`, que exige `--enviar`.
Nao e' inconsistencia: a chave daquele script leva a data da carga, entao repetir cria
duplicata irrecuperavel; a chave DESTE e' `{cliente_id}:{YYYY-MM}`, que nao muda com o
dia da execucao — rodar de novo devolve `created: false` e nao cria nada. Alem disso e'
um job agendado: um default que nao envia viraria um agendamento no-op silencioso, o
pior modo de falha possivel aqui.

O job e' BURRO e SEM ESTADO: roda todo mes sobre as duas competencias inteiras e nao
precisa lembrar o que ja mandou, porque a criacao e' idempotente. E' isso que faz a
primeira rodada subir 60 dias e as seguintes so o mes novo da ponta.
"""
```

**3c.** Substitua a função `main` inteira por:

```python
def _competencia(texto: str) -> date:
    """Converte `YYYY-MM` num `date` no dia 1. Erro de digitacao morre aqui, no
    argparse — nao pode virar uma rodada vazia silenciosa."""
    try:
        return datetime.strptime(texto, "%Y-%m").date()
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"competencia invalida: {texto!r} (use YYYY-MM, ex.: 2026-08)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Job mensal: cards de calibracao vencendo, um por cliente, "
                    "no board Cobranca do GrowthHS."
    )
    parser.add_argument("--competencia", type=_competencia, action="append", default=None,
                        metavar="YYYY-MM",
                        help="Mes de vencimento a cobrir; repetivel. "
                             "Padrao: mes corrente + mes seguinte.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simula: monta tudo e imprime o resumo, sem NENHUM request.")
    parser.add_argument("--limite", type=int, default=None,
                        help="Processa so os N primeiros CLIENTES — para um teste controlado")
    parser.add_argument("--pendencias", default=None, help="Caminho do CSV do relatorio")
    args = parser.parse_args()

    enviar = not args.dry_run
    competencias = args.competencia or competencias_padrao(date.today())

    if enviar and not integracao_ativa():
        print("ERRO: integracao com o GrowthHS esta DESLIGADA "
              "(configure HSGROWTH_BASE_URL e HSGROWTH_API_KEY) — abortando. "
              "Nada foi lido nem enviado.")
        raise SystemExit(1)

    caminho_relatorio = args.pendencias or str(
        _dir_relatorios() / f"pendencias-vencendo-growthhs-{date.today().isoformat()}.csv"
    )
    # Cria o diretorio ANTES de qualquer envio: um caminho invalido precisa falhar
    # rapido, nao depois de ja ter criado cards em producao.
    os.makedirs(os.path.dirname(caminho_relatorio) or ".", exist_ok=True)
    # Nao basta criar o diretorio: se ele ja existe mas pertence a outro usuario
    # (o container roda como root, entao `relatorios/` nasce root), o makedirs passa
    # e a falha so aparece no open() la embaixo — DEPOIS de os cards ja terem sido
    # enviados. Abrir agora, em modo append, transforma isso em falha imediata.
    try:
        open(caminho_relatorio, "a", encoding="utf-8").close()
    except OSError as exc:
        print(f"ERRO: nao consigo gravar o relatorio em {caminho_relatorio}: {exc}\n"
              f"Use --pendencias com um caminho gravavel. Nada foi enviado.")
        raise SystemExit(1)

    db = SessionLocal()
    try:
        r = processar(db, competencias=competencias, enviar=enviar, limite=args.limite)
    finally:
        db.close()

    _escrever_csv_relatorio(caminho_relatorio, r["pendencias"] + r["excluidos"])

    print(f"Competencias: {', '.join(f'{c:%Y-%m}' for c in competencias)}")
    print(f"Clientes: {r['clientes']} / Aparelhos: {r['aparelhos']}")
    if enviar:
        print(f"Criados: {r['criados']} / Ja existentes: {r['existentes']} / "
              f"Falhas: {r['falhas']}")
    else:
        print("MODO DRY-RUN — NADA FOI ENVIADO. Rode sem --dry-run para valer.")
    print(f"Excluidos por OS em andamento: {len(r['excluidos'])}")
    print(f"Relatorio gravado em: {caminho_relatorio}")

    # As falhas vao TAMBEM para o stdout, nao so para o CSV. Em producao a imagem
    # sobe pelo Dockerfile sem bind mount: se RELATORIOS_DIR nao apontar para um
    # volume persistente, o CSV some no redeploy. O stdout, que vai para o log do
    # servico, e' o unico canal que sobrevive sempre — e a falha e' a unica diagnose
    # que este job produz.
    for p in r["pendencias"]:
        print(f"  FALHA aparelho={p['equipamento_cliente_id']} cliente={p['cliente_id']} "
              f"serie={p['serie']} vence={p['prox_calibragem']}: {p['motivo']}")

    # Saida !=0 quando houve falha, para conseguir alertar. Excluido por OS NAO e'
    # falha: e' informacao operacional, o job funcionou como projetado.
    if r["falhas"]:
        raise SystemExit(1)
```

- [ ] **Step 4: Rodar o arquivo inteiro**

Run: `pytest tests/test_enviar_vencendo_growthhs.py -q`
Expected: PASS (todos).

- [ ] **Step 5: Commit**

```bash
git add backend/app/scripts/enviar_vencendo_growthhs.py backend/tests/test_enviar_vencendo_growthhs.py
git commit -m "feat(growthhs): cli do job vencendo troca --dias por --competencia e relata excluidos"
```

---

### Task 6: Worker mensal e limpeza da config

**Files:**
- Modify: `backend/app/tarefas/vencendo.py`
- Modify: `backend/app/core/config.py:20` (remove `JOB_VENCENDO_DIAS`)
- Test: `backend/tests/test_tarefa_vencendo.py`

**Interfaces:**
- Consumes: `segundos_ate_proxima_mensal` (Task 1); `processar(competencias=...)` e `competencias_padrao` (Tasks 3–5).
- Produces: `vencendo.iniciar(ciclos=None, dormir=None)` e `vencendo.loop_mensal(ciclos=None, dormir=None)` (era `loop_diario`), `vencendo._rodar_job()`.

- [ ] **Step 1: Ajustar os testes**

Em `backend/tests/test_tarefa_vencendo.py`:

**1a.** Adicione `from datetime import date` no topo (depois de `import asyncio`).

**1b.** Troque as duas ocorrências de `vencendo.loop_diario` por `vencendo.loop_mensal` (nos testes `test_roda_o_job_no_horario` e `test_falha_no_job_nao_mata_o_loop`).

**1c.** Substitua `test_rodar_job_usa_a_janela_configurada` inteiro por:

```python
def test_rodar_job_usa_o_mes_corrente_e_o_seguinte(monkeypatch):
    """O worker precisa chamar o MESMO processar() do script — nada de uma segunda
    copia da regra de selecao (o projeto ja se queimou com logica duplicada)."""
    chamadas = {}

    class FakeSession:
        def close(self):
            chamadas["fechou"] = True

    monkeypatch.setattr(vencendo, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(vencendo, "processar",
                        lambda db, **kw: chamadas.update(kw) or
                        {"clientes": 2, "aparelhos": 5, "criados": 2, "existentes": 0,
                         "falhas": 0, "pendencias": [], "excluidos": []})

    vencendo._rodar_job()

    hoje = date.today()
    corrente = hoje.replace(day=1)
    seguinte = (corrente.replace(year=corrente.year + 1, month=1)
                if corrente.month == 12 else corrente.replace(month=corrente.month + 1))
    assert chamadas["competencias"] == [corrente, seguinte]
    assert chamadas["enviar"] is True
    assert chamadas["fechou"] is True
```

**1d.** Remova a linha `monkeypatch.setattr(settings, "JOB_VENCENDO_DIAS", 50)` (estava dentro do teste substituído acima — confirme que não sobrou nenhuma referência a `JOB_VENCENDO_DIAS` no arquivo).

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_tarefa_vencendo.py -q`
Expected: FAIL — `ImportError: cannot import name 'segundos_ate_proxima'` (o módulo `app/tarefas/vencendo.py` ainda importa a função removida na Task 1).

- [ ] **Step 3: Implementar**

**3a.** Em `backend/app/core/config.py`, apague a linha:

```python
    JOB_VENCENDO_DIAS: int = 50
```

**3b.** Substitua **todo** o conteúdo de `backend/app/tarefas/vencendo.py` por:

```python
"""Worker mensal: dispara o job de calibracao vencendo de dentro da propria aplicacao.

Por que aqui e nao em cron: producao sobe no Easypanel a partir do Dockerfile, onde
agendar significa instalar cron na imagem ou depender de um servico externo. Como o
backend e' um servico unico e a criacao de card e' idempotente (a chave
`{cliente_id}:{YYYY-MM}` nao muda com a data da execucao), um agendador embutido sobe
junto com o deploy, sem passo de infraestrutura — e mesmo que rodasse duas vezes, nao
criaria card duplicado.

Roda todo dia 1 as 8h (SP) sobre o mes corrente + o mes seguinte. Como o mes de tras ja
foi varrido na rodada anterior, ele volta `created: false` e na pratica so nasce card do
mes novo da ponta — a primeira rodada sobe 60 dias, as seguintes 30.

Nasce DESLIGADO (`JOB_VENCENDO_ATIVO=false`): a maquina de desenvolvimento aponta para
o banco de producao com a chave real, entao ligar tem que ser decisao explicita de quem
faz o deploy.
"""
import asyncio
import logging
from datetime import date, datetime
from typing import Optional

from app.core.agendamento import TZ_SP, segundos_ate_proxima_mensal
from app.core.config import settings
from app.models.database import SessionLocal
from app.scripts.enviar_vencendo_growthhs import competencias_padrao, processar

logger = logging.getLogger(__name__)


def _rodar_job() -> None:
    """Uma execucao. Reusa o `processar` do script — a regra de selecao mora num
    lugar so; uma segunda copia aqui divergiria com o tempo."""
    db = SessionLocal()
    try:
        r = processar(db, competencias=competencias_padrao(date.today()), enviar=True)
    finally:
        db.close()

    logger.info(
        "job vencendo: %s clientes, %s aparelhos, %s criados, %s ja existentes, "
        "%s falhas, %s excluidos por OS",
        r["clientes"], r["aparelhos"], r["criados"], r["existentes"],
        r["falhas"], len(r["excluidos"]),
    )
    for p in r["pendencias"]:
        logger.error(
            "job vencendo FALHA aparelho=%s cliente=%s serie=%s vence=%s: %s",
            p["equipamento_cliente_id"], p["cliente_id"], p["serie"],
            p["prox_calibragem"], p["motivo"],
        )


async def loop_mensal(ciclos: Optional[int] = None, dormir=None) -> None:
    """Dorme ate o dia 1, roda, repete.

    `ciclos` limita as voltas e `dormir` troca o sleep — ambos so para teste. Sao
    parametros, e nao monkeypatch de `asyncio.sleep`, de proposito: `tarefas.asyncio`
    E' o modulo global, entao trocar `sleep` ali afeta o event loop inteiro, inclusive
    o do proprio teste (custou um RecursionError e um teste travado ate descobrir).
    """
    dormir = dormir or asyncio.sleep
    volta = 0
    while ciclos is None or volta < ciclos:
        espera = segundos_ate_proxima_mensal(datetime.now(TZ_SP),
                                             settings.JOB_VENCENDO_HORA)
        logger.info("job vencendo: proximo disparo em %.1f dias", espera / 86400)
        await dormir(espera)
        try:
            # Em thread separada: `processar` e' sincrono (SQLAlchemy + httpx) e
            # bloquearia o event loop da API por toda a duracao da carga.
            await asyncio.to_thread(_rodar_job)
        except Exception:
            # Nunca propagar: uma falha aqui mataria a task e o agendamento sumiria
            # em silencio ate o proximo restart. Loga e tenta de novo no mes que vem.
            logger.exception("job vencendo falhou; seguindo para o proximo mes")
        volta += 1


def iniciar(ciclos: Optional[int] = None, dormir=None) -> Optional[asyncio.Task]:
    """Cria a task de fundo, ou None se o job estiver desligado."""
    if not settings.JOB_VENCENDO_ATIVO:
        logger.info("job vencendo: DESLIGADO (JOB_VENCENDO_ATIVO=false)")
        return None
    logger.info("job vencendo: LIGADO, disparo todo dia 1 as %sh (SP)",
                settings.JOB_VENCENDO_HORA)
    return asyncio.create_task(loop_mensal(ciclos, dormir))
```

- [ ] **Step 4: Rodar a suíte inteira**

Run: `pytest -q`
Expected: PASS — **toda** a suíte, sem falha nem erro de coleta. Se algum arquivo ainda referenciar `JOB_VENCENDO_DIAS`, `loop_diario`, `segundos_ate_proxima` ou `DIAS_PADRAO`, corrija agora:

```bash
grep -rn "JOB_VENCENDO_DIAS\|loop_diario\|segundos_ate_proxima\b\|proxima_execucao\b\|DIAS_PADRAO" backend/app backend/tests
```
Expected: nenhuma saída.

- [ ] **Step 5: Commit**

```bash
git add backend/app/tarefas/vencendo.py backend/app/core/config.py backend/tests/test_tarefa_vencendo.py
git commit -m "feat(growthhs): worker do job vencendo passa a rodar todo dia 1 sobre duas competencias"
```

---

### Task 7: Documentação e changelog

**Files:**
- Rename + rewrite: `docs/operacao-growthhs-job-diario.md` → `docs/operacao-growthhs-job-mensal.md`
- Modify: `CLAUDE.md` (bloco de comandos do backend + os dois avisos sobre o job)
- Modify: `frontend/src/app/changelog/data.ts` (nova primeira entrada)

**Interfaces:**
- Consumes: o comportamento final das Tasks 1–6.
- Produces: nada de código.

- [ ] **Step 1: Renomear e reescrever o doc de operação**

```bash
git mv docs/operacao-growthhs-job-diario.md docs/operacao-growthhs-job-mensal.md
```

Substitua **todo** o conteúdo do arquivo novo por:

````markdown
# Operação — job mensal do GrowthHS (calibração vencendo)

Cria um card no board **Cobrança** (2) do GrowthHS para cada **cliente** com aparelhos
cuja calibração vence no mês. Um card por **cliente + mês de vencimento**, com todos os
aparelhos daquele cliente que vencem naquele mês.

## A cadência

Roda **todo dia 1, às 08:00 (São Paulo)**, sobre **duas competências: o mês corrente e o
mês seguinte**.

```
01/08 → competências agosto + setembro
        cliente 123 → cria "123:2026-08" e "123:2026-09"        (2 cards)

01/09 → competências setembro + outubro
        "123:2026-09" já existe → created:false, nada acontece
        "123:2026-10" é novo → cria                              (1 card)
```

A primeira rodada sobe **60 dias**; as seguintes, só o mês novo da ponta. Isso não é
uma regra no código — é consequência da chave `{cliente_id}:{YYYY-MM}`, que não muda com
a data da execução. O comercial fica sempre com **2 meses à frente** à vista, e cada
aparelho é avisado com **31 a 61 dias** de antecedência.

O job é **burro e sem estado**: não guarda o que já mandou. Rodar de novo é inofensivo.

## Por que um card por cliente

O comercial cobra todos os aparelhos do cliente **na primeira ligação**. Com um card por
aparelho, os cards seguintes chegavam depois de o assunto já estar resolvido e obrigavam
a repetir o mesmo fechamento N vezes.

O agrupamento só é seguro porque a varredura é **mensal**. Na janela rolante diária de
antes, o segundo aparelho a entrar na janela depois de o card do cliente já existir
voltaria `created: false` e sumiria sem erro nenhum.

## Ligar em produção

Nasce **desligado**. No Easypanel:

```
JOB_VENCENDO_ATIVO=true
```

E redeploy. Confirme no log do serviço:

```
INFO app.tarefas.vencendo: job vencendo: LIGADO, disparo todo dia 1 as 8h (SP)
```

Se aparecer `DESLIGADO (JOB_VENCENDO_ATIVO=false)`, a env não chegou ao container.

> Por que nasce desligado: a máquina de desenvolvimento aponta para o **banco de produção
> com a chave real**. Se o padrão fosse ligado, qualquer `docker compose up` local passaria
> a criar cards de verdade.

Outras envs (opcionais): `JOB_VENCENDO_HORA` (padrão `8`) e `RELATORIOS_DIR`.
**`JOB_VENCENDO_DIAS` não existe mais** — a janela não é medida em dias; pode ser
removida do Easypanel.

### Por que não cron

O backend é um serviço único no Easypanel e a criação de card é idempotente, então
execuções repetidas não duplicam nada. Cron custaria instalar cron na imagem ou depender
de um serviço externo; o worker embutido sobe junto com o deploy, sem passo de
infraestrutura.

## Rodar à mão

```bash
docker exec gestorhs-backend python -m app.scripts.enviar_vencendo_growthhs --dry-run
```

| Flag | Para quê |
|---|---|
| `--competencia YYYY-MM` | Mês a cobrir; **repetível**. Padrão: mês corrente + seguinte. |
| `--dry-run` | Monta tudo e mostra o resumo **sem enviar nada**. |
| `--limite N` | Processa só os N primeiros **clientes** — teste controlado. |
| `--pendencias CAMINHO` | Onde gravar o CSV do relatório. |

> ⚠️ Aqui o padrão é **enviar** (`--dry-run` para simular) — o contrário de
> `enviar_atrasados_growthhs`, que exige `--enviar`. É proposital: a chave deste job não
> depende da data da execução, então repetir é inofensivo; e um job agendado que não
> envia por padrão seria um agendamento silenciosamente inútil.

Adiantar a primeira rodada, sem esperar o dia 1:

```bash
docker exec gestorhs-backend python -m app.scripts.enviar_vencendo_growthhs \
  --competencia 2026-08 --competencia 2026-09 --dry-run
```

Confira o resumo e rode de novo sem `--dry-run`. A rodada automática do dia 1 seguinte
encontra tudo criado e só sobe o mês da ponta.

## Quando algo falha

O laço é best-effort **por cliente**: uma falha num card não derruba a rodada. O relatório
sai em **dois lugares** — no **stdout** (log do serviço, o canal que sempre sobrevive) e
num **CSV**:

```
tipo,competencia,cliente_id,equipamento_cliente_id,serie,prox_calibragem,motivo
falha,2026-08,123,77,SN-9,2026-08-03,GrowthHS respondeu 422: ...
excluido,2026-08,456,88,SN-1,2026-08-19,OS em andamento (os_atual=10902)
```

- **`falha`** — o card do cliente não foi criado. Uma linha por aparelho dele, com o
  corpo da resposta do GrowthHS, que é onde o 422 diz qual campo reprovou. O processo
  sai com código 1.
- **`excluido`** — o aparelho vence na competência mas tem **OS em andamento**, então
  não virou card ("entre em contato" é ruído para quem já mandou o aparelho). **Não é
  falha** e não afeta o código de saída; está no relatório porque a rodada é uma foto
  única do dia 1 e a omissão não pode ser silenciosa.

O CSV vai para `{UPLOAD_DIR}/relatorios/` — na prática `/data/uploads/relatorios/`, o
volume **persistente** que já existe nos dois ambientes. **Nada a configurar no deploy.**

```bash
docker exec gestorhs-backend ls /data/uploads/relatorios/
```

Como o job é idempotente, basta corrigir a causa e rodar de novo — ou esperar o próximo
dia 1, que reprocessa as competências inteiras.

## O que o job NÃO faz

- **Não pega vencidos** (`prox_calibragem < hoje`) — esse backlog foi a carga única da
  Etapa 1, em formato por cliente.
- **Não atualiza** cards existentes. O endpoint do GrowthHS é *create-or-return*, não
  upsert: o card é um retrato do momento em que foi criado. Se a data de calibração de um
  aparelho mudar depois, o card do mês não muda junto.
- **Não avisa** aparelho com OS em andamento no dia da rodada — sai no relatório como
  `excluido`.
- **Não pega quem entra na janela depois da rodada.** Aparelho cujo cliente já tem card
  daquele mês não é acrescentado a ele. Na prática o risco é baixo: quem está em
  laboratório sai com data +1 ano e deixa a janela sozinho.
````

- [ ] **Step 2: Atualizar o `CLAUDE.md`**

**2a.** No bloco de comandos do backend, troque as duas linhas do script de vencendo:

```
python -m app.scripts.enviar_vencendo_growthhs --dry-run          # SIMULA o job diario dos 50 dias
python -m app.scripts.enviar_vencendo_growthhs                    # roda o job dos 50 dias a mao
```

por:

```
python -m app.scripts.enviar_vencendo_growthhs --dry-run          # SIMULA o job mensal (mes corrente + seguinte)
python -m app.scripts.enviar_vencendo_growthhs                    # roda o job mensal a mao
```

**2b.** Substitua os dois blocos de citação (`> ℹ️`) sobre o job de vencendo — o que fala da chave `{equipamento_cliente_id}:{prox_calibragem}` e o que fala do job dos 50 dias — por:

```markdown
> ℹ️ **`enviar_vencendo_growthhs` ENVIA por padrao** (use `--dry-run` para simular) — o inverso
> do script de atrasados, de proposito. A chave e `{cliente_id}:{YYYY-MM}`, que **nao muda
> com a data da execucao**, entao repetir devolve `created: false` e nao duplica; alem disso o
> agendamento chama esse mesmo caminho, e um default que nao envia viraria um job inutil em
> silencio.

> ℹ️ **O job de vencendo roda sozinho dentro da API**, nao por cron: `app/tarefas/vencendo.py`
> cria uma task de fundo no lifespan que dispara **todo dia 1 as 8h** (fuso de SP) sobre o
> **mes corrente + o mes seguinte** — um card por CLIENTE por mes. Nasce DESLIGADO — ligue com
> `JOB_VENCENDO_ATIVO=true` no ambiente. Motivo do padrao: a maquina de desenvolvimento aponta
> para o banco de producao com a chave real. Detalhes em
> [docs/operacao-growthhs-job-mensal.md](docs/operacao-growthhs-job-mensal.md).
```

- [ ] **Step 3: Entrada no changelog**

Em `frontend/src/app/changelog/data.ts`, insira como **primeira** entrada do array `CHANGELOG` (antes da `1.26.0`):

```ts
  {
    versao: '1.27.0',
    data: '27/07/2026',
    itens: [
      { tipo: 'melhoria', texto: 'Os avisos de calibração vencendo enviados ao GrowthHS agora chegam agrupados: um card por cliente com todos os aparelhos que vencem naquele mês, no lugar de um card separado por aparelho. A verificação passou a ser mensal (todo dia 1) e cobre o mês corrente e o seguinte, então o comercial enxerga sempre dois meses à frente e cobra tudo de uma vez.' },
    ],
  },
```

- [ ] **Step 4: Verificar**

```bash
cd frontend && npx tsc -b --noEmit && cd ..
grep -rn "operacao-growthhs-job-diario" CLAUDE.md docs/*.md
```
Expected: `tsc` sem erro; o `grep` sem saída. A spec e este plano, em `docs/superpowers/`, citam o nome antigo de propósito (registro histórico) e por isso ficam fora do grep.

- [ ] **Step 5: Commit**

```bash
git add docs/operacao-growthhs-job-mensal.md CLAUDE.md frontend/src/app/changelog/data.ts
git commit -m "docs(changelog): v1.27.0 — job de calibracao vencendo mensal e por cliente"
```

---

## Verificação final

Depois da Task 7, antes de dar a entrega por concluída:

```bash
cd backend && source .venv/bin/activate
pytest -q                                    # suite inteira verde
grep -rn "JOB_VENCENDO_DIAS\|loop_diario\|DIAS_PADRAO" app tests    # sem saída
cd ../frontend && npm run lint && npx tsc -b --noEmit && npm run build
```

Um dry-run de verdade contra o banco real (o Erick roda; **não** rodar sem `--dry-run` sem combinar):

```bash
docker exec gestorhs-backend python -m app.scripts.enviar_vencendo_growthhs --dry-run
```

Conferir no resumo: número de clientes bem menor que o de aparelhos (é o ganho da mudança),
duas competências listadas, e a contagem de excluídos por OS fazendo sentido.
