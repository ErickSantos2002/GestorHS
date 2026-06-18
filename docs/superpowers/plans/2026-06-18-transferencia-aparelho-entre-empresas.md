# Transferência de aparelho entre empresas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir transferir um aparelho (`equipamento_cliente`) de uma empresa para outra, com auditoria, bloqueando se houver OS ativa.

**Architecture:** Endpoint dedicado `POST /equipamentos-cliente/{id}/transferir` (Admin) que valida, troca `equipamento_cliente.cliente`, zera `os_atual` e grava uma linha numa nova tabela de auditoria `transferencias_equipamento`. As OS antigas (que têm `cliente` próprio) permanecem com a empresa antiga. Frontend: botão + modal com busca de empresa, e uma seção "Transferências" na ficha.

**Tech Stack:** Backend FastAPI + SQLAlchemy 2 + Alembic + Pydantic v2 (pytest em Docker). Frontend React 19 + TS + Vitest. Commits: PT-BR sem acentos, uma linha, sem co-autor; tipos feat/fix/docs/refactor.

**Spec:** [docs/superpowers/specs/2026-06-18-transferencia-aparelho-entre-empresas-design.md](../specs/2026-06-18-transferencia-aparelho-entre-empresas-design.md)

## Ambiente de teste
- Backend (sem venv local): `docker compose exec -T backend pytest <args>` a partir da raiz.
- Frontend (de `frontend/`): `npx vitest run`, `npx tsc -b --noEmit`, `npm run lint`, `npm run build`.

---

## File Structure
- **Create** `backend/app/models/transferencia_equipamento.py` — modelo + relationships/props de nome.
- **Modify** `backend/app/models/__init__.py` — registrar o modelo.
- **Create** `backend/alembic/versions/0009_transferencias_equipamento.py` — migração da tabela.
- **Modify** `backend/app/schemas/frota.py` — `TransferirIn`, `TransferenciaOut`.
- **Modify** `backend/app/api/equipamentos_cliente.py` — endpoints `transferir` e `transferencias`.
- **Create** `backend/tests/test_frota_transferencia.py` — testes.
- **Modify** `frontend/src/app/frota/api.ts` — tipo `Transferencia` + métodos `transferir`/`transferencias`.
- **Create** `frontend/src/app/frota/TransferirModal.tsx` — modal de transferência (busca de empresa).
- **Modify** `frontend/src/app/frota/EquipamentoClienteDetailPage.tsx` — botão, modal, seção "Transferências".
- **Modify** `frontend/src/app/changelog/data.ts` — nova versão.

---

## Task 1: Modelo `TransferenciaEquipamento` + migração 0009

**Files:**
- Create: `backend/app/models/transferencia_equipamento.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/0009_transferencias_equipamento.py`

- [ ] **Step 1: Criar o modelo**

`backend/app/models/transferencia_equipamento.py`:
```python
from sqlalchemy import Column, Integer, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship

from app.models.database import Base


class TransferenciaEquipamento(Base):
    __tablename__ = "transferencias_equipamento"

    id = Column(Integer, primary_key=True, index=True)
    equipamento_cliente = Column(Integer, ForeignKey("equipamentos_cliente.id"), nullable=False)
    de_cliente = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    para_cliente = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    data = Column(DateTime(timezone=True), nullable=False)
    usuario = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    obs = Column(Text, nullable=True)

    de_rel = relationship("Cliente", foreign_keys=[de_cliente], lazy="joined")
    para_rel = relationship("Cliente", foreign_keys=[para_cliente], lazy="joined")
    usuario_rel = relationship("Usuario", lazy="joined")

    @property
    def de_cliente_nome(self):
        return self.de_rel.nome if self.de_rel else None

    @property
    def para_cliente_nome(self):
        return self.para_rel.nome if self.para_rel else None

    @property
    def usuario_nome(self):
        return self.usuario_rel.nome if self.usuario_rel else None
```

- [ ] **Step 2: Registrar no `models/__init__.py`**

Adicionar o import (após a linha `from app.models.os_certificado import OSCertificado`):
```python
from app.models.transferencia_equipamento import TransferenciaEquipamento
```
E adicionar `"TransferenciaEquipamento"` ao final da lista `__all__`.

- [ ] **Step 3: Criar a migração 0009**

`backend/alembic/versions/0009_transferencias_equipamento.py`:
```python
"""transferencias_equipamento — auditoria de transferencia de aparelho entre empresas

Revision ID: 0009_transferencias_equipamento
Revises: 0008_cert_overrides
Create Date: 2026-06-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_transferencias_equipamento"
down_revision = "0008_cert_overrides"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "transferencias_equipamento",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("equipamento_cliente", sa.Integer(), sa.ForeignKey("equipamentos_cliente.id"), nullable=False),
        sa.Column("de_cliente", sa.Integer(), sa.ForeignKey("clientes.id"), nullable=False),
        sa.Column("para_cliente", sa.Integer(), sa.ForeignKey("clientes.id"), nullable=False),
        sa.Column("data", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usuario", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("obs", sa.Text(), nullable=True),
    )
    op.create_index("ix_transferencias_equipamento_id", "transferencias_equipamento", ["id"])


def downgrade():
    op.drop_index("ix_transferencias_equipamento_id", table_name="transferencias_equipamento")
    op.drop_table("transferencias_equipamento")
```

- [ ] **Step 4: Verificar import + criação da tabela em memória**

Run: `docker compose exec -T backend python -c "from app.models import TransferenciaEquipamento; from app.models.database import Base; print('transferencias_equipamento' in Base.metadata.tables)"`
Expected: imprime `True`.

- [ ] **Step 5: Commit**

```bash
cd /home/ericks/github/GestorHS
git add backend/app/models/transferencia_equipamento.py backend/app/models/__init__.py backend/alembic/versions/0009_transferencias_equipamento.py
git commit -m "feat(frota): modelo e migracao de transferencias_equipamento"
```

---

## Task 2: Schemas + endpoints `transferir` e `transferencias` + testes

**Files:**
- Modify: `backend/app/schemas/frota.py`
- Modify: `backend/app/api/equipamentos_cliente.py`
- Test: `backend/tests/test_frota_transferencia.py`

- [ ] **Step 1: Escrever os testes (falham primeiro)**

`backend/tests/test_frota_transferencia.py`:
```python
def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _cliente(db_session, nome):
    from app.models import Cliente
    c = Cliente(nome=nome)
    db_session.add(c); db_session.commit(); db_session.refresh(c)
    return c.id


def _ordem(db_session, cliente, equipamento_cliente, fase):
    from app.models import Ordem
    o = Ordem(cliente=cliente, equipamento_cliente=equipamento_cliente, fase=fase, situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    return o.id


def test_transferir_muda_dono_zera_os_atual_e_registra(
    client, usuario_admin, os_base, db_session
):
    from app.models import EquipamentoCliente
    ec = db_session.get(EquipamentoCliente, os_base["equipamento_cliente"])
    ec.os_atual = 12345
    db_session.commit()
    destino = _cliente(db_session, "Empresa Nova")
    h = _headers(client, "admin", "senha123")

    r = client.post(f"/equipamentos-cliente/{os_base['equipamento_cliente']}/transferir",
                    json={"cliente": destino, "obs": "venda"}, headers=h)
    assert r.status_code == 200
    assert r.json()["cliente"] == destino

    db_session.refresh(ec)
    assert ec.cliente == destino
    assert ec.os_atual is None

    trs = client.get(f"/equipamentos-cliente/{os_base['equipamento_cliente']}/transferencias", headers=h).json()
    assert len(trs) == 1
    assert trs[0]["de_cliente"] == os_base["cliente"]
    assert trs[0]["para_cliente"] == destino
    assert trs[0]["para_cliente_nome"] == "Empresa Nova"
    assert trs[0]["usuario_nome"] == "Admin"
    assert trs[0]["obs"] == "venda"


def test_transferir_bloqueia_com_os_ativa_409(client, usuario_admin, fases_seed, os_base, db_session):
    destino = _cliente(db_session, "Destino")
    _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 5)  # ativa
    h = _headers(client, "admin", "senha123")
    r = client.post(f"/equipamentos-cliente/{os_base['equipamento_cliente']}/transferir",
                    json={"cliente": destino}, headers=h)
    assert r.status_code == 409


def test_transferir_destino_inexistente_404(client, usuario_admin, os_base):
    h = _headers(client, "admin", "senha123")
    r = client.post(f"/equipamentos-cliente/{os_base['equipamento_cliente']}/transferir",
                    json={"cliente": 99999}, headers=h)
    assert r.status_code == 404


def test_transferir_mesmo_cliente_400(client, usuario_admin, os_base):
    h = _headers(client, "admin", "senha123")
    r = client.post(f"/equipamentos-cliente/{os_base['equipamento_cliente']}/transferir",
                    json={"cliente": os_base["cliente"]}, headers=h)
    assert r.status_code == 400


def test_transferir_exige_admin_403(client, usuario_lab, os_base, db_session):
    destino = _cliente(db_session, "Destino")
    h = _headers(client, "lab", "senha123")
    r = client.post(f"/equipamentos-cliente/{os_base['equipamento_cliente']}/transferir",
                    json={"cliente": destino}, headers=h)
    assert r.status_code == 403


def test_os_antiga_mantem_cliente_antigo(client, usuario_admin, fases_seed, os_base, db_session):
    from app.models import Ordem
    oid = _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 8)  # finalizada
    destino = _cliente(db_session, "Empresa Nova")
    h = _headers(client, "admin", "senha123")
    client.post(f"/equipamentos-cliente/{os_base['equipamento_cliente']}/transferir",
                json={"cliente": destino}, headers=h)
    db_session.expire_all()
    assert db_session.get(Ordem, oid).cliente == os_base["cliente"]  # OS antiga: dono antigo
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `docker compose exec -T backend pytest tests/test_frota_transferencia.py -q`
Expected: FAIL (rota inexistente → 405/404).

- [ ] **Step 3: Adicionar os schemas em `backend/app/schemas/frota.py`**

No fim do arquivo:
```python
class TransferirIn(BaseModel):
    cliente: int
    obs: Optional[str] = None


class TransferenciaOut(BaseModel):
    id: int
    equipamento_cliente: int
    de_cliente: int
    de_cliente_nome: Optional[str] = None
    para_cliente: int
    para_cliente_nome: Optional[str] = None
    usuario: Optional[int] = None
    usuario_nome: Optional[str] = None
    data: datetime
    obs: Optional[str] = None
    model_config = {"from_attributes": True}
```
(`Optional`, `datetime`, `BaseModel` já estão importados no topo do arquivo.)

- [ ] **Step 4: Atualizar imports de `backend/app/api/equipamentos_cliente.py`**

Trocar a linha de import de models e a de schemas, e adicionar os helpers:
```python
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, status as http_status, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, EquipamentoCliente, HistoricoEquipamento, Ordem, OSCertificado, Cliente, TransferenciaEquipamento
from app.api.deps import get_current_usuario, require_funcao
from app.api.cadastros_common import excluir_protegido
from app.api.ordens_acoes import agora
from app.core import os_workflow as wf
from app.schemas.frota import (
    FrotaListOut, FrotaPage, EquipamentoClienteOut,
    EquipamentoClienteCreate, EquipamentoClienteUpdate, HistoricoOut, EquipCertItem,
    TransferirIn, TransferenciaOut,
)
from app.schemas.ordens import OrdemListOut
```

- [ ] **Step 5: Adicionar os dois endpoints**

No fim de `backend/app/api/equipamentos_cliente.py` (após `excluir`):
```python
@router.post("/{item_id}/transferir", response_model=EquipamentoClienteOut)
def transferir(item_id: int, dados: TransferirIn, db: Session = Depends(get_db),
               usuario: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(EquipamentoCliente).filter(EquipamentoCliente.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    destino = db.query(Cliente).filter(Cliente.id == dados.cliente).first()
    if destino is None:
        raise HTTPException(status_code=404, detail="cliente destino não encontrado")
    if destino.id == obj.cliente:
        raise HTTPException(status_code=400, detail="aparelho já pertence a este cliente")
    ativa = (
        db.query(Ordem)
        .filter(Ordem.equipamento_cliente == obj.id, Ordem.fase.in_(wf.ATIVAS))
        .first()
    )
    if ativa is not None:
        raise HTTPException(status_code=409, detail="finalize ou cancele a OS ativa antes de transferir")
    db.add(TransferenciaEquipamento(
        equipamento_cliente=obj.id,
        de_cliente=obj.cliente,
        para_cliente=destino.id,
        data=agora(),
        usuario=usuario.id,
        obs=dados.obs,
    ))
    obj.cliente = destino.id
    obj.os_atual = None
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{item_id}/transferencias", response_model=list[TransferenciaOut])
def transferencias(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    if db.query(EquipamentoCliente).filter(EquipamentoCliente.id == item_id).first() is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    return (
        db.query(TransferenciaEquipamento)
        .filter(TransferenciaEquipamento.equipamento_cliente == item_id)
        .order_by(TransferenciaEquipamento.data.desc(), TransferenciaEquipamento.id.desc())
        .all()
    )
```

- [ ] **Step 6: Rodar os testes do arquivo — devem passar**

Run: `docker compose exec -T backend pytest tests/test_frota_transferencia.py -q`
Expected: PASS (6 testes).

- [ ] **Step 7: Suíte completa de backend**

Run: `docker compose exec -T backend pytest -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
cd /home/ericks/github/GestorHS
git add backend/app/schemas/frota.py backend/app/api/equipamentos_cliente.py backend/tests/test_frota_transferencia.py
git commit -m "feat(frota): endpoints de transferir aparelho e listar transferencias"
```

---

## Task 3: Frontend — tipos e métodos de API

**Files:**
- Modify: `frontend/src/app/frota/api.ts`

- [ ] **Step 1: Adicionar o tipo `Transferencia`**

Após a interface `EquipCertItem` (que termina por volta da linha 83), adicionar:
```ts
export interface Transferencia {
  id: number
  equipamento_cliente: number
  de_cliente: number
  de_cliente_nome: string | null
  para_cliente: number
  para_cliente_nome: string | null
  usuario: number | null
  usuario_nome: string | null
  data: string
  obs: string | null
}
```

- [ ] **Step 2: Adicionar os métodos no `equipamentosClienteApi`**

Dentro do objeto `equipamentosClienteApi`, após `certificados:` (linha ~123), adicionar:
```ts
  transferencias: (id: number): Promise<Transferencia[]> => apiJson<Transferencia[]>(`/equipamentos-cliente/${id}/transferencias`),
  transferir: (id: number, body: { cliente: number; obs?: string | null }): Promise<EquipamentoCliente> =>
    apiJson<EquipamentoCliente>(`/equipamentos-cliente/${id}/transferir`, { method: 'POST', body: JSON.stringify(body) }),
```

- [ ] **Step 3: Type-check**

Run: `cd /home/ericks/github/GestorHS/frontend && npx tsc -b --noEmit`
Expected: limpo. (Sem commit isolado; commit junto na Task 5.)

---

## Task 4: Frontend — `TransferirModal.tsx`

**Files:**
- Create: `frontend/src/app/frota/TransferirModal.tsx`

- [ ] **Step 1: Criar o modal**

`frontend/src/app/frota/TransferirModal.tsx` (busca de empresa nos moldes da busca de caixa do `AbrirOSModal`):
```tsx
import { useEffect, useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { ApiError } from '../../lib/api'
import { clientesApi, type ClienteListItem } from '../clientes/api'
import { equipamentosClienteApi } from './api'

export function TransferirModal({ equipamentoClienteId, donoAtual, onClose, onTransferida }: {
  equipamentoClienteId: number
  donoAtual: number
  onClose: () => void
  onTransferida: () => void
}) {
  const [q, setQ] = useState('')
  const [resultados, setResultados] = useState<ClienteListItem[]>([])
  const [destino, setDestino] = useState<ClienteListItem | null>(null)
  const [obs, setObs] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (destino || !q.trim()) { setResultados([]); return }
    let vivo = true
    clientesApi.listar({ q: q.trim(), limit: 8 })
      .then((r) => { if (vivo) setResultados(r.items) })
      .catch(() => { if (vivo) setResultados([]) })
    return () => { vivo = false }
  }, [q, destino])

  async function submeter(e: FormEvent) {
    e.preventDefault()
    if (!destino) return
    setErro(''); setEnviando(true)
    try {
      await equipamentosClienteApi.transferir(equipamentoClienteId, { cliente: destino.id, obs: obs.trim() || null })
      onTransferida()
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao transferir')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Transferir aparelho"
      size="lg"
      footer={
        <>
          <Button variant="secondary" type="button" onClick={onClose}>Cancelar</Button>
          <Button type="submit" form="form-transferir" disabled={enviando || destino == null || destino.id === donoAtual}>
            {enviando ? 'Transferindo…' : 'Transferir'}
          </Button>
        </>
      }
    >
      <form id="form-transferir" className="space-y-4" onSubmit={submeter}>
        <p className="text-sm text-slate-400">Escolha a empresa de destino. O histórico de OS antigas continua com a empresa atual.</p>

        {destino ? (
          <div className="flex items-center justify-between rounded-lg bg-primary/10 border border-primary/30 px-3 py-2">
            <span className="text-sm font-semibold text-primary">{destino.nome ?? `#${destino.id}`}</span>
            <button type="button" className="text-xs text-slate-400 hover:text-slate-200" onClick={() => setDestino(null)}>trocar</button>
          </div>
        ) : (
          <div>
            <Input id="busca-empresa" label="Empresa de destino" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar por nome" />
            {resultados.length > 0 && (
              <ul className="mt-1 rounded-lg border border-border divide-y divide-border overflow-hidden">
                {resultados.map((c) => (
                  <li key={c.id}>
                    <button type="button" onClick={() => { setDestino(c); setQ('') }}
                      className="w-full text-left px-3 py-2 text-sm hover:bg-background-elevated">
                      {c.nome ?? `#${c.id}`}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {destino && destino.id === donoAtual && (
          <p className="text-sm text-warning">Esta empresa já é a dona atual do aparelho.</p>
        )}

        <Input id="obs-transferencia" label="Observação (opcional)" value={obs} onChange={(e) => setObs(e.target.value)} placeholder="Motivo da transferência" />

        {erro && <p className="text-sm text-danger">{erro}</p>}
      </form>
    </Modal>
  )
}
```

- [ ] **Step 2: Type-check + lint**

Run: `cd /home/ericks/github/GestorHS/frontend && npx tsc -b --noEmit && npm run lint`
Expected: limpo. (Commit junto na Task 5.)

Nota: confirmar lendo `frontend/src/app/clientes/api.ts` que `clientesApi.listar` aceita `{ q, limit }` e que `ClienteListItem` tem `id` e `nome` (tem). Confirmar que `Modal` aceita `size="lg"` (o `AbrirOSModal` usa `size="xl"`; usar `"lg"` ou `"xl"` conforme o componente aceitar — se `"lg"` não existir, usar `"xl"`).

---

## Task 5: Frontend — ficha do aparelho (botão + modal + seção)

**Files:**
- Modify: `frontend/src/app/frota/EquipamentoClienteDetailPage.tsx`

Contexto (confirme lendo): imports na linha 13-14; estados ~40-52 (`abrindoOS`, `ordens`, etc.); efeito de carga ~54-81 (carrega historico/ordens/certificados); o derivado `osEmAndamento = osAtiva(ordens)` ~147; botões ~197-201; aside com `<Secao titulo="Histórico de movimentação">` que fecha antes de `</DetailAside>` (~248).

- [ ] **Step 1: Imports**

Na linha 12-14, adicionar o import do modal e o tipo `Transferencia`:
```tsx
import { AbrirOSModal } from '../ordens/AbrirOSModal'
import { TransferirModal } from './TransferirModal'
import { ordensApi, formatData, osAtiva, TIPO_SERVICO, type OrdemListItem } from '../ordens/api'
import { equipamentosClienteApi, STATUS_CALIBRACAO, type EquipamentoCliente, type EquipamentoClientePayload, type Historico, type StatusCalibracao, type EquipCertItem, type Transferencia } from './api'
```

- [ ] **Step 2: Estado + carga das transferências**

Após `const [certs, setCerts] = useState<EquipCertItem[]>([])` (~linha 51), adicionar:
```tsx
  const [transferindo, setTransferindo] = useState(false)
  const [transferencias, setTransferencias] = useState<Transferencia[]>([])
```
No efeito de carga (junto das outras chamadas, ~linha 80, após a de `certificados`), adicionar:
```tsx
    void equipamentosClienteApi.transferencias(Number(id)).then((t) => { if (ativo) setTransferencias(t) }).catch(() => {})
```

- [ ] **Step 3: Botão "Transferir"**

Na barra de botões (~linha 197-201), entre o "Abrir OS"/"Ver OS" e "Excluir", adicionar (visível só para Admin, desabilitado se houver OS em andamento):
```tsx
          {editando && isAdmin(user) && (
            <Button
              variant="secondary"
              onClick={() => setTransferindo(true)}
              disabled={!!osEmAndamento}
              title={osEmAndamento ? 'Finalize a OS em andamento antes de transferir' : undefined}
            >
              Transferir
            </Button>
          )}
```

- [ ] **Step 4: Renderizar o modal**

Onde o `AbrirOSModal` é renderizado condicionalmente (~linha 299, `{abrindoOS && obj && <AbrirOSModal ... />}`), adicionar logo abaixo:
```tsx
        {transferindo && obj && (
          <TransferirModal
            equipamentoClienteId={obj.id}
            donoAtual={obj.cliente}
            onClose={() => setTransferindo(false)}
            onTransferida={() => { setTransferindo(false); window.location.reload() }}
          />
        )}
```

- [ ] **Step 5: Seção "Transferências" no aside**

Logo após o fechamento da `<Secao titulo="Histórico de movimentação">` (`</Secao>`, ~linha 248) e antes de `</DetailAside>`, adicionar:
```tsx
            <Secao titulo="Transferências">
              {transferencias.length === 0 ? (
                <p className="text-sm text-slate-500">Sem transferências.</p>
              ) : (
                <Table head={<><TH>Data</TH><TH>De → Para</TH><TH>Usuário</TH><TH>Obs</TH></>}>
                  {transferencias.map((t) => (
                    <tr key={t.id} className="hover:bg-background-elevated transition-colors">
                      <TD>{formatData(t.data)}</TD>
                      <TD>{(t.de_cliente_nome ?? `#${t.de_cliente}`)} → {(t.para_cliente_nome ?? `#${t.para_cliente}`)}</TD>
                      <TD>{t.usuario_nome ?? '—'}</TD>
                      <TD>{t.obs ?? '—'}</TD>
                    </tr>
                  ))}
                </Table>
              )}
            </Secao>
```

- [ ] **Step 6: Type-check + lint + testes**

Run: `cd /home/ericks/github/GestorHS/frontend && npx tsc -b --noEmit && npm run lint && npm test`
Expected: tudo limpo / verde. (Sem teste de render do modal — a lógica de API já é coberta; verificação visual na Task 6. Decisão consciente, mesmo critério das features anteriores.)

- [ ] **Step 7: Commit**

```bash
cd /home/ericks/github/GestorHS
git add frontend/src/app/frota/api.ts frontend/src/app/frota/TransferirModal.tsx frontend/src/app/frota/EquipamentoClienteDetailPage.tsx
git commit -m "feat(frota): botao e modal de transferir aparelho na ficha"
```

---

## Task 6: Verificação completa + changelog

**Files:**
- Modify: `frontend/src/app/changelog/data.ts`

- [ ] **Step 1: Backend completo**

Run: `docker compose exec -T backend pytest -q`
Expected: PASS.

- [ ] **Step 2: Frontend completo**

Run: `cd /home/ericks/github/GestorHS/frontend && npm test && npx tsc -b --noEmit && npm run lint && npm run build`
Expected: tudo PASS / build OK.

- [ ] **Step 3: Verificação visual**

Com backend e frontend no ar, abrir a ficha de um aparelho (modo edição):
- Botão **"Transferir"** aparece (Admin) e fica **desabilitado** se houver OS em andamento.
- Clicar abre o modal; buscar e escolher a empresa destino; confirmar.
- A ficha recarrega já sob o novo dono; a seção **"Transferências"** mostra o registro.

- [ ] **Step 4: Changelog**

Ler `frontend/src/app/changelog/data.ts` e inserir no TOPO do array `CHANGELOG`:
```ts
  {
    versao: '1.8.0',
    data: '18/06/2026',
    itens: [
      { tipo: 'novidade', texto: 'Agora é possível transferir um aparelho de uma empresa para outra direto na ficha do aparelho (botão "Transferir"). O histórico de OS antigas continua com a empresa anterior, e cada transferência fica registrada com data, empresas e responsável. Não é permitido transferir enquanto houver uma OS em andamento.' },
    ],
  },
```

- [ ] **Step 5: Teste do changelog**

Run: `cd /home/ericks/github/GestorHS/frontend && npx vitest run src/app/changelog/data.test.ts`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd /home/ericks/github/GestorHS
git add frontend/src/app/changelog/data.ts
git commit -m "docs(changelog): v1.8.0 — transferencia de aparelho entre empresas"
```

---

## Self-review (preenchido)

- **Cobertura do spec:** tabela/migração (Task 1); endpoint transferir com validações 404/400/409 + zera os_atual + auditoria (Task 2); endpoint listar transferências (Task 2); só Admin (Task 2, `require_funcao(ADMIN)`); OS antigas mantêm dono (Task 2 teste); frontend api/modal/botão/seção (Tasks 3-5); bloqueio visual por OS ativa (Task 5); changelog (Task 6).
- **Placeholders:** nenhum — todo passo tem código/comando reais. Notas de "confirmar ao ler" são checagens pontuais de integração (nomes de props do Modal, assinatura de clientesApi), não lacunas de design.
- **Consistência de tipos:** `TransferenciaEquipamento` (model) → `TransferenciaOut` (chaves `de_cliente`/`para_cliente`/`*_nome`/`usuario_nome`/`data`/`obs`) → TS `Transferencia` batem; `transferir(id, {cliente, obs})` e `transferencias(id)` casam entre api.ts, modal e página; `wf.ATIVAS`/`agora` existem (os_workflow / ordens_acoes); `osAtiva(ordens)` já existe na página (feature anterior).
