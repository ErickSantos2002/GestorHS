# Inbound do TaskHS (lado GestorHS) — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar ao GestorHS o endpoint que o TaskHS vai chamar quando o card entrar na lista do Financeiro, e fazer a caixa com Phoebus virar card espelhado para que esse elo exista.

**Architecture:** O critério `all(== 47)` passa a responder duas perguntas (pular o Pós-Vendas e ficar fora do board do TaskHS) através de um núcleo único, `caixa_so_de_modulo`. A regra de "esta caixa pode avançar 6 → 10?" sai de dentro do endpoint do GrowthHS para `core/avanco_inbound.py` e passa a servir os dois integradores. O endpoint novo tem chave própria e recusa caixa sem Phoebus.

**Tech Stack:** Python 3.12 · FastAPI · SQLAlchemy 2 · pytest (SQLite in-memory)

**Spec:** [docs/superpowers/specs/2026-09-18-taskhs-inbound-financeiro-design.md](../specs/2026-09-18-taskhs-inbound-financeiro-design.md)

⚠️ **Este plano cobre SÓ o lado GestorHS.** O lado TaskHS (a ação `avisar_gestorhs`) está especificado na spec e é implementado numa sessão aberta dentro de `~/github/TaskHS` — **não edite aquele repo daqui.** Ao terminar este plano, o GestorHS fica pronto e **inerte**: sem `TASKHS_INBOUND_API_KEY` o endpoint responde 503 e nada muda em produção além do espelhamento das caixas com Phoebus (ver o aviso na Task 3).

## Global Constraints

- **Idioma do domínio é PT-BR.** Nomes de funções, variáveis, testes e mensagens em português. Comentários e docstrings de código novo em `app/` **sem acentos**; markdown pode ter acento.
- **Commits** em Conventional Commits, **português sem acentos**, assunto de **uma linha só**, sem corpo. Terminar com a linha de co-autoria exigida nesta sessão.
- **Nunca comparar fase por ID cru.** Use as constantes de `os_workflow` (`FASE_POSVENDAS=6`, `FASE_FINANCEIRO=10`, `FASE_PREPARANDO=7`, `FASE_FINALIZADA=8`) e `posicao()`/`ORDEM_FASES`. O ID 10 é numericamente maior que 7 e 8 mas vem antes deles.
- **Ids de catálogo sempre via `settings`**, lidos na chamada: `settings.EQUIPAMENTO_PHOEBUS_ID` (36), `settings.EQUIPAMENTO_MODULO_ID` (47). Um set de módulo congelaria o valor no import e furaria o monkeypatch.
- **Chave de integração nasce vazia = desligada.** Motivo: a máquina de desenvolvimento aponta para o banco de produção.
- ⚠️ **As fixtures de client do `conftest.py` são o MESMO objeto.** Pedir `client` e `client_exp` na mesma assinatura troca a identidade em silêncio. Peça uma só.
- ⚠️ **Teste que monta `Caixa`/`Ordem` precisa da fixture `fases_seed`** (direta ou por um `_fases` autouse). `caixas.fase` e `ordens.fase` são FK para `fases`, e sem o seed o INSERT morre com `FOREIGN KEY constraint failed`.
- **Baseline desta máquina: 4 falhas pré-existentes** (`PermissionError` em `test_certificados_gerais.py` e `test_publico_certificado_geral.py`). Verde é **bater a baseline**, não zero. Confira antes de começar: `cd backend && source .venv/bin/activate && pytest -q 2>&1 | tail -3`.
- **Nenhuma migração Alembic.** Este plano não toca em schema.

---

### Task 1: Núcleo `caixa_so_de_modulo`

Aditiva: nada passa a usar o nome novo ainda, então a suíte inteira continua na baseline no fim desta task.

**Files:**
- Modify: `backend/app/core/fluxo_modulo.py`
- Test: `backend/tests/test_fluxo_modulo.py`

**Interfaces:**
- Consumes: `settings.EQUIPAMENTO_MODULO_ID`
- Produces: `fluxo_modulo.caixa_so_de_modulo(ordens) -> bool`; `caixa_pula_posvendas` passa a delegar a ele, com a mesma assinatura e o mesmo resultado

- [ ] **Step 1: Escrever os testes que falham**

Acrescente ao fim de `backend/tests/test_fluxo_modulo.py`:

```python
# --- nucleo compartilhado das duas decisoes (set/2026) ---

def test_so_de_modulo_reconhece_caixa_100_por_cento_modulo():
    assert fluxo_modulo.caixa_so_de_modulo([_os(settings.EQUIPAMENTO_MODULO_ID)]) is True
    assert fluxo_modulo.caixa_so_de_modulo(
        [_os(settings.EQUIPAMENTO_MODULO_ID), _os(settings.EQUIPAMENTO_MODULO_ID)]) is True


def test_so_de_modulo_recusa_phoebus_em_qualquer_composicao():
    """Phoebus sozinho, com o modulo dele, ou com aparelho comum: nenhuma e' 100% Modulo."""
    assert fluxo_modulo.caixa_so_de_modulo([_os(settings.EQUIPAMENTO_PHOEBUS_ID)]) is False
    assert fluxo_modulo.caixa_so_de_modulo(
        [_os(settings.EQUIPAMENTO_PHOEBUS_ID), _os(settings.EQUIPAMENTO_MODULO_ID)]) is False
    assert fluxo_modulo.caixa_so_de_modulo(
        [_os(settings.EQUIPAMENTO_PHOEBUS_ID), _os(1)]) is False


def test_so_de_modulo_recusa_mista_e_vazia():
    assert fluxo_modulo.caixa_so_de_modulo([_os(1), _os(settings.EQUIPAMENTO_MODULO_ID)]) is False
    assert fluxo_modulo.caixa_so_de_modulo([_os(1)]) is False
    assert fluxo_modulo.caixa_so_de_modulo([]) is False


def test_pula_posvendas_e_so_de_modulo_sao_a_MESMA_resposta():
    """As duas decisoes (pular o Pos-Vendas, ficar fora do board do TaskHS) partem do
    mesmo criterio. Se divergirem, uma copia do predicado foi introduzida."""
    casos = [[], [_os(1)], [_os(settings.EQUIPAMENTO_MODULO_ID)],
             [_os(settings.EQUIPAMENTO_PHOEBUS_ID)],
             [_os(settings.EQUIPAMENTO_PHOEBUS_ID), _os(settings.EQUIPAMENTO_MODULO_ID)],
             [_os(1), _os(settings.EQUIPAMENTO_MODULO_ID)]]
    for ordens in casos:
        assert fluxo_modulo.caixa_pula_posvendas(ordens) == fluxo_modulo.caixa_so_de_modulo(ordens)
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_fluxo_modulo.py -q
```
Esperado: FAIL com `AttributeError: module 'app.core.fluxo_modulo' has no attribute 'caixa_so_de_modulo'`.

- [ ] **Step 3: Implementar o núcleo e fazer `caixa_pula_posvendas` delegar**

Em `backend/app/core/fluxo_modulo.py`, substitua a função `caixa_pula_posvendas` inteira por estas duas:

```python
def caixa_so_de_modulo(ordens) -> bool:
    """True SO se todas as OS sao Modulo (47). Nucleo de DUAS decisoes: pular o
    Pos-Vendas e ficar fora do board do TaskHS.

    ⚠️ "modulo" aqui e' ESTRITAMENTE o catalogo 47. Em `caixa_de_modulo`, logo
    acima, "modulo" quer dizer "modulo OU phoebus" (`any`) — nomes parecidos,
    conjuntos diferentes. `caixa_de_modulo` segue valendo para o board do
    GrowthHS, que e' comercial e onde Phoebus nao tem proposta.

    Recebe a lista de ordens JA FILTRADA pelo chamador. Lista vazia devolve
    False: caixa sem OS ativa nao tem para onde desviar nem card a suprimir.
    """
    ativas = list(ordens)
    return bool(ativas) and all(
        getattr(o, "equipamento_catalogo", None) == settings.EQUIPAMENTO_MODULO_ID
        for o in ativas)


def caixa_pula_posvendas(ordens) -> bool:
    """A caixa 100% Modulo e' a unica que nao passa pelo comercial.

    Delega a `caixa_so_de_modulo`: o criterio e' o mesmo, e o nome existe porque
    "pula o Pos-Vendas" e' a frase que descreve a decisao no `api/caixas.py`.
    Foi reaproveitar o predicado ERRADO para esta pergunta que mandou 7 caixas de
    Phoebus+Modulo ao Financeiro sem aceite em 18/09/2026.
    """
    return caixa_so_de_modulo(ordens)
```

Atualize o docstring de módulo, cujo item 2 passa a valer para as duas decisões:

```python
2. Caixa 100% Modulo nao passa pelo Pos-Vendas E fica fora do board do TaskHS
   (`caixa_so_de_modulo`, `all`; `caixa_pula_posvendas` delega a ele).
   Consumido por `api/caixas.py`, `api/espelhamento.py` e pelos scripts.
```

- [ ] **Step 4: Rodar e ver passar**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_fluxo_modulo.py -q
```
Esperado: PASS, todos.

- [ ] **Step 5: Rodar a suíte inteira**

```bash
cd backend && source .venv/bin/activate && pytest -q 2>&1 | tail -5
```
Esperado: **4 falhas, a baseline.** Esta task é aditiva — `caixa_pula_posvendas` devolve exatamente o que devolvia.

- [ ] **Step 6: Commit**

```bash
cd /home/ericks/github/GestorHS
git add backend/app/core/fluxo_modulo.py backend/tests/test_fluxo_modulo.py
git commit -m "$(cat <<'MSG'
refactor(caixas): nucleo unico para caixa 100% modulo

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

---

### Task 2: Extrair o avanço inbound para `core/avanco_inbound.py`

Refatoração pura. O guardião de que não mudou comportamento são os 14 testes que já existem em `test_integracao_growthhs_ganho.py` e `test_integracao_growthhs_auth.py` — eles têm de continuar passando **sem edição**.

**Files:**
- Create: `backend/app/core/avanco_inbound.py`
- Modify: `backend/app/api/integracao_growthhs.py`
- Test: `backend/tests/test_avanco_inbound.py` (novo)

**Interfaces:**
- Consumes: `os_workflow.FASE_POSVENDAS`, `FASE_FINANCEIRO`, `FASE_PREPARANDO`, `FASE_FINALIZADA`
- Produces: `avanco_inbound.estado_para_avanco(fase: int | None) -> str`, devolvendo uma das constantes `avanco_inbound.AVANCAR` (`"avancar"`), `NO_OP` (`"no_op"`), `FASE_ERRADA` (`"fase_errada"`); e `avanco_inbound.FASES_JA_AVANCADAS: tuple[int, ...]`

> **Desvio deliberado da spec:** a spec escreveu `estado_para_avanco(caixa)`. Aqui a função recebe **a fase**, não a caixa. A regra não depende de mais nada da caixa, e receber um `int` deixa o teste do núcleo trivial e sem banco. Os endpoints passam `cx.fase`.

- [ ] **Step 1: Escrever o teste do núcleo**

Crie `backend/tests/test_avanco_inbound.py`:

```python
"""Regra compartilhada do avanco inbound 6 -> 10.

Dois integradores chamam esse avanco por caminhos proprios — o GrowthHS ao marcar
a proposta como "Ganho" e o TaskHS ao mover o card para a lista do Financeiro — e a
pergunta "essa caixa pode avancar agora?" e' a mesma nos dois.
"""
from app.core import avanco_inbound as ai
from app.core import os_workflow as wf


def test_posvendas_avanca():
    assert ai.estado_para_avanco(wf.FASE_POSVENDAS) == ai.AVANCAR


def test_fases_ja_avancadas_sao_no_op():
    """Chamada repetida nao pode virar erro: quem chama nao sabe se ja mandou este
    mesmo evento antes. No caso do TaskHS o reenvio e' garantido por construcao —
    o GestorHS move o card para a lista do Financeiro ao avancar, o que dispara a
    automacao de volta."""
    for fase in (wf.FASE_FINANCEIRO, wf.FASE_PREPARANDO, wf.FASE_FINALIZADA):
        assert ai.estado_para_avanco(fase) == ai.NO_OP


def test_fases_anteriores_ao_posvendas_sao_erro():
    assert ai.estado_para_avanco(wf.FASE_RECEBIDO) == ai.FASE_ERRADA
    assert ai.estado_para_avanco(wf.FASE_LABORATORIO) == ai.FASE_ERRADA


def test_caixa_arquivada_e_erro_nao_no_op():
    """Fase None e' caixa cancelada/arquivada. Avancar isso e' erro de quem chamou,
    nao repeticao inofensiva — por isso nao cai no no_op."""
    assert ai.estado_para_avanco(None) == ai.FASE_ERRADA


def test_cancelada_e_erro():
    assert ai.estado_para_avanco(wf.FASE_CANCELADA) == ai.FASE_ERRADA


def test_fases_ja_avancadas_nao_inclui_posvendas():
    """Se a 6 entrasse nessa tupla, TODA chamada viraria no-op em silencio e a
    integracao pararia de funcionar sem erro nenhum."""
    assert wf.FASE_POSVENDAS not in ai.FASES_JA_AVANCADAS
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_avanco_inbound.py -q
```
Esperado: FAIL na coleta com `ModuleNotFoundError: No module named 'app.core.avanco_inbound'`.

- [ ] **Step 3: Criar o núcleo**

Crie `backend/app/core/avanco_inbound.py`:

```python
"""Regra do avanco inbound da caixa: Pos-Vendas(6) -> Financeiro(10). Puro, sem I/O.

Dois integradores pedem esse avanco por caminhos proprios — o GrowthHS ao marcar a
proposta como "Ganho" e o TaskHS ao mover o card para a lista do Financeiro — e a
pergunta "essa caixa pode avancar agora?" e' a mesma nos dois. O que NAO e' comum
(a chave de API, a obs gravada no log, as validacoes de escopo de cada um) fica em
cada endpoint.
"""
from app.core import os_workflow as wf

AVANCAR = "avancar"
NO_OP = "no_op"
FASE_ERRADA = "fase_errada"

# Fases que ja passaram do ponto de avanco. Chamada repetida vira no-op, nao erro:
# quem chama nao sabe se ja mandou este mesmo evento antes. No TaskHS o reenvio e'
# garantido por construcao — avancar a caixa move o card para a lista do
# Financeiro, o que dispara a automacao de volta. E' aqui que esse laco morre.
FASES_JA_AVANCADAS = (wf.FASE_FINANCEIRO, wf.FASE_PREPARANDO, wf.FASE_FINALIZADA)


def estado_para_avanco(fase: int | None) -> str:
    """O que fazer com uma caixa nesta fase: AVANCAR, NO_OP ou FASE_ERRADA.

    Recebe a FASE, nao a caixa: a regra nao depende de mais nada, e um `int` deixa
    o teste sem banco.

    `None` e' caixa arquivada (cancelada) e devolve FASE_ERRADA, nao NO_OP —
    avancar caixa arquivada e' erro de quem chamou, nao repeticao inofensiva.
    """
    if fase in FASES_JA_AVANCADAS:
        return NO_OP
    if fase == wf.FASE_POSVENDAS:
        return AVANCAR
    return FASE_ERRADA
```

- [ ] **Step 4: Rodar e ver passar**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_avanco_inbound.py -q
```
Esperado: PASS, 6 testes.

- [ ] **Step 5: Fazer o endpoint do GrowthHS usar o núcleo**

Em `backend/app/api/integracao_growthhs.py`:

1. Troque as constantes locais. Remova estas duas linhas:

```python
FASE_POSVENDAS = 6
# Fases que ja passaram do ponto de avanco (10/7/8): chamada repetida vira no-op,
# nao erro — o GrowthHS nao sabe se ja mandou essa mesma "ganho" antes.
_FASES_JA_AVANCADAS = (wf.FASE_FINANCEIRO, 7, wf.FASE_FINALIZADA)
```

e acrescente `from app.core import avanco_inbound as ai` ao bloco de imports.

2. Substitua o corpo de decisão do endpoint. O trecho atual:

```python
    if cx.fase in _FASES_JA_AVANCADAS:
        logger.info("GrowthHS ganho: caixa %s ja avancada (fase %s), no-op", caixa_id, cx.fase)
        if dados.numero_proposta is not None:
            cx.numero_proposta = dados.numero_proposta
            db.commit()
        return GanhoOut(movida=False, caixa_id=cx.id, fase=cx.fase)
    if cx.fase != FASE_POSVENDAS:
        logger.warning("GrowthHS ganho: caixa %s nao esta em Pos-Vendas (fase %s)", caixa_id, cx.fase)
        raise HTTPException(status_code=409, detail="caixa nao esta em Pos-Vendas")
```

passa a ser:

```python
    estado = ai.estado_para_avanco(cx.fase)
    if estado == ai.NO_OP:
        logger.info("GrowthHS ganho: caixa %s ja avancada (fase %s), no-op", caixa_id, cx.fase)
        if dados.numero_proposta is not None:
            cx.numero_proposta = dados.numero_proposta
            db.commit()
        return GanhoOut(movida=False, caixa_id=cx.id, fase=cx.fase)
    if estado != ai.AVANCAR:
        logger.warning("GrowthHS ganho: caixa %s nao esta em Pos-Vendas (fase %s)", caixa_id, cx.fase)
        raise HTTPException(status_code=409, detail="caixa nao esta em Pos-Vendas")
```

3. Nas duas referências restantes a `FASE_POSVENDAS` dentro da chamada de `executar_avanco_caixa`, troque por `wf.FASE_POSVENDAS`:

```python
    executar_avanco_caixa(
        db, cx,
        origem=wf.FASE_POSVENDAS,
        destino=wf.proxima_fase(wf.FASE_POSVENDAS),
```

4. Atualize o docstring de módulo, cuja primeira frase passa a mencionar o núcleo:

```python
"""Endpoint inbound chamado pelo GrowthHS: ao marcar uma proposta como "Ganho",
o card correspondente precisa mover a caixa de Pos-Vendas(6) para Financeiro(10)
no GestorHS. Autenticado por API key fixa (`require_growthhs_inbound`, T1), nao
por JWT — quem chama e o GrowthHS, nao um usuario logado.

A regra "essa caixa pode avancar agora?" vive em `core/avanco_inbound.py`, e e'
compartilhada com o inbound do TaskHS (`api/integracao_taskhs.py`)."""
```

5. Confirme que não sobrou constante local:

```bash
cd /home/ericks/github/GestorHS
grep -n "FASE_POSVENDAS\|_FASES_JA_AVANCADAS" backend/app/api/integracao_growthhs.py
```
Esperado: só as linhas com o prefixo `wf.`, nenhuma definição local.

- [ ] **Step 6: Rodar os testes do GrowthHS SEM editá-los**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_integracao_growthhs_ganho.py tests/test_integracao_growthhs_auth.py -q
```
Esperado: PASS, 14 testes. **Se algum falhar, a extração mudou comportamento — pare e investigue em vez de ajustar o teste.** Esses 14 são o guardião desta task.

- [ ] **Step 7: Rodar a suíte inteira**

```bash
cd backend && source .venv/bin/activate && pytest -q 2>&1 | tail -5
```
Esperado: 4 falhas, a baseline.

- [ ] **Step 8: Commit**

```bash
cd /home/ericks/github/GestorHS
git add backend/app/core/avanco_inbound.py backend/app/api/integracao_growthhs.py \
        backend/tests/test_avanco_inbound.py
git commit -m "$(cat <<'MSG'
refactor(caixas): regra do avanco inbound sai para o core

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

---

### Task 3: Espelhamento do TaskHS passa ao critério estreito

⚠️ **Esta task muda comportamento em produção assim que for deployada:** caixa com Phoebus passa a virar card no board `Serviço`. É o objetivo — sem `external_id` não existe elo — mas **leia a seção "Ordem de implantação" da spec antes de deployar**, em especial o item 3 sobre as caixas 639, 670, 685 e 692, que ganhariam um card novo ao lado do card manual delas.

**Files:**
- Modify: `backend/app/api/espelhamento.py` (3 chamadas)
- Test: `backend/tests/test_taskhs_bloqueio_modulo.py`

**Interfaces:**
- Consumes: `fluxo_modulo.caixa_so_de_modulo(ordens) -> bool` (Task 1)
- Produces: nada novo. Caixa com Phoebus passa a espelhar; o `motivo` do log de integração vira `"caixa_so_de_modulo"`.

- [ ] **Step 1: Inverter os testes que mudam**

Em `backend/tests/test_taskhs_bloqueio_modulo.py`:

1. Substitua o docstring do topo por:

```python
"""Caixa 100% Modulo nao vira card no TaskHS — nem ao avancar, nem ao cancelar.

Caixa com PHOEBUS dentro vira: ela passa por servico e pertence ao board. Ate
18/09/2026 o criterio era `caixa_de_modulo` (`any`), largo demais, e o setor de
Servicos criava esses cards a mao — 12 deles. O criterio agora e'
`fluxo_modulo.caixa_so_de_modulo` (`all`).
"""
```

2. Substitua `test_avancar_caixa_de_phoebus_nao_espelha` (linhas 44-48) por:

```python
def test_avancar_caixa_de_phoebus_espelha(client_exp, db_session, captura):
    """Inverteu em 18/09/2026: o Phoebus passa por servico e o card dele no board e'
    justamente o elo que o inbound do TaskHS usa para achar a caixa."""
    cx_id, _ = _caixa_com(db_session, catalogo_id=settings.EQUIPAMENTO_PHOEBUS_ID)
    r = client_exp.post(f"/caixas/{cx_id}/avancar", json={})
    assert r.status_code == 200
    assert len(captura) == 1
    assert captura[0]["external_id"] == str(cx_id)
```

3. Substitua `test_avancar_caixa_mista_nao_espelha` (linhas 61-77) por uma versão que espera espelhamento. Reescreva o teste inteiro, porque o corpo monta a caixa:

```python
def test_avancar_caixa_mista_espelha(client_exp, db_session, captura):
    """Inverteu: caixa mista tem aparelho comum dentro, que precisa do board.
    Antes uma OS de modulo contaminava a caixa inteira."""
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
    assert len(captura) == 1
```

4. Acrescente ao fim do arquivo o caso da composição real das 7 caixas:

```python
def test_avancar_caixa_de_phoebus_com_modulo_espelha(client_exp, db_session, captura):
    """A composicao real das 7 caixas de 18/09/2026: o aparelho e o modulo dele na
    mesma caixa. Precisa de card, porque e' por ele que o TaskHS avisa o GestorHS."""
    from app.models import Cliente, Equipamento, EquipamentoCliente, Ordem
    cx_id, _ = _caixa_com(db_session, catalogo_id=settings.EQUIPAMENTO_PHOEBUS_ID)
    cli = db_session.query(Cliente).first()
    eq_mod = Equipamento(id=settings.EQUIPAMENTO_MODULO_ID, descricao="Modulo")
    db_session.add(eq_mod); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq_mod.id, serie="SER-PAR-MOD")
    db_session.add(ec); db_session.flush()
    db_session.add(Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=4,
                         situacao="E", caixa=cx_id))
    db_session.commit()
    r = client_exp.post(f"/caixas/{cx_id}/avancar", json={})
    assert r.status_code == 200
    assert len(captura) == 1
    assert captura[0]["external_id"] == str(cx_id)
```

5. Em `test_bloqueio_registra_log_pulado` (linha 102), o `motivo` esperado muda. Localize a asserção que compara com `"caixa_de_modulo"` e troque o valor esperado por `"caixa_so_de_modulo"`:

```bash
cd /home/ericks/github/GestorHS
grep -n "caixa_de_modulo" backend/tests/test_taskhs_bloqueio_modulo.py
```
Troque **apenas** as ocorrências dentro de `test_bloqueio_registra_log_pulado` por `caixa_so_de_modulo`. Os nomes de teste que contêm `caixa_de_modulo` como texto (ex.: `test_avancar_caixa_de_modulo_nao_espelha`) **não** mudam.

6. **Não toque** nestes cinco, que montam a caixa com Módulo puro e seguem valendo: `test_avancar_caixa_de_modulo_nao_espelha`, `test_avancar_caixa_comum_continua_espelhando`, `test_caixa_cujo_modulo_esta_cancelado_volta_a_espelhar`, `test_cancelar_caixa_de_modulo_nao_arquiva_card`, `test_anexar_nota_fiscal_em_caixa_de_modulo_nao_espelha`.

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_taskhs_bloqueio_modulo.py -q
```
Esperado: FAIL em `test_avancar_caixa_de_phoebus_espelha`, `test_avancar_caixa_mista_espelha`, `test_avancar_caixa_de_phoebus_com_modulo_espelha` (todos com `assert 0 == 1`, porque nada foi capturado) e em `test_bloqueio_registra_log_pulado` (motivo ainda antigo).

- [ ] **Step 3: Trocar o predicado no espelhamento**

Em `backend/app/api/espelhamento.py` há **três** chamadas a trocar. Faça a troca e ajuste os comentários:

Em `espelhar_caixa_sync`:

```python
    ordens = ordens_do_card(caixa)
    if fluxo_modulo.caixa_so_de_modulo(ordens):
        registrar_log_integracao(integracao="taskhs", status="pulado",
                                 motivo="caixa_so_de_modulo",
                                 referencia_os=ordens[0].id if ordens else None)
        return False
```

E ajuste a última frase do docstring dessa função, de `Devolve False quando a caixa é de módulo/phoebus (fluxo próprio, fora do board).` para:

```python
    Devolve False quando a caixa é 100% Módulo (serviço de bancada, fora do board).
```

Em `agendar_espelhamento_caixa`:

```python
    ordens = ordens_do_card(caixa)
    if fluxo_modulo.caixa_so_de_modulo(ordens):
        # A caixa 100% Módulo tem serviço de bancada e não entra no board. Bloquear
        # ANTES de montar o payload também congela card antigo: criar, mover e
        # arquivar são o mesmo caminho, então nada mexe no que já foi enviado.
        # ⚠️ NÃO é `caixa_de_modulo` (`any`): caixa com Phoebus PRECISA do card, que
        # é o elo usado pelo inbound do TaskHS para achar a caixa.
        registrar_log_integracao(integracao="taskhs", status="pulado",
                                 motivo="caixa_so_de_modulo",
                                 referencia_os=ordens[0].id if ordens else None)
        return
```

E no docstring dessa função, troque `ou caixa de módulo` por `ou caixa 100% Módulo`.

A terceira chamada é a que sobra em `agendar_espelhamento_caixa` — confirme que não ficou nenhuma:

```bash
cd /home/ericks/github/GestorHS
grep -n "caixa_de_modulo" backend/app/api/espelhamento.py
```
Esperado: nenhuma linha, ou só a linha de comentário que menciona `caixa_de_modulo` para contrastar.

- [ ] **Step 4: Rodar e ver passar**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_taskhs_bloqueio_modulo.py -q
```
Esperado: PASS, 9 testes.

- [ ] **Step 5: Conferir que o GrowthHS NÃO mudou**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_growthhs_bloqueio_modulo.py -q
```
Esperado: PASS sem nenhuma edição no arquivo. **É este comando que trava a decisão de que o board comercial mantém o critério largo.** Se falhar, `growthhs_cards.py` foi alterado por engano.

- [ ] **Step 6: Rodar a suíte inteira**

```bash
cd backend && source .venv/bin/activate && pytest -q 2>&1 | tail -8
```
Esperado: 4 falhas, a baseline. Se aparecer falha em outro arquivo, é teste que assumia que caixa de Phoebus não espelha — avalie caso a caso antes de mexer.

- [ ] **Step 7: Commit**

```bash
cd /home/ericks/github/GestorHS
git add backend/app/api/espelhamento.py backend/tests/test_taskhs_bloqueio_modulo.py
git commit -m "$(cat <<'MSG'
feat(caixas): caixa com phoebus volta a virar card no taskhs

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

---

### Task 4: Endpoint inbound do TaskHS

Chave, dependência e rota juntas: a dependência sozinha não tem rota para ser exercitada, e o padrão do repo é testar a auth batendo no endpoint (`test_integracao_growthhs_auth.py`).

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/api/deps.py`
- Create: `backend/app/api/integracao_taskhs.py`
- Modify: `backend/app/main.py` (import e `include_router`)
- Test: `backend/tests/test_integracao_taskhs.py` (novo)

**Interfaces:**
- Consumes: `avanco_inbound.estado_para_avanco(fase) -> str` e as constantes `AVANCAR`/`NO_OP` (Task 2); `settings.EQUIPAMENTO_PHOEBUS_ID`; `caixas.executar_avanco_caixa` e `caixas._ordens_ativas`
- Produces: `POST /integracao/taskhs/caixas/{caixa_id}/financeiro`; `settings.TASKHS_INBOUND_API_KEY`; `deps.require_taskhs_inbound`

- [ ] **Step 1: Escrever o teste**

Crie `backend/tests/test_integracao_taskhs.py`:

```python
"""Endpoint inbound `POST /integracao/taskhs/caixas/{id}/financeiro`.

Chamado pela automacao do TaskHS quando o card entra na lista do Financeiro (205).
So vale para caixa com PHOEBUS dentro: sair da fase 6 grava `aceite`, e na caixa
normal esse aval vem do "Ganho" da proposta no GrowthHS — deixar o TaskHS gravar
seria forjar aprovacao comercial.

Usa o `client` do conftest (X-API-Key, nao JWT).
"""
import pytest

from app.core.config import settings
from app.models import Caixa, Cliente, Equipamento, EquipamentoCliente, LogOS, Ordem

CHAVE = "segredo-taskhs-123"


@pytest.fixture(autouse=True)
def _fases(fases_seed):
    """`caixas.fase` e `ordens.fase` sao FK para `fases` — sem o seed o INSERT morre."""


@pytest.fixture(autouse=True)
def _chave(monkeypatch):
    monkeypatch.setattr(settings, "TASKHS_INBOUND_API_KEY", CHAVE)


def _caixa(db, *, catalogos, fase=6):
    """Caixa na fase informada, uma OS por item de `catalogos`.

    Item `None` cria a OS SEM equipamento vinculado (`equipamento_catalogo` devolve
    None) — e' o caso da caixa "normal" do conftest, e nao a mesma coisa que uma
    lista vazia, que criaria caixa sem OS nenhuma.
    """
    cli = Cliente(nome="Cliente TaskHS")
    db.add(cli); db.flush()
    cx = Caixa(obs="Caixa taskhs", fase=fase)
    db.add(cx); db.flush()
    ids = []
    for cat in catalogos:
        ec_id = None
        if cat is not None:
            eq = db.query(Equipamento).filter(Equipamento.id == cat).one_or_none()
            if eq is None:
                eq = Equipamento(id=cat, descricao=f"Equipamento {cat}")
                db.add(eq); db.flush()
            ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id,
                                    serie=f"S-{cat}-{len(ids)}")
            db.add(ec); db.flush()
            ec_id = ec.id
        o = Ordem(cliente=cli.id, equipamento_cliente=ec_id, fase=fase,
                  situacao="E", caixa=cx.id)
        db.add(o); db.flush()
        ids.append(o.id)
    db.commit(); db.refresh(cx)
    return cx.id, ids


def _chamar(client, caixa_id, *, chave=CHAVE, body=None):
    return client.post(f"/integracao/taskhs/caixas/{caixa_id}/financeiro",
                       json=body if body is not None else {"card_id": 2018},
                       headers={"X-API-Key": chave})


PAR = [settings.EQUIPAMENTO_PHOEBUS_ID, settings.EQUIPAMENTO_MODULO_ID]


def test_phoebus_com_modulo_avanca_para_financeiro(client, db_session):
    cx_id, os_ids = _caixa(db_session, catalogos=PAR)
    r = _chamar(client, cx_id)
    assert r.status_code == 200
    assert r.json() == {"movida": True, "caixa_id": cx_id, "fase": 10}

    db_session.expire_all()
    assert db_session.get(Caixa, cx_id).fase == 10
    assert all(db_session.get(Ordem, i).fase == 10 for i in os_ids)


def test_so_phoebus_avanca(client, db_session):
    cx_id, _ = _caixa(db_session, catalogos=[settings.EQUIPAMENTO_PHOEBUS_ID])
    assert _chamar(client, cx_id).json()["movida"] is True


def test_caixa_normal_recusa_409_e_nao_ganha_aceite(client, db_session):
    """A trava de escopo. Caixa sem Phoebus tem o "Ganho" do GrowthHS como fonte do
    aceite; avancar por aqui gravaria um aval comercial que ninguem deu."""
    cx_id, os_ids = _caixa(db_session, catalogos=[1])
    r = _chamar(client, cx_id)
    assert r.status_code == 409
    assert "phoebus" in r.json()["detail"].lower()

    db_session.expire_all()
    assert db_session.get(Caixa, cx_id).fase == 6
    o = db_session.get(Ordem, os_ids[0])
    assert o.aceite is not True
    assert o.data_aceite is None


def test_caixa_com_os_sem_equipamento_recusa_409(client, db_session):
    """OS sem equipamento vinculado nao tem Phoebus — `equipamento_catalogo` devolve
    None, e None nao pode passar pela trava por omissao. E' a forma das caixas da
    fixture `caixa_posvendas` do conftest."""
    cx_id, _ = _caixa(db_session, catalogos=[None, None])
    assert _chamar(client, cx_id).status_code == 409


def test_caixa_100_por_cento_modulo_recusa_409(client, db_session):
    """Essa nao tem card no board (fica fora do espelhamento), entao nao deveria
    chegar aqui. Se chegar, recusa."""
    cx_id, _ = _caixa(db_session, catalogos=[settings.EQUIPAMENTO_MODULO_ID])
    assert _chamar(client, cx_id).status_code == 409


def test_segunda_chamada_e_no_op_nao_erro(client, db_session):
    """O laco card -> caixa -> card: avancar move o card para a lista 205, o que
    dispara a automacao de volta. E' aqui que a corrente morre."""
    cx_id, _ = _caixa(db_session, catalogos=PAR)
    assert _chamar(client, cx_id).json()["movida"] is True
    r = _chamar(client, cx_id)
    assert r.status_code == 200
    assert r.json() == {"movida": False, "caixa_id": cx_id, "fase": 10}


def test_caixa_em_laboratorio_devolve_409(client, db_session):
    cx_id, _ = _caixa(db_session, catalogos=PAR, fase=5)
    assert _chamar(client, cx_id).status_code == 409


def test_caixa_inexistente_devolve_404(client):
    assert _chamar(client, 999999).status_code == 404


def test_grava_obs_no_log_da_os(client, db_session):
    cx_id, os_ids = _caixa(db_session, catalogos=PAR)
    _chamar(client, cx_id, body={"card_id": 2018, "observacao": "card 2018"})

    textos = [l.texto for l in db_session.query(LogOS).filter(LogOS.os == os_ids[0]).all()]
    assert any("via TaskHS" in (t or "") for t in textos)
    assert any("card 2018" in (t or "") for t in textos)


def test_chave_errada_devolve_401(client, db_session):
    cx_id, _ = _caixa(db_session, catalogos=PAR)
    assert _chamar(client, cx_id, chave="errada").status_code == 401


def test_header_ausente_devolve_401(client, db_session):
    cx_id, _ = _caixa(db_session, catalogos=PAR)
    r = client.post(f"/integracao/taskhs/caixas/{cx_id}/financeiro", json={})
    assert r.status_code == 401


def test_header_nao_ascii_devolve_401_e_nao_500(client, db_session):
    """Starlette decodifica header como latin-1; `compare_digest` levanta TypeError
    com caractere nao-ASCII. Sem o guard isso vira 500."""
    cx_id, _ = _caixa(db_session, catalogos=PAR)
    assert _chamar(client, cx_id, chave="chave-com-acento-ç").status_code == 401


def test_integracao_desligada_devolve_503(client, db_session, monkeypatch):
    cx_id, _ = _caixa(db_session, catalogos=PAR)
    monkeypatch.setattr(settings, "TASKHS_INBOUND_API_KEY", "")
    assert _chamar(client, cx_id).status_code == 503
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_integracao_taskhs.py -q
```
Esperado: FAIL — 404 em tudo, porque a rota não existe (e possivelmente `AttributeError` no `monkeypatch.setattr` de um campo que `Settings` ainda não tem).

- [ ] **Step 3: Acrescentar a chave na configuração**

Em `backend/app/core/config.py`, logo depois do bloco de `GROWTHHS_INBOUND_API_KEY`:

```python
    # Integracao INBOUND do TaskHS (card na lista do Financeiro -> caixa 6 -> 10).
    # Vazio = desligada (503). Chave PROPRIA, nao a do GrowthHS: um vazamento
    # derruba uma integracao, nao duas, e a rotacao fica independente.
    TASKHS_INBOUND_API_KEY: str = ""
```

- [ ] **Step 4: Acrescentar a dependência de auth**

Em `backend/app/api/deps.py`, logo depois de `require_growthhs_inbound`:

```python
def require_taskhs_inbound(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    configurada = settings.TASKHS_INBOUND_API_KEY
    if not configurada:
        raise HTTPException(status_code=503, detail="integracao inbound do TaskHS desligada")
    try:
        # compare_digest lanca TypeError se algum dos lados tiver caractere
        # nao-ASCII (Starlette decodifica headers como latin-1) — trata como
        # chave invalida em vez de deixar vazar como 500.
        valido = bool(x_api_key) and secrets.compare_digest(x_api_key, configurada)
    except TypeError:
        valido = False
    if not valido:
        logger.warning("TaskHS inbound: X-API-Key invalida ou ausente")
        raise HTTPException(status_code=401, detail="api key invalida")
```

- [ ] **Step 5: Criar o endpoint**

Crie `backend/app/api/integracao_taskhs.py`:

```python
"""Endpoint inbound chamado pela automacao do TaskHS: quando o card entra na lista
do Financeiro (205), a caixa correspondente avanca de Pos-Vendas(6) para
Financeiro(10) no GestorHS. Autenticado por API key propria
(`require_taskhs_inbound`), nao por JWT — quem chama e' o TaskHS.

Existe porque a caixa com Phoebus nao tem proposta no GrowthHS, logo nao tem o
gatilho de "Ganho" que move a caixa normal. O setor de Servicos trabalha no board
do TaskHS, e mover o card ja e' o gesto que significa "servico terminou".

A regra "essa caixa pode avancar agora?" vive em `core/avanco_inbound.py`,
compartilhada com o inbound do GrowthHS."""
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.caixas import executar_avanco_caixa, _ordens_ativas
from app.api.deps import require_taskhs_inbound
from app.core import avanco_inbound as ai
from app.core import os_workflow as wf
from app.core.config import settings
from app.models import Caixa
from app.models.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integracao/taskhs", tags=["integracao-taskhs"])


class FinanceiroIn(BaseModel):
    card_id: int | None = None
    observacao: str | None = None


class FinanceiroOut(BaseModel):
    movida: bool
    caixa_id: int
    fase: int


def _tem_phoebus(ativas) -> bool:
    """Trava de escopo, POSITIVA de proposito.

    ⚠️ NAO escreva `not fluxo_modulo.caixa_so_de_modulo(ativas)`: isso deixaria
    passar a caixa NORMAL (sem Phoebus e sem modulo), que e' exatamente o caso que
    a decisao do `aceite` quer barrar. Sair da fase 6 grava `aceite`/`data_aceite`,
    e na caixa normal esse aval vem do "Ganho" da proposta no GrowthHS.
    """
    return any(getattr(o, "equipamento_catalogo", None) == settings.EQUIPAMENTO_PHOEBUS_ID
               for o in ativas)


@router.post("/caixas/{caixa_id}/financeiro", response_model=FinanceiroOut)
def financeiro(
    caixa_id: int,
    dados: FinanceiroIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: None = Depends(require_taskhs_inbound),
):
    cx = db.query(Caixa).filter(Caixa.id == caixa_id).first()
    if cx is None:
        logger.warning("TaskHS financeiro: caixa %s nao encontrada (card=%s)",
                       caixa_id, dados.card_id)
        raise HTTPException(status_code=404, detail="caixa nao encontrada")

    estado = ai.estado_para_avanco(cx.fase)
    if estado == ai.NO_OP:
        logger.info("TaskHS financeiro: caixa %s ja avancada (fase %s), no-op",
                    caixa_id, cx.fase)
        return FinanceiroOut(movida=False, caixa_id=cx.id, fase=cx.fase)

    ativas = _ordens_ativas(cx)
    if not _tem_phoebus(ativas):
        logger.warning("TaskHS financeiro: caixa %s nao tem Phoebus (card=%s)",
                       caixa_id, dados.card_id)
        raise HTTPException(
            status_code=409,
            detail="caixa sem Phoebus: avanco pelo TaskHS nao se aplica")

    if estado != ai.AVANCAR:
        logger.warning("TaskHS financeiro: caixa %s nao esta em Pos-Vendas (fase %s)",
                       caixa_id, cx.fase)
        raise HTTPException(status_code=409, detail="caixa nao esta em Pos-Vendas")

    obs = "via TaskHS"
    if dados.observacao and dados.observacao.strip():
        obs = f"via TaskHS: {dados.observacao.strip()}"

    executar_avanco_caixa(
        db, cx,
        origem=wf.FASE_POSVENDAS,
        destino=wf.proxima_fase(wf.FASE_POSVENDAS),
        ativas=ativas,
        usuario=None,
        obs=obs,
        cod_retorno=None,
        background_tasks=background_tasks,
    )
    logger.info("TaskHS financeiro: caixa %s movida para Financeiro (card=%s)",
                caixa_id, dados.card_id)
    return FinanceiroOut(movida=True, caixa_id=cx.id, fase=cx.fase)
```

> **Ordem das validações, de propósito:** o `NO_OP` vem **antes** da trava de Phoebus, para que reenvio em caixa já avançada responda 200 em vez de 409 — é o que mantém o laço do card inofensivo. A trava de Phoebus vem **antes** do `FASE_ERRADA` para que a mensagem de erro aponte a causa mais informativa: "essa caixa não é deste fluxo" é mais útil que "essa caixa está na fase errada".

- [ ] **Step 6: Registrar o router**

Em `backend/app/main.py`:

1. Na linha 8 (o import longo), acrescente `integracao_taskhs` logo depois de `integracao_growthhs`:

```bash
cd /home/ericks/github/GestorHS
sed -i '8s/integracao_growthhs, /integracao_growthhs, integracao_taskhs, /' backend/app/main.py
grep -n "integracao_taskhs" backend/app/main.py
```

2. Acrescente o `include_router` junto dos outros. Localize a linha de `integracao_growthhs.router` e ponha a nova embaixo:

```bash
cd /home/ericks/github/GestorHS
grep -n "integracao_growthhs.router" backend/app/main.py
```

```python
app.include_router(integracao_taskhs.router)
```

- [ ] **Step 7: Rodar e ver passar**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_integracao_taskhs.py -q
```
Esperado: PASS, 13 testes.

- [ ] **Step 8: Conferir que o GrowthHS continua intacto**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_integracao_growthhs_ganho.py tests/test_integracao_growthhs_auth.py tests/test_avanco_inbound.py -q
```
Esperado: PASS.

- [ ] **Step 9: Rodar a suíte inteira**

```bash
cd backend && source .venv/bin/activate && pytest -q 2>&1 | tail -5
```
Esperado: 4 falhas, a baseline.

- [ ] **Step 10: Commit**

```bash
cd /home/ericks/github/GestorHS
git add backend/app/core/config.py backend/app/api/deps.py \
        backend/app/api/integracao_taskhs.py backend/app/main.py \
        backend/tests/test_integracao_taskhs.py
git commit -m "$(cat <<'MSG'
feat(caixas): inbound do taskhs avanca a caixa para o financeiro

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

---

### Task 5: Documento de operação da adoção dos cards

Não tem teste automatizado: o alvo é o banco do TaskHS e quem executa é o Erick, no Konsole. O entregável é o procedimento, com a consulta de reconferência **antes** do `UPDATE` — o par card↔caixa é um levantamento de 18/09/2026 e card pode ser arquivado ou caixa pode andar de fase nesse meio-tempo.

**Files:**
- Create: `docs/operacao-taskhs-adocao-cards.md`

**Interfaces:**
- Consumes: nada
- Produces: nada em código

- [ ] **Step 1: Escrever o documento**

Crie `docs/operacao-taskhs-adocao-cards.md`:

```markdown
# Adoção dos cards manuais de Phoebus no TaskHS

**Data do levantamento:** 18/09/2026
**Executa:** Erick, no Konsole, contra o banco `taskhs`
**Pré-requisito:** o GestorHS com o critério estreito de espelhamento (`caixa_so_de_modulo`) já **deployado**

## Por que

Até 18/09/2026 o GestorHS não espelhava caixa com Phoebus, e o setor de Serviços criava esses cards à mão — eles têm `external_source` nulo. Com o critério estreito no ar, o GestorHS passa a espelhar essas caixas: sem adotar os cards manuais, o upsert **cria um segundo card** para a mesma caixa, e o board passa a mostrar `CX 1049` duas vezes. Foi o estrago dos 28 cards órfãos de jul–set/2026.

Adotar é gravar `external_source = 'gestorhs'` e `external_id = <id da caixa>` no card que já existe. O upsert então **encontra** esse card e o atualiza, em vez de criar outro.

⚠️ **`CardUpdate` da API do TaskHS não expõe `external_id`/`external_source`** — por isso é SQL, e não chamada de API.

## Os 8 cards (grupo A)

Todos na lista **202** (`🔬LIBERADOS DO LABORATÓRIO`), com a caixa na fase 6. **A 202 é exatamente a lista que o GestorHS usa para a fase 6**, então adotar não move card nenhum de lugar, não apaga histórico e não apaga comentário.

| card | caixa | cliente |
|---|---|---|
| 1935 | 1003 | ACTECH ALUMINA CHEMICAL TECHNOLOGY LTDA |
| 1964 | 1011 | CONSTRUTORA APIA S/A. |
| 1982 | 1028 | GERDAU AÇOS LONGOS S.A. |
| 1984 | 1030 | CONCESSIONARIA DAS LINHAS 5 E 17 DO METRO DE SAO PAULO S.A. |
| 2010 | 1041 | DIANA BIOENERGIA AVANHANDAVA SA (caixa mista) |
| 2012 | 1043 | VOTORANTIM CIMENTOS S/A |
| 2016 | 1047 | JF PASQUA CONDUTORES ELETRICOS EIRELI |
| 2018 | 1049 | CONSORCIO SAO BERNARDO AMBIENTAL |

## Os 4 que NÃO se adota (grupo B)

`639`, `670`, `685` e `692`. O GestorHS diz que essas caixas estão na fase 4 (Recebido) e o TaskHS tem os cards em `Serviços 🪛` / `Pendências`. Adotar arrastaria o card para a lista 196 (Expedição) no próximo espelhamento, desfazendo o trabalho de quem move o card.

⚠️ **Risco em aberto:** com o critério estreito no ar, o próximo avanço dessas 4 caixas cria um card novo na 196, ao lado do card manual. Resolver isso é decidir qual dos dois sistemas está certo, caixa por caixa — conversa própria, ainda não tida.

## Passo 1 — reconferir antes de gravar

```sql
select c.id card, c.title, c.list_id, c.archived,
       c.external_source, c.external_id
  from cards c
 where c.id in (1935,1964,1982,1984,2010,2012,2016,2018)
 order by c.id;
```

Confirme, para as 8 linhas: `external_source` **nulo**, `archived` **false**, `list_id` **202**. Se alguma divergir, pare e reavalie — o levantamento envelheceu.

E no banco `gestorhs`, confirme que as 8 caixas seguem na fase 6:

```sql
select id, fase from caixas
 where id in (1003,1011,1028,1030,1041,1043,1047,1049) order by id;
```

## Passo 2 — gravar

```sql
-- Adota os 8 cards manuais das caixas de Phoebus paradas no Pos-Vendas.
-- Os cards NAO saem de lugar: a lista 202 ja e' a que o GestorHS usa para a fase 6.
BEGIN;
UPDATE cards SET external_source = 'gestorhs', external_id = '1003' WHERE id = 1935;
UPDATE cards SET external_source = 'gestorhs', external_id = '1011' WHERE id = 1964;
UPDATE cards SET external_source = 'gestorhs', external_id = '1028' WHERE id = 1982;
UPDATE cards SET external_source = 'gestorhs', external_id = '1030' WHERE id = 1984;
UPDATE cards SET external_source = 'gestorhs', external_id = '1041' WHERE id = 2010;
UPDATE cards SET external_source = 'gestorhs', external_id = '1043' WHERE id = 2012;
UPDATE cards SET external_source = 'gestorhs', external_id = '1047' WHERE id = 2016;
UPDATE cards SET external_source = 'gestorhs', external_id = '1049' WHERE id = 2018;
COMMIT;
```

⚠️ **`uq_card_external` é `UniqueConstraint("external_source", "external_id")`.** Se alguma dessas caixas já tiver card espelhado — não deveria, o gate bloqueou desde sempre — o `UPDATE` viola a constraint. O `BEGIN`/`COMMIT` existe para abortar o lote inteiro nesse caso, em vez de deixar metade adotada.

## Passo 3 — conferir

Repita a consulta do Passo 1. As 8 linhas devem ter `external_source = 'gestorhs'` e o `external_id` da tabela acima, **com `list_id` ainda 202**.

## Rollback

```sql
BEGIN;
UPDATE cards SET external_source = NULL, external_id = NULL
 WHERE id in (1935,1964,1982,1984,2010,2012,2016,2018);
COMMIT;
```

Devolve os cards ao estado manual. Não desfaz card que o GestorHS tenha criado depois — para esses, arquive pela tela.
```

- [ ] **Step 2: Commit**

```bash
cd /home/ericks/github/GestorHS
git add docs/operacao-taskhs-adocao-cards.md
git commit -m "$(cat <<'MSG'
docs(caixas): procedimento de adocao dos cards manuais de phoebus

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

---

### Task 6: Documentação no `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: nada
- Produces: nada em código

- [ ] **Step 1: Documentar os dois predicados e o espelhamento estreito**

Na seção "Integracao com o TaskHS", logo depois do parágrafo que começa com `⚠️ **Um card por CAIXA, nunca por OS**`, acrescente:

```markdown
⚠️ **Só a caixa 100% Módulo fica fora do board do TaskHS** (`fluxo_modulo.caixa_so_de_modulo`, `all(== 47)`). Caixa com Phoebus dentro — sozinho, com o módulo dele, ou junto de aparelho comum — **vira card**: ela passa por serviço, e o card é o elo que o inbound usa para achar a caixa. Mudou em 18/09/2026; antes o critério era `caixa_de_modulo` (`any`), largo demais, e o setor de Serviços criava esses cards à mão (12 deles, dos quais 8 foram adotados — ver [docs/operacao-taskhs-adocao-cards.md](docs/operacao-taskhs-adocao-cards.md)).

⚠️ **O board do GrowthHS mantém o critério LARGO** (`caixa_de_modulo`, `any`), e a divergência é intencional: aquele board é comercial e Phoebus não tem proposta nele. Ao mexer num, não "uniformize" o outro.
```

- [ ] **Step 2: Documentar o endpoint inbound**

Ainda na seção do TaskHS, acrescente ao fim:

```markdown
**Inbound: o card no Financeiro avança a caixa.** `POST /integracao/taskhs/caixas/{id}/financeiro` ([integracao_taskhs.py](backend/app/api/integracao_taskhs.py)) move a caixa de Pós-Vendas(6) para Financeiro(10), disparado pela automação do TaskHS quando o card entra na lista **205**. Existe porque a caixa com Phoebus não tem proposta no GrowthHS, logo não tem o gatilho de "Ganho". Chave **própria** (`TASKHS_INBOUND_API_KEY`), vazia = 503.

- ⚠️ **Recusa 409 caixa sem Phoebus.** A trava é positiva (`_tem_phoebus`), não `not caixa_so_de_modulo(...)` — a negação deixaria passar a caixa **normal**, e sair da fase 6 grava `aceite`/`data_aceite`. Na caixa normal esse aval vem do "Ganho" no GrowthHS; deixar o TaskHS gravá-lo forjaria aprovação comercial.
- **O laço card → caixa → card se fecha sozinho:** avançar a caixa move o card para a 205, o que dispara a automação de volta. Não é loop porque a regra em [core/avanco_inbound.py](backend/app/core/avanco_inbound.py) devolve `no_op` para caixa já na 10 e o endpoint responde `movida: false`.
- A regra "essa caixa pode avançar agora?" é **compartilhada** com o inbound do GrowthHS (`core/avanco_inbound.py`). Ao mexer, lembre que são dois chamadores.
- O lado TaskHS (a ação `avisar_gestorhs` no motor de automação) vive no **outro repo**; a especificação dos dois lados está em [docs/superpowers/specs/2026-09-18-taskhs-inbound-financeiro-design.md](docs/superpowers/specs/2026-09-18-taskhs-inbound-financeiro-design.md).
```

- [ ] **Step 3: Conferir que não sobrou referência à regra antiga**

```bash
cd /home/ericks/github/GestorHS
grep -n "caixa de módulo/phoebus\|caixa deles ja nao vira card" CLAUDE.md || echo "nenhuma sobra"
```

- [ ] **Step 4: Commit**

```bash
cd /home/ericks/github/GestorHS
git add CLAUDE.md
git commit -m "$(cat <<'MSG'
docs(caixas): inbound do taskhs e espelhamento estreito

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

---

## Verificação final (antes de dizer que acabou)

- [ ] `cd backend && source .venv/bin/activate && pytest -q 2>&1 | tail -5` → **4 falhas**, as da baseline, nenhuma a mais.
- [ ] `grep -rn "caixa_de_modulo" backend/app/api/espelhamento.py` → nenhuma chamada (só comentário de contraste, se houver).
- [ ] `grep -rn "caixa_de_modulo" backend/app/api/growthhs_cards.py backend/app/api/logs_integracao.py` → **continua existindo**. O board comercial mantém o critério largo.
- [ ] `grep -rn "_FASES_JA_AVANCADAS\|^FASE_POSVENDAS = 6" backend/app/api/` → vazio. As constantes locais saíram.
- [ ] `curl -s localhost:8001/openapi.json | python3 -c "import json,sys; print([p for p in json.load(sys.stdin)['paths'] if 'taskhs' in p])"` com a API local de pé → mostra `/integracao/taskhs/caixas/{caixa_id}/financeiro`.
- [ ] `git log --oneline -6` → seis commits, um por task.

## Depois do merge — ordem de implantação (o Erick executa)

A ordem importa. Ela está inteira na seção "Ordem de implantação" da spec; o resumo:

1. **Deployar o GestorHS** com `TASKHS_INBOUND_API_KEY` **vazia**. O endpoint fica inerte (503).
2. **Rodar a adoção** dos 8 cards, seguindo [docs/operacao-taskhs-adocao-cards.md](../../operacao-taskhs-adocao-cards.md) — depois do deploy e antes de qualquer avanço dessas caixas.
3. **Decidir o grupo B** (639, 670, 685, 692) antes que algo toque essas caixas.
4. **Implementar o lado TaskHS** numa sessão aberta em `~/github/TaskHS` (`cl TaskHS`), a partir da spec.
5. **Ligar:** gerar a chave, pôr o mesmo valor nos dois lados, cadastrar a automação na lista 205.
6. **Validar com uma caixa só**, movendo o card de 202 para 205 à mão, antes de contar ao setor.

## Fora do escopo deste plano

- **Todo o lado TaskHS.** Outro repo, outra sessão, plano próprio.
- **Os 4 cards do grupo B** e os 365 cards manuais legados.
- **O board do GrowthHS.**
- **Changelog e versão.** Nenhuma tela do GestorHS muda; fica a critério do Erick.
