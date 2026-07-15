# Aba "Certificados Gerais" com link público + QR — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para implementar tarefa a tarefa. Passos usam checkbox (`- [ ]`).

**Goal:** Aba "Gerais" na página Certificados para anexar PDFs avulsos (nome + arquivo), cada um com link público assinado (HMAC) e QR code baixável, reusando o mecanismo de link público já existente.

**Architecture:** Backend — modelo `CertificadoGeral`, migração `0015`, módulo de link HMAC `certgeral:{id}`, endpoint público `/publico/certificado-geral/{id}` (PDF inline), router CRUD `/certificados-gerais`. Frontend — aba nova em `CertificadosPage`, componente `CertificadosGeraisTab` (upload, lista, copiar link, QR baixável, excluir), helper de permissão, e a lib `qrcode` gerando o QR no cliente.

**Tech Stack:** Backend Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic. Frontend React 19 · TS · Vite 8 · Tailwind v4 · Vitest. QR: `qrcode` (npm).

## Global Constraints

- Idioma do domínio **PT-BR** em nomes, rotas, mensagens.
- Só **PDF**; limite **10 MB** (padrão do `storage`).
- Permissão de escrita (anexar/excluir): **`("Administrador", "Laboratório", "Qualidade")`**. Leitura da lista: qualquer usuário interno logado.
- Link público via HMAC, namespace **`certgeral:{id}`** (não colidir com `cert:`/`nf:`); base em `CERT_PUBLIC_BASE_URL`; se vazia, link é `None` e a UI trata.
- PDF público servido **inline** com `X-Content-Type-Options: nosniff`.
- Backend: `pytest -q` no container (`docker exec gestorhs-backend pytest -q`). Frontend: `npm run lint && npx tsc -b --noEmit && npm run build && npm test`.
- Commits Conventional Commits em PT-BR sem acentos, uma linha, sem trailer de co-autor.
- Registrar router novo no `main.py` (`include_router`) e modelo novo em `models/__init__.py`.

---

### Task 1: Link público `certificado_geral_link.py` (puro)

**Files:**
- Create: `backend/app/core/certificado_geral_link.py`
- Test: `backend/tests/test_certificado_geral_link.py`

**Interfaces:**
- Produces: `assinar(id: int) -> str`, `verificar(id: int, token: str | None) -> bool`, `link_certificado_geral(id: int) -> str | None`.
- Consumes: `app.core.assinatura` (`assinar(msg)/verificar(msg, token)`), `app.core.config.settings.CERT_PUBLIC_BASE_URL`.

- [ ] **Step 1: Escrever o teste que falha**

```python
# backend/tests/test_certificado_geral_link.py
from app.core import certificado_geral_link as link


def test_assinar_e_verificar_roundtrip():
    t = link.assinar(7)
    assert link.verificar(7, t) is True


def test_token_adulterado_ou_de_outro_id_falha():
    t = link.assinar(7)
    assert link.verificar(8, t) is False        # id diferente
    assert link.verificar(7, t + "x") is False  # token adulterado
    assert link.verificar(7, None) is False


def test_link_none_quando_base_vazia(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "CERT_PUBLIC_BASE_URL", "")
    assert link.link_certificado_geral(7) is None


def test_link_montado_com_base(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "CERT_PUBLIC_BASE_URL", "https://x.com/")
    url = link.link_certificado_geral(7)
    assert url is not None
    assert url.startswith("https://x.com/publico/certificado-geral/7?t=")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker exec gestorhs-backend pytest -q tests/test_certificado_geral_link.py`
Expected: FAIL — módulo `certificado_geral_link` não existe.

- [ ] **Step 3: Implementar o módulo**

```python
# backend/app/core/certificado_geral_link.py
"""Link publico assinado para download de certificado geral (sem login)."""
from app.core import assinatura
from app.core.config import settings


def _mensagem(cert_id: int) -> str:
    return f"certgeral:{cert_id}"


def assinar(cert_id: int) -> str:
    return assinatura.assinar(_mensagem(cert_id))


def verificar(cert_id: int, token: str | None) -> bool:
    return assinatura.verificar(_mensagem(cert_id), token)


def link_certificado_geral(cert_id: int) -> str | None:
    base = settings.CERT_PUBLIC_BASE_URL
    if not base:
        return None
    return f"{base.rstrip('/')}/publico/certificado-geral/{cert_id}?t={assinar(cert_id)}"
```

- [ ] **Step 4: Rodar e ver passar**

Run: `docker exec gestorhs-backend pytest -q tests/test_certificado_geral_link.py`
Expected: PASS (4 testes).

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/certificado_geral_link.py backend/tests/test_certificado_geral_link.py
git commit -m "feat(cert): link publico assinado para certificado geral"
```

---

### Task 2: Modelo, migração, schema e router CRUD `/certificados-gerais`

**Files:**
- Create: `backend/app/models/certificado_geral.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/0015_certificado_geral.py`
- Create: `backend/app/schemas/certificado_geral.py`
- Create: `backend/app/api/certificados_gerais.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_certificados_gerais.py`

**Interfaces:**
- `CertificadoGeral` model: `id, nome(String200, not null), arquivo(String64, not null), usuario(FK usuarios.id, nullable), data_upload(DateTime tz)`, property `usuario_nome`.
- `CertificadoGeralOut` (Pydantic, `from_attributes`): `id, nome, data_upload, usuario_nome, link: str | None`. `link` é preenchido pelo router (não é coluna).
- Router `/certificados-gerais`: `POST ""` (multipart `nome: Form`, `arquivo: UploadFile`) → 201; `GET ""` → lista; `DELETE /{id}` → 200. `GESTOR_CERT_GERAL = ("Administrador", "Laboratório", "Qualidade")`.
- Consumes: `storage.salvar_upload/remover_arquivo/caminho_arquivo/TIPOS_PDF/ArquivoInvalido`, `certificado_geral_link.link_certificado_geral`, `deps.get_current_usuario/require_funcao`.
- Subdir de storage: constante `SUBDIR = "certificados-gerais"` no router.

- [ ] **Step 1: Modelo + registro em `models/__init__.py`**

```python
# backend/app/models/certificado_geral.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.models.database import Base


class CertificadoGeral(Base):
    """Documento PDF avulso (ex.: certificado de gas anual), sem vinculo com OS/cliente.

    Servido ao publico so por link HMAC assinado (certgeral:{id})."""
    __tablename__ = "certificados_gerais"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(200), nullable=False)
    arquivo = Column(String(64), nullable=False)   # basename do PDF no storage
    usuario = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    data_upload = Column(DateTime(timezone=True), nullable=True)

    usuario_rel = relationship("Usuario", lazy="joined")

    @property
    def usuario_nome(self):
        return self.usuario_rel.nome if self.usuario_rel else None
```

Em `backend/app/models/__init__.py`: adicionar `from app.models.certificado_geral import CertificadoGeral` (junto das outras importações de modelo) e incluir `"CertificadoGeral"` na lista `__all__`.

- [ ] **Step 2: Migração 0015**

```python
# backend/alembic/versions/0015_certificado_geral.py
"""certificados gerais: documento PDF avulso com link publico

Revision ID: 0015_certificado_geral
Revises: 0014_certificado_avulso
"""
from alembic import op
import sqlalchemy as sa

revision = "0015_certificado_geral"
down_revision = "0014_certificado_avulso"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "certificados_gerais",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(200), nullable=False),
        sa.Column("arquivo", sa.String(64), nullable=False),
        sa.Column("usuario", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("data_upload", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_table("certificados_gerais")
```

- [ ] **Step 3: Schema**

```python
# backend/app/schemas/certificado_geral.py
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CertificadoGeralOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nome: str
    data_upload: Optional[datetime] = None
    usuario_nome: Optional[str] = None
    link: Optional[str] = None
```

- [ ] **Step 4: Escrever o teste do router (falha)**

```python
# backend/tests/test_certificados_gerais.py
import io


def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _pdf():
    return ("cert.pdf", io.BytesIO(b"%PDF-1.4 conteudo"), "application/pdf")


def test_anexar_lista_e_link(client, usuario_lab, db_session, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "CERT_PUBLIC_BASE_URL", "https://x.com")
    h = _headers(client, "lab@hs.com", "senha123")
    r = client.post("/certificados-gerais", data={"nome": "Certificado de Gas 2027"},
                    files={"arquivo": _pdf()}, headers=h)
    assert r.status_code == 201
    body = r.json()
    assert body["nome"] == "Certificado de Gas 2027"
    assert body["link"] and "/publico/certificado-geral/" in body["link"]

    itens = client.get("/certificados-gerais", headers=h).json()
    assert len(itens) == 1 and itens[0]["nome"] == "Certificado de Gas 2027"


def test_anexar_exige_permissao_403(client, usuario_comercial, db_session):
    h = _headers(client, "comercial@hs.com", "senha123")
    r = client.post("/certificados-gerais", data={"nome": "X"},
                    files={"arquivo": _pdf()}, headers=h)
    assert r.status_code == 403


def test_anexar_recusa_nao_pdf_415(client, usuario_lab, db_session):
    h = _headers(client, "lab@hs.com", "senha123")
    r = client.post("/certificados-gerais", data={"nome": "X"},
                    files={"arquivo": ("a.png", io.BytesIO(b"x"), "image/png")}, headers=h)
    assert r.status_code == 415


def test_nome_obrigatorio_422(client, usuario_lab, db_session):
    h = _headers(client, "lab@hs.com", "senha123")
    r = client.post("/certificados-gerais", data={"nome": "   "},
                    files={"arquivo": _pdf()}, headers=h)
    assert r.status_code == 422


def test_excluir_remove(client, usuario_lab, db_session):
    from app.models import CertificadoGeral
    h = _headers(client, "lab@hs.com", "senha123")
    cid = client.post("/certificados-gerais", data={"nome": "Gas"},
                      files={"arquivo": _pdf()}, headers=h).json()["id"]
    assert client.delete(f"/certificados-gerais/{cid}", headers=h).status_code == 200
    assert db_session.query(CertificadoGeral).count() == 0
```

Nota: se as fixtures `usuario_lab`/`usuario_comercial` não existirem em `conftest.py`, criar espelhando as já usadas em `test_certificado_avulso.py` (mesma senha `senha123`).

- [ ] **Step 5: Rodar e ver falhar**

Run: `docker exec gestorhs-backend pytest -q tests/test_certificados_gerais.py`
Expected: FAIL — router/model não existem.

- [ ] **Step 6: Implementar o router + registrar no main**

```python
# backend/app/api/certificados_gerais.py
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_usuario, require_funcao
from app.core import certificado_geral_link, storage
from app.models import CertificadoGeral, Usuario
from app.models.database import get_db
from app.schemas.certificado_geral import CertificadoGeralOut

router = APIRouter(prefix="/certificados-gerais", tags=["certificados-gerais"])

GESTOR_CERT_GERAL = ("Administrador", "Laboratório", "Qualidade")
SUBDIR = "certificados-gerais"


def _out(c: CertificadoGeral) -> CertificadoGeralOut:
    dto = CertificadoGeralOut.model_validate(c)
    dto.link = certificado_geral_link.link_certificado_geral(c.id)
    return dto


@router.post("", response_model=CertificadoGeralOut, status_code=status.HTTP_201_CREATED)
def anexar(nome: str = Form(...), arquivo: UploadFile = File(...),
           db: Session = Depends(get_db),
           usuario: Usuario = Depends(require_funcao(*GESTOR_CERT_GERAL))):
    nome_limpo = (nome or "").strip()
    if not nome_limpo:
        raise HTTPException(422, "nome é obrigatório")
    if len(nome_limpo) > 200:
        raise HTTPException(422, "nome muito longo (máx. 200)")
    try:
        basename = storage.salvar_upload(arquivo, subdir=SUBDIR, tipos_permitidos=storage.TIPOS_PDF)
    except storage.ArquivoInvalido as e:
        raise HTTPException(e.status, e.detail)
    c = CertificadoGeral(nome=nome_limpo, arquivo=basename, usuario=usuario.id,
                         data_upload=datetime.now(timezone.utc))
    db.add(c); db.commit(); db.refresh(c)
    return _out(c)


@router.get("", response_model=list[CertificadoGeralOut])
def listar(db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    itens = db.query(CertificadoGeral).order_by(CertificadoGeral.id.desc()).all()
    return [_out(c) for c in itens]


@router.delete("/{cert_id}")
def excluir(cert_id: int, db: Session = Depends(get_db),
            _: Usuario = Depends(require_funcao(*GESTOR_CERT_GERAL))):
    c = db.query(CertificadoGeral).filter(CertificadoGeral.id == cert_id).first()
    if c is None:
        raise HTTPException(404, "certificado não encontrado")
    storage.remover_arquivo(SUBDIR, c.arquivo)
    db.delete(c); db.commit()
    return {"ok": True}
```

Em `backend/app/main.py`: adicionar `certificados_gerais` na linha de import do `app.api` e `app.include_router(certificados_gerais.router)` junto dos outros.

- [ ] **Step 7: Rodar e ver passar**

Run: `docker exec gestorhs-backend pytest -q tests/test_certificados_gerais.py`
Expected: PASS (5 testes).

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/certificado_geral.py backend/app/models/__init__.py backend/alembic/versions/0015_certificado_geral.py backend/app/schemas/certificado_geral.py backend/app/api/certificados_gerais.py backend/app/main.py backend/tests/test_certificados_gerais.py
git commit -m "feat(cert): CRUD de certificados gerais com upload de PDF"
```

---

### Task 3: Endpoint público de download

**Files:**
- Modify: `backend/app/api/publico.py`
- Test: `backend/tests/test_publico_certificado_geral.py`

**Interfaces:**
- `GET /publico/certificado-geral/{cert_id}?t=…` — valida `certificado_geral_link.verificar`; carrega `CertificadoGeral`; serve o PDF do disco via `FileResponse` (`inline`, `nosniff`). 403 link inválido, 404 não encontrado.
- Consumes: `certificado_geral_link`, `storage`, `CertificadoGeral`.

- [ ] **Step 1: Escrever o teste (falha)**

```python
# backend/tests/test_publico_certificado_geral.py
import io


def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _anexar(client, db_session):
    h = _headers(client, "lab@hs.com", "senha123")
    return client.post("/certificados-gerais", data={"nome": "Gas"},
                       files={"arquivo": ("g.pdf", io.BytesIO(b"%PDF-1.4 x"), "application/pdf")},
                       headers=h).json()["id"]


def test_download_publico_com_token_valido(client, usuario_lab, db_session):
    from app.core import certificado_geral_link
    cid = _anexar(client, db_session)
    t = certificado_geral_link.assinar(cid)
    r = client.get(f"/publico/certificado-geral/{cid}?t={t}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "inline" in r.headers.get("content-disposition", "")


def test_download_publico_token_invalido_403(client, usuario_lab, db_session):
    cid = _anexar(client, db_session)
    assert client.get(f"/publico/certificado-geral/{cid}?t=errado").status_code == 403


def test_download_publico_inexistente_404(client):
    from app.core import certificado_geral_link
    t = certificado_geral_link.assinar(9999)
    assert client.get(f"/publico/certificado-geral/9999?t={t}").status_code == 404
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker exec gestorhs-backend pytest -q tests/test_publico_certificado_geral.py`
Expected: FAIL — rota não existe (404 sem checar token / rota ausente).

- [ ] **Step 3: Implementar o endpoint**

Em `backend/app/api/publico.py`: adicionar `certificado_geral_link` e `CertificadoGeral` aos imports, o `SUBDIR_CERT_GERAL = "certificados-gerais"`, e a rota:

```python
@router.get("/certificado-geral/{cert_id}")
def baixar_certificado_geral_publico(cert_id: int, t: str = "", db: Session = Depends(get_db)):
    if not certificado_geral_link.verificar(cert_id, t):
        raise HTTPException(status_code=403, detail="link inválido")
    c = db.query(CertificadoGeral).filter(CertificadoGeral.id == cert_id).first()
    if c is None or not c.arquivo:
        raise HTTPException(status_code=404, detail="certificado não encontrado")
    try:
        caminho = storage.caminho_arquivo("certificados-gerais", c.arquivo)
    except storage.ArquivoInvalido:
        raise HTTPException(status_code=404, detail="arquivo não encontrado")
    if not caminho.exists():
        raise HTTPException(status_code=404, detail="arquivo não encontrado")
    return FileResponse(
        caminho,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="certificado-geral-{cert_id}.pdf"',
            "X-Content-Type-Options": "nosniff",
        },
    )
```

(o import `certificado_geral` deve ser adicionado à linha `from app.core import ...` existente; `CertificadoGeral` à linha `from app.models import ...`.)

- [ ] **Step 4: Rodar e ver passar**

Run: `docker exec gestorhs-backend pytest -q tests/test_publico_certificado_geral.py`
Expected: PASS (3 testes).

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/publico.py backend/tests/test_publico_certificado_geral.py
git commit -m "feat(cert): download publico de certificado geral por link assinado"
```

---

### Task 4: Frontend — aba "Gerais" (upload, lista, link, QR, excluir)

**Files:**
- Modify: `frontend/package.json` (dependência `qrcode` + `@types/qrcode`)
- Modify: `frontend/src/app/certificados/api.ts`
- Modify: `frontend/src/auth/roles.ts`
- Create: `frontend/src/app/certificados/CertificadosGeraisTab.tsx`
- Modify: `frontend/src/app/certificados/CertificadosPage.tsx`
- Test: `frontend/src/app/certificados/api.geral.test.ts`
- Test: `frontend/src/auth/roles.geral.test.ts`

**Interfaces:**
- `certificadosApi.listarGerais(): Promise<CertGeralItem[]>`, `enviarGeral(nome, file): Promise<CertGeralItem>`, `excluirGeral(id): Promise<void>`.
- `CertGeralItem = { id: number; nome: string; data_upload: string | null; usuario_nome: string | null; link: string | null }`.
- `podeGerenciarCertificadosGerais(user): boolean` = admin || funcao ∈ {'Laboratório','Qualidade'}.

- [ ] **Step 1: Instalar a lib de QR**

Run (na pasta frontend):
```bash
npm i qrcode && npm i -D @types/qrcode
```
Expected: instala sem erro; `package.json`/`package-lock.json` atualizados.

- [ ] **Step 2: Escrever os testes que falham**

```ts
// frontend/src/app/certificados/api.geral.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { certificadosApi } from './api'
import { setTokens } from '../../lib/auth-storage'

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('certificadosApi (gerais)', () => {
  beforeEach(() => { localStorage.clear(); vi.restoreAllMocks(); setTokens({ access_token: 't', refresh_token: 'r' }) })

  it('listarGerais bate no path certo', async () => {
    const f = vi.fn().mockResolvedValue(json([]))
    vi.stubGlobal('fetch', f)
    await certificadosApi.listarGerais()
    expect(String(f.mock.calls[0][0])).toContain('/certificados-gerais')
  })

  it('enviarGeral manda multipart com nome e arquivo', async () => {
    const f = vi.fn().mockResolvedValue(json({ id: 1, nome: 'Gas', data_upload: null, usuario_nome: null, link: null }))
    vi.stubGlobal('fetch', f)
    await certificadosApi.enviarGeral('Gas', new File([new Blob(['x'])], 'g.pdf', { type: 'application/pdf' }))
    const init = f.mock.calls[0][1] as RequestInit
    expect(init.method).toBe('POST')
    expect(init.body).toBeInstanceOf(FormData)
  })

  it('excluirGeral usa DELETE', async () => {
    const f = vi.fn().mockResolvedValue(json({ ok: true }))
    vi.stubGlobal('fetch', f)
    await certificadosApi.excluirGeral(3)
    const init = f.mock.calls[0][1] as RequestInit
    expect(String(f.mock.calls[0][0])).toContain('/certificados-gerais/3')
    expect(init.method).toBe('DELETE')
  })
})
```

```ts
// frontend/src/auth/roles.geral.test.ts
import { describe, it, expect } from 'vitest'
import { podeGerenciarCertificadosGerais } from './roles'

const u = (funcao: string | null) => ({ funcao }) as never

describe('podeGerenciarCertificadosGerais', () => {
  it('libera admin, laboratorio e qualidade', () => {
    expect(podeGerenciarCertificadosGerais(u('Administrador'))).toBe(true)
    expect(podeGerenciarCertificadosGerais(u('Laboratório'))).toBe(true)
    expect(podeGerenciarCertificadosGerais(u('Qualidade'))).toBe(true)
  })
  it('bloqueia outras funcoes e null', () => {
    expect(podeGerenciarCertificadosGerais(u('Comercial Pós-Vendas'))).toBe(false)
    expect(podeGerenciarCertificadosGerais(null)).toBe(false)
  })
})
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `cd frontend && npx vitest run src/app/certificados/api.geral.test.ts src/auth/roles.geral.test.ts`
Expected: FAIL — funções não existem.

- [ ] **Step 4: `api.ts` + `roles.ts`**

Em `frontend/src/app/certificados/api.ts` adicionar o tipo e, dentro do objeto `certificadosApi`, os métodos:

```ts
export interface CertGeralItem {
  id: number
  nome: string
  data_upload: string | null
  usuario_nome: string | null
  link: string | null
}
```
```ts
  listarGerais: (): Promise<CertGeralItem[]> => apiJson<CertGeralItem[]>('/certificados-gerais'),
  enviarGeral: async (nome: string, file: File): Promise<CertGeralItem> => {
    const fd = new FormData()
    fd.append('nome', nome)
    fd.append('arquivo', file)
    const res = await apiFetch('/certificados-gerais', { method: 'POST', body: fd })
    if (!res.ok) {
      let detail = res.statusText
      try { const b = await res.json(); if (b.detail) detail = b.detail } catch { /* sem corpo */ }
      throw new ApiError(res.status, detail)
    }
    return (await res.json()) as CertGeralItem
  },
  excluirGeral: (id: number): Promise<void> => apiVoid(`/certificados-gerais/${id}`, { method: 'DELETE' }),
```

Em `frontend/src/auth/roles.ts` adicionar:
```ts
export const FUNCAO_LABORATORIO = 'Laboratório'
export const FUNCAO_QUALIDADE = 'Qualidade'

export function podeGerenciarCertificadosGerais(user: User | null): boolean {
  return isAdmin(user) || user?.funcao === FUNCAO_LABORATORIO || user?.funcao === FUNCAO_QUALIDADE
}
```

- [ ] **Step 5: Rodar e ver passar (api + roles)**

Run: `cd frontend && npx vitest run src/app/certificados/api.geral.test.ts src/auth/roles.geral.test.ts`
Expected: PASS.

- [ ] **Step 6: Componente `CertificadosGeraisTab.tsx`**

```tsx
import { useEffect, useState } from 'react'
import QRCode from 'qrcode'
import { certificadosApi, type CertGeralItem } from './api'
import { Spinner } from '../../components/ui/Spinner'
import { useAuth } from '../../auth/AuthContext'
import { podeGerenciarCertificadosGerais } from '../../auth/roles'
import { ApiError } from '../../lib/api'

export function CertificadosGeraisTab() {
  const { user } = useAuth()
  const podeEditar = podeGerenciarCertificadosGerais(user)
  const [itens, setItens] = useState<CertGeralItem[] | null>(null)
  const [nome, setNome] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [copiado, setCopiado] = useState<number | null>(null)
  const [qr, setQr] = useState<{ id: number; url: string } | null>(null)

  function recarregar() {
    certificadosApi.listarGerais().then(setItens).catch(() => setItens([]))
  }
  useEffect(recarregar, [])

  async function onEnviar(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    if (!nome.trim()) { setErro('Dê um nome antes de anexar o arquivo'); e.target.value = ''; return }
    setEnviando(true); setErro('')
    try { await certificadosApi.enviarGeral(nome.trim(), file); setNome(''); recarregar() }
    catch (err) { setErro(err instanceof ApiError ? err.message : 'Falha ao anexar') }
    finally { setEnviando(false); e.target.value = '' }
  }

  async function copiar(item: CertGeralItem) {
    if (!item.link) return
    try { await navigator.clipboard.writeText(item.link); setCopiado(item.id); setTimeout(() => setCopiado(null), 1500) } catch { /* ignore */ }
  }

  async function mostrarQr(item: CertGeralItem) {
    if (!item.link) return
    if (qr?.id === item.id) { setQr(null); return }
    const url = await QRCode.toDataURL(item.link, { width: 240, margin: 1 })
    setQr({ id: item.id, url })
  }

  async function onExcluir(id: number) {
    if (!window.confirm('Excluir este certificado?')) return
    try { await certificadosApi.excluirGeral(id); recarregar() }
    catch { setErro('Falha ao excluir') }
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-500">
        Certificados gerais (ex.: certificado de gás anual). Anexe o PDF, dê um nome e compartilhe o link/QR com o cliente — sem precisar de login.
      </p>

      {podeEditar && (
        <div className="flex flex-wrap items-end gap-3 rounded-2xl bg-background-surface border border-border p-4">
          <div className="flex-1 min-w-60">
            <label className="block text-xs font-medium text-slate-400 mb-1">Nome</label>
            <input value={nome} onChange={(e) => setNome(e.target.value)} placeholder="Ex.: Certificado de Gás 2027"
              className="w-full text-sm text-slate-200 bg-background-elevated border border-border rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-primary/40 placeholder-slate-500" />
          </div>
          <label className="cursor-pointer shrink-0">
            <span className="inline-flex items-center rounded-lg px-3 py-2.5 text-sm font-semibold bg-primary text-white hover:bg-primary-600 transition-colors">
              {enviando ? 'Enviando…' : 'Anexar PDF'}
            </span>
            <input type="file" accept="application/pdf" className="hidden" onChange={onEnviar} disabled={enviando} />
          </label>
        </div>
      )}

      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}

      {itens === null ? (
        <div className="py-10 flex justify-center"><Spinner className="w-7 h-7" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum certificado geral anexado.</p>
      ) : (
        <ul className="space-y-2">
          {itens.map((item) => (
            <li key={item.id} className="rounded-2xl bg-background-surface border border-border p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-slate-100">{item.nome}</p>
                  <p className="text-xs text-slate-500">
                    {item.data_upload ? new Date(item.data_upload).toLocaleDateString('pt-BR') : '—'}
                    {item.usuario_nome ? ` · ${item.usuario_nome}` : ''}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {item.link ? (
                    <>
                      <button onClick={() => copiar(item)} className="text-xs font-semibold text-primary hover:underline">
                        {copiado === item.id ? 'Copiado!' : 'Copiar link'}
                      </button>
                      <button onClick={() => mostrarQr(item)} className="text-xs font-semibold text-primary hover:underline">
                        {qr?.id === item.id ? 'Ocultar QR' : 'QR code'}
                      </button>
                    </>
                  ) : (
                    <span className="text-xs text-slate-500">link público indisponível</span>
                  )}
                  {podeEditar && (
                    <button onClick={() => onExcluir(item.id)} className="text-xs font-semibold text-danger hover:underline">Excluir</button>
                  )}
                </div>
              </div>
              {qr?.id === item.id && (
                <div className="mt-3 flex flex-col items-center gap-2">
                  <img src={qr.url} alt={`QR de ${item.nome}`} className="rounded-lg bg-white p-2" width={200} height={200} />
                  <a href={qr.url} download={`qr-${item.nome}.png`} className="text-xs font-semibold text-primary hover:underline">Baixar QR</a>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
```

- [ ] **Step 7: Ligar a aba em `CertificadosPage.tsx`**

Adicionar `'Gerais'` ao array `ABAS` e importar/renderizar `CertificadosGeraisTab`. Ajustar a expressão de render para incluir a nova aba, ex.:
```tsx
import { CertificadosGeraisTab } from './CertificadosGeraisTab'
// ABAS = ['Modelos', 'Imagens', 'Em branco', 'Gerais'] as const
// no render:
{aba === 'Modelos' ? <ModelosTab /> : aba === 'Imagens' ? <ImagensTab /> : aba === 'Em branco' ? <AvulsosTab /> : <CertificadosGeraisTab />}
```

- [ ] **Step 8: Verificar (lint/tsc/build/test)**

Run: `cd frontend && npm run lint && npx tsc -b --noEmit && npm test`
Expected: lint limpo, tipos OK, testes verdes (inclui os novos de api/roles).

- [ ] **Step 9: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/app/certificados/api.ts frontend/src/auth/roles.ts frontend/src/app/certificados/CertificadosGeraisTab.tsx frontend/src/app/certificados/CertificadosPage.tsx frontend/src/app/certificados/api.geral.test.ts frontend/src/auth/roles.geral.test.ts
git commit -m "feat(cert): aba Gerais com upload, link publico e qr code"
```

---

### Task 5: Changelog + verificação completa

**Files:**
- Modify: `frontend/src/app/changelog/data.ts`

- [ ] **Step 1: Bump de versão (v1.16.0)**

Adicionar como primeira entrada de `CHANGELOG`:
```ts
{
  versao: '1.16.0',
  data: '15/07/2026',
  itens: [
    { tipo: 'novidade', texto: 'Nova aba "Gerais" na página Certificados: anexe um PDF (ex.: certificado de gás anual), dê um nome e gere um link público e um QR code para o cliente baixar sem precisar de login — economizando papel. Só PDF, até 10 MB.' },
  ],
},
```

- [ ] **Step 2: Verificação completa**

Run backend: `docker exec gestorhs-backend pytest -q`
Expected: tudo verde (inclui os novos testes de link/CRUD/público).

Run frontend: `cd frontend && npm run lint && npx tsc -b --noEmit && npm run build && npm test`
Expected: lint/tsc/build limpos, testes verdes.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/changelog/data.ts
git commit -m "docs(changelog): v1.16.0 — aba de certificados gerais com link e qr"
```

---

## Self-Review (feita)

- **Cobertura da spec:** modelo+migração (T2), link HMAC (T1), endpoint público inline+nosniff (T3), router CRUD com permissão Admin/Lab/Qualidade e leitura logada (T2), aba com upload/lista/copiar/QR/excluir + permissão (T4), changelog (T5). ✔
- **Sem placeholders:** todo passo tem código concreto e comando com resultado esperado; o único "ajustar a expressão de render" (T4 step 7) traz o exemplo exato. ✔
- **Consistência de tipos:** `CertificadoGeralOut.link` preenchido no router (T2) e consumido no front como `CertGeralItem.link` (T4); `GESTOR_CERT_GERAL`/`podeGerenciarCertificadosGerais` batem com a permissão da spec; `SUBDIR="certificados-gerais"` igual no router (T2) e no público (T3); mensagem HMAC `certgeral:{id}` definida em T1 e usada em T3. ✔
- **Migração:** `0015`, `down_revision=0014_certificado_avulso` (última confirmada). ✔
