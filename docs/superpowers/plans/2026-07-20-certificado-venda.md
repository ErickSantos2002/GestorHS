# Certificado de venda — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emitir o primeiro certificado de um aparelho — o da venda — sem abrir OS, vinculado ao aparelho da frota do cliente.

**Architecture:** Tabela nova `certificados_venda` com FK + unique em `equipamento_cliente` (um por aparelho, regerável por upsert). Reusa o motor de certificado existente (`_montar_contexto`, `preencher`, `html_para_pdf`) e o espelhamento de calibração na frota, ambos extraídos para aceitar valores soltos em vez de uma OS. No front, o formulário do modal da OS é extraído para um componente compartilhado.

**Tech Stack:** Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · pytest (SQLite in-memory) · React 19 · TS · Vite 8 · Tailwind v4 · Vitest + Testing Library

**Spec:** [docs/superpowers/specs/2026-07-20-certificado-venda-design.md](../specs/2026-07-20-certificado-venda-design.md)

## Global Constraints

- Idioma do domínio é **PT-BR**: modelos, rotas, variáveis e mensagens em português.
- Mensagens de **commit** em português **sem acentos** (ASCII), uma linha, sem corpo e sem trailer de co-autor. Formato: `tipo(escopo): descricao curta no imperativo`.
- Lógica de negócio pura vai em `backend/app/core/` (sem I/O).
- Todo router novo precisa de `include_router` manual em `backend/app/main.py`.
- Regra de função gateada no backend por `require_funcao(...)` **e** espelhada em `frontend/src/auth/roles.ts` — sempre os dois lados.
- Isolamento de tenant no portal é **pelo token** (`cli.cliente`), **nunca** por parâmetro de URL.
- Tipo do certificado de venda é sempre `"C"` (Calibração).
- Backend: rodar `pytest -q` de `backend/` com a venv ativa (`source .venv/bin/activate`).
- Frontend: verificação completa é `npm run lint && npx tsc -b --noEmit && npm run build`.
- Nunca fazer `git push` — só commits locais.

---

### Task 1: Modelo e migração `certificados_venda`

**Files:**
- Create: `backend/app/models/certificado_venda.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/0017_certificado_venda.py`
- Test: `backend/tests/test_certificado_venda_model.py`

**Interfaces:**
- Consumes: nada (primeira task).
- Produces: `CertificadoVenda` (importável de `app.models`) com colunas `id`, `equipamento_cliente`, `html`, `calib_cert`, `data_calibracao`, `usuario`, `data_geracao`; unique constraint `uq_certificados_venda_equip` em `equipamento_cliente`; property `usuario_nome -> str | None`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_certificado_venda_model.py`:

```python
import pytest
from sqlalchemy.exc import IntegrityError


def _aparelho(db_session):
    from app.models import Cliente, Equipamento, EquipamentoCliente
    cli = Cliente(nome="ACME"); eq = Equipamento(descricao="Mark X")
    db_session.add_all([cli, eq]); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie="S1")
    db_session.add(ec); db_session.commit(); db_session.refresh(ec)
    return ec


def test_grava_e_le_certificado_de_venda(db_session, usuario_lab):
    from datetime import date
    from app.models import CertificadoVenda
    ec = _aparelho(db_session)
    cv = CertificadoVenda(
        equipamento_cliente=ec.id, html="<p>ok</p>", calib_cert="V-001",
        data_calibracao=date(2026, 7, 20), usuario=usuario_lab.id,
    )
    db_session.add(cv); db_session.commit(); db_session.refresh(cv)
    assert cv.id is not None
    assert cv.calib_cert == "V-001"
    assert cv.usuario_nome == "Lab"


def test_um_certificado_de_venda_por_aparelho(db_session):
    from app.models import CertificadoVenda
    ec = _aparelho(db_session)
    db_session.add(CertificadoVenda(equipamento_cliente=ec.id, html="<p>a</p>"))
    db_session.commit()
    db_session.add(CertificadoVenda(equipamento_cliente=ec.id, html="<p>b</p>"))
    with pytest.raises(IntegrityError):
        db_session.commit()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_certificado_venda_model.py -q`
Expected: FAIL — `ImportError: cannot import name 'CertificadoVenda' from 'app.models'`

- [ ] **Step 3: Write the model**

Create `backend/app/models/certificado_venda.py`:

```python
from sqlalchemy import (Column, Integer, String, Text, Date, DateTime,
                        ForeignKey, UniqueConstraint)
from sqlalchemy.orm import relationship

from app.models.database import Base


class CertificadoVenda(Base):
    """Primeiro certificado do aparelho, emitido na VENDA — sem OS.

    Diferente de CertificadoAvulso (sem vinculo nenhum, para aparelho de POC), este e
    ancorado no aparelho da frota do cliente. O unique em equipamento_cliente garante
    "um por aparelho" no banco: regerar e um upsert, nao uma duplicata.

    Nao ha coluna `tipo`: certificado de venda e sempre de calibracao ("C").
    """
    __tablename__ = "certificados_venda"
    __table_args__ = (
        UniqueConstraint("equipamento_cliente", name="uq_certificados_venda_equip"),
    )

    id = Column(Integer, primary_key=True, index=True)
    equipamento_cliente = Column(Integer, ForeignKey("equipamentos_cliente.id"), nullable=False)
    html = Column(Text, nullable=False)               # certificado preenchido, auto-contido
    calib_cert = Column(String(50), nullable=True)    # so para a listagem
    data_calibracao = Column(Date, nullable=True)     # so para a listagem
    usuario = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    data_geracao = Column(DateTime(timezone=True), nullable=True)

    usuario_rel = relationship("Usuario", lazy="joined")

    @property
    def usuario_nome(self):
        return self.usuario_rel.nome if self.usuario_rel else None
```

- [ ] **Step 4: Register the model**

In `backend/app/models/__init__.py`, next to the existing `from app.models.certificado_avulso import CertificadoAvulso` line, add:

```python
from app.models.certificado_venda import CertificadoVenda
```

If the file has an `__all__` list, add `"CertificadoVenda"` to it as well.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_certificado_venda_model.py -q`
Expected: PASS (2 passed)

- [ ] **Step 6: Write the migration**

Create `backend/alembic/versions/0017_certificado_venda.py`:

```python
"""certificado de venda: primeiro certificado do aparelho, sem OS"""
import sqlalchemy as sa
from alembic import op

revision = "0017_certificado_venda"
down_revision = "0016_instalacao_modulo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "certificados_venda",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("equipamento_cliente", sa.Integer(), nullable=False),
        sa.Column("html", sa.Text(), nullable=False),
        sa.Column("calib_cert", sa.String(length=50), nullable=True),
        sa.Column("data_calibracao", sa.Date(), nullable=True),
        sa.Column("usuario", sa.Integer(), nullable=True),
        sa.Column("data_geracao", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["equipamento_cliente"], ["equipamentos_cliente.id"]),
        sa.ForeignKeyConstraint(["usuario"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("equipamento_cliente", name="uq_certificados_venda_equip"),
    )
    op.create_index(op.f("ix_certificados_venda_id"), "certificados_venda", ["id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_certificados_venda_id"), table_name="certificados_venda")
    op.drop_table("certificados_venda")
```

- [ ] **Step 7: Verify the migration chain is linear**

Run: `cd backend && source .venv/bin/activate && alembic heads`
Expected: uma única head — `0017_certificado_venda`. Se aparecer mais de uma, o `down_revision` está errado; corrija antes de seguir.

- [ ] **Step 8: Run the full backend suite**

Run: `cd backend && source .venv/bin/activate && pytest -q`
Expected: PASS — nenhum teste existente quebra (a task só acrescenta tabela).

- [ ] **Step 9: Commit**

```bash
git add backend/app/models/certificado_venda.py backend/app/models/__init__.py \
        backend/alembic/versions/0017_certificado_venda.py \
        backend/tests/test_certificado_venda_model.py
git commit -m "feat(cert): modelo e migracao do certificado de venda"
```

---

### Task 2: `montar_contexto_venda` no motor de certificado

**Files:**
- Modify: `backend/app/core/certificado_gerar.py`
- Test: `backend/tests/test_certificado_contexto_venda.py`

**Interfaces:**
- Consumes: `_montar_contexto(...)`, `modelo_marca(db, equipamento_id)`, `_endereco(cli)`, `_fmt(d)` — todos já existentes em `app/core/certificado_gerar.py`.
- Produces: `montar_contexto_venda(db: Session, ec, valores: dict) -> dict[str, str]`, onde `ec` é um `EquipamentoCliente` e `valores` é um dict com as chaves `nomecli`, `cnpj`, `endcli`, `serie`, `patrimonio`, `datacompra`, `calib_cert`, `data_calibracao`, `prox_calibragem`, `calib_temp`, `calib_pressao`, `calib_teste1`, `calib_teste2`, `calib_teste3`, `calib_teste_media`, `calib_situacao`.

**Por que delegar a `_montar_contexto` é obrigatório:** `preencher()` substitui **apenas** as chaves presentes no contexto — um token ausente sai **literalmente escrito no PDF** (`preencher("<p>[a] [b]</p>", {"a": "X"})` → `"<p>X [b]</p>"`). Montar um dict próprio criaria a terceira lista paralela de chaves e um token novo entraria só em um caminho.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_certificado_contexto_venda.py`:

```python
from datetime import date


def _aparelho(db_session):
    from app.models import Cliente, Equipamento, EquipamentoCliente, Marca
    m = Marca(descricao="Alcoscan")
    db_session.add(m); db_session.flush()
    cli = Cliente(nome="ACME Ltda", cgc="11222333000144",
                  endereco="Rua X", numero=10, bairro="Centro",
                  municipio="Recife", estado="PE")
    eq = Equipamento(descricao="Mark X", marca=m.id)
    db_session.add_all([cli, eq]); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie="S1",
                            patrimonio="P1", datacompra=date(2026, 1, 5))
    db_session.add(ec); db_session.commit(); db_session.refresh(ec)
    return ec


def _valores(**kw):
    base = {
        "calib_cert": "V-001", "data_calibracao": date(2026, 7, 20),
        "prox_calibragem": date(2027, 7, 20),
        "calib_temp": "22", "calib_pressao": "1013",
        "calib_teste1": "0,10", "calib_teste2": "0,11", "calib_teste3": "0,12",
        "calib_teste_media": "0,11", "calib_situacao": "Aparelho inicial",
    }
    base.update(kw)
    return base


def test_contexto_venda_tem_o_mesmo_conjunto_de_chaves_da_os(db_session):
    """Blindagem contra token vazando como [token] no PDF."""
    from app.core.certificado_gerar import montar_contexto_venda, _montar_contexto
    ec = _aparelho(db_session)
    ctx = montar_contexto_venda(db_session, ec, _valores())
    assert set(ctx.keys()) == set(_montar_contexto().keys())


def test_contexto_venda_puxa_cliente_e_aparelho_do_cadastro(db_session):
    from app.core.certificado_gerar import montar_contexto_venda
    ec = _aparelho(db_session)
    ctx = montar_contexto_venda(db_session, ec, _valores())
    assert ctx["nomecli"] == "ACME Ltda"
    assert ctx["cnpj"] == "11222333000144"
    assert "Rua X" in ctx["endcli"] and "Recife" in ctx["endcli"]
    assert ctx["modelo"] == "Mark X"
    assert ctx["marca"] == "Alcoscan"
    assert ctx["serie"] == "S1"
    assert ctx["patrimonio"] == "P1"
    assert ctx["datacompra"] == "05/01/2026"


def test_contexto_venda_usa_XXXX_como_numero_de_os(db_session):
    """Nao ha OS: mesma convencao ja usada no certificado avulso."""
    from app.core.certificado_gerar import montar_contexto_venda
    ec = _aparelho(db_session)
    ctx = montar_contexto_venda(db_session, ec, _valores())
    assert ctx["os"] == "XXXX"


def test_contexto_venda_dataentr_cai_na_data_de_compra(db_session):
    from app.core.certificado_gerar import montar_contexto_venda
    ec = _aparelho(db_session)
    ctx = montar_contexto_venda(db_session, ec, _valores())
    assert ctx["dataentr"] == "05/01/2026"


def test_contexto_venda_dataentr_cai_em_hoje_sem_data_de_compra(db_session):
    from app.core.certificado_gerar import montar_contexto_venda
    ec = _aparelho(db_session)
    ec.datacompra = None
    db_session.commit()
    ctx = montar_contexto_venda(db_session, ec, _valores())
    assert ctx["dataentr"] == date.today().strftime("%d/%m/%Y")


def test_contexto_venda_preenche_proxima_calibragem(db_session):
    from app.core.certificado_gerar import montar_contexto_venda
    ec = _aparelho(db_session)
    ctx = montar_contexto_venda(db_session, ec, _valores())
    assert ctx["proxcalibragem"] == "20/07/2027"


def test_contexto_venda_valores_do_modal_sobrepoem_o_cadastro(db_session):
    """O laboratorio pode corrigir serie/patrimonio na hora de gerar."""
    from app.core.certificado_gerar import montar_contexto_venda
    ec = _aparelho(db_session)
    ctx = montar_contexto_venda(db_session, ec, _valores(serie="S1-CORRIGIDA",
                                                         nomecli="ACME Filial"))
    assert ctx["serie"] == "S1-CORRIGIDA"
    assert ctx["nomecli"] == "ACME Filial"


def test_nenhum_token_vaza_no_html_de_venda(db_session):
    """Template usando TODOS os tokens nao pode deixar nenhum [token] literal."""
    from app.core.certificado_gerar import CAMPOS, montar_contexto_venda, preencher
    ec = _aparelho(db_session)
    template = " ".join(f"[{nome}]" for nome, _ in CAMPOS)
    html = preencher(template, montar_contexto_venda(db_session, ec, _valores()))
    assert "[" not in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_certificado_contexto_venda.py -q`
Expected: FAIL — `ImportError: cannot import name 'montar_contexto_venda'`

- [ ] **Step 3: Implement `montar_contexto_venda`**

In `backend/app/core/certificado_gerar.py`, add right after the existing `montar_contexto_avulso` function:

```python
def montar_contexto_venda(db: Session, ec, valores: dict) -> dict[str, str]:
    """Contexto do certificado de VENDA: sem OS, mas com o aparelho ja cadastrado.

    Cliente e aparelho saem do cadastro; `valores` (o que o laboratorio digitou no
    modal) sobrepoe o que for informado, permitindo corrigir na hora sem alterar o
    cadastro. `modelo`/`marca` vem sempre do catalogo — sao atributo do aparelho.

    Delega ao mesmo `_montar_contexto` da OS e do avulso: e o que garante que o
    conjunto de chaves seja identico e nenhum token vaze como [token] no PDF.
    """
    cli = ec.cliente_rel
    modelo, marca = modelo_marca(db, ec.equipamento)

    def _v(chave, padrao=""):
        valor = valores.get(chave)
        return valor if valor not in (None, "") else padrao

    # Nao ha "data de recebimento" numa venda: usa a data de compra do cadastro,
    # caindo em hoje quando o cadastro nao tem.
    dataentr = _fmt(ec.datacompra) if ec.datacompra else _fmt(date.today())

    return _montar_contexto(
        nomecli=_v("nomecli", (cli.nome if cli else "") or ""),
        cnpj=_v("cnpj", ((cli.cgc or cli.cpf) if cli else "") or ""),
        endcli=_v("endcli", _endereco(cli)),
        modelo=modelo,
        marca=marca,
        serie=_v("serie", ec.serie or ""),
        patrimonio=_v("patrimonio", ec.patrimonio or ""),
        datacompra=_fmt(valores.get("datacompra")) or _fmt(ec.datacompra),
        os_num="XXXX",                       # sem OS — convencao ja usada no avulso
        calibcert=_v("calib_cert"),
        proxcalibragem=_fmt(valores.get("prox_calibragem")),
        tipocalibragem="",                   # nao se aplica a uma venda
        datacali=_fmt(valores.get("data_calibracao")),
        dataentr=dataentr,
        temp=_v("calib_temp"),
        pressao=_v("calib_pressao"),
        t1=_v("calib_teste1"),
        t2=_v("calib_teste2"),
        t3=_v("calib_teste3"),
        media=_v("calib_teste_media"),
        situ=_v("calib_situacao"),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_certificado_contexto_venda.py -q`
Expected: PASS (8 passed)

- [ ] **Step 5: Run the full backend suite**

Run: `cd backend && source .venv/bin/activate && pytest -q`
Expected: PASS — em especial `tests/test_certificado_contexto.py` e `tests/test_certificado_gerar.py` seguem verdes (a task só acrescenta função).

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/certificado_gerar.py backend/tests/test_certificado_contexto_venda.py
git commit -m "feat(cert): contexto do certificado de venda reusando a fonte unica de tokens"
```

---

### Task 3: Espelhamento de calibração a partir de valores soltos

**Files:**
- Modify: `backend/app/api/ordens_acoes.py:34-49`
- Test: `backend/tests/test_espelhar_calibracao_valores.py`

**Interfaces:**
- Consumes: `EquipamentoCliente` (`app.models`).
- Produces: `espelhar_calibracao_valores(db: Session, ec, valores: dict, ult: date | None, prox: date | None) -> None` em `app/api/ordens_acoes.py`, onde `valores` usa as chaves `calib_cert`, `calib_temp`, `calib_pressao`, `calib_teste1`, `calib_teste2`, `calib_teste3`, `calib_teste_media`, `calib_situacao`. `espelhar_calibracao(db, ordem)` mantém a assinatura e o comportamento atuais.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_espelhar_calibracao_valores.py`:

```python
from datetime import date, datetime, timezone


def _aparelho(db_session):
    from app.models import Cliente, Equipamento, EquipamentoCliente
    cli = Cliente(nome="ACME"); eq = Equipamento(descricao="Mark X")
    db_session.add_all([cli, eq]); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie="S1")
    db_session.add(ec); db_session.commit(); db_session.refresh(ec)
    return ec


def test_espelha_valores_soltos_no_aparelho(db_session):
    from app.api.ordens_acoes import espelhar_calibracao_valores
    ec = _aparelho(db_session)
    espelhar_calibracao_valores(
        db_session, ec,
        {"calib_cert": "V-001", "calib_temp": "22", "calib_pressao": "1013",
         "calib_teste1": "0,10", "calib_teste2": "0,11", "calib_teste3": "0,12",
         "calib_teste_media": "0,11", "calib_situacao": "Aparelho inicial"},
        ult=date(2026, 7, 20), prox=date(2027, 7, 20),
    )
    db_session.commit(); db_session.refresh(ec)
    assert ec.calib_cert == "V-001"
    assert ec.calib_situacao == "Aparelho inicial"
    assert ec.calib_teste_media == "0,11"
    assert ec.ult_calibragem == date(2026, 7, 20)
    assert ec.prox_calibragem == date(2027, 7, 20)


def test_valor_ausente_nao_apaga_o_que_ja_havia(db_session):
    from app.api.ordens_acoes import espelhar_calibracao_valores
    ec = _aparelho(db_session)
    ec.calib_temp = "20"
    db_session.commit()
    espelhar_calibracao_valores(db_session, ec, {"calib_cert": "V-002"},
                                ult=None, prox=None)
    db_session.commit(); db_session.refresh(ec)
    assert ec.calib_cert == "V-002"
    assert ec.calib_temp == "20"      # preservado


def test_espelhar_calibracao_da_os_continua_igual(db_session):
    """Regressao: o caminho da OS nao pode mudar de comportamento."""
    from app.api.ordens_acoes import espelhar_calibracao
    from app.models import Ordem
    ec = _aparelho(db_session)
    ordem = Ordem(cliente=ec.cliente, equipamento_cliente=ec.id, situacao="E",
                  tipo_servico="C", fase=5,
                  calib_cert="OS-9", calib_temp="21", calib_situacao="Aparelho subsequente",
                  data_calibracao=datetime(2026, 7, 20, tzinfo=timezone.utc),
                  prox_calibragem=datetime(2027, 7, 20, tzinfo=timezone.utc))
    db_session.add(ordem); db_session.commit()
    espelhar_calibracao(db_session, ordem)
    db_session.commit(); db_session.refresh(ec)
    assert ec.calib_cert == "OS-9"
    assert ec.calib_temp == "21"
    assert ec.ult_calibragem == date(2026, 7, 20)
    assert ec.prox_calibragem == date(2027, 7, 20)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_espelhar_calibracao_valores.py -q`
Expected: FAIL — `ImportError: cannot import name 'espelhar_calibracao_valores'`

- [ ] **Step 3: Extract the shared function**

In `backend/app/api/ordens_acoes.py`, replace the whole existing `espelhar_calibracao` function (currently at lines 34-49) with:

```python
def espelhar_calibracao_valores(db: Session, ec, valores: dict,
                                ult=None, prox=None) -> None:
    """Copia resultados de calibracao para o equipamento_cliente a partir de valores soltos.

    Miolo compartilhado entre o fluxo da OS (`espelhar_calibracao`) e o certificado de
    venda, que nao tem OS. Valor ausente/None NAO apaga o que ja existe no cadastro.
    """
    for campo in _CAMPOS_CALIB:
        valor = valores.get(campo)
        if valor is not None:
            setattr(ec, campo, valor)
    if ult is not None:
        ec.ult_calibragem = ult
    if prox is not None:
        ec.prox_calibragem = prox


def espelhar_calibracao(db: Session, ordem) -> None:
    """Copia os resultados de calibração da OS para o equipamento_cliente."""
    from app.models import EquipamentoCliente
    if not ordem.equipamento_cliente:
        return
    ec = db.query(EquipamentoCliente).filter(EquipamentoCliente.id == ordem.equipamento_cliente).first()
    if ec is None:
        return
    espelhar_calibracao_valores(
        db, ec,
        {campo: getattr(ordem, campo) for campo in _CAMPOS_CALIB},
        ult=ordem.data_calibracao.date() if ordem.data_calibracao is not None else None,
        prox=ordem.prox_calibragem.date() if ordem.prox_calibragem is not None else None,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_espelhar_calibracao_valores.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Run the full backend suite (regression gate)**

Run: `cd backend && source .venv/bin/activate && pytest -q`
Expected: PASS — esta é a task de maior risco de regressão, porque mexe no fluxo de OS já em produção. Se qualquer teste de OS falhar, o wrapper divergiu do original; corrija antes de commitar.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/ordens_acoes.py backend/tests/test_espelhar_calibracao_valores.py
git commit -m "refactor(cert): extrai espelhamento de calibracao para aceitar valores soltos"
```

---

### Task 4: Endpoints do certificado de venda

**Files:**
- Create: `backend/app/schemas/certificado_venda.py`
- Create: `backend/app/api/certificados_venda.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_certificado_venda_api.py`

**Interfaces:**
- Consumes: `CertificadoVenda` (Task 1), `montar_contexto_venda` (Task 2), `espelhar_calibracao_valores` (Task 3), `preencher` e `html_para_pdf` (existentes).
- Produces: rotas `GET /equipamentos-cliente/{id}/certificado-venda-campos`, `POST /equipamentos-cliente/{id}/certificado-venda`, `GET /equipamentos-cliente/{id}/certificado-venda/pdf`. Schemas `CertificadoVendaCamposOut`, `CertificadoVendaIn`, `CertificadoVendaOut`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_certificado_venda_api.py`:

```python
from datetime import date


def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _modelo(db_session, equipamento_id, texto="<p>[nomecli] | [serie] | [calibcert] | [os] | [proxcalibragem]</p>"):
    from app.models import CertificadoModelo
    db_session.add(CertificadoModelo(equipamento=equipamento_id, tipo="C", texto=texto))
    db_session.commit()


def _payload(**kw):
    base = {
        "calib_cert": "V-001",
        "data_calibracao": "2026-07-20",
        "prox_calibragem": "2027-07-20",
        "calib_temp": "22", "calib_pressao": "1013",
        "calib_teste1": "0,10", "calib_teste2": "0,11", "calib_teste3": "0,12",
        "calib_teste_media": "0,11", "calib_situacao": "Aparelho inicial",
    }
    base.update(kw)
    return base


def test_campos_vem_preenchidos_do_cadastro(client, usuario_lab, os_base, db_session):
    h = _headers(client, "lab@hs.com", "senha123")
    r = client.get(f"/equipamentos-cliente/{os_base['equipamento_cliente']}/certificado-venda-campos", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["nomecli"] == "Cliente OS"
    assert body["serie"] == "SER-1"
    assert body["patrimonio"] == "PAT-1"
    assert body["calib_situacao"] == "Aparelho inicial"     # default da venda
    assert body["data_calibracao"] == date.today().isoformat()


def test_gerar_salva_preenche_o_html_e_espelha_na_frota(client, usuario_lab, os_base, db_session):
    _modelo(db_session, os_base["equipamento"])
    h = _headers(client, "lab@hs.com", "senha123")
    r = client.post(f"/equipamentos-cliente/{os_base['equipamento_cliente']}/certificado-venda",
                    json=_payload(), headers=h)
    assert r.status_code == 201
    body = r.json()
    assert body["calib_cert"] == "V-001"

    from app.models import CertificadoVenda, EquipamentoCliente
    cv = db_session.query(CertificadoVenda).filter(
        CertificadoVenda.equipamento_cliente == os_base["equipamento_cliente"]).first()
    assert "Cliente OS" in cv.html and "SER-1" in cv.html and "XXXX" in cv.html
    assert "[" not in cv.html                     # nenhum token vazou
    assert cv.usuario == usuario_lab.id
    assert cv.data_geracao is not None

    ec = db_session.get(EquipamentoCliente, os_base["equipamento_cliente"])
    db_session.refresh(ec)
    assert ec.calib_cert == "V-001"
    assert ec.ult_calibragem == date(2026, 7, 20)
    assert ec.prox_calibragem == date(2027, 7, 20)


def test_regerar_sobrescreve_e_nao_duplica(client, usuario_lab, os_base, db_session):
    _modelo(db_session, os_base["equipamento"])
    h = _headers(client, "lab@hs.com", "senha123")
    url = f"/equipamentos-cliente/{os_base['equipamento_cliente']}/certificado-venda"
    assert client.post(url, json=_payload(), headers=h).status_code == 201
    r = client.post(url, json=_payload(calib_cert="V-002"), headers=h)
    assert r.status_code == 201

    from app.models import CertificadoVenda
    todos = db_session.query(CertificadoVenda).filter(
        CertificadoVenda.equipamento_cliente == os_base["equipamento_cliente"]).all()
    assert len(todos) == 1
    db_session.refresh(todos[0])
    assert todos[0].calib_cert == "V-002"


def test_aparelho_sem_modelo_de_certificado_409(client, usuario_lab, os_base):
    h = _headers(client, "lab@hs.com", "senha123")
    r = client.post(f"/equipamentos-cliente/{os_base['equipamento_cliente']}/certificado-venda",
                    json=_payload(), headers=h)
    assert r.status_code == 409
    assert "modelo de certificado" in r.json()["detail"]


def test_admin_pode_gerar(client, usuario_admin, os_base, db_session):
    _modelo(db_session, os_base["equipamento"])
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.post(f"/equipamentos-cliente/{os_base['equipamento_cliente']}/certificado-venda",
                    json=_payload(), headers=h)
    assert r.status_code == 201


def test_comercial_nao_pode_gerar(client, usuario_comercial, os_base, db_session):
    _modelo(db_session, os_base["equipamento"])
    h = _headers(client, "comercial@hs.com", "senha123")
    r = client.post(f"/equipamentos-cliente/{os_base['equipamento_cliente']}/certificado-venda",
                    json=_payload(), headers=h)
    assert r.status_code == 403


def test_aparelho_inexistente_404(client, usuario_lab):
    h = _headers(client, "lab@hs.com", "senha123")
    assert client.get("/equipamentos-cliente/99999/certificado-venda-campos", headers=h).status_code == 404
    assert client.post("/equipamentos-cliente/99999/certificado-venda", json=_payload(), headers=h).status_code == 404


def test_pdf_baixa_e_404_sem_certificado(client, usuario_lab, os_base, db_session):
    h = _headers(client, "lab@hs.com", "senha123")
    url = f"/equipamentos-cliente/{os_base['equipamento_cliente']}/certificado-venda/pdf"
    assert client.get(url, headers=h).status_code == 404
    _modelo(db_session, os_base["equipamento"])
    client.post(f"/equipamentos-cliente/{os_base['equipamento_cliente']}/certificado-venda",
                json=_payload(), headers=h)
    r = client.get(url, headers=h)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"


def test_gerar_nao_cria_nem_altera_nenhuma_os(client, usuario_lab, os_base, db_session):
    """O ponto da feature: certificado de venda existe SEM OS."""
    _modelo(db_session, os_base["equipamento"])
    h = _headers(client, "lab@hs.com", "senha123")
    client.post(f"/equipamentos-cliente/{os_base['equipamento_cliente']}/certificado-venda",
                json=_payload(), headers=h)
    from app.models import Ordem, EquipamentoCliente
    assert db_session.query(Ordem).count() == 0
    ec = db_session.get(EquipamentoCliente, os_base["equipamento_cliente"])
    assert ec.os_atual is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_certificado_venda_api.py -q`
Expected: FAIL — todas as rotas devolvem 404 (router não existe).

- [ ] **Step 3: Write the schemas**

Create `backend/app/schemas/certificado_venda.py`:

```python
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CertificadoVendaCamposOut(BaseModel):
    """Campos ja preenchidos para o modal: cliente e aparelho vem do cadastro."""
    nomecli: str = ""
    cnpj: str = ""
    endcli: str = ""
    modelo: str = ""
    marca: str = ""
    serie: str = ""
    patrimonio: str = ""
    datacompra: Optional[date] = None
    calib_cert: Optional[str] = None
    data_calibracao: Optional[date] = None
    prox_calibragem: Optional[date] = None
    calib_temp: Optional[str] = None
    calib_pressao: Optional[str] = None
    calib_teste1: Optional[str] = None
    calib_teste2: Optional[str] = None
    calib_teste3: Optional[str] = None
    calib_teste_media: Optional[str] = None
    calib_situacao: Optional[str] = None
    ja_gerado: bool = False           # o front usa para dizer "Gerar" ou "Regerar"


class CertificadoVendaIn(BaseModel):
    # cliente/aparelho: opcionais — sobrepoem o cadastro so se vierem preenchidos
    nomecli: Optional[str] = None
    cnpj: Optional[str] = None
    endcli: Optional[str] = None
    serie: Optional[str] = None
    patrimonio: Optional[str] = None
    datacompra: Optional[date] = None
    # calibracao: digitada no modal
    calib_cert: Optional[str] = None
    data_calibracao: Optional[date] = None
    prox_calibragem: Optional[date] = None
    calib_temp: Optional[str] = None
    calib_pressao: Optional[str] = None
    calib_teste1: Optional[str] = None
    calib_teste2: Optional[str] = None
    calib_teste3: Optional[str] = None
    calib_teste_media: Optional[str] = None
    calib_situacao: Optional[str] = None


class CertificadoVendaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    equipamento_cliente: int
    calib_cert: Optional[str] = None
    data_calibracao: Optional[date] = None
    data_geracao: Optional[datetime] = None
    usuario_nome: Optional[str] = None
```

- [ ] **Step 4: Write the router**

Create `backend/app/api/certificados_venda.py`:

```python
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_usuario, require_funcao
from app.api.ordens_acoes import espelhar_calibracao_valores
from app.core.certificado_gerar import modelo_marca, montar_contexto_venda, preencher, _endereco
from app.core.certificado_pdf import html_para_pdf
from app.models import CertificadoModelo, CertificadoVenda, EquipamentoCliente, Usuario
from app.models.database import get_db
from app.schemas.certificado_venda import (CertificadoVendaCamposOut, CertificadoVendaIn,
                                           CertificadoVendaOut)

router = APIRouter(prefix="/equipamentos-cliente", tags=["certificado-venda"])

_GERAR = require_funcao("Laboratório", "Administrador")
SITUACAO_PADRAO_VENDA = "Aparelho inicial"


def _aparelho_ou_404(db: Session, item_id: int) -> EquipamentoCliente:
    ec = db.query(EquipamentoCliente).filter(EquipamentoCliente.id == item_id).first()
    if ec is None:
        raise HTTPException(status_code=404, detail="aparelho não encontrado")
    return ec


def _venda_de(db: Session, item_id: int) -> CertificadoVenda | None:
    return db.query(CertificadoVenda).filter(
        CertificadoVenda.equipamento_cliente == item_id).first()


@router.get("/{item_id}/certificado-venda-campos", response_model=CertificadoVendaCamposOut)
def campos(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    ec = _aparelho_ou_404(db, item_id)
    cli = ec.cliente_rel
    modelo, marca = modelo_marca(db, ec.equipamento)
    cv = _venda_de(db, item_id)
    return CertificadoVendaCamposOut(
        nomecli=(cli.nome if cli else "") or "",
        cnpj=((cli.cgc or cli.cpf) if cli else "") or "",
        endcli=_endereco(cli),
        modelo=modelo,
        marca=marca,
        serie=ec.serie or "",
        patrimonio=ec.patrimonio or "",
        datacompra=ec.datacompra,
        calib_cert=ec.calib_cert,
        data_calibracao=cv.data_calibracao if cv else date.today(),
        prox_calibragem=ec.prox_calibragem,
        calib_temp=ec.calib_temp,
        calib_pressao=ec.calib_pressao,
        calib_teste1=ec.calib_teste1,
        calib_teste2=ec.calib_teste2,
        calib_teste3=ec.calib_teste3,
        calib_teste_media=ec.calib_teste_media,
        calib_situacao=ec.calib_situacao or SITUACAO_PADRAO_VENDA,
        ja_gerado=cv is not None,
    )


@router.post("/{item_id}/certificado-venda", response_model=CertificadoVendaOut,
             status_code=status.HTTP_201_CREATED)
def gerar(item_id: int, dados: CertificadoVendaIn, db: Session = Depends(get_db),
          usuario: Usuario = Depends(_GERAR)):
    ec = _aparelho_ou_404(db, item_id)
    modelo = db.query(CertificadoModelo).filter(
        CertificadoModelo.equipamento == ec.equipamento,
        CertificadoModelo.tipo == "C",
    ).first()
    if modelo is None or not modelo.texto:
        aparelho = ec.equipamento_descricao or "este aparelho"
        raise HTTPException(
            status_code=409,
            detail=f"O aparelho {aparelho} não tem modelo de certificado de Calibração "
                   f"cadastrado. Cadastre o modelo em Certificados antes de gerar.",
        )
    valores = dados.model_dump()
    html = preencher(modelo.texto, montar_contexto_venda(db, ec, valores))

    cv = _venda_de(db, item_id)
    if cv is None:                       # upsert: um por aparelho, regeravel
        cv = CertificadoVenda(equipamento_cliente=item_id)
        db.add(cv)
    cv.html = html
    cv.calib_cert = dados.calib_cert
    cv.data_calibracao = dados.data_calibracao
    cv.usuario = usuario.id
    cv.data_geracao = datetime.now(timezone.utc)

    espelhar_calibracao_valores(db, ec, valores,
                                ult=dados.data_calibracao, prox=dados.prox_calibragem)
    db.commit()
    db.refresh(cv)
    return CertificadoVendaOut.model_validate(cv)


@router.get("/{item_id}/certificado-venda/pdf")
def baixar_pdf(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    _aparelho_ou_404(db, item_id)
    cv = _venda_de(db, item_id)
    if cv is None or not cv.html:
        raise HTTPException(status_code=404, detail="certificado não gerado")
    try:
        pdf = html_para_pdf(cv.html)
    except Exception:
        raise HTTPException(status_code=500, detail="falha ao gerar PDF")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="certificado-venda-{item_id}.pdf"'},
    )
```

- [ ] **Step 5: Register the router**

In `backend/app/main.py`, add `certificados_venda` to the existing `from app.api import ...` list, and add the include next to the other certificate routers:

```python
app.include_router(certificados_venda.router)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_certificado_venda_api.py -q`
Expected: PASS (9 passed)

- [ ] **Step 7: Run the full backend suite**

Run: `cd backend && source .venv/bin/activate && pytest -q`
Expected: PASS. Atenção ao conflito de rota: `certificados_venda.router` usa o mesmo prefixo `/equipamentos-cliente` do router de frota. Se algum teste de frota falhar com 404/422, é colisão de rota — nesse caso registre `certificados_venda.router` **antes** do router de frota em `main.py`.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/certificado_venda.py backend/app/api/certificados_venda.py \
        backend/app/main.py backend/tests/test_certificado_venda_api.py
git commit -m "feat(cert): endpoints de gerar, campos e pdf do certificado de venda"
```

---

### Task 5: Card de certificados da frota une as duas fontes

**Files:**
- Modify: `backend/app/schemas/frota.py:107-111`
- Modify: `backend/app/api/equipamentos_cliente.py:120-131`
- Test: `backend/tests/test_frota_os_certificados.py`

**Interfaces:**
- Consumes: `CertificadoVenda` (Task 1).
- Produces: `EquipCertItem` com `os: int | None`, `tipo: str`, `data_geracao: datetime | None`, `origem: str` (`"os"` ou `"venda"`).

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_frota_os_certificados.py`:

```python
def test_certificados_do_aparelho_inclui_o_de_venda(client, usuario_admin, db_session):
    from app.models import CertificadoVenda
    ec_id, _outro, o1, _o2 = _aparelho_com_os(db_session)
    db_session.add(CertificadoVenda(equipamento_cliente=ec_id, html="<p>v</p>",
                                    calib_cert="V-001"))
    db_session.commit()
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.get(f"/equipamentos-cliente/{ec_id}/certificados", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    de_os = [c for c in body if c["origem"] == "os"]
    de_venda = [c for c in body if c["origem"] == "venda"]
    assert len(de_os) == 1 and de_os[0]["os"] == o1
    assert len(de_venda) == 1
    assert de_venda[0]["os"] is None
    assert de_venda[0]["tipo"] == "C"
    assert body[-1]["origem"] == "venda"        # venda vem por ultimo


def test_certificado_de_venda_nao_vaza_para_outro_aparelho(client, usuario_admin, db_session):
    from app.models import CertificadoVenda
    ec_id, outro, _o1, _o2 = _aparelho_com_os(db_session)
    db_session.add(CertificadoVenda(equipamento_cliente=ec_id, html="<p>v</p>"))
    db_session.commit()
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.get(f"/equipamentos-cliente/{outro}/certificados", headers=h)
    assert r.status_code == 200
    assert r.json() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_frota_os_certificados.py -q`
Expected: FAIL — `KeyError: 'origem'`

- [ ] **Step 3: Widen the schema**

In `backend/app/schemas/frota.py`, replace the `EquipCertItem` class (lines 107-111) with:

```python
class EquipCertItem(BaseModel):
    os: int | None = None          # nulo no certificado de venda (nao ha OS)
    tipo: str
    data_geracao: datetime | None = None
    origem: str = "os"             # "os" | "venda"
    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Union the two sources**

In `backend/app/api/equipamentos_cliente.py`, replace the body of `certificados_do_aparelho` (lines 120-131) with:

```python
@router.get("/{item_id}/certificados", response_model=list[EquipCertItem])
def certificados_do_aparelho(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    if db.query(EquipamentoCliente).filter(EquipamentoCliente.id == item_id).first() is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    rows = (
        db.query(OSCertificado)
        .join(Ordem, OSCertificado.os == Ordem.id)
        .filter(Ordem.equipamento_cliente == item_id)
        .order_by(OSCertificado.os.desc(), OSCertificado.tipo)
        .all()
    )
    itens = [EquipCertItem(os=c.os, tipo=c.tipo, data_geracao=c.data_geracao, origem="os")
             for c in rows]
    # O de venda e cronologicamente o PRIMEIRO da vida do aparelho, entao fecha a lista
    # (que esta em ordem decrescente). Sempre tipo "C".
    venda = db.query(CertificadoVenda).filter(
        CertificadoVenda.equipamento_cliente == item_id).first()
    if venda is not None:
        itens.append(EquipCertItem(os=None, tipo="C",
                                   data_geracao=venda.data_geracao, origem="venda"))
    return itens
```

Add `CertificadoVenda` to the existing `from app.models import ...` line at the top of the file.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_frota_os_certificados.py -q`
Expected: PASS

- [ ] **Step 6: Run the full backend suite**

Run: `cd backend && source .venv/bin/activate && pytest -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/frota.py backend/app/api/equipamentos_cliente.py \
        backend/tests/test_frota_os_certificados.py
git commit -m "feat(frota): card de certificados inclui o certificado de venda"
```

---

### Task 6: Portal serve o certificado de venda

**Files:**
- Modify: `backend/app/schemas/portal.py:35-43`
- Modify: `backend/app/api/portal.py:81-113` e `:167-172`
- Test: `backend/tests/test_portal_certificado_venda.py`

**Interfaces:**
- Consumes: `CertificadoVenda` (Task 1).
- Produces: `PortalCertItem.venda: bool`; rota `GET /portal/certificado-venda/{item_id}`.

**Nota de desenho:** a spec falava em "acrescentar caminho" ao `GET /portal/certificados/{ordem_id}`, mas aquele endpoint recebe **ordem_id** e o certificado de venda não tem OS. Vai uma rota nova por aparelho. O isolamento de tenant é feito comparando `ec.cliente` com `cli.cliente` **do token** — nunca por parâmetro.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_portal_certificado_venda.py`:

```python
from datetime import date


def _login_portal(client):
    # rota real: /auth/login-portal (ver backend/tests/test_portal.py:5)
    tok = client.post("/auth/login-portal", json={
        "documento": "11222333000144", "login": "cliente1", "senha": "portal123",
    }).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _aparelho_vendido(db_session, cliente_id):
    """Aparelho com certificado de venda e SEM OS — o caso da feature."""
    from app.models import Equipamento, EquipamentoCliente, CertificadoVenda
    eq = Equipamento(descricao="Mark X")
    db_session.add(eq); db_session.flush()
    ec = EquipamentoCliente(cliente=cliente_id, equipamento=eq.id, serie="S1",
                            calib_cert="V-001", ult_calibragem=date(2026, 7, 20),
                            prox_calibragem=date(2027, 7, 20))
    db_session.add(ec); db_session.flush()
    db_session.add(CertificadoVenda(equipamento_cliente=ec.id,
                                    html="<p>certificado de venda</p>", calib_cert="V-001"))
    db_session.commit(); db_session.refresh(ec)
    return ec


def test_aparelho_vendido_sem_os_aparece_com_venda_true(client, cliente_portal, db_session):
    ec = _aparelho_vendido(db_session, cliente_portal.cliente)
    h = _login_portal(client)
    r = client.get("/portal/certificados", headers=h)
    assert r.status_code == 200
    items = r.json()["items"]
    alvo = [i for i in items if i["equipamento_cliente"] == ec.id]
    assert len(alvo) == 1
    assert alvo[0]["os"] is None
    assert alvo[0]["venda"] is True


def test_cliente_baixa_o_certificado_de_venda(client, cliente_portal, db_session):
    ec = _aparelho_vendido(db_session, cliente_portal.cliente)
    h = _login_portal(client)
    r = client.get(f"/portal/certificado-venda/{ec.id}", headers=h)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"


def test_cliente_nao_baixa_certificado_de_outro_tenant(client, cliente_portal, db_session):
    """Isolamento pelo token: o id na URL nao pode dar acesso."""
    from app.models import Cliente
    outro = Cliente(nome="Outra Empresa", cgc="99888777000166")
    db_session.add(outro); db_session.flush()
    ec_alheio = _aparelho_vendido(db_session, outro.id)
    h = _login_portal(client)
    r = client.get(f"/portal/certificado-venda/{ec_alheio.id}", headers=h)
    assert r.status_code == 404


def test_sem_certificado_de_venda_404(client, cliente_portal, db_session):
    from app.models import Equipamento, EquipamentoCliente
    eq = Equipamento(descricao="Mark X")
    db_session.add(eq); db_session.flush()
    ec = EquipamentoCliente(cliente=cliente_portal.cliente, equipamento=eq.id, serie="S9")
    db_session.add(ec); db_session.commit(); db_session.refresh(ec)
    h = _login_portal(client)
    assert client.get(f"/portal/certificado-venda/{ec.id}", headers=h).status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_portal_certificado_venda.py -q`
Expected: FAIL — `KeyError: 'venda'` e 404 na rota nova.

- [ ] **Step 3: Add the flag to the schema**

In `backend/app/schemas/portal.py`, add one field to `PortalCertItem` (after `os`):

```python
    venda: bool = False        # PDF vem do certificado de venda (aparelho sem OS)
```

- [ ] **Step 4: Flag the item in the listing**

In `backend/app/api/portal.py`, inside `certificados`, replace the `items = [...]` comprehension with:

```python
    ids_com_venda = {
        cv.equipamento_cliente
        for cv in db.query(CertificadoVenda).filter(
            CertificadoVenda.equipamento_cliente.in_([ec.id for ec, _ in linhas])
        ).all()
    } if linhas else set()
    items = [
        PortalCertItem(
            equipamento_cliente=ec.id,
            equipamento_descricao=ec.equipamento_descricao,
            serie=ec.serie,
            calib_cert=ec.calib_cert,
            ult_calibragem=ec.ult_calibragem,
            prox_calibragem=ec.prox_calibragem,
            pdf=pdf,
            os=ec.os_atual,
            venda=ec.os_atual is None and ec.id in ids_com_venda,
        )
        for ec, pdf in linhas
    ]
```

Add `CertificadoVenda` and `EquipamentoCliente` (if not already imported) to the `from app.models import ...` line at the top of the file.

- [ ] **Step 5: Add the download route**

In `backend/app/api/portal.py`, add right after `baixar_certificado_portal`:

```python
@router.get("/certificado-venda/{item_id}")
def baixar_certificado_venda_portal(item_id: int,
                                    cli: UsuarioCliente = Depends(get_current_cliente),
                                    db: Session = Depends(get_db)):
    """Certificado de venda do aparelho (sem OS).

    Tenant validado pelo TOKEN (`cli.cliente`), nunca pelo id da URL: um id de outro
    cliente responde 404, nao o PDF.
    """
    ec = db.query(EquipamentoCliente).filter(
        EquipamentoCliente.id == item_id,
        EquipamentoCliente.cliente == cli.cliente,
    ).first()
    if ec is None:
        raise HTTPException(status_code=404, detail="certificado não encontrado")
    cv = db.query(CertificadoVenda).filter(
        CertificadoVenda.equipamento_cliente == item_id).first()
    if cv is None or not cv.html:
        raise HTTPException(status_code=404, detail="certificado não encontrado")
    try:
        pdf = html_para_pdf(cv.html)
    except Exception:
        raise HTTPException(status_code=500, detail="falha ao gerar PDF")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="certificado-venda-{item_id}.pdf"'},
    )
```

Make sure `Response` (from `fastapi`) and `html_para_pdf` (from `app.core.certificado_pdf`) are imported at the top of the file; add them if missing.

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_portal_certificado_venda.py -q`
Expected: PASS (4 passed)

- [ ] **Step 7: Run the full backend suite**

Run: `cd backend && source .venv/bin/activate && pytest -q`
Expected: PASS — `tests/test_portal.py` continua verde (só foi acrescentado um campo com default).

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/portal.py backend/app/api/portal.py \
        backend/tests/test_portal_certificado_venda.py
git commit -m "feat(portal): cliente baixa o certificado de venda de aparelho sem OS"
```

---

### Task 7: Extrair o formulário compartilhado `CamposCertificado`

**Files:**
- Create: `frontend/src/app/certificados/CamposCertificado.tsx`
- Modify: `frontend/src/app/ordens/GerarCertificadoModal.tsx`
- Test: `frontend/src/app/certificados/CamposCertificado.test.tsx`

**Interfaces:**
- Consumes: `Input`, `Select` de `src/components/ui/`, `mediaTestes` de `src/lib/calibragem`.
- Produces:
```ts
export interface ValoresCertificado {
  nomecli: string; cnpj: string; endcli: string
  modelo: string; marca: string; serie: string; patrimonio: string; datacompra: string
  dataCalib: string; cert: string; situacao: string
  temp: string; pressao: string; t1: string; t2: string; t3: string; media: string
}
export function valoresIniciais(): ValoresCertificado
export function CamposCertificado(props: {
  valores: ValoresCertificado
  onChange: (patch: Partial<ValoresCertificado>) => void
  extra?: ReactNode        // renderizado no fim da secao Calibracao
}): JSX.Element
```

Esta task é **refactor puro**: nenhum comportamento muda. O ganho é evitar a terceira cópia do mesmo formulário (OS, avulso, venda) divergindo com o tempo.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/app/certificados/CamposCertificado.test.tsx`:

```tsx
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { CamposCertificado, valoresIniciais, type ValoresCertificado } from './CamposCertificado'

function Harness({ extra }: { extra?: React.ReactNode }) {
  const [v, setV] = useState<ValoresCertificado>(valoresIniciais())
  return <CamposCertificado valores={v} onChange={(p) => setV((a) => ({ ...a, ...p }))} extra={extra} />
}

describe('CamposCertificado', () => {
  it('mostra as tres secoes do formulario', () => {
    render(<Harness />)
    expect(screen.getByText('Cliente')).toBeInTheDocument()
    expect(screen.getByText('Aparelho')).toBeInTheDocument()
    expect(screen.getByText('Calibração')).toBeInTheDocument()
  })

  it('calcula a media dos testes automaticamente', () => {
    render(<Harness />)
    fireEvent.change(screen.getByLabelText('Teste 1'), { target: { value: '0,10' } })
    fireEvent.change(screen.getByLabelText('Teste 2'), { target: { value: '0,20' } })
    fireEvent.change(screen.getByLabelText('Teste 3'), { target: { value: '0,30' } })
    expect((screen.getByLabelText('Média dos testes') as HTMLInputElement).value).toBe('0,20')
  })

  it('para de calcular a media depois que o usuario digita a mao', () => {
    render(<Harness />)
    fireEvent.change(screen.getByLabelText('Média dos testes'), { target: { value: '9,99' } })
    fireEvent.change(screen.getByLabelText('Teste 1'), { target: { value: '0,10' } })
    expect((screen.getByLabelText('Média dos testes') as HTMLInputElement).value).toBe('9,99')
  })

  it('renderiza o slot extra no fim da secao de calibracao', () => {
    render(<Harness extra={<p>campo extra</p>} />)
    expect(screen.getByText('campo extra')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/app/certificados/CamposCertificado.test.tsx`
Expected: FAIL — módulo `./CamposCertificado` não existe.

- [ ] **Step 3: Write the shared component**

Create `frontend/src/app/certificados/CamposCertificado.tsx`:

```tsx
import { useEffect, useState, type ReactNode } from 'react'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { mediaTestes } from '../../lib/calibragem'

export interface ValoresCertificado {
  nomecli: string
  cnpj: string
  endcli: string
  modelo: string
  marca: string
  serie: string
  patrimonio: string
  datacompra: string
  dataCalib: string
  cert: string
  situacao: string
  temp: string
  pressao: string
  t1: string
  t2: string
  t3: string
  media: string
}

export function hojeISO(): string {
  return new Date().toISOString().slice(0, 10)
}

export function valoresIniciais(): ValoresCertificado {
  return {
    nomecli: '', cnpj: '', endcli: '',
    modelo: '', marca: '', serie: '', patrimonio: '', datacompra: '',
    dataCalib: hojeISO(), cert: '', situacao: '',
    temp: '', pressao: '', t1: '', t2: '', t3: '', media: '',
  }
}

const secao = 'text-xs font-semibold text-slate-500 uppercase tracking-wide'

/** Formulario de certificado compartilhado entre o fluxo da OS e o de venda.
 *  `extra` entra no fim da secao Calibracao (a venda usa para "Proxima calibracao"). */
export function CamposCertificado({ valores, onChange, extra }: {
  valores: ValoresCertificado
  onChange: (patch: Partial<ValoresCertificado>) => void
  extra?: ReactNode
}) {
  const [mediaEditada, setMediaEditada] = useState(false)

  useEffect(() => {
    if (mediaEditada) return
    // eslint-disable-next-line react-hooks/set-state-in-effect
    onChange({ media: mediaTestes(valores.t1, valores.t2, valores.t3) })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [valores.t1, valores.t2, valores.t3, mediaEditada])

  return (
    <>
      <div className="space-y-3">
        <p className={secao}>Cliente</p>
        <Input id="nomecli" label="Nome" value={valores.nomecli} onChange={(e) => onChange({ nomecli: e.target.value })} />
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Input id="cnpj" label="CNPJ/CPF" value={valores.cnpj} onChange={(e) => onChange({ cnpj: e.target.value })} />
          <Input id="endcli" label="Endereço" value={valores.endcli} onChange={(e) => onChange({ endcli: e.target.value })} />
        </div>
      </div>

      <div className="space-y-3">
        <p className={secao}>Aparelho</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Input id="modelo" label="Modelo" value={valores.modelo} onChange={(e) => onChange({ modelo: e.target.value })} />
          <Input id="marca" label="Marca" value={valores.marca} onChange={(e) => onChange({ marca: e.target.value })} />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Input id="serie" label="Série" value={valores.serie} onChange={(e) => onChange({ serie: e.target.value })} />
          <Input id="patrimonio" label="Patrimônio" value={valores.patrimonio} onChange={(e) => onChange({ patrimonio: e.target.value })} />
          <Input id="datacompra" label="Data de compra" value={valores.datacompra} onChange={(e) => onChange({ datacompra: e.target.value })} />
        </div>
      </div>

      <div className="space-y-3">
        <p className={secao}>Calibração</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Input id="data-calib" label="Data de calibração" type="date" value={valores.dataCalib} onChange={(e) => onChange({ dataCalib: e.target.value })} />
          <Input id="cert" label="Nº do certificado" value={valores.cert} onChange={(e) => onChange({ cert: e.target.value })} />
        </div>
        <Select id="situacao" label="Situação" value={valores.situacao} onChange={(e) => onChange({ situacao: e.target.value })}>
          <option value="">— selecione —</option>
          <option value="Aparelho subsequente">Aparelho subsequente</option>
          <option value="Aparelho inicial">Aparelho inicial</option>
        </Select>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Input id="temp" label="Temperatura" value={valores.temp} onChange={(e) => onChange({ temp: e.target.value })} />
          <Input id="pressao" label="Pressão" value={valores.pressao} onChange={(e) => onChange({ pressao: e.target.value })} />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Input id="t1" label="Teste 1" value={valores.t1} onChange={(e) => onChange({ t1: e.target.value })} />
          <Input id="t2" label="Teste 2" value={valores.t2} onChange={(e) => onChange({ t2: e.target.value })} />
          <Input id="t3" label="Teste 3" value={valores.t3} onChange={(e) => onChange({ t3: e.target.value })} />
        </div>
        <Input id="media" label="Média dos testes" value={valores.media} onChange={(e) => { setMediaEditada(true); onChange({ media: e.target.value }) }} />
        {extra}
      </div>
    </>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/app/certificados/CamposCertificado.test.tsx`
Expected: PASS (4 passed)

- [ ] **Step 5: Rewrite `GerarCertificadoModal` on top of it**

Replace the whole body of `frontend/src/app/ordens/GerarCertificadoModal.tsx` with:

```tsx
import { useEffect, useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Spinner } from '../../components/ui/Spinner'
import { ApiError } from '../../lib/api'
import { CamposCertificado, valoresIniciais, hojeISO, type ValoresCertificado } from '../certificados/CamposCertificado'
import { ordensApi, type OrdemDetalhe, type OSCertificado, type GerarCertificadoPayload } from './api'

export function GerarCertificadoModal({ os, onClose, onGerado }: {
  os: OrdemDetalhe
  onClose: () => void
  onGerado: (certs: OSCertificado[]) => void
}) {
  const [carregando, setCarregando] = useState(true)
  const [v, setV] = useState<ValoresCertificado>(valoresIniciais())
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  function set(patch: Partial<ValoresCertificado>) {
    setV((atual) => ({ ...atual, ...patch }))
  }

  useEffect(() => {
    let ativo = true
    ordensApi.certificadoCampos(os.id)
      .then((c) => {
        if (!ativo) return
        setV({
          nomecli: c.nomecli ?? '', cnpj: c.cnpj ?? '', endcli: c.endcli ?? '',
          modelo: c.modelo ?? '', marca: c.marca ?? '', serie: c.serie ?? '',
          patrimonio: c.patrimonio ?? '', datacompra: c.datacompra ?? '',
          cert: c.calib_cert ?? '', situacao: c.calib_situacao ?? '',
          temp: c.calib_temp ?? '', pressao: c.calib_pressao ?? '',
          t1: c.calib_teste1 ?? '', t2: c.calib_teste2 ?? '', t3: c.calib_teste3 ?? '',
          media: c.calib_teste_media ?? '',
          dataCalib: c.data_calibracao ? c.data_calibracao.slice(0, 10) : hojeISO(),
        })
        setCarregando(false)
      })
      .catch(() => { if (ativo) { setErro('Falha ao carregar os campos do certificado'); setCarregando(false) } })
    return () => { ativo = false }
  }, [os.id])

  async function submeter(e: FormEvent) {
    e.preventDefault()
    setErro(''); setEnviando(true)
    const payload: GerarCertificadoPayload = {
      data_calibracao: v.dataCalib || null,
      nomecli: v.nomecli.trim() || null,
      cnpj: v.cnpj.trim() || null,
      endcli: v.endcli.trim() || null,
      modelo: v.modelo.trim() || null,
      marca: v.marca.trim() || null,
      serie: v.serie.trim() || null,
      patrimonio: v.patrimonio.trim() || null,
      datacompra: v.datacompra.trim() || null,
      calib_cert: v.cert.trim() || null,
      calib_temp: v.temp.trim() || null,
      calib_pressao: v.pressao.trim() || null,
      calib_teste1: v.t1.trim() || null,
      calib_teste2: v.t2.trim() || null,
      calib_teste3: v.t3.trim() || null,
      calib_teste_media: v.media.trim() || null,
      calib_situacao: v.situacao.trim() || null,
    }
    try {
      onGerado(await ordensApi.gerarCertificado(os.id, payload))
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao gerar certificado')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title="Gerar certificado de calibração"
      footer={
        <>
          <button type="button" onClick={onClose} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">Cancelar</button>
          <button type="submit" form="form-gerar-cert" disabled={enviando || carregando} className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all">Gerar</button>
        </>
      }
    >
      {carregando ? (
        <div className="flex justify-center py-10"><Spinner className="w-7 h-7" /></div>
      ) : (
        <form id="form-gerar-cert" className="space-y-5" onSubmit={submeter}>
          <CamposCertificado valores={v} onChange={set} />
          {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
        </form>
      )}
    </Modal>
  )
}
```

- [ ] **Step 6: Run the full frontend suite (regression gate)**

Run: `cd frontend && npm test`
Expected: PASS — em especial os testes existentes do fluxo de certificado da OS. Esta task não pode mudar comportamento nenhum; se um teste de OS falhar, a extração divergiu do original.

- [ ] **Step 7: Typecheck and lint**

Run: `cd frontend && npm run lint && npx tsc -b --noEmit`
Expected: sem erros.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/app/certificados/CamposCertificado.tsx \
        frontend/src/app/certificados/CamposCertificado.test.tsx \
        frontend/src/app/ordens/GerarCertificadoModal.tsx
git commit -m "refactor(cert): extrai formulario compartilhado do certificado"
```

---

### Task 8: Modal e botão do certificado de venda

**Files:**
- Modify: `frontend/src/auth/roles.ts`
- Modify: `frontend/src/app/frota/api.ts:97-111` e `:141-162`
- Create: `frontend/src/app/frota/CertificadoVendaModal.tsx`
- Modify: `frontend/src/app/frota/EquipamentoClienteDetailPage.tsx`
- Test: `frontend/src/app/frota/CertificadoVenda.test.tsx`

**Interfaces:**
- Consumes: `CamposCertificado`, `valoresIniciais`, `hojeISO`, `ValoresCertificado` (Task 7); endpoints da Task 4; `EquipCertItem.origem` (Task 5).
- Produces: `podeGerarCertificadoVenda(user)`; `equipamentosClienteApi.certificadoVendaCampos(id)`, `.gerarCertificadoVenda(id, payload)`, `.baixarCertificadoVendaPdf(id)`; componente `CertificadoVendaModal`.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/app/frota/CertificadoVenda.test.tsx`:

```tsx
import { describe, expect, it } from 'vitest'
import { podeGerarCertificadoVenda } from '../../auth/roles'

describe('podeGerarCertificadoVenda', () => {
  it('permite Administrador e Laboratorio', () => {
    expect(podeGerarCertificadoVenda({ funcao: 'Administrador' } as never)).toBe(true)
    expect(podeGerarCertificadoVenda({ funcao: 'Laboratório' } as never)).toBe(true)
  })

  it('bloqueia as demais funcoes e o usuario nulo', () => {
    expect(podeGerarCertificadoVenda({ funcao: 'Comercial Pós-Vendas' } as never)).toBe(false)
    expect(podeGerarCertificadoVenda({ funcao: 'Expedição' } as never)).toBe(false)
    expect(podeGerarCertificadoVenda(null)).toBe(false)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/app/frota/CertificadoVenda.test.tsx`
Expected: FAIL — `podeGerarCertificadoVenda` não é exportado.

- [ ] **Step 3: Mirror the backend rule in `roles.ts`**

In `frontend/src/auth/roles.ts`, add after `podeGerenciarCertificadosGerais`:

```ts
// Espelha require_funcao("Laboratório", "Administrador") em
// backend/app/api/certificados_venda.py — mudou lá, mude aqui.
export function podeGerarCertificadoVenda(user: User | null): boolean {
  return isAdmin(user) || user?.funcao === FUNCAO_LABORATORIO
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/app/frota/CertificadoVenda.test.tsx`
Expected: PASS (2 passed)

- [ ] **Step 5: Extend the frota API client**

In `frontend/src/app/frota/api.ts`, add the `origem` field to the existing `EquipCertItem` interface (around line 97) and make `os` nullable:

```ts
export interface EquipCertItem {
  os: number | null
  tipo: string
  data_geracao: string | null
  origem: 'os' | 'venda'
}

export interface CertificadoVendaCampos {
  nomecli: string
  cnpj: string
  endcli: string
  modelo: string
  marca: string
  serie: string
  patrimonio: string
  datacompra: string | null
  calib_cert: string | null
  data_calibracao: string | null
  prox_calibragem: string | null
  calib_temp: string | null
  calib_pressao: string | null
  calib_teste1: string | null
  calib_teste2: string | null
  calib_teste3: string | null
  calib_teste_media: string | null
  calib_situacao: string | null
  ja_gerado: boolean
}

export interface CertificadoVendaPayload {
  nomecli: string | null
  cnpj: string | null
  endcli: string | null
  serie: string | null
  patrimonio: string | null
  datacompra: string | null
  calib_cert: string | null
  data_calibracao: string | null
  prox_calibragem: string | null
  calib_temp: string | null
  calib_pressao: string | null
  calib_teste1: string | null
  calib_teste2: string | null
  calib_teste3: string | null
  calib_teste_media: string | null
  calib_situacao: string | null
}
```

Then add three methods to the `equipamentosClienteApi` object, next to `certificados`:

```ts
  certificadoVendaCampos: (id: number): Promise<CertificadoVendaCampos> =>
    apiJson<CertificadoVendaCampos>(`/equipamentos-cliente/${id}/certificado-venda-campos`),
  gerarCertificadoVenda: (id: number, body: CertificadoVendaPayload): Promise<unknown> =>
    apiJson<unknown>(`/equipamentos-cliente/${id}/certificado-venda`, { method: 'POST', body: JSON.stringify(body) }),
  baixarCertificadoVendaPdf: async (id: number): Promise<void> => {
    const res = await apiFetch(`/equipamentos-cliente/${id}/certificado-venda/pdf`)
    if (!res.ok) throw new ApiError(res.status, 'Falha ao baixar PDF')
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `certificado-venda-${id}.pdf`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  },
```

`frontend/src/app/frota/api.ts:1` já importa `apiJson, apiFetch, ApiError` — nenhum import novo é necessário. O corpo acima espelha `ordensApi.baixarCertificadoPdf` (`frontend/src/app/ordens/api.ts:371-384`).

- [ ] **Step 6: Write the modal**

Create `frontend/src/app/frota/CertificadoVendaModal.tsx`:

```tsx
import { useEffect, useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { Spinner } from '../../components/ui/Spinner'
import { ApiError } from '../../lib/api'
import { CamposCertificado, valoresIniciais, hojeISO, type ValoresCertificado } from '../certificados/CamposCertificado'
import { equipamentosClienteApi, type CertificadoVendaPayload } from './api'

export function CertificadoVendaModal({ aparelhoId, onClose, onGerado }: {
  aparelhoId: number
  onClose: () => void
  onGerado: () => void
}) {
  const [carregando, setCarregando] = useState(true)
  const [v, setV] = useState<ValoresCertificado>(valoresIniciais())
  const [prox, setProx] = useState('')
  const [jaGerado, setJaGerado] = useState(false)
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  function set(patch: Partial<ValoresCertificado>) {
    setV((atual) => ({ ...atual, ...patch }))
  }

  useEffect(() => {
    let ativo = true
    equipamentosClienteApi.certificadoVendaCampos(aparelhoId)
      .then((c) => {
        if (!ativo) return
        setV({
          nomecli: c.nomecli, cnpj: c.cnpj, endcli: c.endcli,
          modelo: c.modelo, marca: c.marca, serie: c.serie, patrimonio: c.patrimonio,
          datacompra: c.datacompra ?? '',
          cert: c.calib_cert ?? '', situacao: c.calib_situacao ?? '',
          temp: c.calib_temp ?? '', pressao: c.calib_pressao ?? '',
          t1: c.calib_teste1 ?? '', t2: c.calib_teste2 ?? '', t3: c.calib_teste3 ?? '',
          media: c.calib_teste_media ?? '',
          dataCalib: c.data_calibracao ?? hojeISO(),
        })
        setProx(c.prox_calibragem ?? '')
        setJaGerado(c.ja_gerado)
        setCarregando(false)
      })
      .catch(() => { if (ativo) { setErro('Falha ao carregar os campos do certificado'); setCarregando(false) } })
    return () => { ativo = false }
  }, [aparelhoId])

  async function submeter(e: FormEvent) {
    e.preventDefault()
    setErro(''); setEnviando(true)
    const payload: CertificadoVendaPayload = {
      nomecli: v.nomecli.trim() || null,
      cnpj: v.cnpj.trim() || null,
      endcli: v.endcli.trim() || null,
      serie: v.serie.trim() || null,
      patrimonio: v.patrimonio.trim() || null,
      datacompra: v.datacompra.trim() || null,
      calib_cert: v.cert.trim() || null,
      data_calibracao: v.dataCalib || null,
      prox_calibragem: prox || null,
      calib_temp: v.temp.trim() || null,
      calib_pressao: v.pressao.trim() || null,
      calib_teste1: v.t1.trim() || null,
      calib_teste2: v.t2.trim() || null,
      calib_teste3: v.t3.trim() || null,
      calib_teste_media: v.media.trim() || null,
      calib_situacao: v.situacao.trim() || null,
    }
    try {
      await equipamentosClienteApi.gerarCertificadoVenda(aparelhoId, payload)
      onGerado()
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao gerar certificado de venda')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={jaGerado ? 'Regerar certificado de venda' : 'Gerar certificado de venda'}
      footer={
        <>
          <button type="button" onClick={onClose} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">Cancelar</button>
          <button type="submit" form="form-cert-venda" disabled={enviando || carregando} className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all">{jaGerado ? 'Regerar' : 'Gerar'}</button>
        </>
      }
    >
      {carregando ? (
        <div className="flex justify-center py-10"><Spinner className="w-7 h-7" /></div>
      ) : (
        <form id="form-cert-venda" className="space-y-5" onSubmit={submeter}>
          <CamposCertificado
            valores={v}
            onChange={set}
            extra={
              <Input
                id="prox-calibragem"
                label="Próxima calibração"
                type="date"
                value={prox}
                onChange={(e) => setProx(e.target.value)}
              />
            }
          />
          {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
        </form>
      )}
    </Modal>
  )
}
```

- [ ] **Step 7: Wire the button into the frota page**

In `frontend/src/app/frota/EquipamentoClienteDetailPage.tsx`:

1. Imports — o arquivo **já** importa `useAuth` (linha 10) e `EquipCertItem` (linha 15). Só falta:
   - acrescentar `podeGerarCertificadoVenda` à linha de import de `../../auth/roles` (que hoje traz `isAdmin, podeAbrirOS, podeGerenciarCadastros`);
   - acrescentar a linha nova:
```tsx
import { CertificadoVendaModal } from './CertificadoVendaModal'
```

2. Estado — `const { user } = useAuth()` **já existe na linha 48**; não duplique. Acrescente ao lado do estado dos outros modais (`abrindoOS`, `transferindo`):
```tsx
const [gerandoVenda, setGerandoVenda] = useState(false)
const temVenda = certs.some((c) => c.origem === 'venda')
```

3. Replace the `<h2>Certificados</h2>` header line with a header row carrying the button:
```tsx
<div className="flex items-center justify-between gap-3">
  <h2 className="text-sm font-semibold text-slate-100">Certificados</h2>
  {podeGerarCertificadoVenda(user) && (
    <button
      type="button"
      onClick={() => setGerandoVenda(true)}
      className="text-xs font-semibold text-primary hover:underline"
    >
      {temVenda ? 'Regerar certificado de venda' : 'Gerar certificado de venda'}
    </button>
  )}
</div>
```

4. In the certificates table body, replace the `key` and the OS cell so a venda row renders without a link:
```tsx
{certs.map((c) => (
  <tr key={c.origem === 'venda' ? 'venda' : `${c.os}-${c.tipo}`} className="hover:bg-background-elevated transition-colors">
    <TD>{c.origem === 'venda'
      ? <span className="text-slate-400">— Venda</span>
      : <Link to={`/app/ordens/${c.os}`} className="font-semibold text-primary hover:underline">#{c.os}</Link>}</TD>
    <TD>{c.tipo === 'C' ? 'Calibração' : 'Manutenção'}</TD>
    <TD>{formatData(c.data_geracao)}</TD>
    <TD><button type="button" onClick={() => void baixarPdf(c)} className="text-xs font-semibold text-primary hover:underline">Baixar PDF</button></TD>
  </tr>
))}
```

5. Trocar `baixarPdf` (hoje em `EquipamentoClienteDetailPage.tsx:128-135`, com assinatura `(os: number, tipo: 'C' | 'M')`) por esta versão, que recebe o item e roteia pela origem. A mensagem de erro é **`'Falha ao baixar PDF'`**, idêntica à atual:
```tsx
async function baixarPdf(c: EquipCertItem) {
  setErroDownload('')
  try {
    if (c.origem === 'venda') {
      await equipamentosClienteApi.baixarCertificadoVendaPdf(obj!.id)
    } else {
      await ordensApi.baixarCertificadoPdf(c.os!, c.tipo as 'C' | 'M')
    }
  } catch {
    setErroDownload('Falha ao baixar PDF')
  }
}
```

6. Render the modal next to the other modals at the end of `corpo`:
```tsx
{gerandoVenda && obj && (
  <CertificadoVendaModal
    aparelhoId={obj.id}
    onClose={() => setGerandoVenda(false)}
    onGerado={() => { setGerandoVenda(false); setRecarga((n) => n + 1) }}
  />
)}
```

- [ ] **Step 8: Run the full frontend suite**

Run: `cd frontend && npm test`
Expected: PASS — inclusive os testes existentes de `EquipamentoClienteDetailPage` (`EquipamentoClienteDetailPage.embutido.test.tsx`, `elo.test.tsx`, `ClienteDetalheEmbutido.test.tsx`). Se algum quebrar por causa do `useAuth`, envolva o render do teste no provider que os outros testes de página já usam.

- [ ] **Step 9: Full frontend verification**

Run: `cd frontend && npm run lint && npx tsc -b --noEmit && npm run build`
Expected: sem erros.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/auth/roles.ts frontend/src/app/frota/api.ts \
        frontend/src/app/frota/CertificadoVendaModal.tsx \
        frontend/src/app/frota/CertificadoVenda.test.tsx \
        frontend/src/app/frota/EquipamentoClienteDetailPage.tsx
git commit -m "feat(cert): botao e modal de certificado de venda na ficha do aparelho"
```

---

### Task 9: Portal mostra o botão de download e changelog da release

**Files:**
- Modify: `frontend/src/portal/api.ts`
- Modify: `frontend/src/portal/PortalCertificadosPage.tsx:44-52`
- Modify: `frontend/src/app/changelog/data.ts:24`
- Test: `frontend/src/portal/PortalCertificadosPage.test.tsx`

**Interfaces:**
- Consumes: `PortalCertItem.venda` e `GET /portal/certificado-venda/{id}` (Task 6).
- Produces: `portalApi.baixarCertificadoVenda(equipamentoClienteId)`.

- [ ] **Step 1: Write the failing test**

Create (or extend, if it already exists) `frontend/src/portal/PortalCertificadosPage.test.tsx`:

```tsx
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { PortalCertificadosPage } from './PortalCertificadosPage'
import { portalApi } from './api'

beforeEach(() => { vi.restoreAllMocks() })

function item(over: Record<string, unknown> = {}) {
  return {
    equipamento_cliente: 1, equipamento_descricao: 'Mark X', serie: 'S1',
    calib_cert: 'V-001', ult_calibragem: '2026-07-20', prox_calibragem: '2027-07-20',
    pdf: null, os: null, venda: false, ...over,
  }
}

describe('PortalCertificadosPage', () => {
  it('oferece download quando o aparelho so tem certificado de venda', async () => {
    vi.spyOn(portalApi, 'certificados').mockResolvedValue({ items: [item({ venda: true })], total: 1 } as never)
    render(<PortalCertificadosPage />)
    await waitFor(() => expect(screen.getByRole('button', { name: 'Baixar' })).toBeInTheDocument())
  })

  it('nao oferece download sem OS e sem certificado de venda', async () => {
    vi.spyOn(portalApi, 'certificados').mockResolvedValue({ items: [item()], total: 1 } as never)
    render(<PortalCertificadosPage />)
    await waitFor(() => expect(screen.getByText('Mark X')).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: 'Baixar' })).not.toBeInTheDocument()
  })
})
```

`PortalCertificadosPage` não depende de router nem de provider (só chama `portalApi`), então o render é direto, sem wrapper.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/portal/PortalCertificadosPage.test.tsx`
Expected: FAIL — sem `venda` no tipo e sem botão para o caso de venda.

- [ ] **Step 3: Extend the portal API client**

In `frontend/src/portal/api.ts`, add `venda: boolean` to the `PortalCertItem` interface, and add the download method next to `baixarCertificado`:

```ts
  baixarCertificadoVenda: async (equipamentoClienteId: number): Promise<void> => {
    const res = await apiFetch(`/portal/certificado-venda/${equipamentoClienteId}`)
    if (!res.ok) throw new ApiError(res.status, 'Certificado indisponível')
    const url = URL.createObjectURL(await res.blob())
    window.open(url, '_blank', 'noopener')
  },
```

Espelha `baixarCertificado` (`frontend/src/portal/api.ts:49-54`), que abre o PDF em aba nova em vez de forçar download — mantenha esse comportamento para o cliente ter a mesma experiência nos dois casos.

- [ ] **Step 4: Route the button by source**

In `frontend/src/portal/PortalCertificadosPage.tsx:48-50`, the cell today is:

```tsx
<TD>{c.os != null
  ? <button type="button" className="text-primary hover:underline text-sm" onClick={() => { portalApi.baixarCertificado(c.os!).catch(() => setErro('Certificado indisponível')) }}>Baixar</button>
  : '—'}</TD>
```

Replace it with (o fallback continua sendo o literal `'—'`):

```tsx
<TD>{c.os != null
  ? <button type="button" className="text-primary hover:underline text-sm" onClick={() => { portalApi.baixarCertificado(c.os!).catch(() => setErro('Certificado indisponível')) }}>Baixar</button>
  : c.venda
    ? <button type="button" className="text-primary hover:underline text-sm" onClick={() => { portalApi.baixarCertificadoVenda(c.equipamento_cliente).catch(() => setErro('Certificado indisponível')) }}>Baixar</button>
    : '—'}</TD>
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/portal/PortalCertificadosPage.test.tsx`
Expected: PASS (2 passed)

- [ ] **Step 6: Add the changelog entry**

In `frontend/src/app/changelog/data.ts`, insert a new first entry inside `CHANGELOG` (before the `1.20.0` object at line 25):

```ts
  {
    versao: '1.21.0',
    data: '20/07/2026',
    itens: [
      { tipo: 'novidade', texto: 'Agora dá para emitir o certificado de venda de um aparelho sem precisar abrir uma OS. Na ficha do aparelho, o botão "Gerar certificado de venda" já vem com os dados do cliente e do equipamento preenchidos — basta informar os resultados da calibração e a próxima data. O certificado fica registrado na ficha e o cliente consegue baixá-lo pelo portal.' },
    ],
  },
```

- [ ] **Step 7: Full frontend verification**

Run: `cd frontend && npm test && npm run lint && npx tsc -b --noEmit && npm run build`
Expected: tudo passa.

- [ ] **Step 8: Full backend verification**

Run: `cd backend && source .venv/bin/activate && pytest -q`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/portal/api.ts frontend/src/portal/PortalCertificadosPage.tsx \
        frontend/src/portal/PortalCertificadosPage.test.tsx \
        frontend/src/app/changelog/data.ts
git commit -m "docs(changelog): v1.21.0 — certificado de venda sem abrir OS"
```

---

## Aplicação em produção

1. `alembic upgrade head` — migração **0017**, só cria tabela nova, retrocompatível.
2. Deploy normal, sem rebuild (nenhuma dependência nova).
3. Pré-requisito operacional: o aparelho precisa ter **modelo de certificado de Calibração** cadastrado, senão o botão responde 409 com a mensagem explicando.
