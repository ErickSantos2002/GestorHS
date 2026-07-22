# Caixa como unidade de movimento — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer a Caixa ser a unidade que anda pelas fases (no lugar da OS individual), formalizando a regra "a caixa só avança quando todos os aparelhos terminam o laboratório", e refletir isso como 1 card por caixa no TaskHS e no GrowthHS.

**Architecture:** "Caixa dirige, OS espelha" — `caixas.fase` passa a ser a unidade de movimento; `ordem.fase` continua existindo e é mantida sempre igual à da caixa (sincronia num ponto único: o avançar da caixa fan-out para todas as OS). O progresso individual do laboratório vira `ordens.desfecho_lab`. O avançar/cancelar migram do endpoint de OS para um endpoint de Caixa. As funções puras de espelhamento passam a receber a caixa + suas ordens e agregam.

**Tech Stack:** Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · pytest (SQLite in-memory) — backend. React 19 · TS · Vite · Vitest — frontend.

## Global Constraints

- **Domínio em PT-BR** — nomes de modelos, rotas, variáveis, mensagens. Manter.
- **Commits** Conventional Commits em português **sem acentos** (ASCII), assunto de uma linha, **sem trailer de co-autor**. Escopos: `caixa`, `os`, `cert`, `integr`, `ux`, `ui`.
- **Backend puro em `core/`** (sem I/O, testável isolado); routers em `api/` registrados em `main.py`; um modelo por arquivo.
- **Testes backend**: SQLite in-memory via `conftest.py`, arquivo `test_<modulo>.py`.
- **Forward-only**: sem backfill de cards externos já enviados; OS em voo escoam no modelo antigo.
- **Ordem de fases é lógica, não numérica**: Financeiro é ID 10 (maior que 7/8). Sempre usar `os_workflow.posicao()` / `ORDEM_FASES`, nunca comparar IDs crus.
- **Trabalho todo na branch `feat/caixa-unidade-movimento`**; merge + migration rodados pelo Erick no fim do dia.

## Decisões de mecânica do avançar-da-caixa (derivadas da spec/brainstorm)

Cada transição da caixa aplica **um** efeito por fase, fan-out para todas as OS ativas da caixa:

| Transição | Gate | Efeito por OS | Valor de lote coletado |
|-----------|------|---------------|------------------------|
| Recebido(4)→Lab(5) | nenhum | — | nenhum |
| Lab(5)→Pós-Vendas(6) | **nenhuma OS `pendente`** | `espelhar_calibracao` (OS `concluido`); OS `sem_conserto` não espelha | nenhum |
| Pós-Vendas(6)→Financeiro(10) | nenhum | `aceite=True`, `data_aceite=agora()` | nenhum |
| Financeiro(10)→Preparando(7) | **caixa tem NF** | `pago=True`, `data_pagamento=agora()` | 1 NF (já anexada à caixa) |
| Preparando(7)→Finalizada(8) | nenhum | `cod_retorno=<lote>`, `data_retorno=agora()`, `situacao="F"` | 1 `cod_retorno` (rastreio) |

- **`prox_calibragem` é por OS**, definido na geração do certificado / no laboratório (intrínseco ao aparelho) — **não** é mais coletado no avançar.
- **NF é 1 por caixa** (o Erick confirmou "uma NF nesses 10 aparelhos"): anexada uma vez no nível da caixa e o número/arquivo é replicado em `ordem.nota_fiscal` / `ordem.nota_fiscal_numero` de todas as OS ativas (mantém o espelhamento e o portal por-OS funcionando). Gate Financeiro→Preparando: todas as OS ativas com `nota_fiscal` preenchida.
- **`cod_retorno` é 1 por caixa** (um envio só): coletado no modal de finalizar da caixa e replicado em todas as OS ativas.
- **`sem_conserto`** conta como "pronto" para o gate do laboratório, mas **não** dispara `espelhar_calibracao` (não há calibração).

---

## Estrutura de arquivos

**Backend — criar:**
- `alembic/versions/0019_caixa_unidade_movimento.py` — migração (colunas + backfill).
- `app/schemas/caixa_acoes.py` — schemas dos endpoints de ação da caixa (avançar/cancelar/finalizar/desfecho).
- `tests/test_caixa_workflow.py` — testes da máquina de estados/gate (puro).
- `tests/test_caixa_avancar.py` — testes do endpoint de avançar/cancelar da caixa.
- `tests/test_taskhs_caixa.py` — testes de agregação do payload TaskHS por caixa.
- `tests/test_growthhs_caixa.py` — testes de agregação do card GrowthHS por caixa.

**Backend — modificar:**
- `app/models/caixa.py` — coluna `fase` + relationship + property `fase_atual`.
- `app/models/ordem.py` — colunas `desfecho_lab`, `desfecho_lab_obs`.
- `app/core/os_workflow.py` — helper `pode_avancar_caixa()` / constantes de desfecho (puro).
- `app/api/caixas.py` — endpoints `avancar`/`cancelar`/`finalizar` da caixa; invariante cliente único em `vincular_ordem`.
- `app/api/ordens.py` — endpoint de marcar desfecho da OS; remover botão-avançar por-OS do fluxo (endpoint per-OS `avancar` deixa de ser o caminho — ver Task 8).
- `app/core/taskhs.py` — `montar_titulo`/`montar_obs`/`montar_payload` agregando N ordens.
- `app/core/growthhs_os.py` — `montar_card_os` com `devices[]` de N aparelhos.
- `app/api/espelhamento.py` — `agendar_espelhamento` a partir da caixa.
- `app/api/growthhs_cards.py` — `agendar_card_os` a partir da caixa.
- `app/schemas/caixas.py` — expor `fase`/`desfecho_lab` nos schemas de saída.

**Frontend — modificar:** (detalhado após o mapeamento — Tasks 12+)

---

## Task 1: Migração — colunas `caixas.fase`, `ordens.desfecho_lab` + backfill

**Files:**
- Create: `backend/alembic/versions/0019_caixa_unidade_movimento.py`

**Interfaces:**
- Produces: colunas `caixas.fase` (Integer, FK `fases.id`, nullable), `ordens.desfecho_lab` (String(20), default `'pendente'`), `ordens.desfecho_lab_obs` (Text, nullable).

- [ ] **Step 1: Escrever a migração (upgrade + downgrade + backfill)**

```python
"""caixa unidade de movimento: caixas.fase + ordens.desfecho_lab + backfill"""
import sqlalchemy as sa
from alembic import op

revision = "0019_caixa_unidade_movimento"
down_revision = "0018_log_integracao"
branch_labels = None
depends_on = None

# Ordem logica das fases (espelha app/core/os_workflow.ORDEM_FASES).
# Fase > Laboratorio(pos 1) ja passou do lab -> desfecho concluido no backfill.
ORDEM_FASES = {4: 0, 5: 1, 6: 2, 10: 3, 7: 4, 8: 5}
POS_LAB = 1


def upgrade() -> None:
    op.add_column("caixas", sa.Column("fase", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_caixas_fase", "caixas", "fases", ["fase"], ["id"])
    op.add_column("ordens", sa.Column("desfecho_lab", sa.String(length=20),
                                      nullable=False, server_default="pendente"))
    op.add_column("ordens", sa.Column("desfecho_lab_obs", sa.Text(), nullable=True))

    conn = op.get_bind()
    # 1) caixa.fase = a menor fase (por posicao logica) entre as OS ativas da caixa;
    #    caixas so com OS terminais ou vazias ficam com fase NULL (nao andam mais).
    caixas = conn.execute(sa.text(
        "SELECT DISTINCT caixa FROM ordens WHERE caixa IS NOT NULL"
    )).fetchall()
    for (caixa_id,) in caixas:
        fases = conn.execute(sa.text(
            "SELECT fase FROM ordens WHERE caixa = :c AND fase IS NOT NULL"
        ), {"c": caixa_id}).fetchall()
        ativas = [f for (f,) in fases if f in ORDEM_FASES and f != 8 and f != 9]
        if not ativas:
            continue
        menor = min(ativas, key=lambda f: ORDEM_FASES[f])
        conn.execute(sa.text("UPDATE caixas SET fase = :f WHERE id = :c"),
                     {"f": menor, "c": caixa_id})

    # 2) desfecho_lab: OS ativas cuja fase ja passou do laboratorio -> concluido.
    #    As demais ficam no default 'pendente'. Conservador (operador reconfirma).
    ja_passou = [str(f) for f, pos in ORDEM_FASES.items() if pos > POS_LAB and f != 8]
    if ja_passou:
        conn.execute(sa.text(
            f"UPDATE ordens SET desfecho_lab = 'concluido' "
            f"WHERE fase IN ({','.join(ja_passou)})"
        ))


def downgrade() -> None:
    op.drop_column("ordens", "desfecho_lab_obs")
    op.drop_column("ordens", "desfecho_lab")
    op.drop_constraint("fk_caixas_fase", "caixas", type_="foreignkey")
    op.drop_column("caixas", "fase")
```

- [ ] **Step 2: Rodar a suíte para garantir que o schema novo sobe no SQLite de teste**

Run: `cd backend && source .venv/bin/activate && pytest -q`
Expected: PASS (a suíte cria as tabelas pelos modelos; este passo confirma que nada quebrou antes de mexer nos modelos). Se `conftest.py` cria via `Base.metadata`, a migração não roda nos testes — o objetivo aqui é só baseline verde.

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/0019_caixa_unidade_movimento.py
git commit -m "feat(caixa): migracao fase na caixa e desfecho_lab na os"
```

---

## Task 2: Modelos — `Caixa.fase` e `Ordem.desfecho_lab`

**Files:**
- Modify: `backend/app/models/caixa.py`
- Modify: `backend/app/models/ordem.py:14-16` (após `caixa` / bloco de colunas)
- Test: `backend/tests/test_caixa_workflow.py`

**Interfaces:**
- Produces: `Caixa.fase` (Column Integer FK), `Caixa.fase_rel`, `Caixa.fase_descricao`, `Caixa.fase_cor`; `Ordem.desfecho_lab` (str), `Ordem.desfecho_lab_obs` (str|None).

- [ ] **Step 1: Escrever o teste dos atributos novos**

```python
# backend/tests/test_caixa_workflow.py
from app.models import Caixa, Ordem


def test_caixa_tem_coluna_fase():
    cx = Caixa(fase=4)
    assert cx.fase == 4


def test_ordem_desfecho_lab_default_pendente(db_session):
    # db_session: fixture do conftest que cria as tabelas em memoria
    from app.models import Cliente
    cli = Cliente(nome="ACME")
    db_session.add(cli)
    db_session.flush()
    o = Ordem(cliente=cli.id, fase=5)
    db_session.add(o)
    db_session.flush()
    assert o.desfecho_lab == "pendente"
    assert o.desfecho_lab_obs is None
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd backend && pytest tests/test_caixa_workflow.py -v`
Expected: FAIL (`TypeError: 'fase' is an invalid keyword` ou `AttributeError`).

- [ ] **Step 3: Adicionar `fase` ao modelo `Caixa`**

```python
# backend/app/models/caixa.py
from sqlalchemy import Column, Integer, String, Date, ForeignKey
from sqlalchemy.orm import relationship
from app.models.database import Base


class Caixa(Base):
    __tablename__ = "caixas"

    id = Column(Integer, primary_key=True, index=True)
    data = Column(Date, nullable=True)
    obs = Column(String(1000), nullable=True)
    fase = Column(Integer, ForeignKey("fases.id"), nullable=True)

    ordens = relationship("Ordem", back_populates="caixa_rel", lazy="selectin")
    fase_rel = relationship("Fase", lazy="joined")

    @property
    def total_os(self) -> int:
        return len(self.ordens)

    @property
    def clientes(self) -> list[str]:
        nomes = {o.cliente_nome for o in self.ordens if o.cliente_nome}
        return sorted(nomes)

    @property
    def fase_descricao(self):
        return self.fase_rel.descricao if self.fase_rel else None

    @property
    def fase_cor(self):
        return self.fase_rel.cor if self.fase_rel else None
```

- [ ] **Step 4: Adicionar `desfecho_lab` ao modelo `Ordem`**

Em `backend/app/models/ordem.py`, logo após a linha `caixa = Column(...)` (linha 14):

```python
    desfecho_lab = Column(String(20), nullable=False, default="pendente")
    desfecho_lab_obs = Column(Text, nullable=True)
```

(`Text` já está importado na linha 1.)

- [ ] **Step 5: Rodar e ver passar**

Run: `cd backend && pytest tests/test_caixa_workflow.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/caixa.py backend/app/models/ordem.py backend/tests/test_caixa_workflow.py
git commit -m "feat(caixa): fase na caixa e desfecho_lab na ordem nos modelos"
```

---

## Task 3: Workflow puro — gate `pode_avancar_caixa`

**Files:**
- Modify: `backend/app/core/os_workflow.py`
- Test: `backend/tests/test_caixa_workflow.py`

**Interfaces:**
- Consumes: `proxima_fase`, `eh_ativa`, `FASE_LABORATORIO` (já existentes).
- Produces:
  - Constantes `DESFECHO_PENDENTE="pendente"`, `DESFECHO_CONCLUIDO="concluido"`, `DESFECHO_SEM_CONSERTO="sem_conserto"`, `DESFECHOS_TERMINAIS=("concluido","sem_conserto")`.
  - `desfechos_pendentes(desfechos: list[str]) -> int` — quantos ainda `pendente`.
  - `pode_avancar_caixa(fase_atual: int, desfechos: list[str]) -> tuple[bool, str|None]` — `(True, None)` se pode; `(False, motivo)` se travado. Só a transição a partir de `FASE_LABORATORIO` checa desfechos.

- [ ] **Step 1: Escrever os testes do gate**

```python
# adicionar em backend/tests/test_caixa_workflow.py
from app.core import os_workflow as wf


def test_gate_lab_bloqueia_com_pendente():
    ok, motivo = wf.pode_avancar_caixa(wf.FASE_LABORATORIO, ["concluido", "pendente"])
    assert ok is False
    assert "1" in motivo  # menciona quantos faltam


def test_gate_lab_libera_com_todos_terminais():
    ok, motivo = wf.pode_avancar_caixa(wf.FASE_LABORATORIO, ["concluido", "sem_conserto"])
    assert ok is True
    assert motivo is None


def test_gate_outras_fases_nao_checam_desfecho():
    # Recebido->Lab e Pos-Vendas->Financeiro nao olham desfecho
    assert wf.pode_avancar_caixa(4, ["pendente", "pendente"])[0] is True
    assert wf.pode_avancar_caixa(6, ["pendente"])[0] is True


def test_gate_fase_terminal_nao_avanca():
    ok, _ = wf.pode_avancar_caixa(wf.FASE_FINALIZADA, [])
    assert ok is False
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd backend && pytest tests/test_caixa_workflow.py -k gate -v`
Expected: FAIL (`AttributeError: module ... has no attribute 'pode_avancar_caixa'`).

- [ ] **Step 3: Implementar no `os_workflow.py`**

Adicionar ao fim de `backend/app/core/os_workflow.py`:

```python
DESFECHO_PENDENTE = "pendente"
DESFECHO_CONCLUIDO = "concluido"
DESFECHO_SEM_CONSERTO = "sem_conserto"
DESFECHOS_TERMINAIS = (DESFECHO_CONCLUIDO, DESFECHO_SEM_CONSERTO)


def desfechos_pendentes(desfechos: list[str]) -> int:
    """Quantos aparelhos ainda estao 'pendente' no laboratorio."""
    return sum(1 for d in desfechos if d not in DESFECHOS_TERMINAIS)


def pode_avancar_caixa(fase_atual: int, desfechos: list[str]) -> tuple[bool, str | None]:
    """Regras de avanco da CAIXA. So a saida do laboratorio checa desfecho por aparelho.

    Retorna (True, None) se pode avancar; (False, motivo) se travado.
    """
    if proxima_fase(fase_atual) is None:
        return False, "caixa em fase terminal"
    if fase_atual == FASE_LABORATORIO:
        faltam = desfechos_pendentes(desfechos)
        if faltam > 0:
            return False, f"faltam {faltam} aparelho(s) sem desfecho no laboratorio"
    return True, None
```

- [ ] **Step 4: Rodar e ver passar**

Run: `cd backend && pytest tests/test_caixa_workflow.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/os_workflow.py backend/tests/test_caixa_workflow.py
git commit -m "feat(caixa): gate puro pode_avancar_caixa no workflow"
```

---

## Task 4: Marcar desfecho do laboratório na OS (`sem_conserto` / `concluido`)

**Files:**
- Modify: `backend/app/api/ordens.py` (novo endpoint), `backend/app/schemas/` (schema do corpo)
- Test: `backend/tests/test_caixa_avancar.py`

**Interfaces:**
- Consumes: `Ordem`, `os_workflow` constantes, `registrar_log`, `exige_funcao_da_fase`.
- Produces: `POST /ordens/{ordem_id}/desfecho-lab` com corpo `{ "desfecho": "concluido"|"sem_conserto", "obs": str|None }`; devolve `OrdemOut`. Ao marcar `concluido`, exige certificado gerado (mesma regra que já existia no avançar Lab). Ao marcar `sem_conserto`, exige `obs` não-vazio.

- [ ] **Step 1: Escrever o teste do endpoint**

```python
# backend/tests/test_caixa_avancar.py  (usa o client autenticado do conftest)
def test_marcar_sem_conserto_exige_obs(client_lab, os_no_lab):
    r = client_lab.post(f"/ordens/{os_no_lab}/desfecho-lab",
                        json={"desfecho": "sem_conserto", "obs": ""})
    assert r.status_code == 400


def test_marcar_sem_conserto_ok(client_lab, os_no_lab):
    r = client_lab.post(f"/ordens/{os_no_lab}/desfecho-lab",
                        json={"desfecho": "sem_conserto", "obs": "carcaca trincada"})
    assert r.status_code == 200
    assert r.json()["desfecho_lab"] == "sem_conserto"


def test_marcar_concluido_sem_certificado_falha(client_lab, os_no_lab):
    r = client_lab.post(f"/ordens/{os_no_lab}/desfecho-lab",
                        json={"desfecho": "concluido", "obs": None})
    assert r.status_code == 409
```

> Fixtures `client_lab` (usuário função Laboratório), `os_no_lab` (OS em fase 5 numa caixa) devem ser adicionadas ao `conftest.py` — ver Task 4a abaixo se ainda não existirem. Reusar os helpers de auth já presentes no `conftest.py`.

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd backend && pytest tests/test_caixa_avancar.py -k desfecho -v`
Expected: FAIL (404 na rota inexistente).

- [ ] **Step 3: Adicionar o schema e o endpoint**

Schema em `backend/app/schemas/ordens.py` (ou onde ficam os schemas de OS — seguir o import de `AvancarIn`):

```python
class DesfechoLabIn(BaseModel):
    desfecho: Literal["concluido", "sem_conserto"]
    obs: str | None = None
```

Endpoint em `backend/app/api/ordens.py` (após `avancar`):

```python
@router.post("/{ordem_id}/desfecho-lab", response_model=OrdemOut)
def marcar_desfecho_lab(ordem_id: int, dados: DesfechoLabIn, db: Session = Depends(get_db),
                        usuario: Usuario = Depends(get_current_usuario)):
    ordem = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if ordem is None:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    if ordem.fase != wf.FASE_LABORATORIO:
        raise HTTPException(status_code=409, detail="desfecho só no laboratório")
    exige_funcao_da_fase(db, usuario, ordem.fase)
    if dados.desfecho == wf.DESFECHO_CONCLUIDO:
        tem_cert = db.query(OSCertificado).filter(OSCertificado.os == ordem.id).first() is not None
        if not tem_cert:
            raise HTTPException(status_code=409, detail="gere o certificado antes de concluir")
        espelhar_calibracao(db, ordem)
        ordem.desfecho_lab = wf.DESFECHO_CONCLUIDO
        ordem.desfecho_lab_obs = None
        texto = "Laboratório concluído (aparelho)"
    else:  # sem_conserto
        if not (dados.obs and dados.obs.strip()):
            raise HTTPException(status_code=400, detail="justificativa obrigatória para sem conserto")
        ordem.desfecho_lab = wf.DESFECHO_SEM_CONSERTO
        ordem.desfecho_lab_obs = dados.obs.strip()
        texto = f"Sem conserto: {ordem.desfecho_lab_obs}"
    registrar_log(db, ordem, usuario, texto)
    db.commit()
    db.refresh(ordem)
    return ordem
```

Garantir os imports no topo de `ordens.py`: `from app.core import os_workflow as wf` (já existe), `espelhar_calibracao` (já importado, linha 10), `OSCertificado` (já usado no avançar).

- [ ] **Step 4: Rodar e ver passar**

Run: `cd backend && pytest tests/test_caixa_avancar.py -k desfecho -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/ordens.py backend/app/schemas/ordens.py backend/tests/test_caixa_avancar.py backend/tests/conftest.py
git commit -m "feat(os): endpoint de marcar desfecho do laboratorio na os"
```

---

## Task 5: Invariante "uma caixa = um cliente"

**Files:**
- Modify: `backend/app/api/caixas.py:89-104` (`vincular_ordem`)
- Modify: `backend/app/api/ordens.py:151-153` (`abrir`, após achar a caixa)
- Test: `backend/tests/test_caixa_avancar.py`

**Interfaces:**
- Produces: `vincular_ordem` e `abrir` passam a rejeitar (409) OS cujo `cliente` difere do cliente já presente na caixa.

- [ ] **Step 1: Escrever o teste**

```python
# backend/tests/test_caixa_avancar.py
def test_vincular_ordem_de_outro_cliente_falha(client_exp, caixa_com_os_cliente_a, os_cliente_b):
    r = client_exp.post(f"/caixas/{caixa_com_os_cliente_a}/ordens",
                        json={"ordem_id": os_cliente_b})
    assert r.status_code == 409
    assert "cliente" in r.json()["detail"].lower()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd backend && pytest tests/test_caixa_avancar.py -k outro_cliente -v`
Expected: FAIL (hoje passa sem checar — vincula 200).

- [ ] **Step 3: Adicionar o helper e usá-lo nos dois pontos**

Em `backend/app/api/caixas.py`, adicionar helper e chamar em `vincular_ordem` (substitui a linha 100 `ordem.caixa = cx.id  # vincula/move (sem checar cliente)`):

```python
def _cliente_da_caixa(cx: Caixa) -> int | None:
    """O cliente das OS ativas da caixa (todas iguais por invariante), ou None se vazia."""
    for o in cx.ordens:
        return o.cliente
    return None


def _exige_mesmo_cliente(cx: Caixa, cliente_id: int) -> None:
    atual = _cliente_da_caixa(cx)
    if atual is not None and atual != cliente_id:
        raise HTTPException(status_code=409, detail="OS de cliente diferente do da caixa")
```

No `vincular_ordem`, antes de `ordem.caixa = cx.id`:

```python
    _exige_mesmo_cliente(cx, ordem.cliente)
    ordem.caixa = cx.id  # vincula/move (mesmo cliente garantido acima)
```

Em `backend/app/api/ordens.py`, no `abrir`, logo após a linha 153 (`raise HTTPException(... "caixa não encontrada")`):

```python
    outra = db.query(Ordem).filter(Ordem.caixa == cx.id).first()
    if outra is not None and outra.cliente != ec.cliente:
        raise HTTPException(status_code=409, detail="caixa é de outro cliente")
```

- [ ] **Step 4: Rodar e ver passar**

Run: `cd backend && pytest tests/test_caixa_avancar.py -k cliente -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/caixas.py backend/app/api/ordens.py backend/tests/test_caixa_avancar.py
git commit -m "feat(caixa): invariante um cliente por caixa em vincular e abrir"
```

---

## Task 6: Endpoint `POST /caixas/{id}/avancar` — o coração da mudança

**Files:**
- Create: `backend/app/schemas/caixa_acoes.py`
- Modify: `backend/app/api/caixas.py`
- Test: `backend/tests/test_caixa_avancar.py`

**Interfaces:**
- Consumes: `os_workflow` (`proxima_fase`, `pode_avancar_caixa`, `FASE_LABORATORIO`, `DESFECHO_*`), `espelhar_calibracao`, `registrar_log`, `exige_funcao_da_fase`, `agora`.
- Produces: `POST /caixas/{id}/avancar` corpo `CaixaAvancarIn { obs: str|None, cod_retorno: str|None }`; devolve `CaixaDetalhe`. Avança a caixa e **todas as OS ativas** juntas. Aplica o efeito por fase da tabela de decisões. Sincroniza `caixa.fase` e `ordem.fase`. Dispara **1** espelhamento de caixa (Task 11) e, saindo do laboratório, **1** card GrowthHS de caixa.

- [ ] **Step 1: Escrever os testes do avançar da caixa**

```python
# backend/tests/test_caixa_avancar.py
def test_avancar_caixa_recebido_para_lab(client_exp, caixa_recebido):
    r = client_exp.post(f"/caixas/{caixa_recebido}/avancar", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["fase"] == 5
    assert all(o["fase"] == 5 for o in body["ordens"])  # fan-out


def test_avancar_caixa_lab_travado_com_pendente(client_lab, caixa_lab_um_pendente):
    r = client_lab.post(f"/caixas/{caixa_lab_um_pendente}/avancar", json={})
    assert r.status_code == 409
    assert "faltam" in r.json()["detail"].lower()


def test_avancar_caixa_lab_libera_com_todos_terminais(client_lab, caixa_lab_todos_terminais):
    r = client_lab.post(f"/caixas/{caixa_lab_todos_terminais}/avancar", json={})
    assert r.status_code == 200
    assert r.json()["fase"] == 6


def test_avancar_caixa_finalizar_exige_cod_retorno(client_exp, caixa_preparando):
    r = client_exp.post(f"/caixas/{caixa_preparando}/avancar", json={})
    assert r.status_code == 422
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd backend && pytest tests/test_caixa_avancar.py -k avancar_caixa -v`
Expected: FAIL (404 rota inexistente).

- [ ] **Step 3: Criar o schema de ações**

```python
# backend/app/schemas/caixa_acoes.py
from pydantic import BaseModel


class CaixaAvancarIn(BaseModel):
    obs: str | None = None
    cod_retorno: str | None = None   # obrigatório só em Preparando(7)->Finalizada(8)


class CaixaCancelarIn(BaseModel):
    motivo: str
```

- [ ] **Step 4: Implementar o endpoint em `caixas.py`**

Imports no topo de `caixas.py`:

```python
from app.api.ordens_acoes import registrar_log, exige_funcao_da_fase, agora, espelhar_calibracao
from app.schemas.caixa_acoes import CaixaAvancarIn, CaixaCancelarIn
from app.api.espelhamento import agendar_espelhamento_caixa
from app.api.growthhs_cards import agendar_card_caixa
from app.core import taskhs
from fastapi import BackgroundTasks
```

Endpoint (a lógica por fase espelha o `avancar` de OS, mas fan-out para todas as OS ativas):

```python
def _ordens_ativas(cx: Caixa) -> list[Ordem]:
    return [o for o in cx.ordens if wf.eh_ativa(o.fase)]


@router.post("/{caixa_id}/avancar", response_model=CaixaDetalhe)
def avancar_caixa(caixa_id: int, dados: CaixaAvancarIn, background_tasks: BackgroundTasks,
                  db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_usuario)):
    cx = _get_caixa(db, caixa_id)
    if cx.fase is None:
        raise HTTPException(status_code=409, detail="caixa sem fase ativa")
    exige_funcao_da_fase(db, usuario, cx.fase)
    origem = cx.fase
    destino = wf.proxima_fase(origem)
    ativas = _ordens_ativas(cx)

    ok, motivo = wf.pode_avancar_caixa(origem, [o.desfecho_lab for o in ativas])
    if not ok:
        raise HTTPException(status_code=409, detail=motivo)

    # efeito por fase, fan-out para cada OS ativa
    if origem == 7:  # Preparando -> Finalizada
        if not (dados.cod_retorno and dados.cod_retorno.strip()):
            raise HTTPException(status_code=422, detail="cod_retorno é obrigatório para finalizar")
    for o in ativas:
        if origem == wf.FASE_LABORATORIO:
            if o.desfecho_lab == wf.DESFECHO_CONCLUIDO:
                espelhar_calibracao(db, o)
        elif origem == 6:      # Pós-Vendas -> Financeiro
            o.aceite = True
            o.data_aceite = agora()
        elif origem == 10:     # Financeiro -> Preparando
            if not o.nota_fiscal:
                raise HTTPException(status_code=409, detail="anexe a nota fiscal da caixa antes de confirmar o pagamento")
            o.pago = True
            o.data_pagamento = agora()
        elif origem == 7:      # Preparando -> Finalizada
            o.cod_retorno = dados.cod_retorno.strip()
            o.data_retorno = agora()
            o.situacao = "F"
        o.fase = destino
        registrar_log(db, o, usuario, f"Caixa #{cx.id}: {origem} -> {destino}")
    cx.fase = destino
    db.commit()
    db.refresh(cx)
    agendar_espelhamento_caixa(db, background_tasks, cx)
    if origem == wf.FASE_LABORATORIO:
        agendar_card_caixa(db, background_tasks, cx)
    return cx
```

> `agendar_espelhamento_caixa` e `agendar_card_caixa` são definidos nas Tasks 11 — se estiver executando em ordem, crie stubs no-op temporários e implemente na Task 11. (Subagent-driven: a Task 11 vem antes na dependência; reordene se preferir integrações antes do endpoint.)

- [ ] **Step 5: Rodar e ver passar**

Run: `cd backend && pytest tests/test_caixa_avancar.py -k avancar_caixa -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/caixa_acoes.py backend/app/api/caixas.py backend/tests/test_caixa_avancar.py
git commit -m "feat(caixa): endpoint avancar caixa com gate e fan-out por fase"
```

---

## Task 7: Endpoint `POST /caixas/{id}/cancelar`

**Files:**
- Modify: `backend/app/api/caixas.py`
- Test: `backend/tests/test_caixa_avancar.py`

**Interfaces:**
- Produces: `POST /caixas/{id}/cancelar` corpo `CaixaCancelarIn { motivo: str }`; cancela **todas as OS ativas** da caixa (`fase=FASE_CANCELADA`, `situacao="C"`), zera `caixa.fase`, dispara 1 espelhamento arquivando o card.

- [ ] **Step 1: Escrever o teste**

```python
def test_cancelar_caixa_cancela_todas(client_exp, caixa_recebido):
    r = client_exp.post(f"/caixas/{caixa_recebido}/cancelar", json={"motivo": "cliente desistiu"})
    assert r.status_code == 200
    assert all(o["fase"] == 9 for o in r.json()["ordens"])
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd backend && pytest tests/test_caixa_avancar.py -k cancelar_caixa -v`
Expected: FAIL (404).

- [ ] **Step 3: Implementar**

```python
@router.post("/{caixa_id}/cancelar", response_model=CaixaDetalhe)
def cancelar_caixa(caixa_id: int, dados: CaixaCancelarIn, background_tasks: BackgroundTasks,
                   db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_usuario)):
    cx = _get_caixa(db, caixa_id)
    if cx.fase is None:
        raise HTTPException(status_code=409, detail="caixa sem fase ativa")
    exige_funcao_da_fase(db, usuario, cx.fase)
    origem = cx.fase
    for o in _ordens_ativas(cx):
        o.fase = wf.FASE_CANCELADA
        o.situacao = "C"
        registrar_log(db, o, usuario, f"Caixa #{cx.id} cancelada: {dados.motivo}")
    cx.fase = None
    db.commit()
    db.refresh(cx)
    agendar_espelhamento_caixa(db, background_tasks, cx, origem=origem, arquivado=True)
    return cx
```

- [ ] **Step 4: Rodar e ver passar**

Run: `cd backend && pytest tests/test_caixa_avancar.py -k cancelar_caixa -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/caixas.py backend/tests/test_caixa_avancar.py
git commit -m "feat(caixa): endpoint cancelar caixa cancela todas as os"
```

---

## Task 8: Nota fiscal no nível da caixa (fan-out)

**Files:**
- Modify: `backend/app/api/notas_fiscais.py` (novo endpoint de caixa) — seguir o endpoint de OS existente
- Test: `backend/tests/test_caixa_avancar.py`

**Interfaces:**
- Produces: `POST /caixas/{id}/nota-fiscal` (multipart: arquivo + `numero`) — grava a NF uma vez e replica `nota_fiscal`/`nota_fiscal_numero` em todas as OS ativas da caixa. Mesmo storage do endpoint de OS.

- [ ] **Step 1: Ler o endpoint de NF por OS para copiar o padrão de upload**

Run: `cd backend && grep -n "nota" app/api/notas_fiscais.py`
Depois abrir o arquivo e replicar o fluxo de storage (`app/core/storage.py`) num endpoint de caixa que itera `_ordens_ativas(cx)` e faz `setattr(o, "nota_fiscal", basename)` / `o.nota_fiscal_numero = numero` para cada uma.

- [ ] **Step 2: Escrever o teste**

```python
def test_nf_caixa_replica_em_todas(client_fin, caixa_financeiro):
    arquivo = ("nf.pdf", b"%PDF-1.4 fake", "application/pdf")
    r = client_fin.post(f"/caixas/{caixa_financeiro}/nota-fiscal",
                        data={"numero": "12345"}, files={"arquivo": arquivo})
    assert r.status_code == 200
    for o in r.json()["ordens"]:
        det = client_fin.get(f"/ordens/{o['id']}").json()
        assert det["nota_fiscal_numero"] == "12345"
```

- [ ] **Step 3: Implementar o endpoint** (copiar o handler de OS, trocando o alvo por `_ordens_ativas(cx)` e devolvendo `CaixaDetalhe`). Registrar em `main.py` se necessário (o router de notas já está incluído).

- [ ] **Step 4: Rodar e ver passar**

Run: `cd backend && pytest tests/test_caixa_avancar.py -k nf_caixa -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/notas_fiscais.py backend/tests/test_caixa_avancar.py
git commit -m "feat(caixa): nota fiscal no nivel da caixa replicada nas os"
```

---

## Task 9: `taskhs.py` — agregar N ordens no card da caixa

**Files:**
- Modify: `backend/app/core/taskhs.py`
- Test: `backend/tests/test_taskhs_caixa.py`

**Interfaces:**
- Consumes: `os_workflow.posicao`.
- Produces:
  - `montar_titulo_caixa(caixa, ordens) -> str` — `CX <id> · <cliente> · N aparelho(s)`.
  - `montar_obs_caixa(caixa, ordens, *, certificados_por_os: dict[int, list[dict]], nota_fiscal_url: str|None) -> dict` — obs1..obs6, com obs1 listando os aparelhos e obs2 listando o resultado/desfecho por aparelho.
  - `montar_payload_caixa(caixa, ordens, *, list_id, arquivado, obs) -> dict` — `external_id=str(caixa.id)`.

- [ ] **Step 1: Escrever os testes de agregação**

```python
# backend/tests/test_taskhs_caixa.py
from types import SimpleNamespace
from app.core import taskhs


def _os(**kw):
    base = dict(id=1, cliente_nome="ACME", equipamento_descricao="Bafômetro",
                equipamento_serie="S1", desfecho_lab="concluido", fase=6,
                calib_situacao="Aprovado", calib_cert="C-1", prox_calibragem=None,
                equipamento_rel=SimpleNamespace(patrimonio=None))
    base.update(kw)
    return SimpleNamespace(**base)


def test_titulo_caixa_conta_aparelhos():
    cx = SimpleNamespace(id=7)
    t = taskhs.montar_titulo_caixa(cx, [_os(id=1), _os(id=2)])
    assert "CX 7" in t and "ACME" in t and "2 aparelho" in t


def test_obs2_lista_por_aparelho_com_sem_conserto():
    cx = SimpleNamespace(id=7)
    ordens = [_os(id=1, equipamento_serie="S1"),
              _os(id=2, equipamento_serie="S2", desfecho_lab="sem_conserto",
                  desfecho_lab_obs="carcaça trincada")]
    obs = taskhs.montar_obs_caixa(cx, ordens, certificados_por_os={1: [{"tipo": "C", "url": "http://x"}]},
                                  nota_fiscal_url=None)
    assert "S1" in obs["obs2"] and "S2" in obs["obs2"]
    assert "sem conserto" in obs["obs2"].lower()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd backend && pytest tests/test_taskhs_caixa.py -v`
Expected: FAIL (`AttributeError: ... 'montar_titulo_caixa'`).

- [ ] **Step 3: Implementar as funções de caixa em `taskhs.py`**

Adicionar (reutilizando os helpers `_juntar`, `_bloco`, `_fmt`, `_cabecalho`, `TIPO_SERVICO_LABEL` já no módulo):

```python
def montar_titulo_caixa(caixa, ordens) -> str:
    cliente = next((o.cliente_nome for o in ordens if o.cliente_nome), None)
    n = len(ordens)
    partes = [f"CX {caixa.id}"]
    if cliente:
        partes.append(cliente)
    partes.append(f"{n} aparelho" + ("s" if n != 1 else ""))
    return " · ".join(partes)


def _linha_aparelho_lab(ordem, certificados: list[dict]) -> str:
    ident = ordem.equipamento_serie or ordem.equipamento_descricao or f"OS #{ordem.id}"
    if ordem.desfecho_lab == "sem_conserto":
        motivo = getattr(ordem, "desfecho_lab_obs", None) or "sem detalhe"
        return f"{ident}: sem conserto — {motivo}"
    partes = [ident + ":", ordem.calib_situacao or "calibrado"]
    if ordem.calib_cert:
        partes.append(f"cert {ordem.calib_cert}")
    for c in certificados:
        if c.get("url"):
            partes.append(c["url"])
    return " ".join(partes)


def montar_obs_caixa(caixa, ordens, *, certificados_por_os: dict, nota_fiscal_url=None) -> dict:
    cliente_os = next((o for o in ordens if o.cliente_nome), ordens[0] if ordens else None)
    cabecalho = "\n".join(_cabecalho(cliente_os)) if cliente_os else None
    aparelhos = _bloco([
        _juntar([o.equipamento_descricao, o.equipamento_serie], sep=" / ") or f"OS #{o.id}"
        for o in ordens
    ])
    obs1 = "\n".join([x for x in (cabecalho, aparelhos) if x]) or None
    obs2 = _bloco([_linha_aparelho_lab(o, certificados_por_os.get(o.id, [])) for o in ordens]) or None
    # obs3..obs6 (nível lote) reusam a lógica de uma OS representativa
    rep = ordens[0] if ordens else None
    from app.core.taskhs import _sec_posvendas, _sec_financeiro, _sec_preparando, _sec_finalizada
    return {
        "obs1": obs1,
        "obs2": obs2,
        "obs3": _sec_posvendas(rep) if rep else None,
        "obs4": _sec_financeiro(rep, nota_fiscal_url) if rep else None,
        "obs5": _sec_preparando(rep) if rep else None,
        "obs6": _sec_finalizada(rep) if rep else None,
    }


def montar_payload_caixa(caixa, ordens, *, list_id: int, arquivado: bool, obs: dict) -> dict:
    prox = next((o.prox_calibragem for o in ordens if o.prox_calibragem), None)
    return {
        "source": SOURCE,
        "external_id": str(caixa.id),
        "list_id": list_id,
        "title": montar_titulo_caixa(caixa, ordens),
        **{f"obs{i}": obs.get(f"obs{i}") for i in range(1, 7)},
        "due_date": prox.date().isoformat() if prox else None,
        "priority": "medium",
        "archived": arquivado,
    }
```

- [ ] **Step 4: Rodar e ver passar**

Run: `cd backend && pytest tests/test_taskhs_caixa.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/taskhs.py backend/tests/test_taskhs_caixa.py
git commit -m "feat(integr): payload do taskhs agregando aparelhos da caixa"
```

---

## Task 10: `growthhs_os.py` — `devices[]` com N aparelhos da caixa

**Files:**
- Modify: `backend/app/core/growthhs_os.py`
- Test: `backend/tests/test_growthhs_caixa.py`

**Interfaces:**
- Consumes: `growthhs_payload.montar_cliente`, `montar_contato`.
- Produces: `montar_card_caixa(caixa, cliente, devices: list[dict], board_id: int, hoje) -> dict` — `external_id=str(caixa.id)`, `devices` com todos os aparelhos, 1 `client`/`contact`.

- [ ] **Step 1: Escrever o teste**

```python
# backend/tests/test_growthhs_caixa.py
from datetime import date
from types import SimpleNamespace
from app.core import growthhs_os


def test_card_caixa_lista_todos_devices():
    cx = SimpleNamespace(id=7)
    cli = SimpleNamespace(id=1, nome="ACME", cgc="00", cpf=None, email=None, celular=None,
                          whatsapp=None, telefones=None, endereco=None, numero=None,
                          bairro=None, municipio=None, estado=None, contato=None)
    devices = [{"serial_number": "S1", "model": "Baf", "alcohol_module": None, "next_recalibration_date": None},
               {"serial_number": "S2", "model": "Baf", "alcohol_module": None, "next_recalibration_date": None}]
    card = growthhs_os.montar_card_caixa(cx, cli, devices, 3, date(2026, 7, 22))
    assert card["external_id"] == "7"
    assert len(card["devices"]) == 2
    assert card["client"]["name"] == "ACME"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd backend && pytest tests/test_growthhs_caixa.py -v`
Expected: FAIL (`AttributeError: ... 'montar_card_caixa'`).

- [ ] **Step 3: Implementar** em `growthhs_os.py`:

```python
def montar_card_caixa(caixa, cliente, devices: list[dict], board_id: int, hoje: date) -> dict:
    n = len(devices)
    titulo = " · ".join([f"CX {caixa.id}", _texto(getattr(cliente, "nome", None)) or "",
                         f"{n} aparelho" + ("s" if n != 1 else "")]).strip(" ·")
    return {
        "source": SOURCE_OS,
        "external_id": str(caixa.id),
        "board_id": board_id,
        "title": titulo[:LIMITE_TITLE],
        "description": f"{n} aparelho(s) liberado(s) do laboratório",
        "due_date": f"{(hoje + timedelta(days=DIAS_PRAZO)).isoformat()}T00:00:00",
        "client": montar_cliente(cliente),
        "contact": montar_contato(cliente),
        "devices": devices,
        "business_info": {"origem": "caixa liberada do laboratorio", "caixa_id": caixa.id},
    }
```

- [ ] **Step 4: Rodar e ver passar**

Run: `cd backend && pytest tests/test_growthhs_caixa.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/growthhs_os.py backend/tests/test_growthhs_caixa.py
git commit -m "feat(integr): card do growthhs por caixa com todos os devices"
```

---

## Task 11: Disparo do espelhamento a partir da caixa

**Files:**
- Modify: `backend/app/api/espelhamento.py`, `backend/app/api/growthhs_cards.py`
- Test: coberto indiretamente pelos testes do endpoint (Task 6/7) — os agendamentos são best-effort no-op sem integração ativa.

**Interfaces:**
- Consumes: `taskhs.montar_obs_caixa`/`montar_payload_caixa`/`list_id_da_fase`; `growthhs_os.montar_card_caixa`; `montar_device`/`buscar_elo` (loop por OS).
- Produces:
  - `espelhamento.agendar_espelhamento_caixa(db, background_tasks, caixa, *, origem=None, arquivado=False)`.
  - `growthhs_cards.agendar_card_caixa(db, background_tasks, caixa)`.

- [ ] **Step 1: Implementar `agendar_espelhamento_caixa`** em `espelhamento.py`:

```python
from app.core import taskhs

def _montar_payload_caixa(db, caixa, *, list_id, arquivado):
    from app.models import Ordem, OSCertificado
    ordens = [o for o in caixa.ordens if o.fase not in (9,)] or list(caixa.ordens)
    certificados_por_os = {}
    for o in ordens:
        certs = db.query(OSCertificado).filter(OSCertificado.os == o.id).all()
        certificados_por_os[o.id] = [
            {"tipo": c.tipo, "url": certificado_link.link_certificado(o.id, c.tipo)} for c in certs
        ]
    nf_url = None
    rep_nf = next((o for o in ordens if o.nota_fiscal), None)
    if rep_nf is not None:
        nf_url = nota_fiscal_link.link_nota_fiscal(rep_nf.id)
    obs = taskhs.montar_obs_caixa(caixa, ordens, certificados_por_os=certificados_por_os, nota_fiscal_url=nf_url)
    return taskhs.montar_payload_caixa(caixa, ordens, list_id=list_id, arquivado=arquivado, obs=obs)


def agendar_espelhamento_caixa(db, background_tasks, caixa, *, origem=None, arquivado=False):
    fase = origem if origem is not None else caixa.fase
    list_id = taskhs.list_id_da_fase(fase) if fase is not None else None
    if list_id is None or not taskhs_client.integracao_ativa():
        return
    payload = _montar_payload_caixa(db, caixa, list_id=list_id, arquivado=arquivado)
    background_tasks.add_task(taskhs_client.enviar_card, payload)
```

- [ ] **Step 2: Implementar `agendar_card_caixa`** em `growthhs_cards.py` (reusa `buscar_elo`/`montar_device` num loop):

```python
from app.core.growthhs_os import montar_card_caixa

def agendar_card_caixa(db, background_tasks, caixa) -> None:
    if not hsgrowth_client.integracao_ativa():
        return
    ordens = [o for o in caixa.ordens if o.equipamento_rel is not None]
    if not ordens:
        return
    try:
        devices = []
        for o in ordens:
            ec = o.equipamento_rel
            elo = buscar_elo(db, ec)
            devices.append(montar_device(ec, o.equipamento_descricao, elo=elo))
        cliente = ordens[0].cliente_rel
        card = montar_card_caixa(caixa, cliente, devices, settings.HSGROWTH_BOARD_SERVICOS, date.today())
    except Exception:
        db.rollback()
        logger.exception("falha ao montar card de caixa para o GrowthHS (caixa=%s)", caixa.id)
        return
    background_tasks.add_task(hsgrowth_client.enviar_card, card)
```

- [ ] **Step 3: Rodar a suíte inteira do backend**

Run: `cd backend && pytest -q`
Expected: PASS (todos, incl. os endpoints da Task 6/7 que agora encontram as funções reais).

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/espelhamento.py backend/app/api/growthhs_cards.py
git commit -m "feat(integr): disparo de espelhamento e card a partir da caixa"
```

---

## Task 12: Aposentar o avançar/cancelar por-OS (backend + expor fase/desfecho nos schemas)

**Files:**
- Modify: `backend/app/schemas/caixas.py` (expor `fase`, `desfecho_lab`), `backend/app/api/ordens.py` (deprecar `avancar`/`cancelar` por-OS)
- Test: `backend/tests/test_caixa_avancar.py`

**Interfaces:**
- Produces: `CaixaOut.fase`, `CaixaOut.fase_descricao`, `CaixaOut.fase_cor`; `OrdemResumoCaixa.desfecho_lab`, `desfecho_lab_obs`. Os endpoints `POST /ordens/{id}/avancar` e `/cancelar` passam a responder 409 orientando a usar a caixa (a OS não anda sozinha).

- [ ] **Step 1: Teste — schema da caixa expõe fase e desfecho**

```python
def test_caixa_detalhe_expoe_fase_e_desfecho(client_lab, caixa_lab_um_pendente):
    r = client_lab.get(f"/caixas/{caixa_lab_um_pendente}")
    body = r.json()
    assert "fase" in body
    assert "desfecho_lab" in body["ordens"][0]
```

- [ ] **Step 2: Rodar e ver falhar** → Run: `cd backend && pytest tests/test_caixa_avancar.py -k expoe -v` → FAIL.

- [ ] **Step 3: Atualizar `schemas/caixas.py`**

```python
class OrdemResumoCaixa(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cliente: int
    cliente_nome: str | None = None
    equipamento_descricao: str | None = None
    equipamento_serie: str | None = None
    fase: int | None = None
    fase_descricao: str | None = None
    fase_cor: str | None = None
    desfecho_lab: str = "pendente"
    desfecho_lab_obs: str | None = None


class CaixaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    data: date | None = None
    obs: str | None = None
    fase: int | None = None
    fase_descricao: str | None = None
    fase_cor: str | None = None
    total_os: int = 0
    clientes: list[str] = []
```

- [ ] **Step 4: Deprecar avançar/cancelar por-OS** — no início de `avancar` e `cancelar` em `ordens.py`, após achar a `ordem`:

```python
    raise HTTPException(status_code=409, detail="a OS anda pela caixa; use /caixas/{id}/avancar")
```

(Manter o resto morto ou removê-lo; ajustar/remover os testes por-OS de avanço que existirem em `tests/`.)

- [ ] **Step 5: Rodar a suíte** → Run: `cd backend && pytest -q` → PASS (corrigir testes antigos de avanço por-OS que agora esperam 409).

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/caixas.py backend/app/api/ordens.py backend/tests/
git commit -m "feat(caixa): caixa e a unidade de avanco; os nao anda sozinha"
```

---

## Task 13: Endpoint `GET /caixas/quadro` (colunas por fase, cards = caixa)

**Files:**
- Modify: `backend/app/api/caixas.py`; `backend/app/schemas/caixas.py` (schema do quadro)
- Test: `backend/tests/test_caixa_avancar.py`

**Interfaces:**
- Produces: `GET /caixas/quadro?cliente=` → `list[QuadroCaixaColuna]`, cada coluna `{ fase, descricao, cor, total, caixas: [{ id, cliente_nome, total_os, prontos, pendentes }] }`. `prontos`/`pendentes` contam desfecho_lab para o badge "3/5" na coluna Laboratório.

- [ ] **Step 1: Teste do quadro**

```python
def test_quadro_caixas_agrupa_por_fase(client_lab, caixa_lab_um_pendente):
    r = client_lab.get("/caixas/quadro")
    cols = {c["fase"]: c for c in r.json()}
    assert 5 in cols
    cx = cols[5]["caixas"][0]
    assert cx["total_os"] >= 1 and cx["pendentes"] >= 1
```

- [ ] **Step 2: Rodar e ver falhar** → `pytest tests/test_caixa_avancar.py -k quadro_caixas` → FAIL.

- [ ] **Step 3: Implementar** (espelha `ordens.quadro`, mas agrupando por `Caixa.fase`):

```python
# schemas/caixas.py
class CaixaQuadroItem(BaseModel):
    id: int
    cliente_nome: str | None = None
    total_os: int
    prontos: int
    pendentes: int

class QuadroCaixaColuna(BaseModel):
    fase: int
    descricao: str
    cor: str
    total: int
    caixas: list[CaixaQuadroItem]
```

```python
# api/caixas.py
from app.core import os_workflow as wf

@router.get("/quadro", response_model=list[QuadroCaixaColuna])
def quadro_caixas(cliente: int | None = None, db: Session = Depends(get_db),
                  _: Usuario = Depends(get_current_usuario)):
    fases_ids = list(wf.ATIVAS)
    fases = {f.id: f for f in db.query(Fase).filter(Fase.id.in_(fases_ids)).all()}
    colunas = []
    for fid in fases_ids:
        q = db.query(Caixa).filter(Caixa.fase == fid)
        caixas = q.order_by(Caixa.id.desc()).all()
        itens = []
        for cx in caixas:
            ativas = [o for o in cx.ordens if wf.eh_ativa(o.fase)]
            if cliente is not None and not any(o.cliente == cliente for o in ativas):
                continue
            prontos = sum(1 for o in ativas if o.desfecho_lab in wf.DESFECHOS_TERMINAIS)
            itens.append(CaixaQuadroItem(
                id=cx.id, cliente_nome=next((o.cliente_nome for o in ativas), None),
                total_os=len(ativas), prontos=prontos, pendentes=len(ativas) - prontos))
        f = fases.get(fid)
        colunas.append(QuadroCaixaColuna(
            fase=fid, descricao=f.descricao if f else str(fid),
            cor=f.cor if f else "888", total=len(itens), caixas=itens))
    return colunas
```

Import de `Fase` no topo do `caixas.py`: `from app.models import Usuario, Caixa, Ordem, Fase`.

- [ ] **Step 4: Rodar e ver passar** → `pytest tests/test_caixa_avancar.py -k quadro_caixas` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/caixas.py backend/app/schemas/caixas.py backend/tests/test_caixa_avancar.py
git commit -m "feat(caixa): endpoint de quadro por caixa com progresso do lab"
```

---

## Task 14: Frontend — `caixas/api.ts` (tipos + ações da caixa + quadro)

**Files:**
- Modify: `frontend/src/app/caixas/api.ts`
- Test: `frontend/src/app/caixas/api.test.ts`

**Interfaces:**
- Produces: em `caixasApi` — `avancar(id, payload)`, `cancelar(id, {motivo})`, `quadro({cliente?})`, e em `ordensApi`(caixas usa) `desfechoLab`. Tipos `CaixaDetalhe.fase`, `OrdemResumoCaixa.desfecho_lab`, `QuadroCaixaColuna`, `CaixaQuadroItem`.

- [ ] **Step 1: Teste (Vitest) do novo método** (espelhar `api.test.ts` existente, que mocka `apiJson`):

```ts
// adicionar em src/app/caixas/api.test.ts
it('avancar posta em /caixas/:id/avancar', async () => {
  const spy = vi.spyOn(api, 'apiJson').mockResolvedValue({ id: 7, ordens: [] } as any)
  await caixasApi.avancar(7, { cod_retorno: null, obs: null })
  expect(spy).toHaveBeenCalledWith('/caixas/7/avancar', expect.objectContaining({ method: 'POST' }))
})
```

- [ ] **Step 2: Rodar e ver falhar** → `cd frontend && npx vitest run src/app/caixas/api.test.ts` → FAIL.

- [ ] **Step 3: Adicionar tipos e métodos** em `caixas/api.ts`:

```ts
export interface OrdemResumoCaixa {
  id: number
  cliente: number
  cliente_nome: string | null
  equipamento_descricao: string | null
  equipamento_serie: string | null
  fase: number | null
  fase_descricao: string | null
  fase_cor: string | null
  desfecho_lab: string
  desfecho_lab_obs: string | null
}

export interface CaixaQuadroItem {
  id: number; cliente_nome: string | null
  total_os: number; prontos: number; pendentes: number
}
export interface QuadroCaixaColuna {
  fase: number; descricao: string; cor: string; total: number; caixas: CaixaQuadroItem[]
}
export interface CaixaAvancarPayload { obs?: string | null; cod_retorno?: string | null }
```

Em `CaixaListItem`/`CaixaDetalhe` adicionar `fase: number | null`, `fase_descricao: string | null`, `fase_cor: string | null`.

No objeto `caixasApi`:

```ts
  quadro: (params: { cliente?: number } = {}): Promise<QuadroCaixaColuna[]> => {
    const sp = new URLSearchParams()
    if (params.cliente != null) sp.set('cliente', String(params.cliente))
    const qs = sp.toString()
    return apiJson<QuadroCaixaColuna[]>(`/caixas/quadro${qs ? `?${qs}` : ''}`)
  },
  avancar: (id: number, payload: CaixaAvancarPayload): Promise<CaixaDetalhe> =>
    apiJson<CaixaDetalhe>(`/caixas/${id}/avancar`, { method: 'POST', body: JSON.stringify(payload) }),
  cancelar: (id: number, payload: { motivo: string }): Promise<CaixaDetalhe> =>
    apiJson<CaixaDetalhe>(`/caixas/${id}/cancelar`, { method: 'POST', body: JSON.stringify(payload) }),
  desfechoLab: (osId: number, payload: { desfecho: 'concluido' | 'sem_conserto'; obs: string | null }): Promise<unknown> =>
    apiJson(`/ordens/${osId}/desfecho-lab`, { method: 'POST', body: JSON.stringify(payload) }),
```

- [ ] **Step 4: Rodar e ver passar** → `npx vitest run src/app/caixas/api.test.ts` → PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/caixas/api.ts frontend/src/app/caixas/api.test.ts
git commit -m "feat(ui): api de acoes e quadro da caixa no frontend"
```

---

## Task 15: Frontend — Quadro de Ordens renderiza **caixas**

**Files:**
- Modify: `frontend/src/app/ordens/OrdensPage.tsx:71-150` (componente `Quadro`)
- Test: `frontend/src/app/ordens/OrdensPage.caixa.test.tsx`

**Interfaces:**
- Consumes: `caixasApi.quadro`, `QuadroCaixaColuna`.
- Produces: `Quadro` chama `caixasApi.quadro({cliente})`, renderiza um card por caixa com `CX <id>`, cliente, `N aparelhos` e, na coluna Laboratório (fase 5), badge `prontos/total_os`. Clique → `navigate('/app/caixas/<id>')`.

- [ ] **Step 1: Teste** — o quadro mostra "3/5" na coluna de laboratório:

```tsx
// OrdensPage.caixa.test.tsx
it('mostra progresso do lab no card da caixa', async () => {
  vi.spyOn(caixasApi, 'quadro').mockResolvedValue([
    { fase: 5, descricao: 'Laboratório', cor: 'abc', total: 1,
      caixas: [{ id: 7, cliente_nome: 'ACME', total_os: 5, prontos: 3, pendentes: 2 }] },
  ] as any)
  render(<MemoryRouter><OrdensPage /></MemoryRouter>)
  expect(await screen.findByText(/3\/5/)).toBeInTheDocument()
})
```

- [ ] **Step 2: Rodar e ver falhar** → `cd frontend && npx vitest run src/app/ordens/OrdensPage.caixa.test.tsx` → FAIL.

- [ ] **Step 3: Reescrever o componente `Quadro`** para consumir `caixasApi.quadro` e renderizar caixas. Substituir o corpo de `Quadro` (linhas 71-150) por uma versão que mapeia `QuadroCaixaColuna[]`; o card:

```tsx
<button onClick={() => onAbrir(cx.id)} className="w-full text-left rounded-xl bg-background-elevated border border-border p-3 hover:border-primary/40 transition-colors">
  <div className="flex items-center justify-between gap-2">
    <span className="text-sm font-semibold text-slate-100">CX {cx.id}</span>
    {col.fase === 5 && (
      <span className={cn('text-xs px-2 py-0.5 rounded-full',
        cx.pendentes === 0 ? 'bg-emerald-500/15 text-emerald-400' : 'bg-amber-500/15 text-amber-400')}>
        {cx.prontos}/{cx.total_os} prontos
      </span>
    )}
  </div>
  <p className="text-xs text-slate-300 mt-1 truncate">{cx.cliente_nome ?? '—'}</p>
  <p className="text-xs text-slate-500">{cx.total_os} aparelho{cx.total_os !== 1 ? 's' : ''}</p>
</button>
```

E `onAbrir` no `OrdensPage` passa a navegar para caixa: `onAbrir={(id) => navigate('/app/caixas/' + id)}`. (A "Lista" por-OS pode permanecer para consulta.)

- [ ] **Step 4: Rodar e ver passar** → `npx vitest run src/app/ordens/OrdensPage.caixa.test.tsx` → PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/ordens/OrdensPage.tsx frontend/src/app/ordens/OrdensPage.caixa.test.tsx
git commit -m "feat(ux): quadro de ordens mostra caixas com progresso do lab"
```

---

## Task 16: Frontend — `CaixaDetailPage` vira o posto de trabalho (avançar/cancelar/sem-conserto)

**Files:**
- Modify: `frontend/src/app/caixas/CaixaDetailPage.tsx`
- Create: `frontend/src/app/caixas/AvancarCaixaModal.tsx`, `frontend/src/app/caixas/SemConsertoModal.tsx`
- Test: `frontend/src/app/caixas/CaixaDetailPage.test.tsx`

**Interfaces:**
- Consumes: `caixasApi.avancar/cancelar/desfechoLab`, `TRANSICOES` (de `ordens/api.ts`, para o rótulo/`pedeCodRetorno`).
- Produces: no detalhe da caixa — botão **Avançar caixa** (usa `caixa.fase`→`TRANSICOES[fase]`; se `pedeCodRetorno`, abre `AvancarCaixaModal` pedindo o rastreio; senão avança direto), botão **Cancelar caixa**, e por linha de OS pendente em fase 5 um botão **Sem conserto** (abre `SemConsertoModal` → `desfechoLab`). Badge de progresso "N/M prontos" no cabeçalho quando `fase===5`.

- [ ] **Step 1: Teste** — botão "Avançar caixa" bloqueado quando há pendente no lab:

```tsx
it('bloqueia avancar caixa com aparelho pendente no lab', async () => {
  vi.spyOn(caixasApi, 'obter').mockResolvedValue({
    id: 7, fase: 5, ordens: [
      { id: 1, desfecho_lab: 'concluido', fase: 5 },
      { id: 2, desfecho_lab: 'pendente', fase: 5 }],
  } as any)
  render(<MemoryRouter initialEntries={['/app/caixas/7']}><Routes><Route path="/app/caixas/:id" element={<CaixaDetailPage />} /></Routes></MemoryRouter>)
  const btn = await screen.findByRole('button', { name: /avançar caixa/i })
  expect(btn).toBeDisabled()
})
```

- [ ] **Step 2: Rodar e ver falhar** → `npx vitest run src/app/caixas/CaixaDetailPage.test.tsx` → FAIL.

- [ ] **Step 3: Implementar** — no `CaixaDetailPage`:
  - Computar `pendentesLab = caixa.fase === 5 ? caixa.ordens.filter(o => wf ativa && o.desfecho_lab === 'pendente').length : 0`.
  - Cabeçalho: se `caixa.fase === 5`, badge `${prontos}/${total} prontos`.
  - Botão "Avançar caixa": `disabled = pendentesLab > 0`. `onClick`: se `TRANSICOES[caixa.fase]?.pedeCodRetorno` abre `AvancarCaixaModal`; senão `await caixasApi.avancar(id, { obs: null, cod_retorno: null })` + `carregar()`.
  - Botão "Cancelar caixa" → modal de motivo → `caixasApi.cancelar`.
  - Por linha (só fase 5 e `desfecho_lab === 'pendente'` e `podeEscrever`): botão "Sem conserto" → `SemConsertoModal` → `caixasApi.desfechoLab(o.id, {desfecho:'sem_conserto', obs})` + `carregar()`.
  - `AvancarCaixaModal`: input de `cod_retorno` obrigatório → `caixasApi.avancar(id, { cod_retorno, obs })`.
  - `SemConsertoModal`: textarea de justificativa obrigatória.
  - Remover/`substituir` o fluxo de "Fechar OS selecionadas" por-OS: a finalização agora é o "Avançar caixa" na fase 7 (o `fecharOrdens`/`FecharOrdensModal` por-OS fica obsoleto — remover na Task 17).

- [ ] **Step 4: Rodar e ver passar** → `npx vitest run src/app/caixas/CaixaDetailPage.test.tsx` → PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/caixas/
git commit -m "feat(ux): detalhe da caixa avanca cancela e marca sem conserto"
```

---

## Task 17: Frontend — limpar avançar/cancelar por-OS + changelog

**Files:**
- Modify: `frontend/src/app/ordens/OrdemDetailPage.tsx` (remover botões Avançar/Cancelar da OS), `frontend/src/app/changelog/data.ts`
- Remove (obsoletos): uso de `AvancarModal`/`CancelarModal`/`FecharOrdensModal` por-OS
- Test: rodar as suítes completas

**Interfaces:**
- Produces: a `OrdemDetailPage` deixa de oferecer avançar/cancelar (a OS anda pela caixa); mantém o trabalho técnico (recebimento, certificado). Changelog ganha a entrada da release.

- [ ] **Step 1: Remover os botões e modais de avançar/cancelar** da `OrdemDetailPage` (o `GerarCertificadoModal` e o recebimento permanecem). Ajustar/remover os testes `api.fluxoFases.test.ts`, `api.fecharOrdens.test.ts` que exercitam o avanço por-OS.

- [ ] **Step 2: Adicionar a entrada do changelog** (primeira do array em `data.ts`, vira a versão atual):

```ts
{
  versao: 'vX.Y.0',
  data: '2026-07-22',
  destaques: [
    'A Caixa agora é a unidade que anda pelas fases: a caixa só avança quando todos os aparelhos concluem o laboratório.',
    'Aparelho sem conserto pode ser marcado para não travar o lote.',
    'TaskHS e GrowthHS recebem 1 card por caixa (1 contato, 1 NF, 1 proposta) em vez de 1 por OS.',
  ],
},
```

(Confirmar o shape exato do array em `data.ts` antes de inserir; casar os nomes de campo existentes.)

- [ ] **Step 3: Verificação completa do frontend**

Run: `cd frontend && npm run lint && npx tsc -b --noEmit && npm run build`
Expected: sem erros.

- [ ] **Step 4: Verificação completa do backend**

Run: `cd backend && pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/ordens/OrdemDetailPage.tsx frontend/src/app/changelog/data.ts frontend/src/app/ordens/
git commit -m "feat(ux): os nao avanca sozinha e changelog da mudanca de caixa"
```

---

## Self-Review (preenchido pelo autor do plano)

- **Cobertura da spec:** modelo de dados (T1-T2) · gate Lab→PósVendas (T3, T6) · sem_conserto (T4) · invariante 1 já existia; invariante 2 (T5) · avançar/cancelar por caixa (T6-T7) · NF por caixa (T8) · agregação TaskHS/GrowthHS (T9-T10) · disparo por caixa (T11) · deprecar avanço por-OS (T12) · quadro por caixa (T13-T15) · posto de trabalho (T16) · limpeza + changelog (T17). ✅
- **Ordem de dependência:** T6/T7 chamam funções da T11 — nota no fim da T6 orienta stub temporário ou reordenar T11 antes de T6 na execução subagent-driven.
- **Placeholder scan:** T8 e T17 referenciam "confirmar o shape antes de inserir" (NF handler e array do changelog) — são leituras rápidas do arquivo-alvo, não placeholders de lógica; o passo diz exatamente o que fazer.
- **Nomes/tipos consistentes:** `desfecho_lab`/`DESFECHO_*`, `agendar_espelhamento_caixa`, `agendar_card_caixa`, `montar_*_caixa`, `caixasApi.avancar/cancelar/quadro/desfechoLab` — usados igualzinho entre tasks.

