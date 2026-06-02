# Fase 1A (Acesso) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gestão de acesso interno do GestorHS — CRUD de usuários internos, listar/atribuir funções, ciclo de senha (admin reseta / usuário troca a própria) e navegação gated por função — com a API impondo a permissão.

**Architecture:** Backend FastAPI + SQLAlchemy 2 + Pydantic v2 (routers por domínio `funcoes`/`usuarios`, autorização via `require_funcao("Administrador")`). Frontend React 19 reusando o design system da Fase 0 (Table/Modal/Button/Input/Select/Badge), com `AuthContext` estendido para expor a função e a `Sidebar` filtrando itens admin-only. TDD no backend (pytest, SQLite) e na lógica do frontend (Vitest+RTL); telas visuais verificadas por tsc+lint+E2E manual.

**Tech Stack:** FastAPI, SQLAlchemy 2, Pydantic v2, pytest; React 19, TypeScript, Vite 8, react-router-dom 7, Vitest + RTL.

**Referências:**
- Spec: `docs/superpowers/specs/2026-06-02-fase1a-acesso-design.md`
- Contrato auth existente: `/auth/login`, `/auth/me`, `/auth/refresh`. `require_funcao(*descricoes)` em `app/api/deps.py` retorna o `Usuario` atual e dá 403 se a função não bate.
- Modelos: `Usuario(id, nome, login unique, senha text/hash, email, funcao_id FK funcoes, precisa_redefinir_senha)`, `Funcao(id, descricao unique)`.

**Convenções de teste (backend):** `tests/conftest.py` provê `db_session` (SQLite in-memory), `client` (override de `get_db`) e `usuario_admin` (cria Função "Administrador" + usuário `admin`/`senha123`). Tokens via `POST /auth/login`.

**Como rodar os testes backend:** o container tem as deps e monta `./backend`. Com `docker compose up -d` (na raiz do repo), rode da raiz `d:\GitHub\GestorHS`:
`docker compose exec -T backend python -m pytest -q <caminho>`

**Convenções TS (frontend, do tsconfig):** `verbatimModuleSyntax` (use `import { type X }`), `noUnusedLocals`/`noUnusedParameters`. Lint baseline limpo — qualquer novo erro é para corrigir. npm da pasta `frontend/`; git via `git -C /d/GitHub/GestorHS`.

**Branch:** rode tudo em `feat/fase1a-acesso`. Antes da Task 1:
```bash
git -C /d/GitHub/GestorHS checkout -b feat/fase1a-acesso
```

---

### Task 1: `/auth/me` devolve a descrição da função

**Files:**
- Modify: `backend/app/models/usuario.py`
- Modify: `backend/app/schemas/auth.py`
- Test: `backend/tests/test_auth.py` (adiciona um teste)

- [ ] **Step 1: Teste que falha** — adicione ao fim de `backend/tests/test_auth.py`:

```python
def test_me_retorna_descricao_da_funcao(client, usuario_admin):
    tokens = client.post("/auth/login", json={"login": "admin", "senha": "senha123"}).json()
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert r.status_code == 200
    assert r.json()["funcao"] == "Administrador"
```

- [ ] **Step 2: Rodar e ver falhar**

Run (da raiz): `docker compose exec -T backend python -m pytest tests/test_auth.py::test_me_retorna_descricao_da_funcao -q`
Expected: FAIL (`funcao` ausente / KeyError no JSON).

- [ ] **Step 3: Adicionar o relationship e a property** — `backend/app/models/usuario.py` (substitua o arquivo):

```python
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.models.database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=True)
    login = Column(String(20), nullable=False, unique=True)
    senha = Column(Text, nullable=False)            # hash argon2
    email = Column(String(200), nullable=True)
    funcao_id = Column(Integer, ForeignKey("funcoes.id"), nullable=True)
    precisa_redefinir_senha = Column(Boolean, nullable=False, default=False)

    funcao_rel = relationship("Funcao", lazy="joined")

    @property
    def funcao(self) -> str | None:
        return self.funcao_rel.descricao if self.funcao_rel else None
```

- [ ] **Step 4: Incluir o campo no schema** — em `backend/app/schemas/auth.py`, na classe `UsuarioOut`, adicione o campo `funcao` (e mantenha o resto):

```python
class UsuarioOut(BaseModel):
    id: int
    nome: Optional[str]
    login: str
    email: Optional[str]
    funcao_id: Optional[int]
    funcao: Optional[str] = None

    model_config = {"from_attributes": True}
```

- [ ] **Step 5: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_auth.py -q`
Expected: PASS (todos os testes de auth, incl. o novo).

- [ ] **Step 6: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/app/models/usuario.py backend/app/schemas/auth.py backend/tests/test_auth.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): /auth/me devolve a descricao da funcao"
```
Trailer do commit: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 2: `GET /funcoes` (admin) + fixture de não-admin

**Files:**
- Create: `backend/app/schemas/acesso.py`
- Create: `backend/app/api/funcoes.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/conftest.py` (adiciona fixture `usuario_comum`)
- Test: `backend/tests/test_acesso.py`

- [ ] **Step 1: Fixture de usuário não-admin** — adicione ao fim de `backend/tests/conftest.py`:

```python
@pytest.fixture()
def usuario_comum(db_session):
    funcao = db_session.query(Funcao).filter(Funcao.descricao == "Expedição").first()
    if funcao is None:
        funcao = Funcao(descricao="Expedição")
        db_session.add(funcao)
        db_session.flush()
    u = Usuario(
        nome="Comum",
        login="comum",
        senha=hash_senha("senha123"),
        email="comum@hs.com",
        funcao_id=funcao.id,
        precisa_redefinir_senha=False,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u
```

- [ ] **Step 2: Teste que falha** — crie `backend/tests/test_acesso.py`:

```python
def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def test_listar_funcoes_admin(client, usuario_admin):
    r = client.get("/funcoes", headers=_headers(client, "admin", "senha123"))
    assert r.status_code == 200
    assert any(f["descricao"] == "Administrador" for f in r.json())


def test_funcoes_nega_nao_admin(client, usuario_comum):
    r = client.get("/funcoes", headers=_headers(client, "comum", "senha123"))
    assert r.status_code == 403
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_acesso.py -q`
Expected: FAIL (404 — rota `/funcoes` não existe).

- [ ] **Step 4: Schemas de acesso** — crie `backend/app/schemas/acesso.py`:

```python
from pydantic import BaseModel, Field
from typing import Optional


class FuncaoOut(BaseModel):
    id: int
    descricao: str
    model_config = {"from_attributes": True}


class UsuarioListOut(BaseModel):
    id: int
    nome: Optional[str]
    login: str
    email: Optional[str]
    funcao_id: Optional[int]
    funcao: Optional[str] = None
    precisa_redefinir_senha: bool
    model_config = {"from_attributes": True}


class UsuarioCreate(BaseModel):
    nome: Optional[str] = None
    login: str = Field(min_length=1, max_length=20)
    email: Optional[str] = None
    senha: str = Field(min_length=8)
    funcao_id: Optional[int] = None


class UsuarioUpdate(BaseModel):
    nome: Optional[str] = None
    email: Optional[str] = None
    funcao_id: Optional[int] = None
    login: Optional[str] = Field(default=None, max_length=20)


class RedefinirSenhaIn(BaseModel):
    nova_senha: str = Field(min_length=8)
```

- [ ] **Step 5: Router de funções** — crie `backend/app/api/funcoes.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Funcao
from app.api.deps import require_funcao
from app.schemas.acesso import FuncaoOut

router = APIRouter(prefix="/funcoes", tags=["funcoes"])


@router.get("", response_model=list[FuncaoOut])
def listar(db: Session = Depends(get_db), _: Usuario = Depends(require_funcao("Administrador"))):
    return db.query(Funcao).order_by(Funcao.id).all()
```

- [ ] **Step 6: Registrar o router** — em `backend/app/main.py`, importe e inclua (mantendo o que já existe):

```python
from app.api import auth, funcoes

app.include_router(auth.router)
app.include_router(funcoes.router)
```

- [ ] **Step 7: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_acesso.py -q`
Expected: PASS (2 testes).

- [ ] **Step 8: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/app/schemas/acesso.py backend/app/api/funcoes.py backend/app/main.py backend/tests/conftest.py backend/tests/test_acesso.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): GET /funcoes (admin) + schemas de acesso"
```
Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 3: `GET` e `POST /usuarios`

**Files:**
- Create: `backend/app/api/usuarios.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_acesso.py` (adiciona testes)

- [ ] **Step 1: Testes que falham** — adicione a `backend/tests/test_acesso.py`:

```python
def test_listar_usuarios_admin(client, usuario_admin):
    r = client.get("/usuarios", headers=_headers(client, "admin", "senha123"))
    assert r.status_code == 200
    assert any(u["login"] == "admin" for u in r.json())


def test_usuarios_nega_nao_admin(client, usuario_comum):
    r = client.get("/usuarios", headers=_headers(client, "comum", "senha123"))
    assert r.status_code == 403


def test_criar_usuario(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    r = client.post("/usuarios", json={"login": "joao", "nome": "Joao", "senha": "segredo123"}, headers=h)
    assert r.status_code == 201
    assert r.json()["login"] == "joao"
    # a senha gravada é hash e autentica no login
    assert client.post("/auth/login", json={"login": "joao", "senha": "segredo123"}).status_code == 200


def test_criar_usuario_login_duplicado(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    r = client.post("/usuarios", json={"login": "admin", "senha": "segredo123"}, headers=h)
    assert r.status_code == 409


def test_criar_usuario_senha_curta(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    r = client.post("/usuarios", json={"login": "curto", "senha": "1234"}, headers=h)
    assert r.status_code == 422
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_acesso.py -q`
Expected: FAIL (404 — `/usuarios` não existe).

- [ ] **Step 3: Router de usuários (list + create)** — crie `backend/app/api/usuarios.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Funcao
from app.core.security import hash_senha
from app.api.deps import require_funcao
from app.schemas.acesso import UsuarioListOut, UsuarioCreate

router = APIRouter(prefix="/usuarios", tags=["usuarios"])

ADMIN = "Administrador"


def _conta_admins(db: Session) -> int:
    return (
        db.query(Usuario)
        .join(Funcao, Usuario.funcao_id == Funcao.id)
        .filter(Funcao.descricao == ADMIN)
        .count()
    )


def _eh_admin(db: Session, usuario: Usuario) -> bool:
    if usuario.funcao_id is None:
        return False
    f = db.query(Funcao).filter(Funcao.id == usuario.funcao_id).first()
    return f is not None and f.descricao == ADMIN


@router.get("", response_model=list[UsuarioListOut])
def listar(db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    return db.query(Usuario).order_by(Usuario.id).all()


@router.post("", response_model=UsuarioListOut, status_code=status.HTTP_201_CREATED)
def criar(dados: UsuarioCreate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    if db.query(Usuario).filter(Usuario.login == dados.login).first() is not None:
        raise HTTPException(status_code=409, detail="login já em uso")
    u = Usuario(
        nome=dados.nome,
        login=dados.login,
        email=dados.email,
        senha=hash_senha(dados.senha),
        funcao_id=dados.funcao_id,
        precisa_redefinir_senha=False,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u
```

- [ ] **Step 4: Registrar o router** — em `backend/app/main.py`:

```python
from app.api import auth, funcoes, usuarios

app.include_router(auth.router)
app.include_router(funcoes.router)
app.include_router(usuarios.router)
```

- [ ] **Step 5: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_acesso.py -q`
Expected: PASS (todos, incl. os 5 novos).

- [ ] **Step 6: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/app/api/usuarios.py backend/app/main.py backend/tests/test_acesso.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): GET e POST /usuarios (admin, hash, login unico)"
```
Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 4: `GET` e `PATCH /usuarios/{id}`

**Files:**
- Modify: `backend/app/api/usuarios.py`
- Test: `backend/tests/test_acesso.py`

- [ ] **Step 1: Testes que falham** — adicione a `backend/tests/test_acesso.py`:

```python
def _criar(client, h, **kw):
    return client.post("/usuarios", json=kw, headers=h)


def test_obter_usuario_inexistente_404(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    r = client.get("/usuarios/99999", headers=h)
    assert r.status_code == 404


def test_atualizar_troca_funcao(client, usuario_admin, db_session):
    from app.models import Funcao
    exp = Funcao(descricao="Laboratório")
    db_session.add(exp)
    db_session.commit()
    h = _headers(client, "admin", "senha123")
    novo = _criar(client, h, login="maria", senha="segredo123").json()
    r = client.patch(f"/usuarios/{novo['id']}", json={"funcao_id": exp.id}, headers=h)
    assert r.status_code == 200
    assert r.json()["funcao"] == "Laboratório"


def test_atualizar_login_duplicado_409(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    novo = _criar(client, h, login="pedro", senha="segredo123").json()
    r = client.patch(f"/usuarios/{novo['id']}", json={"login": "admin"}, headers=h)
    assert r.status_code == 409


def test_patch_nega_rebaixar_ultimo_admin(client, usuario_admin, db_session):
    from app.models import Funcao
    exp = db_session.query(Funcao).filter(Funcao.descricao == "Laboratório").first()
    if exp is None:
        exp = Funcao(descricao="Laboratório")
        db_session.add(exp)
        db_session.commit()
    h = _headers(client, "admin", "senha123")
    # admin é o único Administrador; tentar tirar sua função admin -> 400
    r = client.patch(f"/usuarios/{usuario_admin.id}", json={"funcao_id": exp.id}, headers=h)
    assert r.status_code == 400
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_acesso.py -q`
Expected: FAIL (405/404 — rotas `GET/PATCH /usuarios/{id}` não existem).

- [ ] **Step 3: Implementar** — adicione a `backend/app/api/usuarios.py` (importe `UsuarioUpdate` no topo: `from app.schemas.acesso import UsuarioListOut, UsuarioCreate, UsuarioUpdate`):

```python
@router.get("/{usuario_id}", response_model=UsuarioListOut)
def obter(usuario_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    u = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if u is None:
        raise HTTPException(status_code=404, detail="usuário não encontrado")
    return u


@router.patch("/{usuario_id}", response_model=UsuarioListOut)
def atualizar(usuario_id: int, dados: UsuarioUpdate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    u = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if u is None:
        raise HTTPException(status_code=404, detail="usuário não encontrado")
    campos = dados.model_dump(exclude_unset=True)
    if "login" in campos and campos["login"] != u.login:
        if db.query(Usuario).filter(Usuario.login == campos["login"]).first() is not None:
            raise HTTPException(status_code=409, detail="login já em uso")
    if "funcao_id" in campos and campos["funcao_id"] != u.funcao_id and _eh_admin(db, u):
        if _conta_admins(db) <= 1:
            raise HTTPException(status_code=400, detail="não é possível remover o último administrador")
    for chave, valor in campos.items():
        setattr(u, chave, valor)
    db.commit()
    db.refresh(u)
    return u
```

- [ ] **Step 4: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_acesso.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/app/api/usuarios.py backend/tests/test_acesso.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): GET e PATCH /usuarios/{id} (404, login unico, guarda do ultimo admin)"
```
Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 5: `DELETE /usuarios/{id}` com guardas

**Files:**
- Modify: `backend/app/api/usuarios.py`
- Test: `backend/tests/test_acesso.py`

- [ ] **Step 1: Testes que falham** — adicione a `backend/tests/test_acesso.py`:

```python
def test_excluir_a_si_mesmo_400(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    r = client.delete(f"/usuarios/{usuario_admin.id}", headers=h)
    assert r.status_code == 400


def test_excluir_usuario_comum_ok(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    novo = _criar(client, h, login="temp", senha="segredo123").json()
    r = client.delete(f"/usuarios/{novo['id']}", headers=h)
    assert r.status_code == 204
    assert client.get(f"/usuarios/{novo['id']}", headers=h).status_code == 404
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_acesso.py -q`
Expected: FAIL (405 — `DELETE` não existe).

- [ ] **Step 3: Implementar** — adicione a `backend/app/api/usuarios.py` (note que esta rota usa o usuário atual, capturado em `atual`):

```python
@router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(usuario_id: int, db: Session = Depends(get_db), atual: Usuario = Depends(require_funcao(ADMIN))):
    u = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if u is None:
        raise HTTPException(status_code=404, detail="usuário não encontrado")
    if u.id == atual.id:
        raise HTTPException(status_code=400, detail="não é possível excluir o próprio usuário")
    if _eh_admin(db, u) and _conta_admins(db) <= 1:
        raise HTTPException(status_code=400, detail="não é possível excluir o último administrador")
    db.delete(u)
    db.commit()
```

- [ ] **Step 4: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_acesso.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/app/api/usuarios.py backend/tests/test_acesso.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): DELETE /usuarios/{id} (guarda self e ultimo admin)"
```
Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 6: Redefinir senha (admin) e trocar a própria senha

**Files:**
- Modify: `backend/app/api/usuarios.py`
- Modify: `backend/app/schemas/auth.py` (adiciona `TrocarSenhaIn`)
- Modify: `backend/app/api/auth.py` (adiciona `POST /auth/trocar-senha`)
- Test: `backend/tests/test_acesso.py`

- [ ] **Step 1: Testes que falham** — adicione a `backend/tests/test_acesso.py`:

```python
def test_admin_redefine_senha(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    novo = _criar(client, h, login="ana", senha="segredo123").json()
    r = client.post(f"/usuarios/{novo['id']}/redefinir-senha", json={"nova_senha": "novaSenha9"}, headers=h)
    assert r.status_code == 204
    assert client.post("/auth/login", json={"login": "ana", "senha": "novaSenha9"}).status_code == 200


def test_trocar_minha_senha_ok(client, usuario_comum):
    h = _headers(client, "comum", "senha123")
    r = client.post("/auth/trocar-senha", json={"senha_atual": "senha123", "nova_senha": "outraSenha9"}, headers=h)
    assert r.status_code == 204
    assert client.post("/auth/login", json={"login": "comum", "senha": "outraSenha9"}).status_code == 200


def test_trocar_minha_senha_atual_errada(client, usuario_comum):
    h = _headers(client, "comum", "senha123")
    r = client.post("/auth/trocar-senha", json={"senha_atual": "errada", "nova_senha": "outraSenha9"}, headers=h)
    assert r.status_code == 400
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_acesso.py -q`
Expected: FAIL (404 nas rotas novas).

- [ ] **Step 3: Endpoint de redefinir senha** — adicione a `backend/app/api/usuarios.py` (importe `RedefinirSenhaIn`: `from app.schemas.acesso import UsuarioListOut, UsuarioCreate, UsuarioUpdate, RedefinirSenhaIn`):

```python
@router.post("/{usuario_id}/redefinir-senha", status_code=status.HTTP_204_NO_CONTENT)
def redefinir_senha(usuario_id: int, dados: RedefinirSenhaIn, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    u = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if u is None:
        raise HTTPException(status_code=404, detail="usuário não encontrado")
    u.senha = hash_senha(dados.nova_senha)
    u.precisa_redefinir_senha = False
    db.commit()
```

- [ ] **Step 4: Schema `TrocarSenhaIn`** — adicione a `backend/app/schemas/auth.py` (no topo garanta `from pydantic import BaseModel, Field`):

```python
class TrocarSenhaIn(BaseModel):
    senha_atual: str
    nova_senha: str = Field(min_length=8)
```

- [ ] **Step 5: Endpoint de trocar a própria senha** — em `backend/app/api/auth.py`, importe o schema e `get_db`/`verificar_senha`/`hash_senha` (já importados) e adicione a rota. Ajuste o import de schemas para incluir `TrocarSenhaIn` e o de deps para incluir `get_current_usuario` (já está). Acrescente:

```python
from app.schemas.auth import LoginRequest, PortalLoginRequest, Token, RefreshRequest, UsuarioOut, TrocarSenhaIn


@router.post("/trocar-senha", status_code=status.HTTP_204_NO_CONTENT)
def trocar_senha(
    dados: TrocarSenhaIn,
    usuario: Usuario = Depends(get_current_usuario),
    db: Session = Depends(get_db),
):
    if not verificar_senha(dados.senha_atual, usuario.senha):
        raise HTTPException(status_code=400, detail="senha atual incorreta")
    usuario.senha = hash_senha(dados.nova_senha)
    db.commit()
```

(O import existente é `from app.schemas.auth import LoginRequest, PortalLoginRequest, Token, RefreshRequest, UsuarioOut` — apenas acrescente `, TrocarSenhaIn`.)

- [ ] **Step 6: Rodar e ver passar (suíte backend inteira)**

Run: `docker compose exec -T backend python -m pytest -q`
Expected: PASS (todos: auth + acesso).

- [ ] **Step 7: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/app/api/usuarios.py backend/app/schemas/auth.py backend/app/api/auth.py backend/tests/test_acesso.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): redefinir senha (admin) e POST /auth/trocar-senha (proprio usuario)"
```
Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 7: Frontend — `User.funcao` + helper `isAdmin`

**Files:**
- Modify: `frontend/src/auth/AuthContext.tsx` (campo `funcao` na interface `User`)
- Modify: `frontend/src/auth/AuthContext.test.tsx` (ME ganha `funcao`)
- Create: `frontend/src/auth/roles.ts`
- Test: `frontend/src/auth/roles.test.ts`

- [ ] **Step 1: Teste que falha** — crie `frontend/src/auth/roles.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { isAdmin } from './roles'
import { type User } from './AuthContext'

const admin: User = { id: 1, nome: null, login: 'a', email: null, funcao_id: 1, funcao: 'Administrador' }
const comum: User = { id: 2, nome: null, login: 'b', email: null, funcao_id: 2, funcao: 'Expedição' }

describe('isAdmin', () => {
  it('true para Administrador', () => expect(isAdmin(admin)).toBe(true))
  it('false para outra função', () => expect(isAdmin(comum)).toBe(false))
  it('false para null', () => expect(isAdmin(null)).toBe(false))
})
```

- [ ] **Step 2: Rodar e ver falhar**

Run (em `frontend/`): `npm run test -- roles`
Expected: FAIL (módulo `./roles` não existe).

- [ ] **Step 3: Adicionar `funcao` à interface `User`** — em `frontend/src/auth/AuthContext.tsx`, na interface `User`, adicione o campo:

```ts
export interface User {
  id: number
  nome: string | null
  login: string
  email: string | null
  funcao_id: number | null
  funcao: string | null
}
```

- [ ] **Step 4: Criar `roles.ts`** — `frontend/src/auth/roles.ts`:

```ts
import { type User } from './AuthContext'

export const FUNCAO_ADMIN = 'Administrador'

export function isAdmin(user: User | null): boolean {
  return user?.funcao === FUNCAO_ADMIN
}
```

- [ ] **Step 5: Atualizar o ME do teste do AuthContext** — em `frontend/src/auth/AuthContext.test.tsx`, troque a constante `ME` para incluir `funcao`:

```tsx
const ME = { id: 1, nome: 'Erick', login: 'erick', email: null, funcao_id: 1, funcao: 'Administrador' }
```

- [ ] **Step 6: Rodar e ver passar**

Run: `npm run test -- roles AuthContext` e depois `npx tsc -b`
Expected: PASS (roles 3 testes; AuthContext 5 testes) e tsc sem erros.

- [ ] **Step 7: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/auth/roles.ts frontend/src/auth/roles.test.ts frontend/src/auth/AuthContext.tsx frontend/src/auth/AuthContext.test.tsx
git -C /d/GitHub/GestorHS commit -m "feat(frontend): User.funcao + helper isAdmin"
```
Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 8: Frontend — módulo de API de acesso

**Files:**
- Create: `frontend/src/app/acesso/api.ts`
- Test: `frontend/src/app/acesso/api.test.ts`

- [ ] **Step 1: Teste que falha** — crie `frontend/src/app/acesso/api.test.ts`:

```ts
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { listarUsuarios, criarUsuario, excluirUsuario } from './api'
import { setTokens } from '../../lib/auth-storage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

const ITEM = { id: 1, nome: null, login: 'a', email: null, funcao_id: null, funcao: null, precisa_redefinir_senha: false }

describe('acesso/api', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    setTokens({ access_token: 't', refresh_token: 'r' })
  })

  it('listarUsuarios faz GET em /usuarios', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse([ITEM]))
    vi.stubGlobal('fetch', f)
    const r = await listarUsuarios()
    expect(String(f.mock.calls[0][0])).toContain('/usuarios')
    expect(r[0].login).toBe('a')
  })

  it('criarUsuario faz POST com o corpo', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse(ITEM))
    vi.stubGlobal('fetch', f)
    await criarUsuario({ login: 'novo', senha: '12345678' })
    expect(f.mock.calls[0][1].method).toBe('POST')
    expect(String(f.mock.calls[0][1].body)).toContain('novo')
  })

  it('excluirUsuario resolve no 204 com DELETE', async () => {
    const f = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', f)
    await expect(excluirUsuario(5)).resolves.toBeUndefined()
    expect(f.mock.calls[0][1].method).toBe('DELETE')
  })

  it('excluirUsuario lança ApiError em falha', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ detail: 'não é possível excluir o próprio usuário' }, 400))
    vi.stubGlobal('fetch', f)
    await expect(excluirUsuario(5)).rejects.toMatchObject({ status: 400 })
  })
})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm run test -- acesso/api`
Expected: FAIL (módulo não existe).

- [ ] **Step 3: Implementar** — crie `frontend/src/app/acesso/api.ts`:

```ts
import { apiJson, apiFetch, ApiError } from '../../lib/api'

export interface Funcao {
  id: number
  descricao: string
}

export interface UsuarioItem {
  id: number
  nome: string | null
  login: string
  email: string | null
  funcao_id: number | null
  funcao: string | null
  precisa_redefinir_senha: boolean
}

export interface UsuarioCreatePayload {
  nome?: string | null
  login: string
  email?: string | null
  senha: string
  funcao_id?: number | null
}

export interface UsuarioUpdatePayload {
  nome?: string | null
  email?: string | null
  funcao_id?: number | null
  login?: string
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

export function listarFuncoes(): Promise<Funcao[]> {
  return apiJson<Funcao[]>('/funcoes')
}

export function listarUsuarios(): Promise<UsuarioItem[]> {
  return apiJson<UsuarioItem[]>('/usuarios')
}

export function criarUsuario(payload: UsuarioCreatePayload): Promise<UsuarioItem> {
  return apiJson<UsuarioItem>('/usuarios', { method: 'POST', body: JSON.stringify(payload) })
}

export function atualizarUsuario(id: number, payload: UsuarioUpdatePayload): Promise<UsuarioItem> {
  return apiJson<UsuarioItem>(`/usuarios/${id}`, { method: 'PATCH', body: JSON.stringify(payload) })
}

export function excluirUsuario(id: number): Promise<void> {
  return apiVoid(`/usuarios/${id}`, { method: 'DELETE' })
}

export function redefinirSenha(id: number, nova_senha: string): Promise<void> {
  return apiVoid(`/usuarios/${id}/redefinir-senha`, { method: 'POST', body: JSON.stringify({ nova_senha }) })
}

export function trocarMinhaSenha(senha_atual: string, nova_senha: string): Promise<void> {
  return apiVoid('/auth/trocar-senha', { method: 'POST', body: JSON.stringify({ senha_atual, nova_senha }) })
}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `npm run test -- acesso/api` e `npx tsc -b`
Expected: PASS (4 testes); tsc limpo.

- [ ] **Step 5: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/app/acesso/api.ts frontend/src/app/acesso/api.test.ts
git -C /d/GitHub/GestorHS commit -m "feat(frontend): modulo de API de acesso (usuarios, funcoes, senha)"
```
Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 9: Frontend — ícones, gating da Sidebar e dropdown da Topbar

**Files:**
- Modify: `frontend/src/components/ui/icons.tsx` (adiciona `IconUsers`, `IconUser`)
- Modify: `frontend/src/layout/Sidebar.tsx` (item admin-only + correção do "active")
- Test: `frontend/src/layout/Sidebar.test.tsx`
- Modify: `frontend/src/layout/Topbar.tsx` (avatar vira dropdown)

- [ ] **Step 1: Adicionar ícones** — adicione ao fim de `frontend/src/components/ui/icons.tsx` (antes de nada, mantenha o existente):

```tsx
export function IconUsers({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a4 4 0 00-3-3.87M9 20H4v-2a4 4 0 013-3.87m3.5-2.13a4 4 0 10-3-7.74 4 4 0 003 7.74zm6 0a4 4 0 10-3-7.74" />
    </svg>
  )
}

export function IconUser({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 12a4 4 0 100-8 4 4 0 000 8zm-7 8a7 7 0 0114 0" />
    </svg>
  )
}
```

- [ ] **Step 2: Teste de gating que falha** — crie `frontend/src/layout/Sidebar.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

interface FakeUser {
  funcao: string | null
}
let mockUser: FakeUser | null = null
vi.mock('../auth/AuthContext', () => ({ useAuth: () => ({ user: mockUser }) }))

import { Sidebar } from './Sidebar'

describe('Sidebar (gating por função)', () => {
  beforeEach(() => {
    mockUser = null
  })

  it('esconde "Usuários" para não-admin', () => {
    mockUser = { funcao: 'Expedição' }
    render(
      <MemoryRouter>
        <Sidebar collapsed={false} />
      </MemoryRouter>,
    )
    expect(screen.queryByText('Usuários')).toBeNull()
    expect(screen.getByText('Dashboard')).toBeInTheDocument()
  })

  it('mostra "Usuários" para Administrador', () => {
    mockUser = { funcao: 'Administrador' }
    render(
      <MemoryRouter>
        <Sidebar collapsed={false} />
      </MemoryRouter>,
    )
    expect(screen.getByText('Usuários')).toBeInTheDocument()
  })
})
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `npm run test -- Sidebar`
Expected: FAIL (Sidebar ainda não filtra/usa auth — "Usuários" não existe ou aparece sempre).

- [ ] **Step 4: Reescrever a Sidebar** — substitua `frontend/src/layout/Sidebar.tsx`:

```tsx
import { type ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { cn } from '../lib/utils'
import { useAuth } from '../auth/AuthContext'
import { isAdmin } from '../auth/roles'
import { IconDashboard, IconUsers } from '../components/ui/icons'

interface NavItem {
  label: string
  icon: ReactNode
  to: string
  adminOnly?: boolean
}

const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', icon: <IconDashboard />, to: '/app' },
  { label: 'Usuários', icon: <IconUsers />, to: '/app/usuarios', adminOnly: true },
]

export function Sidebar({ collapsed }: { collapsed: boolean }) {
  const location = useLocation()
  const { user } = useAuth()
  const itens = NAV_ITEMS.filter((item) => !item.adminOnly || isAdmin(user))

  return (
    <aside
      className={cn(
        'flex flex-col shrink-0 bg-background-sidebar border-r border-border',
        'transition-[width] duration-300 ease-in-out overflow-hidden',
        collapsed ? 'w-18' : 'w-64',
      )}
    >
      <div className={cn('flex h-16 shrink-0 items-center border-b border-border', collapsed ? 'justify-center px-0' : 'px-5')}>
        {collapsed ? (
          <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-primary/15">
            <span className="text-sm font-bold text-primary">G</span>
          </div>
        ) : (
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-primary/15 flex items-center justify-center shrink-0">
              <span className="text-sm font-bold text-primary">G</span>
            </div>
            <span className="font-bold text-slate-100 text-base tracking-tight">GestorHS</span>
          </div>
        )}
      </div>

      <nav className="flex-1 px-2 py-4 space-y-1">
        {itens.map((item) => {
          const active =
            item.to === '/app'
              ? location.pathname === '/app'
              : location.pathname === item.to || location.pathname.startsWith(item.to + '/')
          return (
            <Link
              key={item.to}
              to={item.to}
              title={collapsed ? item.label : undefined}
              className={cn(
                'relative group flex items-center w-full rounded-lg text-sm font-medium transition-all duration-200',
                collapsed ? 'justify-center px-0 py-2.5 mx-1' : 'gap-3 px-3 py-2',
                active
                  ? cn('bg-primary/10 text-primary font-semibold', !collapsed && 'shadow-[inset_2px_0_0_#10b981] pl-2.5')
                  : cn(!collapsed && 'pl-2.5', 'text-slate-400 dark:text-slate-500 hover:bg-background-elevated hover:text-slate-100'),
              )}
            >
              {item.icon}
              {!collapsed && <span className="truncate">{item.label}</span>}
              {collapsed && (
                <span className="pointer-events-none absolute left-full ml-3 z-50 whitespace-nowrap rounded-lg bg-background-surface border border-border px-2.5 py-1.5 text-xs font-medium text-slate-200 shadow-lg opacity-0 group-hover:opacity-100 transition-opacity duration-150">
                  {item.label}
                </span>
              )}
            </Link>
          )
        })}
      </nav>
    </aside>
  )
}
```

- [ ] **Step 5: Rodar e ver passar**

Run: `npm run test -- Sidebar`
Expected: PASS (2 testes).

- [ ] **Step 6: Topbar com dropdown no avatar** — substitua `frontend/src/layout/Topbar.tsx`:

```tsx
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { cn } from '../lib/utils'
import { useAuth } from '../auth/AuthContext'
import { IconMenu, IconSun, IconMoon, IconLogout, IconUser } from '../components/ui/icons'

function iniciais(nome: string | null, login: string): string {
  const base = (nome ?? login).trim()
  const partes = base.split(/\s+/)
  if (partes.length >= 2) return (partes[0][0] + partes[1][0]).toUpperCase()
  return base.slice(0, 2).toUpperCase()
}

interface TopbarProps {
  dark: boolean
  onToggleTheme: () => void
  onToggleSidebar: () => void
}

const iconBtn = 'rounded-lg p-2 text-slate-400 hover:bg-background-elevated hover:text-slate-100 transition-colors duration-200'

export function Topbar({ dark, onToggleTheme, onToggleSidebar }: TopbarProps) {
  const { user, logout } = useAuth()
  const [aberto, setAberto] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setAberto(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-border bg-background-sidebar px-4 md:px-6">
      <button className={iconBtn} onClick={onToggleSidebar} aria-label="Alternar menu">
        <IconMenu />
      </button>

      <div className="flex items-center gap-2">
        <button className={iconBtn} onClick={onToggleTheme} aria-label="Alternar tema">
          {dark ? <IconSun /> : <IconMoon />}
        </button>

        <div className="relative" ref={ref}>
          <button
            onClick={() => setAberto((o) => !o)}
            aria-label="Menu do usuário"
            className="w-8 h-8 rounded-full bg-gradient-to-br from-primary-400 to-primary-700 flex items-center justify-center text-white text-xs font-bold shadow-sm"
          >
            {user ? iniciais(user.nome, user.login) : '?'}
          </button>
          {aberto && (
            <div className="absolute right-0 top-full mt-2 w-48 rounded-xl bg-background-surface border border-border shadow-2xl z-50 overflow-hidden">
              <Link
                to="/app/conta"
                onClick={() => setAberto(false)}
                className="flex items-center gap-2.5 px-3 py-2.5 text-sm text-slate-300 hover:bg-background-elevated transition-colors"
              >
                <IconUser className="w-4 h-4" />
                Minha conta
              </Link>
              <button
                onClick={() => {
                  setAberto(false)
                  logout()
                }}
                className={cn(
                  'w-full flex items-center gap-2.5 px-3 py-2.5 text-sm text-danger hover:bg-danger/10 transition-colors text-left border-t border-border',
                )}
              >
                <IconLogout className="w-4 h-4" />
                Sair
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
```

- [ ] **Step 7: Verificar tudo**

Run: `npm run test` (suíte inteira), `npx tsc -b`, `npm run lint`
Expected: tudo verde/limpo.

- [ ] **Step 8: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/components/ui/icons.tsx frontend/src/layout/Sidebar.tsx frontend/src/layout/Sidebar.test.tsx frontend/src/layout/Topbar.tsx
git -C /d/GitHub/GestorHS commit -m "feat(frontend): nav gated por funcao + dropdown do avatar (Minha conta/Sair)"
```
Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 10: Frontend — página de Usuários (lista + modais)

Visual (sem testes unitários). Verificação = tsc + lint.

**Files:**
- Create: `frontend/src/app/acesso/UsuarioFormModal.tsx`
- Create: `frontend/src/app/acesso/RedefinirSenhaModal.tsx`
- Create: `frontend/src/app/acesso/UsuariosPage.tsx`

- [ ] **Step 1: Modal de formulário** — crie `frontend/src/app/acesso/UsuarioFormModal.tsx`:

```tsx
import { useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { ApiError } from '../../lib/api'
import { criarUsuario, atualizarUsuario, type UsuarioItem, type Funcao } from './api'

interface Props {
  funcoes: Funcao[]
  usuario: UsuarioItem | null
  onClose: () => void
  onSalvo: () => void
}

export function UsuarioFormModal({ funcoes, usuario, onClose, onSalvo }: Props) {
  const editando = usuario !== null
  const [nome, setNome] = useState(usuario?.nome ?? '')
  const [login, setLogin] = useState(usuario?.login ?? '')
  const [email, setEmail] = useState(usuario?.email ?? '')
  const [senha, setSenha] = useState('')
  const [funcaoId, setFuncaoId] = useState(usuario?.funcao_id ? String(usuario.funcao_id) : '')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setErro('')
    setEnviando(true)
    try {
      const funcao_id = funcaoId ? Number(funcaoId) : null
      if (usuario) {
        await atualizarUsuario(usuario.id, { nome, email, funcao_id, login })
      } else {
        await criarUsuario({ nome, login, email, senha, funcao_id })
      }
      onSalvo()
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao salvar')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={editando ? 'Editar usuário' : 'Novo usuário'}
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors"
          >
            Cancelar
          </button>
          <button
            type="submit"
            form="form-usuario"
            disabled={enviando}
            className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all"
          >
            Salvar
          </button>
        </>
      }
    >
      <form id="form-usuario" className="space-y-4" onSubmit={onSubmit}>
        <Input id="nome" label="Nome" value={nome} onChange={(e) => setNome(e.target.value)} />
        <Input id="login" label="Login" value={login} onChange={(e) => setLogin(e.target.value)} required maxLength={20} />
        <Input id="email" label="E-mail" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        {!editando && (
          <Input
            id="senha"
            label="Senha (mín. 8)"
            type="password"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            required
            minLength={8}
          />
        )}
        <Select id="funcao" label="Função" value={funcaoId} onChange={(e) => setFuncaoId(e.target.value)}>
          <option value="">— sem função —</option>
          {funcoes.map((f) => (
            <option key={f.id} value={f.id}>
              {f.descricao}
            </option>
          ))}
        </Select>
        {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      </form>
    </Modal>
  )
}
```

- [ ] **Step 2: Modal de redefinir senha** — crie `frontend/src/app/acesso/RedefinirSenhaModal.tsx`:

```tsx
import { useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { ApiError } from '../../lib/api'
import { redefinirSenha, type UsuarioItem } from './api'

interface Props {
  usuario: UsuarioItem
  onClose: () => void
  onSalvo: () => void
}

export function RedefinirSenhaModal({ usuario, onClose, onSalvo }: Props) {
  const [nova, setNova] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setErro('')
    setEnviando(true)
    try {
      await redefinirSenha(usuario.id, nova)
      onSalvo()
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao redefinir')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={`Redefinir senha — ${usuario.login}`}
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors"
          >
            Cancelar
          </button>
          <button
            type="submit"
            form="form-senha"
            disabled={enviando}
            className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all"
          >
            Salvar
          </button>
        </>
      }
    >
      <form id="form-senha" className="space-y-4" onSubmit={onSubmit}>
        <Input
          id="nova-senha"
          label="Nova senha (mín. 8)"
          type="password"
          value={nova}
          onChange={(e) => setNova(e.target.value)}
          required
          minLength={8}
        />
        {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      </form>
    </Modal>
  )
}
```

- [ ] **Step 3: Página de Usuários** — crie `frontend/src/app/acesso/UsuariosPage.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Spinner } from '../../components/ui/Spinner'
import { ApiError } from '../../lib/api'
import { useAuth } from '../../auth/AuthContext'
import { isAdmin } from '../../auth/roles'
import { listarUsuarios, listarFuncoes, excluirUsuario, type UsuarioItem, type Funcao } from './api'
import { UsuarioFormModal } from './UsuarioFormModal'
import { RedefinirSenhaModal } from './RedefinirSenhaModal'

export function UsuariosPage() {
  const { user } = useAuth()
  const [usuarios, setUsuarios] = useState<UsuarioItem[] | null>(null)
  const [funcoes, setFuncoes] = useState<Funcao[]>([])
  const [erro, setErro] = useState('')
  const [formAberto, setFormAberto] = useState(false)
  const [editando, setEditando] = useState<UsuarioItem | null>(null)
  const [senhaDe, setSenhaDe] = useState<UsuarioItem | null>(null)

  async function carregar() {
    setErro('')
    try {
      const [us, fs] = await Promise.all([listarUsuarios(), listarFuncoes()])
      setUsuarios(us)
      setFuncoes(fs)
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao carregar')
      setUsuarios([])
    }
  }

  useEffect(() => {
    if (isAdmin(user)) void carregar()
  }, [user])

  if (!isAdmin(user)) {
    return (
      <div className="px-4 md:px-6 py-6">
        <p className="text-sm text-slate-400">Acesso restrito a administradores.</p>
      </div>
    )
  }

  async function onExcluir(u: UsuarioItem) {
    if (!window.confirm(`Excluir o usuário "${u.login}"?`)) return
    try {
      await excluirUsuario(u.id)
      await carregar()
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao excluir')
    }
  }

  return (
    <div className="px-4 md:px-6 py-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-extrabold text-slate-100">Usuários</h1>
        <Button
          onClick={() => {
            setEditando(null)
            setFormAberto(true)
          }}
        >
          Novo usuário
        </Button>
      </div>

      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}

      {usuarios === null ? (
        <div className="flex justify-center py-12">
          <Spinner className="w-8 h-8" />
        </div>
      ) : usuarios.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum usuário cadastrado.</p>
      ) : (
        <Table
          head={
            <>
              <TH>Nome</TH>
              <TH>Login</TH>
              <TH>E-mail</TH>
              <TH>Função</TH>
              <TH>Ações</TH>
            </>
          }
        >
          {usuarios.map((u) => (
            <tr key={u.id} className="hover:bg-background-elevated transition-colors">
              <TD>{u.nome ?? '—'}</TD>
              <TD>{u.login}</TD>
              <TD>{u.email ?? '—'}</TD>
              <TD>
                {u.funcao ? <Badge tone={u.funcao === 'Administrador' ? 'primary' : 'neutral'}>{u.funcao}</Badge> : '—'}
              </TD>
              <TD>
                <div className="flex gap-3">
                  <button
                    onClick={() => {
                      setEditando(u)
                      setFormAberto(true)
                    }}
                    className="text-xs text-primary hover:underline"
                  >
                    Editar
                  </button>
                  <button onClick={() => setSenhaDe(u)} className="text-xs text-slate-400 hover:text-slate-200">
                    Senha
                  </button>
                  <button onClick={() => onExcluir(u)} className="text-xs text-danger hover:underline">
                    Excluir
                  </button>
                </div>
              </TD>
            </tr>
          ))}
        </Table>
      )}

      {formAberto && (
        <UsuarioFormModal
          funcoes={funcoes}
          usuario={editando}
          onClose={() => setFormAberto(false)}
          onSalvo={() => {
            setFormAberto(false)
            void carregar()
          }}
        />
      )}

      {senhaDe && (
        <RedefinirSenhaModal usuario={senhaDe} onClose={() => setSenhaDe(null)} onSalvo={() => setSenhaDe(null)} />
      )}
    </div>
  )
}
```

- [ ] **Step 4: Verificar**

Run: `npx tsc -b` e `npm run lint`
Expected: sem erros.

- [ ] **Step 5: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/app/acesso/UsuarioFormModal.tsx frontend/src/app/acesso/RedefinirSenhaModal.tsx frontend/src/app/acesso/UsuariosPage.tsx
git -C /d/GitHub/GestorHS commit -m "feat(frontend): pagina de Usuarios (lista, criar/editar, redefinir senha, excluir)"
```
Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 11: Frontend — página Minha Conta (trocar senha)

Visual (sem testes unitários). Verificação = tsc + lint.

**Files:**
- Create: `frontend/src/app/pages/MinhaContaPage.tsx`

- [ ] **Step 1: Criar a página** — `frontend/src/app/pages/MinhaContaPage.tsx`:

```tsx
import { useState, type FormEvent } from 'react'
import { Input } from '../../components/ui/Input'
import { ApiError } from '../../lib/api'
import { trocarMinhaSenha } from '../acesso/api'

export function MinhaContaPage() {
  const [atual, setAtual] = useState('')
  const [nova, setNova] = useState('')
  const [confirma, setConfirma] = useState('')
  const [msg, setMsg] = useState<{ tipo: 'ok' | 'erro'; texto: string } | null>(null)
  const [enviando, setEnviando] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setMsg(null)
    if (nova !== confirma) {
      setMsg({ tipo: 'erro', texto: 'A confirmação não confere' })
      return
    }
    setEnviando(true)
    try {
      await trocarMinhaSenha(atual, nova)
      setMsg({ tipo: 'ok', texto: 'Senha alterada com sucesso' })
      setAtual('')
      setNova('')
      setConfirma('')
    } catch (err) {
      setMsg({ tipo: 'erro', texto: err instanceof ApiError ? err.message : 'Falha ao alterar' })
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="px-4 md:px-6 py-6 max-w-md">
      <h1 className="text-2xl font-extrabold text-slate-100 mb-6">Minha conta</h1>
      <div className="rounded-2xl bg-background-surface border border-border p-6">
        <h2 className="text-sm font-semibold text-slate-100 mb-4">Trocar senha</h2>
        <form className="space-y-4" onSubmit={onSubmit}>
          <Input id="atual" label="Senha atual" type="password" value={atual} onChange={(e) => setAtual(e.target.value)} required />
          <Input id="nova" label="Nova senha (mín. 8)" type="password" value={nova} onChange={(e) => setNova(e.target.value)} required minLength={8} />
          <Input
            id="confirma"
            label="Confirmar nova senha"
            type="password"
            value={confirma}
            onChange={(e) => setConfirma(e.target.value)}
            required
            minLength={8}
          />
          {msg && (
            <div
              className={
                msg.tipo === 'ok'
                  ? 'rounded-lg bg-primary/10 border border-primary/20 px-3 py-2.5 text-sm text-primary'
                  : 'rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger'
              }
            >
              {msg.texto}
            </div>
          )}
          <button
            type="submit"
            disabled={enviando}
            className="w-full py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-60 transition-all"
          >
            Salvar
          </button>
        </form>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verificar**

Run: `npx tsc -b` e `npm run lint`
Expected: sem erros.

- [ ] **Step 3: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/app/pages/MinhaContaPage.tsx
git -C /d/GitHub/GestorHS commit -m "feat(frontend): pagina Minha conta (trocar senha)"
```
Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 12: Frontend — rotas e integração final

**Files:**
- Modify: `frontend/src/app/routes.tsx`

- [ ] **Step 1: Adicionar as rotas** — substitua `frontend/src/app/routes.tsx`:

```tsx
import { Routes, Route, Navigate } from 'react-router-dom'
import { MainLayout } from '../layout/MainLayout'
import { DashboardPage } from './pages/DashboardPage'
import { MinhaContaPage } from './pages/MinhaContaPage'
import { UsuariosPage } from './acesso/UsuariosPage'

export default function AppRoutes() {
  return (
    <MainLayout>
      <Routes>
        <Route index element={<DashboardPage />} />
        <Route path="usuarios" element={<UsuariosPage />} />
        <Route path="conta" element={<MinhaContaPage />} />
        <Route path="*" element={<Navigate to="/app" replace />} />
      </Routes>
    </MainLayout>
  )
}
```

- [ ] **Step 2: Suíte completa + build**

Run (em `frontend/`): `npm run test`, `npx tsc -b`, `npm run lint`, `npm run build`
Expected: testes verdes (Fase 0 + roles + acesso/api + Sidebar), tsc/lint limpos, build OK.

- [ ] **Step 3: Verificação manual E2E** (backend no ar: `docker compose up -d`; admin `admin`/`GestorHS@2026`; `frontend/.env` com `VITE_API_URL=http://localhost:8000`)

Run: `npm run dev` e abra a URL.
Verifique:
1. Login como admin → a Sidebar mostra "Usuários".
2. "Usuários" → lista carrega; criar um usuário (com função e senha) aparece na lista.
3. Editar o usuário (trocar função) reflete; "Senha" redefine; "Excluir" remove (com confirmação).
4. Guardas: tentar excluir a si mesmo → erro exibido; login duplicado ao criar → erro exibido.
5. Avatar (dropdown) → "Minha conta" abre `/app/conta`; trocar a própria senha com sucesso; senha atual errada → erro.
6. Logout pelo dropdown → volta a `/login`.
7. (Opcional, se houver um usuário não-admin) logar como ele → "Usuários" some; acessar `/app/usuarios` direto → "Acesso restrito".

- [ ] **Step 4: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/app/routes.tsx
git -C /d/GitHub/GestorHS commit -m "feat(frontend): rotas /app/usuarios e /app/conta"
```
Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

## Notas para o executor

- **Backend roda em container:** garanta `docker compose up -d` antes dos `pytest`. O `--reload` recarrega a API ao editar `backend/`, mas os testes rodam via `docker compose exec` independentemente.
- **Ordem de imports no `usuarios.py`:** as Tasks 3→4→6 vão acrescentando símbolos ao import de `app.schemas.acesso`. O estado final deve ser `from app.schemas.acesso import UsuarioListOut, UsuarioCreate, UsuarioUpdate, RedefinirSenhaIn`.
- **`verbatimModuleSyntax`:** sempre `import { type X }` para tipos (os exemplos seguem isso).
- **`window.confirm`** é usado de propósito na exclusão (evita um Modal de confirmação dedicado nesta fase). Se o lint reclamar de `no-restricted-globals`/`no-alert` (não deve, com a config atual), troque por um Modal de confirmação simples.
- **`react-refresh/only-export-components`:** `roles.ts` fica em arquivo próprio justamente para não adicionar exports não-componentes ao `AuthContext.tsx`.
- **Decomposição:** este é o sub-projeto 1A. O 1B (Cadastros base) virá em spec+plano próprios e reusará o módulo de API tipado, o padrão lista+modal e o gating já estabelecidos aqui.
