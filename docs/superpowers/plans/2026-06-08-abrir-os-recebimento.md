# Abrir OS — Recebimento completo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enriquecer o formulário de abrir OS com data de chegada, caixa, condição de chegada (select), checklist fixo de acessórios, pilhas, bocais e observações — reusando colunas existentes (sem migração).

**Architecture:** Backend: constantes + helpers do recebimento, properties no modelo `Ordem`, `OrdemAbrirIn`/`OrdemOut` estendidos, endpoint `abrir` grava os campos. Frontend: `AbrirOSModal` redesenhado (com busca/criação de caixa), `OrdemDetailPage` exibe os campos, constantes espelhadas. Changelog v1.2.0.

**Tech Stack:** Backend FastAPI + SQLAlchemy + pytest (SQLite). Frontend React + TS + Vite + Vitest.

**Spec:** `docs/superpowers/specs/2026-06-08-abrir-os-recebimento-design.md`

**Convenções:** testes backend `cd backend && python -m pytest -q`; frontend `cd frontend && npx vitest run`. Escrita de OS = `require_funcao("Expedição","Administrador")`. Fixtures de teste: `usuario_comum` (Expedição, comum/senha123), `usuario_admin`, `fases_seed`, `os_base` (devolve ids cliente/equipamento/equipamento_cliente). Helper de auth nos testes: `_headers(client, login, senha)`.

**Regra do projeto:** toda mudança bumpa versão + entra no ChangelogModal (Task 8).

---

## Task 1: Constantes e helpers do recebimento

**Files:**
- Create: `backend/app/core/recebimento.py`
- Test: `backend/tests/test_recebimento.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_recebimento.py`:

```python
import pytest
from app.core import recebimento as rec


def test_listas_fixas():
    assert rec.CHECKLIST_ACESSORIOS[1] == "Bobinas"
    assert rec.CHECKLIST_ACESSORIOS[9] == "Nf de Remessa"
    assert len(rec.CHECKLIST_ACESSORIOS) == 9
    assert "Bom estado" in rec.CONDICOES_CHEGADA
    assert len(rec.CONDICOES_CHEGADA) == 5


def test_ids_para_csv_ordena_e_dedup():
    assert rec.checklist_ids_para_csv([3, 1, 3]) == "1,3"
    assert rec.checklist_ids_para_csv([]) is None
    assert rec.checklist_ids_para_csv(None) is None


def test_ids_para_csv_invalido():
    with pytest.raises(ValueError):
        rec.checklist_ids_para_csv([1, 99])


def test_csv_para_ids_defensivo():
    assert rec.checklist_csv_para_ids("1,3,5") == [1, 3, 5]
    assert rec.checklist_csv_para_ids(" ") == []
    assert rec.checklist_csv_para_ids(None) == []
    # ignora lixo e ids fora da lista (dados legados)
    assert rec.checklist_csv_para_ids("1,x,99,2") == [1, 2]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_recebimento.py -q`
Expected: FAIL (módulo inexistente).

- [ ] **Step 3: Implement**

Create `backend/app/core/recebimento.py`:

```python
"""Constantes e helpers do recebimento da OS (checklist de acessórios + condição)."""

# Lista fixa de acessórios do recebimento (id estável -> rótulo).
CHECKLIST_ACESSORIOS: dict[int, str] = {
    1: "Bobinas",
    2: "Bocal",
    3: "Cabos USB",
    4: "Capa",
    5: "Carregador veicular",
    6: "Carregadores AC/DC",
    7: "Impressora",
    8: "Maleta",
    9: "Nf de Remessa",
}

# Opções fixas do select "Condição de chegada".
CONDICOES_CHEGADA: tuple[str, ...] = (
    "Bom estado",
    "Com avarias",
    "Oxidado",
    "Lacrado",
    "Sem acessórios",
)


def checklist_ids_para_csv(ids: list[int] | None) -> str | None:
    """Valida ids contra a lista fixa, ordena, remove duplicados e junta em CSV.
    Retorna None se a lista for vazia/None. Levanta ValueError para id inválido."""
    if not ids:
        return None
    unicos = sorted(set(ids))
    for i in unicos:
        if i not in CHECKLIST_ACESSORIOS:
            raise ValueError(f"item de checklist inválido: {i}")
    return ",".join(str(i) for i in unicos)


def checklist_csv_para_ids(csv: str | None) -> list[int]:
    """Parse defensivo do CSV: ignora valores não-numéricos e ids fora da lista."""
    if not csv:
        return []
    ids: list[int] = []
    for parte in csv.split(","):
        parte = parte.strip()
        if parte.isdigit():
            n = int(parte)
            if n in CHECKLIST_ACESSORIOS:
                ids.append(n)
    return ids
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_recebimento.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/recebimento.py backend/tests/test_recebimento.py
git commit -m "feat(os): constantes e helpers do recebimento (checklist + condição)"
```

---

## Task 2: Properties no modelo `Ordem`

**Files:**
- Modify: `backend/app/models/ordem.py` (adicionar properties)
- Test: `backend/tests/test_recebimento_model.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_recebimento_model.py`:

```python
def test_ordem_checklist_properties(db_session):
    from app.models import Cliente, Ordem
    cli = Cliente(nome="Cliente CK")
    db_session.add(cli); db_session.flush()
    o = Ordem(cliente=cli.id, situacao="E", checklist="1,3,9", pilhas=4, sopradores=2)
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    assert o.checklist_ids == [1, 3, 9]
    assert o.acessorios_presentes == ["Bobinas", "Cabos USB", "Nf de Remessa"]
    assert o.bocais == 2


def test_ordem_checklist_vazio(db_session):
    from app.models import Cliente, Ordem
    cli = Cliente(nome="Cliente CK2")
    db_session.add(cli); db_session.flush()
    o = Ordem(cliente=cli.id, situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    assert o.checklist_ids == []
    assert o.acessorios_presentes == []
    assert o.bocais == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_recebimento_model.py -q`
Expected: FAIL (`AttributeError: checklist_ids`).

- [ ] **Step 3: Implement**

Em `backend/app/models/ordem.py`, junto às outras `@property` (após `caixa_obs`), adicione:

```python
    @property
    def checklist_ids(self):
        from app.core.recebimento import checklist_csv_para_ids
        return checklist_csv_para_ids(self.checklist)

    @property
    def acessorios_presentes(self):
        from app.core.recebimento import CHECKLIST_ACESSORIOS
        return [CHECKLIST_ACESSORIOS[i] for i in self.checklist_ids]

    @property
    def bocais(self):
        return self.sopradores or 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_recebimento_model.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/ordem.py backend/tests/test_recebimento_model.py
git commit -m "feat(os): properties checklist_ids/acessorios_presentes/bocais em Ordem"
```

---

## Task 3: Schemas `OrdemAbrirIn` e `OrdemOut`

**Files:**
- Modify: `backend/app/schemas/ordens.py` (import `date`, `OrdemAbrirIn`, `OrdemOut`)
- Test: `backend/tests/test_recebimento_schemas.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_recebimento_schemas.py`:

```python
from datetime import date


def test_abrir_in_novos_campos():
    from app.schemas.ordens import OrdemAbrirIn
    m = OrdemAbrirIn(
        equipamento_cliente=1, tipo_servico="C",
        data_chegada=date(2026, 6, 8), condicao_chegada="Bom estado",
        checklist=[1, 3], pilhas=4, bocais=2, observacoes="ok",
    )
    assert m.checklist == [1, 3]
    assert m.bocais == 2
    assert m.observacoes == "ok"
    # acessorios não existe mais
    assert not hasattr(m, "acessorios")


def test_abrir_in_minimo():
    from app.schemas.ordens import OrdemAbrirIn
    m = OrdemAbrirIn(equipamento_cliente=1, tipo_servico="M")
    assert m.data_chegada is None
    assert m.pilhas == 0
    assert m.bocais == 0
    assert m.checklist is None


def test_ordem_out_expoe_recebimento(db_session):
    from app.models import Cliente, Ordem
    from app.schemas.ordens import OrdemOut
    cli = Cliente(nome="Cliente Out")
    db_session.add(cli); db_session.flush()
    o = Ordem(cliente=cli.id, situacao="E", checklist="1,3", pilhas=5, sopradores=1)
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    out = OrdemOut.model_validate(o)
    assert out.checklist_ids == [1, 3]
    assert out.acessorios_presentes == ["Bobinas", "Cabos USB"]
    assert out.pilhas == 5
    assert out.bocais == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_recebimento_schemas.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

Em `backend/app/schemas/ordens.py`:
- Linha 1, troque `from datetime import datetime` por `from datetime import datetime, date`.
- Substitua a classe `OrdemAbrirIn` (atual: equipamento_cliente, tipo_servico, condicao_chegada, acessorios, caixa) por:

```python
class OrdemAbrirIn(BaseModel):
    equipamento_cliente: int
    tipo_servico: Literal["C", "M", "A"]
    data_chegada: date | None = None
    caixa: int | None = None
    condicao_chegada: str | None = None
    checklist: list[int] | None = None
    pilhas: int | None = 0
    bocais: int | None = 0
    observacoes: str | None = None
```

- Em `OrdemOut`, após o campo `pdf_certificado` (ou junto aos campos de recebimento), adicione:

```python
    checklist_ids: list[int] = []
    acessorios_presentes: list[str] = []
    pilhas: int = 0
    bocais: int = 0
```

> `condicao_chegada`, `data_chegada`, `obs`, `caixa` já estão em `OrdemOut`. O campo `acessorios` pode permanecer em `OrdemOut` (coluna ainda existe) — não precisa removê-lo do output.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_recebimento_schemas.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/ordens.py backend/tests/test_recebimento_schemas.py
git commit -m "feat(os): OrdemAbrirIn/OrdemOut com campos de recebimento"
```

---

## Task 4: Endpoint `abrir` grava os campos de recebimento

**Files:**
- Modify: `backend/app/api/ordens.py` (função `abrir`, imports)
- Test: `backend/tests/test_ordens_abrir.py` (novos testes)

- [ ] **Step 1: Write the failing test**

Adicione ao final de `backend/tests/test_ordens_abrir.py`:

```python
def test_abrir_grava_recebimento(client, usuario_comum, fases_seed, os_base, db_session):
    h = _headers(client, "comum", "senha123")
    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"],
        "tipo_servico": "C",
        "data_chegada": "2026-06-08",
        "condicao_chegada": "Bom estado",
        "checklist": [3, 1],
        "pilhas": 4,
        "bocais": 2,
        "observacoes": "veio sem maleta",
    }, headers=h)
    assert r.status_code == 201
    body = r.json()
    assert body["condicao_chegada"] == "Bom estado"
    assert body["checklist_ids"] == [1, 3]
    assert body["acessorios_presentes"] == ["Bobinas", "Cabos USB"]
    assert body["pilhas"] == 4
    assert body["bocais"] == 2
    assert body["obs"] == "veio sem maleta"
    assert body["data_chegada"].startswith("2026-06-08")


def test_abrir_data_chegada_default_hoje(client, usuario_comum, fases_seed, os_base):
    h = _headers(client, "comum", "senha123")
    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "M",
    }, headers=h)
    assert r.status_code == 201
    assert r.json()["data_chegada"] is not None  # default = agora()


def test_abrir_condicao_invalida_400(client, usuario_comum, fases_seed, os_base):
    h = _headers(client, "comum", "senha123")
    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C",
        "condicao_chegada": "INEXISTENTE",
    }, headers=h)
    assert r.status_code == 400


def test_abrir_checklist_id_invalido_400(client, usuario_comum, fases_seed, os_base):
    h = _headers(client, "comum", "senha123")
    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C",
        "checklist": [1, 99],
    }, headers=h)
    assert r.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_ordens_abrir.py -q`
Expected: FAIL (campos não gravados / sem validação).

- [ ] **Step 3: Implement**

Em `backend/app/api/ordens.py`:
- No topo, adicione os imports:

```python
from datetime import datetime, timezone
from app.core import recebimento as rec
```
(Se `datetime`/`timezone` já estiverem importados via `agora`, importe só `rec`. `agora` vem de `ordens_acoes`.)

- Substitua o corpo de `abrir` (a partir da validação da caixa) por:

```python
    if dados.caixa is not None:
        cx = db.query(Caixa).filter(Caixa.id == dados.caixa).first()
        if cx is None:
            raise HTTPException(status_code=404, detail="caixa não encontrada")
    if dados.condicao_chegada is not None and dados.condicao_chegada not in rec.CONDICOES_CHEGADA:
        raise HTTPException(status_code=400, detail="condição de chegada inválida")
    try:
        checklist_csv = rec.checklist_ids_para_csv(dados.checklist)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if dados.data_chegada is not None:
        data_chegada = datetime(
            dados.data_chegada.year, dados.data_chegada.month, dados.data_chegada.day,
            tzinfo=timezone.utc,
        )
    else:
        data_chegada = agora()
    ordem = Ordem(
        cliente=ec.cliente,
        equipamento_cliente=ec.id,
        fase=wf.FASE_RECEBIDO,
        tipo_servico=dados.tipo_servico,
        condicao_chegada=dados.condicao_chegada,
        checklist=checklist_csv,
        pilhas=dados.pilhas or 0,
        sopradores=dados.bocais or 0,
        obs=dados.observacoes,
        data_chegada=data_chegada,
        recebido=True,
        situacao="E",
        caixa=dados.caixa,
    )
    db.add(ordem)
    db.flush()
    ec.os_atual = ordem.id
    registrar_log(db, ordem, usuario, "OS aberta — Recebido")
    db.commit()
    db.refresh(ordem)
    return ordem
```

(Remove a linha antiga `acessorios=dados.acessorios,` e o `data_chegada=agora()` fixo.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_ordens_abrir.py -q`
Expected: PASS (todos, incl. os 4 novos; os antigos de abrir mínimos/caixa/404 seguem verdes).

- [ ] **Step 5: Run full backend suite**

Run: `cd backend && python -m pytest -q`
Expected: tudo verde.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/ordens.py backend/tests/test_ordens_abrir.py
git commit -m "feat(os): abrir grava data/condição/checklist/pilhas/bocais/observações"
```

---

## Task 5: Frontend — `api.ts` (payload, tipos, constantes) + teste

**Files:**
- Modify: `frontend/src/app/ordens/api.ts`
- Test: `frontend/src/app/ordens/api.recebimento.test.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/app/ordens/api.recebimento.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { CHECKLIST_ACESSORIOS, CONDICOES_CHEGADA } from './api'

describe('constantes de recebimento', () => {
  it('checklist tem 9 itens com ids 1..9', () => {
    expect(CHECKLIST_ACESSORIOS).toHaveLength(9)
    expect(CHECKLIST_ACESSORIOS[0]).toEqual({ id: 1, label: 'Bobinas' })
    expect(CHECKLIST_ACESSORIOS[8]).toEqual({ id: 9, label: 'Nf de Remessa' })
  })
  it('condições têm 5 opções', () => {
    expect(CONDICOES_CHEGADA).toEqual([
      'Bom estado', 'Com avarias', 'Oxidado', 'Lacrado', 'Sem acessórios',
    ])
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/app/ordens/api.recebimento.test.ts`
Expected: FAIL (exports inexistentes).

- [ ] **Step 3: Implement**

Em `frontend/src/app/ordens/api.ts`:
- Adicione as constantes (perto do topo, após os imports):

```ts
export const CHECKLIST_ACESSORIOS: { id: number; label: string }[] = [
  { id: 1, label: 'Bobinas' },
  { id: 2, label: 'Bocal' },
  { id: 3, label: 'Cabos USB' },
  { id: 4, label: 'Capa' },
  { id: 5, label: 'Carregador veicular' },
  { id: 6, label: 'Carregadores AC/DC' },
  { id: 7, label: 'Impressora' },
  { id: 8, label: 'Maleta' },
  { id: 9, label: 'Nf de Remessa' },
]

export const CONDICOES_CHEGADA = [
  'Bom estado', 'Com avarias', 'Oxidado', 'Lacrado', 'Sem acessórios',
] as const
```

- Substitua a interface `AbrirPayload` por:

```ts
export interface AbrirPayload {
  equipamento_cliente: number
  tipo_servico: TipoServico
  data_chegada?: string | null
  caixa?: number | null
  condicao_chegada?: string | null
  checklist?: number[] | null
  pilhas?: number | null
  bocais?: number | null
  observacoes?: string | null
}
```

- Em `OrdemDetalhe`, adicione os campos:

```ts
  pilhas: number
  bocais: number
  checklist_ids: number[]
  acessorios_presentes: string[]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/app/ordens/api.recebimento.test.ts`
Expected: PASS (2 passed).

- [ ] **Step 5: Typecheck**

Run: `cd frontend && npx tsc -b --noEmit`
Expected: pode falhar em `AbrirOSModal.tsx` (ainda manda `acessorios`/`condicao` antigos) — será corrigido na Task 6. Se falhar SÓ por isso, prossiga; senão conserte.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/ordens/api.ts frontend/src/app/ordens/api.recebimento.test.ts
git commit -m "feat(os): AbrirPayload/OrdemDetalhe + constantes de recebimento (front)"
```

---

## Task 6: Frontend — `AbrirOSModal` redesenhado

**Files:**
- Modify: `frontend/src/app/ordens/AbrirOSModal.tsx`

- [ ] **Step 1: Reescreva o componente**

Substitua todo o `frontend/src/app/ordens/AbrirOSModal.tsx` por:

```tsx
import { useState, useEffect, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Modal } from '../../components/ui/Modal'
import { Select } from '../../components/ui/Select'
import { Input } from '../../components/ui/Input'
import { Button } from '../../components/ui/Button'
import { ApiError } from '../../lib/api'
import { ordensApi, CHECKLIST_ACESSORIOS, CONDICOES_CHEGADA, type TipoServico } from './api'
import { caixasApi, type CaixaListItem } from '../caixas/api'

function hojeISO(): string {
  // YYYY-MM-DD no fuso local
  const d = new Date()
  const off = d.getTimezoneOffset()
  return new Date(d.getTime() - off * 60000).toISOString().slice(0, 10)
}

export function AbrirOSModal({ equipamentoClienteId, osAtual, onClose, caixa, onAberta }: {
  equipamentoClienteId: number
  osAtual: number | null
  onClose: () => void
  caixa?: number
  onAberta?: (osId: number) => void
}) {
  const navigate = useNavigate()
  const [dataChegada, setDataChegada] = useState(hojeISO())
  const [tipo, setTipo] = useState<TipoServico>('C')
  const [condicao, setCondicao] = useState('')
  const [checklist, setChecklist] = useState<number[]>([])
  const [pilhas, setPilhas] = useState('0')
  const [bocais, setBocais] = useState('0')
  const [obs, setObs] = useState('')
  const [erro, setErro] = useState('')
  const [osAtivaId, setOsAtivaId] = useState<number | null>(null)
  const [enviando, setEnviando] = useState(false)

  // Caixa: travada quando vem por prop; senão busca/cria
  const caixaTravada = caixa != null
  const [caixaId, setCaixaId] = useState<number | null>(caixa ?? null)
  const [caixaQ, setCaixaQ] = useState('')
  const [caixaResultados, setCaixaResultados] = useState<CaixaListItem[]>([])
  const [criandoCaixa, setCriandoCaixa] = useState(false)

  useEffect(() => {
    if (caixaTravada || !caixaQ.trim()) { setCaixaResultados([]); return }
    let vivo = true
    caixasApi.listar({ q: caixaQ.trim(), limit: 8 })
      .then((r) => { if (vivo) setCaixaResultados(r.items) })
      .catch(() => { if (vivo) setCaixaResultados([]) })
    return () => { vivo = false }
  }, [caixaQ, caixaTravada])

  function toggleChecklist(id: number) {
    setChecklist((cur) => cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id])
  }

  async function criarCaixa() {
    setCriandoCaixa(true)
    setErro('')
    try {
      const nova = await caixasApi.criar({ obs: caixaQ.trim() || null })
      setCaixaId(nova.id)
      setCaixaResultados([])
      setCaixaQ('')
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao criar caixa')
    } finally {
      setCriandoCaixa(false)
    }
  }

  async function submeter(e: FormEvent) {
    e.preventDefault()
    setErro('')
    setOsAtivaId(null)
    setEnviando(true)
    try {
      const os = await ordensApi.abrir({
        equipamento_cliente: equipamentoClienteId,
        tipo_servico: tipo,
        data_chegada: dataChegada || null,
        caixa: caixaId,
        condicao_chegada: condicao || null,
        checklist: checklist.length ? checklist : null,
        pilhas: Number(pilhas) || 0,
        bocais: Number(bocais) || 0,
        observacoes: obs.trim() || null,
      })
      if (onAberta) onAberta(os.id)
      else navigate(`/app/ordens/${os.id}`)
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setErro('Este aparelho já possui uma OS ativa.')
        setOsAtivaId(osAtual)
      } else {
        setErro(err instanceof ApiError ? err.message : 'Falha ao abrir OS')
      }
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Abrir OS"
      footer={
        <>
          <Button variant="secondary" type="button" onClick={onClose}>Cancelar</Button>
          <Button type="submit" form="form-abrir-os" disabled={enviando}>Abrir</Button>
        </>
      }
    >
      <form id="form-abrir-os" className="space-y-4" onSubmit={submeter}>
        <div className="grid grid-cols-2 gap-3">
          <Input id="data-chegada" label="Data de chegada" type="date" value={dataChegada} onChange={(e) => setDataChegada(e.target.value)} />
          <Select id="tipo-servico" label="Tipo de serviço" value={tipo} onChange={(e) => setTipo(e.target.value as TipoServico)}>
            <option value="C">Calibração</option>
            <option value="M">Manutenção</option>
            <option value="A">Ambas</option>
          </Select>
        </div>

        {/* Caixa */}
        {caixaTravada ? (
          <p className="text-sm text-slate-400">Caixa: <span className="font-semibold text-slate-200">#{caixa}</span></p>
        ) : caixaId ? (
          <div className="flex items-center justify-between rounded-lg border border-border px-3 py-2 text-sm">
            <span className="text-slate-200">Caixa #{caixaId}</span>
            <button type="button" className="text-xs text-danger hover:underline" onClick={() => setCaixaId(null)}>remover</button>
          </div>
        ) : (
          <div>
            <Input id="caixa-q" label="Caixa (opcional)" value={caixaQ} onChange={(e) => setCaixaQ(e.target.value)} placeholder="Buscar por nº/descrição" />
            {caixaResultados.length > 0 && (
              <ul className="mt-1 divide-y divide-border rounded-lg border border-border overflow-hidden">
                {caixaResultados.map((c) => (
                  <li key={c.id}>
                    <button type="button" className="w-full text-left px-3 py-2 text-sm hover:bg-background-elevated" onClick={() => { setCaixaId(c.id); setCaixaResultados([]); setCaixaQ('') }}>
                      <span className="font-semibold text-slate-200">#{c.id}</span>
                      {c.obs && <span className="text-slate-500"> · {c.obs}</span>}
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {caixaQ.trim() && (
              <button type="button" onClick={criarCaixa} disabled={criandoCaixa} className="mt-1 text-xs font-semibold text-primary hover:underline disabled:opacity-50">
                + Criar caixa "{caixaQ.trim()}"
              </button>
            )}
          </div>
        )}

        <Select id="condicao" label="Condição de chegada" value={condicao} onChange={(e) => setCondicao(e.target.value)}>
          <option value="">—</option>
          {CONDICOES_CHEGADA.map((c) => <option key={c} value={c}>{c}</option>)}
        </Select>

        <div>
          <label className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">Checklist de acessórios</label>
          <div className="grid grid-cols-2 gap-1.5">
            {CHECKLIST_ACESSORIOS.map((item) => (
              <label key={item.id} className="flex items-center gap-2 text-sm text-slate-300">
                <input type="checkbox" checked={checklist.includes(item.id)} onChange={() => toggleChecklist(item.id)} />
                {item.label}
              </label>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Input id="pilhas" label="Pilhas" type="number" min={0} value={pilhas} onChange={(e) => setPilhas(e.target.value)} />
          <Input id="bocais" label="Bocais" type="number" min={0} value={bocais} onChange={(e) => setBocais(e.target.value)} />
        </div>

        <div>
          <label htmlFor="obs" className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">Observações</label>
          <textarea id="obs" value={obs} onChange={(e) => setObs(e.target.value)} rows={3} className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-background-elevated text-slate-300 focus:outline-none focus:ring-2 focus:ring-primary/50" />
        </div>

        {erro && (
          <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger space-y-2">
            <p>{erro}</p>
            {osAtivaId && (
              <button type="button" onClick={() => navigate(`/app/ordens/${osAtivaId}`)} className="text-xs font-semibold text-primary hover:underline">Ver OS atual</button>
            )}
          </div>
        )}
      </form>
    </Modal>
  )
}
```

> Confirme que `Modal` comporta este conteúdo; se ficar estreito (o `Modal` é `max-w-md`), aumente a largura no próprio `Modal` ou envolva o form numa largura maior. Confirme a assinatura de `Button` (variant 'secondary' existe). Se o `Input type="date"`/`number` exigir algo específico, siga o padrão de outros usos no projeto.

- [ ] **Step 2: Typecheck + lint + build**

Run: `cd frontend && npx tsc -b --noEmit && npx eslint src/app/ordens/AbrirOSModal.tsx && npm run build`
Expected: tudo verde.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/ordens/AbrirOSModal.tsx
git commit -m "feat(os): AbrirOSModal com recebimento completo (data/caixa/condição/checklist/pilhas/bocais/obs)"
```

---

## Task 7: Frontend — `OrdemDetailPage` exibe o recebimento

**Files:**
- Modify: `frontend/src/app/ordens/OrdemDetailPage.tsx`

- [ ] **Step 1: Atualize a seção "Recebimento"**

Em `frontend/src/app/ordens/OrdemDetailPage.tsx`, na seção Recebimento, **substitua** a linha:

```tsx
          <Campo label="Acessórios" valor={os.acessorios} />
```

por:

```tsx
          <Campo label="Acessórios" valor={os.acessorios_presentes.length ? os.acessorios_presentes.join(', ') : '—'} />
          <Campo label="Pilhas" valor={os.pilhas} />
          <Campo label="Bocais" valor={os.bocais} />
          <Campo label="Observações" valor={os.obs || '—'} />
```

> Mantém `Condição de chegada`, `Data de chegada` e `Caixa` (já presentes). `acessorios_presentes`, `pilhas`, `bocais` vêm do `OrdemDetalhe` (Task 5). Se `os.obs` já for exibido em outra seção, não duplique — coloque "Observações" só uma vez (na seção Recebimento).

- [ ] **Step 2: Typecheck + lint + build**

Run: `cd frontend && npx tsc -b --noEmit && npx eslint src/app/ordens/OrdemDetailPage.tsx && npm run build`
Expected: verde.

- [ ] **Step 3: Run full frontend suite**

Run: `cd frontend && npx vitest run`
Expected: tudo verde.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/ordens/OrdemDetailPage.tsx
git commit -m "feat(os): detalhe da OS exibe acessórios/pilhas/bocais/observações do recebimento"
```

---

## Task 8: Changelog v1.2.0 + verificação E2E + memória

**Files:**
- Modify: `frontend/src/app/changelog/data.ts`

- [ ] **Step 1: Adicione a entrada no changelog**

Em `frontend/src/app/changelog/data.ts`, no topo do array `CHANGELOG`, adicione:

```ts
  {
    versao: '1.2.0',
    data: '08/06/2026',
    itens: [
      { tipo: 'novidade', texto: 'Recebimento de OS mais completo — ao abrir a OS agora dá para registrar data de chegada, vincular/criar caixa, condição de chegada, checklist de acessórios, quantidade de pilhas e bocais, e observações.' },
    ],
  },
```

- [ ] **Step 2: Valide changelog + suíte**

Run: `cd frontend && npx vitest run src/app/changelog/ && npx tsc -b --noEmit && npm run build`
Expected: verde (incl. `data.test.ts`: VERSAO_ATUAL === CHANGELOG[0].versao = '1.2.0').

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/changelog/data.ts
git commit -m "feat(changelog): v1.2.0 — recebimento de OS completo"
```

- [ ] **Step 4: E2E manual no navegador**

Com backend (Docker `:8000`) e frontend (`npm run dev` `:5173`) no ar, login admin (`admin`/`admin12345`):
1. Frota → abrir um aparelho → "Abrir OS".
2. Preencher: data de chegada (default hoje), tipo, condição "Bom estado", marcar alguns acessórios, pilhas=2, bocais=1, observações, e criar/escolher uma caixa.
3. Abrir → conferir no detalhe da OS: condição, acessórios presentes (rótulos), pilhas, bocais, observações e a caixa vinculada.
4. Abrir OS "mínima" (só tipo) → funciona, data = hoje.
5. Abrir OS a partir de uma Caixa (tela da caixa → Abrir OS) → caixa pré-travada no modal.
> Remover dados de teste ao final, se criados (excluir OS não há na UI — usar com cuidado; preferir aparelho de teste).

- [ ] **Step 5: Atualizar memória do projeto**

Atualizar `project_gestorhs.md`: registrar a etapa "Abrir OS — recebimento completo" concluída (campos, reuso de colunas, v1.2.0) e que é a 1ª etapa da revisão do processo de OS (próximas: fechamento/laboratório).

---

## Self-Review

**Cobertura da spec:**
- Constantes/helpers checklist+condição → Task 1. Properties no modelo → Task 2. OrdemAbrirIn (novos campos, remove acessorios) + OrdemOut → Task 3. Endpoint grava + validações + data default → Task 4. Front payload/tipos/constantes → Task 5. Modal redesenhado (data/caixa busca+cria/condição select/checklist/pilhas/bocais/obs; caixa travada quando vem por prop) → Task 6. Detalhe exibe recebimento → Task 7. Changelog v1.2.0 + E2E + memória → Task 8. ✓
- Sem migração (reuso de colunas) ✓. "acessorios" sai do formulário, coluna mantida ✓.

**Placeholders:** nenhum; trechos de UI dependentes de componentes têm nota para conferir (`Modal` largura, `Button` variant) — não são placeholders de lógica.

**Consistência de tipos/nomes:** backend `OrdemAbrirIn.{checklist:list[int], pilhas, bocais, observacoes, data_chegada}`; `OrdemOut.{checklist_ids, acessorios_presentes, pilhas, bocais}`; model props `checklist_ids/acessorios_presentes/bocais`; `rec.{CHECKLIST_ACESSORIOS, CONDICOES_CHEGADA, checklist_ids_para_csv, checklist_csv_para_ids}`; front `AbrirPayload.{checklist:number[], bocais, observacoes, data_chegada, caixa, condicao_chegada}`, `OrdemDetalhe.{pilhas,bocais,checklist_ids,acessorios_presentes}`, consts `CHECKLIST_ACESSORIOS`/`CONDICOES_CHEGADA`. Consistentes. ✓
- Nota: backend grava `bocais` em `ordens.sopradores`; `OrdemOut.bocais` lê a property `bocais` (=sopradores). Front nunca vê `sopradores`. ✓
