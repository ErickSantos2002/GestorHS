# Página de Certificados (modelos + imagens) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Página "Certificados" para gerenciar o modelo de certificado (HTML) de cada aparelho do catálogo e uma biblioteca de imagens (URL pública) usáveis nos certificados.

**Architecture:** Reaproveita a tabela `certificados` (migração conserta a FK → catálogo `equipamentos` e remapeia 12 templates legados). Novos modelos `CertificadoModelo`/`CertificadoImagem`, router `/certificados-modelo` + `/certificado-imagens` (com 1 rota pública de leitura de imagem), e página React com 2 abas (Modelos: código-fonte HTML + preview em iframe sandbox; Imagens: upload + URL pública).

**Tech Stack:** Backend FastAPI + SQLAlchemy + Alembic + pytest (SQLite). Frontend React + TS + Vite + Vitest.

**Spec:** `docs/superpowers/specs/2026-06-08-certificados-modelo-design.md`

**Convenções:** testes backend `cd backend && python -m pytest -q`; frontend `cd frontend && npx vitest run`. Escrita = `require_funcao("Administrador", "Laboratório")`; leitura = `get_current_usuario`. Storage: `app/core/storage.py` (`salvar_upload(file, subdir=, tipos_permitidos=)`, `caminho_arquivo(subdir, basename)`, `remover_arquivo`, `TIPOS_IMAGEM`, `ArquivoInvalido(status, detail)`). Fixtures de teste: `usuario_admin` (admin/senha123), `usuario_lab` (lab/senha123), `usuario_comercial` (comercial/senha123), `upload_tmp` (redireciona UPLOAD_DIR p/ tmp). Helper de auth nos testes: `_headers(client, login, senha)`.

**Regra do projeto:** toda mudança bumpa versão + entra no ChangelogModal (Task 9).

**NÃO faz parte:** geração do certificado na OS (substituição de campos + PDF) — próxima etapa.

---

## Task 1: Modelos `CertificadoModelo` e `CertificadoImagem`

**Files:**
- Create: `backend/app/models/certificado_modelo.py`
- Create: `backend/app/models/certificado_imagem.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_certificados_modelo_model.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_certificados_modelo_model.py`:

```python
def test_certificado_modelo_props(db_session):
    from app.models import Equipamento, CertificadoModelo
    eq = Equipamento(descricao="Bafômetro Mark X")
    db_session.add(eq); db_session.flush()
    c = CertificadoModelo(equipamento=eq.id, descricao="Cert Mark X", texto="<p>oi</p>")
    db_session.add(c); db_session.commit(); db_session.refresh(c)
    assert c.equipamento_descricao == "Bafômetro Mark X"
    assert c.texto == "<p>oi</p>"


def test_certificado_imagem_url(db_session):
    from app.models import CertificadoImagem
    img = CertificadoImagem(arquivo="abc123.png", nome="Logo")
    db_session.add(img); db_session.commit(); db_session.refresh(img)
    assert img.url == "/certificado-imagens/arquivo/abc123.png"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_certificados_modelo_model.py -q`
Expected: FAIL (ImportError).

- [ ] **Step 3: Create the models**

Create `backend/app/models/certificado_modelo.py`:

```python
from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.models.database import Base


class CertificadoModelo(Base):
    __tablename__ = "certificados"

    id = Column(Integer, primary_key=True, index=True)
    equipamento = Column(Integer, ForeignKey("equipamentos.id"), nullable=True, unique=True)
    descricao = Column(String(100), nullable=True)
    texto = Column(Text, nullable=True)

    equipamento_rel = relationship("Equipamento", lazy="joined")

    @property
    def equipamento_descricao(self):
        return self.equipamento_rel.descricao if self.equipamento_rel else None
```

Create `backend/app/models/certificado_imagem.py`:

```python
from sqlalchemy import Column, Integer, String, DateTime
from app.models.database import Base


class CertificadoImagem(Base):
    __tablename__ = "certificado_imagens"

    id = Column(Integer, primary_key=True, index=True)
    arquivo = Column(String(120), nullable=False)
    nome = Column(String(150), nullable=True)
    datacad = Column(DateTime(timezone=True), nullable=True)

    @property
    def url(self):
        return f"/certificado-imagens/arquivo/{self.arquivo}"
```

- [ ] **Step 4: Register the models**

In `backend/app/models/__init__.py`, add the imports (after the `Caixa` import):

```python
from app.models.certificado_modelo import CertificadoModelo
from app.models.certificado_imagem import CertificadoImagem
```

and add `"CertificadoModelo", "CertificadoImagem"` to `__all__`.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_certificados_modelo_model.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Run full suite (no regression)**

Run: `cd backend && python -m pytest -q`
Expected: all green.

> Nota: o modelo `CertificadoModelo` mapeia a tabela `certificados` com a coluna `equipamento` (que a migração 0006 cria no banco real). Em SQLite de teste, o `create_all` gera a tabela já com `equipamento` — ok.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/certificado_modelo.py backend/app/models/certificado_imagem.py backend/app/models/__init__.py backend/tests/test_certificados_modelo_model.py
git commit -m "feat(certificados): modelos CertificadoModelo + CertificadoImagem"
```

---

## Task 2: Schemas

**Files:**
- Create: `backend/app/schemas/certificados_modelo.py`
- Test: `backend/tests/test_certificados_modelo_schemas.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_certificados_modelo_schemas.py`:

```python
def test_schemas_basicos():
    from app.schemas.certificados_modelo import (
        ModeloItem, CertificadoModeloOut, CertificadoModeloIn, ImagemOut,
    )
    item = ModeloItem(equipamento=3, equipamento_descricao="Mark X", tem_certificado=True)
    assert item.tem_certificado is True
    out = CertificadoModeloOut(equipamento=3, equipamento_descricao="Mark X", descricao="d", texto="<p>x</p>")
    assert out.texto == "<p>x</p>"
    inp = CertificadoModeloIn(texto="<p>y</p>")
    assert inp.descricao is None and inp.texto == "<p>y</p>"
    img = ImagemOut(id=1, nome="Logo", arquivo="a.png", url="/certificado-imagens/arquivo/a.png")
    assert img.url.endswith("a.png")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_certificados_modelo_schemas.py -q`
Expected: FAIL (módulo inexistente).

- [ ] **Step 3: Implement**

Create `backend/app/schemas/certificados_modelo.py`:

```python
from pydantic import BaseModel, ConfigDict


class ModeloItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    equipamento: int
    equipamento_descricao: str | None = None
    tem_certificado: bool = False


class ModeloPage(BaseModel):
    items: list[ModeloItem]


class CertificadoModeloOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    equipamento: int
    equipamento_descricao: str | None = None
    descricao: str | None = None
    texto: str = ""


class CertificadoModeloIn(BaseModel):
    descricao: str | None = None
    texto: str


class ImagemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nome: str | None = None
    arquivo: str
    url: str


class ImagemPage(BaseModel):
    items: list[ImagemOut]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_certificados_modelo_schemas.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/certificados_modelo.py backend/tests/test_certificados_modelo_schemas.py
git commit -m "feat(certificados): schemas de modelo e imagem"
```

---

## Task 3: Router de modelos (lista / obter / upsert)

**Files:**
- Create: `backend/app/api/certificados_modelo.py`
- Modify: `backend/app/main.py:4,37` (import + include_router)
- Test: `backend/tests/test_certificados_modelo_api.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_certificados_modelo_api.py`:

```python
def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _eq(db_session, descricao):
    from app.models import Equipamento
    e = Equipamento(descricao=descricao)
    db_session.add(e); db_session.commit(); db_session.refresh(e)
    return e.id


def test_listar_modelos_flag(client, usuario_admin, db_session):
    h = _headers(client, "admin", "senha123")
    e1 = _eq(db_session, "Mark X")
    e2 = _eq(db_session, "Iblow10")
    # cria certificado só p/ e1
    client.put(f"/certificados-modelo/{e1}", json={"texto": "<p>a</p>"}, headers=h)
    r = client.get("/certificados-modelo", headers=h).json()
    mapa = {i["equipamento"]: i["tem_certificado"] for i in r["items"]}
    assert mapa[e1] is True
    assert mapa[e2] is False


def test_obter_vazio_quando_sem_certificado(client, usuario_admin, db_session):
    h = _headers(client, "admin", "senha123")
    e = _eq(db_session, "Sem Cert")
    r = client.get(f"/certificados-modelo/{e}", headers=h)
    assert r.status_code == 200
    assert r.json()["texto"] == ""
    assert r.json()["equipamento_descricao"] == "Sem Cert"


def test_upsert_cria_e_atualiza(client, usuario_admin, db_session):
    h = _headers(client, "admin", "senha123")
    e = _eq(db_session, "Up")
    r1 = client.put(f"/certificados-modelo/{e}", json={"texto": "<p>1</p>", "descricao": "d1"}, headers=h)
    assert r1.status_code == 200
    assert r1.json()["texto"] == "<p>1</p>"
    r2 = client.put(f"/certificados-modelo/{e}", json={"texto": "<p>2</p>"}, headers=h)
    assert r2.json()["texto"] == "<p>2</p>"
    # ainda 1 certificado p/ o modelo
    assert client.get(f"/certificados-modelo/{e}", headers=h).json()["texto"] == "<p>2</p>"


def test_obter_equipamento_inexistente_404(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    assert client.get("/certificados-modelo/99999", headers=h).status_code == 404


def test_escrita_exige_admin_ou_lab(client, usuario_admin, usuario_comercial, db_session):
    e = _eq(db_session, "Perm")
    h = _headers(client, "comercial", "senha123")
    assert client.put(f"/certificados-modelo/{e}", json={"texto": "x"}, headers=h).status_code == 403


def test_lab_pode_escrever(client, usuario_admin, usuario_lab, db_session):
    e = _eq(db_session, "Lab")
    h = _headers(client, "lab", "senha123")
    assert client.put(f"/certificados-modelo/{e}", json={"texto": "<p>lab</p>"}, headers=h).status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_certificados_modelo_api.py -q`
Expected: FAIL (rotas 404).

- [ ] **Step 3: Implement the router**

Create `backend/app/api/certificados_modelo.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Equipamento, CertificadoModelo
from app.api.deps import get_current_usuario, require_funcao
from app.schemas.certificados_modelo import (
    ModeloItem, ModeloPage, CertificadoModeloOut, CertificadoModeloIn,
)

router = APIRouter(tags=["certificados-modelo"])

_escrita = require_funcao("Administrador", "Laboratório")


def _equipamento_ou_404(db: Session, equipamento_id: int) -> Equipamento:
    eq = db.query(Equipamento).filter(Equipamento.id == equipamento_id).first()
    if eq is None:
        raise HTTPException(status_code=404, detail="modelo de equipamento não encontrado")
    return eq


@router.get("/certificados-modelo", response_model=ModeloPage)
def listar_modelos(
    q: str | None = None,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_usuario),
):
    query = db.query(Equipamento)
    if q:
        query = query.filter(Equipamento.descricao.ilike(f"%{q.strip()}%"))
    equipamentos = query.order_by(Equipamento.descricao).all()
    com_cert = {c.equipamento for c in db.query(CertificadoModelo.equipamento).all()}
    items = [
        ModeloItem(equipamento=e.id, equipamento_descricao=e.descricao, tem_certificado=e.id in com_cert)
        for e in equipamentos
    ]
    return ModeloPage(items=items)


@router.get("/certificados-modelo/{equipamento_id}", response_model=CertificadoModeloOut)
def obter_modelo(equipamento_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    eq = _equipamento_ou_404(db, equipamento_id)
    cert = db.query(CertificadoModelo).filter(CertificadoModelo.equipamento == equipamento_id).first()
    return CertificadoModeloOut(
        equipamento=eq.id,
        equipamento_descricao=eq.descricao,
        descricao=cert.descricao if cert else None,
        texto=cert.texto if cert else "",
    )


@router.put("/certificados-modelo/{equipamento_id}", response_model=CertificadoModeloOut)
def salvar_modelo(
    equipamento_id: int,
    dados: CertificadoModeloIn,
    db: Session = Depends(get_db),
    _: Usuario = Depends(_escrita),
):
    eq = _equipamento_ou_404(db, equipamento_id)
    cert = db.query(CertificadoModelo).filter(CertificadoModelo.equipamento == equipamento_id).first()
    if cert is None:
        cert = CertificadoModelo(equipamento=equipamento_id)
        db.add(cert)
    cert.texto = dados.texto
    cert.descricao = dados.descricao
    db.commit()
    db.refresh(cert)
    return CertificadoModeloOut(
        equipamento=eq.id,
        equipamento_descricao=eq.descricao,
        descricao=cert.descricao,
        texto=cert.texto or "",
    )
```

- [ ] **Step 4: Register the router**

In `backend/app/main.py`:
- Line 4: add `certificados_modelo` to the `from app.api import ...` list.
- After `app.include_router(caixas.router)` (last include): add `app.include_router(certificados_modelo.router)`.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_certificados_modelo_api.py -q`
Expected: PASS (6 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/certificados_modelo.py backend/app/main.py backend/tests/test_certificados_modelo_api.py
git commit -m "feat(certificados): router de modelos (listar/obter/upsert)"
```

---

## Task 4: Router de imagens (CRUD + serve público)

**Files:**
- Modify: `backend/app/api/certificados_modelo.py` (novos endpoints de imagem)
- Test: `backend/tests/test_certificado_imagens_api.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_certificado_imagens_api.py`:

```python
import io


def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _png_bytes():
    # PNG mínimo válido (1x1)
    import base64
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )


def test_upload_listar_excluir(client, usuario_admin, upload_tmp):
    h = _headers(client, "admin", "senha123")
    files = {"file": ("logo.png", io.BytesIO(_png_bytes()), "image/png")}
    r = client.post("/certificado-imagens", data={"nome": "Logo"}, files=files, headers=h)
    assert r.status_code == 201, r.text
    img = r.json()
    assert img["nome"] == "Logo"
    assert img["url"].startswith("/certificado-imagens/arquivo/")
    # lista
    lista = client.get("/certificado-imagens", headers=h).json()
    assert any(i["id"] == img["id"] for i in lista["items"])
    # exclui
    assert client.delete(f"/certificado-imagens/{img['id']}", headers=h).status_code == 204


def test_serve_publico_sem_token(client, usuario_admin, upload_tmp):
    h = _headers(client, "admin", "senha123")
    files = {"file": ("a.png", io.BytesIO(_png_bytes()), "image/png")}
    arquivo = client.post("/certificado-imagens", files=files, headers=h).json()["arquivo"]
    # SEM header de auth
    r = client.get(f"/certificado-imagens/arquivo/{arquivo}")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/")


def test_serve_path_traversal_bloqueado(client):
    r = client.get("/certificado-imagens/arquivo/..%2f..%2fsecret")
    assert r.status_code in (400, 404)


def test_upload_exige_admin_ou_lab(client, usuario_admin, usuario_comercial, upload_tmp):
    h = _headers(client, "comercial", "senha123")
    files = {"file": ("a.png", io.BytesIO(_png_bytes()), "image/png")}
    assert client.post("/certificado-imagens", files=files, headers=h).status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_certificado_imagens_api.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement the endpoints**

Em `backend/app/api/certificados_modelo.py`, adicione os imports no topo:

```python
from datetime import datetime, timezone
from fastapi import UploadFile, File, Form, status as http_status
from fastapi.responses import FileResponse
from app.models import CertificadoImagem
from app.core import storage
from app.schemas.certificados_modelo import ImagemOut, ImagemPage
```

(Junte `CertificadoImagem` ao import existente de `app.models`.)

E adicione ao final do arquivo:

```python
_SUBDIR_IMG = "certificado-imagens"


@router.get("/certificado-imagens", response_model=ImagemPage)
def listar_imagens(db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    imgs = db.query(CertificadoImagem).order_by(CertificadoImagem.id.desc()).all()
    return ImagemPage(items=[ImagemOut.model_validate(i) for i in imgs])


@router.post("/certificado-imagens", response_model=ImagemOut, status_code=http_status.HTTP_201_CREATED)
def enviar_imagem(
    file: UploadFile = File(...),
    nome: str | None = Form(None),
    db: Session = Depends(get_db),
    _: Usuario = Depends(_escrita),
):
    try:
        basename = storage.salvar_upload(file, subdir=_SUBDIR_IMG, tipos_permitidos=storage.TIPOS_IMAGEM)
    except storage.ArquivoInvalido as e:
        raise HTTPException(e.status, e.detail)
    img = CertificadoImagem(arquivo=basename, nome=nome, datacad=datetime.now(timezone.utc))
    db.add(img)
    db.commit()
    db.refresh(img)
    return ImagemOut.model_validate(img)


@router.delete("/certificado-imagens/{img_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def excluir_imagem(img_id: int, db: Session = Depends(get_db), _: Usuario = Depends(_escrita)):
    img = db.query(CertificadoImagem).filter(CertificadoImagem.id == img_id).first()
    if img is None:
        raise HTTPException(404, "imagem não encontrada")
    arquivo = img.arquivo
    db.delete(img)
    db.commit()
    storage.remover_arquivo(_SUBDIR_IMG, arquivo)


@router.get("/certificado-imagens/arquivo/{nome}")
def servir_imagem(nome: str):
    # PÚBLICO (sem auth) — assets de certificado embutidos via <img src>
    try:
        caminho = storage.caminho_arquivo(_SUBDIR_IMG, nome)
    except storage.ArquivoInvalido as e:
        raise HTTPException(e.status, e.detail)
    if not caminho.exists():
        raise HTTPException(404, "imagem não encontrada")
    return FileResponse(caminho)
```

> Atenção à ordem das rotas: `/certificado-imagens/arquivo/{nome}` e `/certificado-imagens/{img_id}` (DELETE) não colidem (métodos/segmentos distintos). O GET de arquivo é público (sem `Depends` de auth).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_certificado_imagens_api.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Run full backend suite**

Run: `cd backend && python -m pytest -q`
Expected: tudo verde.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/certificados_modelo.py backend/tests/test_certificado_imagens_api.py
git commit -m "feat(certificados): imagens (CRUD + serve público)"
```

---

## Task 5: Migração Alembic `0006_certificados_modelo`

**Files:**
- Create: `backend/alembic/versions/0006_certificados_modelo.py`

> A suíte pytest usa SQLite/metadata e não roda Alembic. Esta migração é para o banco real (9998): dry-run + aprovação antes de aplicar (protocolo do projeto). Os 12 templates remapeiam todos para o catálogo (verificado).

- [ ] **Step 1: Create the migration file**

Create `backend/alembic/versions/0006_certificados_modelo.py`:

```python
"""certificados: FK -> equipamentos (catálogo) + certificado_imagens

Revision ID: 0006_certificados_modelo
Revises: 0005_caixas_drop_status
Create Date: 2026-06-08
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_certificados_modelo"
down_revision = "0005_caixas_drop_status"
branch_labels = None
depends_on = None


def upgrade():
    # 1) nova coluna equipamento -> catálogo
    op.add_column("certificados", sa.Column("equipamento", sa.Integer(), nullable=True))
    # backfill: o valor antigo (em equipamento_cliente) já é o id do catálogo legado
    op.execute(
        "UPDATE certificados SET equipamento = equipamento_cliente "
        "WHERE equipamento_cliente IN (SELECT id FROM equipamentos)"
    )
    # remove linhas que não casaram com o catálogo (defensivo — não há)
    op.execute("DELETE FROM certificados WHERE equipamento IS NULL")
    # dedup defensivo: manter só o maior id por equipamento
    op.execute(
        "DELETE FROM certificados a USING certificados b "
        "WHERE a.equipamento = b.equipamento AND a.id < b.id"
    )
    # 2) dropar a FK/coluna antiga
    op.drop_constraint("certificados_equipamento_cliente_fkey", "certificados", type_="foreignkey")
    op.drop_column("certificados", "equipamento_cliente")
    # 3) FK + unique no novo vínculo
    op.create_foreign_key("certificados_equipamento_fkey", "certificados", "equipamentos", ["equipamento"], ["id"])
    op.create_unique_constraint("uq_certificados_equipamento", "certificados", ["equipamento"])
    # 4) tabela de imagens
    op.create_table(
        "certificado_imagens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("arquivo", sa.String(length=120), nullable=False),
        sa.Column("nome", sa.String(length=150), nullable=True),
        sa.Column("datacad", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_table("certificado_imagens")
    op.drop_constraint("uq_certificados_equipamento", "certificados", type_="unique")
    op.drop_constraint("certificados_equipamento_fkey", "certificados", type_="foreignkey")
    op.add_column("certificados", sa.Column("equipamento_cliente", sa.Integer(), nullable=True))
    op.execute("UPDATE certificados SET equipamento_cliente = equipamento")
    op.create_foreign_key(
        "certificados_equipamento_cliente_fkey", "certificados", "equipamentos_cliente",
        ["equipamento_cliente"], ["id"],
    )
    op.drop_column("certificados", "equipamento")
```

> O nome real da FK antiga (`certificados_equipamento_cliente_fkey`) deve ser confirmado no banco antes de aplicar (padrão do Postgres: `<tabela>_<coluna>_fkey`). Se divergir, ajustar o `drop_constraint`.

- [ ] **Step 2: Sanity (syntax + head)**

Run: `cd backend && python -c "import ast; ast.parse(open('alembic/versions/0006_certificados_modelo.py').read()); print('ok')"`
Run: `cd backend && python -m alembic heads`
Expected: `ok` e `0006_certificados_modelo (head)`.

- [ ] **Step 3: Commit (sem aplicar)**

```bash
git add backend/alembic/versions/0006_certificados_modelo.py
git commit -m "feat(certificados): migração 0006 (FK->equipamentos + certificado_imagens)"
```

- [ ] **Step 4: Dry-run + aplicar no banco real (com o usuário)**

> Não aplicar sem confirmar. Antes: `cd backend && docker compose ... alembic upgrade 0005_caixas_drop_status:0006_certificados_modelo --sql` (mostrar SQL) e confirmar o nome real da FK antiga via `SELECT conname FROM pg_constraint WHERE conrelid='certificados'::regclass`. Após o ok: `alembic upgrade head`. Verificar contagem dos 12 e o `UNIQUE`.

---

## Task 6: Frontend — `api.ts` + constantes + teste

**Files:**
- Create: `frontend/src/app/certificados/api.ts`
- Test: `frontend/src/app/certificados/api.test.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/app/certificados/api.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'

const { apiJson, apiFetch } = vi.hoisted(() => ({ apiJson: vi.fn(), apiFetch: vi.fn() }))
vi.mock('../../lib/api', () => {
  class ApiError extends Error {
    status: number
    constructor(status: number, message: string) { super(message); this.status = status }
  }
  return { apiJson: (...a: unknown[]) => apiJson(...a), apiFetch: (...a: unknown[]) => apiFetch(...a), ApiError }
})

import { certificadosApi, CAMPOS_CERTIFICADO } from './api'

beforeEach(() => {
  apiJson.mockReset(); apiJson.mockResolvedValue({})
  apiFetch.mockReset(); apiFetch.mockResolvedValue({ ok: true, json: async () => ({}) })
})

describe('certificadosApi', () => {
  it('listarModelos com q', async () => {
    await certificadosApi.listarModelos({ q: 'mark' })
    expect(apiJson).toHaveBeenCalledWith('/certificados-modelo?q=mark')
  })
  it('obterModelo', async () => {
    await certificadosApi.obterModelo(3)
    expect(apiJson).toHaveBeenCalledWith('/certificados-modelo/3')
  })
  it('salvarModelo manda PUT', async () => {
    await certificadosApi.salvarModelo(3, { descricao: 'd', texto: '<p>x</p>' })
    expect(apiJson).toHaveBeenCalledWith('/certificados-modelo/3', { method: 'PUT', body: JSON.stringify({ descricao: 'd', texto: '<p>x</p>' }) })
  })
  it('excluirImagem usa DELETE via apiFetch', async () => {
    await certificadosApi.excluirImagem(5)
    expect(apiFetch).toHaveBeenCalledWith('/certificado-imagens/5', expect.objectContaining({ method: 'DELETE' }))
  })
  it('tem lista de campos', () => {
    expect(CAMPOS_CERTIFICADO.length).toBeGreaterThan(3)
    expect(CAMPOS_CERTIFICADO.some((c) => c.campo === '[nomecli]')).toBe(true)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/app/certificados/api.test.ts`
Expected: FAIL.

- [ ] **Step 3: Implement**

Create `frontend/src/app/certificados/api.ts`:

```ts
import { apiJson, apiFetch, ApiError } from '../../lib/api'

async function apiVoid(path: string, options: RequestInit = {}): Promise<void> {
  const res = await apiFetch(path, options)
  if (!res.ok) {
    let detail = res.statusText
    try { const b = (await res.json()) as { detail?: string }; if (b.detail) detail = b.detail } catch { /* sem corpo */ }
    throw new ApiError(res.status, detail)
  }
}

export interface ModeloItem {
  equipamento: number
  equipamento_descricao: string | null
  tem_certificado: boolean
}
export interface CertificadoModelo {
  equipamento: number
  equipamento_descricao: string | null
  descricao: string | null
  texto: string
}
export interface ImagemCert {
  id: number
  nome: string | null
  arquivo: string
  url: string
}

export const CAMPOS_CERTIFICADO: { campo: string; desc: string }[] = [
  { campo: '[nomecli]', desc: 'Nome do cliente' },
  { campo: '[cnpj]', desc: 'CNPJ/CPF do cliente' },
  { campo: '[endcli]', desc: 'Endereço do cliente' },
  { campo: '[modelo]', desc: 'Modelo do equipamento' },
  { campo: '[marca]', desc: 'Marca do equipamento' },
  { campo: '[serie]', desc: 'Número de série' },
  { campo: '[datacli]', desc: 'Data do cliente' },
  { campo: '[datacompra]', desc: 'Data de compra' },
  { campo: '[dataemissao]', desc: 'Data de emissão' },
  { campo: '[calibcert]', desc: 'Nº do certificado de calibração' },
]

export const certificadosApi = {
  listarModelos: (params: { q?: string } = {}): Promise<{ items: ModeloItem[] }> => {
    const sp = new URLSearchParams()
    if (params.q) sp.set('q', params.q)
    const qs = sp.toString()
    return apiJson<{ items: ModeloItem[] }>(`/certificados-modelo${qs ? `?${qs}` : ''}`)
  },
  obterModelo: (equipId: number): Promise<CertificadoModelo> =>
    apiJson<CertificadoModelo>(`/certificados-modelo/${equipId}`),
  salvarModelo: (equipId: number, body: { descricao?: string | null; texto: string }): Promise<CertificadoModelo> =>
    apiJson<CertificadoModelo>(`/certificados-modelo/${equipId}`, { method: 'PUT', body: JSON.stringify(body) }),
  listarImagens: (): Promise<{ items: ImagemCert[] }> =>
    apiJson<{ items: ImagemCert[] }>('/certificado-imagens'),
  enviarImagem: async (file: File, nome?: string): Promise<ImagemCert> => {
    const fd = new FormData()
    fd.append('file', file)
    if (nome) fd.append('nome', nome)
    const res = await apiFetch('/certificado-imagens', { method: 'POST', body: fd })
    if (!res.ok) {
      let detail = res.statusText
      try { const b = await res.json(); if (b.detail) detail = b.detail } catch { /* sem corpo */ }
      throw new ApiError(res.status, detail)
    }
    return (await res.json()) as ImagemCert
  },
  excluirImagem: (id: number): Promise<void> => apiVoid(`/certificado-imagens/${id}`, { method: 'DELETE' }),
}
```

> A URL pública da imagem (`img.url`) é relativa (`/certificado-imagens/arquivo/...`). Para usar no `<img src>` da preview, prefixar com a base da API. Reusar o resolvedor de base já existente em `lib/api.ts` se exportado; senão, no componente, montar `apiBase + url` (ver Task 7/8).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/app/certificados/api.test.ts`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/certificados/api.ts frontend/src/app/certificados/api.test.ts
git commit -m "feat(certificados): api do front (modelos + imagens) + campos"
```

---

## Task 7: Frontend — nav + rota + página (abas) + aba Modelos (lista + editor)

**Files:**
- Modify: `frontend/src/components/ui/icons.tsx` (ícone `IconCertificado`, se não houver adequado)
- Modify: `frontend/src/layout/Sidebar.tsx` (item de nav)
- Modify: `frontend/src/app/routes.tsx` (rota)
- Create: `frontend/src/app/certificados/CertificadosPage.tsx`
- Create: `frontend/src/app/certificados/ModelosTab.tsx`

- [ ] **Step 1: Ícone** — em `frontend/src/components/ui/icons.tsx`, adicione (segue o padrão `base(className)`/`stroke="currentColor"`):

```tsx
export function IconCertificado({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 3h9l4 4v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" />
      <path d="M14 3v4h4M8 17l-1.5 3 2-1 2 1L13 17" />
      <circle cx="10.5" cy="12" r="2.5" />
    </svg>
  )
}
```

- [ ] **Step 2: Nav** — em `frontend/src/layout/Sidebar.tsx`: importar `IconCertificado`; no `NAV_ITEMS`, após "Ordens", adicionar:

```tsx
  { label: 'Certificados', icon: <IconCertificado />, to: '/app/certificados', adminOnly: false },
```

> O item deve aparecer para Admin **e Laboratório**. O filtro atual do Sidebar usa `adminOnly`. Como precisamos Admin+Lab, NÃO use `adminOnly`; em vez disso deixe sem `adminOnly` (visível a todos os internos) — a página em si restringe a edição; e para esconder de outros papéis, aplicar um filtro: se o Sidebar suportar função, melhor; caso contrário, deixar visível a internos e gatear ações. **Decisão:** deixar visível a todos os internos (sem `adminOnly`), pois leitura é liberada; escrita é gateada na página. (Mantém o padrão simples do Sidebar.)

- [ ] **Step 3: Rota** — em `frontend/src/app/routes.tsx`: importar `CertificadosPage` e adicionar `<Route path="certificados" element={<CertificadosPage />} />` (após `ordens`).

- [ ] **Step 4: Página com abas** — Create `frontend/src/app/certificados/CertificadosPage.tsx`:

```tsx
import { useState } from 'react'
import { cn } from '../../lib/utils'
import { ModelosTab } from './ModelosTab'
import { ImagensTab } from './ImagensTab'

const ABAS = ['Modelos', 'Imagens'] as const
type Aba = (typeof ABAS)[number]

export function CertificadosPage() {
  const [aba, setAba] = useState<Aba>('Modelos')
  return (
    <div className="px-4 md:px-6 py-6 space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100">Certificados</h1>
        <p className="text-sm text-slate-500 mt-0.5">Modelos de certificado por aparelho e biblioteca de imagens.</p>
      </div>
      <div className="flex gap-2">
        {ABAS.map((a) => (
          <button key={a} onClick={() => setAba(a)}
            className={cn('text-xs px-3 py-1.5 rounded-full font-medium transition-all',
              aba === a ? 'bg-primary/15 text-primary' : 'text-slate-500 hover:text-slate-300 hover:bg-background-elevated')}>
            {a}
          </button>
        ))}
      </div>
      {aba === 'Modelos' ? <ModelosTab /> : <ImagensTab />}
    </div>
  )
}
```

> `ImagensTab` é criado na Task 8. Para esta task compilar, criar um stub `frontend/src/app/certificados/ImagensTab.tsx` com `export function ImagensTab() { return null }` (substituído na Task 8).

- [ ] **Step 5: Aba Modelos (lista + editor)** — Create `frontend/src/app/certificados/ModelosTab.tsx`:

Requisitos: lista de modelos (busca) com selo "Com/Sem certificado"; clicar abre o editor (estado local `selecionado`): textarea de código-fonte HTML (monospace) + pré-visualização em `<iframe sandbox srcDoc={texto}>` lado a lado; bloco de campos disponíveis (`CAMPOS_CERTIFICADO`) como chips; botão Salvar (gated por `podeEditar = isAdmin || funcao==='Laboratório'`); botão Voltar à lista. Implementação de referência:

```tsx
import { useEffect, useState } from 'react'
import { certificadosApi, CAMPOS_CERTIFICADO, type ModeloItem } from './api'
import { Spinner } from '../../components/ui/Spinner'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Badge } from '../../components/ui/Badge'
import { useAuth } from '../../auth/AuthContext'
import { isAdmin } from '../../auth/roles'
import { ApiError } from '../../lib/api'

export function ModelosTab() {
  const { user } = useAuth()
  const podeEditar = isAdmin(user) || user?.funcao === 'Laboratório'
  const [q, setQ] = useState('')
  const [busca, setBusca] = useState('')
  const [itens, setItens] = useState<ModeloItem[] | null>(null)
  const [selecionado, setSelecionado] = useState<ModeloItem | null>(null)
  const [texto, setTexto] = useState('')
  const [descricao, setDescricao] = useState('')
  const [carregandoEd, setCarregandoEd] = useState(false)
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState('')

  useEffect(() => {
    let vivo = true
    certificadosApi.listarModelos({ q: busca || undefined })
      .then((r) => { if (vivo) setItens(r.items) })
      .catch(() => { if (vivo) setItens([]) })
    return () => { vivo = false }
  }, [busca])

  function abrir(m: ModeloItem) {
    setSelecionado(m); setErro(''); setCarregandoEd(true)
    certificadosApi.obterModelo(m.equipamento)
      .then((c) => { setTexto(c.texto); setDescricao(c.descricao ?? '') })
      .catch(() => setErro('Falha ao carregar o certificado'))
      .finally(() => setCarregandoEd(false))
  }

  async function salvar() {
    if (!selecionado) return
    setSalvando(true); setErro('')
    try {
      await certificadosApi.salvarModelo(selecionado.equipamento, { descricao: descricao.trim() || null, texto })
      // atualiza flag na lista
      setItens((cur) => cur?.map((m) => m.equipamento === selecionado.equipamento ? { ...m, tem_certificado: true } : m) ?? null)
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao salvar')
    } finally { setSalvando(false) }
  }

  if (selecionado) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <button onClick={() => setSelecionado(null)} className="text-xs text-primary hover:underline">← Modelos</button>
            <h2 className="text-lg font-bold text-slate-100">{selecionado.equipamento_descricao}</h2>
          </div>
          {podeEditar && <Button onClick={salvar} disabled={salvando || carregandoEd}>{salvando ? 'Salvando…' : 'Salvar'}</Button>}
        </div>
        {erro && <p className="text-sm text-danger">{erro}</p>}
        <div className="flex flex-wrap gap-1.5">
          {CAMPOS_CERTIFICADO.map((c) => (
            <span key={c.campo} title={c.desc} className="rounded-full bg-background-elevated border border-border px-2 py-0.5 text-xs text-slate-400 font-mono">{c.campo}</span>
          ))}
        </div>
        {carregandoEd ? <div className="py-10 flex justify-center"><Spinner className="w-7 h-7" /></div> : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Input id="cert-desc" label="Descrição (opcional)" value={descricao} onChange={(e) => setDescricao(e.target.value)} />
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide">Código-fonte (HTML)</label>
              <textarea value={texto} onChange={(e) => setTexto(e.target.value)} readOnly={!podeEditar}
                className="w-full h-[60vh] px-3 py-2 text-xs font-mono rounded-lg border border-border bg-background-elevated text-slate-200 focus:outline-none focus:ring-2 focus:ring-primary/50" />
            </div>
            <div className="space-y-2">
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide">Pré-visualização</label>
              <iframe title="preview" sandbox="" srcDoc={texto} className="w-full h-[60vh] rounded-lg border border-border bg-white" />
            </div>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <form onSubmit={(e) => { e.preventDefault(); setBusca(q.trim()) }} className="flex gap-2 items-end">
        <Input id="busca-modelo" label="Buscar modelo" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ex.: Mark X" />
        <Button type="submit" variant="secondary">Buscar</Button>
      </form>
      {itens === null ? <div className="py-10 flex justify-center"><Spinner className="w-7 h-7" /></div> : (
        <div className="rounded-xl border border-border divide-y divide-border overflow-hidden">
          {itens.map((m) => (
            <button key={m.equipamento} onClick={() => abrir(m)}
              className="w-full flex items-center justify-between gap-3 px-4 py-3 text-left hover:bg-background-elevated transition-colors">
              <span className="text-sm text-slate-200">{m.equipamento_descricao ?? `#${m.equipamento}`}</span>
              <Badge tone={m.tem_certificado ? 'primary' : 'neutral'}>{m.tem_certificado ? 'Com certificado' : 'Sem certificado'}</Badge>
            </button>
          ))}
          {itens.length === 0 && <p className="px-4 py-8 text-center text-sm text-slate-500">Nenhum modelo.</p>}
        </div>
      )}
    </div>
  )
}
```

> Confira a API de `Badge`/`Input`/`Button` (já usadas no projeto). O `iframe sandbox=""` (sem `allow-scripts`) isola o HTML. As imagens públicas no HTML colado usam URL relativa começando por `/certificado-imagens/arquivo/...` — para o iframe resolver, o HTML deve usar URL absoluta da API OU o iframe ter `<base href>`. Decisão simples: instruir o usuário a colar a URL completa da imagem (a aba Imagens já entrega a URL pronta — ver Task 8, que pode mostrar a URL absoluta).

- [ ] **Step 6: Verificação**

Run: `cd frontend && npx tsc -b --noEmit && npx eslint src/app/certificados src/layout/Sidebar.tsx src/app/routes.tsx src/components/ui/icons.tsx && npm run build`
Expected: verde.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/ui/icons.tsx frontend/src/layout/Sidebar.tsx frontend/src/app/routes.tsx frontend/src/app/certificados/CertificadosPage.tsx frontend/src/app/certificados/ModelosTab.tsx frontend/src/app/certificados/ImagensTab.tsx
git commit -m "feat(certificados): nav + página com abas + aba Modelos (código-fonte + preview)"
```

---

## Task 8: Frontend — aba Imagens

**Files:**
- Modify: `frontend/src/app/certificados/ImagensTab.tsx` (substitui o stub)

- [ ] **Step 1: Implement** — substitua `frontend/src/app/certificados/ImagensTab.tsx`:

Requisitos: grade das imagens (miniatura via URL absoluta), com nome, **URL absoluta + botão copiar** e excluir; botão enviar imagem (nome opcional). Para a URL absoluta, montar `apiBase + img.url`. Reusar o resolvedor de base de `lib/api.ts` — se houver um export (ex.: `API_URL`/`apiBase`); se não houver, derivar com a mesma ordem (`window.__API_URL__` → `import.meta.env.VITE_API_URL` → `http://localhost:8000`). Implementação de referência:

```tsx
import { useEffect, useState } from 'react'
import { certificadosApi, type ImagemCert } from './api'
import { Spinner } from '../../components/ui/Spinner'
import { Button } from '../../components/ui/Button'
import { useAuth } from '../../auth/AuthContext'
import { isAdmin } from '../../auth/roles'
import { ApiError } from '../../lib/api'

function apiBase(): string {
  const w = window as unknown as { __API_URL__?: string }
  return (w.__API_URL__ && w.__API_URL__.length ? w.__API_URL__ : (import.meta.env.VITE_API_URL ?? 'http://localhost:8000')).replace(/\/$/, '')
}

export function ImagensTab() {
  const { user } = useAuth()
  const podeEditar = isAdmin(user) || user?.funcao === 'Laboratório'
  const [itens, setItens] = useState<ImagemCert[] | null>(null)
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [copiada, setCopiada] = useState<number | null>(null)

  function recarregar() {
    certificadosApi.listarImagens().then((r) => setItens(r.items)).catch(() => setItens([]))
  }
  useEffect(() => { recarregar() }, [])

  async function onEnviar(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setEnviando(true); setErro('')
    try {
      await certificadosApi.enviarImagem(file)
      recarregar()
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao enviar imagem')
    } finally { setEnviando(false); e.target.value = '' }
  }

  async function onExcluir(id: number) {
    if (!window.confirm('Excluir esta imagem?')) return
    try { await certificadosApi.excluirImagem(id); recarregar() }
    catch { setErro('Falha ao excluir') }
  }

  async function copiar(img: ImagemCert) {
    const url = apiBase() + img.url
    try { await navigator.clipboard.writeText(url); setCopiada(img.id); setTimeout(() => setCopiada(null), 1500) } catch { /* ignore */ }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-500">Imagens disponíveis para usar nos certificados (cole a URL no HTML do modelo).</p>
        {podeEditar && (
          <label className="cursor-pointer">
            <span className="inline-flex items-center rounded-lg px-3 py-1.5 text-xs font-semibold bg-primary text-white hover:bg-primary-600 transition-colors">
              {enviando ? 'Enviando…' : 'Enviar imagem'}
            </span>
            <input type="file" accept="image/*" className="hidden" onChange={onEnviar} disabled={enviando} />
          </label>
        )}
      </div>
      {erro && <p className="text-sm text-danger">{erro}</p>}
      {itens === null ? <div className="py-10 flex justify-center"><Spinner className="w-7 h-7" /></div> : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhuma imagem.</p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
          {itens.map((img) => (
            <div key={img.id} className="rounded-xl border border-border bg-background-surface p-3 space-y-2">
              <img src={apiBase() + img.url} alt={img.nome ?? 'imagem'} className="w-full h-28 object-contain bg-white rounded-lg" />
              <p className="text-xs text-slate-300 truncate">{img.nome ?? img.arquivo}</p>
              <div className="flex gap-2">
                <button onClick={() => copiar(img)} className="text-xs text-primary hover:underline">{copiada === img.id ? 'Copiado!' : 'Copiar URL'}</button>
                {podeEditar && <button onClick={() => onExcluir(img.id)} className="text-xs text-danger hover:underline ml-auto">Excluir</button>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verificação**

Run: `cd frontend && npx tsc -b --noEmit && npx eslint src/app/certificados && npm run build && npx vitest run`
Expected: verde.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/certificados/ImagensTab.tsx
git commit -m "feat(certificados): aba Imagens (upload + URL pública + copiar)"
```

---

## Task 9: Changelog v1.3.0 + verificação E2E + memória

**Files:**
- Modify: `frontend/src/app/changelog/data.ts`

- [ ] **Step 1: Changelog** — em `frontend/src/app/changelog/data.ts`, no topo do `CHANGELOG`:

```ts
  {
    versao: '1.3.0',
    data: '08/06/2026',
    itens: [
      { tipo: 'novidade', texto: 'Cadastro de Certificados — modelos de certificado por aparelho (edição em HTML com pré-visualização) e biblioteca de imagens para usar nos certificados.' },
    ],
  },
```

- [ ] **Step 2: Validar changelog + suíte**

Run: `cd frontend && npx vitest run src/app/changelog/ && npx tsc -b --noEmit && npm run build`
Expected: verde (`VERSAO_ATUAL` = '1.3.0').

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/changelog/data.ts
git commit -m "feat(changelog): v1.3.0 — cadastro de certificados"
```

- [ ] **Step 4: E2E manual** (após aplicar a migração 0006 — Task 5 Step 4, com o usuário)

Com backend (:8000) e frontend (:5173) no ar, login admin:
1. Nav "Certificados" → aba Modelos: ver a lista (12 com selo "Com certificado").
2. Abrir "Bafômetro Mark X - Plus" → ver o HTML legado no código-fonte + preview renderizando; editar e Salvar.
3. Aba Imagens: enviar uma imagem → copiar URL → abrir a URL no navegador (sem login) → imagem aparece.
> Limpar dados de teste se criar.

- [ ] **Step 5: Atualizar memória do projeto**

Atualizar `project_gestorhs.md`: registrar a página de Certificados (modelos por aparelho + imagens públicas, migração 0006, v1.3.0) e que é a base para a **geração do certificado no laboratório** (próxima etapa).

---

## Self-Review

**Cobertura da spec:** modelos+imagem (Task 1), schemas (Task 2), router modelos list/get/upsert + permissões (Task 3), imagens CRUD + serve público + path-traversal (Task 4), migração 0006 conserta FK + remap + certificado_imagens (Task 5), front api+campos (Task 6), nav/rota/abas/Modelos editor com iframe sandbox + campos (Task 7), aba Imagens com URL pública (Task 8), changelog v1.3.0 + E2E + memória (Task 9). ✓ Geração de PDF explicitamente fora. ✓

**Placeholders:** nenhum "TBD"; notas de implementação (Badge/Input API, base da API, nome real da FK no Postgres) são verificações pontuais, não lacunas de lógica.

**Consistência de tipos/nomes:** backend `CertificadoModelo`(tabela `certificados`, col `equipamento`), `CertificadoImagem`(`certificado_imagens`, `arquivo`/`nome`/`datacad`, prop `url`); schemas `ModeloItem/ModeloPage/CertificadoModeloOut/CertificadoModeloIn/ImagemOut/ImagemPage`; rotas `/certificados-modelo`, `/certificados-modelo/{id}`, `/certificado-imagens`, `/certificado-imagens/{id}`, `/certificado-imagens/arquivo/{nome}`(público); front `certificadosApi.{listarModelos,obterModelo,salvarModelo,listarImagens,enviarImagem,excluirImagem}`, `CAMPOS_CERTIFICADO`, tipos `ModeloItem/CertificadoModelo/ImagemCert`. Consistentes. ✓
- Subdir de storage `"certificado-imagens"` usado igual no salvar/servir/remover. ✓
