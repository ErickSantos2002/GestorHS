# Geração de certificado no laboratório (OS) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ao concluir o laboratório, gerar o certificado de Calibração (e o de Manutenção quando houver) preenchendo o modelo do aparelho com os dados reais; guardar o HTML por OS+tipo e permitir imprimir pelo navegador.

**Architecture:** `certificados.tipo` (C/M) → 2 modelos por aparelho. Motor puro `certificado_gerar` (monta contexto + substitui `[campo]`). Tabela `os_certificados` guarda o HTML preenchido por OS+tipo. Geração automática no avanço 5→6 (best-effort) + endpoint de regerar. Front: editor por tipo + seção/print na OS. PDF no servidor adiado.

**Tech Stack:** Backend FastAPI + SQLAlchemy + Alembic + pytest (SQLite). Frontend React + TS + Vite + Vitest.

**Spec:** `docs/superpowers/specs/2026-06-08-geracao-certificado-os-design.md`

**Convenções:** testes backend `cd backend && python -m pytest -q`; frontend `cd frontend && npx vitest run`. Auth: escrita cert = `require_funcao("Laboratório","Administrador")`; leitura = `get_current_usuario`. Fixtures: `usuario_admin`, `usuario_lab`, `usuario_comercial`, `os_base` (cria cliente+equipamento(catálogo)+equipamento_cliente, devolve ids), `fases_seed`. Helper auth nos testes: `_headers(client, login, senha)`. `agora()` = `from app.api.ordens_acoes import agora` (datetime UTC).

**Regra do projeto:** toda mudança bumpa versão + entra no ChangelogModal (Task 9).

**Fora:** PDF no servidor (campo `os_certificados.pdf` fica reservado).

---

## Task 1: Migração `0007_os_certificados`

**Files:**
- Create: `backend/alembic/versions/0007_os_certificados.py`

> Aplicar no banco real depois (dry-run + aprovação). pytest usa SQLite/metadata.

- [ ] **Step 1: Create the migration**

Create `backend/alembic/versions/0007_os_certificados.py`:

```python
"""certificados.tipo (C/M) + tabela os_certificados

Revision ID: 0007_os_certificados
Revises: 0006_certificados_modelo
Create Date: 2026-06-08
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_os_certificados"
down_revision = "0006_certificados_modelo"
branch_labels = None
depends_on = None


def upgrade():
    # tipo nos modelos de certificado
    op.add_column("certificados", sa.Column("tipo", sa.String(length=1), nullable=False, server_default="C"))
    op.create_check_constraint("certificados_tipo_check", "certificados", "tipo IN ('C','M')")
    # unicidade passa a ser (equipamento, tipo)
    op.drop_constraint("uq_certificados_equipamento", "certificados", type_="unique")
    op.create_unique_constraint("uq_certificados_equipamento_tipo", "certificados", ["equipamento", "tipo"])
    # certificados gerados por OS
    op.create_table(
        "os_certificados",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("os", sa.Integer(), sa.ForeignKey("ordens.id"), nullable=False),
        sa.Column("tipo", sa.String(length=1), nullable=False),
        sa.Column("html", sa.Text(), nullable=True),
        sa.Column("pdf", sa.String(length=50), nullable=True),
        sa.Column("data_geracao", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("tipo IN ('C','M')", name="os_certificados_tipo_check"),
        sa.UniqueConstraint("os", "tipo", name="uq_os_certificados_os_tipo"),
    )


def downgrade():
    op.drop_table("os_certificados")
    op.drop_constraint("uq_certificados_equipamento_tipo", "certificados", type_="unique")
    op.create_unique_constraint("uq_certificados_equipamento", "certificados", ["equipamento"])
    op.drop_constraint("certificados_tipo_check", "certificados", type_="check")
    op.drop_column("certificados", "tipo")
```

- [ ] **Step 2: Sanity**

Run: `cd backend && python -c "import ast; ast.parse(open('alembic/versions/0007_os_certificados.py').read()); print('ok')"`
Run: `cd backend && python -m alembic heads` → `0007_os_certificados (head)`.

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/0007_os_certificados.py
git commit -m "feat(certificados): migração 0007 (tipo C/M + os_certificados, aplicar após aprovação)"
```

---

## Task 2: Modelos — `tipo` em CertificadoModelo + `OSCertificado`

**Files:**
- Modify: `backend/app/models/certificado_modelo.py`
- Create: `backend/app/models/os_certificado.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_os_certificado_model.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_os_certificado_model.py`:

```python
def test_certificado_modelo_tipo_default(db_session):
    from app.models import Equipamento, CertificadoModelo
    eq = Equipamento(descricao="Mark X")
    db_session.add(eq); db_session.flush()
    c = CertificadoModelo(equipamento=eq.id, texto="<p>x</p>")
    db_session.add(c); db_session.commit(); db_session.refresh(c)
    assert c.tipo == "C"


def test_certificado_modelo_dois_tipos(db_session):
    from app.models import Equipamento, CertificadoModelo
    eq = Equipamento(descricao="Mark X")
    db_session.add(eq); db_session.flush()
    db_session.add(CertificadoModelo(equipamento=eq.id, tipo="C", texto="<p>cal</p>"))
    db_session.add(CertificadoModelo(equipamento=eq.id, tipo="M", texto="<p>man</p>"))
    db_session.commit()
    from app.models import CertificadoModelo as CM
    assert db_session.query(CM).filter_by(equipamento=eq.id).count() == 2


def test_os_certificado_model(db_session):
    from app.models import Cliente, Ordem, OSCertificado
    cli = Cliente(nome="C"); db_session.add(cli); db_session.flush()
    o = Ordem(cliente=cli.id, situacao="E"); db_session.add(o); db_session.flush()
    osc = OSCertificado(os=o.id, tipo="C", html="<p>oi</p>")
    db_session.add(osc); db_session.commit(); db_session.refresh(osc)
    assert osc.tipo == "C" and osc.html == "<p>oi</p>"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_os_certificado_model.py -q`
Expected: FAIL.

- [ ] **Step 3: Update `CertificadoModelo`**

Replace `backend/app/models/certificado_modelo.py` with:

```python
from sqlalchemy import Column, Integer, String, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.database import Base


class CertificadoModelo(Base):
    __tablename__ = "certificados"
    __table_args__ = (UniqueConstraint("equipamento", "tipo", name="uq_certificados_equipamento_tipo"),)

    id = Column(Integer, primary_key=True, index=True)
    equipamento = Column(Integer, ForeignKey("equipamentos.id"), nullable=False)
    tipo = Column(String(1), nullable=False, default="C")  # C=Calibração, M=Manutenção
    descricao = Column(String(100), nullable=True)
    texto = Column(Text, nullable=True)

    equipamento_rel = relationship("Equipamento", lazy="joined")

    @property
    def equipamento_descricao(self):
        return self.equipamento_rel.descricao if self.equipamento_rel else None
```

- [ ] **Step 4: Create `OSCertificado`**

Create `backend/app/models/os_certificado.py`:

```python
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, UniqueConstraint
from app.models.database import Base


class OSCertificado(Base):
    __tablename__ = "os_certificados"
    __table_args__ = (UniqueConstraint("os", "tipo", name="uq_os_certificados_os_tipo"),)

    id = Column(Integer, primary_key=True, index=True)
    os = Column(Integer, ForeignKey("ordens.id"), nullable=False)
    tipo = Column(String(1), nullable=False)  # C / M
    html = Column(Text, nullable=True)
    pdf = Column(String(50), nullable=True)
    data_geracao = Column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 5: Register**

In `backend/app/models/__init__.py`, add (after `CertificadoImagem`):

```python
from app.models.os_certificado import OSCertificado
```

and add `"OSCertificado"` to `__all__`.

- [ ] **Step 6: Run tests**

Run: `cd backend && python -m pytest tests/test_os_certificado_model.py -q` → 3 passed.
Run: `cd backend && python -m pytest -q` → tudo verde.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/certificado_modelo.py backend/app/models/os_certificado.py backend/app/models/__init__.py backend/tests/test_os_certificado_model.py
git commit -m "feat(certificados): tipo em CertificadoModelo + modelo OSCertificado"
```

---

## Task 3: Router de modelos por tipo + schemas

**Files:**
- Modify: `backend/app/schemas/certificados_modelo.py`
- Modify: `backend/app/api/certificados_modelo.py`
- Test: `backend/tests/test_certificados_modelo_api.py` (ajustar + novos)

- [ ] **Step 1: Update schemas**

Em `backend/app/schemas/certificados_modelo.py`:
- `ModeloItem`: troque `tem_certificado: bool = False` por:
```python
    tem_calibracao: bool = False
    tem_manutencao: bool = False
```
- `CertificadoModeloOut`: adicione `tipo: str = "C"` (após `equipamento_descricao`).

- [ ] **Step 2: Write/adjust tests**

Substitua o conteúdo de `backend/tests/test_certificados_modelo_api.py` por:

```python
def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _eq(db_session, descricao):
    from app.models import Equipamento
    e = Equipamento(descricao=descricao)
    db_session.add(e); db_session.commit(); db_session.refresh(e)
    return e.id


def test_listar_flags_por_tipo(client, usuario_admin, db_session):
    h = _headers(client, "admin", "senha123")
    e = _eq(db_session, "Mark X")
    client.put(f"/certificados-modelo/{e}?tipo=C", json={"texto": "<p>c</p>"}, headers=h)
    r = client.get("/certificados-modelo", headers=h).json()
    item = next(i for i in r["items"] if i["equipamento"] == e)
    assert item["tem_calibracao"] is True
    assert item["tem_manutencao"] is False


def test_get_put_por_tipo(client, usuario_admin, db_session):
    h = _headers(client, "admin", "senha123")
    e = _eq(db_session, "Iblow")
    client.put(f"/certificados-modelo/{e}?tipo=C", json={"texto": "<p>cal</p>"}, headers=h)
    client.put(f"/certificados-modelo/{e}?tipo=M", json={"texto": "<p>man</p>"}, headers=h)
    assert client.get(f"/certificados-modelo/{e}?tipo=C", headers=h).json()["texto"] == "<p>cal</p>"
    assert client.get(f"/certificados-modelo/{e}?tipo=M", headers=h).json()["texto"] == "<p>man</p>"


def test_tipo_default_c(client, usuario_admin, db_session):
    h = _headers(client, "admin", "senha123")
    e = _eq(db_session, "Def")
    client.put(f"/certificados-modelo/{e}", json={"texto": "<p>x</p>"}, headers=h)  # sem tipo => C
    assert client.get(f"/certificados-modelo/{e}?tipo=C", headers=h).json()["texto"] == "<p>x</p>"
    assert client.get(f"/certificados-modelo/{e}?tipo=M", headers=h).json()["texto"] == ""


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
    assert client.put(f"/certificados-modelo/{e}?tipo=M", json={"texto": "<p>lab</p>"}, headers=h).status_code == 200
```

- [ ] **Step 3: Run tests (fail)**

Run: `cd backend && python -m pytest tests/test_certificados_modelo_api.py -q`
Expected: FAIL.

- [ ] **Step 4: Update the router**

Em `backend/app/api/certificados_modelo.py`, substitua `listar_modelos`, `obter_modelo` e `salvar_modelo` por:

```python
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
    pares = {(row[0], row[1]) for row in db.query(CertificadoModelo.equipamento, CertificadoModelo.tipo).all()}
    items = [
        ModeloItem(
            equipamento=e.id,
            equipamento_descricao=e.descricao,
            tem_calibracao=(e.id, "C") in pares,
            tem_manutencao=(e.id, "M") in pares,
        )
        for e in equipamentos
    ]
    return ModeloPage(items=items)


@router.get("/certificados-modelo/{equipamento_id}", response_model=CertificadoModeloOut)
def obter_modelo(equipamento_id: int, tipo: str = "C", db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    eq = _equipamento_ou_404(db, equipamento_id)
    cert = db.query(CertificadoModelo).filter(
        CertificadoModelo.equipamento == equipamento_id, CertificadoModelo.tipo == tipo
    ).first()
    return CertificadoModeloOut(
        equipamento=eq.id, equipamento_descricao=eq.descricao, tipo=tipo,
        descricao=cert.descricao if cert else None, texto=cert.texto if cert else "",
    )


@router.put("/certificados-modelo/{equipamento_id}", response_model=CertificadoModeloOut)
def salvar_modelo(
    equipamento_id: int,
    dados: CertificadoModeloIn,
    tipo: str = "C",
    db: Session = Depends(get_db),
    _: Usuario = Depends(_escrita),
):
    eq = _equipamento_ou_404(db, equipamento_id)
    cert = db.query(CertificadoModelo).filter(
        CertificadoModelo.equipamento == equipamento_id, CertificadoModelo.tipo == tipo
    ).first()
    if cert is None:
        cert = CertificadoModelo(equipamento=equipamento_id, tipo=tipo)
        db.add(cert)
    cert.texto = dados.texto
    cert.descricao = dados.descricao
    db.commit()
    db.refresh(cert)
    return CertificadoModeloOut(
        equipamento=eq.id, equipamento_descricao=eq.descricao, tipo=cert.tipo,
        descricao=cert.descricao, texto=cert.texto or "",
    )
```

- [ ] **Step 5: Run tests (pass)**

Run: `cd backend && python -m pytest tests/test_certificados_modelo_api.py -q` → 6 passed.
Run: `cd backend && python -m pytest -q` → tudo verde.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/certificados_modelo.py backend/app/api/certificados_modelo.py backend/tests/test_certificados_modelo_api.py
git commit -m "feat(certificados): modelos por tipo (Calibração/Manutenção)"
```

---

## Task 4: Motor de preenchimento `certificado_gerar`

**Files:**
- Create: `backend/app/core/certificado_gerar.py`
- Test: `backend/tests/test_certificado_gerar.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_certificado_gerar.py`:

```python
from datetime import date, datetime, timezone


def test_preencher_substitui_campos():
    from app.core.certificado_gerar import preencher
    html = "Cliente: [nomecli] / Série: [serie] / Temp: [temperatura]"
    out = preencher(html, {"nomecli": "ACME", "serie": "S1", "temperatura": "25"})
    assert out == "Cliente: ACME / Série: S1 / Temp: 25"


def test_preencher_campo_sem_valor_some():
    from app.core.certificado_gerar import preencher
    assert preencher("X[inexistente]Y", {}) == "X[inexistente]Y"  # mantém literal se não no contexto


def test_montar_contexto(db_session):
    from app.models import Cliente, Equipamento, Marca, EquipamentoCliente, Ordem
    from app.core.certificado_gerar import montar_contexto
    marca = Marca(descricao="Alcovisor"); db_session.add(marca); db_session.flush()
    cat = Equipamento(descricao="Mark X", marca=marca.id); db_session.add(cat); db_session.flush()
    cli = Cliente(nome="ACME LTDA", cgc="11222333000144", endereco="Rua A", municipio="SP", estado="SP")
    db_session.add(cli); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=cat.id, serie="SER-9", patrimonio="PAT-9")
    db_session.add(ec); db_session.flush()
    o = Ordem(cliente=cli.id, equipamento_cliente=ec.id, situacao="E",
              calib_cert="C-100", calib_temp="25", calib_pressao="1", calib_teste_media="0,20",
              calib_situacao="Aprovado", data_calibracao=datetime(2026, 6, 8, tzinfo=timezone.utc))
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    ctx = montar_contexto(db_session, o)
    assert ctx["nomecli"] == "ACME LTDA"
    assert ctx["cnpj"] == "11222333000144"
    assert ctx["modelo"] == "Mark X"
    assert ctx["marca"] == "Alcovisor"
    assert ctx["serie"] == "SER-9"
    assert ctx["patrimonio"] == "PAT-9"
    assert ctx["calibcert"] == "C-100"
    assert ctx["temperatura"] == "25"
    assert ctx["media"] == "0,20"
    assert ctx["situacao"] == "Aprovado"
    assert ctx["os"] == str(o.id)
    assert ctx["datacalibracao"] == "08/06/2026"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_certificado_gerar.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

Create `backend/app/core/certificado_gerar.py`:

```python
"""Motor de preenchimento do certificado: monta o contexto a partir da OS e
substitui os campos [token] no HTML do modelo."""
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models import Equipamento, Marca, TipoCalibragem

# Campos suportados (expostos no editor de modelos)
CAMPOS: list[tuple[str, str]] = [
    ("nomecli", "Nome do cliente"),
    ("cnpj", "CNPJ/CPF do cliente"),
    ("endcli", "Endereço do cliente"),
    ("modelo", "Modelo do equipamento"),
    ("marca", "Marca do equipamento"),
    ("serie", "Número de série"),
    ("patrimonio", "Patrimônio"),
    ("datacompra", "Data de compra"),
    ("os", "Número da OS"),
    ("calibcert", "Nº do certificado de calibração"),
    ("datacalibracao", "Data da calibração"),
    ("proxcalibragem", "Próxima calibração"),
    ("tipocalibragem", "Tipo de calibragem"),
    ("temperatura", "Temperatura"),
    ("pressao", "Pressão"),
    ("teste1", "Teste 1"),
    ("teste2", "Teste 2"),
    ("teste3", "Teste 3"),
    ("media", "Média dos testes"),
    ("situacao", "Situação"),
    ("dataemissao", "Data de emissão"),
    ("datacli", "Data (emissão)"),
]


def _fmt(d) -> str:
    if d is None:
        return ""
    if isinstance(d, datetime):
        d = d.date()
    if isinstance(d, date):
        return d.strftime("%d/%m/%Y")
    return str(d)


def _endereco(cli) -> str:
    if cli is None:
        return ""
    partes = [cli.endereco]
    if getattr(cli, "numero", None):
        partes.append(str(cli.numero))
    if getattr(cli, "bairro", None):
        partes.append(cli.bairro)
    cidade = " - ".join(p for p in [getattr(cli, "municipio", None), getattr(cli, "estado", None)] if p)
    if cidade:
        partes.append(cidade)
    return ", ".join(p for p in partes if p)


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
    hoje = _fmt(date.today())
    return {
        "nomecli": (cli.nome if cli else "") or "",
        "cnpj": ((cli.cgc or cli.cpf) if cli else "") or "",
        "endcli": _endereco(cli),
        "modelo": modelo,
        "marca": marca,
        "serie": (ec.serie if ec else "") or "",
        "patrimonio": (ec.patrimonio if ec else "") or "",
        "datacompra": _fmt(ec.datacompra) if ec else "",
        "os": str(ordem.id),
        "calibcert": ordem.calib_cert or "",
        "datacalibracao": _fmt(ordem.data_calibracao),
        "proxcalibragem": _fmt(ordem.prox_calibragem),
        "tipocalibragem": tipocal,
        "temperatura": ordem.calib_temp or "",
        "pressao": ordem.calib_pressao or "",
        "teste1": ordem.calib_teste1 or "",
        "teste2": ordem.calib_teste2 or "",
        "teste3": ordem.calib_teste3 or "",
        "media": ordem.calib_teste_media or "",
        "situacao": ordem.calib_situacao or "",
        "dataemissao": hoje,
        "datacli": hoje,
    }


def preencher(html: str, contexto: dict[str, str]) -> str:
    if not html:
        return html or ""
    for campo, valor in contexto.items():
        html = html.replace(f"[{campo}]", valor or "")
    return html
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_certificado_gerar.py -q` → 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/certificado_gerar.py backend/tests/test_certificado_gerar.py
git commit -m "feat(certificados): motor de preenchimento (contexto + substituição)"
```

---

## Task 5: Geração na OS — helper, endpoints e auto-geração no 5→6

**Files:**
- Modify: `backend/app/core/certificado_gerar.py` (adiciona `gerar_certificados`)
- Create: `backend/app/api/certificados_os.py`
- Modify: `backend/app/main.py` (import + include_router)
- Modify: `backend/app/api/ordens.py` (auto-geração no branch 5→6)
- Test: `backend/tests/test_certificado_os_api.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_certificado_os_api.py`:

```python
def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _os_com_modelo(client, db_session, hadmin, tipos=("C",), tipo_servico="C"):
    from app.models import Cliente, Equipamento, EquipamentoCliente, Ordem, CertificadoModelo
    cat = Equipamento(descricao="Mark X"); db_session.add(cat); db_session.flush()
    cli = Cliente(nome="ACME"); db_session.add(cli); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=cat.id, serie="S1"); db_session.add(ec); db_session.flush()
    o = Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=5, situacao="E",
              tipo_servico=tipo_servico, calib_cert="C-1", calib_temp="25")
    db_session.add(o)
    for t in tipos:
        db_session.add(CertificadoModelo(equipamento=cat.id, tipo=t, texto=f"<p>[nomecli]-[serie]-{t}</p>"))
    db_session.commit(); db_session.refresh(o)
    return o.id


def test_gerar_calibracao(client, usuario_admin, db_session):
    h = _headers(client, "admin", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C",), tipo_servico="C")
    r = client.post(f"/ordens/{oid}/gerar-certificado", headers=h)
    assert r.status_code == 200
    tipos = {c["tipo"]: c for c in r.json()}
    assert "C" in tipos
    assert "ACME-S1-C" in tipos["C"]["html"]
    # GET lista
    lista = client.get(f"/ordens/{oid}/certificados", headers=h).json()
    assert any(c["tipo"] == "C" for c in lista)


def test_gerar_manutencao_quando_servico_M(client, usuario_admin, db_session):
    h = _headers(client, "admin", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C", "M"), tipo_servico="A")
    r = client.post(f"/ordens/{oid}/gerar-certificado", headers=h).json()
    tipos = {c["tipo"] for c in r}
    assert tipos == {"C", "M"}


def test_nao_gera_manutencao_quando_servico_C(client, usuario_admin, db_session):
    h = _headers(client, "admin", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C", "M"), tipo_servico="C")
    r = client.post(f"/ordens/{oid}/gerar-certificado", headers=h).json()
    assert {c["tipo"] for c in r} == {"C"}


def test_sem_modelo_nao_gera_mas_nao_quebra(client, usuario_admin, db_session):
    from app.models import Cliente, Equipamento, EquipamentoCliente, Ordem
    h = _headers(client, "admin", "senha123")
    cat = Equipamento(descricao="X"); db_session.add(cat); db_session.flush()
    cli = Cliente(nome="C"); db_session.add(cli); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=cat.id); db_session.add(ec); db_session.flush()
    o = Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=5, situacao="E", tipo_servico="C")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    r = client.post(f"/ordens/{o.id}/gerar-certificado", headers=h)
    assert r.status_code == 200
    assert r.json() == []


def test_regerar_atualiza_nao_duplica(client, usuario_admin, db_session):
    h = _headers(client, "admin", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C",), tipo_servico="C")
    client.post(f"/ordens/{oid}/gerar-certificado", headers=h)
    client.post(f"/ordens/{oid}/gerar-certificado", headers=h)
    lista = client.get(f"/ordens/{oid}/certificados", headers=h).json()
    assert len([c for c in lista if c["tipo"] == "C"]) == 1


def test_gerar_exige_lab_ou_admin(client, usuario_admin, usuario_comercial, db_session):
    h = _headers(client, "comercial", "senha123")
    oid = _os_com_modelo(client, db_session, _headers(client, "admin", "senha123"), tipos=("C",))
    assert client.post(f"/ordens/{oid}/gerar-certificado", headers=h).status_code == 403


def test_gerar_os_inexistente_404(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    assert client.post("/ordens/99999/gerar-certificado", headers=h).status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_certificado_os_api.py -q`
Expected: FAIL.

- [ ] **Step 3: Add `gerar_certificados` to the engine**

Em `backend/app/core/certificado_gerar.py`, adicione os imports e a função (no final):

```python
from datetime import timezone
from app.models import CertificadoModelo, OSCertificado


def tipos_para(ordem) -> list[str]:
    tipos = ["C"]
    if ordem.tipo_servico in ("M", "A"):
        tipos.append("M")
    return tipos


def gerar_certificados(db: Session, ordem, tipos: list[str]) -> list:
    """Para cada tipo pedido, preenche o modelo do aparelho e upserta em os_certificados.
    Sem modelo p/ o tipo → ignora. Retorna os OSCertificado gerados/atualizados."""
    ec = ordem.equipamento_rel
    if ec is None:
        return []
    contexto = montar_contexto(db, ordem)
    gerados = []
    for tipo in tipos:
        modelo = db.query(CertificadoModelo).filter(
            CertificadoModelo.equipamento == ec.equipamento, CertificadoModelo.tipo == tipo
        ).first()
        if modelo is None or not modelo.texto:
            continue
        html = preencher(modelo.texto, contexto)
        osc = db.query(OSCertificado).filter(
            OSCertificado.os == ordem.id, OSCertificado.tipo == tipo
        ).first()
        if osc is None:
            osc = OSCertificado(os=ordem.id, tipo=tipo)
            db.add(osc)
        osc.html = html
        osc.data_geracao = datetime.now(timezone.utc)
        gerados.append(osc)
    return gerados
```

(O `datetime` já está importado no topo; adicione `timezone` ao import existente `from datetime import date, datetime` → `from datetime import date, datetime, timezone`. Os imports de models podem ficar no topo do arquivo.)

- [ ] **Step 4: Create the endpoints**

Create `backend/app/api/certificados_os.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Ordem, OSCertificado
from app.api.deps import get_current_usuario, require_funcao
from app.core.certificado_gerar import gerar_certificados, tipos_para
from app.schemas.certificados_modelo import OSCertificadoOut

router = APIRouter(tags=["certificados-os"])

_gerar = require_funcao("Laboratório", "Administrador")


def _os_ou_404(db: Session, ordem_id: int) -> Ordem:
    o = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if o is None:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    return o


@router.get("/ordens/{ordem_id}/certificados", response_model=list[OSCertificadoOut])
def listar_os_certificados(ordem_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    _os_ou_404(db, ordem_id)
    cs = db.query(OSCertificado).filter(OSCertificado.os == ordem_id).order_by(OSCertificado.tipo).all()
    return [OSCertificadoOut.model_validate(c) for c in cs]


@router.post("/ordens/{ordem_id}/gerar-certificado", response_model=list[OSCertificadoOut])
def gerar(ordem_id: int, db: Session = Depends(get_db), _: Usuario = Depends(_gerar)):
    ordem = _os_ou_404(db, ordem_id)
    gerados = gerar_certificados(db, ordem, tipos_para(ordem))
    db.commit()
    for g in gerados:
        db.refresh(g)
    return [OSCertificadoOut.model_validate(c) for c in gerados]
```

Adicione `OSCertificadoOut` em `backend/app/schemas/certificados_modelo.py`:

```python
from datetime import datetime


class OSCertificadoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    tipo: str
    html: str | None = None
    pdf: str | None = None
    data_geracao: datetime | None = None
```

- [ ] **Step 5: Register the router**

In `backend/app/main.py`: add `certificados_os` to imports; after `app.include_router(certificados_modelo.router)` add `app.include_router(certificados_os.router)`.

- [ ] **Step 6: Auto-geração no avanço 5→6**

Em `backend/app/api/ordens.py`, no branch `origem == 5` (após `espelhar_calibracao(db, ordem)` e antes de `texto = ...`), adicione:

```python
        try:
            from app.core.certificado_gerar import gerar_certificados, tipos_para
            gerar_certificados(db, ordem, tipos_para(ordem))
        except Exception:
            pass  # best-effort: geração não deve travar o avanço
```

- [ ] **Step 7: Run tests**

Run: `cd backend && python -m pytest tests/test_certificado_os_api.py -q` → 7 passed.
Run: `cd backend && python -m pytest tests/test_ordens_avancar.py -q` → segue verde (auto-geração best-effort).
Run: `cd backend && python -m pytest -q` → tudo verde.

- [ ] **Step 8: Commit**

```bash
git add backend/app/core/certificado_gerar.py backend/app/api/certificados_os.py backend/app/schemas/certificados_modelo.py backend/app/main.py backend/app/api/ordens.py backend/tests/test_certificado_os_api.py
git commit -m "feat(certificados): geração na OS (helper, endpoints, auto no 5→6)"
```

---

## Task 6: Frontend — api (tipo nos modelos + certificados da OS) + campos

**Files:**
- Modify: `frontend/src/app/certificados/api.ts`
- Modify: `frontend/src/app/ordens/api.ts`
- Test: `frontend/src/app/certificados/api.test.ts` (ajustar), `frontend/src/app/ordens/api.certificado.test.ts` (novo)

- [ ] **Step 1: Update `certificados/api.ts`**

- `obterModelo`/`salvarModelo` ganham `tipo` (default 'C') na query string:
```ts
  obterModelo: (equipId: number, tipo: 'C' | 'M' = 'C'): Promise<CertificadoModelo> =>
    apiJson<CertificadoModelo>(`/certificados-modelo/${equipId}?tipo=${tipo}`),
  salvarModelo: (equipId: number, body: { descricao?: string | null; texto: string }, tipo: 'C' | 'M' = 'C'): Promise<CertificadoModelo> =>
    apiJson<CertificadoModelo>(`/certificados-modelo/${equipId}?tipo=${tipo}`, { method: 'PUT', body: JSON.stringify(body) }),
```
- `ModeloItem`: troque `tem_certificado: boolean` por `tem_calibracao: boolean; tem_manutencao: boolean`.
- `CertificadoModelo`: adicione `tipo: 'C' | 'M'`.
- `CAMPOS_CERTIFICADO`: substitua a lista pelos campos completos (os 22 do motor):
```ts
export const CAMPOS_CERTIFICADO: { campo: string; desc: string }[] = [
  { campo: '[nomecli]', desc: 'Nome do cliente' },
  { campo: '[cnpj]', desc: 'CNPJ/CPF do cliente' },
  { campo: '[endcli]', desc: 'Endereço do cliente' },
  { campo: '[modelo]', desc: 'Modelo do equipamento' },
  { campo: '[marca]', desc: 'Marca do equipamento' },
  { campo: '[serie]', desc: 'Número de série' },
  { campo: '[patrimonio]', desc: 'Patrimônio' },
  { campo: '[datacompra]', desc: 'Data de compra' },
  { campo: '[os]', desc: 'Número da OS' },
  { campo: '[calibcert]', desc: 'Nº do certificado' },
  { campo: '[datacalibracao]', desc: 'Data da calibração' },
  { campo: '[proxcalibragem]', desc: 'Próxima calibração' },
  { campo: '[tipocalibragem]', desc: 'Tipo de calibragem' },
  { campo: '[temperatura]', desc: 'Temperatura' },
  { campo: '[pressao]', desc: 'Pressão' },
  { campo: '[teste1]', desc: 'Teste 1' },
  { campo: '[teste2]', desc: 'Teste 2' },
  { campo: '[teste3]', desc: 'Teste 3' },
  { campo: '[media]', desc: 'Média dos testes' },
  { campo: '[situacao]', desc: 'Situação' },
  { campo: '[dataemissao]', desc: 'Data de emissão' },
]
```

- [ ] **Step 2: Update `ordens/api.ts`**

Adicione o tipo e os métodos:
```ts
export interface OSCertificado {
  tipo: 'C' | 'M'
  html: string | null
  pdf: string | null
  data_geracao: string | null
}
```
e em `ordensApi`:
```ts
  certificados: (id: number): Promise<OSCertificado[]> => apiJson<OSCertificado[]>(`/ordens/${id}/certificados`),
  gerarCertificado: (id: number): Promise<OSCertificado[]> =>
    apiJson<OSCertificado[]>(`/ordens/${id}/gerar-certificado`, { method: 'POST' }),
```

- [ ] **Step 3: Tests**

Atualize `frontend/src/app/certificados/api.test.ts`: o teste de `obterModelo`/`salvarModelo` passa a esperar a query `?tipo=C`:
```ts
  it('obterModelo com tipo', async () => {
    await certificadosApi.obterModelo(3, 'C')
    expect(apiJson).toHaveBeenCalledWith('/certificados-modelo/3?tipo=C')
  })
  it('salvarModelo com tipo M', async () => {
    await certificadosApi.salvarModelo(3, { texto: '<p>x</p>' }, 'M')
    expect(apiJson).toHaveBeenCalledWith('/certificados-modelo/3?tipo=M', { method: 'PUT', body: JSON.stringify({ texto: '<p>x</p>' }) })
  })
```
(Remova/ajuste os asserts antigos de `obterModelo(3)`/`salvarModelo` sem tipo para casar com a query `?tipo=C`.)

Crie `frontend/src/app/ordens/api.certificado.test.ts`:
```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
const { apiJson } = vi.hoisted(() => ({ apiJson: vi.fn() }))
vi.mock('../../lib/api', () => ({ apiJson: (...a: unknown[]) => apiJson(...a), apiFetch: vi.fn(), ApiError: class extends Error {} }))
import { ordensApi } from './api'
beforeEach(() => { apiJson.mockReset(); apiJson.mockResolvedValue([]) })
describe('ordensApi certificados', () => {
  it('lista', async () => { await ordensApi.certificados(5); expect(apiJson).toHaveBeenCalledWith('/ordens/5/certificados') })
  it('gera', async () => { await ordensApi.gerarCertificado(5); expect(apiJson).toHaveBeenCalledWith('/ordens/5/gerar-certificado', { method: 'POST' }) })
})
```

- [ ] **Step 4: Run + typecheck**

Run: `cd frontend && npx vitest run src/app/certificados/api.test.ts src/app/ordens/api.certificado.test.ts` → verde.
Run: `cd frontend && npx tsc -b --noEmit` → pode falhar em `ModelosTab.tsx` (usa `tem_certificado`) — será ajustado na Task 7. Se for só lá, prossiga.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/certificados/api.ts frontend/src/app/ordens/api.ts frontend/src/app/certificados/api.test.ts frontend/src/app/ordens/api.certificado.test.ts
git commit -m "feat(certificados): front api por tipo + certificados da OS + campos completos"
```

---

## Task 7: Frontend — editor de modelos por tipo (Calibração/Manutenção)

**Files:**
- Modify: `frontend/src/app/certificados/ModelosTab.tsx`

- [ ] **Step 1: Add tipo toggle + per-tipo flags**

Ajuste `ModelosTab.tsx`:
- A lista usa `tem_calibracao`/`tem_manutencao` (em vez de `tem_certificado`): mostre dois selos pequenos ("Calibração"/"Manutenção") quando presentes, ou "Sem certificado" se nenhum.
- No editor, adicione um estado `tipo: 'C' | 'M'` (default 'C') com um segmented control (dois botões "Calibração" | "Manutenção"); ao trocar o tipo, recarrega via `certificadosApi.obterModelo(equip, tipo)`; ao salvar usa `certificadosApi.salvarModelo(equip, {descricao, texto}, tipo)`.
- Após salvar, atualizar o selo correspondente na lista.

Esboço das partes mudadas (mantendo o resto do componente):
```tsx
// estado
const [tipo, setTipo] = useState<'C' | 'M'>('C')

// ao abrir um modelo OU trocar o tipo:
function carregar(equip: number, t: 'C' | 'M') {
  setCarregandoEd(true); setErro('')
  certificadosApi.obterModelo(equip, t)
    .then((c) => { setTexto(c.texto); setDescricao(c.descricao ?? '') })
    .catch(() => setErro('Falha ao carregar o certificado'))
    .finally(() => setCarregandoEd(false))
}
function abrir(m: ModeloItem) { setSelecionado(m); setTipo('C'); carregar(m.equipamento, 'C') }
function trocarTipo(t: 'C' | 'M') { setTipo(t); if (selecionado) carregar(selecionado.equipamento, t) }

// salvar
await certificadosApi.salvarModelo(selecionado.equipamento, { descricao: descricao.trim() || null, texto }, tipo)
setItens((cur) => cur?.map((m) => m.equipamento === selecionado.equipamento
  ? { ...m, tem_calibracao: tipo === 'C' ? true : m.tem_calibracao, tem_manutencao: tipo === 'M' ? true : m.tem_manutencao }
  : m) ?? null)

// no cabeçalho do editor, segmented control:
<div className="flex gap-1 rounded-lg bg-background-elevated p-1 w-fit">
  {(['C', 'M'] as const).map((t) => (
    <button key={t} type="button" onClick={() => trocarTipo(t)}
      className={'px-3 py-1 text-xs rounded-md ' + (tipo === t ? 'bg-primary text-white' : 'text-slate-400 hover:text-slate-200')}>
      {t === 'C' ? 'Calibração' : 'Manutenção'}
    </button>
  ))}
</div>

// na lista, selos:
{m.tem_calibracao || m.tem_manutencao ? (
  <span className="flex gap-1.5">
    {m.tem_calibracao && <Badge tone="primary">Calibração</Badge>}
    {m.tem_manutencao && <Badge tone="info">Manutenção</Badge>}
  </span>
) : <Badge tone="neutral">Sem certificado</Badge>}
```

- [ ] **Step 2: Verificação**

Run: `cd frontend && npx tsc -b --noEmit && npx eslint src/app/certificados && npm run build` → verde.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/certificados/ModelosTab.tsx
git commit -m "feat(certificados): editor de modelos por tipo (Calibração/Manutenção)"
```

---

## Task 8: Frontend — certificados na OS (seção + impressão)

**Files:**
- Modify: `frontend/src/app/ordens/OrdemDetailPage.tsx`
- Create: `frontend/src/app/ordens/CertificadoImprimir.tsx`
- Modify: `frontend/src/app/routes.tsx` (rota de impressão)

- [ ] **Step 1: Página de impressão** — Create `frontend/src/app/ordens/CertificadoImprimir.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { ordensApi, type OSCertificado } from './api'

export function CertificadoImprimir() {
  const { id, tipo } = useParams()
  const [cert, setCert] = useState<OSCertificado | null | undefined>(undefined)
  useEffect(() => {
    ordensApi.certificados(Number(id))
      .then((cs) => setCert(cs.find((c) => c.tipo === tipo) ?? null))
      .catch(() => setCert(null))
  }, [id, tipo])
  useEffect(() => {
    if (cert?.html) {
      const t = setTimeout(() => window.print(), 400)
      return () => clearTimeout(t)
    }
  }, [cert])
  if (cert === undefined) return <p style={{ padding: 24 }}>Carregando…</p>
  if (!cert || !cert.html) return <p style={{ padding: 24 }}>Certificado não encontrado.</p>
  return <div style={{ background: '#fff', color: '#000' }} dangerouslySetInnerHTML={{ __html: cert.html }} />
}
```

> Esta página é renderizada FORA do layout do app (rota dedicada, fundo branco) só pra imprimir. O HTML é confiável (montado pelo backend a partir do modelo cadastrado por admin/lab), por isso `dangerouslySetInnerHTML` é aceitável aqui.

- [ ] **Step 2: Rota** — em `frontend/src/app/routes.tsx`, importe `CertificadoImprimir` e adicione (dentro do `<Routes>` do app):
```tsx
        <Route path="ordens/:id/certificado/:tipo/imprimir" element={<CertificadoImprimir />} />
```

- [ ] **Step 3: Seção na OS** — em `frontend/src/app/ordens/OrdemDetailPage.tsx`:
- Importe os ícones/`ordensApi` necessários e o tipo `OSCertificado`.
- Adicione estado: `const [certs, setCerts] = useState<OSCertificado[]>([])` e carregue no effect inicial (junto dos outros): `ordensApi.certificados(osId).then(setCerts).catch(() => {})`.
- `podeGerarCert = isAdmin(user) || user?.funcao === 'Laboratório'`.
- Função:
```tsx
async function gerarCertificados() {
  try { const cs = await ordensApi.gerarCertificado(osId); setCerts(cs) }
  catch (e) { setErroCert(e instanceof ApiError ? e.message : 'Falha ao gerar certificado') }
}
```
- Nova `<Secao icon={<IconCertificado .../>} titulo="Certificados" acao={podeGerarCert && <Button onClick={gerarCertificados}>Gerar/Regerar</Button>}>`:
```tsx
{certs.length === 0 ? (
  <p className="text-sm text-slate-500">Nenhum certificado gerado. {podeGerarCert ? 'Clique em "Gerar/Regerar".' : ''}</p>
) : (
  <ul className="space-y-2">
    {certs.map((c) => (
      <li key={c.tipo} className="flex items-center justify-between rounded-lg border border-border px-3 py-2">
        <span className="text-sm text-slate-200">{c.tipo === 'C' ? 'Calibração' : 'Manutenção'}<span className="text-xs text-slate-500 ml-2">{formatData(c.data_geracao)}</span></span>
        <a href={`/app/ordens/${osId}/certificado/${c.tipo}/imprimir`} target="_blank" rel="noopener" className="text-xs font-semibold text-primary hover:underline">Imprimir</a>
      </li>
    ))}
  </ul>
)}
```
> Importe `IconCertificado` de `components/ui/icons`. Use o componente `Secao` já existente no arquivo. `erroCert` já existe no componente.

- [ ] **Step 4: Verificação**

Run: `cd frontend && npx tsc -b --noEmit && npx eslint src/app/ordens && npm run build && npx vitest run` → verde.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/ordens/OrdemDetailPage.tsx frontend/src/app/ordens/CertificadoImprimir.tsx frontend/src/app/routes.tsx
git commit -m "feat(certificados): seção de certificados na OS + página de impressão"
```

---

## Task 9: Changelog v1.4.0 + aplicar migração + E2E + memória

**Files:**
- Modify: `frontend/src/app/changelog/data.ts`

- [ ] **Step 1: Changelog** — no topo do `CHANGELOG`:
```ts
  {
    versao: '1.4.0',
    data: '08/06/2026',
    itens: [
      { tipo: 'novidade', texto: 'Certificado gerado automaticamente no laboratório — ao concluir o laboratório, o sistema preenche o modelo do aparelho com os dados reais (cliente, série, resultados da calibração) e gera o certificado de calibração (e o de manutenção, quando houver). Dá para imprimir/salvar em PDF pela OS.' },
    ],
  },
```

- [ ] **Step 2: Validar + commit**

Run: `cd frontend && npx vitest run src/app/changelog/ && npx tsc -b --noEmit && npm run build` → verde.
```bash
git add frontend/src/app/changelog/data.ts
git commit -m "feat(changelog): v1.4.0 — certificado gerado no laboratório"
```

- [ ] **Step 3: Aplicar a migração 0007 no banco real** (com o usuário)

> Dry-run: `docker compose exec backend alembic upgrade 0006_certificados_modelo:0007_os_certificados --sql` (mostrar). Após ok: `docker compose exec backend alembic upgrade head`. Verificar `certificados.tipo` (12 = 'C'), unique (equipamento,tipo), e `os_certificados` criada.

- [ ] **Step 4: E2E manual** — login admin; abrir uma OS na fase Laboratório (5); "Concluir laboratório" com dados de calibração → conferir no detalhe a seção "Certificados" com o de Calibração gerado → "Imprimir" (abre página branca com o HTML preenchido e diálogo de impressão). Cadastrar um modelo de Manutenção para um aparelho e testar uma OS de Manutenção/Ambas → dois certificados. Botão "Gerar/Regerar" regenera.

- [ ] **Step 5: Memória** — atualizar `project_gestorhs.md`: geração de certificado no laboratório (tipo C/M, os_certificados, motor de preenchimento, auto no 5→6 + regerar, impressão no navegador, v1.4.0); próxima etapa = PDF no servidor.

---

## Self-Review

**Cobertura da spec:** migração 0007 tipo+os_certificados (Task 1); modelos tipo+OSCertificado (Task 2); router modelos por tipo (Task 3); motor preencher+contexto+CAMPOS (Task 4); gerar_certificados + endpoints + auto 5→6 (Task 5); front api por tipo + certificados OS + campos (Task 6); editor por tipo (Task 7); seção OS + impressão (Task 8); changelog + migração + E2E + memória (Task 9). PDF no servidor explicitamente fora. ✓

**Placeholders:** nenhum; trechos de UI têm esboços completos com as partes mudadas + nota de onde encaixam.

**Consistência de tipos/nomes:** backend `CertificadoModelo.tipo`, `OSCertificado{os,tipo,html,pdf,data_geracao}`, `certificado_gerar.{CAMPOS,montar_contexto,preencher,gerar_certificados,tipos_para}`, schemas `ModeloItem{tem_calibracao,tem_manutencao}`/`CertificadoModeloOut{tipo}`/`OSCertificadoOut`; rotas `/certificados-modelo?tipo=`, `/ordens/{id}/certificados`, `/ordens/{id}/gerar-certificado`; front `certificadosApi.{obterModelo,salvarModelo}(…, tipo)`, `ordensApi.{certificados,gerarCertificado}`, tipo `OSCertificado`, rota de impressão `ordens/:id/certificado/:tipo/imprimir`. Consistentes. ✓
- Auto-geração best-effort no 5→6 não derruba o avanço (try/except). ✓
