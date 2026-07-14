# Acesso: login por e-mail + desativar usuário — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trocar o login do usuário interno de `login` (apelido) para **e-mail** (obrigatório e único), e substituir a exclusão de usuário — hoje **quebrada** por FK do histórico — por **desativar/reativar**.

**Architecture:** Duas mudanças independentes na área de Acesso, entregues em ordem de risco: primeiro o **bug fix** (coluna `ativo` + endpoints desativar/reativar + bloqueio de acesso), que fecha sozinho; depois o **refactor de credencial** (e-mail `NOT NULL`/`UNIQUE`, remoção da coluna `login`, autenticação por e-mail), que arrasta uma varredura mecânica nos testes que autenticam. Frontend e changelog fecham a entrega.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2 (+ `email-validator`), pytest (SQLite in-memory, Docker); React 19 + TS + Vite + Vitest.

## Global Constraints

- Backend em Docker: testes com `docker compose exec -T backend pytest ... -q`. Frontend: `cd frontend && npx tsc -b --noEmit && npm run lint && npm test && npm run build`.
- **Duas migrações** (refinamento do spec, que previa uma): `0011_usuario_ativo` (coluna `ativo`) e `0012_usuario_email_credencial` (e-mail NOT NULL/UNIQUE + drop `login`). Cada uma faz uma coisa e cada task fica shippable sozinha. `0011.down_revision = "0010_etapa_financeiro"`; `0012.down_revision = "0011_usuario_ativo"`.
- **NÃO rodar alembic nos testes** (SQLite constrói a partir dos modelos). Migrações são aplicadas em produção à parte.
- Usuário desativado: **login → 403** `"Usuário desativado. Fale com o administrador."`; **refresh → 401**; **rota protegida → 401**. Credencial inexistente/senha errada continuam **401 "Credenciais inválidas"** (timing achatado já existente).
- E-mail é normalizado (`strip()` + `lower()`) na gravação e na busca (comparação case-insensitive).
- Guardas de desativação: não pode desativar **a si mesmo** (400) nem o **último administrador ativo** (400).
- O **portal do cliente não muda** (`usuarios_cliente`, login por documento + login + senha).
- Commits: Conventional Commits PT-BR **sem acentos**, uma linha, sem trailer de co-autor.

---

### Task 1: Desativar usuário (bug fix) — coluna `ativo`, endpoints e bloqueio de acesso

**Files:**
- Modify: `backend/app/models/usuario.py`
- Create: `backend/alembic/versions/0011_usuario_ativo.py`
- Modify: `backend/app/api/deps.py` (`get_current_usuario`)
- Modify: `backend/app/api/auth.py` (`login`, `refresh`)
- Modify: `backend/app/api/usuarios.py` (`_conta_admins`, `listar`, remove `excluir`, add `desativar`/`reativar`)
- Modify: `backend/app/schemas/acesso.py` (`UsuarioListOut.ativo`)
- Test: `backend/tests/test_acesso.py`, `backend/tests/test_auth.py`

**Interfaces:**
- Produces: `Usuario.ativo: bool`; `POST /usuarios/{id}/desativar` (204); `POST /usuarios/{id}/reativar` (204); `GET /usuarios?incluir_inativos=bool`; `UsuarioListOut.ativo`.
- O endpoint `DELETE /usuarios/{id}` **deixa de existir**.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_acesso.py`:

```python
def test_desativar_usuario(client, usuario_admin, usuario_comum, db_session):
    from app.models import Usuario
    h = _headers(client, "admin", "senha123")
    alvo = db_session.query(Usuario).filter(Usuario.login == "comum").first()
    r = client.post(f"/usuarios/{alvo.id}/desativar", headers=h)
    assert r.status_code == 204
    db_session.refresh(alvo)
    assert alvo.ativo is False


def test_reativar_usuario(client, usuario_admin, usuario_comum, db_session):
    from app.models import Usuario
    h = _headers(client, "admin", "senha123")
    alvo = db_session.query(Usuario).filter(Usuario.login == "comum").first()
    client.post(f"/usuarios/{alvo.id}/desativar", headers=h)
    r = client.post(f"/usuarios/{alvo.id}/reativar", headers=h)
    assert r.status_code == 204
    db_session.refresh(alvo)
    assert alvo.ativo is True


def test_nao_desativa_a_si_mesmo(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    r = client.post(f"/usuarios/{usuario_admin.id}/desativar", headers=h)
    assert r.status_code == 400


def test_admin_pode_desativar_outro_admin(client, usuario_admin, usuario_comum, db_session):
    # com 2 admins ativos, um pode desativar o outro (a guarda do "ultimo admin" nao dispara)
    from app.models import Usuario, Funcao
    admin_funcao = db_session.query(Funcao).filter(Funcao.descricao == "Administrador").first()
    outro = db_session.query(Usuario).filter(Usuario.login == "comum").first()
    outro.funcao_id = admin_funcao.id
    db_session.commit()
    h = _headers(client, "comum", "senha123")   # "comum" agora e admin
    r = client.post(f"/usuarios/{usuario_admin.id}/desativar", headers=h)
    assert r.status_code == 204
    db_session.refresh(usuario_admin)
    assert usuario_admin.ativo is False


def test_listar_oculta_inativos_por_padrao(client, usuario_admin, usuario_comum, db_session):
    from app.models import Usuario
    h = _headers(client, "admin", "senha123")
    alvo = db_session.query(Usuario).filter(Usuario.login == "comum").first()
    client.post(f"/usuarios/{alvo.id}/desativar", headers=h)
    ids = [u["id"] for u in client.get("/usuarios", headers=h).json()]
    assert alvo.id not in ids
    ids_todos = [u["id"] for u in client.get("/usuarios?incluir_inativos=true", headers=h).json()]
    assert alvo.id in ids_todos


def test_delete_usuario_nao_existe_mais(client, usuario_admin, usuario_comum, db_session):
    from app.models import Usuario
    h = _headers(client, "admin", "senha123")
    alvo = db_session.query(Usuario).filter(Usuario.login == "comum").first()
    r = client.delete(f"/usuarios/{alvo.id}", headers=h)
    assert r.status_code == 405   # método não permitido: a rota DELETE foi removida
```

Append to `backend/tests/test_auth.py`:

```python
def test_login_usuario_desativado_403(client, usuario_admin, usuario_comum, db_session):
    from app.models import Usuario
    alvo = db_session.query(Usuario).filter(Usuario.login == "comum").first()
    alvo.ativo = False
    db_session.commit()
    r = client.post("/auth/login", json={"login": "comum", "senha": "senha123"})
    assert r.status_code == 403
    assert "desativado" in r.json()["detail"].lower()


def test_token_de_usuario_desativado_401(client, usuario_admin, usuario_comum, db_session):
    from app.models import Usuario
    tok = client.post("/auth/login", json={"login": "comum", "senha": "senha123"}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    assert client.get("/auth/me", headers=h).status_code == 200
    alvo = db_session.query(Usuario).filter(Usuario.login == "comum").first()
    alvo.ativo = False
    db_session.commit()
    assert client.get("/auth/me", headers=h).status_code == 401


def test_refresh_de_usuario_desativado_401(client, usuario_admin, usuario_comum, db_session):
    from app.models import Usuario
    tok = client.post("/auth/login", json={"login": "comum", "senha": "senha123"}).json()
    alvo = db_session.query(Usuario).filter(Usuario.login == "comum").first()
    alvo.ativo = False
    db_session.commit()
    r = client.post("/auth/refresh", json={"refresh_token": tok["refresh_token"]})
    assert r.status_code == 401
```

Also, in `backend/tests/test_acesso.py`, **delete any existing test that exercises `DELETE /usuarios/{id}` expecting success** (the endpoint is being removed) — the new `test_delete_usuario_nao_existe_mais` replaces them.

- [ ] **Step 2: Run to verify failure**

Run: `docker compose exec -T backend pytest tests/test_acesso.py tests/test_auth.py -q`
Expected: FAIL (`ativo` não existe; rotas desativar/reativar 404; login de desativado ainda 200).

- [ ] **Step 3: Add the model column**

In `backend/app/models/usuario.py`, add after `precisa_redefinir_senha`:

```python
    ativo = Column(Boolean, nullable=False, default=True)
```

- [ ] **Step 4: Create the migration**

Create `backend/alembic/versions/0011_usuario_ativo.py`:

```python
"""usuario: coluna ativo (soft delete)

Revision ID: 0011_usuario_ativo
Revises: 0010_etapa_financeiro
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_usuario_ativo"
down_revision = "0010_etapa_financeiro"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "usuarios",
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade():
    op.drop_column("usuarios", "ativo")
```

- [ ] **Step 5: Block deactivated users at the token layer**

In `backend/app/api/deps.py`, in `get_current_usuario`, change the tail:

```python
    usuario = db.query(Usuario).filter(Usuario.id == sub_id).first()
    if usuario is None:
        raise _cred_invalida
    return usuario
```
to:
```python
    usuario = db.query(Usuario).filter(Usuario.id == sub_id).first()
    if usuario is None or not usuario.ativo:
        raise _cred_invalida
    return usuario
```

- [ ] **Step 6: Block deactivated users at login and refresh**

In `backend/app/api/auth.py`, in `login`, after `_verificar_credenciais(usuario, dados.senha)` add the check:

```python
@router.post("/login", response_model=LoginOut)
def login(dados: LoginRequest, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.login == dados.login).first()
    _verificar_credenciais(usuario, dados.senha)
    if not usuario.ativo:
        raise HTTPException(status_code=403, detail="Usuário desativado. Fale com o administrador.")
    if usuario.precisa_redefinir_senha:
        return LoginOut(precisa_redefinir=True)
    ...
```

In `refresh`, the revalidation block currently reads:

```python
    if registro is None or registro.precisa_redefinir_senha:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh inválido")
```
Change it to also reject deactivated internal users:
```python
    if registro is None or registro.precisa_redefinir_senha:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh inválido")
    if tipo == "usuario" and not registro.ativo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh inválido")
```

- [ ] **Step 7: Rework the usuarios endpoints**

In `backend/app/api/usuarios.py`:

7a. `_conta_admins` counts only **active** admins:
```python
def _conta_admins(db: Session) -> int:
    return (
        db.query(Usuario)
        .join(Funcao, Usuario.funcao_id == Funcao.id)
        .filter(Funcao.descricao == ADMIN, Usuario.ativo.is_(True))
        .count()
    )
```

7b. `listar` hides inactive by default:
```python
@router.get("", response_model=list[UsuarioListOut])
def listar(incluir_inativos: bool = False, db: Session = Depends(get_db),
           _: Usuario = Depends(require_funcao(ADMIN))):
    query = db.query(Usuario)
    if not incluir_inativos:
        query = query.filter(Usuario.ativo.is_(True))
    return query.order_by(Usuario.id).all()
```

7c. **Delete** the whole `excluir` route (the `@router.delete("/{usuario_id}") ...` function) and replace it with:
```python
@router.post("/{usuario_id}/desativar", status_code=status.HTTP_204_NO_CONTENT)
def desativar(usuario_id: int, db: Session = Depends(get_db),
              atual: Usuario = Depends(require_funcao(ADMIN))):
    u = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if u is None:
        raise HTTPException(status_code=404, detail="usuário não encontrado")
    if u.id == atual.id:
        raise HTTPException(status_code=400, detail="não é possível desativar o próprio usuário")
    if not u.ativo:
        return  # idempotente
    if _eh_admin(u) and _conta_admins(db) <= 1:
        raise HTTPException(status_code=400, detail="não é possível desativar o último administrador")
    u.ativo = False
    db.commit()
```

> **Nota sobre a guarda do "último administrador" (leia antes de revisar):** ela é
> **inalcançável por construção** neste endpoint — só um admin ativo chama a rota, e
> desativar a si mesmo já é bloqueado antes; logo, se o alvo é admin e não é o próprio
> ator, existem necessariamente ≥ 2 admins ativos. Mantemos a guarda como defesa em
> profundidade (espelha a que existe no `PATCH`, essa sim alcançável ao rebaixar a
> própria função), e por isso **nenhum teste a exercita** — não invente um teste falso
> para ela.

```python


@router.post("/{usuario_id}/reativar", status_code=status.HTTP_204_NO_CONTENT)
def reativar(usuario_id: int, db: Session = Depends(get_db),
             _: Usuario = Depends(require_funcao(ADMIN))):
    u = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if u is None:
        raise HTTPException(status_code=404, detail="usuário não encontrado")
    u.ativo = True
    db.commit()
```

- [ ] **Step 8: Expose `ativo` in the schema**

In `backend/app/schemas/acesso.py`, add to `UsuarioListOut`:
```python
    ativo: bool
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `docker compose exec -T backend pytest tests/test_acesso.py tests/test_auth.py -q`
Expected: PASS.

- [ ] **Step 10: Run the full suite (no regression)**

Run: `docker compose exec -T backend pytest -q`
Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add backend/app/models/usuario.py backend/alembic/versions/0011_usuario_ativo.py backend/app/api/deps.py backend/app/api/auth.py backend/app/api/usuarios.py backend/app/schemas/acesso.py backend/tests/test_acesso.py backend/tests/test_auth.py
git commit -m "fix(acesso): desativar usuario no lugar de excluir (FK do historico impedia o delete)"
```

---

### Task 2: Login por e-mail (e-mail obrigatório e único; remove `login`)

**Files:**
- Modify: `backend/requirements.txt` (`pydantic` → `pydantic[email]`)
- Modify: `backend/app/models/usuario.py`
- Create: `backend/app/core/emails.py`
- Create: `backend/alembic/versions/0012_usuario_email_credencial.py`
- Modify: `backend/app/schemas/auth.py`, `backend/app/schemas/acesso.py`
- Modify: `backend/app/api/auth.py`, `backend/app/api/usuarios.py`
- Modify: `backend/app/scripts/criar_usuario.py`
- Modify: `backend/tests/conftest.py`
- Rewrite: `backend/tests/test_auth.py`, `backend/tests/test_acesso.py`
- Sweep: the other **31** test files that call `/auth/login`
- Test: `backend/tests/test_emails.py`

**Interfaces:**
- Consumes: `Usuario.ativo` (Task 1).
- Produces: `app.core.emails.normalizar(email: str) -> str`; `LoginRequest.email`; `DefinirSenhaIn.email`; `Usuario.email` (NOT NULL, unique); `Usuario.login` **deixa de existir**.

- [ ] **Step 1: Add the dependency and rebuild the image**

In `backend/requirements.txt`, change the line `pydantic` to:
```
pydantic[email]
```
Then rebuild (o `EmailStr` importa `email-validator`, que não está na imagem atual):
```bash
docker compose build backend && docker compose up -d
```
Verify: `docker compose exec -T backend python -c "from pydantic import EmailStr; print('ok')"` → prints `ok`.

- [ ] **Step 2: Write the failing test for the pure helper**

Create `backend/tests/test_emails.py`:

```python
from app.core import emails


def test_normalizar_trim_e_lowercase():
    assert emails.normalizar("  Admin@HS.com  ") == "admin@hs.com"


def test_normalizar_vazio_ou_none():
    assert emails.normalizar("") == ""
    assert emails.normalizar(None) == ""
```

- [ ] **Step 3: Run to verify failure**

Run: `docker compose exec -T backend pytest tests/test_emails.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.core.emails'`).

- [ ] **Step 4: Implement the pure helper**

Create `backend/app/core/emails.py`:

```python
"""Normalização de e-mail (puro, sem I/O). O e-mail é a credencial do usuário interno."""


def normalizar(email: str | None) -> str:
    """Forma canônica para gravar e comparar: sem espaços nas pontas e em minúsculas."""
    return (email or "").strip().lower()
```

- [ ] **Step 5: Run to verify it passes**

Run: `docker compose exec -T backend pytest tests/test_emails.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Update the model**

In `backend/app/models/usuario.py`: **remove** the `login` column entirely and change `email`:

```python
    email = Column(String(200), nullable=False, unique=True)
```

- [ ] **Step 7: Create the migration**

Create `backend/alembic/versions/0012_usuario_email_credencial.py`:

```python
"""usuario: e-mail vira a credencial (NOT NULL + UNIQUE) e a coluna login sai

Revision ID: 0012_usuario_email_credencial
Revises: 0011_usuario_ativo
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_usuario_email_credencial"
down_revision = "0011_usuario_ativo"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    # 1) normaliza os e-mails existentes (todos os usuarios ja tem e-mail, sem duplicatas)
    conn.execute(sa.text("UPDATE usuarios SET email = lower(trim(email)) WHERE email IS NOT NULL"))
    # 2) e-mail obrigatorio e unico
    op.alter_column("usuarios", "email", existing_type=sa.String(200), nullable=False)
    op.create_unique_constraint("uq_usuarios_email", "usuarios", ["email"])
    # 3) o login deixa de existir
    op.drop_column("usuarios", "login")


def downgrade():
    op.add_column("usuarios", sa.Column("login", sa.String(20), nullable=True))
    op.drop_constraint("uq_usuarios_email", "usuarios", type_="unique")
    op.alter_column("usuarios", "email", existing_type=sa.String(200), nullable=True)
```

- [ ] **Step 8: Update the schemas**

In `backend/app/schemas/auth.py`:
- `LoginRequest`: replace `login: str` with `email: str`.
- `DefinirSenhaIn`: replace `login: str` with `email: str`.
- `UsuarioOut`: remove the `login: str` line.
- `PortalLoginRequest` and `DefinirSenhaPortalIn` **stay untouched** (portal do cliente).

In `backend/app/schemas/acesso.py`, import `EmailStr` and rewrite the three user schemas:

```python
from pydantic import BaseModel, Field, EmailStr
from typing import Optional


class UsuarioListOut(BaseModel):
    id: int
    nome: Optional[str]
    email: str
    funcao_id: Optional[int]
    funcao: Optional[str] = None
    precisa_redefinir_senha: bool
    ativo: bool
    model_config = {"from_attributes": True}


class UsuarioCreate(BaseModel):
    nome: Optional[str] = None
    email: EmailStr
    senha: str = Field(min_length=8)
    funcao_id: Optional[int] = None


class UsuarioUpdate(BaseModel):
    nome: Optional[str] = None
    email: Optional[EmailStr] = None
    funcao_id: Optional[int] = None
```
(`FuncaoOut` and `RedefinirSenhaIn` stay as they are.)

- [ ] **Step 9: Authenticate by e-mail**

In `backend/app/api/auth.py`, add the import `from app.core import emails` and change the two lookups:

`login`:
```python
    usuario = db.query(Usuario).filter(Usuario.email == emails.normalizar(dados.email)).first()
```
`definir_senha`:
```python
    usuario = db.query(Usuario).filter(Usuario.email == emails.normalizar(dados.email)).first()
```
Everything else in those functions (timing dummy, `ativo`, `precisa_redefinir_senha`, tokens) stays the same.

- [ ] **Step 10: E-mail uniqueness in the usuarios endpoints**

In `backend/app/api/usuarios.py`, add `from app.core import emails` and change `criar` / `atualizar`:

```python
@router.post("", response_model=UsuarioListOut, status_code=status.HTTP_201_CREATED)
def criar(dados: UsuarioCreate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    email = emails.normalizar(dados.email)
    if db.query(Usuario).filter(Usuario.email == email).first() is not None:
        raise HTTPException(status_code=409, detail="e-mail já em uso")
    u = Usuario(
        nome=dados.nome,
        email=email,
        senha=hash_senha(dados.senha),
        funcao_id=dados.funcao_id,
        precisa_redefinir_senha=False,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u
```

```python
@router.patch("/{usuario_id}", response_model=UsuarioListOut)
def atualizar(usuario_id: int, dados: UsuarioUpdate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    u = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if u is None:
        raise HTTPException(status_code=404, detail="usuário não encontrado")
    campos = dados.model_dump(exclude_unset=True)
    if "email" in campos and campos["email"] is not None:
        campos["email"] = emails.normalizar(campos["email"])
        if campos["email"] != u.email:
            if db.query(Usuario).filter(Usuario.email == campos["email"]).first() is not None:
                raise HTTPException(status_code=409, detail="e-mail já em uso")
    if "funcao_id" in campos and campos["funcao_id"] != u.funcao_id and _eh_admin(u):
        if _conta_admins(db) <= 1:
            raise HTTPException(status_code=400, detail="não é possível remover o último administrador")
    for chave, valor in campos.items():
        setattr(u, chave, valor)
    db.commit()
    db.refresh(u)
    return u
```

- [ ] **Step 11: Update the bootstrap script**

Rewrite `backend/app/scripts/criar_usuario.py`:

```python
"""Cria ou atualiza um usuário interno com senha em hash.

Uso: python -m app.scripts.criar_usuario <email> <senha> [funcao]
"""
import sys
from app.models.database import SessionLocal
from app.models import Usuario, Funcao
from app.core.security import hash_senha
from app.core import emails


def main():
    if len(sys.argv) < 3:
        print("Uso: python -m app.scripts.criar_usuario <email> <senha> [funcao]")
        sys.exit(1)
    email, senha = emails.normalizar(sys.argv[1]), sys.argv[2]
    funcao_desc = sys.argv[3] if len(sys.argv) > 3 else "Administrador"

    db = SessionLocal()
    try:
        funcao = db.query(Funcao).filter(Funcao.descricao == funcao_desc).first()
        if funcao is None:
            print(f"Função '{funcao_desc}' não encontrada. Rode a migração 0001 primeiro.")
            sys.exit(1)
        usuario = db.query(Usuario).filter(Usuario.email == email).first()
        if usuario is None:
            usuario = Usuario(email=email, nome=email)
            db.add(usuario)
        usuario.senha = hash_senha(senha)
        usuario.precisa_redefinir_senha = False
        usuario.ativo = True
        usuario.funcao_id = funcao.id
        db.commit()
        print(f"Usuário '{email}' pronto com função '{funcao_desc}'.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 12: Update the conftest fixtures**

In `backend/tests/conftest.py`, remove `login=` from every **`Usuario(...)`** construction (the `UsuarioCliente` in `cliente_portal` keeps its `login="cliente1"` — the portal is unchanged). The e-mails already present stay as the credentials:

- `usuario_admin` → `Usuario(nome="Admin", senha=..., email="admin@hs.com", funcao_id=..., precisa_redefinir_senha=False)`
- `usuario_comum` → `email="comum@hs.com"`
- `usuario_lab` → `email="lab@hs.com"`
- `usuario_comercial` → `email="comercial@hs.com"`
- `usuario_financeiro` → `email="fin@hs.com"`

- [ ] **Step 13: Sweep the 31 test files that authenticate**

Every test file (except `conftest.py`, `test_auth.py`, `test_acesso.py`, which you rewrite separately) has this helper:

```python
def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}
```
Change it to:
```python
def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}
```
And update every call site with this exact mapping:

| antes | depois |
|---|---|
| `"admin"` | `"admin@hs.com"` |
| `"comum"` | `"comum@hs.com"` |
| `"lab"` | `"lab@hs.com"` |
| `"comercial"` | `"comercial@hs.com"` |
| `"fin"` | `"fin@hs.com"` |

**Do not touch** calls to `/auth/login-portal` (portal do cliente: `documento` + `login` + `senha`) nor the `cliente_portal` fixture.

Find the files with:
`docker compose exec -T backend grep -rl '"/auth/login"' tests/`

- [ ] **Step 14: Rewrite `test_auth.py` and `test_acesso.py` for the new semantics**

In `backend/tests/test_auth.py`: every `/auth/login` and `/auth/definir-senha` body uses `email` instead of `login`; inline `Usuario(...)` creations must provide a unique `email` and no `login`. Add these tests:

```python
def test_login_com_email(client, usuario_admin):
    r = client.post("/auth/login", json={"email": "admin@hs.com", "senha": "senha123"})
    assert r.status_code == 200 and r.json()["access_token"]


def test_login_email_case_insensitive_e_com_espacos(client, usuario_admin):
    r = client.post("/auth/login", json={"email": "  Admin@HS.com ", "senha": "senha123"})
    assert r.status_code == 200 and r.json()["access_token"]


def test_login_email_inexistente_401(client, usuario_admin):
    assert client.post("/auth/login", json={"email": "naoexiste@hs.com", "senha": "senha123"}).status_code == 401


def test_login_senha_errada_401(client, usuario_admin):
    assert client.post("/auth/login", json={"email": "admin@hs.com", "senha": "errada99"}).status_code == 401
```
The deactivated-user tests added in Task 1 must have their login bodies switched to `{"email": "comum@hs.com", ...}` and their `Usuario.login == "comum"` lookups switched to `Usuario.email == "comum@hs.com"`.

In `backend/tests/test_acesso.py`: the `POST /usuarios` payloads lose `login` and gain a required `email`; lookups by `Usuario.login` become `Usuario.email`. Add:

```python
def test_criar_usuario_exige_email(client, usuario_admin):
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.post("/usuarios", json={"nome": "Joao", "senha": "segredo123"}, headers=h)
    assert r.status_code == 422


def test_criar_usuario_email_invalido_422(client, usuario_admin):
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.post("/usuarios", json={"nome": "Joao", "email": "nao-e-email", "senha": "segredo123"}, headers=h)
    assert r.status_code == 422


def test_criar_usuario_email_duplicado_409(client, usuario_admin):
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.post("/usuarios", json={"nome": "Outro", "email": "admin@hs.com", "senha": "segredo123"}, headers=h)
    assert r.status_code == 409


def test_criar_usuario_normaliza_email(client, usuario_admin):
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.post("/usuarios", json={"nome": "Joao", "email": "  Joao@HS.com ", "senha": "segredo123"}, headers=h)
    assert r.status_code == 201 and r.json()["email"] == "joao@hs.com"
```

- [ ] **Step 15: Run the full suite**

Run: `docker compose exec -T backend pytest -q`
Expected: PASS (toda a suíte verde).

- [ ] **Step 16: Commit**

```bash
git add backend/requirements.txt backend/app/models/usuario.py backend/app/core/emails.py backend/alembic/versions/0012_usuario_email_credencial.py backend/app/schemas backend/app/api/auth.py backend/app/api/usuarios.py backend/app/scripts/criar_usuario.py backend/tests
git commit -m "feat(acesso): login por e-mail com e-mail obrigatorio e unico"
```

---

### Task 3: Frontend — login por e-mail e desativar/reativar

**Files:**
- Modify: `frontend/src/auth/AuthContext.tsx`
- Modify: `frontend/src/app/pages/LoginPage.tsx`
- Modify: `frontend/src/app/acesso/api.ts`
- Modify: `frontend/src/app/acesso/UsuarioFormModal.tsx`
- Modify: `frontend/src/app/acesso/UsuariosPage.tsx`
- Check/Modify: `frontend/src/app/acesso/api.test.ts` (se referenciar `login`/`excluirUsuario`)

**Interfaces:**
- Consumes (backend): `POST /auth/login {email, senha}`; `POST /auth/definir-senha {email, senha_atual, nova_senha}`; `GET /usuarios?incluir_inativos=`; `POST /usuarios/{id}/desativar`; `POST /usuarios/{id}/reativar`; `UsuarioItem` sem `login`, com `ativo`.

- [ ] **Step 1: AuthContext — e-mail como credencial**

In `frontend/src/auth/AuthContext.tsx`:
- In `interface User`, remove the line `login: string`.
- Change the context type and the two functions to take `email`:

```tsx
interface AuthContextValue {
  user: User | null
  loading: boolean
  login: (email: string, senha: string) => Promise<LoginResult>
  logout: () => void
  definirSenha: (email: string, senhaAtual: string, novaSenha: string) => Promise<void>
}
```
```tsx
  async function login(email: string, senha: string): Promise<LoginResult> {
    const r = await apiJson<LoginRespBody>('/auth/login', { method: 'POST', body: JSON.stringify({ email, senha }) })
    if (r.precisa_redefinir) return { precisa_redefinir: true }
    setTokens({ access_token: r.access_token as string, refresh_token: r.refresh_token as string })
    const me = await apiJson<User>('/auth/me')
    setUser(me)
    return { precisa_redefinir: false }
  }

  async function definirSenha(email: string, senhaAtual: string, novaSenha: string) {
    const tokens = await apiJson<Tokens>('/auth/definir-senha', {
      method: 'POST',
      body: JSON.stringify({ email, senha_atual: senhaAtual, nova_senha: novaSenha }),
    })
    setTokens(tokens)
    const me = await apiJson<User>('/auth/me')
    setUser(me)
  }
```

- [ ] **Step 2: LoginPage — campo E-mail**

In `frontend/src/app/pages/LoginPage.tsx`:
- Rename the state `usuario` → `email` (`const [email, setEmail] = useState('')`) and update `onLogin`/`onDefinir` to pass `email` to `login(...)`/`definirSenha(...)`.
- Replace the user Input with:

```tsx
              <Input id="email" label="E-mail" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" autoFocus />
```
The error rendering already shows `err.message` from `ApiError`, so the **403 "Usuário desativado…"** appears as-is — no change needed there.

- [ ] **Step 3: acesso/api.ts — tipos e endpoints**

In `frontend/src/app/acesso/api.ts`:

```ts
export interface UsuarioItem {
  id: number
  nome: string | null
  email: string
  funcao_id: number | null
  funcao: string | null
  precisa_redefinir_senha: boolean
  ativo: boolean
}

export interface UsuarioCreatePayload {
  nome?: string | null
  email: string
  senha: string
  funcao_id?: number | null
}

export interface UsuarioUpdatePayload {
  nome?: string | null
  email?: string
  funcao_id?: number | null
}
```
Replace `listarUsuarios` and **remove** `excluirUsuario`, adding the two new actions:

```ts
export function listarUsuarios(incluirInativos = false): Promise<UsuarioItem[]> {
  const qs = incluirInativos ? '?incluir_inativos=true' : ''
  return apiJson<UsuarioItem[]>(`/usuarios${qs}`)
}

export function desativarUsuario(id: number): Promise<void> {
  return apiVoid(`/usuarios/${id}/desativar`, { method: 'POST' })
}

export function reativarUsuario(id: number): Promise<void> {
  return apiVoid(`/usuarios/${id}/reativar`, { method: 'POST' })
}
```

- [ ] **Step 4: UsuarioFormModal — sem Login, com E-mail obrigatório**

In `frontend/src/app/acesso/UsuarioFormModal.tsx`:
- Remove the `login` state (`const [login, setLogin] = useState(...)`) and the `<Input id="login" ... />` field.
- Make e-mail required and send it (no more `null`):

```tsx
    try {
      const funcao_id = funcaoId ? Number(funcaoId) : null
      const nomeVal = nome.trim() || null
      const emailVal = email.trim()
      if (usuario) {
        await atualizarUsuario(usuario.id, { nome: nomeVal, email: emailVal, funcao_id })
      } else {
        await criarUsuario({ nome: nomeVal, email: emailVal, senha, funcao_id })
      }
      onSalvo()
    } catch (err) {
```
```tsx
        <Input id="email" label="E-mail" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
```

- [ ] **Step 5: UsuariosPage — Desativar/Reativar + toggle**

In `frontend/src/app/acesso/UsuariosPage.tsx`:
- Imports: swap `excluirUsuario` for `desativarUsuario, reativarUsuario` and add the `Toggle` component:
```tsx
import { listarUsuarios, listarFuncoes, desativarUsuario, reativarUsuario, type UsuarioItem, type Funcao } from './api'
import { Toggle } from '../../components/ui/Toggle'
```
- Add the state and thread it into `carregar`:
```tsx
  const [mostrarInativos, setMostrarInativos] = useState(false)
```
```tsx
  async function carregar() {
    setErro('')
    try {
      const [us, fs] = await Promise.all([listarUsuarios(mostrarInativos), listarFuncoes()])
      setUsuarios(us)
      setFuncoes(fs)
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao carregar')
      setUsuarios([])
    }
  }
```
and make the effect re-run when the toggle changes:
```tsx
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (isAdmin(user)) void carregar()
  }, [user, mostrarInativos])
```
- Replace `onExcluir` with the two actions (rótulo **explícito** de desativação):
```tsx
  async function onDesativar(u: UsuarioItem) {
    const alvo = u.nome ?? u.email
    if (!window.confirm(`Desativar o usuário "${alvo}"?\n\nEle perde o acesso ao sistema, mas o histórico das OS é preservado.`)) return
    try {
      await desativarUsuario(u.id)
      await carregar()
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao desativar')
    }
  }

  async function onReativar(u: UsuarioItem) {
    try {
      await reativarUsuario(u.id)
      await carregar()
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao reativar')
    }
  }
```
- Add the toggle next to the "Novo usuário" button:
```tsx
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-extrabold text-slate-100">Usuários</h1>
        <div className="flex items-center gap-4">
          <Toggle checked={mostrarInativos} onChange={setMostrarInativos} label="Mostrar desativados" />
          <Button
            onClick={() => {
              setEditando(null)
              setFormAberto(true)
            }}
          >
            Novo usuário
          </Button>
        </div>
      </div>
```
- Table: drop the `Login` column, add `Status`, and swap the action button:
```tsx
        <Table
          head={
            <>
              <TH>Nome</TH>
              <TH>E-mail</TH>
              <TH>Função</TH>
              <TH>Status</TH>
              <TH>Ações</TH>
            </>
          }
        >
          {usuarios.map((u) => (
            <tr key={u.id} className="hover:bg-background-elevated transition-colors">
              <TD>{u.nome ?? '—'}</TD>
              <TD>{u.email}</TD>
              <TD>{u.funcao ? <Badge tone={u.funcao === 'Administrador' ? 'primary' : 'neutral'}>{u.funcao}</Badge> : '—'}</TD>
              <TD>{u.ativo ? <Badge tone="primary">Ativo</Badge> : <Badge tone="warning">Desativado</Badge>}</TD>
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
                  {u.ativo ? (
                    <button onClick={() => onDesativar(u)} className="text-xs text-danger hover:underline">
                      Desativar
                    </button>
                  ) : (
                    <button onClick={() => onReativar(u)} className="text-xs text-primary hover:underline">
                      Reativar
                    </button>
                  )}
                </div>
              </TD>
            </tr>
          ))}
        </Table>
```

> `Toggle` já existe em `frontend/src/components/ui/Toggle.tsx` e é usado na página de Caixas com a mesma assinatura (`checked`, `onChange`, `label`) — confira lá se precisar do uso de referência.

- [ ] **Step 6: RedefinirSenhaModal — título sem `login`**

`frontend/src/app/acesso/RedefinirSenhaModal.tsx` linha 36 usa `usuario.login`, que deixou de existir. Troque por:

```tsx
      title={`Redefinir senha — ${usuario.nome ?? usuario.email}`}
```

- [ ] **Step 7: Corrigir os testes/mocks do frontend que carregam `login`**

Estes quatro pontos quebram o `tsc` porque `UsuarioItem`/`User` não têm mais `login`:

`frontend/src/app/acesso/api.test.ts`:
```ts
const ITEM = { id: 1, nome: null, email: 'a@hs.com', funcao_id: null, funcao: null, precisa_redefinir_senha: false, ativo: true }
```
- a asserção `expect(r[0].login).toBe('a')` vira `expect(r[0].email).toBe('a@hs.com')`;
- `await criarUsuario({ login: 'novo', senha: '12345678' })` vira `await criarUsuario({ email: 'novo@hs.com', senha: '12345678' })`;
- se houver teste de `excluirUsuario`, troque por `desativarUsuario` (espera `POST /usuarios/1/desativar`).

`frontend/src/auth/roles.test.ts` — remova a chave `login` dos objetos `User`:
```ts
const admin: User = { id: 1, nome: null, email: 'a@hs.com', funcao_id: 1, funcao: 'Administrador' }
const comum: User = { id: 2, nome: null, email: 'b@hs.com', funcao_id: 2, funcao: 'Expedição' }
```
e no helper da linha 15: `return { id: 1, nome: 'x', email: 'x@hs.com', funcao } as User`.

`frontend/src/auth/ProtectedRoute.test.tsx` linha 46 — remova `login: 'e'` do corpo mockado:
```tsx
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ id: 1, nome: 'E', email: 'e@hs.com', funcao_id: 1 })))
```

> Os `login` em `frontend/src/app/clientes/api.ts` são do **usuário do portal** (`usuarios_cliente`) — **não mexa neles**.

- [ ] **Step 8: Verify the frontend**

Run: `cd frontend && npx tsc -b --noEmit && npm run lint && npm test && npm run build`
Expected: tsc sem erros, lint limpo, vitest verde, build OK.

- [ ] **Step 9: Commit**

```bash
git add frontend/src
git commit -m "feat(ux): login por e-mail e desativar usuario no lugar de excluir"
```

---

### Task 4: Changelog + verificação final

**Files:**
- Modify: `frontend/src/app/changelog/data.ts`

- [ ] **Step 1: Changelog v1.12.0**

In `frontend/src/app/changelog/data.ts`, insert as the **first** entry of `CHANGELOG` (mantenha a **acentuação** correta, como nas demais entradas):

```ts
  {
    versao: '1.12.0',
    data: '13/07/2026',
    itens: [
      { tipo: 'novidade', texto: 'O login agora é feito com o e-mail, no lugar do nome de usuário. Ao cadastrar um usuário, o e-mail passou a ser obrigatório (e único) — ele é a credencial de acesso.' },
      { tipo: 'correcao', texto: 'Corrigido o erro ao remover um usuário. Como o usuário fica ligado ao histórico das Ordens de Serviço (quem fez cada etapa), agora em vez de excluir ele é "Desativado": perde o acesso ao sistema, mas o histórico é preservado. Desativados ficam ocultos na lista (use "Mostrar desativados") e podem ser reativados.' },
    ],
  },
```

- [ ] **Step 2: Full backend suite**

Run: `docker compose exec -T backend pytest -q`
Expected: PASS.

- [ ] **Step 3: Full frontend verification**

Run: `cd frontend && npx tsc -b --noEmit && npm run lint && npm test && npm run build`
Expected: tudo limpo.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/changelog/data.ts
git commit -m "docs(changelog): v1.12.0 — login por e-mail e desativar usuario"
```

---

## Notas de aplicação (produção, fora dos testes)

1. **Rebuild da imagem do backend** (dependência `email-validator` nova) — sem isso a API não sobe.
2. `docker compose exec -T backend alembic upgrade head` — aplica **0011** (coluna `ativo`) e **0012** (e-mail NOT NULL/UNIQUE + drop `login`). **Requer consentimento — DDL em produção; a 0012 é destrutiva (remove a coluna `login`).**
3. A partir daí **todos entram pelo e-mail** (os 5 e-mails já cadastrados). O `login` antigo deixa de valer.
4. Validar E2E: entrar com `healthsafetyti@gmail.com`; criar um usuário novo (e-mail obrigatório); desativar o usuário `Lucas` (id 7) — o que antes dava 500 — e conferir que ele some da lista, não consegue logar, e o histórico da OS dele continua intacto.
