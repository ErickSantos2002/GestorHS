# Fase 1B (Cadastros de referência) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CRUD dos dados-mestre de referência (setores, marcas, grupos, categorias, catálogo de equipamentos) — leitura para qualquer interno, escrita só Administrador — numa página única "Cadastros" com abas.

**Architecture:** Backend FastAPI + SQLAlchemy 2 + Pydantic v2: um router explícito por entidade (read via `get_current_usuario`, write via `require_funcao("Administrador")`), com exclusão protegida por FK (IntegrityError → 409). Frontend React 19 reusa o design system; um `crudClient` genérico tipado + hook `useCrud` cortam a repetição, com painéis por entidade dentro de uma página com abas. TDD no backend (pytest, SQLite com FK habilitado) e na lógica do frontend (Vitest+RTL).

**Tech Stack:** FastAPI, SQLAlchemy 2, Pydantic v2, pytest; React 19, TypeScript, Vite 8, react-router-dom 7, Vitest + RTL.

**Referências:**
- Spec: `docs/superpowers/specs/2026-06-03-fase1b-cadastros-referencia-design.md`
- Deps existentes: `app/api/deps.py` → `get_current_usuario` (qualquer interno; 401 sem token) e `require_funcao("Administrador")` (retorna o usuário; 403 se função não bate).
- Tabelas (já no banco): `setores(id,descricao)`, `marcas(id,descricao,imagem)`, `grupos(id,descricao,texto)`, `categorias(id,setor→setores,posicao,descricao)`, `equipamentos(id,categoria→categorias,marca→marcas,descricao,detalhes,especificacao,preco_cod,preco_por,custo,peso_calibragem,peso,imagem,estoque,estoque_min,ativo,destaque,datacad)`.

**Convenções de teste (backend):** `tests/conftest.py` provê `db_session` (SQLite in-memory), `client`, `usuario_admin` (`admin`/`senha123`), `usuario_comum` (`comum`/`senha123`). `_headers(client, login, senha)` já existe em `tests/test_acesso.py` — para os novos testes, redefina o helper localmente em cada arquivo de teste novo. Rode no container, da raiz `d:\GitHub\GestorHS`: `docker compose exec -T backend python -m pytest <args>` (garanta `docker compose up -d`).

**Convenções TS (frontend):** `verbatimModuleSyntax` (use `import { type X }`), `noUnusedLocals`/`noUnusedParameters`. npm da pasta `frontend/`; git via `git -C /d/GitHub/GestorHS`. Lint baseline limpo.

**Branch:** rode tudo em `feat/fase1b-cadastros`. Antes da Task 1:
```bash
git -C /d/GitHub/GestorHS checkout -b feat/fase1b-cadastros
```

---

### Task 1: Helper de exclusão + FK no SQLite de teste + entidade Setor (padrão completo)

Estabelece o padrão: modelo, schemas, router (read/write split), helper de exclusão protegida, e habilita FK no SQLite dos testes.

**Files:**
- Modify: `backend/tests/conftest.py` (PRAGMA foreign_keys=ON)
- Create: `backend/app/models/setor.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/app/schemas/cadastros.py`
- Create: `backend/app/api/cadastros_common.py`
- Create: `backend/app/api/setores.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_cadastros_setores.py`

- [ ] **Step 1: Habilitar FK no engine de teste** — em `backend/tests/conftest.py`, adicione `event` ao import do sqlalchemy e registre o PRAGMA logo após criar o engine no fixture `db_session`. O topo do arquivo passa a importar:

```python
from sqlalchemy import create_engine, event
```

E dentro de `db_session`, logo após `engine = create_engine(...)` e antes de `TestingSessionLocal = ...`:

```python
    @event.listens_for(engine, "connect")
    def _set_sqlite_fk(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
```

- [ ] **Step 2: Teste que falha** — crie `backend/tests/test_cadastros_setores.py`:

```python
def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def test_listar_setores_qualquer_interno(client, usuario_comum):
    r = client.get("/setores", headers=_headers(client, "comum", "senha123"))
    assert r.status_code == 200
    assert r.json() == []


def test_criar_setor_exige_admin(client, usuario_comum):
    r = client.post("/setores", json={"descricao": "Laboratório"}, headers=_headers(client, "comum", "senha123"))
    assert r.status_code == 403


def test_crud_setor_admin(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    criado = client.post("/setores", json={"descricao": "Expedição"}, headers=h)
    assert criado.status_code == 201
    sid = criado.json()["id"]
    assert client.get(f"/setores/{sid}", headers=h).json()["descricao"] == "Expedição"
    assert client.patch(f"/setores/{sid}", json={"descricao": "Expedição 2"}, headers=h).json()["descricao"] == "Expedição 2"
    assert client.get("/setores/99999", headers=h).status_code == 404
    assert client.delete(f"/setores/{sid}", headers=h).status_code == 204
    assert client.get(f"/setores/{sid}", headers=h).status_code == 404


def test_excluir_setor_em_uso_409(client, usuario_admin, db_session):
    from app.models import Setor, Categoria
    s = Setor(descricao="Em uso")
    db_session.add(s)
    db_session.flush()
    db_session.add(Categoria(descricao="Cat", setor=s.id, posicao=0))
    db_session.commit()
    r = client.delete(f"/setores/{s.id}", headers=_headers(client, "admin", "senha123"))
    assert r.status_code == 409
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_cadastros_setores.py -q`
Expected: FAIL (404 — `/setores` não existe; import de `Setor`/`Categoria` falha).

- [ ] **Step 4: Modelo Setor** — crie `backend/app/models/setor.py`:

```python
from sqlalchemy import Column, Integer, String
from app.models.database import Base


class Setor(Base):
    __tablename__ = "setores"

    id = Column(Integer, primary_key=True, index=True)
    descricao = Column(String(200), nullable=False)
```

- [ ] **Step 5: Modelo Categoria** (necessário já para o teste de FK; o router de categorias vem na Task 4) — crie `backend/app/models/categoria.py`:

```python
from sqlalchemy import Column, Integer, String, ForeignKey
from app.models.database import Base


class Categoria(Base):
    __tablename__ = "categorias"

    id = Column(Integer, primary_key=True, index=True)
    setor = Column(Integer, ForeignKey("setores.id"), nullable=True)
    posicao = Column(Integer, nullable=False, default=0)
    descricao = Column(String(200), nullable=True)
```

- [ ] **Step 6: Registrar modelos** — substitua `backend/app/models/__init__.py`:

```python
from app.models.funcao import Funcao
from app.models.usuario import Usuario
from app.models.usuario_cliente import UsuarioCliente
from app.models.setor import Setor
from app.models.categoria import Categoria

__all__ = ["Funcao", "Usuario", "UsuarioCliente", "Setor", "Categoria"]
```

- [ ] **Step 7: Schemas** — crie `backend/app/schemas/cadastros.py`:

```python
from pydantic import BaseModel, Field
from typing import Optional


class SetorOut(BaseModel):
    id: int
    descricao: str
    model_config = {"from_attributes": True}


class SetorCreate(BaseModel):
    descricao: str = Field(min_length=1)


class SetorUpdate(BaseModel):
    descricao: Optional[str] = Field(default=None, min_length=1)
```

- [ ] **Step 8: Helper de exclusão protegida** — crie `backend/app/api/cadastros_common.py`:

```python
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def excluir_protegido(db: Session, obj) -> None:
    """Exclui o objeto; se houver FK referenciando-o, devolve 409."""
    try:
        db.delete(obj)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="registro em uso")
```

- [ ] **Step 9: Router de setores** — crie `backend/app/api/setores.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Setor
from app.api.deps import get_current_usuario, require_funcao
from app.api.cadastros_common import excluir_protegido
from app.schemas.cadastros import SetorOut, SetorCreate, SetorUpdate

router = APIRouter(prefix="/setores", tags=["setores"])
ADMIN = "Administrador"


@router.get("", response_model=list[SetorOut])
def listar(db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    return db.query(Setor).order_by(Setor.id).all()


@router.get("/{item_id}", response_model=SetorOut)
def obter(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    obj = db.query(Setor).filter(Setor.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    return obj


@router.post("", response_model=SetorOut, status_code=status.HTTP_201_CREATED)
def criar(dados: SetorCreate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = Setor(descricao=dados.descricao)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/{item_id}", response_model=SetorOut)
def atualizar(item_id: int, dados: SetorUpdate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(Setor).filter(Setor.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    for chave, valor in dados.model_dump(exclude_unset=True).items():
        setattr(obj, chave, valor)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(Setor).filter(Setor.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    excluir_protegido(db, obj)
```

- [ ] **Step 10: Registrar o router** — em `backend/app/main.py`, importe e inclua `setores` (mantendo CORS, `/health` e os routers existentes `auth, funcoes, usuarios`):

```python
from app.api import auth, funcoes, usuarios, setores
```
e após os includes existentes:
```python
app.include_router(setores.router)
```

- [ ] **Step 11: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_cadastros_setores.py -q`
Expected: PASS (4 testes). Rode também a suíte inteira: `docker compose exec -T backend python -m pytest -q` (sem regressões).

- [ ] **Step 12: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/tests/conftest.py backend/app/models/setor.py backend/app/models/categoria.py backend/app/models/__init__.py backend/app/schemas/cadastros.py backend/app/api/cadastros_common.py backend/app/api/setores.py backend/app/main.py backend/tests/test_cadastros_setores.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): cadastro de setores (read interno, write admin) + guarda de exclusao FK"
```
Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 2: Marcas e Grupos

**Files:**
- Create: `backend/app/models/marca.py`, `backend/app/models/grupo.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/schemas/cadastros.py`
- Create: `backend/app/api/marcas.py`, `backend/app/api/grupos.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_cadastros_marcas_grupos.py`

- [ ] **Step 1: Teste que falha** — crie `backend/tests/test_cadastros_marcas_grupos.py`:

```python
def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def test_marcas_read_interno_write_admin(client, usuario_admin, usuario_comum):
    assert client.get("/marcas", headers=_headers(client, "comum", "senha123")).status_code == 200
    assert client.post("/marcas", json={"descricao": "X"}, headers=_headers(client, "comum", "senha123")).status_code == 403
    h = _headers(client, "admin", "senha123")
    mid = client.post("/marcas", json={"descricao": "Dräger"}, headers=h).json()["id"]
    assert client.patch(f"/marcas/{mid}", json={"descricao": "Drager"}, headers=h).json()["descricao"] == "Drager"
    assert client.delete(f"/marcas/{mid}", headers=h).status_code == 204


def test_grupos_crud_com_texto(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    criado = client.post("/grupos", json={"descricao": "VIP", "texto": "clientes preferenciais"}, headers=h)
    assert criado.status_code == 201
    gid = criado.json()["id"]
    assert criado.json()["texto"] == "clientes preferenciais"
    assert client.patch(f"/grupos/{gid}", json={"texto": "atualizado"}, headers=h).json()["texto"] == "atualizado"
    assert client.delete(f"/grupos/{gid}", headers=h).status_code == 204
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_cadastros_marcas_grupos.py -q`
Expected: FAIL (404).

- [ ] **Step 3: Modelos** — crie `backend/app/models/marca.py`:

```python
from sqlalchemy import Column, Integer, String
from app.models.database import Base


class Marca(Base):
    __tablename__ = "marcas"

    id = Column(Integer, primary_key=True, index=True)
    descricao = Column(String(100), nullable=False)
    imagem = Column(String(50), nullable=True)
```

E `backend/app/models/grupo.py`:

```python
from sqlalchemy import Column, Integer, String, Text
from app.models.database import Base


class Grupo(Base):
    __tablename__ = "grupos"

    id = Column(Integer, primary_key=True, index=True)
    descricao = Column(String(200), nullable=False)
    texto = Column(Text, nullable=True)
```

- [ ] **Step 4: Registrar modelos** — substitua `backend/app/models/__init__.py`:

```python
from app.models.funcao import Funcao
from app.models.usuario import Usuario
from app.models.usuario_cliente import UsuarioCliente
from app.models.setor import Setor
from app.models.categoria import Categoria
from app.models.marca import Marca
from app.models.grupo import Grupo

__all__ = ["Funcao", "Usuario", "UsuarioCliente", "Setor", "Categoria", "Marca", "Grupo"]
```

- [ ] **Step 5: Schemas** — adicione ao fim de `backend/app/schemas/cadastros.py`:

```python
class MarcaOut(BaseModel):
    id: int
    descricao: str
    imagem: Optional[str] = None
    model_config = {"from_attributes": True}


class MarcaCreate(BaseModel):
    descricao: str = Field(min_length=1)


class MarcaUpdate(BaseModel):
    descricao: Optional[str] = Field(default=None, min_length=1)


class GrupoOut(BaseModel):
    id: int
    descricao: str
    texto: Optional[str] = None
    model_config = {"from_attributes": True}


class GrupoCreate(BaseModel):
    descricao: str = Field(min_length=1)
    texto: Optional[str] = None


class GrupoUpdate(BaseModel):
    descricao: Optional[str] = Field(default=None, min_length=1)
    texto: Optional[str] = None
```

- [ ] **Step 6: Router de marcas** — crie `backend/app/api/marcas.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Marca
from app.api.deps import get_current_usuario, require_funcao
from app.api.cadastros_common import excluir_protegido
from app.schemas.cadastros import MarcaOut, MarcaCreate, MarcaUpdate

router = APIRouter(prefix="/marcas", tags=["marcas"])
ADMIN = "Administrador"


@router.get("", response_model=list[MarcaOut])
def listar(db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    return db.query(Marca).order_by(Marca.id).all()


@router.get("/{item_id}", response_model=MarcaOut)
def obter(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    obj = db.query(Marca).filter(Marca.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    return obj


@router.post("", response_model=MarcaOut, status_code=status.HTTP_201_CREATED)
def criar(dados: MarcaCreate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = Marca(descricao=dados.descricao)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/{item_id}", response_model=MarcaOut)
def atualizar(item_id: int, dados: MarcaUpdate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(Marca).filter(Marca.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    for chave, valor in dados.model_dump(exclude_unset=True).items():
        setattr(obj, chave, valor)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(Marca).filter(Marca.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    excluir_protegido(db, obj)
```

- [ ] **Step 7: Router de grupos** — crie `backend/app/api/grupos.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Grupo
from app.api.deps import get_current_usuario, require_funcao
from app.api.cadastros_common import excluir_protegido
from app.schemas.cadastros import GrupoOut, GrupoCreate, GrupoUpdate

router = APIRouter(prefix="/grupos", tags=["grupos"])
ADMIN = "Administrador"


@router.get("", response_model=list[GrupoOut])
def listar(db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    return db.query(Grupo).order_by(Grupo.id).all()


@router.get("/{item_id}", response_model=GrupoOut)
def obter(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    obj = db.query(Grupo).filter(Grupo.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    return obj


@router.post("", response_model=GrupoOut, status_code=status.HTTP_201_CREATED)
def criar(dados: GrupoCreate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = Grupo(descricao=dados.descricao, texto=dados.texto)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/{item_id}", response_model=GrupoOut)
def atualizar(item_id: int, dados: GrupoUpdate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(Grupo).filter(Grupo.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    for chave, valor in dados.model_dump(exclude_unset=True).items():
        setattr(obj, chave, valor)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(Grupo).filter(Grupo.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    excluir_protegido(db, obj)
```

- [ ] **Step 8: Registrar routers** — em `backend/app/main.py`, adicione `marcas, grupos` ao import de `app.api` e inclua ambos:

```python
from app.api import auth, funcoes, usuarios, setores, marcas, grupos
```
```python
app.include_router(marcas.router)
app.include_router(grupos.router)
```

- [ ] **Step 9: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_cadastros_marcas_grupos.py -q`
Expected: PASS (2 testes). Suíte inteira sem regressão.

- [ ] **Step 10: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/app/models/marca.py backend/app/models/grupo.py backend/app/models/__init__.py backend/app/schemas/cadastros.py backend/app/api/marcas.py backend/app/api/grupos.py backend/app/main.py backend/tests/test_cadastros_marcas_grupos.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): cadastros de marcas e grupos"
```
Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 3: Categorias (FK setor)

**Files:**
- Modify: `backend/app/schemas/cadastros.py`
- Create: `backend/app/api/categorias.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_cadastros_categorias.py`

(O modelo `Categoria` já foi criado na Task 1.)

- [ ] **Step 1: Teste que falha** — crie `backend/tests/test_cadastros_categorias.py`:

```python
def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def test_categorias_read_interno_write_admin(client, usuario_admin, usuario_comum):
    assert client.get("/categorias", headers=_headers(client, "comum", "senha123")).status_code == 200
    assert client.post("/categorias", json={"descricao": "X"}, headers=_headers(client, "comum", "senha123")).status_code == 403


def test_categoria_crud_com_setor(client, usuario_admin, db_session):
    from app.models import Setor
    s = Setor(descricao="Lab")
    db_session.add(s)
    db_session.commit()
    h = _headers(client, "admin", "senha123")
    criado = client.post("/categorias", json={"descricao": "Bafômetros", "setor": s.id, "posicao": 2}, headers=h)
    assert criado.status_code == 201
    cid = criado.json()["id"]
    assert criado.json()["setor"] == s.id
    assert criado.json()["posicao"] == 2
    assert client.patch(f"/categorias/{cid}", json={"descricao": "Bafômetros PRO"}, headers=h).json()["descricao"] == "Bafômetros PRO"
    assert client.delete(f"/categorias/{cid}", headers=h).status_code == 204
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_cadastros_categorias.py -q`
Expected: FAIL (404).

- [ ] **Step 3: Schemas** — adicione ao fim de `backend/app/schemas/cadastros.py`:

```python
class CategoriaOut(BaseModel):
    id: int
    descricao: Optional[str] = None
    setor: Optional[int] = None
    posicao: int
    model_config = {"from_attributes": True}


class CategoriaCreate(BaseModel):
    descricao: str = Field(min_length=1)
    setor: Optional[int] = None
    posicao: int = 0


class CategoriaUpdate(BaseModel):
    descricao: Optional[str] = Field(default=None, min_length=1)
    setor: Optional[int] = None
    posicao: Optional[int] = None
```

- [ ] **Step 4: Router** — crie `backend/app/api/categorias.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Categoria
from app.api.deps import get_current_usuario, require_funcao
from app.api.cadastros_common import excluir_protegido
from app.schemas.cadastros import CategoriaOut, CategoriaCreate, CategoriaUpdate

router = APIRouter(prefix="/categorias", tags=["categorias"])
ADMIN = "Administrador"


@router.get("", response_model=list[CategoriaOut])
def listar(db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    return db.query(Categoria).order_by(Categoria.posicao, Categoria.id).all()


@router.get("/{item_id}", response_model=CategoriaOut)
def obter(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    obj = db.query(Categoria).filter(Categoria.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    return obj


@router.post("", response_model=CategoriaOut, status_code=status.HTTP_201_CREATED)
def criar(dados: CategoriaCreate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = Categoria(descricao=dados.descricao, setor=dados.setor, posicao=dados.posicao)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/{item_id}", response_model=CategoriaOut)
def atualizar(item_id: int, dados: CategoriaUpdate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(Categoria).filter(Categoria.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    for chave, valor in dados.model_dump(exclude_unset=True).items():
        setattr(obj, chave, valor)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(Categoria).filter(Categoria.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    excluir_protegido(db, obj)
```

- [ ] **Step 5: Registrar** — em `backend/app/main.py`, adicione `categorias` ao import e inclua `app.include_router(categorias.router)`.

- [ ] **Step 6: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_cadastros_categorias.py -q`
Expected: PASS (2 testes). Suíte inteira sem regressão.

- [ ] **Step 7: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/app/schemas/cadastros.py backend/app/api/categorias.py backend/app/main.py backend/tests/test_cadastros_categorias.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): cadastro de categorias (FK setor)"
```
Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 4: Catálogo de equipamentos (FKs categoria + marca)

**Files:**
- Create: `backend/app/models/equipamento.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/schemas/cadastros.py`
- Create: `backend/app/api/equipamentos.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_cadastros_equipamentos.py`

- [ ] **Step 1: Teste que falha** — crie `backend/tests/test_cadastros_equipamentos.py`:

```python
def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def test_equipamentos_read_interno_write_admin(client, usuario_admin, usuario_comum):
    assert client.get("/equipamentos", headers=_headers(client, "comum", "senha123")).status_code == 200
    assert client.post("/equipamentos", json={"descricao": "X"}, headers=_headers(client, "comum", "senha123")).status_code == 403


def test_equipamento_crud_com_fks(client, usuario_admin, db_session):
    from app.models import Marca, Categoria
    m = Marca(descricao="Dräger")
    c = Categoria(descricao="Bafômetros", posicao=0)
    db_session.add_all([m, c])
    db_session.commit()
    h = _headers(client, "admin", "senha123")
    corpo = {"descricao": "Alcotest 6820", "categoria": c.id, "marca": m.id, "preco_por": 1500.50, "estoque": 3, "ativo": True}
    criado = client.post("/equipamentos", json=corpo, headers=h)
    assert criado.status_code == 201
    eid = criado.json()["id"]
    assert criado.json()["marca"] == m.id and criado.json()["ativo"] is True
    assert float(criado.json()["preco_por"]) == 1500.50
    assert client.patch(f"/equipamentos/{eid}", json={"estoque": 5}, headers=h).json()["estoque"] == 5
    assert client.delete(f"/equipamentos/{eid}", headers=h).status_code == 204


def test_excluir_marca_em_uso_409(client, usuario_admin, db_session):
    from app.models import Marca, Equipamento
    m = Marca(descricao="Em uso")
    db_session.add(m)
    db_session.flush()
    db_session.add(Equipamento(descricao="Eq", marca=m.id))
    db_session.commit()
    r = client.delete(f"/marcas/{m.id}", headers=_headers(client, "admin", "senha123"))
    assert r.status_code == 409


def test_excluir_categoria_em_uso_409(client, usuario_admin, db_session):
    from app.models import Categoria, Equipamento
    c = Categoria(descricao="Em uso", posicao=0)
    db_session.add(c)
    db_session.flush()
    db_session.add(Equipamento(descricao="Eq", categoria=c.id))
    db_session.commit()
    r = client.delete(f"/categorias/{c.id}", headers=_headers(client, "admin", "senha123"))
    assert r.status_code == 409
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_cadastros_equipamentos.py -q`
Expected: FAIL (404 / import de `Equipamento` falha).

- [ ] **Step 3: Modelo** — crie `backend/app/models/equipamento.py`:

```python
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, Numeric, Date
from app.models.database import Base


class Equipamento(Base):
    __tablename__ = "equipamentos"

    id = Column(Integer, primary_key=True, index=True)
    categoria = Column(Integer, ForeignKey("categorias.id"), nullable=True)
    marca = Column(Integer, ForeignKey("marcas.id"), nullable=True)
    descricao = Column(String(100), nullable=True)
    detalhes = Column(Text, nullable=True)
    especificacao = Column(Text, nullable=True)
    preco_cod = Column(Numeric(10, 2), nullable=False, default=0)
    preco_por = Column(Numeric(10, 2), nullable=False, default=0)
    custo = Column(Numeric(10, 2), nullable=False, default=0)
    peso_calibragem = Column(Numeric(10, 3), nullable=False, default=0)
    peso = Column(Numeric(10, 3), nullable=False, default=0)
    imagem = Column(String(50), nullable=True)
    estoque = Column(Integer, nullable=False, default=0)
    estoque_min = Column(Integer, nullable=False, default=0)
    ativo = Column(Boolean, nullable=False, default=False)
    destaque = Column(Boolean, nullable=False, default=False)
    datacad = Column(Date, nullable=True)
```

- [ ] **Step 4: Registrar modelo** — substitua `backend/app/models/__init__.py`:

```python
from app.models.funcao import Funcao
from app.models.usuario import Usuario
from app.models.usuario_cliente import UsuarioCliente
from app.models.setor import Setor
from app.models.categoria import Categoria
from app.models.marca import Marca
from app.models.grupo import Grupo
from app.models.equipamento import Equipamento

__all__ = ["Funcao", "Usuario", "UsuarioCliente", "Setor", "Categoria", "Marca", "Grupo", "Equipamento"]
```

- [ ] **Step 5: Schemas** — adicione ao fim de `backend/app/schemas/cadastros.py`:

```python
class EquipamentoOut(BaseModel):
    id: int
    descricao: Optional[str] = None
    categoria: Optional[int] = None
    marca: Optional[int] = None
    detalhes: Optional[str] = None
    especificacao: Optional[str] = None
    preco_cod: float = 0
    preco_por: float = 0
    custo: float = 0
    peso_calibragem: float = 0
    peso: float = 0
    estoque: int = 0
    estoque_min: int = 0
    ativo: bool = False
    destaque: bool = False
    model_config = {"from_attributes": True}


class EquipamentoCreate(BaseModel):
    descricao: str = Field(min_length=1)
    categoria: Optional[int] = None
    marca: Optional[int] = None
    detalhes: Optional[str] = None
    especificacao: Optional[str] = None
    preco_cod: float = 0
    preco_por: float = 0
    custo: float = 0
    peso_calibragem: float = 0
    peso: float = 0
    estoque: int = 0
    estoque_min: int = 0
    ativo: bool = False
    destaque: bool = False


class EquipamentoUpdate(BaseModel):
    descricao: Optional[str] = Field(default=None, min_length=1)
    categoria: Optional[int] = None
    marca: Optional[int] = None
    detalhes: Optional[str] = None
    especificacao: Optional[str] = None
    preco_cod: Optional[float] = None
    preco_por: Optional[float] = None
    custo: Optional[float] = None
    peso_calibragem: Optional[float] = None
    peso: Optional[float] = None
    estoque: Optional[int] = None
    estoque_min: Optional[int] = None
    ativo: Optional[bool] = None
    destaque: Optional[bool] = None
```

- [ ] **Step 6: Router** — crie `backend/app/api/equipamentos.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Equipamento
from app.api.deps import get_current_usuario, require_funcao
from app.api.cadastros_common import excluir_protegido
from app.schemas.cadastros import EquipamentoOut, EquipamentoCreate, EquipamentoUpdate

router = APIRouter(prefix="/equipamentos", tags=["equipamentos"])
ADMIN = "Administrador"


@router.get("", response_model=list[EquipamentoOut])
def listar(db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    return db.query(Equipamento).order_by(Equipamento.id).all()


@router.get("/{item_id}", response_model=EquipamentoOut)
def obter(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    obj = db.query(Equipamento).filter(Equipamento.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    return obj


@router.post("", response_model=EquipamentoOut, status_code=status.HTTP_201_CREATED)
def criar(dados: EquipamentoCreate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = Equipamento(**dados.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/{item_id}", response_model=EquipamentoOut)
def atualizar(item_id: int, dados: EquipamentoUpdate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(Equipamento).filter(Equipamento.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    for chave, valor in dados.model_dump(exclude_unset=True).items():
        setattr(obj, chave, valor)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(Equipamento).filter(Equipamento.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    excluir_protegido(db, obj)
```

- [ ] **Step 7: Registrar** — em `backend/app/main.py`, adicione `equipamentos` ao import e inclua `app.include_router(equipamentos.router)`.

- [ ] **Step 8: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_cadastros_equipamentos.py -q`
Expected: PASS (4 testes). Suíte inteira: `docker compose exec -T backend python -m pytest -q` (sem regressões).

- [ ] **Step 9: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/app/models/equipamento.py backend/app/models/__init__.py backend/app/schemas/cadastros.py backend/app/api/equipamentos.py backend/app/main.py backend/tests/test_cadastros_equipamentos.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): catalogo de equipamentos (FKs categoria/marca) + guarda de exclusao"
```
Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 5: Frontend — módulo de API (crudClient genérico)

**Files:**
- Create: `frontend/src/app/cadastros/api.ts`
- Test: `frontend/src/app/cadastros/api.test.ts`

- [ ] **Step 1: Teste que falha** — crie `frontend/src/app/cadastros/api.test.ts`:

```ts
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setoresApi, equipamentosApi } from './api'
import { setTokens } from '../../lib/auth-storage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('cadastros/api (crudClient)', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    setTokens({ access_token: 't', refresh_token: 'r' })
  })

  it('listar faz GET no recurso', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse([{ id: 1, descricao: 'A' }]))
    vi.stubGlobal('fetch', f)
    const r = await setoresApi.listar()
    expect(String(f.mock.calls[0][0])).toContain('/setores')
    expect(r[0].descricao).toBe('A')
  })

  it('criar faz POST com corpo', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ id: 2, descricao: 'Novo' }))
    vi.stubGlobal('fetch', f)
    await setoresApi.criar({ descricao: 'Novo' })
    expect(f.mock.calls[0][1].method).toBe('POST')
    expect(String(f.mock.calls[0][1].body)).toContain('Novo')
  })

  it('excluir resolve no 204 e propaga 409', async () => {
    const ok = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', ok)
    await expect(equipamentosApi.excluir(5)).resolves.toBeUndefined()
    expect(ok.mock.calls[0][1].method).toBe('DELETE')

    const fail = vi.fn().mockResolvedValue(jsonResponse({ detail: 'registro em uso' }, 409))
    vi.stubGlobal('fetch', fail)
    await expect(equipamentosApi.excluir(5)).rejects.toMatchObject({ status: 409 })
  })
})
```

- [ ] **Step 2: Rodar e ver falhar**

Run (em `frontend/`): `npm run test -- cadastros/api`
Expected: FAIL (módulo não existe).

- [ ] **Step 3: Implementar** — crie `frontend/src/app/cadastros/api.ts`:

```ts
import { apiJson, apiFetch, ApiError } from '../../lib/api'

export interface Setor { id: number; descricao: string }
export interface Marca { id: number; descricao: string; imagem: string | null }
export interface Grupo { id: number; descricao: string; texto: string | null }
export interface Categoria { id: number; descricao: string | null; setor: number | null; posicao: number }
export interface Equipamento {
  id: number
  descricao: string | null
  categoria: number | null
  marca: number | null
  detalhes: string | null
  especificacao: string | null
  preco_cod: number
  preco_por: number
  custo: number
  peso_calibragem: number
  peso: number
  estoque: number
  estoque_min: number
  ativo: boolean
  destaque: boolean
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

export interface CrudClient<TOut, TCreate, TUpdate> {
  listar: () => Promise<TOut[]>
  obter: (id: number) => Promise<TOut>
  criar: (payload: TCreate) => Promise<TOut>
  atualizar: (id: number, payload: TUpdate) => Promise<TOut>
  excluir: (id: number) => Promise<void>
}

function crudClient<TOut, TCreate, TUpdate>(base: string): CrudClient<TOut, TCreate, TUpdate> {
  return {
    listar: () => apiJson<TOut[]>(base),
    obter: (id) => apiJson<TOut>(`${base}/${id}`),
    criar: (payload) => apiJson<TOut>(base, { method: 'POST', body: JSON.stringify(payload) }),
    atualizar: (id, payload) => apiJson<TOut>(`${base}/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
    excluir: (id) => apiVoid(`${base}/${id}`, { method: 'DELETE' }),
  }
}

export const setoresApi = crudClient<Setor, { descricao: string }, { descricao?: string }>('/setores')
export const marcasApi = crudClient<Marca, { descricao: string }, { descricao?: string }>('/marcas')
export const gruposApi = crudClient<Grupo, { descricao: string; texto?: string | null }, { descricao?: string; texto?: string | null }>('/grupos')
export const categoriasApi = crudClient<
  Categoria,
  { descricao: string; setor?: number | null; posicao?: number },
  { descricao?: string; setor?: number | null; posicao?: number }
>('/categorias')
export type EquipamentoPayload = Omit<Equipamento, 'id'>
export const equipamentosApi = crudClient<Equipamento, EquipamentoPayload, Partial<EquipamentoPayload>>('/equipamentos')
```

- [ ] **Step 4: Rodar e ver passar**

Run: `npm run test -- cadastros/api` (3 testes) e `npx tsc -b`.
Expected: PASS; tsc limpo.

- [ ] **Step 5: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/app/cadastros/api.ts frontend/src/app/cadastros/api.test.ts
git -C /d/GitHub/GestorHS commit -m "feat(frontend): modulo de API de cadastros (crudClient generico)"
```
Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 6: Frontend — hook `useCrud`

**Files:**
- Create: `frontend/src/app/cadastros/useCrud.ts`
- Test: `frontend/src/app/cadastros/useCrud.test.ts`

- [ ] **Step 1: Teste que falha** — crie `frontend/src/app/cadastros/useCrud.test.ts`:

```ts
import { describe, it, expect, vi } from 'vitest'
import { describe, it, expect, vi } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { useCrud } from './useCrud'
import { ApiError } from '../../lib/api'

describe('useCrud', () => {
  it('carrega itens no mount', async () => {
    const client = { listar: vi.fn().mockResolvedValue([{ id: 1 }, { id: 2 }]) }
    const { result } = renderHook(() => useCrud(client))
    await waitFor(() => expect(result.current.itens).not.toBeNull())
    expect(result.current.itens).toHaveLength(2)
    expect(result.current.erro).toBe('')
  })

  it('expõe erro quando listar falha', async () => {
    const client = { listar: vi.fn().mockRejectedValue(new ApiError(500, 'boom')) }
    const { result } = renderHook(() => useCrud(client))
    await waitFor(() => expect(result.current.erro).toBe('boom'))
    expect(result.current.itens).toEqual([])
  })

  it('recarregar busca de novo', async () => {
    const client = { listar: vi.fn().mockResolvedValue([{ id: 1 }]) }
    const { result } = renderHook(() => useCrud(client))
    await waitFor(() => expect(result.current.itens).toHaveLength(1))
    client.listar.mockResolvedValue([{ id: 1 }, { id: 2 }])
    await act(async () => {
      await result.current.recarregar()
    })
    expect(result.current.itens).toHaveLength(2)
  })
})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm run test -- useCrud`
Expected: FAIL (módulo não existe).

- [ ] **Step 3: Implementar** — crie `frontend/src/app/cadastros/useCrud.ts`:

```ts
import { useCallback, useEffect, useState } from 'react'
import { ApiError } from '../../lib/api'

export interface ListClient<T> {
  listar: () => Promise<T[]>
}

export function useCrud<T>(client: ListClient<T>) {
  const [itens, setItens] = useState<T[] | null>(null)
  const [erro, setErro] = useState('')

  const recarregar = useCallback(async () => {
    setErro('')
    try {
      const dados = await client.listar()
      setItens(dados)
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao carregar')
      setItens([])
    }
  }, [client])

  useEffect(() => {
    void recarregar()
  }, [recarregar])

  return { itens, erro, setErro, recarregar }
}
```

If `npm run lint` flags `react-hooks/set-state-in-effect` here, add `// eslint-disable-next-line react-hooks/set-state-in-effect` directly above the `void recarregar()` line (legitimate fetch-on-mount; same accepted pattern as `UsuariosPage`).

- [ ] **Step 4: Rodar e ver passar**

Run: `npm run test -- useCrud`, `npx tsc -b`, `npm run lint`.
Expected: PASS (3 testes + o placeholder); tsc/lint limpos.

- [ ] **Step 5: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/app/cadastros/useCrud.ts frontend/src/app/cadastros/useCrud.test.ts
git -C /d/GitHub/GestorHS commit -m "feat(frontend): hook useCrud (lista/erro/recarregar)"
```
Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 7: Frontend — painéis simples (CadastroSimples + GruposPanel)

Visual; verificação = tsc + lint.

**Files:**
- Create: `frontend/src/app/cadastros/CadastroSimples.tsx`
- Create: `frontend/src/app/cadastros/GruposPanel.tsx`

- [ ] **Step 1: CadastroSimples** (descrição-only; usado por Setores e Marcas) — crie `frontend/src/app/cadastros/CadastroSimples.tsx`:

```tsx
import { useState, type FormEvent } from 'react'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Spinner } from '../../components/ui/Spinner'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { ApiError } from '../../lib/api'
import { useCrud } from './useCrud'
import { type CrudClient } from './api'

interface SimpleItem {
  id: number
  descricao: string
}

type SimpleClient<T> = CrudClient<T, { descricao: string }, { descricao?: string }>

export function CadastroSimples<T extends SimpleItem>({ titulo, client }: { titulo: string; client: SimpleClient<T> }) {
  const { itens, erro, setErro, recarregar } = useCrud<T>(client)
  const [aberto, setAberto] = useState(false)
  const [editando, setEditando] = useState<T | null>(null)
  const [descricao, setDescricao] = useState('')
  const [erroForm, setErroForm] = useState('')
  const [enviando, setEnviando] = useState(false)

  function abrirNovo() {
    setEditando(null)
    setDescricao('')
    setErroForm('')
    setAberto(true)
  }

  function abrirEdicao(it: T) {
    setEditando(it)
    setDescricao(it.descricao)
    setErroForm('')
    setAberto(true)
  }

  async function salvar(e: FormEvent) {
    e.preventDefault()
    setErroForm('')
    setEnviando(true)
    try {
      if (editando) await client.atualizar(editando.id, { descricao })
      else await client.criar({ descricao })
      setAberto(false)
      await recarregar()
    } catch (err) {
      setErroForm(err instanceof ApiError ? err.message : 'Falha ao salvar')
    } finally {
      setEnviando(false)
    }
  }

  async function excluir(it: T) {
    if (!window.confirm(`Excluir "${it.descricao}"?`)) return
    try {
      await client.excluir(it.id)
      await recarregar()
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao excluir')
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-100">{titulo}</h2>
        <Button onClick={abrirNovo}>Novo</Button>
      </div>
      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      {itens === null ? (
        <div className="flex justify-center py-10"><Spinner className="w-7 h-7" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum registro.</p>
      ) : (
        <Table head={<><TH>Descrição</TH><TH>Ações</TH></>}>
          {itens.map((it) => (
            <tr key={it.id} className="hover:bg-background-elevated transition-colors">
              <TD>{it.descricao}</TD>
              <TD>
                <div className="flex gap-3">
                  <button onClick={() => abrirEdicao(it)} className="text-xs text-primary hover:underline">Editar</button>
                  <button onClick={() => excluir(it)} className="text-xs text-danger hover:underline">Excluir</button>
                </div>
              </TD>
            </tr>
          ))}
        </Table>
      )}
      {aberto && (
        <Modal
          open
          onClose={() => setAberto(false)}
          title={editando ? `Editar — ${titulo}` : `Novo — ${titulo}`}
          footer={
            <>
              <button type="button" onClick={() => setAberto(false)} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">Cancelar</button>
              <button type="submit" form="form-simples" disabled={enviando} className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all">Salvar</button>
            </>
          }
        >
          <form id="form-simples" className="space-y-4" onSubmit={salvar}>
            <Input id="descricao" label="Descrição" value={descricao} onChange={(e) => setDescricao(e.target.value)} required />
            {erroForm && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erroForm}</div>}
          </form>
        </Modal>
      )}
    </div>
  )
}
```

- [ ] **Step 2: GruposPanel** (descrição + texto) — crie `frontend/src/app/cadastros/GruposPanel.tsx`:

```tsx
import { useState, type FormEvent } from 'react'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Spinner } from '../../components/ui/Spinner'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { ApiError } from '../../lib/api'
import { useCrud } from './useCrud'
import { gruposApi, type Grupo } from './api'

export function GruposPanel() {
  const { itens, erro, setErro, recarregar } = useCrud<Grupo>(gruposApi)
  const [aberto, setAberto] = useState(false)
  const [editando, setEditando] = useState<Grupo | null>(null)
  const [descricao, setDescricao] = useState('')
  const [texto, setTexto] = useState('')
  const [erroForm, setErroForm] = useState('')
  const [enviando, setEnviando] = useState(false)

  function abrirNovo() {
    setEditando(null); setDescricao(''); setTexto(''); setErroForm(''); setAberto(true)
  }
  function abrirEdicao(g: Grupo) {
    setEditando(g); setDescricao(g.descricao); setTexto(g.texto ?? ''); setErroForm(''); setAberto(true)
  }

  async function salvar(e: FormEvent) {
    e.preventDefault(); setErroForm(''); setEnviando(true)
    try {
      const payload = { descricao, texto: texto.trim() || null }
      if (editando) await gruposApi.atualizar(editando.id, payload)
      else await gruposApi.criar(payload)
      setAberto(false); await recarregar()
    } catch (err) {
      setErroForm(err instanceof ApiError ? err.message : 'Falha ao salvar')
    } finally {
      setEnviando(false)
    }
  }

  async function excluir(g: Grupo) {
    if (!window.confirm(`Excluir "${g.descricao}"?`)) return
    try { await gruposApi.excluir(g.id); await recarregar() }
    catch (err) { setErro(err instanceof ApiError ? err.message : 'Falha ao excluir') }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-100">Grupos</h2>
        <Button onClick={abrirNovo}>Novo</Button>
      </div>
      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      {itens === null ? (
        <div className="flex justify-center py-10"><Spinner className="w-7 h-7" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum registro.</p>
      ) : (
        <Table head={<><TH>Descrição</TH><TH>Observação</TH><TH>Ações</TH></>}>
          {itens.map((g) => (
            <tr key={g.id} className="hover:bg-background-elevated transition-colors">
              <TD>{g.descricao}</TD>
              <TD>{g.texto ?? '—'}</TD>
              <TD>
                <div className="flex gap-3">
                  <button onClick={() => abrirEdicao(g)} className="text-xs text-primary hover:underline">Editar</button>
                  <button onClick={() => excluir(g)} className="text-xs text-danger hover:underline">Excluir</button>
                </div>
              </TD>
            </tr>
          ))}
        </Table>
      )}
      {aberto && (
        <Modal
          open
          onClose={() => setAberto(false)}
          title={editando ? 'Editar — Grupo' : 'Novo — Grupo'}
          footer={
            <>
              <button type="button" onClick={() => setAberto(false)} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">Cancelar</button>
              <button type="submit" form="form-grupo" disabled={enviando} className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all">Salvar</button>
            </>
          }
        >
          <form id="form-grupo" className="space-y-4" onSubmit={salvar}>
            <Input id="g-descricao" label="Descrição" value={descricao} onChange={(e) => setDescricao(e.target.value)} required />
            <div>
              <label htmlFor="g-texto" className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">Observação</label>
              <textarea id="g-texto" value={texto} onChange={(e) => setTexto(e.target.value)} className="w-full text-sm text-slate-200 bg-background-elevated border border-border rounded-lg px-3 py-2.5 resize-none focus:outline-none focus:ring-2 focus:ring-primary/40 placeholder-slate-500 leading-relaxed" rows={3} />
            </div>
            {erroForm && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erroForm}</div>}
          </form>
        </Modal>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Verificar**

Run: `npx tsc -b` e `npm run lint`. Sem erros (corrija lint mínimo se houver).

- [ ] **Step 4: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/app/cadastros/CadastroSimples.tsx frontend/src/app/cadastros/GruposPanel.tsx
git -C /d/GitHub/GestorHS commit -m "feat(frontend): paineis CadastroSimples (setores/marcas) e Grupos"
```
Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 8: Frontend — painéis Categorias e Equipamentos

Visual; verificação = tsc + lint.

**Files:**
- Create: `frontend/src/app/cadastros/CategoriasPanel.tsx`
- Create: `frontend/src/app/cadastros/EquipamentosPanel.tsx`

- [ ] **Step 1: CategoriasPanel** — crie `frontend/src/app/cadastros/CategoriasPanel.tsx`:

```tsx
import { useEffect, useState, type FormEvent } from 'react'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Spinner } from '../../components/ui/Spinner'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { ApiError } from '../../lib/api'
import { useCrud } from './useCrud'
import { categoriasApi, setoresApi, type Categoria, type Setor } from './api'

export function CategoriasPanel() {
  const { itens, erro, setErro, recarregar } = useCrud<Categoria>(categoriasApi)
  const [setores, setSetores] = useState<Setor[]>([])
  const [aberto, setAberto] = useState(false)
  const [editando, setEditando] = useState<Categoria | null>(null)
  const [descricao, setDescricao] = useState('')
  const [setorId, setSetorId] = useState('')
  const [posicao, setPosicao] = useState('0')
  const [erroForm, setErroForm] = useState('')
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void setoresApi.listar().then(setSetores).catch(() => setSetores([]))
  }, [])

  function nomeSetor(id: number | null) {
    return setores.find((s) => s.id === id)?.descricao ?? '—'
  }

  function abrirNovo() {
    setEditando(null); setDescricao(''); setSetorId(''); setPosicao('0'); setErroForm(''); setAberto(true)
  }
  function abrirEdicao(c: Categoria) {
    setEditando(c); setDescricao(c.descricao ?? ''); setSetorId(c.setor ? String(c.setor) : ''); setPosicao(String(c.posicao)); setErroForm(''); setAberto(true)
  }

  async function salvar(e: FormEvent) {
    e.preventDefault(); setErroForm(''); setEnviando(true)
    try {
      const payload = { descricao, setor: setorId ? Number(setorId) : null, posicao: Number(posicao) || 0 }
      if (editando) await categoriasApi.atualizar(editando.id, payload)
      else await categoriasApi.criar(payload)
      setAberto(false); await recarregar()
    } catch (err) {
      setErroForm(err instanceof ApiError ? err.message : 'Falha ao salvar')
    } finally {
      setEnviando(false)
    }
  }

  async function excluir(c: Categoria) {
    if (!window.confirm(`Excluir "${c.descricao}"?`)) return
    try { await categoriasApi.excluir(c.id); await recarregar() }
    catch (err) { setErro(err instanceof ApiError ? err.message : 'Falha ao excluir') }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-100">Categorias</h2>
        <Button onClick={abrirNovo}>Novo</Button>
      </div>
      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      {itens === null ? (
        <div className="flex justify-center py-10"><Spinner className="w-7 h-7" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum registro.</p>
      ) : (
        <Table head={<><TH>Descrição</TH><TH>Setor</TH><TH>Posição</TH><TH>Ações</TH></>}>
          {itens.map((c) => (
            <tr key={c.id} className="hover:bg-background-elevated transition-colors">
              <TD>{c.descricao ?? '—'}</TD>
              <TD>{nomeSetor(c.setor)}</TD>
              <TD>{c.posicao}</TD>
              <TD>
                <div className="flex gap-3">
                  <button onClick={() => abrirEdicao(c)} className="text-xs text-primary hover:underline">Editar</button>
                  <button onClick={() => excluir(c)} className="text-xs text-danger hover:underline">Excluir</button>
                </div>
              </TD>
            </tr>
          ))}
        </Table>
      )}
      {aberto && (
        <Modal
          open
          onClose={() => setAberto(false)}
          title={editando ? 'Editar — Categoria' : 'Nova — Categoria'}
          footer={
            <>
              <button type="button" onClick={() => setAberto(false)} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">Cancelar</button>
              <button type="submit" form="form-categoria" disabled={enviando} className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all">Salvar</button>
            </>
          }
        >
          <form id="form-categoria" className="space-y-4" onSubmit={salvar}>
            <Input id="c-descricao" label="Descrição" value={descricao} onChange={(e) => setDescricao(e.target.value)} required />
            <Select id="c-setor" label="Setor" value={setorId} onChange={(e) => setSetorId(e.target.value)}>
              <option value="">— sem setor —</option>
              {setores.map((s) => <option key={s.id} value={s.id}>{s.descricao}</option>)}
            </Select>
            <Input id="c-posicao" label="Posição" type="number" value={posicao} onChange={(e) => setPosicao(e.target.value)} />
            {erroForm && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erroForm}</div>}
          </form>
        </Modal>
      )}
    </div>
  )
}
```

- [ ] **Step 2: EquipamentosPanel** — crie `frontend/src/app/cadastros/EquipamentosPanel.tsx`:

```tsx
import { useEffect, useState, type FormEvent } from 'react'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Spinner } from '../../components/ui/Spinner'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { ApiError } from '../../lib/api'
import { useCrud } from './useCrud'
import { equipamentosApi, categoriasApi, marcasApi, type Equipamento, type Categoria, type Marca, type EquipamentoPayload } from './api'

const VAZIO: EquipamentoPayload = {
  descricao: '', categoria: null, marca: null, detalhes: null, especificacao: null,
  preco_cod: 0, preco_por: 0, custo: 0, peso_calibragem: 0, peso: 0,
  estoque: 0, estoque_min: 0, ativo: false, destaque: false,
}

export function EquipamentosPanel() {
  const { itens, erro, setErro, recarregar } = useCrud<Equipamento>(equipamentosApi)
  const [categorias, setCategorias] = useState<Categoria[]>([])
  const [marcas, setMarcas] = useState<Marca[]>([])
  const [aberto, setAberto] = useState(false)
  const [editandoId, setEditandoId] = useState<number | null>(null)
  const [form, setForm] = useState<EquipamentoPayload>(VAZIO)
  const [erroForm, setErroForm] = useState('')
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void categoriasApi.listar().then(setCategorias).catch(() => setCategorias([]))
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void marcasApi.listar().then(setMarcas).catch(() => setMarcas([]))
  }, [])

  function nome(lista: { id: number; descricao: string | null }[], id: number | null) {
    return lista.find((x) => x.id === id)?.descricao ?? '—'
  }

  function set<K extends keyof EquipamentoPayload>(chave: K, valor: EquipamentoPayload[K]) {
    setForm((f) => ({ ...f, [chave]: valor }))
  }

  function abrirNovo() {
    setEditandoId(null); setForm(VAZIO); setErroForm(''); setAberto(true)
  }
  function abrirEdicao(e: Equipamento) {
    setEditandoId(e.id)
    setForm({
      descricao: e.descricao ?? '', categoria: e.categoria, marca: e.marca, detalhes: e.detalhes, especificacao: e.especificacao,
      preco_cod: e.preco_cod, preco_por: e.preco_por, custo: e.custo, peso_calibragem: e.peso_calibragem, peso: e.peso,
      estoque: e.estoque, estoque_min: e.estoque_min, ativo: e.ativo, destaque: e.destaque,
    })
    setErroForm(''); setAberto(true)
  }

  async function salvar(ev: FormEvent) {
    ev.preventDefault(); setErroForm(''); setEnviando(true)
    try {
      if (editandoId !== null) await equipamentosApi.atualizar(editandoId, form)
      else await equipamentosApi.criar(form)
      setAberto(false); await recarregar()
    } catch (err) {
      setErroForm(err instanceof ApiError ? err.message : 'Falha ao salvar')
    } finally {
      setEnviando(false)
    }
  }

  async function excluir(e: Equipamento) {
    if (!window.confirm(`Excluir "${e.descricao}"?`)) return
    try { await equipamentosApi.excluir(e.id); await recarregar() }
    catch (err) { setErro(err instanceof ApiError ? err.message : 'Falha ao excluir') }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-100">Catálogo de equipamentos</h2>
        <Button onClick={abrirNovo}>Novo</Button>
      </div>
      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      {itens === null ? (
        <div className="flex justify-center py-10"><Spinner className="w-7 h-7" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum registro.</p>
      ) : (
        <Table head={<><TH>Descrição</TH><TH>Categoria</TH><TH>Marca</TH><TH>Preço</TH><TH>Estoque</TH><TH>Status</TH><TH>Ações</TH></>}>
          {itens.map((e) => (
            <tr key={e.id} className="hover:bg-background-elevated transition-colors">
              <TD>{e.descricao ?? '—'}</TD>
              <TD>{nome(categorias, e.categoria)}</TD>
              <TD>{nome(marcas, e.marca)}</TD>
              <TD>{e.preco_por.toFixed(2)}</TD>
              <TD>{e.estoque}</TD>
              <TD><Badge tone={e.ativo ? 'primary' : 'neutral'}>{e.ativo ? 'Ativo' : 'Inativo'}</Badge></TD>
              <TD>
                <div className="flex gap-3">
                  <button onClick={() => abrirEdicao(e)} className="text-xs text-primary hover:underline">Editar</button>
                  <button onClick={() => excluir(e)} className="text-xs text-danger hover:underline">Excluir</button>
                </div>
              </TD>
            </tr>
          ))}
        </Table>
      )}
      {aberto && (
        <Modal
          open
          onClose={() => setAberto(false)}
          title={editandoId !== null ? 'Editar — Equipamento' : 'Novo — Equipamento'}
          footer={
            <>
              <button type="button" onClick={() => setAberto(false)} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">Cancelar</button>
              <button type="submit" form="form-equip" disabled={enviando} className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all">Salvar</button>
            </>
          }
        >
          <form id="form-equip" className="space-y-4" onSubmit={salvar}>
            <Input id="e-descricao" label="Descrição" value={form.descricao} onChange={(ev) => set('descricao', ev.target.value)} required />
            <div className="grid grid-cols-2 gap-3">
              <Select id="e-categoria" label="Categoria" value={form.categoria ? String(form.categoria) : ''} onChange={(ev) => set('categoria', ev.target.value ? Number(ev.target.value) : null)}>
                <option value="">— sem categoria —</option>
                {categorias.map((c) => <option key={c.id} value={c.id}>{c.descricao}</option>)}
              </Select>
              <Select id="e-marca" label="Marca" value={form.marca ? String(form.marca) : ''} onChange={(ev) => set('marca', ev.target.value ? Number(ev.target.value) : null)}>
                <option value="">— sem marca —</option>
                {marcas.map((m) => <option key={m.id} value={m.id}>{m.descricao}</option>)}
              </Select>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <Input id="e-preco_por" label="Preço" type="number" step="0.01" value={String(form.preco_por)} onChange={(ev) => set('preco_por', Number(ev.target.value))} />
              <Input id="e-custo" label="Custo" type="number" step="0.01" value={String(form.custo)} onChange={(ev) => set('custo', Number(ev.target.value))} />
              <Input id="e-preco_cod" label="Preço cod." type="number" step="0.01" value={String(form.preco_cod)} onChange={(ev) => set('preco_cod', Number(ev.target.value))} />
            </div>
            <div className="grid grid-cols-3 gap-3">
              <Input id="e-estoque" label="Estoque" type="number" value={String(form.estoque)} onChange={(ev) => set('estoque', Number(ev.target.value))} />
              <Input id="e-estoque_min" label="Estoque mín." type="number" value={String(form.estoque_min)} onChange={(ev) => set('estoque_min', Number(ev.target.value))} />
              <Input id="e-peso" label="Peso" type="number" step="0.001" value={String(form.peso)} onChange={(ev) => set('peso', Number(ev.target.value))} />
            </div>
            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input type="checkbox" checked={form.ativo} onChange={(ev) => set('ativo', ev.target.checked)} className="accent-primary" />
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

- [ ] **Step 3: Verificar**

Run: `npx tsc -b` e `npm run lint`. Sem erros (corrija lint mínimo se houver).

- [ ] **Step 4: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/app/cadastros/CategoriasPanel.tsx frontend/src/app/cadastros/EquipamentosPanel.tsx
git -C /d/GitHub/GestorHS commit -m "feat(frontend): paineis de Categorias e Equipamentos"
```
Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 9: Frontend — página Cadastros (abas) + nav + rota + integração

**Files:**
- Modify: `frontend/src/components/ui/icons.tsx` (adiciona `IconCadastros`)
- Create: `frontend/src/app/cadastros/CadastrosPage.tsx`
- Modify: `frontend/src/layout/Sidebar.tsx` (item de nav)
- Modify: `frontend/src/app/routes.tsx` (rota)

- [ ] **Step 1: Ícone** — adicione ao fim de `frontend/src/components/ui/icons.tsx`:

```tsx
export function IconCadastros({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 6a2 2 0 012-2h9l5 5v9a2 2 0 01-2 2H6a2 2 0 01-2-2V6z M8 10h8 M8 14h5" />
    </svg>
  )
}
```

- [ ] **Step 2: CadastrosPage com abas** — crie `frontend/src/app/cadastros/CadastrosPage.tsx`:

```tsx
import { useState } from 'react'
import { cn } from '../../lib/utils'
import { useAuth } from '../../auth/AuthContext'
import { isAdmin } from '../../auth/roles'
import { CadastroSimples } from './CadastroSimples'
import { GruposPanel } from './GruposPanel'
import { CategoriasPanel } from './CategoriasPanel'
import { EquipamentosPanel } from './EquipamentosPanel'
import { setoresApi, marcasApi, type Setor, type Marca } from './api'

const ABAS = ['Setores', 'Marcas', 'Grupos', 'Categorias', 'Equipamentos'] as const
type Aba = (typeof ABAS)[number]

export function CadastrosPage() {
  const { user } = useAuth()
  const [aba, setAba] = useState<Aba>('Setores')

  if (!isAdmin(user)) {
    return (
      <div className="px-4 md:px-6 py-6">
        <p className="text-sm text-slate-400">Acesso restrito a administradores.</p>
      </div>
    )
  }

  return (
    <div className="px-4 md:px-6 py-6 space-y-6">
      <h1 className="text-2xl font-extrabold text-slate-100">Cadastros</h1>
      <div className="flex flex-wrap gap-2">
        {ABAS.map((a) => (
          <button
            key={a}
            onClick={() => setAba(a)}
            className={cn(
              'text-xs px-3 py-1.5 rounded-full font-medium transition-all',
              aba === a ? 'bg-primary/15 text-primary' : 'text-slate-500 hover:text-slate-300 hover:bg-background-elevated',
            )}
          >
            {a}
          </button>
        ))}
      </div>
      <div className="rounded-2xl bg-background-surface border border-border p-5">
        {aba === 'Setores' && <CadastroSimples<Setor> titulo="Setores" client={setoresApi} />}
        {aba === 'Marcas' && <CadastroSimples<Marca> titulo="Marcas" client={marcasApi} />}
        {aba === 'Grupos' && <GruposPanel />}
        {aba === 'Categorias' && <CategoriasPanel />}
        {aba === 'Equipamentos' && <EquipamentosPanel />}
      </div>
    </div>
  )
}
```

Nota: `CadastroSimples<Marca>` aceita o `marcasApi` porque `MarcaCreate`/`Update` são `{descricao}` — compatível com `SimpleClient`. Se o TypeScript reclamar da variância do client, troque a assinatura de `CadastroSimples` para aceitar `CrudClient<T, { descricao: string }, { descricao?: string }>` (já é o caso) — `marcasApi`/`setoresApi` satisfazem.

- [ ] **Step 3: Nav** — em `frontend/src/layout/Sidebar.tsx`, importe `IconCadastros` (junto de `IconDashboard, IconUsers`) e adicione ao array `NAV_ITEMS` (depois de "Usuários"):

```tsx
  { label: 'Cadastros', icon: <IconCadastros />, to: '/app/cadastros', adminOnly: true },
```

- [ ] **Step 4: Rota** — em `frontend/src/app/routes.tsx`, importe `CadastrosPage` e adicione a rota dentro do `<Routes>` (depois de `usuarios`):

```tsx
import { CadastrosPage } from './cadastros/CadastrosPage'
```
```tsx
        <Route path="cadastros" element={<CadastrosPage />} />
```

- [ ] **Step 5: Verificar tudo**

Run (em `frontend/`): `npm run test`, `npx tsc -b`, `npm run lint`, `npm run build`.
Expected: testes verdes (incl. cadastros/api + useCrud), tsc/lint limpos, build OK.

- [ ] **Step 6: Verificação manual E2E** (backend `docker compose up -d`; admin `admin`/`GestorHS@2026`; `frontend/.env` com `VITE_API_URL=http://localhost:8000`)

`npm run dev` e abra a URL. Verifique:
1. Admin loga → Sidebar mostra "Cadastros".
2. `/app/cadastros` → abas Setores/Marcas/Grupos/Categorias/Equipamentos alternam.
3. Criar/editar/excluir um setor; criar uma categoria escolhendo um setor; criar um equipamento escolhendo categoria+marca.
4. Excluir um setor que tem categoria, ou marca/categoria em uso por equipamento → erro **"registro em uso"** (409); o registro permanece.
5. Os selects de categoria/marca no form de equipamento vêm populados.

- [ ] **Step 7: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/components/ui/icons.tsx frontend/src/app/cadastros/CadastrosPage.tsx frontend/src/layout/Sidebar.tsx frontend/src/app/routes.tsx
git -C /d/GitHub/GestorHS commit -m "feat(frontend): pagina Cadastros com abas + nav + rota"
```
Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

## Notas para o executor

- **Backend roda no container:** `docker compose up -d` antes dos `pytest`. O FK do SQLite só é imposto por causa do PRAGMA da Task 1 — o teste de delete-em-uso depende disso.
- **`models/__init__.py`** é reescrito nas Tasks 1, 2 e 4 (acumulando imports). O estado final exporta Funcao, Usuario, UsuarioCliente, Setor, Categoria, Marca, Grupo, Equipamento.
- **`main.py`** ganha um `include_router` por entidade (setores, marcas, grupos, categorias, equipamentos) além do que já existia. Mantenha CORS e `/health`.
- **`verbatimModuleSyntax`:** `import { type X }` para tipos.
- **`window.confirm`** na exclusão (padrão do 1A).
- **Reúso vs 1A:** não refatoramos `UsuariosPage`; o `useCrud`/`crudClient` são introduzidos só para os cadastros novos.
- **`CadastroSimples` genérico:** se a inferência de tipo do componente genérico em JSX (`<CadastroSimples<Marca> .../>`) der problema, garanta que a prop `client` está tipada como `CrudClient<T, { descricao: string }, { descricao?: string }>` — `setoresApi` e `marcasApi` já satisfazem essa forma.
