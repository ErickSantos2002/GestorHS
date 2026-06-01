# Fundação do Backend + Autenticação — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Subir um backend FastAPI conectado ao banco do GestorHS, com login JWT para equipe e portal, senhas com hash e suporte a funções (papéis) — tudo testado.

**Architecture:** FastAPI + SQLAlchemy (estilo clássico `declarative_base()` + `Column`, igual ao tiny-integrador) + Alembic para migrações + JWT. Layout espelha o tiny-integrador: `app/core`, `app/models`, `app/schemas`, `app/api`. Os testes usam SQLite em memória (os modelos de auth só usam tipos portáveis), então não dependem do Postgres real.

**Tech Stack:** Python, FastAPI, SQLAlchemy, psycopg2-binary, Alembic, passlib[argon2], python-jose[cryptography], pydantic-settings, pytest, httpx.

**Pré-requisitos:** Python 3.11+ instalado. O banco `gestorhs-banco` (porta 9998) já existe e já tem as tabelas `usuarios`, `usuarios_cliente`, `clientes` migradas. Este plano **altera** essas tabelas (não as recria) e **cria** a tabela `funcoes`.

**Decisões de segurança embutidas** (do review de segurança, ver design §10):
- `senha` passa de `varchar(12)` para `text` em `usuarios` e `usuarios_cliente`; guardamos só hash argon2.
- Os valores legados de senha são invalidados e marcados para redefinição (`precisa_redefinir_senha = true`).
- `usuarios_cliente` ganha `UNIQUE (cliente, login)`.

**Convenção de nomes** (usada em todas as tasks):
- Hashing: `hash_senha(senha) -> str`, `verificar_senha(senha, hash) -> bool`
- JWT: `criar_access_token(sub, tipo)`, `criar_refresh_token(sub, tipo)`, `decodificar_token(token) -> dict`
- Modelos: `Funcao` (`funcoes`), `Usuario` (`usuarios`), `UsuarioCliente` (`usuarios_cliente`)
- Schemas: `LoginRequest`, `Token`, `UsuarioOut`, `RefreshRequest`
- Dependências: `get_db`, `get_current_usuario`, `get_current_cliente`, `require_funcao(...)`

---

### Task 1: Scaffold do projeto, dependências e configuração

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`
- Create: `backend/app/__init__.py` (vazio)
- Create: `backend/app/core/__init__.py` (vazio)
- Create: `backend/app/core/config.py`
- Create: `backend/tests/__init__.py` (vazio)
- Create: `backend/tests/test_config.py`

- [ ] **Step 1: Criar `backend/requirements.txt`**

```
fastapi
uvicorn[standard]
sqlalchemy
psycopg2-binary
alembic
pydantic
pydantic-settings
python-dotenv
passlib[argon2]
python-jose[cryptography]
pytest
httpx
```

- [ ] **Step 2: Criar `backend/.env.example`** (modelo — o `.env` real fica fora do git)

```
DATABASE_URL=postgresql+psycopg2://administrador:TROCAR_SENHA@62.72.11.28:9998/gestorhs-banco
JWT_SECRET_KEY=troque-por-uma-chave-aleatoria-de-32-bytes
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

- [ ] **Step 3: Escrever o teste que falha** em `backend/tests/test_config.py`

```python
import os

def test_settings_carrega_do_ambiente(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg2://u:p@localhost:5432/db")
    monkeypatch.setenv("JWT_SECRET_KEY", "segredo-de-teste")
    # importa tardio para pegar o ambiente do monkeypatch
    from app.core.config import Settings
    s = Settings()
    assert s.DATABASE_URL.endswith("/db")
    assert s.JWT_SECRET_KEY == "segredo-de-teste"
    assert s.JWT_ALGORITHM == "HS256"
    assert s.ACCESS_TOKEN_EXPIRE_MINUTES == 30
```

- [ ] **Step 4: Rodar o teste e ver falhar**

Run (a partir de `backend/`): `python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.config'`

- [ ] **Step 5: Criar os arquivos `__init__.py` vazios** (`app/__init__.py`, `app/core/__init__.py`, `tests/__init__.py`)

- [ ] **Step 6: Implementar `backend/app/core/config.py`** (mesmo estilo do tiny-integrador)

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
```

- [ ] **Step 7: Rodar o teste e ver passar**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add backend/requirements.txt backend/.env.example backend/app backend/tests
git commit -m "feat(backend): scaffold do projeto e configuracao via pydantic-settings"
```

---

### Task 2: Sessão de banco de dados

**Files:**
- Create: `backend/app/models/__init__.py` (vazio)
- Create: `backend/app/models/database.py`

- [ ] **Step 1: Implementar `backend/app/models/database.py`** (espelha o tiny-integrador + adiciona `get_db`)

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

Base = declarative_base()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 2: Criar `backend/app/models/__init__.py`** (vazio por enquanto)

- [ ] **Step 3: Verificar que importa sem erro** (não toca no banco real)

Run: `python -c "from app.models.database import Base, get_db, SessionLocal; print('ok')"`
Expected: imprime `ok` (exige `JWT_SECRET_KEY` e `DATABASE_URL` no `.env`; para esta verificação, um `.env` com valores quaisquer basta — nada conecta ainda)

- [ ] **Step 4: Commit**

```bash
git add backend/app/models
git commit -m "feat(backend): engine, Base e sessao do SQLAlchemy"
```

---

### Task 3: Modelos de Funcao, Usuario e UsuarioCliente

**Files:**
- Create: `backend/app/models/funcao.py`
- Create: `backend/app/models/usuario.py`
- Create: `backend/app/models/usuario_cliente.py`

> Mapeamos só as colunas relevantes para auth; as demais colunas das tabelas continuam existindo no banco e são ignoradas pelo ORM. O mapeamento completo vem nos planos de cadastros.

- [ ] **Step 1: Implementar `backend/app/models/funcao.py`**

```python
from sqlalchemy import Column, Integer, String
from app.models.database import Base


class Funcao(Base):
    __tablename__ = "funcoes"

    id = Column(Integer, primary_key=True, index=True)
    descricao = Column(String(100), nullable=False, unique=True)
```

- [ ] **Step 2: Implementar `backend/app/models/usuario.py`**

```python
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey
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
```

- [ ] **Step 3: Implementar `backend/app/models/usuario_cliente.py`**

```python
from sqlalchemy import Column, Integer, BigInteger, String, Text, Boolean, ForeignKey, UniqueConstraint
from app.models.database import Base


class UsuarioCliente(Base):
    __tablename__ = "usuarios_cliente"
    __table_args__ = (UniqueConstraint("cliente", "login", name="uq_usuarios_cliente_login"),)

    id = Column(Integer, primary_key=True, index=True)
    cliente = Column(BigInteger, ForeignKey("clientes.id"), nullable=False)
    nome = Column(String(100), nullable=True)
    login = Column(String(20), nullable=False)
    senha = Column(Text, nullable=False)            # hash argon2
    email = Column(String(200), nullable=True)
    precisa_redefinir_senha = Column(Boolean, nullable=False, default=False)
```

- [ ] **Step 4: Registrar os modelos em `backend/app/models/__init__.py`**

```python
from app.models.funcao import Funcao
from app.models.usuario import Usuario
from app.models.usuario_cliente import UsuarioCliente

__all__ = ["Funcao", "Usuario", "UsuarioCliente"]
```

- [ ] **Step 5: Verificar importação**

Run: `python -c "from app.models import Funcao, Usuario, UsuarioCliente; print('ok')"`
Expected: imprime `ok`

- [ ] **Step 6: Commit**

```bash
git add backend/app/models
git commit -m "feat(backend): modelos Funcao, Usuario e UsuarioCliente"
```

---

### Task 4: Hashing de senha

**Files:**
- Create: `backend/app/core/security.py`
- Create: `backend/tests/test_security.py`

- [ ] **Step 1: Escrever o teste que falha** em `backend/tests/test_security.py`

```python
from app.core.security import hash_senha, verificar_senha


def test_hash_difere_do_texto_puro():
    h = hash_senha("minhaSenha123")
    assert h != "minhaSenha123"
    assert len(h) > 20


def test_verificar_senha_correta_e_incorreta():
    h = hash_senha("minhaSenha123")
    assert verificar_senha("minhaSenha123", h) is True
    assert verificar_senha("errada", h) is False
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_security.py -v`
Expected: FAIL — `ImportError: cannot import name 'hash_senha'`

- [ ] **Step 3: Implementar o hashing em `backend/app/core/security.py`**

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_senha(senha: str) -> str:
    return pwd_context.hash(senha)


def verificar_senha(senha: str, hash_armazenado: str) -> bool:
    if not hash_armazenado:
        return False
    try:
        return pwd_context.verify(senha, hash_armazenado)
    except ValueError:
        # hash em formato inválido (ex.: valor legado) — nunca autentica
        return False
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_security.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/security.py backend/tests/test_security.py
git commit -m "feat(backend): hashing de senha com argon2"
```

---

### Task 5: Tokens JWT (access + refresh)

**Files:**
- Modify: `backend/app/core/security.py`
- Modify: `backend/tests/test_security.py`

- [ ] **Step 1: Acrescentar os testes que falham** ao fim de `backend/tests/test_security.py`

```python
import pytest
from jose import JWTError
from app.core.security import criar_access_token, criar_refresh_token, decodificar_token


def test_access_token_roundtrip():
    token = criar_access_token(sub="42", tipo="usuario")
    dados = decodificar_token(token)
    assert dados["sub"] == "42"
    assert dados["tipo"] == "usuario"
    assert dados["token_use"] == "access"


def test_refresh_token_marca_uso():
    token = criar_refresh_token(sub="7", tipo="cliente")
    dados = decodificar_token(token)
    assert dados["token_use"] == "refresh"
    assert dados["tipo"] == "cliente"


def test_token_invalido_levanta_erro():
    with pytest.raises(JWTError):
        decodificar_token("nao-e-um-token")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_security.py -v`
Expected: FAIL — `ImportError: cannot import name 'criar_access_token'`

- [ ] **Step 3: Acrescentar a lógica de JWT** ao fim de `backend/app/core/security.py`

```python
from datetime import datetime, timedelta, timezone
from jose import jwt
from app.core.config import settings


def _criar_token(sub: str, tipo: str, token_use: str, expira_em: timedelta) -> str:
    agora = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "tipo": tipo,            # "usuario" (equipe) ou "cliente" (portal)
        "token_use": token_use,  # "access" ou "refresh"
        "iat": agora,
        "exp": agora + expira_em,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def criar_access_token(sub: str, tipo: str) -> str:
    return _criar_token(sub, tipo, "access", timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))


def criar_refresh_token(sub: str, tipo: str) -> str:
    return _criar_token(sub, tipo, "refresh", timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))


def decodificar_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_security.py -v`
Expected: PASS (5 passed). Garanta um `.env` com `JWT_SECRET_KEY` ao rodar.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/security.py backend/tests/test_security.py
git commit -m "feat(backend): tokens JWT de access e refresh"
```

---

### Task 6: Schemas de autenticação

**Files:**
- Create: `backend/app/schemas/__init__.py` (vazio)
- Create: `backend/app/schemas/auth.py`

- [ ] **Step 1: Implementar `backend/app/schemas/auth.py`** (estilo Pydantic do tiny-integrador)

```python
from pydantic import BaseModel
from typing import Optional


class LoginRequest(BaseModel):
    login: str
    senha: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UsuarioOut(BaseModel):
    id: int
    nome: Optional[str]
    login: str
    email: Optional[str]
    funcao_id: Optional[int]

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Criar `backend/app/schemas/__init__.py`** (vazio)

- [ ] **Step 3: Verificar importação**

Run: `python -c "from app.schemas.auth import LoginRequest, Token, UsuarioOut, RefreshRequest; print('ok')"`
Expected: imprime `ok`

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas
git commit -m "feat(backend): schemas de autenticacao"
```

---

### Task 7: Infra de teste (conftest) e dependências de autorização

**Files:**
- Create: `backend/tests/conftest.py`
- Create: `backend/app/api/__init__.py` (vazio)
- Create: `backend/app/api/deps.py`

- [ ] **Step 1: Implementar `backend/tests/conftest.py`** (SQLite em memória + override de `get_db` + cliente HTTP)

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.database import Base, get_db
from app.models import Funcao, Usuario, UsuarioCliente  # registra as tabelas no metadata
from app.core.security import hash_senha


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    from app.main import app

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def usuario_admin(db_session):
    funcao = Funcao(descricao="Administrador")
    db_session.add(funcao)
    db_session.flush()
    u = Usuario(
        nome="Admin",
        login="admin",
        senha=hash_senha("senha123"),
        email="admin@hs.com",
        funcao_id=funcao.id,
        precisa_redefinir_senha=False,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u
```

- [ ] **Step 2: Implementar `backend/app/api/deps.py`**

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, UsuarioCliente
from app.core.security import decodificar_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

_cred_invalida = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Credenciais inválidas",
    headers={"WWW-Authenticate": "Bearer"},
)


def _payload_valido(token: str, tipo_esperado: str) -> dict:
    try:
        dados = decodificar_token(token)
    except JWTError:
        raise _cred_invalida
    if dados.get("token_use") != "access" or dados.get("tipo") != tipo_esperado:
        raise _cred_invalida
    return dados


def get_current_usuario(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> Usuario:
    dados = _payload_valido(token, "usuario")
    usuario = db.query(Usuario).filter(Usuario.id == int(dados["sub"])).first()
    if usuario is None:
        raise _cred_invalida
    return usuario


def get_current_cliente(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> UsuarioCliente:
    dados = _payload_valido(token, "cliente")
    cli = db.query(UsuarioCliente).filter(UsuarioCliente.id == int(dados["sub"])).first()
    if cli is None:
        raise _cred_invalida
    return cli


def require_funcao(*descricoes: str):
    def _checagem(usuario: Usuario = Depends(get_current_usuario), db: Session = Depends(get_db)) -> Usuario:
        from app.models import Funcao
        if usuario.funcao_id is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem função atribuída")
        funcao = db.query(Funcao).filter(Funcao.id == usuario.funcao_id).first()
        if funcao is None or funcao.descricao not in descricoes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado para sua função")
        return usuario
    return _checagem
```

- [ ] **Step 3: Criar `backend/app/api/__init__.py`** (vazio)

- [ ] **Step 4: Verificar importação**

Run: `python -c "from app.api.deps import get_current_usuario, get_current_cliente, require_funcao; print('ok')"`
Expected: imprime `ok`

- [ ] **Step 5: Commit**

```bash
git add backend/tests/conftest.py backend/app/api
git commit -m "test(backend): infra de teste (sqlite) e dependencias de autorizacao"
```

---

### Task 8: Rotas de autenticação e app principal

**Files:**
- Create: `backend/app/api/auth.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/test_auth.py`

- [ ] **Step 1: Escrever os testes que falham** em `backend/tests/test_auth.py`

```python
def test_login_sucesso_retorna_tokens(client, usuario_admin):
    r = client.post("/auth/login", json={"login": "admin", "senha": "senha123"})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["token_type"] == "bearer"
    assert corpo["access_token"]
    assert corpo["refresh_token"]


def test_login_senha_errada_401(client, usuario_admin):
    r = client.post("/auth/login", json={"login": "admin", "senha": "errada"})
    assert r.status_code == 401


def test_login_senha_legada_exige_redefinicao(client, db_session):
    from app.models import Usuario
    db_session.add(Usuario(nome="Velho", login="velho", senha="", precisa_redefinir_senha=True))
    db_session.commit()
    r = client.post("/auth/login", json={"login": "velho", "senha": "qualquer"})
    assert r.status_code == 403
    assert "redefin" in r.json()["detail"].lower()


def test_me_com_token(client, usuario_admin):
    tokens = client.post("/auth/login", json={"login": "admin", "senha": "senha123"}).json()
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert r.status_code == 200
    assert r.json()["login"] == "admin"


def test_me_sem_token_401(client):
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_refresh_gera_novo_access(client, usuario_admin):
    tokens = client.post("/auth/login", json={"login": "admin", "senha": "senha123"}).json()
    r = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200
    assert r.json()["access_token"]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_auth.py -v`
Expected: FAIL — `app.main` não existe ainda (erro de coleta)

- [ ] **Step 3: Implementar `backend/app/api/auth.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, UsuarioCliente
from app.core.security import (
    verificar_senha,
    criar_access_token,
    criar_refresh_token,
    decodificar_token,
)
from app.schemas.auth import LoginRequest, Token, RefreshRequest, UsuarioOut
from app.api.deps import get_current_usuario
from jose import JWTError

router = APIRouter(prefix="/auth", tags=["auth"])


def _autenticar(registro, senha: str):
    if registro is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")
    if registro.precisa_redefinir_senha:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Senha precisa ser redefinida")
    if not verificar_senha(senha, registro.senha):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")


@router.post("/login", response_model=Token)
def login(dados: LoginRequest, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.login == dados.login).first()
    _autenticar(usuario, dados.senha)
    return Token(
        access_token=criar_access_token(sub=str(usuario.id), tipo="usuario"),
        refresh_token=criar_refresh_token(sub=str(usuario.id), tipo="usuario"),
    )


@router.post("/login-portal", response_model=Token)
def login_portal(dados: LoginRequest, db: Session = Depends(get_db)):
    cli = db.query(UsuarioCliente).filter(UsuarioCliente.login == dados.login).first()
    _autenticar(cli, dados.senha)
    return Token(
        access_token=criar_access_token(sub=str(cli.id), tipo="cliente"),
        refresh_token=criar_refresh_token(sub=str(cli.id), tipo="cliente"),
    )


@router.get("/me", response_model=UsuarioOut)
def me(usuario: Usuario = Depends(get_current_usuario)):
    return usuario


@router.post("/refresh", response_model=Token)
def refresh(dados: RefreshRequest):
    try:
        payload = decodificar_token(dados.refresh_token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh inválido")
    if payload.get("token_use") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh inválido")
    sub, tipo = payload["sub"], payload["tipo"]
    return Token(
        access_token=criar_access_token(sub=sub, tipo=tipo),
        refresh_token=criar_refresh_token(sub=sub, tipo=tipo),
    )
```

- [ ] **Step 4: Implementar `backend/app/main.py`**

```python
from fastapi import FastAPI
from app.api import auth

app = FastAPI(title="GestorHS API")

app.include_router(auth.router)


@app.get("/health", tags=["infra"])
def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Rodar e ver passar**

Run: `python -m pytest tests/test_auth.py -v`
Expected: PASS (6 passed)

- [ ] **Step 6: Rodar a suíte inteira**

Run: `python -m pytest -v`
Expected: PASS (todos os testes das Tasks 1–8)

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/auth.py backend/app/main.py backend/tests/test_auth.py
git commit -m "feat(backend): rotas de login, me e refresh com JWT"
```

---

### Task 9: Migração Alembic — endurecimento de credenciais

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/0001_auth_hardening.py`

> Esta migração **altera** tabelas que já existem (criadas fora do Alembic) e **cria** `funcoes`. Não use autogenerate; o `upgrade()` abaixo é explícito.

- [ ] **Step 1: Inicializar o Alembic** (a partir de `backend/`)

Run: `python -m alembic init alembic`
Expected: cria `alembic.ini` e a pasta `alembic/`

- [ ] **Step 2: Apontar o Alembic para a `DATABASE_URL`** — substituir o `run_migrations_online` em `backend/alembic/env.py` para ler do settings (trecho relevante):

```python
from app.core.config import settings
from app.models.database import Base
from app.models import Funcao, Usuario, UsuarioCliente  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
target_metadata = Base.metadata
```

- [ ] **Step 3: Escrever a migração** em `backend/alembic/versions/0001_auth_hardening.py`

```python
"""auth hardening: funcoes, senha->text, unicidade e flag de redefinicao

Revision ID: 0001_auth_hardening
Revises:
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_auth_hardening"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # 1. Tabela de funções + seed
    op.create_table(
        "funcoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("descricao", sa.String(length=100), nullable=False, unique=True),
    )
    op.bulk_insert(
        sa.table("funcoes", sa.column("descricao", sa.String)),
        [
            {"descricao": "Administrador"},
            {"descricao": "Expedição"},
            {"descricao": "Laboratório"},
            {"descricao": "Comercial Pós-Vendas"},
        ],
    )

    # 2. usuarios: senha -> text, funcao_id, flag; invalida senhas legadas
    op.alter_column("usuarios", "senha", type_=sa.Text(), existing_nullable=False)
    op.add_column("usuarios", sa.Column("funcao_id", sa.Integer(), sa.ForeignKey("funcoes.id"), nullable=True))
    op.add_column("usuarios", sa.Column("precisa_redefinir_senha", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("UPDATE usuarios SET senha = '', precisa_redefinir_senha = true")

    # 3. usuarios_cliente: senha -> text, flag, unicidade (cliente, login); invalida legadas
    op.alter_column("usuarios_cliente", "senha", type_=sa.Text(), existing_nullable=False)
    op.add_column("usuarios_cliente", sa.Column("precisa_redefinir_senha", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_unique_constraint("uq_usuarios_cliente_login", "usuarios_cliente", ["cliente", "login"])
    op.execute("UPDATE usuarios_cliente SET senha = '', precisa_redefinir_senha = true")


def downgrade():
    op.drop_constraint("uq_usuarios_cliente_login", "usuarios_cliente", type_="unique")
    op.drop_column("usuarios_cliente", "precisa_redefinir_senha")
    op.drop_column("usuarios", "precisa_redefinir_senha")
    op.drop_column("usuarios", "funcao_id")
    op.drop_table("funcoes")
    # senha permanece como text (não revertendo para varchar(12) por segurança)
```

- [ ] **Step 4: Rodar a migração contra o banco real** (exige `.env` com `DATABASE_URL` válida)

Run: `python -m alembic upgrade head`
Expected: cria `funcoes` (com 4 papéis), altera `usuarios`/`usuarios_cliente`, e a tabela `alembic_version` passa a marcar `0001_auth_hardening`

- [ ] **Step 5: Conferir no banco**

Run: `python -c "from app.models.database import SessionLocal; from sqlalchemy import text; d=SessionLocal(); print(d.execute(text('select descricao from funcoes order by id')).fetchall())"`
Expected: `[('Administrador',), ('Expedição',), ('Laboratório',), ('Comercial Pós-Vendas',)]`

- [ ] **Step 6: Commit**

```bash
git add backend/alembic.ini backend/alembic
git commit -m "feat(backend): migracao de endurecimento de credenciais (funcoes, senha text, unicidade)"
```

---

### Task 10: Bootstrap de admin, execução e smoke test

**Files:**
- Create: `backend/app/scripts/__init__.py` (vazio)
- Create: `backend/app/scripts/criar_usuario.py`

- [ ] **Step 1: Implementar `backend/app/scripts/criar_usuario.py`** (cria/atualiza um usuário interno com senha em hash)

```python
"""Cria ou atualiza um usuário interno com senha em hash.

Uso: python -m app.scripts.criar_usuario <login> <senha> [funcao]
Ex.:  python -m app.scripts.criar_usuario admin SenhaForte! Administrador
"""
import sys
from app.models.database import SessionLocal
from app.models import Usuario, Funcao
from app.core.security import hash_senha


def main():
    if len(sys.argv) < 3:
        print("Uso: python -m app.scripts.criar_usuario <login> <senha> [funcao]")
        sys.exit(1)
    login, senha = sys.argv[1], sys.argv[2]
    funcao_desc = sys.argv[3] if len(sys.argv) > 3 else "Administrador"

    db = SessionLocal()
    try:
        funcao = db.query(Funcao).filter(Funcao.descricao == funcao_desc).first()
        if funcao is None:
            print(f"Função '{funcao_desc}' não encontrada. Rode a migração 0001 primeiro.")
            sys.exit(1)
        usuario = db.query(Usuario).filter(Usuario.login == login).first()
        if usuario is None:
            usuario = Usuario(login=login, nome=login)
            db.add(usuario)
        usuario.senha = hash_senha(senha)
        usuario.precisa_redefinir_senha = False
        usuario.funcao_id = funcao.id
        db.commit()
        print(f"Usuário '{login}' pronto com função '{funcao_desc}'.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Criar o admin de bootstrap** (a partir de `backend/`, com `.env` configurado)

Run: `python -m app.scripts.criar_usuario admin SenhaForte!2026 Administrador`
Expected: imprime `Usuário 'admin' pronto com função 'Administrador'.`

- [ ] **Step 3: Subir a API**

Run: `python -m uvicorn app.main:app --reload --port 8000`
Expected: servidor sobe; `GET http://localhost:8000/health` responde `{"status":"ok"}`; o Swagger fica em `http://localhost:8000/docs`

- [ ] **Step 4: Smoke test do login** (em outro terminal)

Run:
```bash
curl -s -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" -d "{\"login\":\"admin\",\"senha\":\"SenhaForte!2026\"}"
```
Expected: JSON com `access_token`, `refresh_token` e `"token_type":"bearer"`

- [ ] **Step 5: Smoke test do `/auth/me`** (use o access_token do passo anterior)

Run:
```bash
curl -s http://localhost:8000/auth/me -H "Authorization: Bearer <ACCESS_TOKEN>"
```
Expected: JSON com `"login":"admin"` e o `funcao_id` do Administrador

- [ ] **Step 6: Commit**

```bash
git add backend/app/scripts
git commit -m "feat(backend): script de bootstrap de usuario admin"
```

---

## Self-Review

**1. Cobertura do spec (design §4.3, §4.4, §8, §10):**
- FastAPI modular, SQLAlchemy, Pydantic, Alembic → Tasks 1–3, 9. ✅
- JWT + hash de senha → Tasks 4, 5, 8. ✅
- Dois públicos (equipe `usuario` / portal `cliente`) → Tasks 7, 8 (`/login`, `/login-portal`, tipos no token). ✅
- Funções e `require_funcao` → Tasks 3, 7, 9 (seed dos 4 papéis). ✅
- Segurança §10: senha→text, invalidar legadas, `UNIQUE (cliente, login)` → Task 9. ✅
- *Fora deste plano (planos futuros):* fluxo de redefinição de senha (UI), mapa função→fase, demais tabelas/módulos. Anotado.

**2. Varredura de placeholders:** nenhum "TBD/TODO"; todo passo de código traz o código completo; comandos com saída esperada. ✅

**3. Consistência de tipos/nomes:** `hash_senha`/`verificar_senha`, `criar_access_token`/`criar_refresh_token`/`decodificar_token`, `Funcao`/`Usuario`/`UsuarioCliente`, `get_current_usuario`/`get_current_cliente`/`require_funcao`, `LoginRequest`/`Token`/`UsuarioOut`/`RefreshRequest` — usados de forma idêntica nas Tasks 4–10. Claim do token `token_use` ("access"/"refresh") e `tipo` ("usuario"/"cliente") consistentes entre `security.py`, `deps.py` e `auth.py`. ✅
