# Fase 8 — Anexos (fotos da OS + PDF de certificado) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) ou superpowers:executing-plans para implementar task a task. Os passos usam checkbox (`- [ ]`).

**Goal:** Permitir anexar e servir, com autenticação, fotos do recebimento da OS e o PDF do certificado, gravando em disco sob `UPLOAD_DIR`.

**Architecture:** Uma camada de storage compartilhada grava arquivos em `UPLOAD_DIR/<subdir>/<basename>` e devolve só o basename (cabe em VARCHAR(50)). As fotos usam a tabela `fotos` existente (FK `os`); o PDF guarda o basename em `ordens.pdf_certificado`. Arquivos são servidos por endpoints autenticados (`FileResponse`), com o download de certificado do portal escopado por tenant. **Sem migração de banco.**

**Tech Stack:** FastAPI (UploadFile/Form, `python-multipart`), SQLAlchemy 2, Pydantic v2, pytest; React 19 + TS + Vite + Vitest.

**Spec:** `docs/superpowers/specs/2026-06-04-fase8-anexos-design.md`

**Convenções:** router por arquivo em `app/api/` registrado em `main.py`; auth `get_current_usuario`/`require_funcao(...)`/`get_current_cliente`; testes pytest com `client`/`db_session`/`usuario_admin`/`usuario_comum`(Expedição)/`usuario_lab`(Laboratório)/`os_base`/`cliente_portal`. Frontend: `apiJson` para JSON; uploads/downloads via `apiFetch` + `FormData`/`blob()`.

---

## File Structure

**Backend:**
- Modify: `backend/app/core/config.py` (setting `UPLOAD_DIR`).
- Create: `backend/app/core/storage.py` (helper de arquivos).
- Modify: `backend/requirements.txt` (`python-multipart`).
- Create: `backend/app/models/foto.py`; Modify: `backend/app/models/__init__.py`.
- Create: `backend/app/schemas/fotos.py`.
- Create: `backend/app/api/fotos.py`; Create: `backend/app/api/certificados.py`; Modify: `backend/app/main.py`.
- Modify: `backend/app/api/portal.py` (download de certificado tenant-scoped + `os` no item) e `backend/app/schemas/portal.py`.
- Modify: `backend/tests/conftest.py` (fixture `upload_tmp`); Create: `backend/tests/test_fotos.py`, `backend/tests/test_certificados.py`.

**Frontend:**
- Modify: `frontend/src/app/ordens/api.ts` (`fotosApi`, `certificadoApi`, `baixarBlob`).
- Create: `frontend/src/app/ordens/FotoImg.tsx` (imagem autenticada via blob).
- Modify: `frontend/src/app/ordens/OrdemDetailPage.tsx` (seção Fotos + certificado).
- Modify: `frontend/src/portal/api.ts` (`baixarCertificado`, campo `os` em `PortalCertItem`) e `frontend/src/portal/PortalCertificadosPage.tsx`.
- Create: `frontend/src/app/ordens/anexos.api.test.ts`.

**Infra:**
- Modify: `backend/.env.example`, `docker-compose.yml`, `backend/.gitignore` (ignorar `uploads/` local).

---

## Task 1: Camada de storage + dependência

**Files:**
- Modify: `backend/app/core/config.py`
- Create: `backend/app/core/storage.py`
- Modify: `backend/requirements.txt`
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_storage.py`

- [ ] **Step 1: Adicionar `python-multipart` ao requirements e instalar**

Em `backend/requirements.txt`, acrescentar uma linha:
```
python-multipart
```
Rodar: `cd backend; pip install python-multipart`

- [ ] **Step 2: Adicionar o setting `UPLOAD_DIR`**

Em `backend/app/core/config.py`, dentro de `Settings`, após `REFRESH_TOKEN_EXPIRE_DAYS`:
```python
    UPLOAD_DIR: str = "uploads"
```
(tem default — não quebra testes/CI; produção sobrescreve via env para `/data/uploads`.)

- [ ] **Step 3: Criar `backend/app/core/storage.py`**

```python
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

TIPOS_IMAGEM = {"image/jpeg", "image/png", "image/webp"}
TIPOS_PDF = {"application/pdf"}

_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}


class ArquivoInvalido(Exception):
    """content-type não permitido ou arquivo grande demais."""

    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(detail)


def _base() -> Path:
    return Path(settings.UPLOAD_DIR)


def salvar_upload(file: UploadFile, *, subdir: str, tipos_permitidos: set[str]) -> str:
    if file.content_type not in tipos_permitidos:
        raise ArquivoInvalido(415, "tipo de arquivo não suportado")
    conteudo = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(conteudo) > MAX_UPLOAD_BYTES:
        raise ArquivoInvalido(413, "arquivo acima do limite de 10 MB")
    ext = _EXT.get(file.content_type, "")
    basename = uuid.uuid4().hex[:16] + ext
    destino = _base() / subdir
    destino.mkdir(parents=True, exist_ok=True)
    (destino / basename).write_bytes(conteudo)
    return basename


def caminho_arquivo(subdir: str, basename: str) -> Path:
    base = _base().resolve()
    alvo = (base / subdir / basename).resolve()
    if base not in alvo.parents:
        raise ArquivoInvalido(400, "caminho inválido")
    return alvo


def remover_arquivo(subdir: str, basename: str) -> None:
    try:
        caminho_arquivo(subdir, basename).unlink(missing_ok=True)
    except ArquivoInvalido:
        pass
```

- [ ] **Step 4: Fixture `upload_tmp` no conftest**

Em `backend/tests/conftest.py`, acrescentar (usa `tmp_path` do pytest e restaura o valor):
```python
@pytest.fixture()
def upload_tmp(tmp_path):
    from app.core.config import settings
    anterior = settings.UPLOAD_DIR
    settings.UPLOAD_DIR = str(tmp_path)
    try:
        yield tmp_path
    finally:
        settings.UPLOAD_DIR = anterior
```

- [ ] **Step 5: Escrever os testes do storage** (`backend/tests/test_storage.py`)

```python
import io

import pytest
from fastapi import UploadFile

from app.core import storage
from app.core.storage import ArquivoInvalido


def _upload(nome, conteudo, content_type):
    return UploadFile(filename=nome, file=io.BytesIO(conteudo), headers={"content-type": content_type})


def test_salva_e_le_imagem(upload_tmp):
    base = storage.salvar_upload(_upload("x.jpg", b"abc", "image/jpeg"), subdir="os/1", tipos_permitidos=storage.TIPOS_IMAGEM)
    assert base.endswith(".jpg")
    assert storage.caminho_arquivo("os/1", base).read_bytes() == b"abc"


def test_rejeita_tipo(upload_tmp):
    with pytest.raises(ArquivoInvalido) as e:
        storage.salvar_upload(_upload("x.txt", b"abc", "text/plain"), subdir="os/1", tipos_permitidos=storage.TIPOS_IMAGEM)
    assert e.value.status == 415


def test_rejeita_tamanho(upload_tmp):
    grande = b"x" * (storage.MAX_UPLOAD_BYTES + 1)
    with pytest.raises(ArquivoInvalido) as e:
        storage.salvar_upload(_upload("x.pdf", grande, "application/pdf"), subdir="certificados/1", tipos_permitidos=storage.TIPOS_PDF)
    assert e.value.status == 413


def test_remove(upload_tmp):
    base = storage.salvar_upload(_upload("x.pdf", b"p", "application/pdf"), subdir="certificados/1", tipos_permitidos=storage.TIPOS_PDF)
    storage.remover_arquivo("certificados/1", base)
    assert not storage.caminho_arquivo("certificados/1", base).exists()
```

- [ ] **Step 6: Rodar** `cd backend; python -m pytest tests/test_storage.py -v` → 4 PASS.

- [ ] **Step 7: Ignorar uploads locais.** Em `backend/.gitignore`, acrescentar `uploads/` (se já não estiver coberto).

- [ ] **Step 8: Commit**
```bash
git add backend/app/core/storage.py backend/app/core/config.py backend/requirements.txt backend/tests/conftest.py backend/tests/test_storage.py backend/.gitignore
git commit -m "feat(backend): camada de storage de arquivos (uploads) + python-multipart"
```

---

## Task 2: Fotos da OS — backend (TDD)

**Files:**
- Create: `backend/app/models/foto.py`; Modify: `backend/app/models/__init__.py`
- Create: `backend/app/schemas/fotos.py`
- Create: `backend/app/api/fotos.py`; Modify: `backend/app/main.py`
- Test: `backend/tests/test_fotos.py`

- [ ] **Step 1: Modelo `Foto`** (`backend/app/models/foto.py`)

```python
from sqlalchemy import Column, Integer, String, ForeignKey
from app.models.database import Base


class Foto(Base):
    __tablename__ = "fotos"

    id = Column(Integer, primary_key=True, index=True)
    cliente = Column(Integer, ForeignKey("clientes.id"), nullable=True)
    codigo = Column(Integer, nullable=True)
    cor = Column(Integer, nullable=True, default=0)
    tipo = Column(String(1), nullable=True, default="I")
    posicao = Column(Integer, nullable=True, default=1)
    arquivo = Column(String(50), nullable=True)
    legenda = Column(String(250), nullable=True)
    os = Column(Integer, ForeignKey("ordens.id"), nullable=True)
```

Em `backend/app/models/__init__.py`, importar e exportar `Foto` (seguir o padrão das outras entidades — adicionar `from app.models.foto import Foto` e incluir em `__all__` se houver).

- [ ] **Step 2: Schema** (`backend/app/schemas/fotos.py`)

```python
from pydantic import BaseModel


class FotoOut(BaseModel):
    id: int
    os: int
    arquivo: str
    legenda: str | None = None
    url: str
```

- [ ] **Step 3: Escrever os testes** (`backend/tests/test_fotos.py`)

```python
def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _abrir_os(db_session):
    from app.models import Cliente, Equipamento, EquipamentoCliente, Ordem
    cli = Cliente(nome="Cliente Foto")
    eq = Equipamento(descricao="Bafômetro")
    db_session.add_all([cli, eq]); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie="S1")
    db_session.add(ec); db_session.flush()
    o = Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=4)
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    return o.id


def _img():
    return {"file": ("foto.jpg", b"\xff\xd8\xff_bytes", "image/jpeg")}


def test_upload_listar_servir_excluir(client, usuario_comum, upload_tmp, db_session):
    h = _headers(client, "comum", "senha123")   # comum = Expedição (autorizado)
    os_id = _abrir_os(db_session)

    r = client.post(f"/ordens/{os_id}/fotos", files=_img(), data={"legenda": "frente"}, headers=h)
    assert r.status_code == 201
    foto = r.json()
    assert foto["os"] == os_id and foto["legenda"] == "frente" and foto["url"].endswith("/arquivo")

    lst = client.get(f"/ordens/{os_id}/fotos", headers=h).json()
    assert len(lst) == 1 and lst[0]["id"] == foto["id"]

    arq = client.get(foto["url"], headers=h)
    assert arq.status_code == 200 and arq.content == b"\xff\xd8\xff_bytes"

    assert client.delete(f"/fotos/{foto['id']}", headers=h).status_code == 204
    assert client.get(f"/ordens/{os_id}/fotos", headers=h).json() == []


def test_upload_tipo_invalido(client, usuario_comum, upload_tmp, db_session):
    h = _headers(client, "comum", "senha123")
    os_id = _abrir_os(db_session)
    r = client.post(f"/ordens/{os_id}/fotos", files={"file": ("a.txt", b"x", "text/plain")}, headers=h)
    assert r.status_code == 415


def test_upload_404_os(client, usuario_comum, upload_tmp, db_session):
    h = _headers(client, "comum", "senha123")
    assert client.post("/ordens/999999/fotos", files=_img(), headers=h).status_code == 404


def test_upload_403_nao_autorizado(client, usuario_lab, upload_tmp, db_session):
    h = _headers(client, "lab", "senha123")  # Laboratório não pode subir foto de recebimento
    os_id = _abrir_os(db_session)
    assert client.post(f"/ordens/{os_id}/fotos", files=_img(), headers=h).status_code == 403
```

- [ ] **Step 4: Rodar e ver falhar** `cd backend; python -m pytest tests/test_fotos.py -v` → 404/erro (rotas não existem).

- [ ] **Step 5: Implementar o router** (`backend/app/api/fotos.py`)

```python
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Ordem, Foto
from app.api.deps import get_current_usuario, require_funcao
from app.core import storage
from app.schemas.fotos import FotoOut

router = APIRouter(tags=["fotos"])
GESTOR_FOTOS = ("Expedição", "Administrador")


def _os_ou_404(db: Session, ordem_id: int) -> Ordem:
    o = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if o is None:
        raise HTTPException(404, "OS não encontrada")
    return o


def _to_out(f: Foto) -> FotoOut:
    return FotoOut(id=f.id, os=f.os, arquivo=f.arquivo, legenda=f.legenda,
                   url=f"/ordens/{f.os}/fotos/{f.id}/arquivo")


@router.post("/ordens/{ordem_id}/fotos", response_model=FotoOut, status_code=201)
def enviar_foto(
    ordem_id: int,
    file: UploadFile = File(...),
    legenda: str | None = Form(None),
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_funcao(*GESTOR_FOTOS)),
):
    o = _os_ou_404(db, ordem_id)
    try:
        basename = storage.salvar_upload(file, subdir=f"os/{ordem_id}", tipos_permitidos=storage.TIPOS_IMAGEM)
    except storage.ArquivoInvalido as e:
        raise HTTPException(e.status, e.detail)
    foto = Foto(os=ordem_id, cliente=o.cliente, arquivo=basename, legenda=legenda, tipo="I")
    db.add(foto); db.commit(); db.refresh(foto)
    return _to_out(foto)


@router.get("/ordens/{ordem_id}/fotos", response_model=list[FotoOut])
def listar_fotos(ordem_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    fotos = db.query(Foto).filter(Foto.os == ordem_id).order_by(Foto.id).all()
    return [_to_out(f) for f in fotos]


@router.get("/ordens/{ordem_id}/fotos/{foto_id}/arquivo")
def baixar_foto(ordem_id: int, foto_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    foto = db.query(Foto).filter(Foto.id == foto_id, Foto.os == ordem_id).first()
    if foto is None:
        raise HTTPException(404, "foto não encontrada")
    caminho = storage.caminho_arquivo(f"os/{ordem_id}", foto.arquivo)
    if not caminho.exists():
        raise HTTPException(404, "arquivo não encontrado")
    return FileResponse(caminho)


@router.delete("/fotos/{foto_id}", status_code=204)
def excluir_foto(foto_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(*GESTOR_FOTOS))):
    foto = db.query(Foto).filter(Foto.id == foto_id).first()
    if foto is None:
        raise HTTPException(404, "foto não encontrada")
    storage.remover_arquivo(f"os/{foto.os}", foto.arquivo)
    db.delete(foto); db.commit()
```

- [ ] **Step 6: Registrar o router** em `backend/app/main.py` (import `fotos` na linha dos routers + `app.include_router(fotos.router)`).

- [ ] **Step 7: Rodar e ver passar** `cd backend; python -m pytest tests/test_fotos.py -v` → 4 PASS. Depois `python -m pytest -q` (sem regressões).

- [ ] **Step 8: Commit**
```bash
git add backend/app/models/foto.py backend/app/models/__init__.py backend/app/schemas/fotos.py backend/app/api/fotos.py backend/app/main.py backend/tests/test_fotos.py
git commit -m "feat(backend): fotos da OS (upload/listar/servir/excluir)"
```

---

## Task 3: Fotos da OS — frontend

**Files:**
- Modify: `frontend/src/app/ordens/api.ts`
- Create: `frontend/src/app/ordens/FotoImg.tsx`
- Modify: `frontend/src/app/ordens/OrdemDetailPage.tsx`

- [ ] **Step 1: Estender `ordens/api.ts`** — acrescentar (no topo, trocar o import para incluir `apiFetch`/`ApiError`; e adicionar os tipos/funções):

```ts
import { apiJson, apiFetch, ApiError } from '../../lib/api'
```
```ts
export interface Foto {
  id: number
  os: number
  arquivo: string
  legenda: string | null
  url: string
}

// Busca um arquivo protegido (precisa de Bearer) e devolve um object URL.
export async function buscarBlobUrl(path: string): Promise<string> {
  const res = await apiFetch(path)
  if (!res.ok) throw new ApiError(res.status, 'Falha ao carregar arquivo')
  const blob = await res.blob()
  return URL.createObjectURL(blob)
}

export const fotosApi = {
  listar: (ordemId: number): Promise<Foto[]> => apiJson<Foto[]>(`/ordens/${ordemId}/fotos`),
  enviar: async (ordemId: number, file: File, legenda?: string): Promise<Foto> => {
    const fd = new FormData()
    fd.append('file', file)
    if (legenda) fd.append('legenda', legenda)
    const res = await apiFetch(`/ordens/${ordemId}/fotos`, { method: 'POST', body: fd })
    if (!res.ok) {
      let detail = res.statusText
      try { const b = await res.json(); if (b.detail) detail = b.detail } catch { /* sem corpo */ }
      throw new ApiError(res.status, detail)
    }
    return (await res.json()) as Foto
  },
  excluir: async (fotoId: number): Promise<void> => {
    const res = await apiFetch(`/fotos/${fotoId}`, { method: 'DELETE' })
    if (!res.ok) throw new ApiError(res.status, 'Falha ao excluir')
  },
}
```
> Nota: ao enviar `FormData`, **não** setar `Content-Type` (o browser define o boundary). `apiFetch` só adiciona o header `Authorization`, então está ok.

- [ ] **Step 2: Componente `FotoImg`** (`frontend/src/app/ordens/FotoImg.tsx`) — imagem autenticada via blob:

```tsx
import { useEffect, useState } from 'react'
import { buscarBlobUrl } from './api'

export function FotoImg({ url, alt, className }: { url: string; alt: string; className?: string }) {
  const [src, setSrc] = useState<string | null>(null)
  useEffect(() => {
    let ativo = true
    let objectUrl: string | null = null
    buscarBlobUrl(url)
      .then((u) => { if (ativo) { objectUrl = u; setSrc(u) } else { URL.revokeObjectURL(u) } })
      .catch(() => { /* ignora; mostra placeholder */ })
    return () => { ativo = false; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [url])
  if (!src) return <div className={className + ' bg-background-elevated animate-pulse'} />
  return <img src={src} alt={alt} className={className} />
}
```

- [ ] **Step 3: Seção "Fotos" no `OrdemDetailPage`**

Ler o arquivo atual para achar onde encaixar (após o bloco de Recebimento). Adicionar:
- imports: `import { fotosApi, type Foto } from './api'`, `import { FotoImg } from './FotoImg'`, e garantir `useState`/`useEffect` já importados; usar o helper de papel já presente (`podeAbrirOS`/Expedição-Admin — o arquivo já calcula permissões).
- estado: `const [fotos, setFotos] = useState<Foto[]>([])`, `const [erroFoto, setErroFoto] = useState('')`.
- carregar as fotos no mesmo efeito que carrega a OS (ou um efeito próprio por `id`): `fotosApi.listar(Number(id)).then(setFotos).catch(() => {})`.
- handlers:
  - `onEnviarFoto(e)` lê `e.target.files[0]`, chama `fotosApi.enviar(Number(id), file)`, recarrega a lista, limpa o input; em erro, `setErroFoto`.
  - `onExcluirFoto(fotoId)` com `window.confirm`, chama `fotosApi.excluir`, recarrega.
- UI: um bloco com título "Fotos", grid de `FotoImg` (miniaturas `w-full h-28 object-cover rounded-lg`), legenda embaixo, botão de excluir por foto **só se** o usuário pode (Expedição/Admin); um `<input type="file" accept="image/*">` (gated) para enviar. Mostrar `erroFoto` se houver. Seguir as classes/estilo das outras seções da página.

Mantenha o restante do arquivo intacto. Se a estrutura de permissão da página usar uma variável diferente (ex.: `podeAgir`), use a verificação de admin/Expedição já disponível ali; em último caso, importe `podeAbrirOS` de `../../auth/roles` e use `podeAbrirOS(user)`.

- [ ] **Step 4: Verificar** `cd frontend; npx tsc -b --noEmit; npm run lint` → limpos.

- [ ] **Step 5: Commit**
```bash
git add frontend/src/app/ordens/api.ts frontend/src/app/ordens/FotoImg.tsx frontend/src/app/ordens/OrdemDetailPage.tsx
git commit -m "feat(frontend): seção de fotos no detalhe da OS (upload/visualizar/excluir)"
```

---

## Task 4: PDF de certificado — backend (TDD)

**Files:**
- Create: `backend/app/api/certificados.py`; Modify: `backend/app/main.py`
- Modify: `backend/app/api/portal.py`, `backend/app/schemas/portal.py`
- Test: `backend/tests/test_certificados.py`

- [ ] **Step 1: Escrever os testes** (`backend/tests/test_certificados.py`)

```python
def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _os_do_cliente(db_session, cliente_id):
    from app.models import Equipamento, EquipamentoCliente, Ordem
    eq = Equipamento(descricao="Bafômetro"); db_session.add(eq); db_session.flush()
    ec = EquipamentoCliente(cliente=cliente_id, equipamento=eq.id, serie="S1"); db_session.add(ec); db_session.flush()
    o = Ordem(cliente=cliente_id, equipamento_cliente=ec.id, fase=5)
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    return o.id


def _pdf():
    return {"file": ("cert.pdf", b"%PDF-1.4 fake", "application/pdf")}


def test_upload_e_download_interno(client, usuario_lab, upload_tmp, db_session):
    from app.models import Cliente
    cli = Cliente(nome="Cli"); db_session.add(cli); db_session.commit()
    os_id = _os_do_cliente(db_session, cli.id)
    h = _headers(client, "lab", "senha123")   # Laboratório autorizado
    r = client.post(f"/ordens/{os_id}/certificado", files=_pdf(), headers=h)
    assert r.status_code == 200
    arq = client.get(f"/ordens/{os_id}/certificado", headers=h)
    assert arq.status_code == 200 and arq.content == b"%PDF-1.4 fake"


def test_upload_tipo_invalido(client, usuario_lab, upload_tmp, db_session):
    from app.models import Cliente
    cli = Cliente(nome="Cli"); db_session.add(cli); db_session.commit()
    os_id = _os_do_cliente(db_session, cli.id)
    h = _headers(client, "lab", "senha123")
    r = client.post(f"/ordens/{os_id}/certificado", files={"file": ("a.txt", b"x", "text/plain")}, headers=h)
    assert r.status_code == 415


def test_upload_403(client, usuario_comum, upload_tmp, db_session):
    from app.models import Cliente
    cli = Cliente(nome="Cli"); db_session.add(cli); db_session.commit()
    os_id = _os_do_cliente(db_session, cli.id)
    h = _headers(client, "comum", "senha123")  # Expedição não calibra
    assert client.post(f"/ordens/{os_id}/certificado", files=_pdf(), headers=h).status_code == 403


def test_download_url_legada_redireciona(client, usuario_lab, upload_tmp, db_session):
    from app.models import Cliente, Ordem
    cli = Cliente(nome="Cli"); db_session.add(cli); db_session.commit()
    os_id = _os_do_cliente(db_session, cli.id)
    o = db_session.query(Ordem).get(os_id); o.pdf_certificado = "http://exemplo/cert.pdf"; db_session.commit()
    r = client.get(f"/ordens/{os_id}/certificado", headers=_headers(client, "lab", "senha123"), follow_redirects=False)
    assert r.status_code in (302, 307)


def _portal_headers(client, db_session, cliente_id):
    from app.models import UsuarioCliente, Cliente
    from app.core.security import hash_senha
    empresa = db_session.query(Cliente).get(cliente_id)
    empresa.cgc = "11222333000144"
    uc = UsuarioCliente(cliente=cliente_id, nome="P", login="p1", senha=hash_senha("portal123"), precisa_redefinir_senha=False)
    db_session.add(uc); db_session.commit()
    tok = client.post("/auth/login-portal", json={"documento": "11222333000144", "login": "p1", "senha": "portal123"}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def test_portal_baixa_so_do_proprio_cliente(client, usuario_lab, upload_tmp, db_session):
    from app.models import Cliente
    dono = Cliente(nome="Dono"); outro = Cliente(nome="Outro"); db_session.add_all([dono, outro]); db_session.commit()
    os_id = _os_do_cliente(db_session, dono.id)
    client.post(f"/ordens/{os_id}/certificado", files=_pdf(), headers=_headers(client, "lab", "senha123"))
    h = _portal_headers(client, db_session, dono.id)
    assert client.get(f"/portal/certificados/{os_id}", headers=h).status_code == 200
    # OS de outro cliente → 404
    os_outro = _os_do_cliente(db_session, outro.id)
    assert client.get(f"/portal/certificados/{os_outro}", headers=h).status_code == 404
```

- [ ] **Step 2: Rodar e ver falhar** `cd backend; python -m pytest tests/test_certificados.py -v`.

- [ ] **Step 3: Router interno** (`backend/app/api/certificados.py`)

```python
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Ordem
from app.api.deps import get_current_usuario, require_funcao
from app.core import storage

router = APIRouter(tags=["certificados"])
GESTOR_CERT = ("Laboratório", "Administrador")


def _os_ou_404(db: Session, ordem_id: int) -> Ordem:
    o = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if o is None:
        raise HTTPException(404, "OS não encontrada")
    return o


def servir_certificado(ordem: Ordem) -> FileResponse | RedirectResponse:
    pdf = ordem.pdf_certificado
    if not pdf:
        raise HTTPException(404, "sem certificado")
    if pdf.startswith("http"):
        return RedirectResponse(pdf)
    caminho = storage.caminho_arquivo(f"certificados/{ordem.id}", pdf)
    if not caminho.exists():
        raise HTTPException(404, "arquivo não encontrado")
    return FileResponse(caminho, media_type="application/pdf")


@router.post("/ordens/{ordem_id}/certificado")
def enviar_certificado(
    ordem_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_funcao(*GESTOR_CERT)),
):
    o = _os_ou_404(db, ordem_id)
    anterior = o.pdf_certificado
    try:
        basename = storage.salvar_upload(file, subdir=f"certificados/{ordem_id}", tipos_permitidos=storage.TIPOS_PDF)
    except storage.ArquivoInvalido as e:
        raise HTTPException(e.status, e.detail)
    if anterior and not anterior.startswith("http"):
        storage.remover_arquivo(f"certificados/{ordem_id}", anterior)
    o.pdf_certificado = basename
    db.commit()
    return {"pdf_certificado": basename}


@router.get("/ordens/{ordem_id}/certificado")
def baixar_certificado(ordem_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    return servir_certificado(_os_ou_404(db, ordem_id))
```

- [ ] **Step 4: Registrar o router** em `main.py` (import `certificados` + `app.include_router(certificados.router)`).

- [ ] **Step 5: Endpoint do portal (tenant-scoped)** — em `backend/app/api/portal.py`, importar o helper e adicionar:

```python
from app.api.certificados import servir_certificado
```
```python
@router.get("/certificados/{ordem_id}")
def baixar_certificado_portal(ordem_id: int, cli: UsuarioCliente = Depends(get_current_cliente), db: Session = Depends(get_db)):
    o = db.query(Ordem).filter(Ordem.id == ordem_id, Ordem.cliente == cli.cliente).first()
    if o is None:
        raise HTTPException(status_code=404, detail="certificado não encontrado")
    return servir_certificado(o)
```
(Confirme que `Ordem`, `HTTPException` e `get_current_cliente` já estão importados em `portal.py` — estão.)

- [ ] **Step 6: Expor o `os` no item de certificado do portal** — em `backend/app/schemas/portal.py`, acrescentar a `PortalCertItem`:
```python
    os: int | None = None
```
E em `backend/app/api/portal.py`, no endpoint `certificados`, ao montar cada `PortalCertItem`, preencher `os=ec.os_atual` (o id da OS de onde veio o PDF; já é a base do outerjoin). Ler o trecho atual e adicionar o campo.

- [ ] **Step 7: Rodar e ver passar** `cd backend; python -m pytest tests/test_certificados.py -v` → todos PASS. Depois `python -m pytest -q` (sem regressões).

- [ ] **Step 8: Commit**
```bash
git add backend/app/api/certificados.py backend/app/main.py backend/app/api/portal.py backend/app/schemas/portal.py backend/tests/test_certificados.py
git commit -m "feat(backend): upload/download de PDF de certificado (interno + portal tenant-scoped)"
```

---

## Task 5: PDF de certificado — frontend

**Files:**
- Modify: `frontend/src/app/ordens/api.ts`, `frontend/src/app/ordens/OrdemDetailPage.tsx`
- Modify: `frontend/src/portal/api.ts`, `frontend/src/portal/PortalCertificadosPage.tsx`

- [ ] **Step 1: `certificadoApi` em `ordens/api.ts`** — acrescentar (reusa `apiFetch`/`ApiError`/`buscarBlobUrl` da Task 3):

```ts
export const certificadoApi = {
  enviar: async (ordemId: number, file: File): Promise<{ pdf_certificado: string }> => {
    const fd = new FormData()
    fd.append('file', file)
    const res = await apiFetch(`/ordens/${ordemId}/certificado`, { method: 'POST', body: fd })
    if (!res.ok) {
      let detail = res.statusText
      try { const b = await res.json(); if (b.detail) detail = b.detail } catch { /* sem corpo */ }
      throw new ApiError(res.status, detail)
    }
    return (await res.json()) as { pdf_certificado: string }
  },
  // Abre o PDF (interno) numa nova aba; baixa via blob por causa do Bearer.
  baixar: async (ordemId: number): Promise<void> => {
    const url = await buscarBlobUrl(`/ordens/${ordemId}/certificado`)
    window.open(url, '_blank', 'noopener')
  },
}
```

- [ ] **Step 2: No `OrdemDetailPage`** — no bloco de resultados de calibração: se `ordem.pdf_certificado`, mostrar botão "Baixar certificado" (chama `certificadoApi.baixar(Number(id))`); e, gated para Laboratório/Admin, um `<input type="file" accept="application/pdf">` "Enviar certificado" que chama `certificadoApi.enviar`, recarrega a OS e mostra erro inline. Seguir o estilo das demais ações. (Permissão de Lab: usar a verificação de função já presente na página — `user.funcao === 'Laboratório' || isAdmin(user)`; importar `isAdmin` de `../../auth/roles` se necessário.)

- [ ] **Step 3: `portal/api.ts`** — acrescentar `os: number | null` em `PortalCertItem` e o método:
```ts
  baixarCertificado: async (ordemId: number): Promise<void> => {
    const res = await apiFetch(`/portal/certificados/${ordemId}`)
    if (!res.ok) throw new ApiError(res.status, 'Certificado indisponível')
    const url = URL.createObjectURL(await res.blob())
    window.open(url, '_blank', 'noopener')
  },
```
(trocar o import para incluir `apiFetch, ApiError` de `../lib/api`.)

- [ ] **Step 4: `PortalCertificadosPage`** — na coluna "PDF", em vez de só linkar quando `http`, mostrar um botão "Baixar" quando houver PDF disponível:
  - se `c.os != null`, botão "Baixar" → `portalApi.baixarCertificado(c.os)` (envolver em try/catch com `setErro`).
  - manter o caso de `c.pdf` começar com `http` como link direto (alternativa). Decisão simples: se `c.os != null && c.pdf` → botão "Baixar"; senão `—`.

- [ ] **Step 5: Verificar** `cd frontend; npx tsc -b --noEmit; npm run lint` → limpos.

- [ ] **Step 6: Commit**
```bash
git add frontend/src/app/ordens/api.ts frontend/src/app/ordens/OrdemDetailPage.tsx frontend/src/portal/api.ts frontend/src/portal/PortalCertificadosPage.tsx
git commit -m "feat(frontend): enviar/baixar PDF de certificado (detalhe da OS + portal)"
```

---

## Task 6: Testes de api do frontend + infra + verificação final

**Files:**
- Create: `frontend/src/app/ordens/anexos.api.test.ts`
- Modify: `backend/.env.example`, `docker-compose.yml`

- [ ] **Step 1: Teste Vitest** (`frontend/src/app/ordens/anexos.api.test.ts`) — cobre paths/método de `fotosApi` e `certificadoApi` (mesmo padrão de `solicitacoes/api.test.ts`):

```ts
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { fotosApi, certificadoApi } from './api'
import { setTokens } from '../../lib/auth-storage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('app/ordens anexos api', () => {
  beforeEach(() => { localStorage.clear(); vi.restoreAllMocks(); setTokens({ access_token: 't', refresh_token: 'r' }) })

  it('fotosApi.listar faz GET /ordens/:id/fotos', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse([]))
    vi.stubGlobal('fetch', f)
    await fotosApi.listar(7)
    expect(String(f.mock.calls[0][0])).toContain('/ordens/7/fotos')
  })

  it('fotosApi.enviar faz POST multipart sem Content-Type manual', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ id: 1, os: 7, arquivo: 'a.jpg', legenda: null, url: '/x' }, 201))
    vi.stubGlobal('fetch', f)
    await fotosApi.enviar(7, new File([new Uint8Array([1])], 'a.jpg', { type: 'image/jpeg' }), 'frente')
    const init = f.mock.calls[0][1]
    expect(init.method).toBe('POST')
    expect(init.body).toBeInstanceOf(FormData)
    // o header Content-Type não é setado manualmente (deixa o browser definir o boundary)
    const headers = new Headers(init.headers)
    expect(headers.get('Content-Type')).toBeNull()
  })

  it('certificadoApi.enviar faz POST /ordens/:id/certificado', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ pdf_certificado: 'x.pdf' }))
    vi.stubGlobal('fetch', f)
    await certificadoApi.enviar(7, new File([new Uint8Array([1])], 'c.pdf', { type: 'application/pdf' }))
    expect(String(f.mock.calls[0][0])).toContain('/ordens/7/certificado')
    expect(f.mock.calls[0][1].method).toBe('POST')
  })
})
```
Rodar: `cd frontend; npx vitest run src/app/ordens/anexos.api.test.ts` → PASS.
> Se o teste do Content-Type falhar porque `apiFetch` injeta algo, ajuste a expectativa para refletir o comportamento real do `apiFetch` (ele só adiciona `Authorization`). Não force `Content-Type` no `fotosApi.enviar`.

- [ ] **Step 2: `.env.example` + compose**

Em `backend/.env.example`, acrescentar:
```
# Pasta de uploads (fotos/PDFs). Em produção, monte um volume e aponte para ele (ex.: /data/uploads).
UPLOAD_DIR=uploads
```
Em `docker-compose.yml`, no serviço `backend`, adicionar um volume nomeado para persistir uploads em dev e a env:
```yaml
    environment:
      - UPLOAD_DIR=/data/uploads
    volumes:
      - ./backend:/app
      - gestorhs-uploads:/data/uploads
```
E no fim do arquivo:
```yaml
volumes:
  gestorhs-uploads:
```
(Manter o volume `./backend:/app` existente; só acrescentar o de uploads e a env. Ajustar a indentação ao formato atual do compose.)

- [ ] **Step 3: Verificação final**
- `cd backend; python -m pytest -q` → tudo verde.
- `cd frontend; npx vitest run; npx tsc -b --noEmit; npm run lint; npm run build` → tudo verde.

- [ ] **Step 4: Commit**
```bash
git add frontend/src/app/ordens/anexos.api.test.ts backend/.env.example docker-compose.yml
git commit -m "test(frontend): api de anexos; chore: UPLOAD_DIR no env.example e volume no compose"
```

---

## Notas de E2E (após execução, fora dos subagentes)
- Numa OS de teste: enviar 1–2 fotos (como Expedição/Admin), ver no detalhe, excluir uma.
- Enviar PDF de certificado (como Laboratório/Admin), baixar pelo interno.
- Logar no portal do cliente dono → baixar o mesmo certificado; confirmar 404 para OS de outro cliente.
- Limpar OS/fotos/PDF de teste e os arquivos em `UPLOAD_DIR` ao fim. Matar dev-servers órfãos 5173/5174/5175.

## Self-review (autor do plano)
- **Cobertura da spec:** §4 storage → Task 1; §5 fotos (modelo/schema/endpoints/UI/testes) → Tasks 2–3; §6 PDF (interno+portal+UI+testes) → Tasks 4–5; §2 deps/infra (python-multipart, UPLOAD_DIR, compose) → Tasks 1 e 6; §7 verificação/E2E → Task 6 + notas. ✓
- **Sem migração:** confirmado — usa `fotos.os` e `fotos.arquivo` existentes; `pdf_certificado` guarda basename ≤20 chars (cabe em VARCHAR(50)).
- **Placeholders:** nenhum — todo passo traz código/comando.
- **Consistência de tipos/rotas:** `FotoOut{id,os,arquivo,legenda,url}` igual no back e no `Foto` do front; rotas `/ordens/{id}/fotos`, `/fotos/{id}`, `/ordens/{id}/certificado`, `/portal/certificados/{id}` batendo entre back/test/front; `servir_certificado` reusado pelo interno e pelo portal; `PortalCertItem.os` adicionado nos dois lados; uploads via `apiFetch`+`FormData` sem `Content-Type` manual (coerente com `lib/api.ts`).
