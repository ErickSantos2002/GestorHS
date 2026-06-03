# Fase 1C (Clientes & Funcionários) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gerir clientes (lista paginada com busca + página de detalhe/edição) e seus funcionários, com leitura para qualquer interno e escrita só Administrador — encerrando os cadastros base da Fase 1.

**Architecture:** Backend FastAPI: `/clientes` com busca (`q` ilike) e paginação (`offset`/`limit`, devolve `{items,total}`), CRUD admin-write/read-any, exclusão protegida por FK (409); funcionários aninhados em `/clientes/{id}/funcionarios`. Frontend React: item de nav visível a todos, página de lista com busca+paginação, página de detalhe `/app/clientes/:id` (form em seções, somente-leitura para não-admin) e uma seção de funcionários embutida. TDD no backend (pytest, SQLite com FK ligado) e na lógica do frontend (Vitest+RTL).

**Tech Stack:** FastAPI, SQLAlchemy 2, Pydantic v2, pytest; React 19, TypeScript, Vite 8, react-router-dom 7, Vitest + RTL.

**Referências:**
- Spec: `docs/superpowers/specs/2026-06-03-fase1c-clientes-funcionarios-design.md`
- Deps: `get_current_usuario` (qualquer interno), `require_funcao("Administrador")`, `excluir_protegido(db,obj)` (IntegrityError→409). Modelos `Setor`, `Grupo` existem. Frontend reusa `apiJson`/`apiFetch`/`ApiError`, `useAuth`/`isAdmin`, componentes do design system, e `gruposApi`/`setoresApi` de `app/cadastros/api.ts`.
- Tabelas já no banco: `clientes` (id bigserial, grupo→grupos, nome, cgc, cpf, endereco, numero bigint, complemento, bairro, municipio, estado char(2), cep char(8), contato, email, telefones, celular, whatsapp, whatsapp1, whatsapp2, insc_mun, insc_est, datcad, obs, imagem, ativo); `funcionarios` (id, cliente→clientes NOT NULL, setor→setores, matricula, centro, nome, email, cargo, admissao, idade, sexo, estado, cidade, ativo).

**Teste backend:** roda no container, da raiz `d:\GitHub\GestorHS`: `docker compose exec -T backend python -m pytest <args>` (garanta `docker compose up -d`). Fixtures: `client`, `db_session`, `usuario_admin` (admin/senha123), `usuario_comum` (comum/senha123). SQLite com `PRAGMA foreign_keys=ON`.

**Convenções TS:** `verbatimModuleSyntax` (`import { type X }`), `noUnusedLocals`/`noUnusedParameters`. npm da pasta `frontend/`; git via `git -C /d/GitHub/GestorHS`. Lint baseline limpo.

**Branch:** rode tudo em `feat/fase1c-clientes`. Antes da Task 1:
```bash
git -C /d/GitHub/GestorHS checkout -b feat/fase1c-clientes
```

---

### Task 1: Backend — modelos + CRUD de clientes (lista paginada/busca, delete protegido)

**Files:**
- Create: `backend/app/models/cliente.py`, `backend/app/models/funcionario.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/app/schemas/clientes.py`
- Create: `backend/app/api/clientes.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_clientes.py`

- [ ] **Step 1: Teste que falha** — crie `backend/tests/test_clientes.py`:

```python
def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def test_clientes_read_interno_write_admin(client, usuario_admin, usuario_comum):
    assert client.get("/clientes", headers=_headers(client, "comum", "senha123")).status_code == 200
    assert client.post("/clientes", json={"nome": "X"}, headers=_headers(client, "comum", "senha123")).status_code == 403


def test_cliente_crud(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    criado = client.post("/clientes", json={"nome": "ACME LTDA", "municipio": "São Paulo", "cgc": "11222333000144"}, headers=h)
    assert criado.status_code == 201
    cid = criado.json()["id"]
    assert client.get(f"/clientes/{cid}", headers=h).json()["nome"] == "ACME LTDA"
    assert client.get("/clientes/99999", headers=h).status_code == 404
    assert client.patch(f"/clientes/{cid}", json={"municipio": "Campinas"}, headers=h).json()["municipio"] == "Campinas"
    assert client.delete(f"/clientes/{cid}", headers=h).status_code == 204
    assert client.get(f"/clientes/{cid}", headers=h).status_code == 404


def test_clientes_busca_e_paginacao(client, usuario_admin, db_session):
    from app.models import Cliente
    for i in range(30):
        db_session.add(Cliente(nome=f"Cliente {i:02d}", municipio="Sorocaba"))
    db_session.add(Cliente(nome="Especial", municipio="Bauru"))
    db_session.commit()
    h = _headers(client, "admin", "senha123")
    # paginação
    r = client.get("/clientes?offset=0&limit=10", headers=h).json()
    assert r["total"] == 31
    assert len(r["items"]) == 10
    # busca filtra
    r2 = client.get("/clientes?q=Especial", headers=h).json()
    assert r2["total"] == 1
    assert r2["items"][0]["nome"] == "Especial"
    # busca por municipio
    r3 = client.get("/clientes?q=Sorocaba", headers=h).json()
    assert r3["total"] == 30


def test_excluir_cliente_em_uso_409(client, usuario_admin, db_session):
    from app.models import Cliente, Funcionario
    c = Cliente(nome="Com funcionario")
    db_session.add(c)
    db_session.flush()
    db_session.add(Funcionario(cliente=c.id, nome="João"))
    db_session.commit()
    r = client.delete(f"/clientes/{c.id}", headers=_headers(client, "admin", "senha123"))
    assert r.status_code == 409
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_clientes.py -q`
Expected: FAIL (404 / ImportError de Cliente/Funcionario).

- [ ] **Step 3: Modelo Cliente** — crie `backend/app/models/cliente.py`:

```python
from sqlalchemy import Column, Integer, BigInteger, String, Text, Boolean, ForeignKey, Date
from app.models.database import Base


class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(BigInteger, primary_key=True, index=True)
    grupo = Column(Integer, ForeignKey("grupos.id"), nullable=True)
    nome = Column(String(100), nullable=True)
    cgc = Column(String(14), nullable=True)
    cpf = Column(String(11), nullable=True)
    endereco = Column(String(100), nullable=True)
    numero = Column(BigInteger, nullable=True)
    complemento = Column(String(60), nullable=True)
    bairro = Column(String(100), nullable=True)
    municipio = Column(String(100), nullable=True)
    estado = Column(String(2), nullable=True)
    cep = Column(String(8), nullable=True)
    contato = Column(String(30), nullable=True)
    email = Column(String(100), nullable=True)
    telefones = Column(String(250), nullable=True)
    celular = Column(String(250), nullable=True)
    whatsapp = Column(String(50), nullable=True)
    whatsapp1 = Column(String(50), nullable=True)
    whatsapp2 = Column(String(50), nullable=True)
    insc_mun = Column(String(20), nullable=True)
    insc_est = Column(String(20), nullable=True)
    datcad = Column(Date, nullable=True)
    obs = Column(Text, nullable=True)
    imagem = Column(String(50), nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)
```

- [ ] **Step 4: Modelo Funcionario** — crie `backend/app/models/funcionario.py`:

```python
from sqlalchemy import Column, Integer, BigInteger, String, Boolean, ForeignKey, Date
from app.models.database import Base


class Funcionario(Base):
    __tablename__ = "funcionarios"

    id = Column(Integer, primary_key=True, index=True)
    cliente = Column(BigInteger, ForeignKey("clientes.id"), nullable=False)
    setor = Column(Integer, ForeignKey("setores.id"), nullable=True)
    matricula = Column(String(50), nullable=False, default="0")
    centro = Column(String(50), nullable=True)
    nome = Column(String(100), nullable=True)
    email = Column(String(200), nullable=True)
    cargo = Column(String(50), nullable=True)
    admissao = Column(Date, nullable=True)
    idade = Column(Integer, nullable=True)
    sexo = Column(String(1), nullable=True)
    estado = Column(String(2), nullable=True, default="SP")
    cidade = Column(String(100), nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)
```

- [ ] **Step 5: Registrar modelos** — substitua `backend/app/models/__init__.py`:

```python
from app.models.funcao import Funcao
from app.models.usuario import Usuario
from app.models.usuario_cliente import UsuarioCliente
from app.models.setor import Setor
from app.models.categoria import Categoria
from app.models.marca import Marca
from app.models.grupo import Grupo
from app.models.equipamento import Equipamento
from app.models.cliente import Cliente
from app.models.funcionario import Funcionario

__all__ = [
    "Funcao", "Usuario", "UsuarioCliente", "Setor", "Categoria",
    "Marca", "Grupo", "Equipamento", "Cliente", "Funcionario",
]
```

- [ ] **Step 6: Schemas de cliente** — crie `backend/app/schemas/clientes.py`:

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date


class ClienteListOut(BaseModel):
    id: int
    nome: Optional[str] = None
    cgc: Optional[str] = None
    cpf: Optional[str] = None
    municipio: Optional[str] = None
    estado: Optional[str] = None
    ativo: bool
    model_config = {"from_attributes": True}


class ClientesPage(BaseModel):
    items: list[ClienteListOut]
    total: int


class ClienteOut(BaseModel):
    id: int
    grupo: Optional[int] = None
    nome: Optional[str] = None
    cgc: Optional[str] = None
    cpf: Optional[str] = None
    endereco: Optional[str] = None
    numero: Optional[int] = None
    complemento: Optional[str] = None
    bairro: Optional[str] = None
    municipio: Optional[str] = None
    estado: Optional[str] = None
    cep: Optional[str] = None
    contato: Optional[str] = None
    email: Optional[str] = None
    telefones: Optional[str] = None
    celular: Optional[str] = None
    whatsapp: Optional[str] = None
    whatsapp1: Optional[str] = None
    whatsapp2: Optional[str] = None
    insc_mun: Optional[str] = None
    insc_est: Optional[str] = None
    datcad: Optional[date] = None
    obs: Optional[str] = None
    ativo: bool
    model_config = {"from_attributes": True}


class ClienteCreate(BaseModel):
    nome: str = Field(min_length=1)
    grupo: Optional[int] = None
    cgc: Optional[str] = None
    cpf: Optional[str] = None
    endereco: Optional[str] = None
    numero: Optional[int] = None
    complemento: Optional[str] = None
    bairro: Optional[str] = None
    municipio: Optional[str] = None
    estado: Optional[str] = None
    cep: Optional[str] = None
    contato: Optional[str] = None
    email: Optional[str] = None
    telefones: Optional[str] = None
    celular: Optional[str] = None
    whatsapp: Optional[str] = None
    whatsapp1: Optional[str] = None
    whatsapp2: Optional[str] = None
    insc_mun: Optional[str] = None
    insc_est: Optional[str] = None
    obs: Optional[str] = None
    ativo: bool = True


class ClienteUpdate(BaseModel):
    nome: Optional[str] = Field(default=None, min_length=1)
    grupo: Optional[int] = None
    cgc: Optional[str] = None
    cpf: Optional[str] = None
    endereco: Optional[str] = None
    numero: Optional[int] = None
    complemento: Optional[str] = None
    bairro: Optional[str] = None
    municipio: Optional[str] = None
    estado: Optional[str] = None
    cep: Optional[str] = None
    contato: Optional[str] = None
    email: Optional[str] = None
    telefones: Optional[str] = None
    celular: Optional[str] = None
    whatsapp: Optional[str] = None
    whatsapp1: Optional[str] = None
    whatsapp2: Optional[str] = None
    insc_mun: Optional[str] = None
    insc_est: Optional[str] = None
    obs: Optional[str] = None
    ativo: Optional[bool] = None
```

- [ ] **Step 7: Router de clientes** — crie `backend/app/api/clientes.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Cliente
from app.api.deps import get_current_usuario, require_funcao
from app.api.cadastros_common import excluir_protegido
from app.schemas.clientes import ClienteListOut, ClientesPage, ClienteOut, ClienteCreate, ClienteUpdate

router = APIRouter(prefix="/clientes", tags=["clientes"])
ADMIN = "Administrador"


@router.get("", response_model=ClientesPage)
def listar(
    q: str | None = None,
    offset: int = 0,
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_usuario),
):
    query = db.query(Cliente)
    if q:
        termo = f"%{q}%"
        query = query.filter(
            or_(
                Cliente.nome.ilike(termo),
                Cliente.cgc.ilike(termo),
                Cliente.cpf.ilike(termo),
                Cliente.municipio.ilike(termo),
            )
        )
    total = query.count()
    items = query.order_by(Cliente.nome).offset(offset).limit(limit).all()
    return ClientesPage(items=[ClienteListOut.model_validate(c) for c in items], total=total)


@router.get("/{cliente_id}", response_model=ClienteOut)
def obter(cliente_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    obj = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    return obj


@router.post("", response_model=ClienteOut, status_code=status.HTTP_201_CREATED)
def criar(dados: ClienteCreate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = Cliente(**dados.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/{cliente_id}", response_model=ClienteOut)
def atualizar(cliente_id: int, dados: ClienteUpdate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    for chave, valor in dados.model_dump(exclude_unset=True).items():
        setattr(obj, chave, valor)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{cliente_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(cliente_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    excluir_protegido(db, obj)
```

- [ ] **Step 8: Registrar router** — em `backend/app/main.py`, adicione `clientes` ao `from app.api import ...` e `app.include_router(clientes.router)` (mantendo o existente).

- [ ] **Step 9: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_clientes.py -q` (4 testes), depois a suíte inteira `docker compose exec -T backend python -m pytest -q` (sem regressões).

- [ ] **Step 10: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/app/models/cliente.py backend/app/models/funcionario.py backend/app/models/__init__.py backend/app/schemas/clientes.py backend/app/api/clientes.py backend/app/main.py backend/tests/test_clientes.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): CRUD de clientes com busca/paginacao + guarda de exclusao"
```
Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 2: Backend — funcionários aninhados no cliente

**Files:**
- Modify: `backend/app/schemas/clientes.py`
- Create: `backend/app/api/funcionarios.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_funcionarios.py`

(O modelo `Funcionario` já foi criado na Task 1.)

- [ ] **Step 1: Teste que falha** — crie `backend/tests/test_funcionarios.py`:

```python
def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _cliente(client, h):
    return client.post("/clientes", json={"nome": "Cliente FX"}, headers=h).json()["id"]


def test_funcionarios_listar_de_cliente(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    cid = _cliente(client, h)
    assert client.get(f"/clientes/{cid}/funcionarios", headers=h).json() == []
    assert client.get("/clientes/99999/funcionarios", headers=h).status_code == 404


def test_funcionario_crud_aninhado(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    cid = _cliente(client, h)
    criado = client.post(f"/clientes/{cid}/funcionarios", json={"nome": "Maria", "cargo": "Motorista"}, headers=h)
    assert criado.status_code == 201
    assert criado.json()["cliente"] == cid
    fid = criado.json()["id"]
    assert client.patch(f"/funcionarios/{fid}", json={"cargo": "Supervisora"}, headers=h).json()["cargo"] == "Supervisora"
    assert client.delete(f"/funcionarios/{fid}", headers=h).status_code == 204
    assert client.get(f"/clientes/{cid}/funcionarios", headers=h).json() == []


def test_funcionario_cliente_inexistente_404(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    r = client.post("/clientes/99999/funcionarios", json={"nome": "X"}, headers=h)
    assert r.status_code == 404


def test_funcionarios_write_admin(client, usuario_admin, usuario_comum):
    h = _headers(client, "admin", "senha123")
    cid = _cliente(client, h)
    hc = _headers(client, "comum", "senha123")
    assert client.get(f"/clientes/{cid}/funcionarios", headers=hc).status_code == 200
    assert client.post(f"/clientes/{cid}/funcionarios", json={"nome": "X"}, headers=hc).status_code == 403
    assert client.patch("/funcionarios/1", json={"nome": "X"}, headers=hc).status_code == 403
    assert client.delete("/funcionarios/1", headers=hc).status_code == 403
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_funcionarios.py -q`
Expected: FAIL (404 nas rotas novas).

- [ ] **Step 3: Schemas de funcionário** — adicione ao fim de `backend/app/schemas/clientes.py`:

```python
class FuncionarioOut(BaseModel):
    id: int
    cliente: int
    setor: Optional[int] = None
    matricula: Optional[str] = None
    centro: Optional[str] = None
    nome: Optional[str] = None
    email: Optional[str] = None
    cargo: Optional[str] = None
    admissao: Optional[date] = None
    idade: Optional[int] = None
    sexo: Optional[str] = None
    estado: Optional[str] = None
    cidade: Optional[str] = None
    ativo: bool
    model_config = {"from_attributes": True}


class FuncionarioCreate(BaseModel):
    nome: str = Field(min_length=1)
    setor: Optional[int] = None
    matricula: Optional[str] = None
    centro: Optional[str] = None
    email: Optional[str] = None
    cargo: Optional[str] = None
    admissao: Optional[date] = None
    idade: Optional[int] = None
    sexo: Optional[str] = None
    estado: Optional[str] = None
    cidade: Optional[str] = None
    ativo: bool = True


class FuncionarioUpdate(BaseModel):
    nome: Optional[str] = Field(default=None, min_length=1)
    setor: Optional[int] = None
    matricula: Optional[str] = None
    centro: Optional[str] = None
    email: Optional[str] = None
    cargo: Optional[str] = None
    admissao: Optional[date] = None
    idade: Optional[int] = None
    sexo: Optional[str] = None
    estado: Optional[str] = None
    cidade: Optional[str] = None
    ativo: Optional[bool] = None
```

- [ ] **Step 4: Router de funcionários** — crie `backend/app/api/funcionarios.py` (sem prefixo; caminhos mistos):

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Cliente, Funcionario
from app.api.deps import get_current_usuario, require_funcao
from app.schemas.clientes import FuncionarioOut, FuncionarioCreate, FuncionarioUpdate

router = APIRouter(tags=["funcionarios"])
ADMIN = "Administrador"


def _exige_cliente(db: Session, cliente_id: int) -> None:
    if db.query(Cliente).filter(Cliente.id == cliente_id).first() is None:
        raise HTTPException(status_code=404, detail="cliente não encontrado")


@router.get("/clientes/{cliente_id}/funcionarios", response_model=list[FuncionarioOut])
def listar(cliente_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    _exige_cliente(db, cliente_id)
    return db.query(Funcionario).filter(Funcionario.cliente == cliente_id).order_by(Funcionario.id).all()


@router.post("/clientes/{cliente_id}/funcionarios", response_model=FuncionarioOut, status_code=status.HTTP_201_CREATED)
def criar(cliente_id: int, dados: FuncionarioCreate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    _exige_cliente(db, cliente_id)
    obj = Funcionario(cliente=cliente_id, **dados.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/funcionarios/{item_id}", response_model=FuncionarioOut)
def atualizar(item_id: int, dados: FuncionarioUpdate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(Funcionario).filter(Funcionario.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    for chave, valor in dados.model_dump(exclude_unset=True).items():
        setattr(obj, chave, valor)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/funcionarios/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(Funcionario).filter(Funcionario.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    db.delete(obj)
    db.commit()
```

- [ ] **Step 5: Registrar router** — em `backend/app/main.py`, adicione `funcionarios` ao import e `app.include_router(funcionarios.router)`.

- [ ] **Step 6: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_funcionarios.py -q` (4 testes), depois a suíte inteira (sem regressões).

- [ ] **Step 7: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/app/schemas/clientes.py backend/app/api/funcionarios.py backend/app/main.py backend/tests/test_funcionarios.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): funcionarios aninhados no cliente (CRUD, admin-write)"
```
Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 3: Frontend — módulo de API de clientes

**Files:**
- Create: `frontend/src/app/clientes/api.ts`
- Test: `frontend/src/app/clientes/api.test.ts`

- [ ] **Step 1: Teste que falha** — crie `frontend/src/app/clientes/api.test.ts`:

```ts
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { clientesApi, funcionariosApi } from './api'
import { setTokens } from '../../lib/auth-storage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('clientes/api', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    setTokens({ access_token: 't', refresh_token: 'r' })
  })

  it('listar monta a query string (q/offset/limit)', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ items: [], total: 0 }))
    vi.stubGlobal('fetch', f)
    await clientesApi.listar({ q: 'acme', offset: 25, limit: 25 })
    const url = String(f.mock.calls[0][0])
    expect(url).toContain('/clientes?')
    expect(url).toContain('q=acme')
    expect(url).toContain('offset=25')
    expect(url).toContain('limit=25')
  })

  it('criar faz POST com corpo', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ id: 1, nome: 'ACME', ativo: true }))
    vi.stubGlobal('fetch', f)
    await clientesApi.criar({ nome: 'ACME' } as never)
    expect(f.mock.calls[0][1].method).toBe('POST')
    expect(String(f.mock.calls[0][1].body)).toContain('ACME')
  })

  it('funcionariosApi.criar posta no path do cliente', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ id: 9, cliente: 3, ativo: true }))
    vi.stubGlobal('fetch', f)
    await funcionariosApi.criar(3, { nome: 'Maria' } as never)
    expect(String(f.mock.calls[0][0])).toContain('/clientes/3/funcionarios')
    expect(f.mock.calls[0][1].method).toBe('POST')
  })

  it('excluir propaga ApiError', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ detail: 'registro em uso' }, 409))
    vi.stubGlobal('fetch', f)
    await expect(clientesApi.excluir(5)).rejects.toMatchObject({ status: 409 })
  })
})
```

- [ ] **Step 2: Rodar e ver falhar**

Run (em `frontend/`): `npm run test -- clientes/api`
Expected: FAIL (módulo não existe).

- [ ] **Step 3: Implementar** — crie `frontend/src/app/clientes/api.ts`:

```ts
import { apiJson, apiFetch, ApiError } from '../../lib/api'

export interface ClienteListItem {
  id: number
  nome: string | null
  cgc: string | null
  cpf: string | null
  municipio: string | null
  estado: string | null
  ativo: boolean
}

export interface ClientesPage {
  items: ClienteListItem[]
  total: number
}

export interface Cliente {
  id: number
  grupo: number | null
  nome: string | null
  cgc: string | null
  cpf: string | null
  endereco: string | null
  numero: number | null
  complemento: string | null
  bairro: string | null
  municipio: string | null
  estado: string | null
  cep: string | null
  contato: string | null
  email: string | null
  telefones: string | null
  celular: string | null
  whatsapp: string | null
  whatsapp1: string | null
  whatsapp2: string | null
  insc_mun: string | null
  insc_est: string | null
  datcad: string | null
  obs: string | null
  ativo: boolean
}

export interface ClientePayload {
  nome: string
  grupo: number | null
  cgc: string | null
  cpf: string | null
  endereco: string | null
  numero: number | null
  complemento: string | null
  bairro: string | null
  municipio: string | null
  estado: string | null
  cep: string | null
  contato: string | null
  email: string | null
  telefones: string | null
  celular: string | null
  whatsapp: string | null
  whatsapp1: string | null
  whatsapp2: string | null
  insc_mun: string | null
  insc_est: string | null
  obs: string | null
  ativo: boolean
}

export interface Funcionario {
  id: number
  cliente: number
  setor: number | null
  matricula: string | null
  centro: string | null
  nome: string | null
  email: string | null
  cargo: string | null
  admissao: string | null
  idade: number | null
  sexo: string | null
  estado: string | null
  cidade: string | null
  ativo: boolean
}

export interface FuncionarioPayload {
  nome: string
  matricula: string | null
  cargo: string | null
  setor: number | null
  email: string | null
  admissao: string | null
  ativo: boolean
}

async function apiVoid(path: string, options: RequestInit = {}): Promise<void> {
  const res = await apiFetch(path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers as Record<string, string>) },
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = (await res.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      // sem corpo JSON
    }
    throw new ApiError(res.status, detail)
  }
}

export interface ListarParams {
  q?: string
  offset?: number
  limit?: number
}

export const clientesApi = {
  listar: (params: ListarParams = {}): Promise<ClientesPage> => {
    const sp = new URLSearchParams()
    if (params.q) sp.set('q', params.q)
    sp.set('offset', String(params.offset ?? 0))
    sp.set('limit', String(params.limit ?? 25))
    return apiJson<ClientesPage>(`/clientes?${sp.toString()}`)
  },
  obter: (id: number): Promise<Cliente> => apiJson<Cliente>(`/clientes/${id}`),
  criar: (payload: ClientePayload): Promise<Cliente> => apiJson<Cliente>('/clientes', { method: 'POST', body: JSON.stringify(payload) }),
  atualizar: (id: number, payload: Partial<ClientePayload>): Promise<Cliente> =>
    apiJson<Cliente>(`/clientes/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  excluir: (id: number): Promise<void> => apiVoid(`/clientes/${id}`, { method: 'DELETE' }),
}

export const funcionariosApi = {
  listarPorCliente: (clienteId: number): Promise<Funcionario[]> => apiJson<Funcionario[]>(`/clientes/${clienteId}/funcionarios`),
  criar: (clienteId: number, payload: FuncionarioPayload): Promise<Funcionario> =>
    apiJson<Funcionario>(`/clientes/${clienteId}/funcionarios`, { method: 'POST', body: JSON.stringify(payload) }),
  atualizar: (id: number, payload: Partial<FuncionarioPayload>): Promise<Funcionario> =>
    apiJson<Funcionario>(`/funcionarios/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  excluir: (id: number): Promise<void> => apiVoid(`/funcionarios/${id}`, { method: 'DELETE' }),
}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `npm run test -- clientes/api` (4 testes) e `npx tsc -b`.
Expected: PASS; tsc limpo.

- [ ] **Step 5: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/app/clientes/api.ts frontend/src/app/clientes/api.test.ts
git -C /d/GitHub/GestorHS commit -m "feat(frontend): modulo de API de clientes e funcionarios"
```
Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 4: Frontend — lista de clientes (busca + paginação)

Visual; verificação = tsc + lint.

**Files:**
- Create: `frontend/src/app/clientes/ClientesPage.tsx`

- [ ] **Step 1: Criar a página** — `frontend/src/app/clientes/ClientesPage.tsx`:

```tsx
import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Spinner } from '../../components/ui/Spinner'
import { Input } from '../../components/ui/Input'
import { ApiError } from '../../lib/api'
import { useAuth } from '../../auth/AuthContext'
import { isAdmin } from '../../auth/roles'
import { clientesApi, type ClienteListItem } from './api'

const LIMITE = 25

export function ClientesPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [termo, setTermo] = useState('')
  const [busca, setBusca] = useState('')
  const [offset, setOffset] = useState(0)
  const [itens, setItens] = useState<ClienteListItem[] | null>(null)
  const [total, setTotal] = useState(0)
  const [erro, setErro] = useState('')

  useEffect(() => {
    let ativo = true
    setItens(null)
    setErro('')
    clientesApi
      .listar({ q: busca || undefined, offset, limit: LIMITE })
      // eslint-disable-next-line react-hooks/set-state-in-effect
      .then((p) => {
        if (!ativo) return
        setItens(p.items)
        setTotal(p.total)
      })
      .catch((e) => {
        if (!ativo) return
        setErro(e instanceof ApiError ? e.message : 'Falha ao carregar')
        setItens([])
      })
    return () => {
      ativo = false
    }
  }, [busca, offset])

  function onBuscar(e: FormEvent) {
    e.preventDefault()
    setOffset(0)
    setBusca(termo.trim())
  }

  const inicio = total === 0 ? 0 : offset + 1
  const fim = Math.min(offset + LIMITE, total)

  return (
    <div className="px-4 md:px-6 py-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-extrabold text-slate-100">Clientes</h1>
        {isAdmin(user) && <Button onClick={() => navigate('/app/clientes/novo')}>Novo cliente</Button>}
      </div>

      <form onSubmit={onBuscar} className="flex gap-2 max-w-md">
        <Input id="busca" placeholder="Buscar por nome, CNPJ, CPF ou município" value={termo} onChange={(e) => setTermo(e.target.value)} />
        <Button type="submit" variant="secondary">Buscar</Button>
      </form>

      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}

      {itens === null ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum cliente encontrado.</p>
      ) : (
        <>
          <Table head={<><TH>Nome</TH><TH>CNPJ / CPF</TH><TH>Município/UF</TH><TH>Ativo</TH></>}>
            {itens.map((c) => (
              <tr key={c.id} className="hover:bg-background-elevated transition-colors cursor-pointer" onClick={() => navigate(`/app/clientes/${c.id}`)}>
                <TD>{c.nome ?? '—'}</TD>
                <TD>{c.cgc || c.cpf || '—'}</TD>
                <TD>{[c.municipio, c.estado].filter(Boolean).join(' / ') || '—'}</TD>
                <TD><Badge tone={c.ativo ? 'primary' : 'neutral'}>{c.ativo ? 'Ativo' : 'Inativo'}</Badge></TD>
              </tr>
            ))}
          </Table>
          <div className="flex items-center justify-between text-sm text-slate-400">
            <span>{inicio}–{fim} de {total}</span>
            <div className="flex gap-2">
              <Button variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - LIMITE))}>Anterior</Button>
              <Button variant="secondary" disabled={fim >= total} onClick={() => setOffset(offset + LIMITE)}>Próxima</Button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verificar**

Run: `npx tsc -b` e `npm run lint`. Sem erros (corrija lint mínimo se houver; o `eslint-disable` do set-state-in-effect já está posicionado).

- [ ] **Step 3: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/app/clientes/ClientesPage.tsx
git -C /d/GitHub/GestorHS commit -m "feat(frontend): lista de clientes com busca e paginacao"
```
Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 5: Frontend — seção de funcionários (sub-componente do detalhe)

Visual; verificação = tsc + lint. Construída antes do detalhe para o detalhe poder importá-la.

**Files:**
- Create: `frontend/src/app/clientes/FuncionariosSection.tsx`

- [ ] **Step 1: Criar o componente** — `frontend/src/app/clientes/FuncionariosSection.tsx`:

```tsx
import { useEffect, useState, type FormEvent } from 'react'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Spinner } from '../../components/ui/Spinner'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { ApiError } from '../../lib/api'
import { funcionariosApi, type Funcionario, type FuncionarioPayload } from './api'
import { setoresApi, type Setor } from '../cadastros/api'

const VAZIO: FuncionarioPayload = { nome: '', matricula: null, cargo: null, setor: null, email: null, admissao: null, ativo: true }

export function FuncionariosSection({ clienteId, podeEditar }: { clienteId: number; podeEditar: boolean }) {
  const [itens, setItens] = useState<Funcionario[] | null>(null)
  const [setores, setSetores] = useState<Setor[]>([])
  const [erro, setErro] = useState('')
  const [aberto, setAberto] = useState(false)
  const [editandoId, setEditandoId] = useState<number | null>(null)
  const [form, setForm] = useState<FuncionarioPayload>(VAZIO)
  const [erroForm, setErroForm] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function carregar() {
    setErro('')
    try {
      setItens(await funcionariosApi.listarPorCliente(clienteId))
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao carregar')
      setItens([])
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void carregar()
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void setoresApi.listar().then(setSetores).catch(() => setSetores([]))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clienteId])

  function nomeSetor(id: number | null) {
    return setores.find((s) => s.id === id)?.descricao ?? '—'
  }
  function set<K extends keyof FuncionarioPayload>(chave: K, valor: FuncionarioPayload[K]) {
    setForm((f) => ({ ...f, [chave]: valor }))
  }
  function abrirNovo() {
    setEditandoId(null); setForm(VAZIO); setErroForm(''); setAberto(true)
  }
  function abrirEdicao(fn: Funcionario) {
    setEditandoId(fn.id)
    setForm({ nome: fn.nome ?? '', matricula: fn.matricula, cargo: fn.cargo, setor: fn.setor, email: fn.email, admissao: fn.admissao, ativo: fn.ativo })
    setErroForm(''); setAberto(true)
  }

  async function salvar(e: FormEvent) {
    e.preventDefault(); setErroForm(''); setEnviando(true)
    try {
      if (editandoId !== null) await funcionariosApi.atualizar(editandoId, form)
      else await funcionariosApi.criar(clienteId, form)
      setAberto(false); await carregar()
    } catch (err) {
      setErroForm(err instanceof ApiError ? err.message : 'Falha ao salvar')
    } finally {
      setEnviando(false)
    }
  }

  async function excluir(fn: Funcionario) {
    if (!window.confirm(`Excluir o funcionário "${fn.nome}"?`)) return
    try { await funcionariosApi.excluir(fn.id); await carregar() }
    catch (err) { setErro(err instanceof ApiError ? err.message : 'Falha ao excluir') }
  }

  return (
    <div className="rounded-2xl bg-background-surface border border-border p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-100">Funcionários</h2>
        {podeEditar && <Button onClick={abrirNovo}>Novo funcionário</Button>}
      </div>
      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      {itens === null ? (
        <div className="flex justify-center py-8"><Spinner className="w-6 h-6" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum funcionário.</p>
      ) : (
        <Table head={<><TH>Nome</TH><TH>Cargo</TH><TH>Setor</TH><TH>E-mail</TH>{podeEditar && <TH>Ações</TH>}</>}>
          {itens.map((fn) => (
            <tr key={fn.id} className="hover:bg-background-elevated transition-colors">
              <TD>{fn.nome ?? '—'}</TD>
              <TD>{fn.cargo ?? '—'}</TD>
              <TD>{nomeSetor(fn.setor)}</TD>
              <TD>{fn.email ?? '—'}</TD>
              {podeEditar && (
                <TD>
                  <div className="flex gap-3">
                    <button onClick={() => abrirEdicao(fn)} className="text-xs text-primary hover:underline">Editar</button>
                    <button onClick={() => excluir(fn)} className="text-xs text-danger hover:underline">Excluir</button>
                  </div>
                </TD>
              )}
            </tr>
          ))}
        </Table>
      )}
      {aberto && (
        <Modal
          open
          onClose={() => setAberto(false)}
          title={editandoId !== null ? 'Editar funcionário' : 'Novo funcionário'}
          footer={
            <>
              <button type="button" onClick={() => setAberto(false)} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">Cancelar</button>
              <button type="submit" form="form-func" disabled={enviando} className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all">Salvar</button>
            </>
          }
        >
          <form id="form-func" className="space-y-4" onSubmit={salvar}>
            <Input id="f-nome" label="Nome" value={form.nome} onChange={(e) => set('nome', e.target.value)} required />
            <div className="grid grid-cols-2 gap-3">
              <Input id="f-matricula" label="Matrícula" value={form.matricula ?? ''} onChange={(e) => set('matricula', e.target.value || null)} />
              <Input id="f-cargo" label="Cargo" value={form.cargo ?? ''} onChange={(e) => set('cargo', e.target.value || null)} />
            </div>
            <Select id="f-setor" label="Setor" value={form.setor ? String(form.setor) : ''} onChange={(e) => set('setor', e.target.value ? Number(e.target.value) : null)}>
              <option value="">— sem setor —</option>
              {setores.map((s) => <option key={s.id} value={s.id}>{s.descricao}</option>)}
            </Select>
            <Input id="f-email" label="E-mail" type="email" value={form.email ?? ''} onChange={(e) => set('email', e.target.value || null)} />
            <Input id="f-admissao" label="Admissão" type="date" value={form.admissao ?? ''} onChange={(e) => set('admissao', e.target.value || null)} />
            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input type="checkbox" checked={form.ativo} onChange={(e) => set('ativo', e.target.checked)} className="accent-primary" />
              Ativo
            </label>
            {erroForm && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erroForm}</div>}
          </form>
        </Modal>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verificar**

Run: `npx tsc -b` e `npm run lint`. Sem erros (corrija lint mínimo se houver).

- [ ] **Step 3: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/app/clientes/FuncionariosSection.tsx
git -C /d/GitHub/GestorHS commit -m "feat(frontend): secao de funcionarios do cliente"
```
Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 6: Frontend — página de detalhe/edição do cliente

Visual; verificação = tsc + lint.

**Files:**
- Create: `frontend/src/app/clientes/ClienteDetailPage.tsx`

- [ ] **Step 1: Criar a página** — `frontend/src/app/clientes/ClienteDetailPage.tsx`:

```tsx
import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Spinner } from '../../components/ui/Spinner'
import { ApiError } from '../../lib/api'
import { useAuth } from '../../auth/AuthContext'
import { isAdmin } from '../../auth/roles'
import { clientesApi, type ClientePayload } from './api'
import { gruposApi, type Grupo } from '../cadastros/api'
import { FuncionariosSection } from './FuncionariosSection'

const VAZIO: ClientePayload = {
  nome: '', grupo: null, cgc: null, cpf: null, endereco: null, numero: null, complemento: null,
  bairro: null, municipio: null, estado: null, cep: null, contato: null, email: null, telefones: null,
  celular: null, whatsapp: null, whatsapp1: null, whatsapp2: null, insc_mun: null, insc_est: null,
  obs: null, ativo: true,
}

function Secao({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <div className="rounded-2xl bg-background-surface border border-border p-5 space-y-4">
      <h2 className="text-sm font-semibold text-slate-100">{titulo}</h2>
      {children}
    </div>
  )
}

export function ClienteDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const editando = id !== undefined
  const podeEditar = isAdmin(user)

  const [form, setForm] = useState<ClientePayload>(VAZIO)
  const [grupos, setGrupos] = useState<Grupo[]>([])
  const [carregando, setCarregando] = useState(editando)
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void gruposApi.listar().then(setGrupos).catch(() => setGrupos([]))
  }, [])

  useEffect(() => {
    if (!editando) return
    let ativo = true
    clientesApi
      .obter(Number(id))
      .then((c) => {
        if (!ativo) return
        setForm({
          nome: c.nome ?? '', grupo: c.grupo, cgc: c.cgc, cpf: c.cpf, endereco: c.endereco, numero: c.numero,
          complemento: c.complemento, bairro: c.bairro, municipio: c.municipio, estado: c.estado, cep: c.cep,
          contato: c.contato, email: c.email, telefones: c.telefones, celular: c.celular, whatsapp: c.whatsapp,
          whatsapp1: c.whatsapp1, whatsapp2: c.whatsapp2, insc_mun: c.insc_mun, insc_est: c.insc_est, obs: c.obs, ativo: c.ativo,
        })
      })
      .catch((e) => {
        if (ativo) setErro(e instanceof ApiError ? e.message : 'Falha ao carregar')
      })
      // eslint-disable-next-line react-hooks/set-state-in-effect
      .finally(() => {
        if (ativo) setCarregando(false)
      })
    return () => {
      ativo = false
    }
  }, [id, editando])

  function set<K extends keyof ClientePayload>(chave: K, valor: ClientePayload[K]) {
    setForm((f) => ({ ...f, [chave]: valor }))
  }

  async function salvar(e: FormEvent) {
    e.preventDefault(); setErro(''); setEnviando(true)
    try {
      if (editando) {
        await clientesApi.atualizar(Number(id), form)
      } else {
        const novo = await clientesApi.criar(form)
        navigate(`/app/clientes/${novo.id}`, { replace: true })
        return
      }
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao salvar')
    } finally {
      setEnviando(false)
    }
  }

  if (carregando) {
    return <div className="flex justify-center py-16"><Spinner className="w-8 h-8" /></div>
  }

  const ro = !podeEditar
  const txt = (label: string, chave: keyof ClientePayload) => (
    <Input
      id={`c-${chave}`}
      label={label}
      value={(form[chave] as string | null) ?? ''}
      onChange={(e) => set(chave, (e.target.value || null) as ClientePayload[typeof chave])}
      disabled={ro}
    />
  )

  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-3xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-extrabold text-slate-100">{editando ? (form.nome || 'Cliente') : 'Novo cliente'}</h1>
        <Button variant="secondary" onClick={() => navigate('/app/clientes')}>Voltar</Button>
      </div>

      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}

      <form className="space-y-6" onSubmit={salvar}>
        <Secao titulo="Identificação">
          <Input id="c-nome" label="Nome" value={form.nome} onChange={(e) => set('nome', e.target.value)} required disabled={ro} />
          <div className="grid grid-cols-2 gap-3">
            <Select id="c-grupo" label="Grupo" value={form.grupo ? String(form.grupo) : ''} onChange={(e) => set('grupo', e.target.value ? Number(e.target.value) : null)} disabled={ro}>
              <option value="">— sem grupo —</option>
              {grupos.map((g) => <option key={g.id} value={g.id}>{g.descricao}</option>)}
            </Select>
            <label className="flex items-center gap-2 text-sm text-slate-300 mt-6">
              <input type="checkbox" checked={form.ativo} onChange={(e) => set('ativo', e.target.checked)} disabled={ro} className="accent-primary" />
              Ativo
            </label>
          </div>
          <div className="grid grid-cols-2 gap-3">{txt('CNPJ', 'cgc')}{txt('CPF', 'cpf')}</div>
          <div className="grid grid-cols-2 gap-3">{txt('Inscrição municipal', 'insc_mun')}{txt('Inscrição estadual', 'insc_est')}</div>
        </Secao>

        <Secao titulo="Endereço">
          {txt('Logradouro', 'endereco')}
          <div className="grid grid-cols-2 gap-3">
            <Input id="c-numero" label="Número" type="number" value={form.numero != null ? String(form.numero) : ''} onChange={(e) => set('numero', e.target.value ? Number(e.target.value) : null)} disabled={ro} />
            {txt('Complemento', 'complemento')}
          </div>
          <div className="grid grid-cols-2 gap-3">{txt('Bairro', 'bairro')}{txt('CEP', 'cep')}</div>
          <div className="grid grid-cols-2 gap-3">{txt('Município', 'municipio')}{txt('UF', 'estado')}</div>
        </Secao>

        <Secao titulo="Contatos">
          <div className="grid grid-cols-2 gap-3">{txt('Contato', 'contato')}{txt('E-mail', 'email')}</div>
          <div className="grid grid-cols-2 gap-3">{txt('Telefones', 'telefones')}{txt('Celular', 'celular')}</div>
          <div className="grid grid-cols-3 gap-3">{txt('WhatsApp', 'whatsapp')}{txt('WhatsApp 2', 'whatsapp1')}{txt('WhatsApp 3', 'whatsapp2')}</div>
        </Secao>

        <Secao titulo="Observações">
          <textarea
            value={form.obs ?? ''}
            onChange={(e) => set('obs', e.target.value || null)}
            disabled={ro}
            rows={3}
            className="w-full text-sm text-slate-200 bg-background-elevated border border-border rounded-lg px-3 py-2.5 resize-none focus:outline-none focus:ring-2 focus:ring-primary/40 placeholder-slate-500 leading-relaxed disabled:opacity-60"
          />
        </Secao>

        {podeEditar && (
          <button type="submit" disabled={enviando} className="w-full py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-60 transition-all">
            {editando ? 'Salvar alterações' : 'Criar cliente'}
          </button>
        )}
      </form>

      {editando && <FuncionariosSection clienteId={Number(id)} podeEditar={podeEditar} />}
    </div>
  )
}
```

- [ ] **Step 2: Verificar**

Run: `npx tsc -b` e `npm run lint`. Sem erros (corrija lint mínimo se houver).

- [ ] **Step 3: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/app/clientes/ClienteDetailPage.tsx
git -C /d/GitHub/GestorHS commit -m "feat(frontend): pagina de detalhe/edicao do cliente (form em secoes + funcionarios)"
```
Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 7: Frontend — nav + rotas + integração

**Files:**
- Modify: `frontend/src/components/ui/icons.tsx` (adiciona `IconClientes`)
- Modify: `frontend/src/layout/Sidebar.tsx` (item de nav, sem `adminOnly`)
- Modify: `frontend/src/app/routes.tsx` (rotas)

- [ ] **Step 1: Ícone** — adicione ao fim de `frontend/src/components/ui/icons.tsx`:

```tsx
export function IconClientes({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a4 4 0 00-3-3.87M9 20H4v-2a4 4 0 013-3.87m3.5-2.13a4 4 0 10-3-7.74 4 4 0 003 7.74zm6 0a4 4 0 10-3-7.74" />
    </svg>
  )
}
```

- [ ] **Step 2: Nav** — em `frontend/src/layout/Sidebar.tsx`, adicione `IconClientes` ao import de ícones e inclua no `NAV_ITEMS` (depois de "Cadastros"), **sem** `adminOnly` (visível a todos os internos):

```tsx
  { label: 'Clientes', icon: <IconClientes />, to: '/app/clientes' },
```

- [ ] **Step 3: Rotas** — em `frontend/src/app/routes.tsx`, importe as páginas e adicione as rotas dentro de `<Routes>` (a estática `novo` antes da dinâmica `:id`):

```tsx
import { ClientesPage } from './clientes/ClientesPage'
import { ClienteDetailPage } from './clientes/ClienteDetailPage'
```
```tsx
        <Route path="clientes" element={<ClientesPage />} />
        <Route path="clientes/novo" element={<ClienteDetailPage />} />
        <Route path="clientes/:id" element={<ClienteDetailPage />} />
```

- [ ] **Step 4: Verificar tudo**

Run (em `frontend/`): `npm run test`, `npx tsc -b`, `npm run lint`, `npm run build`.
Expected: testes verdes (incl. clientes/api), tsc/lint limpos, build OK. Cole a lista de assets do build.

- [ ] **Step 5: Verificação manual E2E** (backend `docker compose up -d`; admin `admin`/`GestorHS@2026`; `frontend/.env` com `VITE_API_URL=http://localhost:8000`)

`npm run dev` e abra a URL. Verifique:
1. Admin loga → Sidebar mostra "Clientes" → lista carrega (dados reais), busca por nome filtra, paginação navega ("X–Y de N").
2. Abrir um cliente → detalhe com os campos preenchidos em seções; editar um campo e salvar reflete.
3. "Novo cliente" → criar → navega para o detalhe do novo; adicionar um funcionário no detalhe; editar/excluir funcionário.
4. Excluir um cliente que tenha funcionário → erro "registro em uso" (409).
5. (Se houver um usuário não-admin) logar como ele → "Clientes" aparece, lista/detalhe abrem em **modo leitura** (sem "Novo cliente", campos desabilitados, sem salvar).

- [ ] **Step 6: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/components/ui/icons.tsx frontend/src/layout/Sidebar.tsx frontend/src/app/routes.tsx
git -C /d/GitHub/GestorHS commit -m "feat(frontend): nav Clientes + rotas (lista, novo, detalhe)"
```
Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

## Notas para o executor

- **Backend no container:** `docker compose up -d` antes dos `pytest`. FK do SQLite ligado (PRAGMA da Fase 1B) — o teste de delete-cliente-em-uso depende disso.
- **`models/__init__.py`** reescrito na Task 1 (acrescenta Cliente, Funcionario). Estado final exporta as 10 entidades.
- **`main.py`** ganha `include_router(clientes.router)` (Task 1) e `include_router(funcionarios.router)` (Task 2), além do existente.
- **Roteamento:** registre `clientes/novo` **antes** de `clientes/:id` (o react-router v7 prioriza estática, mas mantenha a ordem por clareza). `ClienteDetailPage` distingue criar (sem `:id`) de editar (`useParams().id` definido).
- **Leitura para não-admin:** o detalhe abre com `disabled` nos campos e sem botões de escrita quando `!isAdmin`; a API impõe 403 de qualquer modo.
- **Reúso:** `gruposApi`/`setoresApi` vêm de `app/cadastros/api.ts`; `isAdmin` de `app/../auth/roles`. Não refatoramos código existente.
- **`react-hooks/set-state-in-effect`:** os `eslint-disable-next-line` nos efeitos de fetch seguem o padrão aceito do projeto; se a regra não disparar numa linha (gerando "unused directive"), remova só aquele comentário para manter o lint 0-warnings.
