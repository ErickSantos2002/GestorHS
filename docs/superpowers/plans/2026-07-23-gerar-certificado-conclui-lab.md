# Gerar certificado conclui o laboratório — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gerar (ou regerar) um certificado de calibração/manutenção passa a marcar automaticamente a OS como concluída no laboratório (`desfecho_lab="concluido"`), destravando o avanço da caixa — sem botão dedicado.

**Architecture:** Um helper puro-de-orquestração `concluir_laboratorio` centraliza as ações de "concluir lab" (espelhar na frota + marcar desfecho), hoje inline em `marcar_desfecho_lab`. O endpoint `gerar-certificado` passa a chamá-lo quando a OS está na fase Laboratório com desfecho pendente. O contador "prontos" e `pode_avancar_caixa` ficam intactos — continuam lendo `Ordem.desfecho_lab`, que agora é preenchido no momento da geração.

**Tech Stack:** Python 3.12 · FastAPI · SQLAlchemy 2 · pytest (SQLite in-memory).

## Global Constraints

- Domínio em **PT-BR** (nomes de funções, variáveis, mensagens). Manter.
- Fases são IDs fixos; usar as constantes de [os_workflow.py](../../../backend/app/core/os_workflow.py) (`FASE_LABORATORIO`, `DESFECHO_CONCLUIDO`, `DESFECHO_PENDENTE`), nunca hard-codar números.
- Lógica de negócio pura vai em `core/`; orquestração com I/O em `api/`. `concluir_laboratorio` é orquestração → fica em `app/api/ordens_acoes.py` (junto de `espelhar_calibracao`).
- Commits: Conventional Commits em **português sem acentos**, assunto de uma linha, sem corpo, sem trailer de co-autor. **Não commitar/pushar sem o Erick pedir** — os passos de `git commit` abaixo só rodam sob pedido dele.
- Testes backend: SQLite in-memory; espelham o nome do alvo (`test_<modulo>.py`). Rodar de `backend/` com a venv ativa.

---

### Task 1: Extrair helper `concluir_laboratorio`

Refatoração pura: extrai as ações de "concluir lab" para um helper reutilizável, sem mudar comportamento. `marcar_desfecho_lab` passa a usá-lo. Os testes existentes de desfecho (`test_caixa_avancar.py::test_marcar_concluido_ok`, `test_marcar_sem_conserto_ok`) continuam verdes.

**Files:**
- Modify: `backend/app/api/ordens_acoes.py` (adicionar import de `os_workflow` + o helper após `espelhar_calibracao`, ~linha 64)
- Modify: `backend/app/api/ordens.py:218-225` (usar o helper em `marcar_desfecho_lab`; ajustar imports)
- Test: `backend/tests/test_ordens_acoes.py` (novo)

**Interfaces:**
- Produces: `concluir_laboratorio(db: Session, ordem: Ordem) -> None` — espelha os resultados na frota (`espelhar_calibracao`) e marca `ordem.desfecho_lab = DESFECHO_CONCLUIDO`, `ordem.desfecho_lab_obs = None`. **Não registra log** — quem chama registra com o próprio texto.

- [ ] **Step 1: Escrever o teste que falha**

Criar `backend/tests/test_ordens_acoes.py`:

```python
def test_concluir_laboratorio_espelha_e_marca(db_session):
    from app.models import Cliente, Equipamento, EquipamentoCliente, Ordem
    from app.api.ordens_acoes import concluir_laboratorio

    cat = Equipamento(descricao="Mark X"); db_session.add(cat); db_session.flush()
    cli = Cliente(nome="ACME"); db_session.add(cli); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=cat.id, serie="S1")
    db_session.add(ec); db_session.flush()
    o = Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=5, situacao="E",
              tipo_servico="C", calib_cert="C-1", calib_situacao="Aprovado",
              desfecho_lab="pendente")
    db_session.add(o); db_session.commit(); db_session.refresh(o)

    concluir_laboratorio(db_session, o)
    db_session.commit()
    db_session.refresh(o); db_session.refresh(ec)

    assert o.desfecho_lab == "concluido"
    assert o.desfecho_lab_obs is None
    assert ec.calib_cert == "C-1"          # espelhado na frota
    assert ec.calib_situacao == "Aprovado"
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Run: `pytest tests/test_ordens_acoes.py -v`
Expected: FAIL com `ImportError: cannot import name 'concluir_laboratorio'`.

- [ ] **Step 3: Implementar o helper**

Em `backend/app/api/ordens_acoes.py`, adicionar o import de workflow logo após os imports existentes (topo do arquivo, após a linha `from app.models import ...`):

```python
from app.core import os_workflow as wf
```

E adicionar o helper logo após a função `espelhar_calibracao` (após a linha 64):

```python
def concluir_laboratorio(db: Session, ordem) -> None:
    """Conclui o laboratório de uma OS: espelha os resultados na frota e marca o
    desfecho. NÃO registra log — cada chamador loga com o próprio texto.
    Idempotente na prática: `espelhar_calibracao` só sobrescreve campos do
    equipamento_cliente, sem inserir histórico."""
    espelhar_calibracao(db, ordem)
    ordem.desfecho_lab = wf.DESFECHO_CONCLUIDO
    ordem.desfecho_lab_obs = None
```

- [ ] **Step 4: Rodar o teste e confirmar que passa**

Run: `pytest tests/test_ordens_acoes.py -v`
Expected: PASS.

- [ ] **Step 5: Refatorar `marcar_desfecho_lab` para usar o helper**

Em `backend/app/api/ordens.py`, ajustar o import (linha 10) para incluir `concluir_laboratorio`. Após o ajuste, `espelhar_calibracao` pode ficar sem uso direto neste arquivo — conferir com `grep -n espelhar_calibracao app/api/ordens.py`; se não houver outro uso, removê-lo do import:

```python
from app.api.ordens_acoes import agora, registrar_log, exige_funcao_da_fase, concluir_laboratorio
```

Trocar o corpo do ramo `concluido` em `marcar_desfecho_lab` (linhas 218-225) por:

```python
    if dados.desfecho == wf.DESFECHO_CONCLUIDO:
        tem_cert = db.query(OSCertificado).filter(OSCertificado.os == ordem.id).first() is not None
        if not tem_cert:
            raise HTTPException(status_code=409, detail="gere o certificado antes de concluir")
        concluir_laboratorio(db, ordem)
        texto = "Laboratório concluído (aparelho)"
```

(O ramo `else`/`sem_conserto` e o `registrar_log(db, ordem, usuario, texto)` na linha 232 ficam como estão.)

- [ ] **Step 6: Rodar os testes de desfecho e confirmar que seguem verdes**

Run: `pytest tests/test_ordens_acoes.py tests/test_caixa_avancar.py -v`
Expected: PASS — em especial `test_marcar_concluido_ok`, `test_marcar_concluido_sem_certificado_falha`, `test_marcar_sem_conserto_ok`.

- [ ] **Step 7: Commit** (somente quando o Erick pedir)

```bash
git add backend/app/api/ordens_acoes.py backend/app/api/ordens.py backend/tests/test_ordens_acoes.py
git commit -m "refactor(ordens): extrai concluir_laboratorio de marcar_desfecho_lab"
```

---

### Task 2: Gerar certificado conclui o laboratório

O endpoint `gerar-certificado` conclui a OS quando ela está no Laboratório com desfecho pendente.

**Files:**
- Modify: `backend/app/api/certificados_os.py:59-90` (nomear o usuário; concluir após gerar; imports)
- Test: `backend/tests/test_certificado_os_api.py` (adicionar testes)

**Interfaces:**
- Consumes: `concluir_laboratorio(db, ordem)` da Task 1; `wf.FASE_LABORATORIO`, `wf.DESFECHO_PENDENTE`; `registrar_log(db, ordem, usuario, texto)`.

- [ ] **Step 1: Escrever os testes que falham**

Adicionar ao final de `backend/tests/test_certificado_os_api.py` (o helper `_os_com_modelo` já cria a OS em fase 5 com `desfecho_lab` default "pendente"):

```python
def test_gerar_certificado_conclui_lab(client, usuario_admin, db_session):
    h = _headers(client, "admin@hs.com", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C",), tipo_servico="C")
    r = client.post(f"/ordens/{oid}/gerar-certificado", headers=h)
    assert r.status_code == 200
    from app.models import Ordem, EquipamentoCliente
    o = db_session.get(Ordem, oid); db_session.refresh(o)
    assert o.desfecho_lab == "concluido"          # OS pronta para a caixa avançar
    ec = db_session.get(EquipamentoCliente, o.equipamento_cliente)
    assert ec.calib_cert == "C-1"                 # espelhado na frota


def test_gerar_nao_reabre_sem_conserto(client, usuario_admin, db_session):
    h = _headers(client, "admin@hs.com", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C",), tipo_servico="C")
    from app.models import Ordem
    o = db_session.get(Ordem, oid); o.desfecho_lab = "sem_conserto"
    db_session.commit()
    r = client.post(f"/ordens/{oid}/gerar-certificado", headers=h)
    assert r.status_code == 200
    db_session.refresh(o)
    assert o.desfecho_lab == "sem_conserto"       # guarda `== pendente` não sobrescreve


def test_gerar_fora_do_lab_nao_conclui(client, usuario_admin, db_session):
    h = _headers(client, "admin@hs.com", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C",), tipo_servico="C")
    from app.models import Ordem
    o = db_session.get(Ordem, oid); o.fase = 8   # já passou do laboratório
    db_session.commit()
    r = client.post(f"/ordens/{oid}/gerar-certificado", headers=h)
    assert r.status_code == 200
    db_session.refresh(o)
    assert o.desfecho_lab == "pendente"           # guarda de fase bloqueia
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `pytest tests/test_certificado_os_api.py -k "conclui or reabre or fora_do_lab" -v`
Expected: FAIL — `test_gerar_certificado_conclui_lab` acusa `desfecho_lab == "pendente"` (ainda não conclui).

- [ ] **Step 3: Implementar a conclusão no endpoint**

Em `backend/app/api/certificados_os.py`, ampliar os imports:

```python
from app.api.ordens_acoes import agora, concluir_laboratorio, registrar_log
from app.core import os_workflow as wf
```

Nomear o usuário na assinatura de `gerar` (linha 60), trocando `_: Usuario = Depends(_gerar)` por `usuario: Usuario = Depends(_gerar)`.

No corpo de `gerar`, entre `gerados = gerar_certificados(...)` (linha 86) e `db.commit()` (linha 87), inserir:

```python
    gerados = gerar_certificados(db, ordem, tipos_para(ordem))
    if ordem.fase == wf.FASE_LABORATORIO and ordem.desfecho_lab == wf.DESFECHO_PENDENTE:
        concluir_laboratorio(db, ordem)
        registrar_log(db, ordem, usuario, "Laboratório concluído — certificado gerado")
    db.commit()
```

- [ ] **Step 4: Rodar e confirmar que passam**

Run: `pytest tests/test_certificado_os_api.py -v`
Expected: PASS — os 3 novos testes e todos os pré-existentes (nenhum assere `desfecho_lab`, então seguem verdes).

- [ ] **Step 5: Commit** (somente quando o Erick pedir)

```bash
git add backend/app/api/certificados_os.py backend/tests/test_certificado_os_api.py
git commit -m "feat(cert): gerar certificado conclui o laboratorio da OS"
```

---

### Task 3: Fim-a-fim — gerar certificado destrava a caixa

Prova o objetivo real: com uma caixa em Laboratório e uma OS pendente, gerar o certificado faz a caixa virar 1/1 prontos e liberar o avanço 5→6.

**Files:**
- Test: `backend/tests/test_caixa_avancar.py` (adicionar teste e2e)

**Interfaces:**
- Consumes: fixtures `client_lab`; endpoints `POST /ordens/{id}/gerar-certificado`, `GET /caixas/quadro`, `POST /caixas/{id}/avancar`.

- [ ] **Step 1: Escrever o teste e2e que falha**

Adicionar ao final de `backend/tests/test_caixa_avancar.py`:

```python
def test_gerar_certificado_destrava_caixa(client_lab, db_session):
    """Caixa em Laboratório com 1 OS pendente: gerar o certificado marca a OS como
    concluida e libera o avanco 5->6, sem passar pelo endpoint de desfecho."""
    from app.models import (Cliente, Caixa, Equipamento, EquipamentoCliente,
                             Ordem, CertificadoModelo)
    cat = Equipamento(descricao="Mark X"); db_session.add(cat); db_session.flush()
    cli = Cliente(nome="ACME"); db_session.add(cli); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=cat.id, serie="S1")
    cx = Caixa(obs="lote e2e", fase=5)
    db_session.add_all([ec, cx]); db_session.flush()
    o = Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=5, situacao="E",
              tipo_servico="C", caixa=cx.id, desfecho_lab="pendente")
    db_session.add(o)
    db_session.add(CertificadoModelo(equipamento=cat.id, tipo="C", texto="<p>[serie]</p>"))
    db_session.commit()

    # trava antes: 0/1 prontos, avanco barrado
    trava = client_lab.post(f"/caixas/{cx.id}/avancar", json={})
    assert trava.status_code == 409

    r = client_lab.post(f"/ordens/{o.id}/gerar-certificado")
    assert r.status_code == 200

    cols = {c["fase"]: c for c in client_lab.get("/caixas/quadro").json()}
    cx_item = next(c for c in cols[5]["caixas"] if c["id"] == cx.id)
    assert cx_item["prontos"] == 1 and cx_item["pendentes"] == 0

    ok = client_lab.post(f"/caixas/{cx.id}/avancar", json={})
    assert ok.status_code == 200
    assert ok.json()["fase"] == 6
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `pytest tests/test_caixa_avancar.py::test_gerar_certificado_destrava_caixa -v`
Expected: se as Tasks 1-2 já estiverem implementadas, este teste já passa (é a prova de integração). Se rodado antes delas, FAIL no `assert cx_item["prontos"] == 1`.

- [ ] **Step 3: Rodar a suíte inteira**

Run: `pytest -q`
Expected: PASS (todos).

- [ ] **Step 4: Commit** (somente quando o Erick pedir)

```bash
git add backend/tests/test_caixa_avancar.py
git commit -m "test(caixa): cobre gerar certificado destravando o avanco da caixa"
```

---

### Task 4: Changelog (mudança visível ao usuário)

O comportamento muda o que o usuário vê (gerar certificado agora libera a caixa). Convenção do projeto: fechar a entrega com bump de versão no changelog.

**Files:**
- Modify: `frontend/src/app/changelog/data.ts` (nova entrada no topo — versão mais nova primeiro)

- [ ] **Step 1: Adicionar a entrada de changelog**

Em `frontend/src/app/changelog/data.ts`, inserir uma nova entrada como **primeiro** item do array (é a que vira "versão atual"), seguindo o formato das entradas existentes (conferir a versão anterior no arquivo e incrementar o patch/minor conforme o padrão do projeto). Conteúdo, em PT-BR:

- Título/versão: algo como `vX.Y.Z — certificado conclui o laboratorio`
- Descrição: "Gerar o certificado de calibração ou manutenção agora conclui o laboratório da OS automaticamente e libera o avanço da caixa — não é mais preciso um passo separado."

- [ ] **Step 2: Verificar build do frontend**

Run (de `frontend/`): `npm run lint && npx tsc -b --noEmit`
Expected: sem erros.

- [ ] **Step 3: Commit** (somente quando o Erick pedir)

```bash
git add frontend/src/app/changelog/data.ts
git commit -m "docs(changelog): vX.Y.Z — certificado conclui o laboratorio"
```

---

## Notas de verificação (self-review)

- **Cobertura da spec:** guarda `fase == LABORATORIO and desfecho == pendente` (Task 2 Step 3) cobre "só se estiver no Laboratório e pendente"; não-reabertura de `sem_conserto` (Task 2 test) e não-conclusão fora do lab (Task 2 test) cobrem as bordas; espelhamento coberto na Task 1 e Task 2. `pode_avancar_caixa`/contador intactos — provado pelo e2e (Task 3).
- **Sem espelhamento duplicado:** `espelhar_calibracao` é idempotente (sobrescreve campos do `equipamento_cliente`, não insere histórico); o re-espelhamento na saída da caixa (`caixas.py`) segue inofensivo.
- **Endpoint `desfecho-lab` preservado:** o "Sem conserto" do frontend e o `concluido` manual continuam funcionando (Task 1 mantém o comportamento).
