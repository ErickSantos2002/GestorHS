# Certificado avulso ("em branco") — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** O Laboratório emite um certificado sem OS, sem cliente e sem aparelho cadastrados (caso dos aparelhos de POC), escolhendo um template existente e digitando os dados.

**Architecture:** O conjunto de chaves do contexto (~31 tokens: `CAMPOS` + nomes legados + aliases) passa a viver num **construtor puro compartilhado**, usado tanto pelo fluxo da OS quanto pelo avulso — evitando duas listas paralelas que divergiriam. `preencher()` e `html_para_pdf()` são reaproveitados sem alteração. O avulso é gravado numa tabela nova **sem nenhuma FK para cliente ou aparelho**.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, pytest (SQLite in-memory, Docker); React 19 + TS + Vite + Vitest.

## Global Constraints

- Backend em Docker: testes com `docker compose exec -T backend pytest ... -q`. Frontend: `cd frontend && npx tsc -b --noEmit && npm run lint && npm test && npm run build`.
- **NÃO rodar alembic nos testes** (SQLite constrói pelos modelos). A migração `0014_certificado_avulso` (`down_revision = "0013_nota_fiscal"`) é aplicada em produção à parte. É **aditiva** (só cria uma tabela).
- ⚠️ **`preencher()` só substitui as chaves presentes no contexto.** Um token ausente fica **literalmente escrito no PDF** — verificado: `preencher("<p>[nomecli] / [proxcalibragem]</p>", {"nomecli": "ACME"})` → `"<p>ACME / [proxcalibragem]</p>"`. Por isso o contexto do avulso precisa ter **exatamente o mesmo conjunto de chaves** do da OS.
- **`pulapagina` NÃO entra no contexto.** `preencher()` já o trata fora do laço, inserindo a quebra de página **sem escapar** (é HTML estrutural). Colocá-lo no contexto o escaparia e quebraria a paginação.
- Permissão para gerar: `require_funcao("Laboratório", "Administrador")`.
- Os 12 modelos reais usam: `nomecli, cnpj, endcli, serie, datacompra, os, calibcert, datacali, dataentr, calibtemp, calibpressao, calibteste1, calibteste2, calibteste3, calibtestemedia, situcalib, pulapagina`. Nenhum usa `proxcalibragem` nem os aliases.
- Defaults do formulário avulso: **`os` = `"XXXX"`** e **data de recebimento = hoje** (ambos editáveis).
- Commits: Conventional Commits PT-BR **sem acentos**, uma linha, sem trailer de co-autor.

---

### Task 1: Construtor de contexto compartilhado (refactor seguro)

**Files:**
- Modify: `backend/app/core/certificado_gerar.py`
- Test: `backend/tests/test_certificado_contexto.py`

**Interfaces:**
- Produces: `_montar_contexto(**valores) -> dict[str, str]` (puro, a **única** definição do conjunto de chaves); `montar_contexto_avulso(valores: dict) -> dict[str, str]`.
- `montar_contexto(db, ordem)` mantém a assinatura e o **comportamento idêntico** — passa a extrair da OS e delegar.

Este é o ponto de risco da entrega: mexe no caminho crítico do certificado da OS. Por isso vem isolado, com um teste que trava a equivalência **antes** de qualquer mudança.

- [ ] **Step 1: Write the characterization test (trava o comportamento ATUAL)**

Create `backend/tests/test_certificado_contexto.py`:

```python
"""Contexto do certificado: o conjunto de chaves e a fonte unica da verdade.

`preencher()` so substitui as chaves presentes no contexto — um token ausente fica
LITERALMENTE escrito no PDF. Por isso o contexto do avulso tem de ter exatamente as
mesmas chaves do contexto da OS.
"""
from datetime import date

from app.core.certificado_gerar import CAMPOS, montar_contexto, montar_contexto_avulso, preencher


def _os_com_dados(db_session, os_base):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"],
              fase=5, situacao="E", tipo_servico="C",
              calib_cert="C-1", calib_temp="22", calib_pressao="1013",
              calib_teste1="0,10", calib_teste2="0,11", calib_teste3="0,12",
              calib_teste_media="0,11", calib_situacao="Aprovado")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    return o


def test_avulso_tem_exatamente_as_mesmas_chaves_da_os(db_session, os_base):
    """A regressao que este teste impede: o avulso esquecer uma chave e vazar [token] no PDF."""
    o = _os_com_dados(db_session, os_base)
    ctx_os = montar_contexto(db_session, o)
    ctx_avulso = montar_contexto_avulso({})
    assert set(ctx_avulso.keys()) == set(ctx_os.keys())


def test_nenhum_token_conhecido_vaza_no_avulso():
    """Um modelo que usa TODOS os tokens nao pode sair com nenhum [token] literal."""
    html = " ".join(f"[{campo}]" for campo, _ in CAMPOS)
    saida = preencher(html, montar_contexto_avulso({"nomecli": "ACME"}))
    assert "[" not in saida and "]" not in saida


def test_avulso_usa_os_valores_digitados():
    ctx = montar_contexto_avulso({
        "nomecli": "POC Ltda", "serie": "SN-9", "calib_cert": "AV-1",
        "calib_situacao": "Aprovado", "data_calibracao": date(2026, 7, 14),
    })
    assert ctx["nomecli"] == "POC Ltda"
    assert ctx["serie"] == "SN-9"
    assert ctx["calibcert"] == "AV-1"
    assert ctx["situcalib"] == "Aprovado"
    assert ctx["datacali"] == "14/07/2026"      # formatado DD/MM/AAAA


def test_avulso_preenche_vazio_o_que_nao_foi_informado():
    ctx = montar_contexto_avulso({})
    assert ctx["nomecli"] == ""
    assert ctx["proxcalibragem"] == ""      # nenhum modelo real usa, mas a chave existe
    assert ctx["tipocalibragem"] == ""


def test_avulso_nao_inclui_pulapagina_no_contexto():
    """pulapagina e tratado FORA do laco (HTML estrutural, sem escape).
    No contexto ele seria escapado e a quebra de pagina pararia de funcionar."""
    assert "pulapagina" not in montar_contexto_avulso({})


def test_pulapagina_continua_virando_quebra_de_pagina():
    saida = preencher("<p>a</p>[pulapagina]<p>b</p>", montar_contexto_avulso({}))
    assert "page-break-after" in saida
    assert "[pulapagina]" not in saida
```

- [ ] **Step 2: Run to verify it fails**

Run: `docker compose exec -T backend pytest tests/test_certificado_contexto.py -q`
Expected: FAIL (`ImportError: cannot import name 'montar_contexto_avulso'`).

- [ ] **Step 3: Extract the shared builder**

In `backend/app/core/certificado_gerar.py`, add the pure builder. It is the **única** definição do conjunto de chaves — repare que ele reproduz exatamente as chaves que `montar_contexto` monta hoje (nomes de `CAMPOS` + legados + aliases), **sem `pulapagina`**:

```python
def _montar_contexto(
    *,
    nomecli: str = "", cnpj: str = "", endcli: str = "",
    modelo: str = "", marca: str = "", serie: str = "", patrimonio: str = "",
    datacompra: str = "", os_num: str = "", calibcert: str = "",
    proxcalibragem: str = "", tipocalibragem: str = "",
    datacali: str = "", dataentr: str = "",
    temp: str = "", pressao: str = "", t1: str = "", t2: str = "", t3: str = "",
    media: str = "", situ: str = "",
) -> dict[str, str]:
    """Fonte UNICA do conjunto de chaves do certificado.

    Usado pelo fluxo da OS (`montar_contexto`) e pelo avulso (`montar_contexto_avulso`).
    Manter os dois caminhos aqui impede que um token novo entre em um e falte no outro —
    e um token que falta no contexto sai LITERALMENTE escrito no PDF.
    NAO inclui `pulapagina`: `preencher()` o trata fora do laco, sem escapar.
    """
    hoje = _fmt(date.today())
    return {
        "nomecli": nomecli,
        "cnpj": cnpj,
        "endcli": endcli,
        "modelo": modelo,
        "marca": marca,
        "serie": serie,
        "patrimonio": patrimonio,
        "datacompra": datacompra,
        "os": os_num,
        "calibcert": calibcert,
        "proxcalibragem": proxcalibragem,
        "tipocalibragem": tipocalibragem,
        "dataemissao": hoje,
        # nomes legados (usados nos 12 modelos migrados)
        "datacali": datacali,
        "dataentr": dataentr,
        "calibtemp": temp,
        "calibpressao": pressao,
        "calibteste1": t1,
        "calibteste2": t2,
        "calibteste3": t3,
        "calibtestemedia": media,
        "situcalib": situ,
        # aliases amigáveis (para modelos novos)
        "datacalibracao": datacali,
        "temperatura": temp,
        "pressao": pressao,
        "teste1": t1,
        "teste2": t2,
        "teste3": t3,
        "media": media,
        "situacao": situ,
        "datacli": hoje,
    }
```

- [ ] **Step 4: Make `montar_contexto` delegate (comportamento IDÊNTICO)**

Substitua o corpo de `montar_contexto` para extrair da OS e delegar. Os `cert_overrides`
continuam sendo aplicados **depois** (são específicos da OS):

```python
def montar_contexto(db: Session, ordem) -> dict[str, str]:
    cli = ordem.cliente_rel
    ec = ordem.equipamento_rel  # EquipamentoCliente
    modelo = marca = ""
    if ec is not None:
        cat = db.get(Equipamento, ec.equipamento)
        if cat is not None:
            modelo = cat.descricao or ""
            if cat.marca:
                m = db.get(Marca, cat.marca)
                marca = (m.descricao if m else "") or ""
    tipocal = ""
    if ordem.tipo_calibragem:
        tc = db.get(TipoCalibragem, ordem.tipo_calibragem)
        tipocal = (tc.descricao if tc else "") or ""
    ctx = _montar_contexto(
        nomecli=(cli.nome if cli else "") or "",
        cnpj=((cli.cgc or cli.cpf) if cli else "") or "",
        endcli=_endereco(cli),
        modelo=modelo,
        marca=marca,
        serie=(ec.serie if ec else "") or "",
        patrimonio=(ec.patrimonio if ec else "") or "",
        datacompra=_fmt(ec.datacompra) if ec else "",
        os_num=str(ordem.id),
        calibcert=ordem.calib_cert or "",
        proxcalibragem=_fmt(ordem.prox_calibragem),
        tipocalibragem=tipocal,
        datacali=_fmt(ordem.data_calibracao),
        dataentr=_fmt(ordem.data_chegada),
        temp=ordem.calib_temp or "",
        pressao=ordem.calib_pressao or "",
        t1=ordem.calib_teste1 or "",
        t2=ordem.calib_teste2 or "",
        t3=ordem.calib_teste3 or "",
        media=ordem.calib_teste_media or "",
        situ=ordem.calib_situacao or "",
    )
    for chave, valor in (ordem.cert_overrides or {}).items():
        if valor:
            ctx[chave] = valor
    return ctx
```

- [ ] **Step 5: Add the avulso context builder**

```python
def montar_contexto_avulso(valores: dict) -> dict[str, str]:
    """Contexto de um certificado sem OS (aparelho de POC): os valores sao DIGITADOS.

    Delega ao mesmo `_montar_contexto` do fluxo da OS — e por isso emite exatamente o
    mesmo conjunto de chaves, sem risco de um token vazar como [token] no PDF.
    """
    return _montar_contexto(
        nomecli=valores.get("nomecli") or "",
        cnpj=valores.get("cnpj") or "",
        endcli=valores.get("endcli") or "",
        modelo=valores.get("modelo") or "",
        marca=valores.get("marca") or "",
        serie=valores.get("serie") or "",
        patrimonio=valores.get("patrimonio") or "",
        datacompra=_fmt(valores.get("datacompra")),
        os_num=valores.get("os") or "",
        calibcert=valores.get("calib_cert") or "",
        datacali=_fmt(valores.get("data_calibracao")),
        dataentr=_fmt(valores.get("data_recebimento")),
        temp=valores.get("calib_temp") or "",
        pressao=valores.get("calib_pressao") or "",
        t1=valores.get("calib_teste1") or "",
        t2=valores.get("calib_teste2") or "",
        t3=valores.get("calib_teste3") or "",
        media=valores.get("calib_teste_media") or "",
        situ=valores.get("calib_situacao") or "",
    )
```
(`proxcalibragem` e `tipocalibragem` ficam com o default `""` — nenhum modelo real os usa.)

`_fmt` já aceita `None`, `date` e `datetime` e devolve `""`/`DD/MM/AAAA`.

- [ ] **Step 6: Run the new tests + the existing certificate tests**

Run: `docker compose exec -T backend pytest tests/test_certificado_contexto.py tests/test_certificados.py tests/test_certificado_os_api.py tests/test_certificado_sem_modelo.py -q`
Expected: PASS — os testes do certificado da OS **não podem ter mudado de comportamento** (é um refactor).

- [ ] **Step 7: Run the full suite**

Run: `docker compose exec -T backend pytest -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/core/certificado_gerar.py backend/tests/test_certificado_contexto.py
git commit -m "refactor(cert): fonte unica do contexto do certificado (OS e avulso)"
```

---

### Task 2: Modelo, migração e endpoints do certificado avulso

**Files:**
- Create: `backend/app/models/certificado_avulso.py`
- Modify: `backend/app/models/__init__.py` (exportar o modelo)
- Create: `backend/alembic/versions/0014_certificado_avulso.py`
- Create: `backend/app/schemas/certificado_avulso.py`
- Create: `backend/app/api/certificados_avulsos.py`
- Modify: `backend/app/main.py` (registrar o router)
- Test: `backend/tests/test_certificado_avulso.py`

**Interfaces:**
- Consumes: `montar_contexto_avulso`, `preencher`, `html_para_pdf` (Task 1 / existentes).
- Produces: `POST /certificados-avulsos`, `GET /certificados-avulsos`, `GET /certificados-avulsos/{id}/pdf`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_certificado_avulso.py`:

```python
def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _modelo(db_session, os_base, tipo="C", texto="<p>[nomecli] | [serie] | [calibcert] | [os]</p>"):
    from app.models import CertificadoModelo
    db_session.add(CertificadoModelo(equipamento=os_base["equipamento"], tipo=tipo, texto=texto))
    db_session.commit()


def _payload(os_base, **kw):
    base = {
        "equipamento": os_base["equipamento"], "tipo": "C",
        "nomecli": "POC Ltda", "cnpj": "11222333000144", "endcli": "Rua X, 10",
        "modelo": "ALCOSCAN", "marca": "AC", "serie": "SN-POC-1", "patrimonio": "",
        "datacompra": None, "os": "XXXX", "data_recebimento": "2026-07-14",
        "calib_cert": "AV-001", "data_calibracao": "2026-07-14",
        "calib_temp": "22", "calib_pressao": "1013",
        "calib_teste1": "0,10", "calib_teste2": "0,11", "calib_teste3": "0,12",
        "calib_teste_media": "0,11", "calib_situacao": "Aprovado",
    }
    base.update(kw)
    return base


def test_gerar_avulso_salva_e_preenche_o_html(client, usuario_lab, os_base, db_session):
    _modelo(db_session, os_base)
    h = _headers(client, "lab@hs.com", "senha123")
    r = client.post("/certificados-avulsos", json=_payload(os_base), headers=h)
    assert r.status_code == 201
    body = r.json()
    assert body["nomecli"] == "POC Ltda"
    assert body["calib_cert"] == "AV-001"

    from app.models import CertificadoAvulso
    av = db_session.query(CertificadoAvulso).filter(CertificadoAvulso.id == body["id"]).first()
    assert "POC Ltda" in av.html and "SN-POC-1" in av.html and "XXXX" in av.html
    assert "[" not in av.html          # nenhum token vazou
    assert av.usuario == usuario_lab.id
    assert av.data_geracao is not None


def test_gerar_avulso_nao_cria_nem_altera_nenhuma_OS(client, usuario_lab, os_base, db_session):
    """O ponto da feature: nada de OS, cliente ou aparelho e tocado."""
    from app.models import Ordem
    _modelo(db_session, os_base)
    antes = db_session.query(Ordem).count()
    h = _headers(client, "lab@hs.com", "senha123")
    assert client.post("/certificados-avulsos", json=_payload(os_base), headers=h).status_code == 201
    assert db_session.query(Ordem).count() == antes


def test_gerar_avulso_sem_template_409(client, usuario_lab, os_base, db_session):
    h = _headers(client, "lab@hs.com", "senha123")
    r = client.post("/certificados-avulsos", json=_payload(os_base), headers=h)
    assert r.status_code == 409
    assert "modelo" in r.json()["detail"].lower()


def test_gerar_avulso_exige_laboratorio_403(client, usuario_comercial, os_base, db_session):
    _modelo(db_session, os_base)
    h = _headers(client, "comercial@hs.com", "senha123")
    r = client.post("/certificados-avulsos", json=_payload(os_base), headers=h)
    assert r.status_code == 403


def test_admin_tambem_pode_gerar(client, usuario_admin, os_base, db_session):
    _modelo(db_session, os_base)
    h = _headers(client, "admin@hs.com", "senha123")
    assert client.post("/certificados-avulsos", json=_payload(os_base), headers=h).status_code == 201


def test_listar_avulsos(client, usuario_lab, os_base, db_session):
    _modelo(db_session, os_base)
    h = _headers(client, "lab@hs.com", "senha123")
    client.post("/certificados-avulsos", json=_payload(os_base, calib_cert="AV-1"), headers=h)
    client.post("/certificados-avulsos", json=_payload(os_base, calib_cert="AV-2"), headers=h)
    itens = client.get("/certificados-avulsos", headers=h).json()
    assert [i["calib_cert"] for i in itens] == ["AV-2", "AV-1"]   # mais recentes primeiro
    assert itens[0]["usuario_nome"] == usuario_lab.nome


def test_baixar_pdf_do_avulso(client, usuario_lab, os_base, db_session, monkeypatch):
    from app.api import certificados_avulsos
    monkeypatch.setattr(certificados_avulsos, "html_para_pdf", lambda html: b"%PDF-fake")
    _modelo(db_session, os_base)
    h = _headers(client, "lab@hs.com", "senha123")
    cid = client.post("/certificados-avulsos", json=_payload(os_base), headers=h).json()["id"]
    r = client.get(f"/certificados-avulsos/{cid}/pdf", headers=h)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"


def test_baixar_pdf_inexistente_404(client, usuario_lab):
    h = _headers(client, "lab@hs.com", "senha123")
    assert client.get("/certificados-avulsos/9999/pdf", headers=h).status_code == 404
```

- [ ] **Step 2: Run to verify failure**

Run: `docker compose exec -T backend pytest tests/test_certificado_avulso.py -q`
Expected: FAIL (rota inexistente → 404/405; `CertificadoAvulso` não existe).

- [ ] **Step 3: Create the model**

Create `backend/app/models/certificado_avulso.py`:

```python
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.models.database import Base


class CertificadoAvulso(Base):
    """Certificado emitido SEM OS, cliente ou aparelho cadastrados (aparelhos de POC).

    Nao ha FK para clientes nem equipamentos_cliente — e exatamente o ponto da feature.
    O `html` e auto-contido; os campos soltos existem so para a listagem.
    """
    __tablename__ = "certificados_avulsos"

    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String(1), nullable=False)          # C / M — do template escolhido
    html = Column(Text, nullable=False)               # certificado ja preenchido
    nomecli = Column(String(200), nullable=True)
    serie = Column(String(50), nullable=True)
    calib_cert = Column(String(50), nullable=True)
    data_calibracao = Column(Date, nullable=True)
    usuario = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    data_geracao = Column(DateTime(timezone=True), nullable=True)

    usuario_rel = relationship("Usuario", lazy="joined")

    @property
    def usuario_nome(self):
        return self.usuario_rel.nome if self.usuario_rel else None
```

In `backend/app/models/__init__.py`, export it alongside the others (follow the file's existing import/`__all__` style; do not drop any existing name).

- [ ] **Step 4: Create the migration**

Create `backend/alembic/versions/0014_certificado_avulso.py`:

```python
"""certificados avulsos: certificado sem OS/cliente/aparelho (POC)

Revision ID: 0014_certificado_avulso
Revises: 0013_nota_fiscal
"""
from alembic import op
import sqlalchemy as sa

revision = "0014_certificado_avulso"
down_revision = "0013_nota_fiscal"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "certificados_avulsos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tipo", sa.String(1), nullable=False),
        sa.Column("html", sa.Text(), nullable=False),
        sa.Column("nomecli", sa.String(200), nullable=True),
        sa.Column("serie", sa.String(50), nullable=True),
        sa.Column("calib_cert", sa.String(50), nullable=True),
        sa.Column("data_calibracao", sa.Date(), nullable=True),
        sa.Column("usuario", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("data_geracao", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_table("certificados_avulsos")
```

- [ ] **Step 5: Create the schemas**

Create `backend/app/schemas/certificado_avulso.py`:

```python
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CertificadoAvulsoIn(BaseModel):
    equipamento: int          # o aparelho do TEMPLATE escolhido
    tipo: str                 # C / M
    # dados digitados (todos opcionais — o laboratorio preenche o que tiver)
    nomecli: Optional[str] = None
    cnpj: Optional[str] = None
    endcli: Optional[str] = None
    modelo: Optional[str] = None
    marca: Optional[str] = None
    serie: Optional[str] = None
    patrimonio: Optional[str] = None
    datacompra: Optional[date] = None
    os: Optional[str] = None                    # default do form: "XXXX"
    data_recebimento: Optional[date] = None     # default do form: hoje
    calib_cert: Optional[str] = None
    data_calibracao: Optional[date] = None
    calib_temp: Optional[str] = None
    calib_pressao: Optional[str] = None
    calib_teste1: Optional[str] = None
    calib_teste2: Optional[str] = None
    calib_teste3: Optional[str] = None
    calib_teste_media: Optional[str] = None
    calib_situacao: Optional[str] = None


class CertificadoAvulsoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tipo: str
    nomecli: Optional[str] = None
    serie: Optional[str] = None
    calib_cert: Optional[str] = None
    data_calibracao: Optional[date] = None
    data_geracao: Optional[datetime] = None
    usuario_nome: Optional[str] = None
```

- [ ] **Step 6: Create the router**

Create `backend/app/api/certificados_avulsos.py`:

```python
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_usuario, require_funcao
from app.core.certificado_gerar import montar_contexto_avulso, preencher
from app.core.certificado_pdf import html_para_pdf
from app.models import CertificadoAvulso, CertificadoModelo, Usuario
from app.models.database import get_db
from app.schemas.certificado_avulso import CertificadoAvulsoIn, CertificadoAvulsoOut

router = APIRouter(prefix="/certificados-avulsos", tags=["certificados-avulsos"])

_GERAR = require_funcao("Laboratório", "Administrador")
_LABEL_TIPO = {"C": "Calibração", "M": "Manutenção"}


@router.post("", response_model=CertificadoAvulsoOut, status_code=status.HTTP_201_CREATED)
def gerar(dados: CertificadoAvulsoIn, db: Session = Depends(get_db),
          usuario: Usuario = Depends(_GERAR)):
    modelo = db.query(CertificadoModelo).filter(
        CertificadoModelo.equipamento == dados.equipamento,
        CertificadoModelo.tipo == dados.tipo,
    ).first()
    if modelo is None or not modelo.texto:
        rotulo = _LABEL_TIPO.get(dados.tipo, dados.tipo)
        raise HTTPException(
            status_code=409,
            detail=f"O aparelho escolhido não tem modelo de certificado de {rotulo} cadastrado.",
        )
    html = preencher(modelo.texto, montar_contexto_avulso(dados.model_dump()))
    av = CertificadoAvulso(
        tipo=dados.tipo,
        html=html,
        nomecli=dados.nomecli,
        serie=dados.serie,
        calib_cert=dados.calib_cert,
        data_calibracao=dados.data_calibracao,
        usuario=usuario.id,
        data_geracao=datetime.now(timezone.utc),
    )
    db.add(av)
    db.commit()
    db.refresh(av)
    return av


@router.get("", response_model=list[CertificadoAvulsoOut])
def listar(db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    return db.query(CertificadoAvulso).order_by(CertificadoAvulso.id.desc()).all()


@router.get("/{avulso_id}/pdf")
def baixar_pdf(avulso_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    av = db.query(CertificadoAvulso).filter(CertificadoAvulso.id == avulso_id).first()
    if av is None:
        raise HTTPException(status_code=404, detail="certificado não encontrado")
    try:
        pdf = html_para_pdf(av.html)
    except Exception:
        raise HTTPException(status_code=500, detail="falha ao gerar PDF")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="certificado-avulso-{av.id}.pdf"'},
    )
```

In `backend/app/main.py`: add `certificados_avulsos` to the `from app.api import (...)` line and register `app.include_router(certificados_avulsos.router)`. Do not drop any existing router name.

- [ ] **Step 7: Run tests to verify they pass**

Run: `docker compose exec -T backend pytest tests/test_certificado_avulso.py -q`
Expected: PASS (8 passed).

- [ ] **Step 8: Run the full suite**

Run: `docker compose exec -T backend pytest -q`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/app/models/certificado_avulso.py backend/app/models/__init__.py backend/alembic/versions/0014_certificado_avulso.py backend/app/schemas/certificado_avulso.py backend/app/api/certificados_avulsos.py backend/app/main.py backend/tests/test_certificado_avulso.py
git commit -m "feat(cert): certificado avulso sem OS cliente ou aparelho"
```

---

### Task 3: Frontend — aba "Em branco" na página Certificados

**Files:**
- Modify: `frontend/src/app/certificados/api.ts`
- Create: `frontend/src/app/certificados/CertificadoAvulsoModal.tsx`
- Create: `frontend/src/app/certificados/AvulsosTab.tsx`
- Modify: `frontend/src/app/certificados/CertificadosPage.tsx`
- Test: `frontend/src/app/certificados/api.avulso.test.ts`

**Interfaces:**
- Consumes (backend): `POST /certificados-avulsos`, `GET /certificados-avulsos`, `GET /certificados-avulsos/{id}/pdf`; `certificadosApi.listarModelos()` (já existe, devolve `ModeloItem[]` com `equipamento`, `equipamento_descricao`, `tem_calibracao`, `tem_manutencao`).

- [ ] **Step 1: Write the failing test**

Create `frontend/src/app/certificados/api.avulso.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { certificadosApi } from './api'

function okJson(body: unknown) {
  return { ok: true, status: 200, json: async () => body, headers: new Headers() } as unknown as Response
}

describe('certificados avulsos', () => {
  beforeEach(() => {
    localStorage.setItem('gestorhs.tokens', JSON.stringify({ access_token: 'a', refresh_token: 'r' }))
  })

  it('gera o avulso enviando o template e os campos', async () => {
    const fetchMock = vi.fn().mockResolvedValue(okJson({ id: 1, tipo: 'C' }))
    vi.stubGlobal('fetch', fetchMock)
    await certificadosApi.gerarAvulso({ equipamento: 5, tipo: 'C', nomecli: 'POC', os: 'XXXX' })
    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toContain('/certificados-avulsos')
    expect((init as RequestInit).method).toBe('POST')
    expect(JSON.parse((init as RequestInit).body as string)).toMatchObject({ equipamento: 5, tipo: 'C', os: 'XXXX' })
  })

  it('lista os avulsos', async () => {
    const fetchMock = vi.fn().mockResolvedValue(okJson([{ id: 2 }]))
    vi.stubGlobal('fetch', fetchMock)
    const r = await certificadosApi.listarAvulsos()
    expect(String(fetchMock.mock.calls[0][0])).toContain('/certificados-avulsos')
    expect(r[0].id).toBe(2)
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/app/certificados/api.avulso.test.ts`
Expected: FAIL (`certificadosApi.gerarAvulso is not a function`).

- [ ] **Step 3: Add the API client**

In `frontend/src/app/certificados/api.ts`, add the types and the three calls (siga o estilo do arquivo, que já usa `apiJson`/`apiFetch`):

```ts
export interface AvulsoItem {
  id: number
  tipo: 'C' | 'M'
  nomecli: string | null
  serie: string | null
  calib_cert: string | null
  data_calibracao: string | null
  data_geracao: string | null
  usuario_nome: string | null
}

export interface AvulsoPayload {
  equipamento: number
  tipo: 'C' | 'M'
  nomecli?: string | null
  cnpj?: string | null
  endcli?: string | null
  modelo?: string | null
  marca?: string | null
  serie?: string | null
  patrimonio?: string | null
  datacompra?: string | null
  os?: string | null
  data_recebimento?: string | null
  calib_cert?: string | null
  data_calibracao?: string | null
  calib_temp?: string | null
  calib_pressao?: string | null
  calib_teste1?: string | null
  calib_teste2?: string | null
  calib_teste3?: string | null
  calib_teste_media?: string | null
  calib_situacao?: string | null
}
```
E dentro do objeto `certificadosApi`:
```ts
  gerarAvulso: (payload: AvulsoPayload): Promise<AvulsoItem> =>
    apiJson<AvulsoItem>('/certificados-avulsos', { method: 'POST', body: JSON.stringify(payload) }),

  listarAvulsos: (): Promise<AvulsoItem[]> => apiJson<AvulsoItem[]>('/certificados-avulsos'),
```
Para o PDF, use o helper de download autenticado que o projeto já tem: em
`frontend/src/app/ordens/api.ts` existe `ordensApi.baixarCertificadoPdf`, que baixa um
PDF protegido criando uma âncora com `download` e revogando o object URL. **Leia esse
helper e reproduza o mesmo idioma** aqui como `baixarAvulsoPdf(id)` apontando para
`/certificados-avulsos/{id}/pdf`. (Não use `window.open` num blob — é o vetor de XSS
que já corrigimos nesta base.)

- [ ] **Step 4: Create the modal**

Create `frontend/src/app/certificados/CertificadoAvulsoModal.tsx`.

O formulário reproduz o do laboratório (`frontend/src/app/ordens/GerarCertificadoModal.tsx`)
— **leia-o e siga a mesma estrutura visual e o mesmo comportamento**, com estas diferenças:

1. **Seletor de template no topo** (obrigatório): um `Select` alimentado por
   `certificadosApi.listarModelos()`. Cada `ModeloItem` vira uma ou duas opções conforme
   `tem_calibracao` / `tem_manutencao`, com `value` = `"{equipamento}:{tipo}"` e rótulo
   `"{equipamento_descricao} — Calibração"` / `"— Manutenção"`. Sem seleção, o botão
   Salvar fica desabilitado.
2. **Todos os campos começam vazios**, exceto os dois defaults:
   - `os` (label **"Número da OS"**) inicia com **`'XXXX'`**;
   - `data_recebimento` (label **"Data de recebimento"**, `type="date"`) inicia com **hoje**
     (`new Date().toISOString().slice(0, 10)`).
   Ambos editáveis.
3. Os demais campos são os mesmos: Nome, CNPJ/CPF, Endereço; Modelo, Marca, Série,
   Patrimônio, Data de compra; Data de calibração (`type="date"`), Nº do certificado,
   Situação (`Select`), Temperatura, Pressão, Teste 1/2/3, Média.
4. **Média automática**: o modal da OS recalcula a média a partir dos testes até o usuário
   editá-la à mão (estado `mediaEditada`). Reproduza esse mesmo comportamento.
5. Ao salvar: monta o `AvulsoPayload` (quebrando o `"{equipamento}:{tipo}"` do seletor em
   `equipamento` + `tipo`), chama `certificadosApi.gerarAvulso`, e em caso de erro exibe
   `err.message` (o 409 do template inexistente aparece assim). Sucesso → `onGerado()`.

- [ ] **Step 5: Create the tab**

Create `frontend/src/app/certificados/AvulsosTab.tsx`:
- Carrega `certificadosApi.listarAvulsos()`.
- Cabeçalho com um texto curto explicando o uso (**"Certificados emitidos sem OS — para
  aparelhos de POC, de empresas não cadastradas."**) e o botão **"Gerar certificado em
  branco"** (visível só para Laboratório/Admin — use `isAdmin(user) || user?.funcao === 'Laboratório'`,
  mesmo critério do `podeGerarCert` em `OrdemDetailPage.tsx`).
- `Table` com as colunas: **Nº do certificado · Cliente · Série · Tipo · Data da calibração ·
  Gerado por · Ações**. A ação é **Baixar PDF** (chama `baixarAvulsoPdf(id)`).
- Lista vazia → `<p>` com "Nenhum certificado avulso emitido."
- Ao gerar com sucesso, recarrega a lista.

- [ ] **Step 6: Add the tab to the page**

In `frontend/src/app/certificados/CertificadosPage.tsx`, add the third tab:

```tsx
const ABAS = ['Modelos', 'Imagens', 'Em branco'] as const
```
and render it:
```tsx
      {aba === 'Modelos' ? <ModelosTab /> : aba === 'Imagens' ? <ImagensTab /> : <AvulsosTab />}
```
(importando `AvulsosTab`). Atualize também o subtítulo da página para mencionar os
certificados em branco.

- [ ] **Step 7: Verify the frontend**

Run: `cd frontend && npx tsc -b --noEmit && npm run lint && npm test && npm run build`
Expected: tudo limpo.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/app/certificados
git commit -m "feat(ux): aba de certificado em branco na pagina Certificados"
```

---

### Task 4: Changelog + verificação final

**Files:**
- Modify: `frontend/src/app/changelog/data.ts`

- [ ] **Step 1: Changelog v1.14.0**

In `frontend/src/app/changelog/data.ts`, insert as the **first** entry (mantenha a **acentuação** correta — a regra "sem acentos" vale só para mensagens de commit):

```ts
  {
    versao: '1.14.0',
    data: '14/07/2026',
    itens: [
      { tipo: 'novidade', texto: 'O laboratório agora pode emitir um certificado em branco, sem OS: na página Certificados, aba "Em branco", escolha um modelo já cadastrado, preencha os dados e gere o PDF. Serve para aparelhos de POC, de empresas que não estão cadastradas no sistema. O certificado fica registrado (com quem emitiu e quando) e pode ser baixado a qualquer momento, sem ficar vinculado a nenhuma empresa ou aparelho.' },
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
git commit -m "docs(changelog): v1.14.0 — certificado em branco sem OS"
```

---

## Notas de aplicação (produção, fora dos testes)

1. `docker compose exec -T backend alembic upgrade head` — migração **0014** (só **cria a tabela nova**; **retrocompatível**, não toca em nada existente).
2. Deploy normal (sem rebuild — nenhuma dependência nova).
3. Validar E2E: na página Certificados → aba "Em branco" → "Gerar certificado em branco" → escolher um template (ex.: um dos 12 aparelhos que têm modelo) → preencher (o Nº da OS já vem `XXXX` e a data de recebimento já vem hoje) → gerar → conferir que o PDF sai preenchido e **sem nenhum `[token]` literal** → conferir que a OS/cliente/aparelho não foram tocados.
