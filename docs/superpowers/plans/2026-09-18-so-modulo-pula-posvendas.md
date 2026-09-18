# Só a caixa 100% Módulo pula o Pós-Vendas — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Estreitar o critério do desvio do Pós-Vendas para "todas as OS ativas da caixa são Módulo (47)", e devolver ao Pós-Vendas as 7 caixas de Phoebus+Módulo que o backfill de 18/09/2026 levou ao Financeiro por engano.

**Architecture:** `core/fluxo_modulo.py` passa a expor **dois** predicados em vez de um: `caixa_de_modulo` (`any(36 ou 47)`, inalterado, responde "bloqueia o card do TaskHS/GrowthHS?") e `caixa_pula_posvendas` (`all(== 47)`, novo, responde "pula o Pós-Vendas?"). Só o avanço da caixa e os dois scripts de Phoebus trocam de predicado; as três integrações não são tocadas. Um script novo de uso único reverte as 7 caixas.

**Tech Stack:** Python 3.12 · FastAPI · SQLAlchemy 2 · pytest (SQLite in-memory) · React 19 · TypeScript · Vitest

**Spec:** [docs/superpowers/specs/2026-09-18-so-modulo-pula-posvendas-design.md](../specs/2026-09-18-so-modulo-pula-posvendas-design.md)

## Global Constraints

- **Idioma do domínio é PT-BR.** Nomes de funções, variáveis, testes e mensagens em português. Comentários e docstrings **sem acentos** quando forem código novo em `app/` (padrão do repo nesses módulos); markdown e texto de tela podem ter acento.
- **Commits** em Conventional Commits, **português sem acentos**, assunto de **uma linha só**, sem corpo. Terminar com a linha de co-autoria exigida nesta sessão.
- **Nunca comparar fase por ID cru.** Usar as constantes de `os_workflow` e `posicao()`/`ORDEM_FASES`. O ID 10 (Financeiro) é numericamente maior que 7 e 8 mas vem antes deles.
- **Ids de catálogo:** Phoebus = `settings.EQUIPAMENTO_PHOEBUS_ID` (36), Módulo = `settings.EQUIPAMENTO_MODULO_ID` (47). **Sempre via `settings`**, lido na chamada — um set de módulo congelaria o valor no import e furaria o monkeypatch.
- **Scripts de manutenção SIMULAM por padrão** e só gravam com `--aplicar`.
- ⚠️ **As fixtures de client do `conftest.py` são o MESMO objeto.** Pedir `client` e `client_lab` na mesma assinatura de teste troca a identidade em silêncio. Peça uma só.
- **Baseline de teste desta máquina: 4 falhas pré-existentes** (`PermissionError` em `test_certificados_gerais.py` e `test_publico_certificado_geral.py`). Verde é **bater a baseline**, não zero. Confira a baseline ANTES de começar: `cd backend && source .venv/bin/activate && pytest -q 2>&1 | tail -3`.
- **Não commitar changelog nem bump de versão.** Ficou pendente de propósito: o Erick ainda não definiu o número, e a entrada vai cobrir a rota e esta correção juntas.

---

### Task 1: Núcleo — predicado novo e constante da fase 6

Aditiva: nada passa a usar `caixa_pula_posvendas` ainda, então toda a suíte continua verde no fim desta task.

**Files:**
- Modify: `backend/app/core/fluxo_modulo.py`
- Modify: `backend/app/core/os_workflow.py`
- Test: `backend/tests/test_fluxo_modulo.py`

**Interfaces:**
- Consumes: `settings.EQUIPAMENTO_MODULO_ID`, `settings.EQUIPAMENTO_PHOEBUS_ID`
- Produces: `fluxo_modulo.caixa_pula_posvendas(ordens) -> bool`; `os_workflow.FASE_POSVENDAS = 6`; `os_workflow.PROXIMA_SO_MODULO` (renomeado de `PROXIMA_MODULO`)

- [ ] **Step 1: Escrever os testes que falham**

Acrescente ao **fim** de `backend/tests/test_fluxo_modulo.py`:

```python
# --- quem pula o Pos-Vendas (correcao de 18/09/2026) ---

def test_pula_posvendas_so_modulo():
    """A UNICA composicao que nao passa pelo comercial: servico de bancada."""
    assert fluxo_modulo.caixa_pula_posvendas([_os(settings.EQUIPAMENTO_MODULO_ID)]) is True
    assert fluxo_modulo.caixa_pula_posvendas(
        [_os(settings.EQUIPAMENTO_MODULO_ID), _os(settings.EQUIPAMENTO_MODULO_ID)]) is True


def test_pula_posvendas_phoebus_com_modulo_nao_pula():
    """O bug: o par completo gera servico e precisa do aceite comercial. Sao 22 caixas
    na base, e no TaskHS elas param em 'LIBERADOS DO LABORATORIO', antes da lista
    'Servicos' — nao chegaram nem perto do Financeiro."""
    ordens = [_os(settings.EQUIPAMENTO_PHOEBUS_ID), _os(settings.EQUIPAMENTO_MODULO_ID)]
    assert fluxo_modulo.caixa_pula_posvendas(ordens) is False


def test_pula_posvendas_so_phoebus_nao_pula():
    """O aparelho sozinho tambem gera servico — decidido em 18/09/2026."""
    assert fluxo_modulo.caixa_pula_posvendas([_os(settings.EQUIPAMENTO_PHOEBUS_ID)]) is False


def test_pula_posvendas_mista_nao_pula():
    """Caixa mista cai fora por CONSTRUCAO. Antes precisava de um `all` separado no
    backfill para nao arrastar o aparelho normal; agora a regra ja exclui."""
    assert fluxo_modulo.caixa_pula_posvendas(
        [_os(1), _os(settings.EQUIPAMENTO_MODULO_ID)]) is False


def test_pula_posvendas_lista_vazia():
    """Caixa sem OS ativa nao tem para onde desviar."""
    assert fluxo_modulo.caixa_pula_posvendas([]) is False


def test_pula_posvendas_le_settings_na_chamada(monkeypatch):
    """Mesmo motivo de `equipamentos_de_modulo`: valor congelado no import furaria o
    override por env e o monkeypatch."""
    monkeypatch.setattr(settings, "EQUIPAMENTO_MODULO_ID", 999)
    assert fluxo_modulo.caixa_pula_posvendas([_os(999)]) is True
```

E **substitua** o teste `test_rotulo_concorda_com_caixa_de_modulo` (linhas 99-106) por:

```python
def test_desvio_implica_rotulo_de_modulo():
    """Antes era EQUIVALENCIA (`rotulo is not None` == `caixa_de_modulo`). Agora e'
    IMPLICACAO, nos dois sentidos uteis: quem desvia tem rotulo 'modulo' e tem card
    bloqueado. Ter rotulo NAO implica desviar — Phoebus+Modulo tem rotulo 'ambos' e
    segue pelo Pos-Vendas. Se a implicacao quebrar, o Financeiro passa a ver um badge
    que nao explica a fase em que a caixa esta."""
    casos = [[], [_os(1)], [_os(settings.EQUIPAMENTO_PHOEBUS_ID)],
             [_os(settings.EQUIPAMENTO_MODULO_ID)],
             [_os(1), _os(settings.EQUIPAMENTO_MODULO_ID)],
             [_os(settings.EQUIPAMENTO_PHOEBUS_ID), _os(settings.EQUIPAMENTO_MODULO_ID)]]
    for ordens in casos:
        if fluxo_modulo.caixa_pula_posvendas(ordens):
            assert fluxo_modulo.rotulo_modulo(ordens) == "modulo"
            assert fluxo_modulo.caixa_de_modulo(ordens) is True
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_fluxo_modulo.py -q
```
Esperado: FAIL com `AttributeError: module 'app.core.fluxo_modulo' has no attribute 'caixa_pula_posvendas'`.

- [ ] **Step 3: Implementar o predicado**

Em `backend/app/core/fluxo_modulo.py`, acrescente ao fim do arquivo:

```python
def caixa_pula_posvendas(ordens) -> bool:
    """True SO se todas as OS sao Modulo (47) — a unica composicao que nao passa
    pelo comercial.

    NAO confundir com `caixa_de_modulo`, logo acima: aquele e' `any(36 ou 47)` e
    responde outra pergunta ("vira card no TaskHS/GrowthHS?"). As duas respostas nao
    coincidem, e foi reaproveitar uma para a outra que mandou 7 caixas de
    Phoebus+Modulo direto ao Financeiro em 18/09/2026. Por isso este predicado e'
    batizado pelo que DECIDE, e nao pela composicao: `caixa_so_de_modulo` seria
    armadilha, porque "modulo" quer dizer coisas diferentes nos dois nomes.

    Recebe a lista de ordens JA FILTRADA pelo chamador, igual a `caixa_de_modulo`.
    Lista vazia devolve False: caixa sem OS ativa nao tem para onde desviar.
    """
    ativas = list(ordens)
    return bool(ativas) and all(
        getattr(o, "equipamento_catalogo", None) == settings.EQUIPAMENTO_MODULO_ID
        for o in ativas)
```

Ajuste também as docstrings que deixaram de ser verdade. No **docstring de módulo** (topo do arquivo), substitua a primeira linha `"""Modulo e Phoebus seguem um fluxo de servico proprio.` e o parágrafo seguinte por:

```python
"""Modulo e Phoebus tem regras proprias — duas, que NAO coincidem.

1. Caixa que contenha um deles nao vira card no TaskHS nem no GrowthHS
   (`caixa_de_modulo`, `any`). Consumido por `api/espelhamento.py` e
   `api/growthhs_cards.py`.
2. Caixa 100% Modulo nao passa pelo Pos-Vendas (`caixa_pula_posvendas`, `all`).
   Consumido por `api/caixas.py` e pelos scripts de Phoebus.

Ate 18/09/2026 a pergunta 2 reaproveitava o predicado da 1, e por isso caixa de
Phoebus+Modulo pulava o comercial sem dever. Logica pura, sem I/O.
"""
```

Na docstring de `caixa_de_modulo`, troque a primeira linha por:

```python
    """True se QUALQUER OS da lista e' de modulo/phoebus — bloqueia o CARD.

    Responde SO a pergunta das integracoes. Para o desvio do Pos-Vendas use
    `caixa_pula_posvendas`, que e' mais estreito.
```

Na docstring de `rotulo_modulo`, troque o parágrafo que começa em `Aparelho comum na mesma caixa nao muda o rotulo:` por:

```python
    Aparelho comum na mesma caixa nao muda o rotulo: o aviso e' sobre o que ha de
    Phoebus/modulo ali. O rotulo fala de COMPOSICAO, nao de desvio de fase — desde
    18/09/2026 so a caixa 100% Modulo desvia, e `rotulo_modulo` continua marcando
    Phoebus e o par. A implicacao que vale (e tem teste) e' a estreita: caixa que
    desvia tem rotulo 'modulo'.
```

- [ ] **Step 4: Rodar e ver passar**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_fluxo_modulo.py -q
```
Esperado: PASS, todos.

- [ ] **Step 5: Renomear o mapa e criar a constante da fase 6**

Em `backend/app/core/os_workflow.py`:

1. Acrescente a constante junto das outras, depois de `FASE_LABORATORIO = 5`:

```python
FASE_POSVENDAS = 6
```

2. Renomeie `PROXIMA_MODULO` para `PROXIMA_SO_MODULO` e reescreva o comentário acima dele:

```python
# Rota da caixa 100% Modulo: o servico de bancada dela nao passa pelo comercial, entao
# sai do laboratorio direto para o Financeiro. Mapa separado, e nao um `if` dentro de
# `proxima_fase`, para o fluxo inteiro continuar legivel de um olhar — do jeito que
# `PROXIMA` ja e. Quem decide qual mapa vale e' o chamador, via
# `fluxo_modulo.caixa_pula_posvendas`. Caixa com Phoebus dentro (sozinho ou com o
# modulo dele) usa `PROXIMA`, como qualquer outra.
PROXIMA_SO_MODULO = {4: 5, 5: 10, 10: 7, 7: 8}
```

3. Em `proxima_fase`, troque `PROXIMA_MODULO` por `PROXIMA_SO_MODULO` e a primeira linha da docstring por:

```python
    """Proxima fase no fluxo. `pula_posvendas` usa a rota da caixa 100% Modulo (5 -> 10).
```

4. Atualize as três referências ao nome antigo em comentários (nenhuma é código):

```bash
cd /home/ericks/github/GestorHS
sed -i 's/os_workflow\.PROXIMA_MODULO/os_workflow.PROXIMA_SO_MODULO/' backend/app/schemas/caixas.py backend/app/scripts/mover_phoebus_posvendas.py
sed -i 's/`PROXIMA_MODULO`/`PROXIMA_SO_MODULO`/' backend/tests/test_caixas_quadro_modulo.py
grep -rn "PROXIMA_MODULO" backend/ frontend/src/ || echo "nenhuma sobra"
```

Esperado do `grep`: `nenhuma sobra`.

- [ ] **Step 6: Rodar a suíte inteira**

```bash
cd backend && source .venv/bin/activate && pytest -q 2>&1 | tail -5
```
Esperado: mesma contagem de falhas da baseline (4). Esta task é aditiva — nada mudou de comportamento.

- [ ] **Step 7: Commit**

```bash
cd /home/ericks/github/GestorHS
git add backend/app/core/fluxo_modulo.py backend/app/core/os_workflow.py \
        backend/tests/test_fluxo_modulo.py backend/app/schemas/caixas.py \
        backend/app/scripts/mover_phoebus_posvendas.py backend/tests/test_caixas_quadro_modulo.py
git commit -m "$(cat <<'MSG'
refactor(caixas): predicado proprio para o desvio do pos-vendas

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

---

### Task 2: Ligar a rota nova no avanço da caixa

Aqui o comportamento muda. É o commit que conserta o bug.

**Files:**
- Modify: `backend/app/api/caixas.py:277-285`
- Test: `backend/tests/test_caixa_pula_posvendas.py` (reescrita da premissa)

**Interfaces:**
- Consumes: `fluxo_modulo.caixa_pula_posvendas(ordens) -> bool` (Task 1)
- Produces: nada novo — `POST /caixas/{id}/avancar` passa a devolver fase 6 para caixa com Phoebus

- [ ] **Step 1: Reescrever o teste para a regra nova**

Substitua **todo** o conteúdo de `backend/tests/test_caixa_pula_posvendas.py` por:

```python
"""So a caixa 100% Modulo sai do laboratorio direto para o Financeiro.

O servico de bancada do modulo nao passa pelo comercial. O aparelho Phoebus passa —
sozinho ou acompanhado do modulo dele — e por isso volta ao fluxo normal. Ate
18/09/2026 o criterio era o mesmo do bloqueio de card (`caixa_de_modulo`, `any`), e
7 caixas de Phoebus+Modulo foram parar no Financeiro sem aceite comercial.

O criterio agora e' `fluxo_modulo.caixa_pula_posvendas` (`all`).
"""
from app.core.config import settings
from app.models import Caixa, Cliente, Equipamento, EquipamentoCliente, Ordem


def _caixa_no_lab(db, *, catalogos, desfecho="concluido"):
    """Caixa em fase 5 com uma OS por id de catalogo em `catalogos`.

    Ids explicitos (nao autoincrement): a regra depende justamente deles. A lista
    permite montar a caixa Phoebus+Modulo, que e' o caso que o desvio NAO pega.
    """
    cli = Cliente(nome="Cliente Fluxo")
    db.add(cli); db.flush()
    cx = Caixa(obs="Caixa fluxo", fase=5)
    db.add(cx); db.flush()
    os_ids = []
    for cat in catalogos:
        eq = db.query(Equipamento).filter(Equipamento.id == cat).one_or_none()
        if eq is None:
            eq = Equipamento(id=cat, descricao=f"Equipamento {cat}")
            db.add(eq); db.flush()
        ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id,
                                serie=f"SER-{cat}-{len(os_ids)}")
        db.add(ec); db.flush()
        o = Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=5, situacao="E",
                  caixa=cx.id, desfecho_lab=desfecho)
        db.add(o); db.flush()
        os_ids.append(o.id)
    db.commit(); db.refresh(cx)
    return cx.id, os_ids


def test_caixa_so_de_modulo_vai_do_lab_direto_ao_financeiro(client_lab, db_session):
    cx_id, _ = _caixa_no_lab(db_session, catalogos=[settings.EQUIPAMENTO_MODULO_ID])
    r = client_lab.post(f"/caixas/{cx_id}/avancar", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["fase"] == 10
    assert all(o["fase"] == 10 for o in body["ordens"])   # fan-out acompanha


def test_caixa_de_phoebus_com_modulo_passa_pelo_posvendas(client_lab, db_session):
    """O bug de 18/09/2026. O par completo gera servico e precisa do aceite comercial —
    no TaskHS essas caixas param em 'LIBERADOS DO LABORATORIO', antes de 'Servicos'."""
    cx_id, _ = _caixa_no_lab(db_session, catalogos=[settings.EQUIPAMENTO_PHOEBUS_ID,
                                                   settings.EQUIPAMENTO_MODULO_ID])
    r = client_lab.post(f"/caixas/{cx_id}/avancar", json={})
    assert r.status_code == 200
    assert r.json()["fase"] == 6


def test_caixa_so_de_phoebus_passa_pelo_posvendas(client_lab, db_session):
    """O aparelho sozinho tambem gera servico."""
    cx_id, _ = _caixa_no_lab(db_session, catalogos=[settings.EQUIPAMENTO_PHOEBUS_ID])
    r = client_lab.post(f"/caixas/{cx_id}/avancar", json={})
    assert r.status_code == 200
    assert r.json()["fase"] == 6


def test_caixa_mista_passa_pelo_posvendas(client_lab, db_session):
    """Modulo + aparelho comum: o comum precisa do aceite, entao a caixa inteira vai."""
    cx_id, _ = _caixa_no_lab(db_session, catalogos=[settings.EQUIPAMENTO_MODULO_ID, 1])
    r = client_lab.post(f"/caixas/{cx_id}/avancar", json={})
    assert r.status_code == 200
    assert r.json()["fase"] == 6


def test_caixa_comum_continua_indo_para_posvendas(client_lab, db_session):
    """Controle positivo: sem ele, o desvio poderia valer para todo mundo e os
    testes acima passariam do mesmo jeito."""
    cx_id, _ = _caixa_no_lab(db_session, catalogos=[1])
    r = client_lab.post(f"/caixas/{cx_id}/avancar", json={})
    assert r.status_code == 200
    assert r.json()["fase"] == 6


def test_caixa_so_de_modulo_nao_ganha_aceite_ao_pular_posvendas(client_lab, db_session):
    """Aceite e' o registro da aprovacao comercial. Pulando a fase 6, ninguem
    aprovou nada — inventar `aceite=True` seria forjar um aval que nao houve."""
    cx_id, os_ids = _caixa_no_lab(db_session, catalogos=[settings.EQUIPAMENTO_MODULO_ID])
    assert client_lab.post(f"/caixas/{cx_id}/avancar", json={}).status_code == 200

    o = db_session.get(Ordem, os_ids[0])
    db_session.refresh(o)
    assert o.fase == 10
    assert o.aceite is not True
    assert o.data_aceite is None


def test_caixa_so_de_modulo_segue_o_fluxo_normal_do_financeiro_em_diante(client_lab, db_session):
    """Depois do desvio, a caixa volta a andar como qualquer outra: 10 -> 7 -> 8.
    Protege contra o desvio 'vazar' para as fases seguintes."""
    from app.core import os_workflow as wf
    cx_id, _ = _caixa_no_lab(db_session, catalogos=[settings.EQUIPAMENTO_MODULO_ID])
    assert client_lab.post(f"/caixas/{cx_id}/avancar", json={}).status_code == 200

    cx = db_session.get(Caixa, cx_id)
    db_session.refresh(cx)
    assert cx.fase == wf.FASE_FINANCEIRO
    assert wf.proxima_fase(cx.fase, pula_posvendas=True) == wf.FASE_PREPARANDO


def test_caixa_so_de_modulo_travada_no_lab_continua_travada(client_lab, db_session):
    """O desvio nao e' um atalho: aparelho sem desfecho ainda trava a saida do
    laboratorio, igual a qualquer caixa."""
    cx_id, _ = _caixa_no_lab(db_session, catalogos=[settings.EQUIPAMENTO_MODULO_ID],
                             desfecho="pendente")
    r = client_lab.post(f"/caixas/{cx_id}/avancar", json={})
    assert r.status_code == 409
    assert "faltam" in r.json()["detail"].lower()
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_caixa_pula_posvendas.py -q
```
Esperado: FAIL nos três testes de Phoebus (`assert 10 == 6`) — `test_caixa_de_phoebus_com_modulo_passa_pelo_posvendas`, `test_caixa_so_de_phoebus_passa_pelo_posvendas` e `test_caixa_mista_passa_pelo_posvendas`. Os demais passam.

- [ ] **Step 3: Trocar o predicado no avanço**

Em `backend/app/api/caixas.py`, substitua o bloco de comentário + a linha 284:

```python
    # Phoebus/Modulo tem fluxo proprio: sai do laboratorio direto para o Financeiro,
    # sem passar pelo comercial. Mesmo criterio que ja tira a caixa deles do board do
    # TaskHS/GrowthHS — uma fonte de verdade so para "isto e' servico de modulo".
    # `caixa_de_modulo` recebe a lista JA filtrada: aqui quem conta sao as OS ativas,
    # as mesmas que vao andar de fase logo abaixo.
    pula_posvendas = fluxo_modulo.caixa_de_modulo(ativas)
```

por:

```python
    # A caixa 100% Modulo sai do laboratorio direto para o Financeiro: o servico de
    # bancada dela nao passa pelo comercial. NAO e' o mesmo criterio que tira a caixa
    # do board do TaskHS/GrowthHS — aquele e' `caixa_de_modulo`, mais largo, e
    # reaproveita-lo aqui mandou 7 caixas de Phoebus+Modulo ao Financeiro sem aceite
    # em 18/09/2026. Recebe a lista JA filtrada: quem conta sao as OS ativas, as
    # mesmas que vao andar de fase logo abaixo.
    pula_posvendas = fluxo_modulo.caixa_pula_posvendas(ativas)
```

- [ ] **Step 4: Rodar e ver passar**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_caixa_pula_posvendas.py -q
```
Esperado: PASS, 9 testes.

Depois a suíte inteira, porque este passo muda comportamento:

```bash
pytest -q 2>&1 | tail -15
```
Esperado: **4 falhas, a baseline, nada mais.** Foi conferido antes de escrever este plano que nenhum outro teste depende da fase de destino de uma caixa de Phoebus: `test_mover_phoebus_posvendas.py` e `test_finalizar_caixas_phoebus.py` chamam os scripts direto (que ainda têm o `all` próprio, trocado na Task 3), e `test_taskhs_bloqueio_modulo.py` avança da fase 4 para a 5 — igual nas duas rotas — e só verifica que nada foi espelhado. Se aparecer falha em `test_taskhs_bloqueio_modulo.py` ou `test_growthhs_bloqueio_modulo.py`, **pare**: o bloqueio de card não deve mudar nesta entrega.

- [ ] **Step 5: Commit**

```bash
cd /home/ericks/github/GestorHS
git add backend/app/api/caixas.py backend/tests/test_caixa_pula_posvendas.py
git commit -m "$(cat <<'MSG'
fix(caixas): so a caixa 100% modulo pula o pos-vendas

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

---

### Task 3: Alinhar os dois scripts de Phoebus ao mesmo predicado

Aqui some a divergência `any`/`all` que precisou ser documentada em 18/09/2026.

**Files:**
- Modify: `backend/app/scripts/mover_phoebus_posvendas.py:46-66`
- Modify: `backend/app/scripts/finalizar_caixas_phoebus.py:52-67`
- Test: `backend/tests/test_mover_phoebus_posvendas.py`
- Test: `backend/tests/test_finalizar_caixas_phoebus.py`

**Interfaces:**
- Consumes: `fluxo_modulo.caixa_pula_posvendas(ordens) -> bool` (Task 1)
- Produces: nada novo. `caixas_alvo` de ambos passa a excluir caixa com Phoebus.

- [ ] **Step 1: Escrever os testes que falham**

⚠️ **Ordem importa.** Os dois arquivos importam as funções direto (`from app.scripts.X import caixas_alvo, processar`), então chame `caixas_alvo(...)`, **não** `modulo.caixas_alvo(...)`. E faça a troca em massa **antes** de acrescentar o teste novo, senão o `sed` desfaz o que você acabou de escrever.

1. Troque em massa o id de catálogo nos dois arquivos de teste — as caixas montadas ali são o **alvo**, e Phoebus deixou de ser alvo:

```bash
cd /home/ericks/github/GestorHS
sed -i 's/settings\.EQUIPAMENTO_PHOEBUS_ID/settings.EQUIPAMENTO_MODULO_ID/g' \
    backend/tests/test_mover_phoebus_posvendas.py
sed -i '20s/settings\.EQUIPAMENTO_PHOEBUS_ID/settings.EQUIPAMENTO_MODULO_ID/' \
    backend/tests/test_finalizar_caixas_phoebus.py
```

(No `test_finalizar_caixas_phoebus.py` só a linha 20 muda — é o default do helper `_caixa`. Confira: `sed -n '20p' backend/tests/test_finalizar_caixas_phoebus.py`.)

2. Em `backend/tests/test_mover_phoebus_posvendas.py`, substitua o bloco das linhas 37-43 (o `parametrize` e o teste) por um teste sem parametrize:

```python
def test_caixas_alvo_pega_so_modulo_parado_em_posvendas(db_session):
    cx_id, _ = _caixa(db_session, catalogo_id=settings.EQUIPAMENTO_MODULO_ID)
    assert [c.id for c in caixas_alvo(db_session)] == [cx_id]
```

3. Confira se `import pytest` (linha 7) ficou sem uso e, se ficou, remova a linha:

```bash
grep -n "pytest\." backend/tests/test_mover_phoebus_posvendas.py || sed -i '/^import pytest$/d' backend/tests/test_mover_phoebus_posvendas.py
```

4. Acrescente ao **fim** de `backend/tests/test_mover_phoebus_posvendas.py`:

```python
def test_caixas_alvo_ignora_caixa_com_phoebus(db_session):
    """O aparelho gera servico e precisa do aceite comercial. Era o bug: com o
    criterio antigo (`any`) o backfill levou 7 caixas de Phoebus+Modulo ao
    Financeiro."""
    _caixa(db_session, catalogo_id=settings.EQUIPAMENTO_PHOEBUS_ID)
    assert caixas_alvo(db_session) == []


def test_caixas_alvo_ignora_caixa_de_phoebus_com_modulo(db_session):
    """A composicao real das 7: o par completo na mesma caixa."""
    cx_id, _ = _caixa(db_session, catalogo_id=settings.EQUIPAMENTO_PHOEBUS_ID)
    cx = db_session.get(Caixa, cx_id)
    cli = db_session.query(Cliente).first()
    eq = db_session.query(Equipamento).filter(
        Equipamento.id == settings.EQUIPAMENTO_MODULO_ID).one_or_none()
    if eq is None:
        eq = Equipamento(id=settings.EQUIPAMENTO_MODULO_ID, descricao="Modulo")
        db_session.add(eq); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie="S-PAR-MOD")
    db_session.add(ec); db_session.flush()
    db_session.add(Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=cx.fase,
                         situacao="E", caixa=cx_id))
    db_session.commit()
    assert caixas_alvo(db_session) == []
```

5. Acrescente ao **fim** de `backend/tests/test_finalizar_caixas_phoebus.py`:

```python
def test_alvo_ignora_caixa_com_phoebus_no_financeiro(db_session):
    """Caixa com o aparelho dentro segue o fluxo dela — inclusive a que voltou para o
    Pos-Vendas na reversao de 18/09/2026."""
    _caixa(db_session, catalogo_id=settings.EQUIPAMENTO_PHOEBUS_ID)
    assert caixas_alvo(db_session, excluir=set()) == []
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_mover_phoebus_posvendas.py tests/test_finalizar_caixas_phoebus.py -q
```
Esperado: FAIL nos dois testes novos (`assert [<Caixa>] == []`).

- [ ] **Step 3: Trocar o predicado nos dois scripts**

Em `backend/app/scripts/mover_phoebus_posvendas.py`, substitua a função `caixas_alvo` inteira por:

```python
def caixas_alvo(db: Session) -> list[Caixa]:
    """Caixas em Pos-Vendas cujas OS ativas sao TODAS Modulo.

    Mesmo predicado do avanco em tempo real (`fluxo_modulo.caixa_pula_posvendas`) —
    nao ha mais duas versoes da regra. Ate 18/09/2026 este script usava um `all`
    proprio porque o avanco usava um `any` largo demais; com o criterio corrigido, a
    caixa com Phoebus e a caixa mista caem fora por construcao nos dois caminhos.

    Caixa sem nenhuma OS ativa tambem fica de fora: nao ha o que mover, e adiantar
    so a caixa deixaria uma fase 10 vazia.
    """
    alvo = []
    for cx in db.query(Caixa).filter(Caixa.fase == ORIGEM).order_by(Caixa.id).all():
        if fluxo_modulo.caixa_pula_posvendas(_ordens_ativas(cx)):
            alvo.append(cx)
    return alvo
```

Ajuste também a linha do log em `processar`, que diz "fluxo do Phoebus/Modulo":

```python
                          f"Caixa #{cx.id}: {ORIGEM} -> {DESTINO} "
                          f"(fluxo da caixa 100% Modulo nao passa por Pos-Vendas)")
```

⚠️ **Não** altere o texto que o backfill **já gravou** em produção — a Task 4 procura por `"nao passa por Pos-Vendas"`, que é substring comum às duas versões. Confira: o trecho novo também contém `nao passa por Pos-Vendas`.

Em `backend/app/scripts/finalizar_caixas_phoebus.py`, substitua o corpo de `caixas_alvo`:

```python
def caixas_alvo(db: Session, *, excluir: set[int]) -> list[Caixa]:
    """Caixas no Financeiro cujas OS ativas sao TODAS Modulo, menos `excluir`.

    Mesmo predicado do avanco (`fluxo_modulo.caixa_pula_posvendas`). Caixa com
    Phoebus dentro tem nota fiscal a receber e segue o fluxo dela, entao nunca entra
    aqui — nem se for passada em `--excluir` ao contrario.
    """
    alvo = []
    for cx in db.query(Caixa).filter(Caixa.fase == ORIGEM).order_by(Caixa.id).all():
        if cx.id in excluir:
            continue
        if fluxo_modulo.caixa_pula_posvendas(_ordens_ativas(cx)):
            alvo.append(cx)
    return alvo
```

E, no docstring de módulo desse arquivo, troque a linha `Alvo: caixas cujas OS ativas sao TODAS de Phoebus/Modulo e estao na fase 10. Caixa de` por `Alvo: caixas cujas OS ativas sao TODAS Modulo e estao na fase 10. Caixa de`.

- [ ] **Step 4: Rodar e ver passar**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_mover_phoebus_posvendas.py tests/test_finalizar_caixas_phoebus.py -q
```
Esperado: PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/ericks/github/GestorHS
git add backend/app/scripts/mover_phoebus_posvendas.py backend/app/scripts/finalizar_caixas_phoebus.py \
        backend/tests/test_mover_phoebus_posvendas.py backend/tests/test_finalizar_caixas_phoebus.py
git commit -m "$(cat <<'MSG'
refactor(caixas): scripts de phoebus usam o mesmo predicado do avanco

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

---

### Task 4: Script que devolve as 7 caixas ao Pós-Vendas

**Files:**
- Create: `backend/app/scripts/reverter_posvendas_phoebus_modulo.py`
- Test: `backend/tests/test_reverter_posvendas_phoebus_modulo.py`

**Interfaces:**
- Consumes: `fluxo_modulo.caixa_pula_posvendas` (Task 1), `os_workflow.FASE_POSVENDAS` e `FASE_FINANCEIRO` (Task 1), `app.api.ordens_acoes.registrar_log(db, ordem, usuario, texto)`
- Produces: `caixas_alvo(db) -> list[Caixa]`; `conferir(db, caixas) -> list[str]`; `processar(db, *, aplicar) -> dict`; `LoteSujo(Exception)`

- [ ] **Step 1: Escrever os testes que falham**

Crie `backend/tests/test_reverter_posvendas_phoebus_modulo.py`:

```python
"""Reversao do backfill: as caixas de Phoebus+Modulo voltam do Financeiro ao Pos-Vendas.

O alvo e' triplice de proposito — fase 10 E log do backfill E a regra nova dizendo que
nao devia ter desviado. So a fase pegaria caixa que chegou ao Financeiro sozinha; so o
log pegaria as 100% Modulo, que estao certas onde estao.
"""
import pytest

from app.api.ordens_acoes import registrar_log
from app.core.config import settings
from app.core import os_workflow as wf
from app.models import Caixa, Cliente, Equipamento, EquipamentoCliente, NotaFiscal, Ordem
from app.scripts import reverter_posvendas_phoebus_modulo as rev


def _caixa(db, *, catalogos, fase=10, com_log=True):
    """Caixa na fase informada, uma OS por id de catalogo, com o log do backfill."""
    cli = Cliente(nome="Cliente Rev")
    db.add(cli); db.flush()
    cx = Caixa(obs="Caixa rev", fase=fase)
    db.add(cx); db.flush()
    ordens = []
    for cat in catalogos:
        eq = db.query(Equipamento).filter(Equipamento.id == cat).one_or_none()
        if eq is None:
            eq = Equipamento(id=cat, descricao=f"Equipamento {cat}")
            db.add(eq); db.flush()
        ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id,
                                serie=f"S-{cx.id}-{cat}-{len(ordens)}")
        db.add(ec); db.flush()
        o = Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=fase, situacao="E",
                  caixa=cx.id)
        db.add(o); db.flush()
        ordens.append(o)
    if com_log:
        for o in ordens:
            registrar_log(db, o, None,
                          f"Caixa #{cx.id}: 6 -> 10 "
                          f"(fluxo do Phoebus/Modulo nao passa por Pos-Vendas)")
    db.commit(); db.refresh(cx)
    return cx.id, [o.id for o in ordens]


PAR = [settings.EQUIPAMENTO_PHOEBUS_ID, settings.EQUIPAMENTO_MODULO_ID]


def test_alvo_pega_phoebus_com_modulo_no_financeiro(db_session):
    cx_id, _ = _caixa(db_session, catalogos=PAR)
    assert [c.id for c in rev.caixas_alvo(db_session)] == [cx_id]


def test_alvo_ignora_caixa_so_de_modulo(db_session):
    """Essa desviou com razao: pela regra nova ela continua pulando o Pos-Vendas."""
    _caixa(db_session, catalogos=[settings.EQUIPAMENTO_MODULO_ID])
    assert rev.caixas_alvo(db_session) == []


def test_alvo_ignora_caixa_sem_o_log_do_backfill(db_session):
    """Caixa de aparelho comum que chegou ao Financeiro pelo fluxo normal nao e' erro."""
    _caixa(db_session, catalogos=[1], com_log=False)
    assert rev.caixas_alvo(db_session) == []


def test_alvo_ignora_caixa_em_outra_fase(db_session):
    """As 6 fechadas pelo ENC-ADM-20260918 ficam onde estao — decisao de 18/09/2026."""
    _caixa(db_session, catalogos=PAR, fase=8)
    assert rev.caixas_alvo(db_session) == []


def test_simula_por_padrao_sem_gravar(db_session):
    cx_id, os_ids = _caixa(db_session, catalogos=PAR)
    r = rev.processar(db_session, aplicar=False)
    assert r["caixas"] == 1 and r["ordens"] == 2

    db_session.expire_all()
    assert db_session.get(Caixa, cx_id).fase == wf.FASE_FINANCEIRO
    assert db_session.get(Ordem, os_ids[0]).fase == wf.FASE_FINANCEIRO


def test_aplicar_devolve_caixa_e_os_ao_posvendas(db_session):
    cx_id, os_ids = _caixa(db_session, catalogos=PAR)
    rev.processar(db_session, aplicar=True)

    db_session.expire_all()
    assert db_session.get(Caixa, cx_id).fase == wf.FASE_POSVENDAS
    assert all(db_session.get(Ordem, i).fase == wf.FASE_POSVENDAS for i in os_ids)


def test_aplicar_deixa_rastro_no_log_da_os(db_session):
    from app.models import LogOS
    _, os_ids = _caixa(db_session, catalogos=PAR)
    rev.processar(db_session, aplicar=True)

    textos = [l.texto for l in db_session.query(LogOS).filter(LogOS.os == os_ids[0]).all()]
    assert any("10 -> 6" in t for t in textos)


def test_recusa_lote_com_aceite(db_session):
    _, os_ids = _caixa(db_session, catalogos=PAR)
    o = db_session.get(Ordem, os_ids[0]); o.aceite = True; db_session.commit()

    with pytest.raises(rev.LoteSujo, match="aceite"):
        rev.processar(db_session, aplicar=False)


def test_recusa_lote_com_nota_fiscal_da_caixa(db_session):
    cx_id, _ = _caixa(db_session, catalogos=PAR)
    db_session.add(NotaFiscal(caixa=cx_id, numero="123",
                              arquivo="a.pdf", arquivo_xml="a.xml"))
    db_session.commit()

    with pytest.raises(rev.LoteSujo, match="nota fiscal"):
        rev.processar(db_session, aplicar=False)


def test_idempotente_segunda_rodada_nao_acha_nada(db_session):
    _caixa(db_session, catalogos=PAR)
    rev.processar(db_session, aplicar=True)
    assert rev.processar(db_session, aplicar=True)["caixas"] == 0
```

⚠️ **Antes do Step 2**, confirme os nomes das colunas de `NotaFiscal` — o teste acima assume `caixa`, `numero`, `arquivo`, `arquivo_xml`:

```bash
cd /home/ericks/github/GestorHS && sed -n '19,35p' backend/app/models/nota_fiscal.py
```
Se divergirem, ajuste a chamada no teste (só nomes de coluna, a lógica não muda).

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_reverter_posvendas_phoebus_modulo.py -q
```
Esperado: FAIL na coleta com `ModuleNotFoundError: No module named 'app.scripts.reverter_posvendas_phoebus_modulo'`.

- [ ] **Step 3: Escrever o script**

Crie `backend/app/scripts/reverter_posvendas_phoebus_modulo.py`:

```python
"""Devolve ao Pos-Vendas as caixas de Phoebus+Modulo que o backfill levou ao Financeiro.

`mover_phoebus_posvendas` rodou em 18/09/2026 com o criterio largo (`any` de
Phoebus/Modulo) e moveu 39 caixas de 6 -> 10. Pela regra correta — so a caixa 100%
Modulo pula o Pos-Vendas — 7 delas nao deviam ter saido: 1003, 1011, 1028, 1030, 1043,
1047 e 1049, todas Phoebus+Modulo. No TaskHS os cards dessas 7 estao parados em
"LIBERADOS DO LABORATORIO" (lista 202), antes ainda de "Servicos" (203): elas nao
passaram por servico nem pelo comercial.

CRITERIO (triplice, auto-limitante):
  - caixa na fase 10 (Financeiro), E
  - com o log do backfill em alguma OS dela (MARCA_BACKFILL), E
  - `not fluxo_modulo.caixa_pula_posvendas(ativas)` — a regra nova diz que ela nao
    devia ter desviado.

RECUSA O LOTE INTEIRO se achar `aceite`, `pago` ou nota fiscal em qualquer caixa alvo:
seria caixa que o Financeiro ja trabalhou, e voltar ao Pos-Vendas desfaria o trabalho.
Conferido em 18/09/2026: as 7 estao zeradas nos cinco campos.

NAO fala com TaskHS nem GrowthHS: essas caixas nunca tiveram card espelhado (o gate de
modulo bloqueia), e os cards que existem no board foram feitos a mao.

As 6 caixas de Phoebus+Modulo ja fechadas pelo ENC-ADM-20260918 NAO sao tocadas: estao
na fase 8, ja foram despachadas e o cliente recebeu.

SIMULA POR PADRAO. Para gravar: --aplicar

    python -m app.scripts.reverter_posvendas_phoebus_modulo
    python -m app.scripts.reverter_posvendas_phoebus_modulo --aplicar

Para achar o que esta rodada fez:

    select * from logs_os where texto like '%10 -> 6 (Phoebus%';
"""
import argparse

from sqlalchemy.orm import Session

from app.api.ordens_acoes import registrar_log
from app.core import fluxo_modulo
from app.core import os_workflow as wf
from app.models import Caixa, LogOS, NotaFiscal
from app.models.database import SessionLocal

ORIGEM = wf.FASE_FINANCEIRO     # 10
DESTINO = wf.FASE_POSVENDAS     # 6

# Trecho do log gravado por `mover_phoebus_posvendas`. E' o que amarra o alvo AQUELE
# lote, e nao a qualquer caixa que tenha chegado ao Financeiro por conta propria.
MARCA_BACKFILL = "nao passa por Pos-Vendas"


class LoteSujo(Exception):
    """Alguma caixa alvo ja foi trabalhada pelo Financeiro. Nada e' gravado."""


def _ordens_ativas(caixa: Caixa) -> list:
    return [o for o in caixa.ordens if wf.eh_ativa(o.fase)]


def _veio_do_backfill(db: Session, caixa: Caixa) -> bool:
    ids = [o.id for o in caixa.ordens]
    if not ids:
        return False
    return db.query(LogOS).filter(
        LogOS.os.in_(ids), LogOS.texto.like(f"%{MARCA_BACKFILL}%")).first() is not None


def caixas_alvo(db: Session) -> list[Caixa]:
    """Caixas do backfill que, pela regra nova, nao deviam ter saido do Pos-Vendas."""
    alvo = []
    for cx in db.query(Caixa).filter(Caixa.fase == ORIGEM).order_by(Caixa.id).all():
        ativas = _ordens_ativas(cx)
        if not ativas or fluxo_modulo.caixa_pula_posvendas(ativas):
            continue
        if _veio_do_backfill(db, cx):
            alvo.append(cx)
    return alvo


def conferir(db: Session, caixas: list[Caixa]) -> list[str]:
    """Motivos para NAO reverter. Lista vazia = lote limpo."""
    problemas = []
    for cx in caixas:
        for o in _ordens_ativas(cx):
            if o.aceite:
                problemas.append(f"caixa {cx.id}: OS {o.id} ja tem aceite")
            if o.pago:
                problemas.append(f"caixa {cx.id}: OS {o.id} ja esta paga")
            if o.nota_fiscal:
                problemas.append(f"caixa {cx.id}: OS {o.id} tem nota fiscal legada")
        if db.query(NotaFiscal).filter(NotaFiscal.caixa == cx.id).first() is not None:
            problemas.append(f"caixa {cx.id}: ja tem nota fiscal anexada")
    return problemas


def processar(db: Session, *, aplicar: bool) -> dict:
    """Devolve as caixas alvo ao Pos-Vendas. Sem `aplicar`, so conta e descreve."""
    caixas = caixas_alvo(db)
    problemas = conferir(db, caixas)
    if problemas:
        raise LoteSujo("; ".join(problemas))

    detalhes = []
    total_ordens = 0
    for cx in caixas:
        ativas = _ordens_ativas(cx)
        total_ordens += len(ativas)
        detalhes.append({
            "caixa": cx.id,
            "ordens": [o.id for o in ativas],
            "cliente": next((o.cliente_nome for o in ativas if o.cliente_nome), None),
        })
        if not aplicar:
            continue
        for o in ativas:
            o.fase = DESTINO
            registrar_log(db, o, None,
                          f"Caixa #{cx.id}: {ORIGEM} -> {DESTINO} "
                          f"(Phoebus+Modulo passa pelo Pos-Vendas: reversao do "
                          f"backfill de 18/09/2026)")
        cx.fase = DESTINO

    if aplicar:
        db.commit()

    return {"caixas": len(caixas), "ordens": total_ordens, "detalhes": detalhes}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--aplicar", action="store_true",
                    help="grava de fato (sem isso, so simula)")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        r = processar(db, aplicar=args.aplicar)
    except LoteSujo as e:
        print(f"RECUSADO, nada foi gravado: {e}")
        raise SystemExit(1)
    finally:
        db.close()

    for d in r["detalhes"]:
        print(f"  caixa {d['caixa']:>5}  {len(d['ordens'])} OS  {d['cliente'] or '?'}")
    acao = "revertidas" if args.aplicar else "a reverter (SIMULACAO)"
    print(f"\n{r['caixas']} caixas / {r['ordens']} OS {acao}: {ORIGEM} -> {DESTINO}")
    if not args.aplicar:
        print("Rode de novo com --aplicar para gravar.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Rodar e ver passar**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_reverter_posvendas_phoebus_modulo.py -q
```
Esperado: PASS, 10 testes.

- [ ] **Step 5: Rodar a suíte inteira**

```bash
cd backend && source .venv/bin/activate && pytest -q 2>&1 | tail -5
```
Esperado: 4 falhas (a baseline), nada mais.

- [ ] **Step 6: Commit**

```bash
cd /home/ericks/github/GestorHS
git add backend/app/scripts/reverter_posvendas_phoebus_modulo.py \
        backend/tests/test_reverter_posvendas_phoebus_modulo.py
git commit -m "$(cat <<'MSG'
feat(caixas): script devolve ao pos-vendas a caixa de phoebus com modulo

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

---

### Task 5: Frontend — badge de composição em qualquer coluna

**Files:**
- Modify: `frontend/src/app/ordens/OrdensPage.tsx:126-133` e `:155-163`
- Test: `frontend/src/app/ordens/OrdensPage.modulo.test.tsx`

**Interfaces:**
- Consumes: campo `modulo?: 'phoebus' | 'modulo' | 'ambos' | null` de `caixas/api.ts:87` (inalterado)
- Produces: nada — só renderização

- [ ] **Step 1: Inverter o teste do escopo do badge**

Em `frontend/src/app/ordens/OrdensPage.modulo.test.tsx`:

1. Substitua o docstring do topo (linhas 1-7) por:

```tsx
/**
 * Badge de Phoebus/Modulo no quadro de Ordens.
 *
 * O badge fala de COMPOSICAO da caixa, nao de desvio de fase: diz o que ela leva
 * dentro, e portanto que o card dela no TaskHS e' feito a mao. Desde 18/09/2026 so a
 * caixa 100% Modulo pula o Pos-Vendas, entao amarrar o badge ao Financeiro esconderia
 * a informacao justamente das caixas de Phoebus, que seguem o fluxo normal.
 */
```

2. Substitua o `describe` da linha 34 por `describe('badge de Phoebus/Modulo no quadro', () => {`.

3. Substitua o último teste (`'nao mostra aviso fora do Financeiro, mesmo sendo caixa de modulo'`) por:

```tsx
  it('mostra o badge fora do Financeiro tambem', async () => {
    // Phoebus+Modulo passa pelo Pos-Vendas como qualquer caixa, e no Laboratorio ou
    // no Pos-Vendas continua sendo util saber o que ela carrega.
    quadro.mockResolvedValue([{
      fase: 5, descricao: 'Laboratório', cor: 'abc', total: 1,
      caixas: [{ id: 900, cliente_nome: 'ACME', total_os: 1, prontos: 1,
                 pendentes: 0, modulo: 'ambos' }],
    }])
    tela()
    expect(await screen.findByText('CX 900')).toBeInTheDocument()
    expect(screen.getByText('Phoebus + Módulo')).toBeInTheDocument()
  })
```

4. No teste `'mostra os dois quando a caixa leva aparelho e modulo juntos'`, troque o comentário `// Caso mais comum no Financeiro: 7 das 8 caixas em 18/09/2026.` por `// 22 caixas na base. Desde 18/09/2026 elas passam pelo Pos-Vendas, nao pulam.`

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd frontend && npx vitest run src/app/ordens/OrdensPage.modulo.test.tsx
```
Esperado: FAIL em `mostra o badge fora do Financeiro tambem` — `Unable to find an element with the text: Phoebus + Módulo`.

- [ ] **Step 3: Soltar o badge da coluna do Financeiro**

Em `frontend/src/app/ordens/OrdensPage.tsx`, substitua o bloco das linhas 126-133:

```tsx
                      {col.fase === 10 && cx.modulo && (
                        <span
                          className="text-xs px-2 py-0.5 rounded-full bg-violet-500/15 text-violet-300 shrink-0"
                          title="Caixa de Phoebus: o serviço dele não passa pelo Pós-Vendas, por isso chegou direto ao Financeiro."
                        >
                          {ROTULO_MODULO[cx.modulo]}
                        </span>
                      )}
```

por:

```tsx
                      {cx.modulo && (
                        <span
                          className="text-xs px-2 py-0.5 rounded-full bg-violet-500/15 text-violet-300 shrink-0"
                          title="O que esta caixa carrega. Caixa com Phoebus ou módulo não vira card automático no TaskHS — o card dela é feito à mão. Só a caixa 100% módulo pula o Pós-Vendas."
                        >
                          {ROTULO_MODULO[cx.modulo]}
                        </span>
                      )}
```

E substitua o comentário de `ROTULO_MODULO` (linhas 155-157):

```tsx
/** Texto do badge de Phoebus/Módulo. Os três casos são reais na base: a caixa leva só
 *  o aparelho, só o módulo, ou os dois juntos. O badge diz a COMPOSIÇÃO — é por ela
 *  que se sabe que o card do TaskHS dessa caixa é manual. Não confundir com o desvio
 *  do Pós-Vendas, que desde 18/09/2026 só vale para a caixa 100% módulo. */
```

- [ ] **Step 4: Rodar e ver passar**

```bash
cd frontend && npx vitest run src/app/ordens/OrdensPage.modulo.test.tsx
```
Esperado: PASS, 5 testes.

- [ ] **Step 5: Verificação completa do frontend**

```bash
cd frontend && npm run lint && npx tsc -b --noEmit && npm run build
```
Esperado: os três sem erro.

- [ ] **Step 6: Commit**

```bash
cd /home/ericks/github/GestorHS
git add frontend/src/app/ordens/OrdensPage.tsx frontend/src/app/ordens/OrdensPage.modulo.test.tsx
git commit -m "$(cat <<'MSG'
fix(ui): badge de phoebus e modulo vale em qualquer coluna do quadro

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

---

### Task 6: Documentação — `CLAUDE.md`

O `CLAUDE.md` descreve hoje a regra errada em quatro pontos. Deixá-lo desatualizado faz a próxima sessão reintroduzir o bug.

**Files:**
- Modify: `CLAUDE.md` (raiz do repo)

**Interfaces:**
- Consumes: nada
- Produces: nada

- [ ] **Step 1: Corrigir a seção da segunda rota**

Na seção "O ciclo de negócio e o workflow da OS", substitua o parágrafo que começa com `**Phoebus e Módulo têm uma segunda rota**, em `PROXIMA_MODULO` (set/2026):` e o bloco de fluxo logo abaixo por:

```markdown
**A caixa 100% Módulo tem uma segunda rota**, em `PROXIMA_SO_MODULO` (set/2026): o serviço de bancada dela não passa pelo comercial, então a caixa sai do **Laboratório(5) direto para o Financeiro(10)**, pulando Pós-Vendas.

```
Recebido(4) → Laboratório(5) → Financeiro(10) → Preparando Retorno(7) → Finalizada(8)
```

⚠️ **Caixa com Phoebus dentro NÃO pula** — nem o aparelho sozinho, nem o par Phoebus+Módulo. O aparelho gera serviço e precisa do aceite comercial. Isso é **mais estreito** que o critério que bloqueia o card do TaskHS/GrowthHS, e confundir os dois foi o bug de 18/09/2026: 7 caixas de Phoebus+Módulo (1003, 1011, 1028, 1030, 1043, 1047, 1049) foram parar no Financeiro sem aceite, revertidas por `app.scripts.reverter_posvendas_phoebus_modulo`.
```

- [ ] **Step 2: Corrigir o parágrafo do critério**

Substitua o parágrafo `Quem decide a rota é o chamador, com o **mesmo** `fluxo_modulo.caixa_de_modulo()` que já tira essas caixas do board do TaskHS/GrowthHS — um critério só para "isto é serviço de módulo". Ao mexer em transição, lembre que são **dois** mapas: escrever só em `PROXIMA` deixa a rota do módulo para trás em silêncio.` por:

```markdown
Quem decide a rota é o chamador, com `fluxo_modulo.caixa_pula_posvendas()` — `all(== 47)`. **Não confundir com `caixa_de_modulo()`**, que é `any(36 ou 47)` e responde outra pergunta: "esta caixa vira card no TaskHS/GrowthHS?". As duas respostas não coincidem, e `fluxo_modulo` existe justamente para manter as duas visíveis lado a lado. Ao mexer em transição, lembre que são **dois** mapas: escrever só em `PROXIMA` deixa a rota do módulo para trás em silêncio.
```

- [ ] **Step 3: Corrigir o ⚠️ do aceite e o do encerramento**

No parágrafo `⚠️ **Pular a 6 significa ficar SEM `aceite`**`, substitua a frase final `Antes do desvio existir, 40 caixas (82 OS) empilharam na fase 6; `app.scripts.mover_phoebus_posvendas` é o acerto delas (39 movidas em 18/09/2026 — a mista ficou de fora).` por:

```markdown
Antes do desvio existir, 40 caixas (82 OS) empilharam na fase 6; `app.scripts.mover_phoebus_posvendas` é o acerto delas (39 movidas em 18/09/2026). Esse backfill rodou com o critério largo e levou junto 13 caixas de Phoebus+Módulo que não deviam ter saído — 7 revertidas, 6 já fechadas pelo `ENC-ADM-20260918` e deixadas como estão por já terem sido despachadas.
```

No ⚠️ de `finalizar_caixas_phoebus`, troque `Caixa de Phoebus despachada não fecha pelo fluxo normal` por `Caixa 100% Módulo despachada não fecha pelo fluxo normal` e, na frase final, `poupando as 10 que ainda estavam na empresa` por `poupando as 10 que ainda estavam na empresa (6 delas eram Phoebus+Módulo e hoje o script nem as pegaria)`.

- [ ] **Step 4: Registrar o script novo na lista de comandos**

Na lista de comandos do backend, depois da linha de `finalizar_caixas_phoebus`, acrescente:

```markdown
python -m app.scripts.reverter_posvendas_phoebus_modulo                            # SIMULA: devolve ao Pos-Vendas a caixa de Phoebus+Modulo do backfill (--aplicar grava)
```

E acrescente `reverter_posvendas_phoebus_modulo` à lista de **scripts de uso único** no bloco `ℹ️` que já enumera `corrigir_cnpj_proposta_99`, `unificar_markx_mercury` etc.

- [ ] **Step 5: Conferir que não sobrou referência à regra antiga**

```bash
cd /home/ericks/github/GestorHS
grep -n "PROXIMA_MODULO\|Phoebus/Módulo têm uma segunda rota\|Phoebus e Módulo têm uma segunda rota" CLAUDE.md || echo "nenhuma sobra"
```
Esperado: `nenhuma sobra`.

- [ ] **Step 6: Commit**

```bash
cd /home/ericks/github/GestorHS
git add CLAUDE.md
git commit -m "$(cat <<'MSG'
docs(caixas): so a caixa 100% modulo pula o pos-vendas

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

---

## Verificação final (antes de dizer que acabou)

- [ ] `cd backend && source .venv/bin/activate && pytest -q 2>&1 | tail -5` → **4 falhas**, as da baseline, nenhuma a mais.
- [ ] `cd frontend && npm run lint && npx tsc -b --noEmit && npm run build` → os três limpos.
- [ ] `grep -rn "PROXIMA_MODULO" backend/ frontend/src/ CLAUDE.md` → vazio.
- [ ] `grep -rn "caixa_de_modulo" backend/app/api/caixas.py backend/app/scripts/` → vazio (os consumidores do desvio migraram; `espelhamento.py`, `growthhs_cards.py` e `logs_integracao.py` **devem** continuar usando).
- [ ] `git log --oneline -6` → seis commits, um por task.

## Depois do merge — ação em produção (o Erick executa)

1. `python -m app.scripts.reverter_posvendas_phoebus_modulo` (simulação) → conferir **7 caixas / 17 OS**: 1003, 1011, 1028, 1030, 1043, 1047, 1049.
2. Só então `--aplicar`.
3. Sem ação no TaskHS: os cards dessas 7 são manuais e já estão na lista certa (`🔬LIBERADOS DO LABORATÓRIO`).

## Fora do escopo deste plano

- **Changelog e bump de versão** em `frontend/src/app/changelog/data.ts` — o Erick ainda não definiu o número, e a entrada vai cobrir a rota do Phoebus e esta correção juntas.
- **As 6 caixas do `ENC-ADM-20260918`** ficam na fase 8. Rollback disponível em `~/projetos/gestorhs-backups/rollback-ENC-ADM-20260918.sql` se a decisão mudar.
