# Nota fiscal obrigatória no Financeiro — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** O Financeiro só avança a OS para Preparando Retorno depois de anexar a nota fiscal de serviço (PDF ou XML) e informar o número da NF; o anexo fica baixável no GestorHS e no cartão do TaskHS.

**Architecture:** Espelha o padrão já existente do certificado: coluna de anexo em `ordens`, upload via `storage.salvar_upload`, e um gate `409` no `avancar` (igual ao "gere o certificado antes de concluir o laboratório"). O link público reusa o HMAC do certificado — extraído para um módulo compartilhado **sem alterar o formato da mensagem do certificado**, para não invalidar os links já publicados nos cartões.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, pytest (SQLite in-memory, Docker); React 19 + TS + Vite + Vitest.

## Global Constraints

- Backend em Docker: testes com `docker compose exec -T backend pytest ... -q`. Frontend: `cd frontend && npx tsc -b --noEmit && npm run lint && npm test && npm run build`.
- **NÃO rodar alembic nos testes** (SQLite constrói pelos modelos). A migração `0013_nota_fiscal` (`down_revision = "0012_usuario_email_credencial"`) é aplicada em produção à parte. Ela é **retrocompatível** (só adiciona colunas nullable).
- Um arquivo por OS: **PDF ou XML**. Tipo fora disso → **415**. Limite de 10 MB (já vem do storage).
- **Número da NF obrigatório** no upload: ausente → **422**; em branco após `strip()` → **422**.
- Permissão de upload: `require_funcao("Financeiro", "Administrador")`.
- Gate do avanço (origem **10** → 7): sem `ordem.nota_fiscal` → **409** `"anexe a nota fiscal antes de confirmar o pagamento"`.
- ⚠️ **RESTRIÇÃO CRÍTICA:** a mensagem HMAC do certificado é `f"cert:{ordem_id}:{tipo_codigo}"` e **NÃO PODE MUDAR** — links de certificado já publicados nos cartões do TaskHS quebrariam (403). Há um teste de regressão travando o token exato.
- **Nunca** comparar fase com `>=`/`<=` (o id 10 do Financeiro é maior que 7/8). Backend: `os_workflow.posicao()`. Frontend: `posicaoFase()`.
- Commits: Conventional Commits PT-BR **sem acentos**, uma linha, sem trailer de co-autor.

---

### Task 1: Anexo da nota fiscal — modelo, migração, storage (XML) e endpoints

**Files:**
- Modify: `backend/app/models/ordem.py`
- Create: `backend/alembic/versions/0013_nota_fiscal.py`
- Modify: `backend/app/core/storage.py`
- Create: `backend/app/api/notas_fiscais.py`
- Modify: `backend/app/main.py` (registrar o router)
- Modify: `backend/app/schemas/ordens.py` (`OrdemOut`)
- Test: `backend/tests/test_nota_fiscal.py`

**Interfaces:**
- Produces: `Ordem.nota_fiscal: str | None`, `Ordem.nota_fiscal_numero: str | None`; `storage.TIPOS_NOTA_FISCAL`; `POST/GET /ordens/{id}/nota-fiscal`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_nota_fiscal.py`:

```python
import io


def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _os(db_session, os_base, fase=10):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"],
              fase=fase, tipo_servico="C", situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    return o


def _pdf():
    return ("nf.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")


def _xml():
    return ("nf.xml", io.BytesIO(b"<nfse/>"), "application/xml")


def test_upload_pdf_ok(client, usuario_financeiro, fases_seed, os_base, db_session, upload_tmp):
    o = _os(db_session, os_base)
    h = _headers(client, "fin@hs.com", "senha123")
    r = client.post(f"/ordens/{o.id}/nota-fiscal", files={"file": _pdf()}, data={"numero": "12345"}, headers=h)
    assert r.status_code == 200
    db_session.refresh(o)
    assert o.nota_fiscal.endswith(".pdf")
    assert o.nota_fiscal_numero == "12345"


def test_upload_xml_ok(client, usuario_financeiro, fases_seed, os_base, db_session, upload_tmp):
    o = _os(db_session, os_base)
    h = _headers(client, "fin@hs.com", "senha123")
    r = client.post(f"/ordens/{o.id}/nota-fiscal", files={"file": _xml()}, data={"numero": "77"}, headers=h)
    assert r.status_code == 200
    db_session.refresh(o)
    assert o.nota_fiscal.endswith(".xml")


def test_upload_tipo_invalido_415(client, usuario_financeiro, fases_seed, os_base, db_session, upload_tmp):
    o = _os(db_session, os_base)
    h = _headers(client, "fin@hs.com", "senha123")
    imagem = ("nf.png", io.BytesIO(b"\x89PNG"), "image/png")
    r = client.post(f"/ordens/{o.id}/nota-fiscal", files={"file": imagem}, data={"numero": "1"}, headers=h)
    assert r.status_code == 415


def test_upload_sem_numero_422(client, usuario_financeiro, fases_seed, os_base, db_session, upload_tmp):
    o = _os(db_session, os_base)
    h = _headers(client, "fin@hs.com", "senha123")
    r = client.post(f"/ordens/{o.id}/nota-fiscal", files={"file": _pdf()}, headers=h)
    assert r.status_code == 422


def test_upload_numero_em_branco_422(client, usuario_financeiro, fases_seed, os_base, db_session, upload_tmp):
    o = _os(db_session, os_base)
    h = _headers(client, "fin@hs.com", "senha123")
    r = client.post(f"/ordens/{o.id}/nota-fiscal", files={"file": _pdf()}, data={"numero": "   "}, headers=h)
    assert r.status_code == 422


def test_substituir_remove_o_arquivo_anterior(client, usuario_financeiro, fases_seed, os_base, db_session, upload_tmp):
    o = _os(db_session, os_base)
    h = _headers(client, "fin@hs.com", "senha123")
    client.post(f"/ordens/{o.id}/nota-fiscal", files={"file": _pdf()}, data={"numero": "1"}, headers=h)
    db_session.refresh(o)
    antigo = upload_tmp / f"notas-fiscais/{o.id}" / o.nota_fiscal
    assert antigo.exists()
    client.post(f"/ordens/{o.id}/nota-fiscal", files={"file": _xml()}, data={"numero": "2"}, headers=h)
    db_session.refresh(o)
    assert not antigo.exists()          # o anterior foi apagado do disco
    assert o.nota_fiscal_numero == "2"


def test_upload_exige_funcao_financeiro_403(client, usuario_lab, fases_seed, os_base, db_session, upload_tmp):
    o = _os(db_session, os_base)
    h = _headers(client, "lab@hs.com", "senha123")
    r = client.post(f"/ordens/{o.id}/nota-fiscal", files={"file": _pdf()}, data={"numero": "1"}, headers=h)
    assert r.status_code == 403


def test_download_ok_e_sem_anexo_404(client, usuario_financeiro, usuario_admin, fases_seed, os_base, db_session, upload_tmp):
    o = _os(db_session, os_base)
    ha = _headers(client, "admin@hs.com", "senha123")
    assert client.get(f"/ordens/{o.id}/nota-fiscal", headers=ha).status_code == 404
    hf = _headers(client, "fin@hs.com", "senha123")
    client.post(f"/ordens/{o.id}/nota-fiscal", files={"file": _pdf()}, data={"numero": "1"}, headers=hf)
    r = client.get(f"/ordens/{o.id}/nota-fiscal", headers=ha)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
```

- [ ] **Step 2: Run to verify failure**

Run: `docker compose exec -T backend pytest tests/test_nota_fiscal.py -q`
Expected: FAIL (rota `/ordens/{id}/nota-fiscal` não existe → 404/405).

- [ ] **Step 3: Add the model columns**

In `backend/app/models/ordem.py`, after `pdf_certificado`:

```python
    nota_fiscal = Column(String(50), nullable=True)          # basename do arquivo em disco
    nota_fiscal_numero = Column(String(50), nullable=True)   # numero da NF
```

- [ ] **Step 4: Create the migration**

Create `backend/alembic/versions/0013_nota_fiscal.py`:

```python
"""ordens: anexo e numero da nota fiscal de servico

Revision ID: 0013_nota_fiscal
Revises: 0012_usuario_email_credencial
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_nota_fiscal"
down_revision = "0012_usuario_email_credencial"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ordens", sa.Column("nota_fiscal", sa.String(50), nullable=True))
    op.add_column("ordens", sa.Column("nota_fiscal_numero", sa.String(50), nullable=True))


def downgrade():
    op.drop_column("ordens", "nota_fiscal_numero")
    op.drop_column("ordens", "nota_fiscal")
```

- [ ] **Step 5: Allow XML in the storage**

In `backend/app/core/storage.py`, after `TIPOS_PDF`:

```python
TIPOS_XML = {"application/xml", "text/xml"}
TIPOS_NOTA_FISCAL = TIPOS_PDF | TIPOS_XML
```
and add to the `_EXT` map:
```python
    "application/xml": ".xml",
    "text/xml": ".xml",
```

- [ ] **Step 6: Create the router**

Create `backend/app/api/notas_fiscais.py`:

```python
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Ordem
from app.api.deps import get_current_usuario, require_funcao
from app.core import storage

router = APIRouter(tags=["notas-fiscais"])
GESTOR_NF = ("Financeiro", "Administrador")


def _os_ou_404(db: Session, ordem_id: int) -> Ordem:
    o = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if o is None:
        raise HTTPException(404, "OS não encontrada")
    return o


def _subdir(ordem_id: int) -> str:
    return f"notas-fiscais/{ordem_id}"


def _media_type(basename: str) -> str:
    return "application/xml" if basename.lower().endswith(".xml") else "application/pdf"


@router.post("/ordens/{ordem_id}/nota-fiscal")
def enviar_nota_fiscal(
    ordem_id: int,
    file: UploadFile = File(...),
    numero: str = Form(...),
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_funcao(*GESTOR_NF)),
):
    o = _os_ou_404(db, ordem_id)
    num = (numero or "").strip()
    if not num:
        raise HTTPException(422, "número da nota fiscal é obrigatório")
    anterior = o.nota_fiscal
    try:
        basename = storage.salvar_upload(
            file, subdir=_subdir(ordem_id), tipos_permitidos=storage.TIPOS_NOTA_FISCAL
        )
    except storage.ArquivoInvalido as e:
        raise HTTPException(e.status, e.detail)
    if anterior:
        storage.remover_arquivo(_subdir(ordem_id), anterior)
    o.nota_fiscal = basename
    o.nota_fiscal_numero = num
    db.commit()
    return {"nota_fiscal": basename, "nota_fiscal_numero": num}


@router.get("/ordens/{ordem_id}/nota-fiscal")
def baixar_nota_fiscal(ordem_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    o = _os_ou_404(db, ordem_id)
    if not o.nota_fiscal:
        raise HTTPException(404, "sem nota fiscal")
    try:
        caminho = storage.caminho_arquivo(_subdir(ordem_id), o.nota_fiscal)
    except storage.ArquivoInvalido as e:
        raise HTTPException(e.status, e.detail)
    if not caminho.exists():
        raise HTTPException(404, "arquivo não encontrado")
    return FileResponse(caminho, media_type=_media_type(o.nota_fiscal))
```

In `backend/app/main.py`: add `notas_fiscais` to the `from app.api import (...)` line and register it near the other routers:
```python
app.include_router(notas_fiscais.router)
```

- [ ] **Step 7: Expose the fields in `OrdemOut`**

In `backend/app/schemas/ordens.py`, in `OrdemOut`, right after the `pdf_certificado` line:

```python
    nota_fiscal: str | None = None
    nota_fiscal_numero: str | None = None
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `docker compose exec -T backend pytest tests/test_nota_fiscal.py -q`
Expected: PASS (8 passed).

- [ ] **Step 9: Commit**

```bash
git add backend/app/models/ordem.py backend/alembic/versions/0013_nota_fiscal.py backend/app/core/storage.py backend/app/api/notas_fiscais.py backend/app/main.py backend/app/schemas/ordens.py backend/tests/test_nota_fiscal.py
git commit -m "feat(financeiro): anexo da nota fiscal na OS (pdf ou xml) com numero"
```

---

### Task 2: Bloqueio do avanço sem nota fiscal

**Files:**
- Modify: `backend/app/api/ordens.py` (`avancar`, ramo `origem == 10`)
- Modify: `backend/tests/test_ordens_avancar.py`

**Interfaces:**
- Consumes: `Ordem.nota_fiscal` (Task 1).
- Produces: avançar a fase 10 sem NF → **409**.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_ordens_avancar.py`:

```python
def test_financeiro_sem_nota_fiscal_409(client, usuario_financeiro, fases_seed, os_base, db_session):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"], fase=10, situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    hf = _headers(client, "fin@hs.com", "senha123")
    r = client.post(f"/ordens/{o.id}/avancar", json={}, headers=hf)
    assert r.status_code == 409
    assert "nota fiscal" in r.json()["detail"].lower()
    db_session.refresh(o)
    assert o.fase == 10 and o.pago is False   # nada mudou


def test_financeiro_com_nota_fiscal_avanca(client, usuario_financeiro, fases_seed, os_base, db_session):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"], fase=10, situacao="E",
              nota_fiscal="abc123.pdf", nota_fiscal_numero="777")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    hf = _headers(client, "fin@hs.com", "senha123")
    r = client.post(f"/ordens/{o.id}/avancar", json={}, headers=hf)
    assert r.status_code == 200 and r.json()["fase"] == 7
    db_session.refresh(o)
    assert o.pago is True and o.data_pagamento is not None
```

Also update the existing `test_financeiro_marca_pago` and `test_cadeia_feliz_completa`: the OS at fase 10 now needs a nota fiscal to advance. In `test_financeiro_marca_pago`, add `nota_fiscal="nf.pdf", nota_fiscal_numero="1"` to the `Ordem(...)` construction. In `test_cadeia_feliz_completa`, before the 10→7 step, set the NF directly on the OS:

```python
    # o Financeiro so avanca com a nota fiscal anexada
    from app.models import Ordem
    o_db = db_session.get(Ordem, oid)
    o_db.nota_fiscal = "nf.pdf"
    o_db.nota_fiscal_numero = "777"
    db_session.commit()
```

- [ ] **Step 2: Run to verify failure**

Run: `docker compose exec -T backend pytest tests/test_ordens_avancar.py -q`
Expected: FAIL (`test_financeiro_sem_nota_fiscal_409` recebe 200 — o avanço ainda não é bloqueado).

- [ ] **Step 3: Add the gate**

In `backend/app/api/ordens.py`, in `avancar`, the branch:

```python
    elif origem == 10:                    # Financeiro -> Preparando Retorno
        ordem.pago = True
        ordem.data_pagamento = agora()
        texto = "Pagamento confirmado"
```
becomes:
```python
    elif origem == 10:                    # Financeiro -> Preparando Retorno
        if not ordem.nota_fiscal:
            raise HTTPException(status_code=409, detail="anexe a nota fiscal antes de confirmar o pagamento")
        ordem.pago = True
        ordem.data_pagamento = agora()
        texto = "Pagamento confirmado"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T backend pytest tests/test_ordens_avancar.py -q`
Expected: PASS.

- [ ] **Step 5: Run the full suite**

Run: `docker compose exec -T backend pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/ordens.py backend/tests/test_ordens_avancar.py
git commit -m "feat(financeiro): bloqueia avanco sem nota fiscal anexada"
```

---

### Task 3: Assinatura compartilhada + link público da nota fiscal

**Files:**
- Create: `backend/app/core/assinatura.py`
- Modify: `backend/app/core/certificado_link.py` (delegar, **sem mudar a mensagem**)
- Create: `backend/app/core/nota_fiscal_link.py`
- Modify: `backend/app/api/publico.py`
- Test: `backend/tests/test_nota_fiscal_link.py`, `backend/tests/test_certificado_link.py` (regressão), `backend/tests/test_publico_nota_fiscal.py`

**Interfaces:**
- Produces: `assinatura.assinar(mensagem) -> str`, `assinatura.verificar(mensagem, token) -> bool`; `nota_fiscal_link.{assinar, verificar, link_nota_fiscal}`; `GET /publico/nota-fiscal/{ordem_id}?t=<token>`.
- `certificado_link.{assinar, verificar, link_certificado, NOME_PUBLICO}` mantêm assinatura e **produzem os mesmos tokens de antes**.

- [ ] **Step 1: Write the regression test that locks the certificate token**

Append to `backend/tests/test_certificado_link.py`:

```python
def test_token_do_certificado_nao_mudou(monkeypatch):
    """REGRESSAO: links de certificado ja publicados nos cards do TaskHS nao podem quebrar.
    O HMAC e sobre a mensagem exata "cert:{ordem_id}:{tipo}"."""
    import hashlib
    import hmac as _hmac
    from app.core.config import settings
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "segredo-fixo-de-teste")
    esperado = _hmac.new(b"segredo-fixo-de-teste", b"cert:1234:C", hashlib.sha256).hexdigest()
    assert cl.assinar(1234, "C") == esperado
    assert cl.verificar(1234, "C", esperado) is True
```

- [ ] **Step 2: Write the failing tests for the new pieces**

Create `backend/tests/test_nota_fiscal_link.py`:

```python
from app.core import nota_fiscal_link as nl
from app.core.config import settings


def test_assinar_deterministico_e_varia_por_os():
    assert nl.assinar(1234) == nl.assinar(1234)
    assert nl.assinar(1234) != nl.assinar(1235)


def test_verificar_aceita_correto_rejeita_adulterado():
    tok = nl.assinar(1234)
    assert nl.verificar(1234, tok) is True
    assert nl.verificar(1234, tok[:-1] + ("0" if tok[-1] != "0" else "1")) is False
    assert nl.verificar(1235, tok) is False
    assert nl.verificar(1234, "") is False
    assert nl.verificar(1234, None) is False


def test_token_da_nf_difere_do_token_do_certificado():
    """Dominios separados: o token da NF nao pode servir para o certificado."""
    from app.core import certificado_link as cl
    assert nl.assinar(1234) != cl.assinar(1234, "C")


def test_link_none_sem_base(monkeypatch):
    monkeypatch.setattr(settings, "CERT_PUBLIC_BASE_URL", "")
    assert nl.link_nota_fiscal(1234) is None


def test_link_completo_com_base(monkeypatch):
    monkeypatch.setattr(settings, "CERT_PUBLIC_BASE_URL", "http://localhost:8001")
    url = nl.link_nota_fiscal(1234)
    assert url.startswith("http://localhost:8001/publico/nota-fiscal/1234?t=")
    assert url.endswith(nl.assinar(1234))
```

Create `backend/tests/test_publico_nota_fiscal.py`:

```python
import io

from app.core import nota_fiscal_link as nl


def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _os_com_nf(client, db_session, os_base, upload_tmp):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"],
              fase=10, tipo_servico="C", situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    h = _headers(client, "fin@hs.com", "senha123")
    client.post(f"/ordens/{o.id}/nota-fiscal",
                files={"file": ("nf.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
                data={"numero": "999"}, headers=h)
    db_session.refresh(o)
    return o


def test_download_publico_ok(client, usuario_financeiro, fases_seed, os_base, db_session, upload_tmp):
    o = _os_com_nf(client, db_session, os_base, upload_tmp)
    r = client.get(f"/publico/nota-fiscal/{o.id}?t={nl.assinar(o.id)}")   # sem Authorization
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"


def test_download_publico_token_errado_403(client, usuario_financeiro, fases_seed, os_base, db_session, upload_tmp):
    o = _os_com_nf(client, db_session, os_base, upload_tmp)
    assert client.get(f"/publico/nota-fiscal/{o.id}?t=errado").status_code == 403


def test_download_publico_sem_nota_404(client, usuario_admin, fases_seed, os_base, db_session):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"], fase=10, situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    assert client.get(f"/publico/nota-fiscal/{o.id}?t={nl.assinar(o.id)}").status_code == 404
```

- [ ] **Step 3: Run to verify failure**

Run: `docker compose exec -T backend pytest tests/test_nota_fiscal_link.py tests/test_publico_nota_fiscal.py tests/test_certificado_link.py -q`
Expected: FAIL (`ModuleNotFoundError: app.core.nota_fiscal_link`; a rota pública não existe). O teste de regressão do certificado deve **PASSAR** desde já (o formato atual é o que ele trava).

- [ ] **Step 4: Extract the shared HMAC**

Create `backend/app/core/assinatura.py`:

```python
"""Assinatura HMAC para links publicos (puro).

A mensagem assinada e namespaceada por dominio (ex.: "cert:...", "nf:...") para que um
token de um recurso nunca sirva para outro.
"""
import hashlib
import hmac

from app.core.config import settings


def assinar(mensagem: str) -> str:
    return hmac.new(settings.JWT_SECRET_KEY.encode(), mensagem.encode(), hashlib.sha256).hexdigest()


def verificar(mensagem: str, token: str | None) -> bool:
    return hmac.compare_digest(assinar(mensagem), token or "")
```

- [ ] **Step 5: Make `certificado_link` delegate (mensagem INALTERADA)**

Rewrite `backend/app/core/certificado_link.py`:

```python
"""Link publico assinado para download do certificado (sem login no GestorHS)."""
from app.core import assinatura
from app.core.config import settings

NOME_PUBLICO = {"C": "calibracao", "M": "manutencao"}


def _mensagem(ordem_id: int, tipo_codigo: str) -> str:
    # NAO MUDAR este formato: ha links de certificado ja publicados nos cards do TaskHS.
    return f"cert:{ordem_id}:{tipo_codigo}"


def assinar(ordem_id: int, tipo_codigo: str) -> str:
    return assinatura.assinar(_mensagem(ordem_id, tipo_codigo))


def verificar(ordem_id: int, tipo_codigo: str, token: str | None) -> bool:
    return assinatura.verificar(_mensagem(ordem_id, tipo_codigo), token)


def link_certificado(ordem_id: int, tipo_codigo: str) -> str | None:
    base = settings.CERT_PUBLIC_BASE_URL
    if not base:
        return None
    nome = NOME_PUBLICO[tipo_codigo]
    return f"{base.rstrip('/')}/publico/certificado/{ordem_id}/{nome}?t={assinar(ordem_id, tipo_codigo)}"
```

- [ ] **Step 6: Create the nota fiscal link module**

Create `backend/app/core/nota_fiscal_link.py`:

```python
"""Link publico assinado para download da nota fiscal (sem login no GestorHS)."""
from app.core import assinatura
from app.core.config import settings


def _mensagem(ordem_id: int) -> str:
    return f"nf:{ordem_id}"


def assinar(ordem_id: int) -> str:
    return assinatura.assinar(_mensagem(ordem_id))


def verificar(ordem_id: int, token: str | None) -> bool:
    return assinatura.verificar(_mensagem(ordem_id), token)


def link_nota_fiscal(ordem_id: int) -> str | None:
    base = settings.CERT_PUBLIC_BASE_URL
    if not base:
        return None
    return f"{base.rstrip('/')}/publico/nota-fiscal/{ordem_id}?t={assinar(ordem_id)}"
```

- [ ] **Step 7: Add the public endpoint**

In `backend/app/api/publico.py`, extend the imports and add the route:

```python
from fastapi.responses import FileResponse

from app.core import certificado_link, nota_fiscal_link, storage
from app.models import OSCertificado, Ordem
```
(mantenha os imports já existentes de `html_para_pdf`, `get_db`, etc.)

```python
@router.get("/nota-fiscal/{ordem_id}")
def baixar_nota_fiscal_publica(ordem_id: int, t: str = "", db: Session = Depends(get_db)):
    if not nota_fiscal_link.verificar(ordem_id, t):
        raise HTTPException(status_code=403, detail="link inválido")
    o = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if o is None or not o.nota_fiscal:
        raise HTTPException(status_code=404, detail="nota fiscal não encontrada")
    try:
        caminho = storage.caminho_arquivo(f"notas-fiscais/{ordem_id}", o.nota_fiscal)
    except storage.ArquivoInvalido:
        raise HTTPException(status_code=404, detail="nota fiscal não encontrada")
    if not caminho.exists():
        raise HTTPException(status_code=404, detail="arquivo não encontrado")
    media = "application/xml" if o.nota_fiscal.lower().endswith(".xml") else "application/pdf"
    return FileResponse(
        caminho,
        media_type=media,
        headers={"Content-Disposition": f'inline; filename="nota-fiscal-{ordem_id}"'},
    )
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `docker compose exec -T backend pytest tests/test_nota_fiscal_link.py tests/test_publico_nota_fiscal.py tests/test_certificado_link.py tests/test_publico_certificado.py -q`
Expected: PASS — **incluindo** o teste de regressão do token do certificado e os testes do endpoint público de certificado (que não podem ter quebrado).

- [ ] **Step 9: Commit**

```bash
git add backend/app/core/assinatura.py backend/app/core/certificado_link.py backend/app/core/nota_fiscal_link.py backend/app/api/publico.py backend/tests/test_nota_fiscal_link.py backend/tests/test_publico_nota_fiscal.py backend/tests/test_certificado_link.py
git commit -m "feat(financeiro): link publico assinado para download da nota fiscal"
```

---

### Task 4: Nota fiscal no cartão do TaskHS

**Files:**
- Modify: `backend/app/core/taskhs.py` (`_sec_financeiro`, `montar_descricao`)
- Modify: `backend/app/api/ordens.py` (`_agendar_espelhamento`)
- Modify: `backend/tests/test_taskhs_descricao.py`

**Interfaces:**
- Consumes: `nota_fiscal_link.link_nota_fiscal` (Task 3); `Ordem.nota_fiscal*` (Task 1).
- Produces: `montar_descricao(ordem, *, certificados: list[dict], nota_fiscal_url: str | None = None)`.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_taskhs_descricao.py`, add the NF fields to the `_ordem` stub's base dict:

```python
        nota_fiscal=None, nota_fiscal_numero=None,
```

Then append:

```python
def test_secao_financeiro_com_nota_fiscal():
    o = _ordem(fase=10, pago=False, data_pagamento=None, cod_retorno=None, data_retorno=None,
               nota_fiscal="abc.pdf", nota_fiscal_numero="12345")
    d = taskhs.montar_descricao(o, certificados=[], nota_fiscal_url="http://x/nf")
    assert "💰 Financeiro" in d
    assert "Nota fiscal: 12345 — http://x/nf" in d


def test_secao_financeiro_sem_nota_fiscal_omite_a_linha():
    o = _ordem(fase=10, pago=False, data_pagamento=None, cod_retorno=None, data_retorno=None)
    d = taskhs.montar_descricao(o, certificados=[])
    assert "💰 Financeiro" in d
    assert "Nota fiscal" not in d


def test_nota_fiscal_sem_url_mostra_so_o_numero():
    o = _ordem(fase=10, pago=False, data_pagamento=None, cod_retorno=None, data_retorno=None,
               nota_fiscal="abc.pdf", nota_fiscal_numero="12345")
    d = taskhs.montar_descricao(o, certificados=[], nota_fiscal_url=None)
    assert "Nota fiscal: 12345" in d
    assert "—" not in d.split("Nota fiscal: 12345")[1].split("\n")[0]
```

- [ ] **Step 2: Run to verify failure**

Run: `docker compose exec -T backend pytest tests/test_taskhs_descricao.py -q`
Expected: FAIL (`montar_descricao() got an unexpected keyword argument 'nota_fiscal_url'`).

- [ ] **Step 3: Implement in `backend/app/core/taskhs.py`**

Change `_sec_financeiro` to take the url and emit the NF line:

```python
def _sec_financeiro(ordem, nota_fiscal_url: str | None = None) -> str | None:
    if wf.posicao(ordem.fase) < wf.posicao(10):
        return None
    if ordem.pago:
        pagamento = f"Pagamento: confirmado em {_fmt(ordem.data_pagamento)}" if ordem.data_pagamento else "Pagamento: confirmado"
    else:
        pagamento = "Pagamento: pendente"
    nota = None
    if ordem.nota_fiscal_numero:
        nota = f"Nota fiscal: {ordem.nota_fiscal_numero}"
        if nota_fiscal_url:
            nota = f"{nota} — {nota_fiscal_url}"
    return _bloco("💰 Financeiro", [pagamento, nota])
```

And `montar_descricao` gains the parameter and threads it through:

```python
def montar_descricao(ordem, *, certificados: list[dict], nota_fiscal_url: str | None = None) -> str | None:
    cabecalho = "\n".join(_cabecalho(ordem)) or None
    secoes = [
        _sec_recebido(ordem) if wf.posicao(ordem.fase) >= wf.posicao(4) else None,
        _sec_laboratorio(ordem, certificados),
        _sec_posvendas(ordem),
        _sec_financeiro(ordem, nota_fiscal_url),
        _sec_preparando(ordem),
        _sec_finalizada(ordem),
    ]
    blocos = [b for b in [cabecalho, *secoes] if b]
    return "\n\n".join(blocos) if blocos else None
```

- [ ] **Step 4: Wire it in `backend/app/api/ordens.py`**

Add the import `from app.core import nota_fiscal_link` (junto aos outros de `app.core`) and change `_agendar_espelhamento`:

```python
def _agendar_espelhamento(db, background_tasks, ordem, *, lista, arquivado):
    """Monta descricao (com links de certificado e nota fiscal) e agenda o upsert no TaskHS."""
    if lista is None or not taskhs_client.integracao_ativa():
        return
    certs = db.query(OSCertificado).filter(OSCertificado.os == ordem.id).all()
    certificados = [
        {"tipo": c.tipo, "url": certificado_link.link_certificado(ordem.id, c.tipo)}
        for c in certs
    ]
    nf_url = nota_fiscal_link.link_nota_fiscal(ordem.id) if ordem.nota_fiscal else None
    descricao = taskhs.montar_descricao(ordem, certificados=certificados, nota_fiscal_url=nf_url)
    payload = taskhs.montar_payload(ordem, lista=lista, arquivado=arquivado, descricao=descricao)
    background_tasks.add_task(taskhs_client.enviar_card, payload)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose exec -T backend pytest tests/test_taskhs_descricao.py tests/test_ordens_taskhs.py -q`
Expected: PASS.

- [ ] **Step 6: Run the full suite**

Run: `docker compose exec -T backend pytest -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/taskhs.py backend/app/api/ordens.py backend/tests/test_taskhs_descricao.py
git commit -m "feat(integracao): nota fiscal na secao Financeiro do card do TaskHS"
```

---

### Task 5: Frontend — seção Nota fiscal na OS

**Files:**
- Modify: `frontend/src/auth/roles.ts`
- Modify: `frontend/src/app/ordens/api.ts`
- Create: `frontend/src/app/ordens/NotaFiscalModal.tsx`
- Modify: `frontend/src/app/ordens/OrdemDetailPage.tsx`
- Test: `frontend/src/app/ordens/api.notaFiscal.test.ts`

**Interfaces:**
- Consumes (backend): `POST /ordens/{id}/nota-fiscal` (multipart: `file` + `numero`), `GET /ordens/{id}/nota-fiscal`; `OrdemDetalhe.nota_fiscal`, `OrdemDetalhe.nota_fiscal_numero`.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/app/ordens/api.notaFiscal.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ordensApi } from './api'

function okJson(body: unknown) {
  return { ok: true, status: 200, json: async () => body, headers: new Headers() } as unknown as Response
}

describe('enviarNotaFiscal', () => {
  beforeEach(() => {
    localStorage.setItem('gestorhs.tokens', JSON.stringify({ access_token: 'a', refresh_token: 'r' }))
  })

  it('envia multipart com o arquivo e o numero', async () => {
    const fetchMock = vi.fn().mockResolvedValue(okJson({ nota_fiscal: 'x.pdf', nota_fiscal_numero: '123' }))
    vi.stubGlobal('fetch', fetchMock)
    const file = new File([new Uint8Array([1])], 'nf.pdf', { type: 'application/pdf' })
    await ordensApi.enviarNotaFiscal(7, file, '123')
    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toContain('/ordens/7/nota-fiscal')
    expect((init as RequestInit).method).toBe('POST')
    const body = (init as RequestInit).body as FormData
    expect(body.get('numero')).toBe('123')
    expect(body.get('file')).toBeInstanceOf(File)
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/app/ordens/api.notaFiscal.test.ts`
Expected: FAIL (`ordensApi.enviarNotaFiscal is not a function`).

- [ ] **Step 3: Add the API client + types**

In `frontend/src/app/ordens/api.ts`, add the two fields to the `OrdemDetalhe` interface (junto de `pdf_certificado`):

```ts
  nota_fiscal: string | null
  nota_fiscal_numero: string | null
```

And add to the `ordensApi` object:

```ts
  enviarNotaFiscal: async (ordemId: number, file: File, numero: string): Promise<void> => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('numero', numero)
    const res = await apiFetch(`/ordens/${ordemId}/nota-fiscal`, { method: 'POST', body: fd })
    if (!res.ok) {
      let detail = res.statusText
      try { const b = await res.json(); if (b.detail) detail = b.detail } catch { /* sem corpo */ }
      throw new ApiError(res.status, detail)
    }
  },
```
(o download usa o `buscarBlobUrl` que já existe: `buscarBlobUrl(`/ordens/${id}/nota-fiscal`)`)

- [ ] **Step 4: Add the role rule**

In `frontend/src/auth/roles.ts`, after `FUNCAO_COMERCIAL`:

```ts
export const FUNCAO_FINANCEIRO = 'Financeiro'

export function podeAnexarNotaFiscal(user: User | null): boolean {
  return isAdmin(user) || user?.funcao === FUNCAO_FINANCEIRO
}
```
(se `FUNCAO_FINANCEIRO` já existir do trabalho anterior, apenas acrescente a função `podeAnexarNotaFiscal`.)

- [ ] **Step 5: Create the upload modal**

Create `frontend/src/app/ordens/NotaFiscalModal.tsx`:

```tsx
import { useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { ApiError } from '../../lib/api'
import { ordensApi } from './api'

interface Props {
  ordemId: number
  onClose: () => void
  onEnviado: () => void
}

export function NotaFiscalModal({ ordemId, onClose, onEnviado }: Props) {
  const [file, setFile] = useState<File | null>(null)
  const [numero, setNumero] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setErro('')
    if (!file) { setErro('Escolha o arquivo da nota fiscal (PDF ou XML).'); return }
    if (!numero.trim()) { setErro('Informe o número da nota fiscal.'); return }
    setEnviando(true)
    try {
      await ordensApi.enviarNotaFiscal(ordemId, file, numero.trim())
      onEnviado()
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao anexar a nota fiscal')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Anexar nota fiscal"
      footer={
        <>
          <button type="button" onClick={onClose} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">
            Cancelar
          </button>
          <button type="submit" form="form-nota-fiscal" disabled={enviando} className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all">
            Anexar
          </button>
        </>
      }
    >
      <form id="form-nota-fiscal" className="space-y-4" onSubmit={onSubmit}>
        <Input id="numero-nf" label="Número da nota fiscal" value={numero} onChange={(e) => setNumero(e.target.value)} required />
        <div>
          <label htmlFor="arquivo-nf" className="block text-sm font-medium text-slate-300 mb-1.5">Arquivo (PDF ou XML)</label>
          <input
            id="arquivo-nf"
            type="file"
            accept="application/pdf,.pdf,application/xml,text/xml,.xml"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="block w-full text-sm text-slate-300 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:bg-background-elevated file:text-slate-200 file:text-sm"
          />
        </div>
        {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      </form>
    </Modal>
  )
}
```

- [ ] **Step 6: Add the section to the OS detail page**

In `frontend/src/app/ordens/OrdemDetailPage.tsx`:

Imports — `IconCertificado` **já está importado** (linha ~7); acrescente:
```tsx
import { podeAnexarNotaFiscal } from '../../auth/roles'
import { NotaFiscalModal } from './NotaFiscalModal'
```
e acrescente `buscarBlobUrl` à lista que já vem de `./api`.

Estado do modal — o componente **já usa um estado `acao`** para todos os modais
(linha 107). Acrescente `'nota-fiscal'` à união, em vez de criar um estado novo:
```tsx
  const [acao, setAcao] = useState<'avancar' | 'cancelar' | 'gerar' | 'nota-fiscal' | null>(null)
```

Junto dos outros derivados (perto de `podeGerarOuRegerar`):
```tsx
  // A secao aparece do Financeiro em diante — use posicaoFase, NUNCA comparacao numerica (id 10 > 7/8).
  const mostraNotaFiscal = posicaoFase(os.fase) >= posicaoFase(10)
  const podeAnexarNF = podeAnexarNotaFiscal(user)
```

Recarga após anexar — siga o padrão que o `aoGerarCert` já usa (linha ~181):
```tsx
  function aoAnexarNF() {
    setAcao(null)
    void ordensApi.obter(osId).then(setOs).catch(() => {})
  }
```

A seção (renderize junto das outras `<Secao>`, depois da seção do certificado):
```tsx
      {mostraNotaFiscal && (
        <Secao
          icon={<IconCertificado />}
          titulo="Nota fiscal"
          acao={podeAnexarNF ? (
            <Button variant={os.nota_fiscal ? 'secondary' : 'primary'} onClick={() => setAcao('nota-fiscal')}>
              {os.nota_fiscal ? 'Substituir' : 'Anexar nota fiscal'}
            </Button>
          ) : undefined}
        >
          {os.nota_fiscal ? (
            <div className="flex items-center justify-between gap-3">
              <Campo label="Número" valor={os.nota_fiscal_numero} />
              <button
                onClick={async () => {
                  const url = await buscarBlobUrl(`/ordens/${os.id}/nota-fiscal`)
                  window.open(url, '_blank')
                }}
                className="text-xs text-primary hover:underline"
              >
                Baixar
              </button>
            </div>
          ) : (
            <p className="text-sm text-slate-500">
              Nenhuma nota fiscal anexada. É obrigatória para o Financeiro confirmar o pagamento.
            </p>
          )}
        </Secao>
      )}
```

E o modal, junto dos outros no fim do componente (linha ~454, ao lado de `acao === 'gerar'`):
```tsx
      {acao === 'nota-fiscal' && (
        <NotaFiscalModal ordemId={os.id} onClose={() => setAcao(null)} onEnviado={aoAnexarNF} />
      )}
```

- [ ] **Step 7: Verify the frontend**

Run: `cd frontend && npx tsc -b --noEmit && npm run lint && npm test && npm run build`
Expected: tudo limpo.

- [ ] **Step 8: Commit**

```bash
git add frontend/src
git commit -m "feat(ux): secao de nota fiscal na OS com upload e download"
```

---

### Task 6: Changelog + verificação final

**Files:**
- Modify: `frontend/src/app/changelog/data.ts`

- [ ] **Step 1: Changelog v1.13.0**

In `frontend/src/app/changelog/data.ts`, insert as the **first** entry (mantenha a **acentuação** correta — a regra "sem acentos" vale só para mensagens de commit):

```ts
  {
    versao: '1.13.0',
    data: '14/07/2026',
    itens: [
      { tipo: 'novidade', texto: 'O Financeiro agora precisa anexar a nota fiscal de serviço (PDF ou XML) e informar o número da NF antes de confirmar o pagamento e liberar a OS para envio. A nota fica disponível para download na própria OS e no cartão do TaskHS.' },
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
git commit -m "docs(changelog): v1.13.0 — nota fiscal obrigatoria no Financeiro"
```

---

## Notas de aplicação (produção, fora dos testes)

1. `docker compose exec -T backend alembic upgrade head` — migração **0013** (só adiciona duas colunas nullable; **retrocompatível**, o código antigo não quebra).
2. Deploy do código novo (backend + frontend). **Não** requer rebuild por dependência nova.
3. Sem backfill: as OS que já estão no Financeiro passam a exigir a NF para avançar.
4. Validar E2E: numa OS em Financeiro, tentar avançar sem NF (deve dar a mensagem do 409), anexar a NF (PDF) com número, avançar (vai para Preparando Retorno e marca como paga), e conferir a linha `Nota fiscal: {numero} — {link}` na seção 💰 Financeiro do cartão do TaskHS.
