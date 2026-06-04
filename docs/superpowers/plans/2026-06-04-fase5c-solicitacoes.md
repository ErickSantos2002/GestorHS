# Fase 5C (Solicitar recalibração) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **GATE:** a migração 0003 só é aplicada no banco real (9998) na Task 6, com confirmação do usuário.

**Goal:** Cliente solicita recalibração pelo portal; o Comercial vê e atende internamente — fechando o laço alerta→cliente→OS.

**Architecture:** Backend — tabela nova `solicitacoes` (Alembic 0003) + modelo; endpoints de portal (`get_current_cliente`, escopados) e internos (`get_current_usuario`/`require_funcao`). Frontend — botão na Minha frota + página "Minhas solicitações" (portal) e página "Solicitações" (interno).

**Tech Stack:** Backend FastAPI/SQLAlchemy/Alembic/pytest; Frontend React 19/TS/Vite/Vitest.

**Spec:** `docs/superpowers/specs/2026-06-04-fase5c-solicitacoes-design.md`

**Comandos:** Backend Docker (`docker compose exec -T backend ...`). Frontend `npm --prefix frontend run test|lint|build`. Git via `git -C /d/GitHub/GestorHS`. Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

**Branch:** antes da Task 1:
```bash
git -C /d/GitHub/GestorHS checkout -b feat/fase5c-solicitacoes
```

## Convenções (já estabelecidas)
- Backend: Alembic em `backend/alembic/versions/` (revision/down_revision; `op.create_table`/`op.drop_table`). `app/api/portal.py` usa `get_current_cliente`; `agora()` em `app/api/ordens_acoes.py`. `require_funcao(*descricoes)` em deps. Modelos um-por-arquivo + `__init__`; relationships `lazy="joined"` + props. Testes pytest/SQLite (`create_all`); fixtures `cliente_portal` (empresa cgc="11222333000144" + usuário cliente1/portal123), `usuario_admin`/`usuario_comercial` (login `comercial`)/`usuario_lab` (login `lab`)/`usuario_comum` (login `comum`, Expedição).
- Frontend: `portal/api.ts`; `PortalFrotaPage` (5B); `PortalLayout` (nav); `portal/routes.tsx`. `app/<dominio>/api.ts` + página + `Sidebar.tsx` (NAV_ITEMS) + `app/routes.tsx`. `auth/roles.ts` (`isAdmin`, `FUNCAO_COMERCIAL`). Componentes `Table/Badge/Button/Spinner/Select`; `apiJson`/`apiVoid`. Lint: disable `react-hooks/set-state-in-effect` só na 1ª setState síncrona do efeito.

---

### Task 1: Tabela `solicitacoes` (modelo + migração 0003)

**Files:**
- Create: `backend/app/models/solicitacao.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/0003_solicitacoes.py`

> Sem teste pytest próprio (o modelo é exercido pelos endpoints nas Tasks 2–3, via SQLite `create_all`). A migração é verificada por `alembic history` (sem tocar no banco); aplicação no 9998 só na Task 6.

- [ ] **Step 1: Criar `backend/app/models/solicitacao.py`**

```python
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.models.database import Base


class Solicitacao(Base):
    __tablename__ = "solicitacoes"

    id = Column(Integer, primary_key=True, index=True)
    cliente = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    equipamento_cliente = Column(Integer, ForeignKey("equipamentos_cliente.id"), nullable=False)
    status = Column(String(20), nullable=False, default="pendente")
    data_solicitacao = Column(DateTime(timezone=True), nullable=True)
    data_atendimento = Column(DateTime(timezone=True), nullable=True)
    atendido_por = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    obs = Column(Text, nullable=True)

    cliente_rel = relationship("Cliente", lazy="joined")
    equipamento_rel = relationship("EquipamentoCliente", lazy="joined")
    atendente_rel = relationship("Usuario", lazy="joined")

    @property
    def cliente_nome(self):
        return self.cliente_rel.nome if self.cliente_rel else None

    @property
    def equipamento_descricao(self):
        return self.equipamento_rel.equipamento_descricao if self.equipamento_rel else None

    @property
    def atendido_por_nome(self):
        return self.atendente_rel.nome if self.atendente_rel else None
```

- [ ] **Step 2: Registrar em `backend/app/models/__init__.py`** — adicione `from app.models.solicitacao import Solicitacao` e inclua `"Solicitacao"` no `__all__`.

- [ ] **Step 3: Criar `backend/alembic/versions/0003_solicitacoes.py`**

```python
"""solicitacoes: pedidos de recalibracao do portal

Revision ID: 0003_solicitacoes
Revises: 0002_os_schema
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_solicitacoes"
down_revision = "0002_os_schema"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "solicitacoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cliente", sa.Integer(), sa.ForeignKey("clientes.id"), nullable=False),
        sa.Column("equipamento_cliente", sa.Integer(), sa.ForeignKey("equipamentos_cliente.id"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pendente"),
        sa.Column("data_solicitacao", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data_atendimento", sa.DateTime(timezone=True), nullable=True),
        sa.Column("atendido_por", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("obs", sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_table("solicitacoes")
```

- [ ] **Step 4: Verificar que a migração parseia/encadeia (sem tocar no banco)**

Run: `docker compose exec -T backend alembic history`
Expected: mostra `0002_os_schema -> 0003_solicitacoes (head)`. (Não rode `upgrade` — isso é a Task 6.)

- [ ] **Step 5: Verificar que o modelo importa**

Run: `docker compose exec -T backend python -c "from app.models import Solicitacao; print(Solicitacao.__tablename__)"`
Expected: `solicitacoes`.

- [ ] **Step 6: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/app/models/solicitacao.py backend/app/models/__init__.py backend/alembic/versions/0003_solicitacoes.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): modelo Solicitacao + migracao 0003 (nao aplicada)"
```

---

### Task 2: Endpoints do portal (solicitar + minhas-solicitacoes)

**Files:**
- Create: `backend/app/schemas/solicitacoes.py`
- Modify: `backend/app/api/portal.py`
- Test: `backend/tests/test_solicitacoes.py`

- [ ] **Step 1: Escrever os testes falhando** — `backend/tests/test_solicitacoes.py`:

```python
def _ph(client):
    tok = client.post("/auth/login-portal", json={"documento": "11222333000144", "login": "cliente1", "senha": "portal123"}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _aparelho(db_session, cliente_id):
    from app.models import Equipamento, EquipamentoCliente
    eq = Equipamento(descricao="Bafômetro")
    db_session.add(eq); db_session.flush()
    ec = EquipamentoCliente(cliente=cliente_id, equipamento=eq.id, serie="S1", ativo=True)
    db_session.add(ec); db_session.commit(); db_session.refresh(ec)
    return ec


def test_solicitar_cria_pendente(client, cliente_portal, db_session):
    ec = _aparelho(db_session, cliente_portal.cliente)
    r = client.post("/portal/solicitar-recalibracao", json={"equipamento_cliente": ec.id}, headers=_ph(client))
    assert r.status_code == 201
    assert r.json()["status"] == "pendente"
    assert r.json()["equipamento_cliente"] == ec.id


def test_solicitar_duplicada_409(client, cliente_portal, db_session):
    ec = _aparelho(db_session, cliente_portal.cliente)
    h = _ph(client)
    assert client.post("/portal/solicitar-recalibracao", json={"equipamento_cliente": ec.id}, headers=h).status_code == 201
    assert client.post("/portal/solicitar-recalibracao", json={"equipamento_cliente": ec.id}, headers=h).status_code == 409


def test_solicitar_aparelho_de_outro_cliente_404(client, cliente_portal, db_session):
    from app.models import Cliente, Equipamento, EquipamentoCliente
    outro = Cliente(nome="Outro")
    eq = Equipamento(descricao="B")
    db_session.add_all([outro, eq]); db_session.flush()
    ec = EquipamentoCliente(cliente=outro.id, equipamento=eq.id, ativo=True)
    db_session.add(ec); db_session.commit(); db_session.refresh(ec)
    r = client.post("/portal/solicitar-recalibracao", json={"equipamento_cliente": ec.id}, headers=_ph(client))
    assert r.status_code == 404


def test_minhas_solicitacoes(client, cliente_portal, db_session):
    ec = _aparelho(db_session, cliente_portal.cliente)
    client.post("/portal/solicitar-recalibracao", json={"equipamento_cliente": ec.id}, headers=_ph(client))
    r = client.get("/portal/minhas-solicitacoes", headers=_ph(client))
    assert r.status_code == 200
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["status"] == "pendente"


def test_minhas_solicitacoes_sem_token_401(client):
    assert client.get("/portal/minhas-solicitacoes").status_code == 401
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_solicitacoes.py -q`
Expected: FAIL (404 — endpoints não existem).

- [ ] **Step 3: Criar `backend/app/schemas/solicitacoes.py`**

```python
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class SolicitarIn(BaseModel):
    equipamento_cliente: int
    obs: str | None = None


class PortalSolicitacaoItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    equipamento_cliente: int
    equipamento_descricao: str | None = None
    status: str
    data_solicitacao: datetime | None = None
    data_atendimento: datetime | None = None


class PortalSolicitacaoPage(BaseModel):
    items: list[PortalSolicitacaoItem]
    total: int


class SolicitacaoItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cliente: int
    cliente_nome: str | None = None
    equipamento_cliente: int
    equipamento_descricao: str | None = None
    status: str
    data_solicitacao: datetime | None = None
    data_atendimento: datetime | None = None
    atendido_por: int | None = None
    atendido_por_nome: str | None = None
    obs: str | None = None


class SolicitacaoPage(BaseModel):
    items: list[SolicitacaoItem]
    total: int
```

- [ ] **Step 4: Adicionar os endpoints do portal em `backend/app/api/portal.py`**

Atualize os imports: `from fastapi import APIRouter, Depends, Query, HTTPException` (acrescente `HTTPException` se faltar); `from app.models import UsuarioCliente, Cliente, EquipamentoCliente, Ordem, Solicitacao` (acrescente `Solicitacao`); `from app.api.ordens_acoes import agora`; `from app.schemas.solicitacoes import SolicitarIn, PortalSolicitacaoItem, PortalSolicitacaoPage`. Acrescente ao fim:
```python
@router.post("/solicitar-recalibracao", response_model=PortalSolicitacaoItem, status_code=201)
def solicitar(dados: SolicitarIn, cli: UsuarioCliente = Depends(get_current_cliente), db: Session = Depends(get_db)):
    ec = (
        db.query(EquipamentoCliente)
        .filter(EquipamentoCliente.id == dados.equipamento_cliente, EquipamentoCliente.cliente == cli.cliente)
        .first()
    )
    if ec is None:
        raise HTTPException(status_code=404, detail="aparelho não encontrado")
    pendente = (
        db.query(Solicitacao)
        .filter(Solicitacao.equipamento_cliente == ec.id, Solicitacao.status == "pendente")
        .first()
    )
    if pendente is not None:
        raise HTTPException(status_code=409, detail="já há uma solicitação pendente para este aparelho")
    s = Solicitacao(cliente=cli.cliente, equipamento_cliente=ec.id, status="pendente", data_solicitacao=agora(), obs=dados.obs)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.get("/minhas-solicitacoes", response_model=PortalSolicitacaoPage)
def minhas_solicitacoes(
    offset: int = 0,
    limit: int = Query(25, ge=1, le=100),
    cli: UsuarioCliente = Depends(get_current_cliente),
    db: Session = Depends(get_db),
):
    query = db.query(Solicitacao).filter(Solicitacao.cliente == cli.cliente)
    total = query.count()
    items = query.order_by(Solicitacao.id.desc()).offset(offset).limit(limit).all()
    return PortalSolicitacaoPage(items=[PortalSolicitacaoItem.model_validate(s) for s in items], total=total)
```

- [ ] **Step 5: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_solicitacoes.py -q`
Expected: PASS (5 passed).

- [ ] **Step 6: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/app/schemas/solicitacoes.py backend/app/api/portal.py backend/tests/test_solicitacoes.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): portal solicitar-recalibracao + minhas-solicitacoes"
```

---

### Task 3: Endpoints internos (`/solicitacoes`)

**Files:**
- Create: `backend/app/api/solicitacoes.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_solicitacoes.py` (estender)

- [ ] **Step 1: Escrever os testes falhando** — acrescente ao FIM de `backend/tests/test_solicitacoes.py`:

```python
def _hdr(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _solic(db_session, cliente_portal):
    from app.models import Equipamento, EquipamentoCliente, Solicitacao
    from app.api.ordens_acoes import agora
    eq = Equipamento(descricao="Bafômetro")
    db_session.add(eq); db_session.flush()
    ec = EquipamentoCliente(cliente=cliente_portal.cliente, equipamento=eq.id, ativo=True)
    db_session.add(ec); db_session.flush()
    s = Solicitacao(cliente=cliente_portal.cliente, equipamento_cliente=ec.id, status="pendente", data_solicitacao=agora())
    db_session.add(s); db_session.commit(); db_session.refresh(s)
    return s


def test_listar_solicitacoes_interno(client, usuario_comum, cliente_portal, db_session):
    _solic(db_session, cliente_portal)
    r = client.get("/solicitacoes", headers=_hdr(client, "comum", "senha123"))
    assert r.status_code == 200
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["cliente_nome"] == "Cliente Teste"


def test_atender_comercial(client, usuario_comercial, cliente_portal, db_session):
    s = _solic(db_session, cliente_portal)
    r = client.post(f"/solicitacoes/{s.id}/atender", headers=_hdr(client, "comercial", "senha123"))
    assert r.status_code == 200
    assert r.json()["status"] == "atendida"
    assert r.json()["atendido_por_nome"] is not None


def test_atender_admin(client, usuario_admin, cliente_portal, db_session):
    s = _solic(db_session, cliente_portal)
    assert client.post(f"/solicitacoes/{s.id}/atender", headers=_hdr(client, "admin", "senha123")).json()["status"] == "atendida"


def test_atender_403(client, usuario_lab, cliente_portal, db_session):
    s = _solic(db_session, cliente_portal)
    assert client.post(f"/solicitacoes/{s.id}/atender", headers=_hdr(client, "lab", "senha123")).status_code == 403


def test_reatender_409(client, usuario_comercial, cliente_portal, db_session):
    s = _solic(db_session, cliente_portal)
    h = _hdr(client, "comercial", "senha123")
    client.post(f"/solicitacoes/{s.id}/atender", headers=h)
    assert client.post(f"/solicitacoes/{s.id}/atender", headers=h).status_code == 409


def test_atender_404(client, usuario_comercial, db_session):
    assert client.post("/solicitacoes/99999/atender", headers=_hdr(client, "comercial", "senha123")).status_code == 404
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_solicitacoes.py -q`
Expected: FAIL (404/405 — /solicitacoes não existe).

- [ ] **Step 3: Criar `backend/app/api/solicitacoes.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Solicitacao
from app.api.deps import get_current_usuario, require_funcao
from app.api.ordens_acoes import agora
from app.schemas.solicitacoes import SolicitacaoItem, SolicitacaoPage

router = APIRouter(prefix="/solicitacoes", tags=["solicitacoes"])


@router.get("", response_model=SolicitacaoPage)
def listar(
    status: str | None = None,
    offset: int = 0,
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_usuario),
):
    query = db.query(Solicitacao)
    if status:
        query = query.filter(Solicitacao.status == status)
    total = query.count()
    pendentes_primeiro = case((Solicitacao.status == "pendente", 0), else_=1)
    items = (
        query.order_by(pendentes_primeiro, Solicitacao.data_solicitacao.desc())
        .offset(offset).limit(limit).all()
    )
    return SolicitacaoPage(items=[SolicitacaoItem.model_validate(s) for s in items], total=total)


@router.post("/{solic_id}/atender", response_model=SolicitacaoItem)
def atender(
    solic_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_funcao("Comercial Pós-Vendas", "Administrador")),
):
    s = db.query(Solicitacao).filter(Solicitacao.id == solic_id).first()
    if s is None:
        raise HTTPException(status_code=404, detail="solicitação não encontrada")
    if s.status != "pendente":
        raise HTTPException(status_code=409, detail="solicitação já atendida")
    s.status = "atendida"
    s.atendido_por = usuario.id
    s.data_atendimento = agora()
    db.commit()
    db.refresh(s)
    return s
```

- [ ] **Step 4: Registrar o router em `backend/app/main.py`**

```python
from app.api import solicitacoes
app.include_router(solicitacoes.router)
```

- [ ] **Step 5: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_solicitacoes.py -q`
Expected: PASS (11 passed — 5 do portal + 6 internos).

- [ ] **Step 6: Rodar a suíte backend inteira**

Run: `docker compose exec -T backend python -m pytest -q`
Expected: verde (~160).

- [ ] **Step 7: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/app/api/solicitacoes.py backend/app/main.py backend/tests/test_solicitacoes.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): solicitacoes internas (listar + atender)"
```

---

### Task 4: Frontend portal (botão + Minhas solicitações)

**Files:**
- Modify: `frontend/src/portal/api.ts`
- Modify: `frontend/src/portal/PortalFrotaPage.tsx`
- Create: `frontend/src/portal/PortalSolicitacoesPage.tsx`
- Modify: `frontend/src/portal/PortalLayout.tsx`
- Modify: `frontend/src/portal/routes.tsx`
- Test: `frontend/src/portal/api.test.ts` (estender)

- [ ] **Step 1: Escrever os testes falhando** — acrescente ao FIM do describe em `frontend/src/portal/api.test.ts`:

```ts
  it('solicitar faz POST /portal/solicitar-recalibracao', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ id: 1, status: 'pendente' }, 201))
    vi.stubGlobal('fetch', f)
    await portalApi.solicitar({ equipamento_cliente: 7 })
    expect(String(f.mock.calls[0][0])).toContain('/portal/solicitar-recalibracao')
    expect(f.mock.calls[0][1]).toMatchObject({ method: 'POST' })
  })

  it('minhasSolicitacoes bate em /portal/minhas-solicitacoes', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ items: [], total: 0 }))
    vi.stubGlobal('fetch', f)
    await portalApi.minhasSolicitacoes({})
    expect(String(f.mock.calls[0][0])).toContain('/portal/minhas-solicitacoes')
  })
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm --prefix frontend run test -- portal/api`
Expected: FAIL (métodos ausentes).

- [ ] **Step 3: Estender `frontend/src/portal/api.ts`** — acrescente ao fim (tipos + mapa) e os 2 métodos em `portalApi`:

```ts
export const STATUS_SOLIC: Record<string, { label: string; tone: 'warning' | 'primary' }> = {
  pendente: { label: 'Pendente', tone: 'warning' },
  atendida: { label: 'Atendida', tone: 'primary' },
}

export interface PortalSolicitacaoItem {
  id: number
  equipamento_cliente: number
  equipamento_descricao: string | null
  status: string
  data_solicitacao: string | null
  data_atendimento: string | null
}
export interface PortalSolicitacaoPage { items: PortalSolicitacaoItem[]; total: number }
```
Em `portalApi`:
```ts
  solicitar: (payload: { equipamento_cliente: number; obs?: string }): Promise<PortalSolicitacaoItem> =>
    apiJson<PortalSolicitacaoItem>('/portal/solicitar-recalibracao', { method: 'POST', body: JSON.stringify(payload) }),
  minhasSolicitacoes: (params: { offset?: number; limit?: number } = {}): Promise<PortalSolicitacaoPage> => {
    const sp = new URLSearchParams()
    sp.set('offset', String(params.offset ?? 0))
    sp.set('limit', String(params.limit ?? 25))
    return apiJson<PortalSolicitacaoPage>(`/portal/minhas-solicitacoes?${sp.toString()}`)
  },
```

- [ ] **Step 4: Rodar e ver passar**

Run: `npm --prefix frontend run test -- portal/api`
Expected: PASS.

- [ ] **Step 5: Reescrever `frontend/src/portal/PortalFrotaPage.tsx`** com a coluna de ação "Solicitar" (conteúdo completo):

```tsx
import { useEffect, useState, type FormEvent } from 'react'
import { Table, TH, TD } from '../components/ui/Table'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { Spinner } from '../components/ui/Spinner'
import { Input } from '../components/ui/Input'
import { Select } from '../components/ui/Select'
import { ApiError } from '../lib/api'
import { portalApi, STATUS_CALIB, formatData, type PortalFrotaItem } from './api'

const LIMITE = 25

export function PortalFrotaPage() {
  const [status, setStatus] = useState('')
  const [termo, setTermo] = useState('')
  const [busca, setBusca] = useState('')
  const [offset, setOffset] = useState(0)
  const [itens, setItens] = useState<PortalFrotaItem[] | null>(null)
  const [total, setTotal] = useState(0)
  const [erro, setErro] = useState('')
  const [aviso, setAviso] = useState('')

  useEffect(() => {
    let ativo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setItens(null)
    setErro('')
    portalApi.minhaFrota({ status: status || undefined, q: busca || undefined, offset, limit: LIMITE })
      .then((p) => { if (!ativo) return; setItens(p.items); setTotal(p.total) })
      .catch((e) => { if (!ativo) return; setErro(e instanceof ApiError ? e.message : 'Falha ao carregar'); setItens([]) })
    return () => { ativo = false }
  }, [status, busca, offset])

  function onBuscar(e: FormEvent) { e.preventDefault(); setOffset(0); setBusca(termo.trim()) }

  async function solicitar(item: PortalFrotaItem) {
    if (!window.confirm('Solicitar recalibração deste aparelho?')) return
    setAviso(''); setErro('')
    try {
      await portalApi.solicitar({ equipamento_cliente: item.id })
      setAviso(`Solicitação enviada para ${item.equipamento_descricao ?? 'o aparelho'}.`)
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao solicitar')
    }
  }

  const inicio = total === 0 ? 0 : offset + 1
  const fim = Math.min(offset + LIMITE, total)

  return (
    <div className="px-4 md:px-6 py-6 space-y-6">
      <h1 className="text-2xl font-extrabold text-slate-100">Minha frota</h1>
      <div className="flex flex-wrap gap-2 items-end">
        <div className="w-48">
          <Select id="status" label="Status" value={status} onChange={(e) => { setOffset(0); setStatus(e.target.value) }}>
            <option value="">Todos</option>
            <option value="em_dia">Em dia</option>
            <option value="vencendo">Vencendo</option>
            <option value="vencido">Vencido</option>
            <option value="sem_data">Sem data</option>
          </Select>
        </div>
        <form onSubmit={onBuscar} className="flex gap-2 items-end flex-1 min-w-60">
          <div className="flex-1"><Input id="busca" label="Busca" placeholder="Série ou patrimônio" value={termo} onChange={(e) => setTermo(e.target.value)} /></div>
          <Button type="submit" variant="secondary">Buscar</Button>
        </form>
      </div>
      {aviso && <div className="rounded-lg bg-primary/10 border border-primary/20 px-3 py-2.5 text-sm text-primary">{aviso}</div>}
      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      {itens === null ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum aparelho encontrado.</p>
      ) : (
        <>
          <Table head={<><TH>Aparelho</TH><TH>Série / Patrimônio</TH><TH>Próx. calibração</TH><TH>Status</TH><TH>Ações</TH></>}>
            {itens.map((e) => {
              const s = STATUS_CALIB[e.status_calibracao] ?? STATUS_CALIB.sem_data
              return (
                <tr key={e.id} className="hover:bg-background-elevated transition-colors">
                  <TD>{e.equipamento_descricao ?? '—'}</TD>
                  <TD>{e.serie || e.patrimonio || '—'}</TD>
                  <TD>{formatData(e.prox_calibragem)}</TD>
                  <TD><Badge tone={s.tone}>{s.label}</Badge></TD>
                  <TD><button onClick={() => solicitar(e)} className="text-xs text-primary hover:underline">Solicitar recalibração</button></TD>
                </tr>
              )
            })}
          </Table>
          <div className="flex items-center justify-between text-sm text-slate-400">
            <span>{inicio}–{fim} de {total}</span>
            <div className="flex gap-2">
              <Button variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - LIMITE))}>Anterior</Button>
              <Button variant="secondary" disabled={fim >= total} onClick={() => setOffset(offset + LIMITE)}>Próxima</Button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
```

- [ ] **Step 6: Criar `frontend/src/portal/PortalSolicitacoesPage.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { Table, TH, TD } from '../components/ui/Table'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { Spinner } from '../components/ui/Spinner'
import { ApiError } from '../lib/api'
import { portalApi, STATUS_SOLIC, formatData, type PortalSolicitacaoItem } from './api'

const LIMITE = 25

export function PortalSolicitacoesPage() {
  const [offset, setOffset] = useState(0)
  const [itens, setItens] = useState<PortalSolicitacaoItem[] | null>(null)
  const [total, setTotal] = useState(0)
  const [erro, setErro] = useState('')

  useEffect(() => {
    let ativo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setItens(null)
    setErro('')
    portalApi.minhasSolicitacoes({ offset, limit: LIMITE })
      .then((p) => { if (!ativo) return; setItens(p.items); setTotal(p.total) })
      .catch((e) => { if (!ativo) return; setErro(e instanceof ApiError ? e.message : 'Falha ao carregar'); setItens([]) })
    return () => { ativo = false }
  }, [offset])

  const inicio = total === 0 ? 0 : offset + 1
  const fim = Math.min(offset + LIMITE, total)

  return (
    <div className="px-4 md:px-6 py-6 space-y-6">
      <h1 className="text-2xl font-extrabold text-slate-100">Minhas solicitações</h1>
      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      {itens === null ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhuma solicitação.</p>
      ) : (
        <>
          <Table head={<><TH>Aparelho</TH><TH>Data</TH><TH>Status</TH></>}>
            {itens.map((s) => {
              const st = STATUS_SOLIC[s.status] ?? STATUS_SOLIC.pendente
              return (
                <tr key={s.id} className="hover:bg-background-elevated transition-colors">
                  <TD>{s.equipamento_descricao ?? '—'}</TD>
                  <TD>{formatData(s.data_solicitacao)}</TD>
                  <TD><Badge tone={st.tone}>{st.label}</Badge></TD>
                </tr>
              )
            })}
          </Table>
          <div className="flex items-center justify-between text-sm text-slate-400">
            <span>{inicio}–{fim} de {total}</span>
            <div className="flex gap-2">
              <Button variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - LIMITE))}>Anterior</Button>
              <Button variant="secondary" disabled={fim >= total} onClick={() => setOffset(offset + LIMITE)}>Próxima</Button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
```

- [ ] **Step 7: Adicionar a nav "Solicitações" em `frontend/src/portal/PortalLayout.tsx`** — no array `NAV`, após "Minhas OS":
```tsx
  { label: 'Solicitações', to: '/portal/solicitacoes' },
```

- [ ] **Step 8: Adicionar a rota em `frontend/src/portal/routes.tsx`** — importe `PortalSolicitacoesPage` e adicione dentro do `<Routes>` interno (junto das outras):
```tsx
                  <Route path="solicitacoes" element={<PortalSolicitacoesPage />} />
```

- [ ] **Step 9: Verificar lint + build**

Run: `npm --prefix frontend run lint` (sem erros) e `npm --prefix frontend run build` (limpo).

- [ ] **Step 10: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/portal/api.ts frontend/src/portal/api.test.ts frontend/src/portal/PortalFrotaPage.tsx frontend/src/portal/PortalSolicitacoesPage.tsx frontend/src/portal/PortalLayout.tsx frontend/src/portal/routes.tsx
git -C /d/GitHub/GestorHS commit -m "feat(frontend): portal solicitar recalibracao + pagina Minhas solicitacoes"
```

---

### Task 5: Frontend interno (página Solicitações)

**Files:**
- Create: `frontend/src/app/solicitacoes/api.ts`
- Create: `frontend/src/app/solicitacoes/SolicitacoesPage.tsx`
- Modify: `frontend/src/auth/roles.ts`
- Modify: `frontend/src/components/ui/icons.tsx` (`IconSolicitacoes`)
- Modify: `frontend/src/layout/Sidebar.tsx`
- Modify: `frontend/src/app/routes.tsx`
- Test: `frontend/src/app/solicitacoes/api.test.ts`
- Test: `frontend/src/auth/roles.test.ts` (estender)

- [ ] **Step 1: Escrever os testes falhando**

`frontend/src/app/solicitacoes/api.test.ts`:
```ts
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { solicitacoesApi } from './api'
import { setTokens } from '../../lib/auth-storage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('app/solicitacoes/api', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    setTokens({ access_token: 't', refresh_token: 'r' })
  })

  it('listar monta a query (status/offset/limit)', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ items: [], total: 0 }))
    vi.stubGlobal('fetch', f)
    await solicitacoesApi.listar({ status: 'pendente', offset: 25, limit: 25 })
    const url = String(f.mock.calls[0][0])
    expect(url).toContain('/solicitacoes?')
    expect(url).toContain('status=pendente')
  })

  it('atender faz POST /solicitacoes/{id}/atender', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ id: 1, status: 'atendida' }))
    vi.stubGlobal('fetch', f)
    await solicitacoesApi.atender(1)
    expect(String(f.mock.calls[0][0])).toContain('/solicitacoes/1/atender')
    expect(f.mock.calls[0][1]).toMatchObject({ method: 'POST' })
  })
})
```
E em `frontend/src/auth/roles.test.ts`, acrescente ao fim do describe (e inclua `podeAtenderSolicitacao` no import do topo, junto de `podeRegistrarContato`):
```ts
  it('podeAtenderSolicitacao: admin e Comercial sim, outros não', () => {
    expect(podeAtenderSolicitacao(u('Administrador'))).toBe(true)
    expect(podeAtenderSolicitacao(u('Comercial Pós-Vendas'))).toBe(true)
    expect(podeAtenderSolicitacao(u('Laboratório'))).toBe(false)
    expect(podeAtenderSolicitacao(null)).toBe(false)
  })
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm --prefix frontend run test -- solicitacoes/api auth/roles`
Expected: FAIL (módulo/função ausentes).

- [ ] **Step 3: Criar `frontend/src/app/solicitacoes/api.ts`**

```ts
import { apiJson } from '../../lib/api'

export function formatData(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return isNaN(d.getTime()) ? '—' : d.toLocaleDateString('pt-BR')
}

export const STATUS_SOLIC: Record<string, { label: string; tone: 'warning' | 'primary' }> = {
  pendente: { label: 'Pendente', tone: 'warning' },
  atendida: { label: 'Atendida', tone: 'primary' },
}

export interface SolicitacaoItem {
  id: number
  cliente: number
  cliente_nome: string | null
  equipamento_cliente: number
  equipamento_descricao: string | null
  status: string
  data_solicitacao: string | null
  data_atendimento: string | null
  atendido_por: number | null
  atendido_por_nome: string | null
  obs: string | null
}
export interface SolicitacaoPage { items: SolicitacaoItem[]; total: number }

export const solicitacoesApi = {
  listar: (params: { status?: string; offset?: number; limit?: number } = {}): Promise<SolicitacaoPage> => {
    const sp = new URLSearchParams()
    if (params.status) sp.set('status', params.status)
    sp.set('offset', String(params.offset ?? 0))
    sp.set('limit', String(params.limit ?? 25))
    return apiJson<SolicitacaoPage>(`/solicitacoes?${sp.toString()}`)
  },
  atender: (id: number): Promise<SolicitacaoItem> =>
    apiJson<SolicitacaoItem>(`/solicitacoes/${id}/atender`, { method: 'POST' }),
}
```

- [ ] **Step 4: Estender `frontend/src/auth/roles.ts`** (no fim):

```ts
export function podeAtenderSolicitacao(user: User | null): boolean {
  return isAdmin(user) || user?.funcao === FUNCAO_COMERCIAL
}
```

- [ ] **Step 5: Adicionar `IconSolicitacoes` em `frontend/src/components/ui/icons.tsx`**

```tsx
export function IconSolicitacoes({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 10h8M8 14h5m-5 7l-4-4h12a3 3 0 003-3V7a3 3 0 00-3-3H6a3 3 0 00-3 3v14z" />
    </svg>
  )
}
```

- [ ] **Step 6: Adicionar nav em `frontend/src/layout/Sidebar.tsx`** — importe `IconSolicitacoes` e adicione ao `NAV_ITEMS` (após Cobrança, sem `adminOnly`):
```tsx
  { label: 'Solicitações', icon: <IconSolicitacoes />, to: '/app/solicitacoes' },
```

- [ ] **Step 7: Criar `frontend/src/app/solicitacoes/SolicitacoesPage.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Spinner } from '../../components/ui/Spinner'
import { Select } from '../../components/ui/Select'
import { ApiError } from '../../lib/api'
import { useAuth } from '../../auth/AuthContext'
import { podeAtenderSolicitacao } from '../../auth/roles'
import { solicitacoesApi, STATUS_SOLIC, formatData, type SolicitacaoItem } from './api'

const LIMITE = 25

export function SolicitacoesPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const podeAtender = podeAtenderSolicitacao(user)
  const [status, setStatus] = useState('pendente')
  const [offset, setOffset] = useState(0)
  const [itens, setItens] = useState<SolicitacaoItem[] | null>(null)
  const [total, setTotal] = useState(0)
  const [erro, setErro] = useState('')

  useEffect(() => {
    let ativo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setItens(null)
    setErro('')
    solicitacoesApi.listar({ status: status || undefined, offset, limit: LIMITE })
      .then((p) => { if (!ativo) return; setItens(p.items); setTotal(p.total) })
      .catch((e) => { if (!ativo) return; setErro(e instanceof ApiError ? e.message : 'Falha ao carregar'); setItens([]) })
    return () => { ativo = false }
  }, [status, offset])

  async function atender(item: SolicitacaoItem) {
    setErro('')
    try {
      const atualizada = await solicitacoesApi.atender(item.id)
      setItens((prev) => prev?.map((i) => (i.id === atualizada.id ? atualizada : i)) ?? prev)
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao atender')
    }
  }

  const inicio = total === 0 ? 0 : offset + 1
  const fim = Math.min(offset + LIMITE, total)

  return (
    <div className="px-4 md:px-6 py-6 space-y-6">
      <h1 className="text-2xl font-extrabold text-slate-100">Solicitações</h1>
      <div className="w-52">
        <Select id="status" label="Status" value={status} onChange={(e) => { setOffset(0); setStatus(e.target.value) }}>
          <option value="">Todas</option>
          <option value="pendente">Pendentes</option>
          <option value="atendida">Atendidas</option>
        </Select>
      </div>
      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      {itens === null ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhuma solicitação.</p>
      ) : (
        <>
          <Table head={<><TH>Cliente</TH><TH>Aparelho</TH><TH>Data</TH><TH>Status</TH><TH>Atendido por</TH><TH>Ações</TH></>}>
            {itens.map((s) => {
              const st = STATUS_SOLIC[s.status] ?? STATUS_SOLIC.pendente
              return (
                <tr key={s.id} className="hover:bg-background-elevated transition-colors">
                  <TD>{s.cliente_nome ?? `#${s.cliente}`}</TD>
                  <TD>{s.equipamento_descricao ?? '—'}</TD>
                  <TD>{formatData(s.data_solicitacao)}</TD>
                  <TD><Badge tone={st.tone}>{st.label}</Badge></TD>
                  <TD>{s.atendido_por_nome ?? '—'}</TD>
                  <TD>
                    <div className="flex gap-3">
                      <button onClick={() => navigate(`/app/frota?cliente=${s.cliente}`)} className="text-xs text-primary hover:underline">Ver frota</button>
                      {podeAtender && s.status === 'pendente' && (
                        <button onClick={() => atender(s)} className="text-xs text-primary hover:underline">Marcar como atendida</button>
                      )}
                    </div>
                  </TD>
                </tr>
              )
            })}
          </Table>
          <div className="flex items-center justify-between text-sm text-slate-400">
            <span>{inicio}–{fim} de {total}</span>
            <div className="flex gap-2">
              <Button variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - LIMITE))}>Anterior</Button>
              <Button variant="secondary" disabled={fim >= total} onClick={() => setOffset(offset + LIMITE)}>Próxima</Button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
```

- [ ] **Step 8: Registrar a rota em `frontend/src/app/routes.tsx`**

```tsx
import { SolicitacoesPage } from './solicitacoes/SolicitacoesPage'
```
```tsx
        <Route path="solicitacoes" element={<SolicitacoesPage />} />
```

- [ ] **Step 9: Rodar testes + lint + build**

Run: `npm --prefix frontend run test -- solicitacoes/api auth/roles` → PASS.
Run: `npm --prefix frontend run lint` (sem erros) e `npm --prefix frontend run build` (limpo).

- [ ] **Step 10: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/app/solicitacoes/api.ts frontend/src/app/solicitacoes/SolicitacoesPage.tsx frontend/src/app/solicitacoes/api.test.ts frontend/src/auth/roles.ts frontend/src/auth/roles.test.ts frontend/src/components/ui/icons.tsx frontend/src/layout/Sidebar.tsx frontend/src/app/routes.tsx
git -C /d/GitHub/GestorHS commit -m "feat(frontend): pagina interna Solicitacoes + atender + nav"
```

---

### Task 6: Aplicar migração 0003 no 9998 + verificação final

**Files:** nenhum (operação de banco + verificação).

- [ ] **Step 1: Suíte completa (SQLite, não precisa da migração aplicada)**

Run: `docker compose exec -T backend python -m pytest -q` → ~160 passed.
Run: `npm --prefix frontend run test` → ~83 passed.
Run: `npm --prefix frontend run lint` (limpo) e `npm --prefix frontend run build` (limpo).

- [ ] **Step 2: [GATE] Aplicar a migração 0003 no banco real** — *só após confirmação do usuário pelo controlador.*

Run: `docker compose exec -T backend alembic upgrade head`
Expected: `Running upgrade 0002_os_schema -> 0003_solicitacoes`.
Verificar: `docker compose exec -T backend python -c "import psycopg2,os; c=psycopg2.connect(os.environ['DATABASE_URL'].replace('postgresql+psycopg2','postgresql')); cur=c.cursor(); cur.execute(\"SELECT 1 FROM information_schema.tables WHERE table_name='solicitacoes'\"); print('solicitacoes existe:', cur.fetchone() is not None); c.close()"`
Expected: `solicitacoes existe: True`.

- [ ] **Step 3: (sem commit — verificação/operação)** Reporte os números e a confirmação da migração.

---

## Notas para o executor
- A migração 0003 **não** é aplicada no banco real até a Task 6 Step 2, e só com confirmação do usuário (o controlador faz o gate). Os testes pytest usam SQLite via `create_all`, então passam sem a migração aplicada.
- Portal: `solicitar` valida que o aparelho é do cliente do token (404 senão) e bloqueia 2ª pendente (409). Interno: `atender` só Comercial/Admin; pendentes aparecem primeiro na lista.
- `atender` NÃO cria OS (a OS nasce quando o aparelho chega, via Frota/Abrir OS).
- Após a Task 6, o controlador faz o E2E (cliente de teste: solicita no portal → atende no /app), e **remove as solicitações + o usuário-cliente de teste** ao fim.
```
