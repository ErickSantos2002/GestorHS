# Fase 3B (Backend de Ordens de Serviço) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Backend completo da Ordem de Serviço — modelos, endpoints REST e motor de avanço por formulário-portão validado por função — coberto por pytest, sem frontend.

**Architecture:** Modelos SQLAlchemy `Fase`/`LogOS`/`Ordem` mapeando tabelas já existentes no banco; um módulo puro `os_workflow` com o grafo de transições lineares; routers `ordens`/`fases` e extensão de `funcoes`. Avanço/cancelamento validam dinamicamente a `funcao_responsavel` da fase atual (Admin sempre pode). `fase` é a fonte da verdade; `situacao` legado é mantido em sincronia.

**Tech Stack:** FastAPI, SQLAlchemy 2, Pydantic v2, pytest (SQLite in-memory).

**Spec:** `docs/superpowers/specs/2026-06-03-fase3b-backend-os-design.md`

**Comandos:** testes rodam no container (`docker compose up -d` na raiz `d:\GitHub\GestorHS`): `docker compose exec -T backend python -m pytest <args>`. Git via `git -C /d/GitHub/GestorHS`. Trailer de commit: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

**Branch:** antes da Task 1:
```bash
git -C /d/GitHub/GestorHS checkout -b feat/fase3b-backend-os
```

## Convenções do código (já estabelecidas — siga-as)

- Modelos: um arquivo por modelo em `backend/app/models/`, PK `Integer`, registrados em `app/models/__init__.py`. Relationships `lazy="joined"`; propriedades de conveniência expõem nomes relacionados.
- Routers em `backend/app/api/`, registrados em `backend/app/main.py` via `app.include_router(...)`. Padrão de lista: `{items, total}` com `offset`/`limit=Query(25, ge=1, le=100)`.
- Deps: `get_current_usuario` (qualquer interno), `require_funcao(*descricoes)` (403 fora da lista). `Usuario.funcao` (property) → descrição; `Usuario.funcao_id` → int. `excluir_protegido(db, obj)` em `app/api/cadastros_common.py` (IntegrityError→409).
- Testes: helper local por arquivo `_headers(client, login, senha)` faz `POST /auth/login` e devolve `{"Authorization": f"Bearer {tok['access_token']}"}`. Seed direto via `db_session`. Fixtures existentes: `client`, `db_session`, `usuario_admin` (login `admin`/`senha123`, função Administrador), `usuario_comum` (login `comum`/`senha123`, função **Expedição**).

---

### Task 1: Modelos `Fase`, `LogOS`, `Ordem` + fixtures compartilhadas

**Files:**
- Create: `backend/app/models/fase.py`
- Create: `backend/app/models/log_os.py`
- Create: `backend/app/models/ordem.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_os_models.py`

- [ ] **Step 1: Escrever o teste falhando** — `backend/tests/test_os_models.py`:

```python
def test_ordem_propriedades_e_relationships(db_session):
    from app.models import Cliente, Equipamento, EquipamentoCliente, Fase, Ordem, LogOS, Funcao
    exp = Funcao(descricao="Expedição")
    db_session.add(exp); db_session.flush()
    db_session.add(Fase(id=4, descricao="Recebido", cor="3b82f6", funcao_responsavel=exp.id))
    cli = Cliente(nome="ACME")
    eq = Equipamento(descricao="Bafômetro X")
    db_session.add_all([cli, eq]); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie="S-123")
    db_session.add(ec); db_session.flush()
    o = Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=4, tipo_servico="C")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    assert o.situacao == "E"        # default
    assert o.recebido is False      # default
    assert o.aceite is False        # default
    assert o.cliente_nome == "ACME"
    assert o.equipamento_serie == "S-123"
    assert o.equipamento_descricao == "Bafômetro X"
    assert o.fase_descricao == "Recebido"
    assert o.fase_cor == "3b82f6"
    log = LogOS(os=o.id, usuario=None, texto="abertura")
    db_session.add(log); db_session.commit(); db_session.refresh(log)
    assert log.os == o.id and log.texto == "abertura"


def test_fase_funcao_nome(db_session):
    from app.models import Fase, Funcao
    lab = Funcao(descricao="Laboratório")
    db_session.add(lab); db_session.flush()
    f = Fase(id=5, descricao="Laboratório", cor="6366f1", funcao_responsavel=lab.id)
    db_session.add(f); db_session.commit(); db_session.refresh(f)
    assert f.funcao_nome == "Laboratório"
    f2 = Fase(id=8, descricao="Finalizada", cor="10b981", funcao_responsavel=None)
    db_session.add(f2); db_session.commit(); db_session.refresh(f2)
    assert f2.funcao_nome is None
```

- [ ] **Step 2: Rodar o teste e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_os_models.py -q`
Expected: FAIL (ImportError: cannot import name 'Fase'/'Ordem'/'LogOS').

- [ ] **Step 3: Criar `backend/app/models/fase.py`**

```python
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.models.database import Base


class Fase(Base):
    __tablename__ = "fases"

    id = Column(Integer, primary_key=True, index=True)
    descricao = Column(String(100), nullable=False)
    cor = Column(String(6), nullable=False, default="000000")
    funcao_responsavel = Column(Integer, ForeignKey("funcoes.id"), nullable=True)

    funcao_rel = relationship("Funcao", lazy="joined")

    @property
    def funcao_nome(self):
        return self.funcao_rel.descricao if self.funcao_rel else None
```

- [ ] **Step 4: Criar `backend/app/models/log_os.py`**

```python
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from app.models.database import Base


class LogOS(Base):
    __tablename__ = "logs_os"

    id = Column(Integer, primary_key=True, index=True)
    os = Column(Integer, ForeignKey("ordens.id"), nullable=False)
    usuario = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    datalog = Column(DateTime(timezone=True), nullable=True)
    autor = Column(String(1), nullable=False, default="1")
    texto = Column(Text, nullable=True)
```

- [ ] **Step 5: Criar `backend/app/models/ordem.py`**

```python
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime, Numeric
from sqlalchemy.orm import relationship
from app.models.database import Base


class Ordem(Base):
    __tablename__ = "ordens"

    id = Column(Integer, primary_key=True, index=True)
    cliente = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    equipamento_cliente = Column(Integer, ForeignKey("equipamentos_cliente.id"), nullable=True)
    fase = Column(Integer, ForeignKey("fases.id"), nullable=True)
    tipo_calibragem = Column(Integer, nullable=True)
    caixa = Column(Integer, nullable=True)
    checklist = Column(String(50), nullable=True)
    # datas do ciclo
    data_solicitacao = Column(DateTime(timezone=True), nullable=True)
    data_envio = Column(DateTime(timezone=True), nullable=True)
    data_chegada = Column(DateTime(timezone=True), nullable=True)
    data_calibracao = Column(DateTime(timezone=True), nullable=True)
    data_retorno = Column(DateTime(timezone=True), nullable=True)
    data_entrega = Column(DateTime(timezone=True), nullable=True)
    prox_calibragem = Column(DateTime(timezone=True), nullable=True)
    # rastreio
    cod_envio = Column(String(50), nullable=True)
    cod_retorno = Column(String(50), nullable=True)
    etiqueta = Column(String(50), nullable=True)
    # resultados (preenchidos na 3E — intocados aqui)
    calib_cert = Column(String(50), nullable=True)
    calib_temp = Column(String(50), nullable=True)
    calib_pressao = Column(String(50), nullable=True)
    calib_teste1 = Column(String(50), nullable=True)
    calib_teste2 = Column(String(50), nullable=True)
    calib_teste3 = Column(String(50), nullable=True)
    calib_teste_media = Column(String(50), nullable=True)
    calib_situacao = Column(String(50), nullable=True)
    pdf_certificado = Column(String(50), nullable=True)
    certificado = Column(Text, nullable=True)
    # financeiro (fora do v1)
    valor = Column(Numeric(10, 2), nullable=False, default=0)
    frete_envio = Column(Numeric(10, 2), nullable=False, default=0)
    frete_retorno = Column(Numeric(10, 2), nullable=False, default=0)
    pago = Column(Boolean, nullable=False, default=False)
    recebido = Column(Boolean, nullable=False, default=False)
    # controle
    garantia = Column(Boolean, nullable=False, default=True)
    situacao = Column(String(1), nullable=False, default="E")
    chave = Column(String(12), nullable=True)
    pilhas = Column(Integer, nullable=True, default=0)
    sopradores = Column(Integer, nullable=True, default=0)
    arquivo = Column(String(50), nullable=True)
    obs = Column(Text, nullable=True)
    # adicionadas em 0002
    tipo_servico = Column(String(1), nullable=True)
    condicao_chegada = Column(Text, nullable=True)
    acessorios = Column(Text, nullable=True)
    aceite = Column(Boolean, nullable=False, default=False)
    data_aceite = Column(DateTime(timezone=True), nullable=True)

    cliente_rel = relationship("Cliente", lazy="joined")
    equipamento_rel = relationship("EquipamentoCliente", lazy="joined")
    fase_rel = relationship("Fase", lazy="joined")

    @property
    def cliente_nome(self):
        return self.cliente_rel.nome if self.cliente_rel else None

    @property
    def equipamento_serie(self):
        return self.equipamento_rel.serie if self.equipamento_rel else None

    @property
    def equipamento_descricao(self):
        return self.equipamento_rel.equipamento_descricao if self.equipamento_rel else None

    @property
    def fase_descricao(self):
        return self.fase_rel.descricao if self.fase_rel else None

    @property
    def fase_cor(self):
        return self.fase_rel.cor if self.fase_rel else None
```

- [ ] **Step 6: Registrar em `backend/app/models/__init__.py`** — adicione os imports e o `__all__`:

```python
from app.models.fase import Fase
from app.models.log_os import LogOS
from app.models.ordem import Ordem
```
E inclua `"Fase", "LogOS", "Ordem"` na lista `__all__`.

- [ ] **Step 7: Adicionar fixtures compartilhadas em `backend/tests/conftest.py`** (no fim do arquivo):

```python
def _get_or_create_funcao(db_session, descricao):
    f = db_session.query(Funcao).filter(Funcao.descricao == descricao).first()
    if f is None:
        f = Funcao(descricao=descricao)
        db_session.add(f)
        db_session.flush()
    return f


@pytest.fixture()
def fases_seed(db_session):
    from app.models import Fase
    exp = _get_or_create_funcao(db_session, "Expedição")
    lab = _get_or_create_funcao(db_session, "Laboratório")
    com = _get_or_create_funcao(db_session, "Comercial Pós-Vendas")
    db_session.add_all([
        Fase(id=4, descricao="Recebido", cor="3b82f6", funcao_responsavel=exp.id),
        Fase(id=5, descricao="Laboratório", cor="6366f1", funcao_responsavel=lab.id),
        Fase(id=6, descricao="Pós-Vendas", cor="f59e0b", funcao_responsavel=com.id),
        Fase(id=7, descricao="Preparando Retorno", cor="14b8a6", funcao_responsavel=exp.id),
        Fase(id=8, descricao="Finalizada", cor="10b981", funcao_responsavel=None),
        Fase(id=9, descricao="Cancelada", cor="ef4444", funcao_responsavel=None),
    ])
    db_session.commit()
    return {"exp": exp.id, "lab": lab.id, "com": com.id}


@pytest.fixture()
def usuario_lab(db_session):
    f = _get_or_create_funcao(db_session, "Laboratório")
    u = Usuario(nome="Lab", login="lab", senha=hash_senha("senha123"),
                email="lab@hs.com", funcao_id=f.id, precisa_redefinir_senha=False)
    db_session.add(u); db_session.commit(); db_session.refresh(u)
    return u


@pytest.fixture()
def usuario_comercial(db_session):
    f = _get_or_create_funcao(db_session, "Comercial Pós-Vendas")
    u = Usuario(nome="Comercial", login="comercial", senha=hash_senha("senha123"),
                email="comercial@hs.com", funcao_id=f.id, precisa_redefinir_senha=False)
    db_session.add(u); db_session.commit(); db_session.refresh(u)
    return u


@pytest.fixture()
def os_base(db_session):
    """Cria um cliente + equipamento + equipamento_cliente e devolve seus ids."""
    from app.models import Cliente, Equipamento, EquipamentoCliente
    cli = Cliente(nome="Cliente OS")
    eq = Equipamento(descricao="Bafômetro")
    db_session.add_all([cli, eq]); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie="SER-1", patrimonio="PAT-1")
    db_session.add(ec); db_session.commit(); db_session.refresh(ec)
    return {"cliente": cli.id, "equipamento": eq.id, "equipamento_cliente": ec.id}
```

- [ ] **Step 8: Rodar os testes e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_os_models.py -q`
Expected: PASS (2 passed).

- [ ] **Step 9: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/app/models/fase.py backend/app/models/log_os.py backend/app/models/ordem.py backend/app/models/__init__.py backend/tests/conftest.py backend/tests/test_os_models.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): modelos Fase/LogOS/Ordem + fixtures de teste da OS"
```

---

### Task 2: Motor de workflow (módulo puro)

**Files:**
- Create: `backend/app/core/os_workflow.py`
- Test: `backend/tests/test_os_workflow.py`

- [ ] **Step 1: Escrever o teste falhando** — `backend/tests/test_os_workflow.py`:

```python
from app.core import os_workflow as wf


def test_proxima_fase():
    assert wf.proxima_fase(4) == 5
    assert wf.proxima_fase(5) == 6
    assert wf.proxima_fase(6) == 7
    assert wf.proxima_fase(7) == 8
    assert wf.proxima_fase(8) is None   # terminal
    assert wf.proxima_fase(9) is None   # terminal


def test_eh_ativa():
    assert all(wf.eh_ativa(f) for f in (4, 5, 6, 7))
    assert not wf.eh_ativa(8)
    assert not wf.eh_ativa(9)


def test_constantes():
    assert wf.FASE_RECEBIDO == 4
    assert wf.FASE_FINALIZADA == 8
    assert wf.FASE_CANCELADA == 9
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_os_workflow.py -q`
Expected: FAIL (ModuleNotFoundError os_workflow).

- [ ] **Step 3: Criar `backend/app/core/os_workflow.py`**

```python
"""Grafo de transições da Ordem de Serviço (linear). Puro, sem I/O."""

FASE_RECEBIDO = 4
FASE_FINALIZADA = 8
FASE_CANCELADA = 9

# fase atual -> próxima fase (linear)
PROXIMA = {4: 5, 5: 6, 6: 7, 7: 8}
ATIVAS = (4, 5, 6, 7)


def proxima_fase(fase: int) -> int | None:
    return PROXIMA.get(fase)


def eh_ativa(fase: int) -> bool:
    return fase in ATIVAS
```

- [ ] **Step 4: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_os_workflow.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/app/core/os_workflow.py backend/tests/test_os_workflow.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): motor de workflow da OS (grafo de fases)"
```

---

### Task 3: Schemas da OS e das fases

**Files:**
- Create: `backend/app/schemas/ordens.py`
- Create: `backend/app/schemas/fases.py`
- Test: `backend/tests/test_os_schemas.py`

- [ ] **Step 1: Escrever o teste falhando** — `backend/tests/test_os_schemas.py`:

```python
import pytest
from pydantic import ValidationError


def test_abrir_in_valida_tipo_servico():
    from app.schemas.ordens import OrdemAbrirIn
    ok = OrdemAbrirIn(equipamento_cliente=1, tipo_servico="C")
    assert ok.tipo_servico == "C"
    with pytest.raises(ValidationError):
        OrdemAbrirIn(equipamento_cliente=1, tipo_servico="X")


def test_cancelar_in_exige_motivo():
    from app.schemas.ordens import CancelarIn
    with pytest.raises(ValidationError):
        CancelarIn(motivo="")


def test_avancar_in_opcional():
    from app.schemas.ordens import AvancarIn
    a = AvancarIn()
    assert a.obs is None and a.cod_retorno is None


def test_funcao_create_exige_descricao():
    from app.schemas.fases import FuncaoCreate
    with pytest.raises(ValidationError):
        FuncaoCreate(descricao="")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_os_schemas.py -q`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Criar `backend/app/schemas/ordens.py`**

```python
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class OrdemListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cliente: int
    cliente_nome: str | None = None
    equipamento_cliente: int | None = None
    equipamento_descricao: str | None = None
    equipamento_serie: str | None = None
    fase: int | None = None
    fase_descricao: str | None = None
    fase_cor: str | None = None
    tipo_servico: str | None = None
    data_chegada: datetime | None = None
    prox_calibragem: datetime | None = None
    situacao: str


class OrdemPage(BaseModel):
    items: list[OrdemListOut]
    total: int


class QuadroColuna(BaseModel):
    fase: int
    descricao: str
    cor: str
    ordens: list[OrdemListOut]


class OrdemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cliente: int
    cliente_nome: str | None = None
    equipamento_cliente: int | None = None
    equipamento_descricao: str | None = None
    equipamento_serie: str | None = None
    fase: int | None = None
    fase_descricao: str | None = None
    fase_cor: str | None = None
    tipo_servico: str | None = None
    condicao_chegada: str | None = None
    acessorios: str | None = None
    aceite: bool
    recebido: bool
    situacao: str
    etiqueta: str | None = None
    cod_retorno: str | None = None
    obs: str | None = None
    data_chegada: datetime | None = None
    data_calibracao: datetime | None = None
    data_retorno: datetime | None = None
    data_aceite: datetime | None = None
    prox_calibragem: datetime | None = None
    # espelho (preenchidos na 3E — só leitura)
    calib_cert: str | None = None
    calib_temp: str | None = None
    calib_pressao: str | None = None
    calib_teste_media: str | None = None
    calib_situacao: str | None = None
    pdf_certificado: str | None = None


class OrdemAbrirIn(BaseModel):
    equipamento_cliente: int
    tipo_servico: Literal["C", "M", "A"]
    condicao_chegada: str | None = None
    acessorios: str | None = None


class AvancarIn(BaseModel):
    obs: str | None = None
    cod_retorno: str | None = None


class CancelarIn(BaseModel):
    motivo: str = Field(min_length=1)


class LogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    os: int
    usuario: int | None = None
    autor: str
    datalog: datetime | None = None
    texto: str | None = None
```

- [ ] **Step 4: Criar `backend/app/schemas/fases.py`**

```python
from pydantic import BaseModel, ConfigDict, Field


class FaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    descricao: str
    cor: str
    funcao_responsavel: int | None = None
    funcao_nome: str | None = None


class FaseUpdate(BaseModel):
    funcao_responsavel: int | None = None


class FuncaoCreate(BaseModel):
    descricao: str = Field(min_length=1)


class FuncaoUpdate(BaseModel):
    descricao: str = Field(min_length=1)
```

- [ ] **Step 5: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_os_schemas.py -q`
Expected: PASS (4 passed).

- [ ] **Step 6: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/app/schemas/ordens.py backend/app/schemas/fases.py backend/tests/test_os_schemas.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): schemas da OS e das fases"
```

---

### Task 4: Router de fases (GET + PATCH responsável)

**Files:**
- Create: `backend/app/api/fases.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_fases.py`

- [ ] **Step 1: Escrever o teste falhando** — `backend/tests/test_fases.py`:

```python
def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def test_listar_fases(client, usuario_admin, fases_seed):
    h = _headers(client, "admin", "senha123")
    r = client.get("/fases", headers=h)
    assert r.status_code == 200
    fases = r.json()
    assert [f["id"] for f in fases] == [4, 5, 6, 7, 8, 9]
    recebido = next(f for f in fases if f["id"] == 4)
    assert recebido["descricao"] == "Recebido"
    assert recebido["funcao_nome"] == "Expedição"


def test_patch_fase_responsavel_admin(client, usuario_admin, usuario_lab, fases_seed):
    h = _headers(client, "admin", "senha123")
    lab_id = fases_seed["lab"]
    r = client.patch("/fases/4", json={"funcao_responsavel": lab_id}, headers=h)
    assert r.status_code == 200
    assert r.json()["funcao_responsavel"] == lab_id
    assert r.json()["funcao_nome"] == "Laboratório"


def test_patch_fase_funcao_inexistente_404(client, usuario_admin, fases_seed):
    h = _headers(client, "admin", "senha123")
    assert client.patch("/fases/4", json={"funcao_responsavel": 9999}, headers=h).status_code == 404


def test_patch_fase_inexistente_404(client, usuario_admin, fases_seed):
    h = _headers(client, "admin", "senha123")
    assert client.patch("/fases/99", json={"funcao_responsavel": None}, headers=h).status_code == 404


def test_patch_fase_exige_admin(client, usuario_admin, usuario_comum, fases_seed):
    h = _headers(client, "comum", "senha123")
    assert client.patch("/fases/4", json={"funcao_responsavel": None}, headers=h).status_code == 403
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_fases.py -q`
Expected: FAIL (404 em todas — rota /fases não existe).

- [ ] **Step 3: Criar `backend/app/api/fases.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Fase, Funcao
from app.api.deps import get_current_usuario, require_funcao
from app.schemas.fases import FaseOut, FaseUpdate

router = APIRouter(prefix="/fases", tags=["fases"])
ADMIN = "Administrador"


@router.get("", response_model=list[FaseOut])
def listar(db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    return db.query(Fase).order_by(Fase.id).all()


@router.patch("/{fase_id}", response_model=FaseOut)
def atualizar(fase_id: int, dados: FaseUpdate, db: Session = Depends(get_db),
              _: Usuario = Depends(require_funcao(ADMIN))):
    fase = db.query(Fase).filter(Fase.id == fase_id).first()
    if fase is None:
        raise HTTPException(status_code=404, detail="fase não encontrada")
    if dados.funcao_responsavel is not None:
        if db.query(Funcao).filter(Funcao.id == dados.funcao_responsavel).first() is None:
            raise HTTPException(status_code=404, detail="função não encontrada")
    fase.funcao_responsavel = dados.funcao_responsavel
    db.commit()
    db.refresh(fase)
    return fase
```

- [ ] **Step 4: Registrar o router em `backend/app/main.py`** — importe e inclua junto dos demais `include_router`:

```python
from app.api import fases
app.include_router(fases.router)
```

- [ ] **Step 5: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_fases.py -q`
Expected: PASS (5 passed).

- [ ] **Step 6: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/app/api/fases.py backend/app/main.py backend/tests/test_fases.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): router de fases (GET + PATCH funcao_responsavel)"
```

---

### Task 5: CRUD de funções (POST/PATCH/DELETE)

**Files:**
- Modify: `backend/app/api/funcoes.py`
- Test: `backend/tests/test_funcoes_crud.py`

> Nota: `GET /funcoes` já existe e é **admin-only** — não altere isso. Reuse `FuncaoOut` de `app/schemas/acesso.py` (já usado no GET).

- [ ] **Step 1: Escrever o teste falhando** — `backend/tests/test_funcoes_crud.py`:

```python
def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def test_criar_funcao(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    r = client.post("/funcoes", json={"descricao": "Recepção"}, headers=h)
    assert r.status_code == 201
    assert r.json()["descricao"] == "Recepção"


def test_criar_funcao_duplicada_409(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    client.post("/funcoes", json={"descricao": "Recepção"}, headers=h)
    assert client.post("/funcoes", json={"descricao": "Recepção"}, headers=h).status_code == 409


def test_patch_funcao(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    fid = client.post("/funcoes", json={"descricao": "Recepção"}, headers=h).json()["id"]
    r = client.patch(f"/funcoes/{fid}", json={"descricao": "Recepcao 2"}, headers=h)
    assert r.status_code == 200 and r.json()["descricao"] == "Recepcao 2"


def test_delete_funcao(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    fid = client.post("/funcoes", json={"descricao": "Temp"}, headers=h).json()["id"]
    assert client.delete(f"/funcoes/{fid}", headers=h).status_code == 204


def test_delete_funcao_em_uso_por_usuario_409(client, usuario_admin, usuario_comum):
    # usuario_comum tem função "Expedição"
    from app.models import Funcao
    h = _headers(client, "admin", "senha123")
    # descobre o id da função Expedição via lista
    fid = next(f["id"] for f in client.get("/funcoes", headers=h).json() if f["descricao"] == "Expedição")
    assert client.delete(f"/funcoes/{fid}", headers=h).status_code == 409


def test_delete_funcao_em_uso_por_fase_409(client, usuario_admin, fases_seed):
    h = _headers(client, "admin", "senha123")
    # função Laboratório é responsável pela fase 5
    fid = fases_seed["lab"]
    assert client.delete(f"/funcoes/{fid}", headers=h).status_code == 409


def test_funcoes_crud_exige_admin(client, usuario_admin, usuario_comum):
    h = _headers(client, "comum", "senha123")
    assert client.post("/funcoes", json={"descricao": "X"}, headers=h).status_code == 403
    assert client.patch("/funcoes/1", json={"descricao": "X"}, headers=h).status_code == 403
    assert client.delete("/funcoes/1", headers=h).status_code == 403
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_funcoes_crud.py -q`
Expected: FAIL (405/404 — POST/PATCH/DELETE não existem).

- [ ] **Step 3: Estender `backend/app/api/funcoes.py`** — substitua o conteúdo por:

```python
from fastapi import APIRouter, Depends, HTTPException, status as http_status
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Funcao
from app.api.deps import require_funcao
from app.api.cadastros_common import excluir_protegido
from app.schemas.acesso import FuncaoOut
from app.schemas.fases import FuncaoCreate, FuncaoUpdate

router = APIRouter(prefix="/funcoes", tags=["funcoes"])
ADMIN = "Administrador"


@router.get("", response_model=list[FuncaoOut])
def listar(db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    return db.query(Funcao).order_by(Funcao.id).all()


@router.post("", response_model=FuncaoOut, status_code=http_status.HTTP_201_CREATED)
def criar(dados: FuncaoCreate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    if db.query(Funcao).filter(Funcao.descricao == dados.descricao).first() is not None:
        raise HTTPException(status_code=409, detail="função já existe")
    obj = Funcao(descricao=dados.descricao)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/{funcao_id}", response_model=FuncaoOut)
def atualizar(funcao_id: int, dados: FuncaoUpdate, db: Session = Depends(get_db),
              _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(Funcao).filter(Funcao.id == funcao_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrada")
    existe = db.query(Funcao).filter(Funcao.descricao == dados.descricao, Funcao.id != funcao_id).first()
    if existe is not None:
        raise HTTPException(status_code=409, detail="função já existe")
    obj.descricao = dados.descricao
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{funcao_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def excluir(funcao_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(Funcao).filter(Funcao.id == funcao_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrada")
    excluir_protegido(db, obj)
```

> A proteção de exclusão depende das FKs `usuarios.funcao_id → funcoes.id` e `fases.funcao_responsavel → funcoes.id` com `PRAGMA foreign_keys=ON` (já ativo no conftest), que disparam IntegrityError → 409 em `excluir_protegido`.

- [ ] **Step 4: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_funcoes_crud.py -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/app/api/funcoes.py backend/tests/test_funcoes_crud.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): CRUD de funcoes (admin) com exclusao protegida"
```

---

### Task 6: Endpoints de leitura da OS (lista, quadro, detalhe, logs)

**Files:**
- Create: `backend/app/api/ordens.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_ordens_leitura.py`

- [ ] **Step 1: Escrever o teste falhando** — `backend/tests/test_ordens_leitura.py`:

```python
def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _ordem(db_session, cliente, equipamento_cliente, fase, **kw):
    from app.models import Ordem
    o = Ordem(cliente=cliente, equipamento_cliente=equipamento_cliente, fase=fase,
              situacao=kw.pop("situacao", "E"), **kw)
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    return o


def test_lista_paginada_e_total(client, usuario_admin, fases_seed, os_base, db_session):
    for fase in (4, 5, 6, 8):
        _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], fase)
    h = _headers(client, "admin", "senha123")
    r = client.get("/ordens?limit=2", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 4
    assert len(body["items"]) == 2
    # ordem id desc
    assert body["items"][0]["id"] > body["items"][1]["id"]


def test_lista_filtra_por_fase(client, usuario_admin, fases_seed, os_base, db_session):
    _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 5)
    _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 8)
    h = _headers(client, "admin", "senha123")
    r = client.get("/ordens?fase=5", headers=h)
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["fase"] == 5
    assert r.json()["items"][0]["fase_descricao"] == "Laboratório"


def test_lista_busca_por_id_numerico(client, usuario_admin, fases_seed, os_base, db_session):
    o = _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 4)
    h = _headers(client, "admin", "senha123")
    r = client.get(f"/ordens?q={o.id}", headers=h)
    assert r.json()["total"] == 1 and r.json()["items"][0]["id"] == o.id


def test_lista_busca_por_nome_cliente(client, usuario_admin, fases_seed, os_base, db_session):
    _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 4)
    h = _headers(client, "admin", "senha123")
    r = client.get("/ordens?q=Cliente OS", headers=h)
    assert r.json()["total"] == 1


def test_quadro_so_ativas_agrupado(client, usuario_admin, fases_seed, os_base, db_session):
    _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 4)
    _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 6)
    _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 8)  # finalizada, fora
    h = _headers(client, "admin", "senha123")
    colunas = client.get("/ordens/quadro", headers=h).json()
    assert [c["fase"] for c in colunas] == [4, 5, 6, 7]
    por_fase = {c["fase"]: len(c["ordens"]) for c in colunas}
    assert por_fase == {4: 1, 5: 0, 6: 1, 7: 0}


def test_detalhe_e_404(client, usuario_admin, fases_seed, os_base, db_session):
    o = _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 4, tipo_servico="C")
    h = _headers(client, "admin", "senha123")
    r = client.get(f"/ordens/{o.id}", headers=h)
    assert r.status_code == 200
    assert r.json()["cliente_nome"] == "Cliente OS"
    assert r.json()["equipamento_serie"] == "SER-1"
    assert client.get("/ordens/9999", headers=h).status_code == 404


def test_logs_da_os(client, usuario_admin, fases_seed, os_base, db_session):
    from app.models import LogOS
    o = _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 4)
    db_session.add(LogOS(os=o.id, usuario=None, texto="aberta")); db_session.commit()
    h = _headers(client, "admin", "senha123")
    r = client.get(f"/ordens/{o.id}/logs", headers=h)
    assert r.status_code == 200 and len(r.json()) == 1 and r.json()[0]["texto"] == "aberta"
    assert client.get("/ordens/9999/logs", headers=h).status_code == 404


def test_leitura_liberada_a_qualquer_interno(client, usuario_admin, usuario_comum, fases_seed, os_base, db_session):
    _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 4)
    h = _headers(client, "comum", "senha123")
    assert client.get("/ordens", headers=h).status_code == 200
    assert client.get("/ordens/quadro", headers=h).status_code == 200
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_ordens_leitura.py -q`
Expected: FAIL (404 — rota /ordens não existe).

- [ ] **Step 3: Criar `backend/app/api/ordens.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status as http_status, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Ordem, Cliente, Fase, LogOS
from app.api.deps import get_current_usuario
from app.core import os_workflow as wf
from app.schemas.ordens import OrdemListOut, OrdemPage, QuadroColuna, OrdemOut, LogOut

router = APIRouter(prefix="/ordens", tags=["ordens"])


@router.get("", response_model=OrdemPage)
def listar(
    fase: int | None = None,
    cliente: int | None = None,
    tipo: str | None = None,
    q: str | None = None,
    offset: int = 0,
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_usuario),
):
    query = db.query(Ordem)
    if fase is not None:
        query = query.filter(Ordem.fase == fase)
    if cliente is not None:
        query = query.filter(Ordem.cliente == cliente)
    if tipo:
        query = query.filter(Ordem.tipo_servico == tipo)
    if q:
        if q.strip().isdigit():
            query = query.filter(Ordem.id == int(q.strip()))
        else:
            termo = f"%{q}%"
            query = query.join(Cliente, Ordem.cliente == Cliente.id).filter(
                or_(Ordem.etiqueta.ilike(termo), Cliente.nome.ilike(termo))
            )
    total = query.count()
    items = query.order_by(Ordem.id.desc()).offset(offset).limit(limit).all()
    return OrdemPage(items=[OrdemListOut.model_validate(o) for o in items], total=total)


@router.get("/quadro", response_model=list[QuadroColuna])
def quadro(cliente: int | None = None, db: Session = Depends(get_db),
           _: Usuario = Depends(get_current_usuario)):
    fases = {f.id: f for f in db.query(Fase).filter(Fase.id.in_(wf.ATIVAS)).all()}
    colunas: list[QuadroColuna] = []
    for fid in wf.ATIVAS:
        query = db.query(Ordem).filter(Ordem.fase == fid)
        if cliente is not None:
            query = query.filter(Ordem.cliente == cliente)
        ordens = query.order_by(Ordem.id.desc()).all()
        f = fases.get(fid)
        colunas.append(QuadroColuna(
            fase=fid,
            descricao=f.descricao if f else "",
            cor=f.cor if f else "000000",
            ordens=[OrdemListOut.model_validate(o) for o in ordens],
        ))
    return colunas


@router.get("/{ordem_id}", response_model=OrdemOut)
def obter(ordem_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    obj = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    return obj


@router.get("/{ordem_id}/logs", response_model=list[LogOut])
def logs(ordem_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    if db.query(Ordem).filter(Ordem.id == ordem_id).first() is None:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    return db.query(LogOS).filter(LogOS.os == ordem_id).order_by(LogOS.id).all()
```

> Ordem das rotas importa: `/quadro` é declarada **antes** de `/{ordem_id}` para não ser capturada como id.

- [ ] **Step 4: Registrar o router em `backend/app/main.py`**

```python
from app.api import ordens
app.include_router(ordens.router)
```

- [ ] **Step 5: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_ordens_leitura.py -q`
Expected: PASS (8 passed).

- [ ] **Step 6: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/app/api/ordens.py backend/app/main.py backend/tests/test_ordens_leitura.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): endpoints de leitura da OS (lista, quadro, detalhe, logs)"
```

---

### Task 7: Abrir OS (POST /ordens)

**Files:**
- Create: `backend/app/api/ordens_acoes.py` (helpers de ação compartilhados)
- Modify: `backend/app/api/ordens.py`
- Test: `backend/tests/test_ordens_abrir.py`

> Os helpers de autorização dinâmica e de log ficam em `ordens_acoes.py` para serem reusados por abrir/avançar/cancelar (DRY).

- [ ] **Step 1: Escrever o teste falhando** — `backend/tests/test_ordens_abrir.py`:

```python
def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def test_abrir_os_sucesso(client, usuario_comum, fases_seed, os_base, db_session):
    # usuario_comum = Expedição
    h = _headers(client, "comum", "senha123")
    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C",
        "condicao_chegada": "riscado", "acessorios": "case",
    }, headers=h)
    assert r.status_code == 201
    body = r.json()
    assert body["fase"] == 4
    assert body["cliente"] == os_base["cliente"]      # derivado do equipamento
    assert body["recebido"] is True
    assert body["data_chegada"] is not None
    # os_atual atualizado no equipamento
    from app.models import EquipamentoCliente
    ec = db_session.get(EquipamentoCliente, os_base["equipamento_cliente"])
    db_session.refresh(ec)
    assert ec.os_atual == body["id"]
    # log de abertura
    logs = client.get(f"/ordens/{body['id']}/logs", headers=h).json()
    assert len(logs) == 1


def test_abrir_os_admin_tambem_pode(client, usuario_admin, fases_seed, os_base):
    h = _headers(client, "admin", "senha123")
    r = client.post("/ordens", json={"equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "M"}, headers=h)
    assert r.status_code == 201


def test_abrir_os_equipamento_inexistente_404(client, usuario_comum, fases_seed):
    h = _headers(client, "comum", "senha123")
    assert client.post("/ordens", json={"equipamento_cliente": 9999, "tipo_servico": "C"}, headers=h).status_code == 404


def test_abrir_os_duplicada_409(client, usuario_comum, fases_seed, os_base):
    h = _headers(client, "comum", "senha123")
    p = {"equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C"}
    assert client.post("/ordens", json=p, headers=h).status_code == 201
    assert client.post("/ordens", json=p, headers=h).status_code == 409  # já tem OS ativa


def test_abrir_os_exige_expedicao_ou_admin(client, usuario_admin, usuario_lab, fases_seed, os_base):
    h = _headers(client, "lab", "senha123")
    assert client.post("/ordens", json={"equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C"}, headers=h).status_code == 403
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_ordens_abrir.py -q`
Expected: FAIL (405/404 — POST /ordens não existe).

- [ ] **Step 3: Criar `backend/app/api/ordens_acoes.py`**

```python
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Ordem, Fase, LogOS, Usuario

ADMIN = "Administrador"


def agora() -> datetime:
    return datetime.now(timezone.utc)


def exige_funcao_da_fase(db: Session, usuario: Usuario, fase_id: int) -> None:
    """403 se o usuário não for Admin nem a função responsável pela fase atual."""
    if usuario.funcao == ADMIN:
        return
    fase = db.query(Fase).filter(Fase.id == fase_id).first()
    if fase is None or fase.funcao_responsavel is None or usuario.funcao_id != fase.funcao_responsavel:
        raise HTTPException(status_code=403, detail="Acesso negado para sua função nesta fase")


def registrar_log(db: Session, ordem: Ordem, usuario: Usuario | None, texto: str) -> None:
    db.add(LogOS(os=ordem.id, usuario=usuario.id if usuario else None, datalog=agora(), autor="1", texto=texto))
```

- [ ] **Step 4: Adicionar o endpoint `abrir` em `backend/app/api/ordens.py`**

Adicione os imports no topo:
```python
from app.api.deps import require_funcao
from app.api.ordens_acoes import agora, registrar_log
from app.models import EquipamentoCliente
from app.core import os_workflow as wf
from app.schemas.ordens import OrdemAbrirIn
```
E o endpoint (depois dos GET):
```python
@router.post("", response_model=OrdemOut, status_code=http_status.HTTP_201_CREATED)
def abrir(dados: OrdemAbrirIn, db: Session = Depends(get_db),
          usuario: Usuario = Depends(require_funcao("Expedição", "Administrador"))):
    ec = db.query(EquipamentoCliente).filter(EquipamentoCliente.id == dados.equipamento_cliente).first()
    if ec is None:
        raise HTTPException(status_code=404, detail="equipamento do cliente não encontrado")
    ativa = (
        db.query(Ordem)
        .filter(Ordem.equipamento_cliente == ec.id, Ordem.fase.in_(wf.ATIVAS))
        .first()
    )
    if ativa is not None:
        raise HTTPException(status_code=409, detail="aparelho já possui OS ativa")
    ordem = Ordem(
        cliente=ec.cliente,
        equipamento_cliente=ec.id,
        fase=wf.FASE_RECEBIDO,
        tipo_servico=dados.tipo_servico,
        condicao_chegada=dados.condicao_chegada,
        acessorios=dados.acessorios,
        data_chegada=agora(),
        recebido=True,
        situacao="E",
    )
    db.add(ordem)
    db.flush()
    ec.os_atual = ordem.id
    registrar_log(db, ordem, usuario, "OS aberta — Recebido")
    db.commit()
    db.refresh(ordem)
    return ordem
```

- [ ] **Step 5: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_ordens_abrir.py -q`
Expected: PASS (5 passed).

- [ ] **Step 6: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/app/api/ordens_acoes.py backend/app/api/ordens.py backend/tests/test_ordens_abrir.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): abrir OS (POST /ordens) com trava de duplicidade e os_atual"
```

---

### Task 8: Avançar OS (POST /ordens/{id}/avancar)

**Files:**
- Modify: `backend/app/api/ordens.py`
- Test: `backend/tests/test_ordens_avancar.py`

- [ ] **Step 1: Escrever o teste falhando** — `backend/tests/test_ordens_avancar.py`:

```python
def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _abrir(client, h, equipamento_cliente):
    return client.post("/ordens", json={"equipamento_cliente": equipamento_cliente, "tipo_servico": "C"}, headers=h).json()


def test_cadeia_feliz_completa(client, usuario_admin, usuario_comum, usuario_lab, usuario_comercial, fases_seed, os_base, db_session):
    he = _headers(client, "comum", "senha123")       # Expedição
    hl = _headers(client, "lab", "senha123")          # Laboratório
    hc = _headers(client, "comercial", "senha123")    # Comercial
    o = _abrir(client, he, os_base["equipamento_cliente"])
    oid = o["id"]
    # 4 -> 5 (Expedição)
    r = client.post(f"/ordens/{oid}/avancar", json={"obs": "ao lab"}, headers=he)
    assert r.status_code == 200 and r.json()["fase"] == 5
    # 5 -> 6 (Laboratório) seta data_calibracao
    r = client.post(f"/ordens/{oid}/avancar", json={}, headers=hl)
    assert r.json()["fase"] == 6 and r.json()["data_calibracao"] is not None
    # 6 -> 7 (Comercial) seta aceite
    r = client.post(f"/ordens/{oid}/avancar", json={}, headers=hc)
    assert r.json()["fase"] == 7 and r.json()["aceite"] is True and r.json()["data_aceite"] is not None
    # 7 -> 8 (Expedição) exige cod_retorno, situacao=F
    r = client.post(f"/ordens/{oid}/avancar", json={"cod_retorno": "BR123"}, headers=he)
    assert r.json()["fase"] == 8 and r.json()["situacao"] == "F" and r.json()["cod_retorno"] == "BR123"
    # logs acumulados: abertura + 4 avanços = 5
    assert len(client.get(f"/ordens/{oid}/logs", headers=he).json()) == 5


def test_avancar_funcao_errada_403(client, usuario_comum, usuario_lab, fases_seed, os_base):
    he = _headers(client, "comum", "senha123")
    hl = _headers(client, "lab", "senha123")
    o = _abrir(client, he, os_base["equipamento_cliente"])   # fase 4 (Expedição)
    # Laboratório não pode avançar a fase 4
    assert client.post(f"/ordens/{o['id']}/avancar", json={}, headers=hl).status_code == 403


def test_admin_override_avanca_qualquer_fase(client, usuario_admin, usuario_comum, fases_seed, os_base):
    he = _headers(client, "comum", "senha123")
    ha = _headers(client, "admin", "senha123")
    o = _abrir(client, he, os_base["equipamento_cliente"])
    # admin avança 4->5 mesmo sendo Administrador (não Expedição)
    assert client.post(f"/ordens/{o['id']}/avancar", json={}, headers=ha).json()["fase"] == 5


def test_avancar_cod_retorno_obrigatorio_422(client, usuario_admin, fases_seed, os_base, db_session):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"], fase=7, situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    ha = _headers(client, "admin", "senha123")
    r = client.post(f"/ordens/{o.id}/avancar", json={}, headers=ha)
    assert r.status_code == 422


def test_avancar_os_encerrada_409(client, usuario_admin, fases_seed, os_base, db_session):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"], fase=8, situacao="F")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    ha = _headers(client, "admin", "senha123")
    assert client.post(f"/ordens/{o.id}/avancar", json={}, headers=ha).status_code == 409


def test_avancar_os_inexistente_404(client, usuario_admin, fases_seed):
    ha = _headers(client, "admin", "senha123")
    assert client.post("/ordens/9999/avancar", json={}, headers=ha).status_code == 404
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_ordens_avancar.py -q`
Expected: FAIL (404 — /avancar não existe).

- [ ] **Step 3: Adicionar o endpoint `avancar` em `backend/app/api/ordens.py`**

Adicione ao import de `ordens_acoes`: `from app.api.ordens_acoes import agora, registrar_log, exige_funcao_da_fase` e importe `AvancarIn` de `app.schemas.ordens`. Endpoint:
```python
@router.post("/{ordem_id}/avancar", response_model=OrdemOut)
def avancar(ordem_id: int, dados: AvancarIn, db: Session = Depends(get_db),
            usuario: Usuario = Depends(get_current_usuario)):
    ordem = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if ordem is None:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    if not wf.eh_ativa(ordem.fase):
        raise HTTPException(status_code=409, detail="OS já encerrada")
    exige_funcao_da_fase(db, usuario, ordem.fase)
    destino = wf.proxima_fase(ordem.fase)
    origem = ordem.fase

    if origem == 5:                       # Laboratório -> Pós-Vendas
        ordem.data_calibracao = agora()
        texto = "Calibração/manutenção concluída"
    elif origem == 6:                     # Pós-Vendas -> Preparando Retorno
        ordem.aceite = True
        ordem.data_aceite = agora()
        texto = "Aceite registrado"
    elif origem == 7:                     # Preparando Retorno -> Finalizada
        if not (dados.cod_retorno and dados.cod_retorno.strip()):
            raise HTTPException(status_code=422, detail="cod_retorno é obrigatório para finalizar")
        ordem.cod_retorno = dados.cod_retorno.strip()
        ordem.data_retorno = agora()
        ordem.situacao = "F"
        texto = f"Postado para retorno — Finalizada (rastreio: {ordem.cod_retorno})"
    else:                                 # 4 -> 5 (Recebido -> Laboratório)
        texto = "Encaminhado ao laboratório"

    if dados.obs:
        texto = f"{texto} — {dados.obs}"
    ordem.fase = destino
    registrar_log(db, ordem, usuario, texto)
    db.commit()
    db.refresh(ordem)
    return ordem
```

- [ ] **Step 4: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_ordens_avancar.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/app/api/ordens.py backend/tests/test_ordens_avancar.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): avancar OS por portao com validacao dinamica de funcao"
```

---

### Task 9: Cancelar OS (POST /ordens/{id}/cancelar) + verificação final

**Files:**
- Modify: `backend/app/api/ordens.py`
- Test: `backend/tests/test_ordens_cancelar.py`

- [ ] **Step 1: Escrever o teste falhando** — `backend/tests/test_ordens_cancelar.py`:

```python
import pytest


def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _os_em(db_session, os_base, fase):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"], fase=fase, situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    return o


@pytest.mark.parametrize("fase,login", [(4, "comum"), (5, "lab"), (6, "comercial"), (7, "comum")])
def test_cancelar_pela_funcao_responsavel(client, usuario_comum, usuario_lab, usuario_comercial, fases_seed, os_base, db_session, fase, login):
    o = _os_em(db_session, os_base, fase)
    h = _headers(client, login, "senha123")
    r = client.post(f"/ordens/{o.id}/cancelar", json={"motivo": "cliente desistiu"}, headers=h)
    assert r.status_code == 200
    assert r.json()["fase"] == 9 and r.json()["situacao"] == "C"
    logs = client.get(f"/ordens/{o.id}/logs", headers=h).json()
    assert any("cliente desistiu" in (l["texto"] or "") for l in logs)


def test_cancelar_admin_sempre_pode(client, usuario_admin, fases_seed, os_base, db_session):
    o = _os_em(db_session, os_base, 5)
    h = _headers(client, "admin", "senha123")
    assert client.post(f"/ordens/{o.id}/cancelar", json={"motivo": "x"}, headers=h).json()["fase"] == 9


def test_cancelar_funcao_errada_403(client, usuario_comum, usuario_lab, fases_seed, os_base, db_session):
    o = _os_em(db_session, os_base, 4)   # responsável = Expedição
    h = _headers(client, "lab", "senha123")
    assert client.post(f"/ordens/{o.id}/cancelar", json={"motivo": "x"}, headers=h).status_code == 403


def test_cancelar_os_encerrada_409(client, usuario_admin, fases_seed, os_base, db_session):
    o = _os_em(db_session, os_base, 9)
    h = _headers(client, "admin", "senha123")
    assert client.post(f"/ordens/{o.id}/cancelar", json={"motivo": "x"}, headers=h).status_code == 409


def test_cancelar_motivo_vazio_422(client, usuario_admin, fases_seed, os_base, db_session):
    o = _os_em(db_session, os_base, 4)
    h = _headers(client, "admin", "senha123")
    assert client.post(f"/ordens/{o.id}/cancelar", json={"motivo": ""}, headers=h).status_code == 422


def test_cancelar_os_inexistente_404(client, usuario_admin, fases_seed):
    h = _headers(client, "admin", "senha123")
    assert client.post("/ordens/9999/cancelar", json={"motivo": "x"}, headers=h).status_code == 404
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_ordens_cancelar.py -q`
Expected: FAIL (404 — /cancelar não existe).

- [ ] **Step 3: Adicionar o endpoint `cancelar` em `backend/app/api/ordens.py`**

Importe `CancelarIn` de `app.schemas.ordens` e `FASE_CANCELADA` já vem via `wf`. Endpoint:
```python
@router.post("/{ordem_id}/cancelar", response_model=OrdemOut)
def cancelar(ordem_id: int, dados: CancelarIn, db: Session = Depends(get_db),
             usuario: Usuario = Depends(get_current_usuario)):
    ordem = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if ordem is None:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    if not wf.eh_ativa(ordem.fase):
        raise HTTPException(status_code=409, detail="OS já encerrada")
    exige_funcao_da_fase(db, usuario, ordem.fase)
    ordem.fase = wf.FASE_CANCELADA
    ordem.situacao = "C"
    registrar_log(db, ordem, usuario, f"OS cancelada: {dados.motivo}")
    db.commit()
    db.refresh(ordem)
    return ordem
```

- [ ] **Step 4: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_ordens_cancelar.py -q`
Expected: PASS (9 passed — 4 do parametrize + 5).

- [ ] **Step 5: Rodar a suíte inteira**

Run: `docker compose exec -T backend python -m pytest -q`
Expected: tudo verde (74 anteriores + ~44 novos ≈ 118 passed).

- [ ] **Step 6: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/app/api/ordens.py backend/tests/test_ordens_cancelar.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): cancelar OS (saida lateral) + suite completa verde"
```

---

## Notas para o executor

- A migração `0002` já foi aplicada ao banco real; os modelos refletem o schema pós-0002. A suíte usa SQLite via `create_all`, então as fixtures (`fases_seed`) é que materializam as 6 fases nos testes.
- `Ordem.equipamento_cliente` é FK; `EquipamentoCliente.os_atual` é `Integer` **sem** FK no modelo (evita ciclo no `create_all`) — atribuir o id da OS funciona normalmente.
- Autorização de avançar/cancelar é **dinâmica** (depende da `funcao_responsavel` da fase atual) — por isso usa `get_current_usuario` + `exige_funcao_da_fase`, não `require_funcao` fixo. Abrir usa `require_funcao("Expedição", "Administrador")`.
- Nada dos campos `calib_*`/certificado/`prox_calibragem`/espelhamento (3E), fotos, financeiro ou frontend é tocado nesta fase.
- Rotas estáticas (`/quadro`) antes das paramétricas (`/{ordem_id}`) no router.
```
