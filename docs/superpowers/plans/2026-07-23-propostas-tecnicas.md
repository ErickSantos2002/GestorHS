# Propostas Técnicas — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trazer a criação de Propostas Técnicas do Tiny para o GestorHS, portando o módulo Proposal (maduro) do `hsgrowth-sistema`, adaptado à convenção PT-BR do Gestor e plugado à frota real (`equipamento_cliente` + `status_calibracao`).

**Architecture:** Porta o modelo (proposta + itens-snapshot + versões/histórico), a camada de serviço/repo (numeração com retry, totais, versionamento) e o builder de HTML do PDF do GrowthHS. Remove o que é específico do board de cards do GrowthHS (N:N cards, status, marcador, prefill-from-card). Renderiza o PDF com o Playwright que o Gestor já usa (`core/certificado_pdf.py`). Adiciona o delta do Gestor: seleção de aparelhos da frota (com farol de vencimento) que preenche os templates do bloco técnico (com detecção Phoebus).

**Tech Stack:** Backend Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · pytest (SQLite in-memory). PDF: Playwright/Chromium (já instalado). Frontend React 19 · TS · Vite · Vitest · Tailwind. Nova dep frontend: `react-quill-new` (editor rico compatível com React 19).

**Fontes de port (repo `/home/ericks/github/hsgrowth-sistema/`):**
- `backend/app/models/proposal.py`, `models/proposal_version.py`, `models/service.py`, `models/product.py`, `models/mixins.py`
- `backend/app/services/proposal_service.py`, `repositories/proposal_repository.py`, `services/proposal_pdf_service.py`, `schemas/proposal.py`
- `frontend/src/utils/proposalDefaults.ts`, `components/proposals/ProposalModal.tsx`

## Global Constraints

- **Domínio em PT-BR** — TODOS os models/tabelas/colunas/rotas/variáveis/mensagens em PT-BR (o GrowthHS é em inglês; traduzir ao portar). Mapa de tradução na Task 2.
- **Commits** Conventional Commits em português **sem acentos** (ASCII), uma linha, sem trailer de co-autor. Escopos: `proposta`, `catalogo`, `pdf`, `ux`, `ui`.
- **Backend**: um model por arquivo em `models/` (exportar em `models/__init__.py`); schemas em `schemas/`; routers em `api/` registrados em `main.py`; lógica pura em `core/`.
- **Testes backend**: SQLite in-memory (`conftest.py`), `test_<modulo>.py`. Frontend: Vitest + Testing Library.
- **Permissão**: Propostas e catálogos (Serviços/Produtos) — função **Comercial Pós-Vendas** + **Administrador** (usar e gerenciar). Backend `require_funcao("Comercial Pós-Vendas", "Administrador")`; frontend helper novo em `roles.ts`.
- **Sem status/workflow, sem vínculo com OS/Caixa, sem cards** (não-objetivos da spec).
- **PDF**: renderizar com Playwright do Gestor; nunca WeasyPrint. Título **"Proposta Técnica"**.
- **Migração**: `revision="0020_propostas"`, `down_revision="0019_caixa_unidade_movimento"`.
- **Changelog**: próxima versão **1.25.0** (atual 1.24.1).

## Decisões de mecânica (derivadas da spec + exploração)

- **PDF ao vivo, versões em arquivo.** A proposta atual renderiza o PDF **on-the-fly** a cada request (padrão do Gestor — não persiste a "atual"). O **histórico** persiste o PDF de cada versão em `UPLOAD_DIR/propostas/{id}/v{n}.pdf` (grava bytes direto, como o GrowthHS). Não há coluna `proposta.pdf`.
- **Sem entidade Person.** O contato ("aos cuidados de") vira um campo texto na proposta + o `cliente.contato` do cadastro. Não porta o model Person.
- **Itens manuais** (sem auto-gerar dos aparelhos nesta entrega). Os aparelhos selecionados alimentam só o bloco técnico.
- **Histórico = snapshot completo** (portado) + **diff renderizado na tela** comparando versão N×N-1 (o "o que mudou" é derivado no frontend).

---

## Estrutura de arquivos

**Backend — criar:** `alembic/versions/0020_propostas.py`; `models/servico.py`, `produto.py`, `proposta.py` (Proposta+PropostaItem+PropostaAparelho), `proposta_versao.py`; `schemas/servico.py`, `produto.py`, `proposta.py`; `core/proposta_pdf.py` (builder HTML + geração/arquivamento); `api/servicos.py`, `produtos.py`, `propostas.py`; `tests/test_servicos.py`, `test_produtos.py`, `test_propostas.py`, `test_proposta_pdf.py`.
**Backend — modificar:** `core/certificado_pdf.py` (expor `renderizar_pdf`), `models/__init__.py`, `main.py`, `api/deps.py` (const `GESTOR_PROPOSTA` opcional).
**Frontend — criar:** `src/app/propostas/` (`api.ts`, `PropostasPage.tsx`, `PropostaModal.tsx`, `HistoricoModal.tsx`, `propostaDefaults.ts`, testes); telas de cadastro Serviço/Produto; `components/ui/RichText.tsx` (wrapper do react-quill-new).
**Frontend — modificar:** `src/auth/roles.ts`, rotas (`App.tsx`/`routes.tsx`), menu/nav, `changelog/data.ts`, `package.json` (react-quill-new).

---

## Task 1: Migração 0020 (todas as tabelas)

**Files:** Create `backend/alembic/versions/0020_propostas.py`

**Interfaces:** Produces as tabelas `servicos`, `produtos`, `propostas`, `proposta_itens`, `proposta_aparelhos`, `proposta_versoes`.

- [ ] **Step 1: Escrever a migração** (segue o padrão de `0019`; cabeçalho + `op.create_table`).

```python
"""propostas tecnicas: catalogos servico/produto + proposta/itens/aparelhos/versoes"""
import sqlalchemy as sa
from alembic import op

revision = "0020_propostas"
down_revision = "0019_caixa_unidade_movimento"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "servicos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sku", sa.String(length=100), nullable=True),
        sa.Column("nome", sa.String(length=255), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("unidade", sa.String(length=20), nullable=True),
        sa.Column("preco", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("codigo_servico", sa.String(length=100), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_servicos_sku", "servicos", ["sku"], unique=True)
    op.create_table(
        "produtos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sku", sa.String(length=100), nullable=True),
        sa.Column("nome", sa.String(length=255), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("unidade", sa.String(length=20), nullable=True),
        sa.Column("preco", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("ncm", sa.String(length=20), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_produtos_sku", "produtos", ["sku"], unique=True)
    op.create_table(
        "propostas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("cliente", sa.Integer(), sa.ForeignKey("clientes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("contato", sa.String(length=255), nullable=True),
        sa.Column("vendedor", sa.String(length=255), nullable=True),
        sa.Column("data", sa.Date(), nullable=True),
        sa.Column("intro", sa.Text(), nullable=True),
        sa.Column("outros_itens", sa.Text(), nullable=True),
        sa.Column("desconto", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("frete", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("forma_envio", sa.String(length=100), nullable=True),
        sa.Column("forma_frete", sa.String(length=100), nullable=True),
        sa.Column("transportador", sa.String(length=255), nullable=True),
        sa.Column("condicao_pagamento", sa.String(length=255), nullable=True),
        sa.Column("validade_dias", sa.Integer(), nullable=True),
        sa.Column("data_entrega", sa.Date(), nullable=True),
        sa.Column("descricao_entrega", sa.String(length=500), nullable=True),
        sa.Column("endereco_entrega_diferente", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("endereco_entrega", sa.JSON(), nullable=True),
        sa.Column("cliente_override", sa.JSON(), nullable=True),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("assinatura", sa.String(length=255), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_propostas_numero", "propostas", ["numero"], unique=True)
    op.create_table(
        "proposta_itens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("proposta", sa.Integer(), sa.ForeignKey("propostas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("descricao", sa.String(length=500), nullable=False),
        sa.Column("sku", sa.String(length=100), nullable=True),
        sa.Column("quantidade", sa.Numeric(12, 4), nullable=False, server_default="1"),
        sa.Column("unidade", sa.String(length=20), nullable=True),
        sa.Column("preco_un", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.create_table(
        "proposta_aparelhos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("proposta", sa.Integer(), sa.ForeignKey("propostas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("equipamento_cliente", sa.Integer(), sa.ForeignKey("equipamentos_cliente.id", ondelete="SET NULL"), nullable=True),
        sa.Column("serie", sa.String(length=100), nullable=True),
        sa.Column("modelo", sa.String(length=255), nullable=True),
        sa.Column("patrimonio", sa.String(length=100), nullable=True),
        sa.Column("prox_calibragem", sa.Date(), nullable=True),
    )
    op.create_table(
        "proposta_versoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("proposta", sa.Integer(), sa.ForeignKey("propostas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("numero_versao", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=True),
        sa.Column("pdf_path", sa.String(length=500), nullable=True),
        sa.Column("alterado_por", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("proposta_versoes")
    op.drop_table("proposta_aparelhos")
    op.drop_table("proposta_itens")
    op.drop_index("ix_propostas_numero", table_name="propostas")
    op.drop_table("propostas")
    op.drop_index("ix_produtos_sku", table_name="produtos")
    op.drop_table("produtos")
    op.drop_index("ix_servicos_sku", table_name="servicos")
    op.drop_table("servicos")
```

- [ ] **Step 2: Rodar baseline** — `cd backend && source .venv/bin/activate && pytest -q` (a suíte constrói tabelas pelos modelos; este passo é só baseline verde. As 4 falhas pré-existentes de upload permanecem).

- [ ] **Step 3: Commit** — `git add backend/alembic/versions/0020_propostas.py && git commit -m "feat(proposta): migracao catalogos e proposta"`

---

## Task 2: Models (PT-BR) + export

**Files:** Create `backend/app/models/servico.py`, `produto.py`, `proposta.py`, `proposta_versao.py`; Modify `backend/app/models/__init__.py`. Test `backend/tests/test_propostas.py`.

**Mapa de tradução growthhs→Gestor** (aplicar em todo o port): `Proposal`→`Proposta`, `ProposalItem`→`PropostaItem`, `ProposalVersion`→`PropostaVersao`, `Service`→`Servico`, `Product`→`Produto`. Colunas: `number`→`numero`, `client_id`→`cliente`, `seller_name`→`vendedor`, `date`→`data`, `other_items`→`outros_itens`, `discount`→`desconto`, `shipping`→`frete`, `shipping_method`→`forma_envio`, `freight_type`→`forma_frete`, `carrier_name`→`transportador`, `payment_terms`→`condicao_pagamento`, `validity_days`→`validade_dias`, `delivery_date`→`data_entrega`, `delivery_desc`→`descricao_entrega`, `different_delivery_address`→`endereco_entrega_diferente`, `delivery_address`→`endereco_entrega`, `client_override`→`cliente_override`, `notes`→`observacoes`, `signature`→`assinatura`, `intro`→`intro`. Item: `description`→`descricao`, `quantity`→`quantidade`, `unit`→`unidade`, `unit_price`→`preco_un`. Versão: `version_number`→`numero_versao`, `changed_by`→`alterado_por`. **Removidos:** `person_id`, `card_links`, `internal_status`, `product_id` (item).

**Interfaces:** Produces os models `Servico`, `Produto`, `Proposta` (rel `itens`, `aparelhos`, `versoes`, `cliente_rel`), `PropostaItem`, `PropostaAparelho`, `PropostaVersao`.

- [ ] **Step 1: Teste dos atributos** (RED)

```python
# backend/tests/test_propostas.py
def test_models_proposta_basico(db_session):
    from app.models import Cliente, Proposta, PropostaItem
    cli = Cliente(nome="ACME"); db_session.add(cli); db_session.flush()
    p = Proposta(numero=1, cliente=cli.id, vendedor="Fulano")
    p.itens.append(PropostaItem(descricao="Calibracao", quantidade=2, preco_un=395, total=790))
    db_session.add(p); db_session.flush()
    assert p.numero == 1
    assert p.itens[0].total == 790
    assert p.is_deleted is False
```

- [ ] **Step 2: Rodar e ver falhar** — `pytest tests/test_propostas.py -k models_proposta -v` → FAIL (ImportError).

- [ ] **Step 3: Escrever os models.** `servico.py` (traduz growthhs `service.py`, PT-BR, sem SoftDelete se não precisar — mantenha `ativo`):

```python
# backend/app/models/servico.py
from sqlalchemy import Column, Integer, String, Text, Numeric, Boolean
from app.models.database import Base


class Servico(Base):
    __tablename__ = "servicos"
    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(100), nullable=True, unique=True, index=True)
    nome = Column(String(255), nullable=False, index=True)
    descricao = Column(Text, nullable=True)
    unidade = Column(String(20), nullable=True)
    preco = Column(Numeric(12, 2), nullable=False, default=0)
    codigo_servico = Column(String(100), nullable=True)  # CNAE / codigo de servico
    ativo = Column(Boolean, nullable=False, default=True)
```

`produto.py` idêntico trocando `codigo_servico` por `ncm = Column(String(20), nullable=True)` e `__tablename__ = "produtos"`, classe `Produto`.

`proposta.py` (traduz `proposal.py` + adiciona `PropostaAparelho`; timestamps/soft-delete inline pois o Gestor não tem mixins):

```python
# backend/app/models/proposta.py
from datetime import datetime
from sqlalchemy import (Column, Integer, String, Text, Numeric, Date, DateTime,
                        ForeignKey, Boolean, JSON)
from sqlalchemy.orm import relationship
from app.models.database import Base


class Proposta(Base):
    __tablename__ = "propostas"
    id = Column(Integer, primary_key=True, index=True)
    numero = Column(Integer, nullable=False, unique=True, index=True)
    cliente = Column(Integer, ForeignKey("clientes.id", ondelete="SET NULL"), nullable=True, index=True)
    contato = Column(String(255), nullable=True)         # "aos cuidados de"
    vendedor = Column(String(255), nullable=True)        # = criador, imutavel
    data = Column(Date, nullable=True)
    intro = Column(Text, nullable=True)
    outros_itens = Column(Text, nullable=True)           # HTML do editor rico
    desconto = Column(Numeric(12, 2), nullable=False, default=0)
    frete = Column(Numeric(12, 2), nullable=False, default=0)
    forma_envio = Column(String(100), nullable=True)
    forma_frete = Column(String(100), nullable=True)
    transportador = Column(String(255), nullable=True)
    condicao_pagamento = Column(String(255), nullable=True)
    validade_dias = Column(Integer, nullable=True)
    data_entrega = Column(Date, nullable=True)
    descricao_entrega = Column(String(500), nullable=True)
    endereco_entrega_diferente = Column(Boolean, nullable=False, default=False)
    endereco_entrega = Column(JSON, nullable=True)
    cliente_override = Column(JSON, nullable=True)
    observacoes = Column(Text, nullable=True)
    assinatura = Column(String(255), nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    cliente_rel = relationship("Cliente", lazy="joined")
    itens = relationship("PropostaItem", back_populates="proposta_rel", cascade="all, delete-orphan", lazy="selectin")
    aparelhos = relationship("PropostaAparelho", back_populates="proposta_rel", cascade="all, delete-orphan", lazy="selectin")
    versoes = relationship("PropostaVersao", back_populates="proposta_rel", cascade="all, delete-orphan", lazy="selectin", order_by="PropostaVersao.numero_versao")


class PropostaItem(Base):
    __tablename__ = "proposta_itens"
    id = Column(Integer, primary_key=True, index=True)
    proposta = Column(Integer, ForeignKey("propostas.id", ondelete="CASCADE"), nullable=False, index=True)
    descricao = Column(String(500), nullable=False)
    sku = Column(String(100), nullable=True)
    quantidade = Column(Numeric(12, 4), nullable=False, default=1)
    unidade = Column(String(20), nullable=True)
    preco_un = Column(Numeric(12, 2), nullable=False, default=0)
    total = Column(Numeric(12, 2), nullable=False, default=0)
    proposta_rel = relationship("Proposta", back_populates="itens")


class PropostaAparelho(Base):
    __tablename__ = "proposta_aparelhos"
    id = Column(Integer, primary_key=True, index=True)
    proposta = Column(Integer, ForeignKey("propostas.id", ondelete="CASCADE"), nullable=False, index=True)
    equipamento_cliente = Column(Integer, ForeignKey("equipamentos_cliente.id", ondelete="SET NULL"), nullable=True)
    serie = Column(String(100), nullable=True)
    modelo = Column(String(255), nullable=True)
    patrimonio = Column(String(100), nullable=True)
    prox_calibragem = Column(Date, nullable=True)
    proposta_rel = relationship("Proposta", back_populates="aparelhos")
```

`proposta_versao.py` (traduz `proposal_version.py`):

```python
# backend/app/models/proposta_versao.py
from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, JSON, DateTime
from sqlalchemy.orm import relationship
from app.models.database import Base


class PropostaVersao(Base):
    __tablename__ = "proposta_versoes"
    id = Column(Integer, primary_key=True, index=True)
    proposta = Column(Integer, ForeignKey("propostas.id", ondelete="CASCADE"), nullable=False, index=True)
    numero_versao = Column(Integer, nullable=False)
    snapshot = Column(JSON, nullable=True)
    pdf_path = Column(String(500), nullable=True)
    alterado_por = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    proposta_rel = relationship("Proposta", back_populates="versoes")
```

Adicionar todos ao `backend/app/models/__init__.py` (seguir o padrão de export existente: `from app.models.proposta import Proposta, PropostaItem, PropostaAparelho`, etc.).

- [ ] **Step 4: Rodar e ver passar** — `pytest tests/test_propostas.py -k models_proposta -v` → PASS.
- [ ] **Step 5: Commit** — `git add backend/app/models/ backend/tests/test_propostas.py && git commit -m "feat(proposta): models servico produto proposta itens aparelhos versoes"`

---

## Task 3: Catálogo de Serviços — schema + API (CRUD)

**Files:** Create `backend/app/schemas/servico.py`, `backend/app/api/servicos.py`; Modify `backend/app/main.py` (registrar), `backend/app/api/deps.py` (const). Test `backend/tests/test_servicos.py`.

**Interfaces:** Produces `GET/POST/PATCH/DELETE /servicos` (list sem auth-de-escrita; escrita `require_funcao("Comercial Pós-Vendas", "Administrador")`). Schemas `ServicoOut/Create/Update`.

- [ ] **Step 1: Teste** (RED) — criar serviço exige função; listar retorna.

```python
# backend/tests/test_servicos.py
def test_criar_servico_exige_funcao(client, client_comercial):
    r = client.post("/servicos", json={"nome": "Calibracao", "sku": "312", "preco": 395})
    assert r.status_code in (401, 403)
    r = client_comercial.post("/servicos", json={"nome": "Calibracao", "sku": "312", "preco": 395})
    assert r.status_code == 201
    assert r.json()["sku"] == "312"
```

> Fixture `client_comercial` (usuário função "Comercial Pós-Vendas", login real) deve ser adicionada ao `conftest.py` reusando o padrão de `client_lab`/`client_fin` (login via `/auth/login`, `fases_seed` não é necessário aqui).

- [ ] **Step 2: Rodar e ver falhar** — `pytest tests/test_servicos.py -v` → FAIL (404).

- [ ] **Step 3: Implementar.** Schema (espelha o padrão de `schemas/cadastros.py`):

```python
# backend/app/schemas/servico.py
from typing import Optional
from pydantic import BaseModel, Field


class ServicoOut(BaseModel):
    id: int
    sku: Optional[str] = None
    nome: str
    descricao: Optional[str] = None
    unidade: Optional[str] = None
    preco: float = 0
    codigo_servico: Optional[str] = None
    ativo: bool = True
    model_config = {"from_attributes": True}


class ServicoCreate(BaseModel):
    nome: str = Field(min_length=1)
    sku: Optional[str] = None
    descricao: Optional[str] = None
    unidade: Optional[str] = None
    preco: float = 0
    codigo_servico: Optional[str] = None
    ativo: bool = True


class ServicoUpdate(BaseModel):
    nome: Optional[str] = Field(default=None, min_length=1)
    sku: Optional[str] = None
    descricao: Optional[str] = None
    unidade: Optional[str] = None
    preco: Optional[float] = None
    codigo_servico: Optional[str] = None
    ativo: Optional[bool] = None
```

Router (espelha `api/marcas.py`, mas com todos os campos e a função Comercial):

```python
# backend/app/api/servicos.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.models.database import get_db
from app.models import Usuario, Servico
from app.api.deps import get_current_usuario, require_funcao
from app.schemas.servico import ServicoOut, ServicoCreate, ServicoUpdate

router = APIRouter(prefix="/servicos", tags=["servicos"])
_escrita = require_funcao("Comercial Pós-Vendas", "Administrador")


@router.get("", response_model=list[ServicoOut])
def listar(q: str | None = None, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    query = db.query(Servico)
    if q:
        query = query.filter(Servico.nome.ilike(f"%{q}%") | Servico.sku.ilike(f"%{q}%"))
    return query.order_by(Servico.nome).all()


@router.post("", response_model=ServicoOut, status_code=status.HTTP_201_CREATED)
def criar(dados: ServicoCreate, db: Session = Depends(get_db), _: Usuario = Depends(_escrita)):
    obj = Servico(**dados.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@router.patch("/{item_id}", response_model=ServicoOut)
def atualizar(item_id: int, dados: ServicoUpdate, db: Session = Depends(get_db), _: Usuario = Depends(_escrita)):
    obj = db.query(Servico).filter(Servico.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    for chave, valor in dados.model_dump(exclude_unset=True).items():
        setattr(obj, chave, valor)
    db.commit(); db.refresh(obj)
    return obj


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(_escrita)):
    obj = db.query(Servico).filter(Servico.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    db.delete(obj); db.commit()
```

Registrar em `main.py`: adicionar `servicos` ao import da linha 8 e `app.include_router(servicos.router)` no bloco de include_routers.

- [ ] **Step 4: Rodar e ver passar** — `pytest tests/test_servicos.py -v` → PASS; suíte completa `pytest -q`.
- [ ] **Step 5: Commit** — `git add backend/app/schemas/servico.py backend/app/api/servicos.py backend/app/main.py backend/tests/ && git commit -m "feat(catalogo): cadastro de servicos com sku"`

---

## Task 4: Catálogo de Produtos — schema + API

**Files:** Create `backend/app/schemas/produto.py`, `backend/app/api/produtos.py`; Modify `main.py`. Test `backend/tests/test_produtos.py`.

**Interfaces:** Idêntico à Task 3 trocando `Servico`→`Produto`, `codigo_servico`→`ncm`, prefixo `/produtos`.

- [ ] **Step 1: Teste** — espelhar `test_servicos.py` para produtos (criar exige função, `ncm` no lugar de `codigo_servico`).
- [ ] **Step 2: Rodar e ver falhar** → FAIL.
- [ ] **Step 3: Implementar** — copiar Task 3 (schema `produto.py` com `ncm: Optional[str]`; router `produtos.py` idêntico com `Produto`/prefix `/produtos`); registrar em `main.py`.
- [ ] **Step 4: Rodar e ver passar** → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(catalogo): cadastro de produtos avulsos"`

---

## Task 5: Schemas de Proposta (PT-BR, enxutos)

**Files:** Create `backend/app/schemas/proposta.py`. Test em `test_propostas.py`.

**Interfaces:** Produces `PropostaItemCreate/Out`, `PropostaAparelhoCreate/Out`, `PropostaCreate`, `PropostaUpdate`, `PropostaOut`, `PropostaListOut`, `PropostaVersaoOut`. Porta `schemas/proposal.py` com o mapa de tradução da Task 2; **remove** `service_card_id`, `internal_status`, `marker`, `linked_cards`, `person_id`, `product_id`; **adiciona** `contato` e a lista `aparelhos`.

- [ ] **Step 1: Escrever o schema** (traduzir `schemas/proposal.py`; `date`→`data` com alias de tipo `date as date_type`). Campos derivados na resposta: `total_itens`, `total`, `cliente_nome`, `cliente_documento`. `PropostaAparelhoCreate` = `{equipamento_cliente: int}` (o backend faz o snapshot série/modelo). Incluir `PropostaVersaoOut { id, numero_versao, alterado_por, created_at, has_pdf, snapshot }`.

```python
# backend/app/schemas/proposta.py  (esqueleto — completar todos os campos do model Proposta da Task 2)
from datetime import date as date_type, datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class PropostaItemBase(BaseModel):
    descricao: str
    sku: Optional[str] = None
    quantidade: float = 1
    unidade: Optional[str] = None
    preco_un: float = 0

class PropostaItemCreate(PropostaItemBase):
    pass

class PropostaItemOut(PropostaItemBase):
    id: int
    total: float
    model_config = {"from_attributes": True}


class PropostaAparelhoCreate(BaseModel):
    equipamento_cliente: int

class PropostaAparelhoOut(BaseModel):
    id: int
    equipamento_cliente: Optional[int] = None
    serie: Optional[str] = None
    modelo: Optional[str] = None
    patrimonio: Optional[str] = None
    prox_calibragem: Optional[date_type] = None
    model_config = {"from_attributes": True}


class PropostaBase(BaseModel):
    cliente: Optional[int] = None
    contato: Optional[str] = None
    vendedor: Optional[str] = None
    data: Optional[date_type] = None
    intro: Optional[str] = None
    outros_itens: Optional[str] = None
    desconto: float = 0
    frete: float = 0
    forma_envio: Optional[str] = None
    forma_frete: Optional[str] = None
    transportador: Optional[str] = None
    condicao_pagamento: Optional[str] = None
    validade_dias: Optional[int] = None
    data_entrega: Optional[date_type] = None
    descricao_entrega: Optional[str] = None
    endereco_entrega_diferente: bool = False
    endereco_entrega: Optional[dict] = None
    cliente_override: Optional[dict] = None
    observacoes: Optional[str] = None
    assinatura: Optional[str] = None

class PropostaCreate(PropostaBase):
    itens: List[PropostaItemCreate] = Field(default_factory=list)
    aparelhos: List[PropostaAparelhoCreate] = Field(default_factory=list)

class PropostaUpdate(BaseModel):
    # todos opcionais; se itens/aparelhos vierem, substituem a lista inteira
    # (copiar todos os campos de PropostaBase como Optional + itens/aparelhos Optional[List])
    ...

class PropostaVersaoOut(BaseModel):
    id: int
    numero_versao: int
    alterado_por: Optional[str] = None
    created_at: Optional[datetime] = None
    has_pdf: bool = False
    snapshot: Optional[dict] = None
    model_config = {"from_attributes": True}

class PropostaOut(PropostaBase):
    id: int
    numero: int
    itens: List[PropostaItemOut] = Field(default_factory=list)
    aparelhos: List[PropostaAparelhoOut] = Field(default_factory=list)
    total_itens: float = 0
    total: float = 0
    cliente_nome: Optional[str] = None
    cliente_documento: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = {"from_attributes": True}

class PropostaListOut(BaseModel):
    items: List[PropostaOut]
    total: int
    page: int
    page_size: int
    total_pages: int
```

- [ ] **Step 2: Commit** — `git add backend/app/schemas/proposta.py && git commit -m "feat(proposta): schemas pydantic da proposta"`

---

## Task 6: Camada de serviço/repo — numeração, totais, itens/aparelhos, versionamento

**Files:** Create `backend/app/core/proposta_servico.py` (lógica de service+repo unida; o Gestor não usa camada de repository separada — colocar como funções que recebem `db`). Test `backend/tests/test_propostas.py`.

**Interfaces:** Consumes models + schemas. Produces:
- `proximo_numero(db) -> int` = `max(numero)+1`.
- `criar_proposta(db, dados: PropostaCreate, vendedor: str) -> Proposta` — retry anti-corrida (5x, IntegrityError, rollback), aplica itens (calcula `total = quantidade*preco_un`) e aparelhos (snapshot série/modelo/patrimônio/prox da frota), `vendedor` = nome do usuário.
- `atualizar_proposta(db, proposta, dados, alterado_por)` — **versiona antes** (snapshot + `arquivar_pdf_versao`), depois aplica (não sobrescreve `vendedor`; se `itens`/`aparelhos` vierem, substitui a lista).
- `montar_saida(db, proposta) -> PropostaOut` — calcula `total_itens = soma(item.total)`, `total = total_itens + frete − desconto`, `cliente_nome`/`cliente_documento` respeitando `cliente_override`.
- `snapshot_proposta(proposta) -> dict` — estado exibível (número, data, cliente, total, itens[...]) — portar `_snapshot`.

Portar de `proposal_service.py` (`_to_response`, `_snapshot`, `create`, `update`) e `proposal_repository.py` (`next_number`, `_apply_items`, `create` com retry, `update`, `add_version`). Remover tudo de cards/marcador. Ao aplicar aparelhos, buscar o `EquipamentoCliente` e gravar snapshot:

```python
def _aplicar_aparelhos(db, proposta, aparelhos):
    from app.models import EquipamentoCliente
    proposta.aparelhos.clear()
    for a in aparelhos:
        ec = db.get(EquipamentoCliente, a.equipamento_cliente)
        proposta.aparelhos.append(PropostaAparelho(
            equipamento_cliente=a.equipamento_cliente,
            serie=ec.serie if ec else None,
            modelo=ec.equipamento_descricao if ec else None,
            patrimonio=ec.patrimonio if ec else None,
            prox_calibragem=ec.prox_calibragem.date() if ec and ec.prox_calibragem else None,
        ))
```

- [ ] **Step 1: Testes** (RED) — numeração incremental; total calculado; snapshot de item; aparelho puxa série da frota; update cria versão.

```python
def test_criar_proposta_calcula_total_e_numero(db_session):
    from app.core import proposta_servico as ps
    from app.schemas.proposta import PropostaCreate, PropostaItemCreate
    from app.models import Cliente
    cli = Cliente(nome="ACME"); db_session.add(cli); db_session.flush()
    dados = PropostaCreate(cliente=cli.id, itens=[PropostaItemCreate(descricao="Calib", quantidade=2, preco_un=395)])
    p = ps.criar_proposta(db_session, dados, vendedor="Fulano")
    assert p.numero == 1
    assert float(p.itens[0].total) == 790.0
    out = ps.montar_saida(db_session, p)
    assert out.total == 790.0

def test_atualizar_cria_versao(db_session, monkeypatch):
    # monkeypatch arquivar_pdf_versao -> retorna None (nao renderiza PDF no teste)
    ...
```

- [ ] **Step 2: Rodar e ver falhar** → FAIL.
- [ ] **Step 3: Implementar** `core/proposta_servico.py` conforme interfaces acima (portar as funções literais do growthhs, traduzidas). `arquivar_pdf_versao` é importado da Task 7 (proposta_pdf) — no versionamento, chamar dentro de try/except best-effort (igual growthhs).
- [ ] **Step 4: Rodar e ver passar** → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(proposta): numeracao totais itens aparelhos e versionamento"`

---

## Task 7: PDF — refactor do renderer + builder da proposta

**Files:** Modify `backend/app/core/certificado_pdf.py` (expor `renderizar_pdf`); Create `backend/app/core/proposta_pdf.py`. Test `backend/tests/test_proposta_pdf.py`.

**Interfaces:**
- `certificado_pdf.renderizar_pdf(documento_html: str, *, scale: float = 1.0, margin_mm: int = 0) -> bytes` — extrai o miolo Playwright+anti-SSRF de `html_para_pdf` numa função reusável que recebe um **documento HTML completo** (não embrulha). `html_para_pdf` passa a chamar `renderizar_pdf(montar_documento(html_cert), scale=0.8, margin_mm=8)`.
- `proposta_pdf.montar_html(proposta, cliente) -> str` — porta `_build_html` + `_CSS` do growthhs, com: título "Proposta Técnica"; campos do `Cliente` do Gestor (`nome`, `cgc`/`cpf`→documento, `endereco`, `municipio`/`estado`, `email`, `celular`/`whatsapp`/`telefones`, `contato`); helpers `_fmt_moeda`/`_fmt_data`/`_fmt_documento`/`_esc`/`_sanitizar_html` (portar literais de `proposal_pdf_service.py:42-110`); `_CSS` **copiado verbatim** de `proposal_pdf_service.py:117-337`.
- `proposta_pdf.gerar_pdf(db, proposta_id) -> bytes` — carrega a proposta (não-deletada), `montar_html`, `renderizar_pdf`.
- `proposta_pdf.arquivar_pdf_versao(db, proposta, numero_versao) -> str|None` — porta `archive_version_pdf`: grava bytes em `UPLOAD_DIR/propostas/{id}/v{n}.pdf` (usa `settings.UPLOAD_DIR`), best-effort.
- `proposta_pdf.ler_pdf_versao(pdf_path) -> bytes` — porta `read_version_pdf`.

**Copiar verbatim (referência exata):** o bloco `_CSS` (`proposal_pdf_service.py:117-337`) e a estrutura de `_build_html` (`:340-708`) — adaptar SÓ o acesso a dados do cliente (mapa Cliente do Gestor) e o texto do título. As seções (cabeçalho H&S, endereço, itens, outros itens sanitizados, totais, condições, assinatura) são idênticas.

- [ ] **Step 1: Refactor `certificado_pdf.py`** — extrair `renderizar_pdf(documento, *, scale, margin_mm)` (o corpo do `with sync_playwright()` de `html_para_pdf`), e reescrever `html_para_pdf` para delegar. Rodar os testes de certificado existentes para garantir que não quebrou: `pytest -k certificado -q` (ignorar as 4 falhas pré-existentes de upload).
- [ ] **Step 2: Teste do builder** (RED) — o HTML tem "Proposta Técnica", o nome do cliente, e a soma dos itens.

```python
def test_montar_html_tem_titulo_tecnica(db_session):
    from app.core import proposta_pdf
    from app.models import Cliente, Proposta, PropostaItem
    cli = Cliente(nome="ACME", cgc="08857492000148")
    db_session.add(cli); db_session.flush()
    p = Proposta(numero=7, cliente=cli.id)
    p.itens.append(PropostaItem(descricao="Calibracao", quantidade=1, preco_un=395, total=395))
    db_session.add(p); db_session.flush()
    html = proposta_pdf.montar_html(p, cli)
    assert "Proposta Técnica" in html
    assert "ACME" in html
    assert "395" in html
```

- [ ] **Step 3: Rodar e ver falhar** → FAIL.
- [ ] **Step 4: Implementar** `proposta_pdf.py` (portar/adaptar conforme interfaces). NÃO chamar Playwright no teste do builder (só testa a string). `gerar_pdf` é exercitado só via endpoint (Task 8) com Playwright disponível.
- [ ] **Step 5: Rodar e ver passar** → PASS; suíte `pytest -q`.
- [ ] **Step 6: Commit** — `git add backend/app/core/certificado_pdf.py backend/app/core/proposta_pdf.py backend/tests/test_proposta_pdf.py && git commit -m "feat(pdf): builder da proposta tecnica via playwright do gestor"`

---

## Task 8: API de Propostas

**Files:** Create `backend/app/api/propostas.py`; Modify `main.py`. Test `test_propostas.py`.

**Interfaces (porta `endpoints/proposals.py`, enxuto):**
- `GET /propostas?page&page_size&q` → `PropostaListOut` (só não-deletadas).
- `POST /propostas` (`require_funcao(...)`, injeta `vendedor = usuario.nome`) → `PropostaOut` (201).
- `GET /propostas/{id}` → `PropostaOut`.
- `PUT /propostas/{id}` → atualiza (versiona antes).
- `DELETE /propostas/{id}` → soft-delete (`is_deleted=True`, `deleted_at=now`).
- `GET /propostas/{id}/pdf?download=0|1` → `Response(content=gerar_pdf(...), media_type="application/pdf", headers=Content-Disposition)` (padrão dos certificados do Gestor).
- `GET /propostas/{id}/versoes` → `list[PropostaVersaoOut]` (com `has_pdf = bool(pdf_path)`).
- `GET /propostas/{id}/versoes/{versao_id}/pdf` → `Response(ler_pdf_versao(v.pdf_path), ...)`.
- `POST /propostas/{id}/duplicar` (**novo**) → clona a proposta (novo `numero`, copia itens/aparelhos/campos, `data=hoje`, `vendedor=usuario.nome`, sem versões), retorna a nova `PropostaOut`.

Ordem das rotas: declarar `/{id}/pdf`, `/{id}/versoes...`, `/{id}/duplicar` **antes** de `/{id}` (lição do GrowthHS).

- [ ] **Step 1: Testes** (RED) — criar via API exige função; PDF endpoint devolve `application/pdf`; duplicar gera número novo; delete some da lista.
- [ ] **Step 2: Rodar e ver falhar** → FAIL.
- [ ] **Step 3: Implementar** o router; registrar em `main.py` (cuidar da ordem se o prefixo colidir — `/propostas` é específico, ok).
- [ ] **Step 4: Rodar e ver passar** → PASS (o teste de PDF exige Playwright; se o ambiente não tiver, marcar `@pytest.mark.skipif`).
- [ ] **Step 5: Commit** — `git commit -m "feat(proposta): api de propostas com pdf versoes e duplicar"`

---

## Task 9: roles.ts + backend gate + nav

**Files:** Modify `frontend/src/auth/roles.ts`, rotas (`App.tsx`/`routes.tsx`), menu. (Backend já usa `require_funcao("Comercial Pós-Vendas", "Administrador")` nas Tasks 3/4/8.)

**Interfaces:** Produces `podeGerenciarPropostas(user)` = `isAdmin || funcao === FUNCAO_COMERCIAL` em `roles.ts` (espelha o backend). Usar pra gatear a página e os cadastros no menu.

- [ ] **Step 1:** adicionar em `roles.ts`:
```ts
export function podeGerenciarPropostas(user: User | null): boolean {
  return isAdmin(user) || user?.funcao === FUNCAO_COMERCIAL
}
```
- [ ] **Step 2:** adicionar as rotas `/app/propostas`, `/app/catalogo/servicos`, `/app/catalogo/produtos` (lazy) e itens de menu gateados por `podeGerenciarPropostas`.
- [ ] **Step 3: Commit** — `git commit -m "feat(ux): rota e permissao de propostas e catalogo"`

---

## Task 10: Frontend — dependência do editor rico + api.ts

**Files:** Modify `frontend/package.json` (add `react-quill-new`); Create `frontend/src/components/ui/RichText.tsx`, `frontend/src/app/propostas/api.ts`. Test `frontend/src/app/propostas/api.test.ts`.

**Interfaces:**
- Adicionar `react-quill-new` (compatível React 19) via `npm i react-quill-new`. `RichText.tsx` = wrapper fino (`import ReactQuill from 'react-quill-new'; import 'react-quill-new/dist/quill.snow.css'`) com props `value`/`onChange`.
- `propostas/api.ts`: tipos (`Proposta`, `PropostaItem`, `PropostaAparelho`, `PropostaVersao`, `PropostaCreate`) + métodos `listar/obter/criar/atualizar/excluir/pdfUrl/duplicar/listarVersoes/versaoPdfUrl`. E `servicosApi`/`produtosApi` via o `crudClient` de `cadastros/api.ts` (`crudClient('/servicos')`, `crudClient('/produtos')`). E `frotaDoCliente(clienteId)` chamando `GET /equipamentos-cliente?cliente=<id>&limit=100` (já existe no backend, devolve `status_calibracao` por item).

- [ ] **Step 1: Teste** (Vitest) do api.ts (mockar `apiJson`, espelhar `caixas/api.test.ts`): `criar` posta em `/propostas`, `duplicar` posta em `/propostas/:id/duplicar`.
- [ ] **Step 2: Rodar e ver falhar** — `cd frontend && npx vitest run src/app/propostas/api.test.ts` → FAIL.
- [ ] **Step 3: Implementar** `RichText.tsx` + `api.ts`. `npm i react-quill-new` primeiro.
- [ ] **Step 4: Rodar e ver passar** + `npx tsc -b --noEmit`.
- [ ] **Step 5: Commit** — `git commit -m "feat(ui): editor rico e api de propostas no frontend"`

---

## Task 11: Frontend — cadastros de Serviços e Produtos

**Files:** Create páginas de cadastro (Serviços, Produtos) em `frontend/src/app/catalogo/` (espelhar `EquipamentosPanel.tsx` — form multi-campo com `Input`/`Select`/`Badge`, tabela + modal). Test ao lado.

**Interfaces:** Consome `servicosApi`/`produtosApi` (Task 10). Páginas gateadas por `podeGerenciarPropostas`.

- [ ] **Step 1: Teste** — a página lista serviços e o modal cria (mock da api).
- [ ] **Step 2: Rodar e ver falhar** → FAIL.
- [ ] **Step 3: Implementar** copiando o esqueleto de `EquipamentosPanel.tsx` (estados `form`/`VAZIO`/`set`, grid de inputs: nome, sku, unidade, preço, codigo_servico/ncm, ativo). Duas páginas (Serviço/Produto).
- [ ] **Step 4: Rodar e ver passar** + `tsc`.
- [ ] **Step 5: Commit** — `git commit -m "feat(ui): cadastros de servicos e produtos"`

---

## Task 12: Frontend — templates do bloco técnico (port)

**Files:** Create `frontend/src/app/propostas/propostaDefaults.ts`.

**Interfaces:** Porta **verbatim** `frontend/src/utils/proposalDefaults.ts` do GrowthHS: `esc`, `DEFAULT_NOTES`, `buildDefaultOtherItems(modelo, aparelhos)`, `buildPhoebusOtherItems(serial, modulo)`. Sem mudanças (o conteúdo é o mesmo boilerplate H&S).

- [ ] **Step 1:** Copiar o arquivo literal de `hsgrowth-sistema/frontend/src/utils/proposalDefaults.ts` para `frontend/src/app/propostas/propostaDefaults.ts`.
- [ ] **Step 2: Commit** — `git commit -m "feat(proposta): templates bafometro e phoebus do bloco tecnico"`

---

## Task 13: Frontend — construtor (PropostaModal) + seção de frota

**Files:** Create `frontend/src/app/propostas/PropostaModal.tsx`. Test ao lado.

**Interfaces:** Porta `components/proposals/ProposalModal.tsx` do GrowthHS (seções: Cliente + override, Identificação, Itens com busca no catálogo, Outros itens com `RichText` + seletor de modelo, Totais, Transportador, Condições, Observações/Assinatura), **removendo** o vínculo com card e `internal_status`, e **adicionando** a seção **Aparelhos**:
- Ao escolher o cliente, chamar `frotaDoCliente(clienteId)` → lista com **farol** (`status_calibracao`: badge vencido=vermelho / vencendo=amarelo / em dia=verde / sem data=cinza) + checkbox por aparelho. Selecionados → `aparelhos: [{equipamento_cliente}]` no payload.
- Botão "Aplicar modelo" no bloco Outros itens: usa os aparelhos marcados para montar `modelo`/`aparelhos`/`serial` e chamar `buildDefaultOtherItems`/`buildPhoebusOtherItems`. Detecção Phoebus: o item da frota já traz o elo (ver `_anotar_elo` no backend — expor `modulo_instalado`/série do Phoebus no schema da frota, ou usar heurística de modelo `/phoebus/i`).
- Busca de item por linha: `servicosApi.listar({q})` + `produtosApi.listar({q})` → ao selecionar, copia `nome`→descricao, `sku`, `preco`→preco_un.
- Totais recalculados no cliente (`total_itens = soma(qtd*preco_un)`, `total = total_itens + frete − desconto`).

- [ ] **Step 1: Teste** — marcar um aparelho da frota mock adiciona ao payload; escolher modelo Phoebus preenche o editor; total recalcula.
- [ ] **Step 2: Rodar e ver falhar** → FAIL.
- [ ] **Step 3: Implementar** portando o `ProposalModal` (adaptar imports do design system do Gestor: `Modal`/`Input`/`Select`/`Button`/`Badge`; `RichText` da Task 10). Usar `EMPTY_FORM` traduzido (Task 5 fields).
- [ ] **Step 4: Rodar e ver passar** + `tsc` + `eslint`.
- [ ] **Step 5: Commit** — `git commit -m "feat(ux): construtor de proposta com selecao de frota"`

---

## Task 14: Frontend — lista de Propostas + Histórico (com diff)

**Files:** Create `frontend/src/app/propostas/PropostasPage.tsx`, `HistoricoModal.tsx`. Test ao lado.

**Interfaces:**
- `PropostasPage`: tabela (Número, Data, Cliente, CNPJ, Valor, Ações). Ações por linha: Ver PDF (abre `pdfUrl` inline), Editar (abre `PropostaModal`), Baixar PDF, **Duplicar** (`duplicar` → abre a nova pra editar), Histórico (abre `HistoricoModal`), Excluir (confirm → `excluir`). Busca por cliente/número. Botão "Nova proposta".
- `HistoricoModal`: `listarVersoes(id)` → cards `#vN`, data-hora, "Alterado por", total; botão ver/baixar PDF da versão (`versaoPdfUrl`, desabilita se `!has_pdf`). **Diff campo-a-campo:** comparar `snapshot` da versão N com a N-1 (ou com o estado atual para a mais recente) e renderizar as diferenças ("Frete: 200 → 250", "Item adicionado/removido"). Implementar `diffSnapshots(anterior, atual): string[]` puro + teste.

- [ ] **Step 1: Teste** — `diffSnapshots` detecta mudança de frete e item adicionado; a lista renderiza ações; o histórico lista versões.
- [ ] **Step 2: Rodar e ver falhar** → FAIL.
- [ ] **Step 3: Implementar** a página, o modal de histórico e o `diffSnapshots` puro.
- [ ] **Step 4: Rodar e ver passar** + `tsc` + `eslint`.
- [ ] **Step 5: Commit** — `git commit -m "feat(ux): lista de propostas e historico com diff"`

---

## Task 15: Verificação final + changelog

**Files:** Modify `frontend/src/app/changelog/data.ts`; verificação completa.

- [ ] **Step 1: Changelog** — adicionar como PRIMEIRA entrada do array `CHANGELOG` (shape `{versao, data, itens:[{tipo, texto}]}`):
```ts
{
  versao: '1.25.0',
  data: '23/07/2026',
  itens: [
    { tipo: 'novidade', texto: 'Nova página de Propostas Técnicas: monte a proposta escolhendo o cliente, os aparelhos da frota (com farol de vencimento) e os itens do catálogo, e gere o PDF.' },
    { tipo: 'novidade', texto: 'Novos cadastros de Serviços (com SKU) e Produtos para compor as propostas.' },
    { tipo: 'melhoria', texto: 'Histórico de alterações da proposta: veja quem mudou o quê e quando, com o PDF de cada versão.' },
  ],
},
```
- [ ] **Step 2: Verificação backend** — `cd backend && source .venv/bin/activate && pytest -q` (só as 4 falhas pré-existentes de upload).
- [ ] **Step 3: Verificação frontend** — `cd frontend && npm run lint && npx tsc -b --noEmit && npm run build`.
- [ ] **Step 4: Rodar o app e conferir o PDF** — gerar uma proposta de teste e conferir visualmente o PDF (título "Proposta Técnica", layout fiel ao Tiny). Ajustar `scale`/`margin` no `renderizar_pdf` se a densidade destoar (o CSS do GrowthHS foi feito pra WeasyPrint em 1:1; no Chromium usar `scale=1.0`, `margin_mm=0` e deixar o `@page 1.5cm` do CSS mandar).
- [ ] **Step 5: Commit** — `git commit -m "docs(changelog): v1.25.0 - propostas tecnicas"`

---

## Self-Review

- **Cobertura da spec:** catálogos separados (T3, T4) · proposta+itens-snapshot+aparelhos+versões (T2, T6) · PDF Playwright título Proposta Técnica (T7) · API incl. duplicar (T8) · frota com farol no construtor (T13) · histórico snapshot + diff na tela (T14) · permissão Comercial+Admin (T9) · editor rico (T10) · changelog 1.25.0 (T15). ✅
- **Dependência de ordem:** T6 usa `arquivar_pdf_versao` da T7 — executar T7 antes de T6, ou stub no versionamento (nota na T6). Recomendo **T7 antes de T6** na execução.
- **Placeholder scan:** `PropostaUpdate` na T5 e trechos "copiar verbatim de proposal_pdf_service.py:linhas" — são referências de cópia exata (o arquivo-fonte é literal e está mapeado), não placeholders de lógica. O `_CSS` (220 linhas) e os templates são cópia direta.
- **Risco visual (PDF):** o CSS do GrowthHS foi desenhado pra WeasyPrint; no Chromium pode precisar de ajuste de `scale`/`@page` (T15 Step 4 cobre a conferência visual).
- **Nomes/tipos consistentes:** mapa de tradução PT-BR fixado na T2 e reusado em todas as tasks (`proposta`, `numero`, `frete`, `desconto`, `outros_itens`, `preco_un`, `numero_versao`, `alterado_por`).
