# Fase 3E (Calibração & Certificado) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enriquecer o portão Laboratório→Pós-Vendas com resultados de calibração + certificado, gravando na OS e espelhando no cadastro do aparelho.

**Architecture:** Backend — catálogo `tipos_calibragem` (leitura), extensão de `AvancarIn` com campos de calibração opcionais e do branch `origem == 5` do `avancar` (grava na OS + espelha no `equipamentos_cliente` via helper `espelhar_calibracao`). Frontend — `tiposCalibragemApi`, `AvancarModal` em modo calibração (só fase Laboratório) com média automática e próxima calibração pré-preenchida, e link de PDF no detalhe.

**Tech Stack:** Backend FastAPI/SQLAlchemy/Pydantic/pytest; Frontend React 19/TS/Vite/Vitest.

**Spec:** `docs/superpowers/specs/2026-06-03-fase3e-calibracao-certificado-design.md`

**Comandos:** Backend no Docker (`docker compose exec -T backend python -m pytest <args>`, da raiz `d:\GitHub\GestorHS` com o container de pé). Frontend: `npm --prefix frontend run test|lint|build`. Git via `git -C /d/GitHub/GestorHS`. Trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

**Branch:** antes da Task 1:
```bash
git -C /d/GitHub/GestorHS checkout -b feat/fase3e-calibracao
```

## Convenções (já estabelecidas)
- Backend: modelo um-por-arquivo em `app/models/` + registro em `__init__.py`; router em `app/api/` + `app.include_router` em `main.py`; `GET` de catálogo com `get_current_usuario`. Testes pytest/SQLite com fixtures `fases_seed`, `usuario_lab`, `usuario_comum`, `os_base` (cria cliente+equipamento+equipamento_cliente e devolve ids); helper local `_headers(client, login, senha)`.
- Frontend: `apiJson`; `AvancarModal` (3D) recebe `transicao`; `TRANSICOES` em `ordens/api.ts`; `Select`/`Input`. Lint `react-hooks/set-state-in-effect`: disable só na linha exata do setState síncrono no efeito. Telas por `tsc`/`lint`/`build`.

---

### Task 1: Catálogo `tipos_calibragem` (modelo + endpoint)

**Files:**
- Create: `backend/app/models/tipo_calibragem.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/schemas/ordens.py`
- Create: `backend/app/api/tipos_calibragem.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_tipos_calibragem.py`

- [ ] **Step 1: Escrever o teste falhando** — `backend/tests/test_tipos_calibragem.py`:

```python
def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def test_listar_tipos_calibragem(client, usuario_comum, db_session):
    from app.models import TipoCalibragem
    db_session.add(TipoCalibragem(descricao="Calibração Anual"))
    db_session.commit()
    h = _headers(client, "comum", "senha123")
    r = client.get("/tipos-calibragem", headers=h)
    assert r.status_code == 200
    assert any(t["descricao"] == "Calibração Anual" for t in r.json())


def test_tipos_calibragem_exige_auth(client):
    assert client.get("/tipos-calibragem").status_code == 401
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_tipos_calibragem.py -q`
Expected: FAIL (ImportError TipoCalibragem / 404 rota).

- [ ] **Step 3: Criar `backend/app/models/tipo_calibragem.py`**

```python
from sqlalchemy import Column, Integer, String, Text, Numeric
from app.models.database import Base


class TipoCalibragem(Base):
    __tablename__ = "tipos_calibragem"

    id = Column(Integer, primary_key=True, index=True)
    descricao = Column(String(200), nullable=False)
    texto = Column(Text, nullable=True)
    valor = Column(Numeric(10, 2), nullable=False, default=0)
```

- [ ] **Step 4: Registrar em `backend/app/models/__init__.py`** — adicione `from app.models.tipo_calibragem import TipoCalibragem` e inclua `"TipoCalibragem"` no `__all__`.

- [ ] **Step 5: Adicionar `TipoCalibragemOut` em `backend/app/schemas/ordens.py`** (no fim):

```python
class TipoCalibragemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    descricao: str
```

- [ ] **Step 6: Criar `backend/app/api/tipos_calibragem.py`**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, TipoCalibragem
from app.api.deps import get_current_usuario
from app.schemas.ordens import TipoCalibragemOut

router = APIRouter(prefix="/tipos-calibragem", tags=["tipos-calibragem"])


@router.get("", response_model=list[TipoCalibragemOut])
def listar(db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    return db.query(TipoCalibragem).order_by(TipoCalibragem.descricao).all()
```

- [ ] **Step 7: Registrar o router em `backend/app/main.py`**

```python
from app.api import tipos_calibragem
app.include_router(tipos_calibragem.router)
```

- [ ] **Step 8: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_tipos_calibragem.py -q`
Expected: PASS (2 passed).

- [ ] **Step 9: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/app/models/tipo_calibragem.py backend/app/models/__init__.py backend/app/schemas/ordens.py backend/app/api/tipos_calibragem.py backend/app/main.py backend/tests/test_tipos_calibragem.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): catalogo tipos_calibragem (modelo + GET)"
```

---

### Task 2: Calibração no portão Lab→Pós + espelhamento

**Files:**
- Modify: `backend/app/schemas/ordens.py` (estender `AvancarIn`)
- Modify: `backend/app/api/ordens_acoes.py` (helper `espelhar_calibracao`)
- Modify: `backend/app/api/ordens.py` (branch `origem == 5`)
- Test: `backend/tests/test_ordens_avancar.py` (estender)

- [ ] **Step 1: Escrever os testes falhando** — acrescente ao FIM de `backend/tests/test_ordens_avancar.py`:

```python
def test_avancar_lab_com_calibracao_espelha(client, usuario_lab, fases_seed, os_base, db_session):
    from app.models import Ordem, EquipamentoCliente
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"], fase=5, situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    h = _headers(client, "lab", "senha123")
    r = client.post(f"/ordens/{o.id}/avancar", json={
        "calib_cert": "HF999", "calib_temp": "22.0", "calib_teste_media": "0,16",
        "calib_situacao": "Aprovado", "prox_calibragem": "2027-06-03",
    }, headers=h)
    assert r.status_code == 200
    assert r.json()["fase"] == 6
    assert r.json()["calib_cert"] == "HF999"
    assert r.json()["calib_situacao"] == "Aprovado"
    ec = db_session.get(EquipamentoCliente, os_base["equipamento_cliente"])
    db_session.refresh(ec)
    assert ec.calib_cert == "HF999"
    assert ec.calib_situacao == "Aprovado"
    assert str(ec.prox_calibragem) == "2027-06-03"
    assert ec.ult_calibragem is not None


def test_avancar_lab_manutencao_pura_nao_espelha(client, usuario_lab, fases_seed, os_base, db_session):
    from app.models import Ordem, EquipamentoCliente
    ec0 = db_session.get(EquipamentoCliente, os_base["equipamento_cliente"])
    ec0.calib_cert = "ORIG"
    db_session.commit()
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"], fase=5, situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    h = _headers(client, "lab", "senha123")
    r = client.post(f"/ordens/{o.id}/avancar", json={"obs": "só manutenção"}, headers=h)
    assert r.status_code == 200 and r.json()["fase"] == 6
    ec = db_session.get(EquipamentoCliente, os_base["equipamento_cliente"])
    db_session.refresh(ec)
    assert ec.calib_cert == "ORIG"  # inalterado


def test_avancar_lab_sem_equipamento_nao_quebra(client, usuario_lab, fases_seed, os_base, db_session):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=None, fase=5, situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    h = _headers(client, "lab", "senha123")
    r = client.post(f"/ordens/{o.id}/avancar", json={"calib_cert": "X"}, headers=h)
    assert r.status_code == 200 and r.json()["fase"] == 6


def test_calibracao_ignorada_fora_da_fase_lab(client, usuario_comum, fases_seed, os_base, db_session):
    # usuario_comum = Expedição (responsável pela fase 4); calib enviado em 4->5 deve ser ignorado
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"], fase=4, situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    h = _headers(client, "comum", "senha123")
    r = client.post(f"/ordens/{o.id}/avancar", json={"calib_cert": "NAOAPLICA"}, headers=h)
    assert r.status_code == 200 and r.json()["fase"] == 5
    assert r.json()["calib_cert"] is None
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_ordens_avancar.py -q`
Expected: FAIL (campos de calibração não gravam / não espelham).

- [ ] **Step 3: Estender `AvancarIn` em `backend/app/schemas/ordens.py`** — adicione os campos (mantendo `obs`/`cod_retorno`):

```python
class AvancarIn(BaseModel):
    obs: str | None = None
    cod_retorno: str | None = None
    tipo_calibragem: int | None = None
    calib_cert: str | None = None
    calib_temp: str | None = None
    calib_pressao: str | None = None
    calib_teste1: str | None = None
    calib_teste2: str | None = None
    calib_teste3: str | None = None
    calib_teste_media: str | None = None
    calib_situacao: str | None = None
    pdf_certificado: str | None = None
    prox_calibragem: datetime | None = None
```
(`datetime` já é importado no topo do arquivo — confirme; se não, adicione `from datetime import datetime`.)

- [ ] **Step 4: Adicionar `espelhar_calibracao` em `backend/app/api/ordens_acoes.py`**

```python
_CAMPOS_CALIB = (
    "calib_cert", "calib_temp", "calib_pressao", "calib_teste1", "calib_teste2",
    "calib_teste3", "calib_teste_media", "calib_situacao",
)


def espelhar_calibracao(db: Session, ordem) -> None:
    """Copia os resultados de calibração da OS para o equipamento_cliente."""
    from app.models import EquipamentoCliente
    if not ordem.equipamento_cliente:
        return
    ec = db.query(EquipamentoCliente).filter(EquipamentoCliente.id == ordem.equipamento_cliente).first()
    if ec is None:
        return
    for campo in _CAMPOS_CALIB:
        valor = getattr(ordem, campo)
        if valor is not None:
            setattr(ec, campo, valor)
    if ordem.data_calibracao is not None:
        ec.ult_calibragem = ordem.data_calibracao.date()
    if ordem.prox_calibragem is not None:
        ec.prox_calibragem = ordem.prox_calibragem.date()
```

- [ ] **Step 5: Enriquecer o branch `origem == 5` em `backend/app/api/ordens.py`**

Atualize o import de `ordens_acoes` para incluir `espelhar_calibracao` (junto de `agora, registrar_log, exige_funcao_da_fase`). Substitua o branch:
```python
    if origem == 5:                       # Laboratório -> Pós-Vendas
        ordem.data_calibracao = agora()
        texto = "Calibração/manutenção concluída"
```
por:
```python
    if origem == 5:                       # Laboratório -> Pós-Vendas
        ordem.data_calibracao = agora()
        for campo in (
            "tipo_calibragem", "calib_cert", "calib_temp", "calib_pressao",
            "calib_teste1", "calib_teste2", "calib_teste3", "calib_teste_media",
            "calib_situacao", "pdf_certificado", "prox_calibragem",
        ):
            valor = getattr(dados, campo)
            if valor is not None:
                setattr(ordem, campo, valor)
        espelhar_calibracao(db, ordem)
        texto = "Calibração/manutenção concluída"
```

- [ ] **Step 6: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_ordens_avancar.py -q`
Expected: PASS (6 anteriores + 4 novos = 10).

- [ ] **Step 7: Rodar a suíte backend inteira**

Run: `docker compose exec -T backend python -m pytest -q`
Expected: verde (123 + 2 da Task 1 + 4 da Task 2 = 129).

- [ ] **Step 8: Commit**

```bash
git -C /d/GitHub/GestorHS add backend/app/schemas/ordens.py backend/app/api/ordens_acoes.py backend/app/api/ordens.py backend/tests/test_ordens_avancar.py
git -C /d/GitHub/GestorHS commit -m "feat(backend): calibracao no portao Lab->Pos + espelhamento no aparelho"
```

---

### Task 3: Frontend — API de calibração

**Files:**
- Modify: `frontend/src/app/cadastros/api.ts` (`tiposCalibragemApi`)
- Modify: `frontend/src/app/ordens/api.ts` (`AvancarPayload` + `TRANSICOES[5]`)
- Test: `frontend/src/app/ordens/api.test.ts` (estender)
- Test: `frontend/src/app/cadastros/fases-funcoes.api.test.ts` (estender)

- [ ] **Step 1: Escrever os testes falhando**

Em `frontend/src/app/ordens/api.test.ts`, acrescente ao fim do `describe`:
```ts
  it('avancar inclui campos de calibração no corpo', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ id: 1 }))
    vi.stubGlobal('fetch', f)
    await ordensApi.avancar(5, { calib_cert: 'HF1', calib_teste_media: '0,1', prox_calibragem: '2027-06-03' })
    const body = String(f.mock.calls[0][1].body)
    expect(body).toContain('calib_cert')
    expect(body).toContain('prox_calibragem')
  })
```
Em `frontend/src/app/cadastros/fases-funcoes.api.test.ts`, acrescente ao fim do `describe`:
```ts
  it('tiposCalibragemApi.listar faz GET /tipos-calibragem', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse([]))
    vi.stubGlobal('fetch', f)
    const { tiposCalibragemApi } = await import('./api')
    await tiposCalibragemApi.listar()
    expect(String(f.mock.calls[0][0])).toContain('/tipos-calibragem')
  })
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm --prefix frontend run test -- ordens/api cadastros/fases-funcoes`
Expected: FAIL (campos/`tiposCalibragemApi` ausentes).

- [ ] **Step 3: Estender `frontend/src/app/cadastros/api.ts`** (no fim):

```ts
export interface TipoCalibragem {
  id: number
  descricao: string
}

export const tiposCalibragemApi = {
  listar: (): Promise<TipoCalibragem[]> => apiJson<TipoCalibragem[]>('/tipos-calibragem'),
}
```

- [ ] **Step 4: Estender `frontend/src/app/ordens/api.ts`**

Atualize a interface `AvancarPayload`:
```ts
export interface AvancarPayload {
  obs?: string | null
  cod_retorno?: string | null
  tipo_calibragem?: number | null
  calib_cert?: string | null
  calib_temp?: string | null
  calib_pressao?: string | null
  calib_teste1?: string | null
  calib_teste2?: string | null
  calib_teste3?: string | null
  calib_teste_media?: string | null
  calib_situacao?: string | null
  pdf_certificado?: string | null
  prox_calibragem?: string | null
}
```
E na constante `TRANSICOES`, troque a entrada `5` para:
```ts
  5: { rotulo: 'Concluir laboratório', pedeCalibracao: true },
```
E o tipo de `TRANSICOES` passa a:
```ts
export const TRANSICOES: Record<number, { rotulo: string; pedeCodRetorno?: boolean; pedeCalibracao?: boolean }> = {
```

- [ ] **Step 5: Rodar e ver passar**

Run: `npm --prefix frontend run test -- ordens/api cadastros/fases-funcoes`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/app/cadastros/api.ts frontend/src/app/ordens/api.ts frontend/src/app/ordens/api.test.ts frontend/src/app/cadastros/fases-funcoes.api.test.ts
git -C /d/GitHub/GestorHS commit -m "feat(frontend): tiposCalibragemApi + campos de calibracao em AvancarPayload"
```

---

### Task 4: `AvancarModal` em modo calibração + wiring

**Files:**
- Modify: `frontend/src/app/ordens/AvancarModal.tsx` (reescrever)
- Modify: `frontend/src/app/ordens/OrdemDetailPage.tsx` (passar `pedeCalibracao` + link de PDF)

> UI — verificada por `lint` + `build`.

- [ ] **Step 1: Reescrever `frontend/src/app/ordens/AvancarModal.tsx`** com o conteúdo completo:

```tsx
import { useEffect, useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { ApiError } from '../../lib/api'
import { tiposCalibragemApi, type TipoCalibragem } from '../cadastros/api'
import { ordensApi, type OrdemDetalhe, type AvancarPayload } from './api'

function maisUmAno(): string {
  const d = new Date()
  d.setFullYear(d.getFullYear() + 1)
  return d.toISOString().slice(0, 10)
}

function calcMedia(t1: string, t2: string, t3: string): string {
  const vals = [t1, t2, t3]
  if (vals.some((v) => v.trim() === '')) return ''
  const nums = vals.map((v) => Number(v.replace(',', '.')))
  if (nums.some((n) => Number.isNaN(n))) return ''
  return ((nums[0] + nums[1] + nums[2]) / 3).toFixed(2).replace('.', ',')
}

export function AvancarModal({ os, rotulo, pedeCodRetorno, pedeCalibracao, onClose, onConcluido }: {
  os: OrdemDetalhe
  rotulo: string
  pedeCodRetorno?: boolean
  pedeCalibracao?: boolean
  onClose: () => void
  onConcluido: (os: OrdemDetalhe) => void
}) {
  const [obs, setObs] = useState('')
  const [codRetorno, setCodRetorno] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  const [tipos, setTipos] = useState<TipoCalibragem[]>([])
  const [tipoCal, setTipoCal] = useState('')
  const [cert, setCert] = useState('')
  const [temp, setTemp] = useState('')
  const [pressao, setPressao] = useState('')
  const [t1, setT1] = useState('')
  const [t2, setT2] = useState('')
  const [t3, setT3] = useState('')
  const [media, setMedia] = useState('')
  const [mediaEditada, setMediaEditada] = useState(false)
  const [situacao, setSituacao] = useState('')
  const [pdf, setPdf] = useState('')
  const [prox, setProx] = useState(pedeCalibracao ? maisUmAno() : '')

  useEffect(() => {
    if (!pedeCalibracao) return
    let ativo = true
    void tiposCalibragemApi.listar().then((ts) => { if (ativo) setTipos(ts) }).catch(() => {})
    return () => { ativo = false }
  }, [pedeCalibracao])

  useEffect(() => {
    if (!pedeCalibracao || mediaEditada) return
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMedia(calcMedia(t1, t2, t3))
  }, [t1, t2, t3, mediaEditada, pedeCalibracao])

  async function submeter(e: FormEvent) {
    e.preventDefault()
    setErro('')
    if (pedeCodRetorno && !codRetorno.trim()) {
      setErro('Código de retorno é obrigatório.')
      return
    }
    const payload: AvancarPayload = {
      obs: obs.trim() || null,
      cod_retorno: pedeCodRetorno ? codRetorno.trim() : null,
    }
    if (pedeCalibracao) {
      payload.tipo_calibragem = tipoCal ? Number(tipoCal) : null
      payload.calib_cert = cert.trim() || null
      payload.calib_temp = temp.trim() || null
      payload.calib_pressao = pressao.trim() || null
      payload.calib_teste1 = t1.trim() || null
      payload.calib_teste2 = t2.trim() || null
      payload.calib_teste3 = t3.trim() || null
      payload.calib_teste_media = media.trim() || null
      payload.calib_situacao = situacao.trim() || null
      payload.pdf_certificado = pdf.trim() || null
      payload.prox_calibragem = prox || null
    }
    setEnviando(true)
    try {
      const atualizada = await ordensApi.avancar(os.id, payload)
      onConcluido(atualizada)
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao avançar')
    } finally {
      setEnviando(false)
    }
  }

  const inputClass = 'w-full px-3 py-2 text-sm rounded-lg border border-border bg-background-elevated text-slate-300 focus:outline-none focus:ring-2 focus:ring-primary/50'

  return (
    <Modal
      open
      onClose={onClose}
      title={rotulo}
      footer={
        <>
          <button type="button" onClick={onClose} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">Cancelar</button>
          <button type="submit" form="form-avancar" disabled={enviando} className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all">Confirmar</button>
        </>
      }
    >
      <form id="form-avancar" className="space-y-4" onSubmit={submeter}>
        {pedeCodRetorno && (
          <Input id="cod-retorno" label="Código de retorno" value={codRetorno} onChange={(e) => setCodRetorno(e.target.value)} required />
        )}
        {pedeCalibracao && (
          <>
            <Select id="tipo-cal" label="Tipo de calibragem" value={tipoCal} onChange={(e) => setTipoCal(e.target.value)}>
              <option value="">— selecione —</option>
              {tipos.map((t) => <option key={t.id} value={t.id}>{t.descricao}</option>)}
            </Select>
            <div className="grid grid-cols-2 gap-3">
              <Input id="cert" label="Nº do certificado" value={cert} onChange={(e) => setCert(e.target.value)} />
              <Input id="situacao" label="Situação" value={situacao} onChange={(e) => setSituacao(e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Input id="temp" label="Temperatura" value={temp} onChange={(e) => setTemp(e.target.value)} />
              <Input id="pressao" label="Pressão" value={pressao} onChange={(e) => setPressao(e.target.value)} />
            </div>
            <div className="grid grid-cols-3 gap-3">
              <Input id="t1" label="Teste 1" value={t1} onChange={(e) => setT1(e.target.value)} />
              <Input id="t2" label="Teste 2" value={t2} onChange={(e) => setT2(e.target.value)} />
              <Input id="t3" label="Teste 3" value={t3} onChange={(e) => setT3(e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Input id="media" label="Média dos testes" value={media} onChange={(e) => { setMediaEditada(true); setMedia(e.target.value) }} />
              <Input id="prox" label="Próxima calibração" type="date" value={prox} onChange={(e) => setProx(e.target.value)} />
            </div>
            <Input id="pdf" label="PDF do certificado (nome ou URL)" value={pdf} onChange={(e) => setPdf(e.target.value)} />
          </>
        )}
        <div>
          <label htmlFor="obs" className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">Observação</label>
          <textarea id="obs" value={obs} onChange={(e) => setObs(e.target.value)} rows={3} className={inputClass} />
        </div>
        {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      </form>
    </Modal>
  )
}
```

- [ ] **Step 2: Atualizar `frontend/src/app/ordens/OrdemDetailPage.tsx`** — duas edições:

(a) Na renderização do modal de avanço, passe `pedeCalibracao`:
```tsx
      {acao === 'avancar' && transicao && (
        <AvancarModal os={os} rotulo={transicao.rotulo} pedeCodRetorno={transicao.pedeCodRetorno} pedeCalibracao={transicao.pedeCalibracao} onClose={() => setAcao(null)} onConcluido={aoConcluir} />
      )}
```

(b) No bloco "Resultados da calibração", troque a linha do PDF:
```tsx
            <Campo label="PDF" valor={os.pdf_certificado} />
```
por:
```tsx
            <Campo label="PDF" valor={os.pdf_certificado && os.pdf_certificado.startsWith('http')
              ? <a href={os.pdf_certificado} target="_blank" rel="noreferrer" className="text-primary hover:underline">abrir</a>
              : os.pdf_certificado} />
```

- [ ] **Step 3: Verificar lint + build**

Run: `npm --prefix frontend run lint`
Expected: sem erros.
Run: `npm --prefix frontend run build`
Expected: limpo.

- [ ] **Step 4: Commit**

```bash
git -C /d/GitHub/GestorHS add frontend/src/app/ordens/AvancarModal.tsx frontend/src/app/ordens/OrdemDetailPage.tsx
git -C /d/GitHub/GestorHS commit -m "feat(frontend): formulario de calibracao no portao Laboratorio + link de PDF"
```

---

### Task 5: Verificação final

**Files:** nenhum.

- [ ] **Step 1: Backend completo**

Run: `docker compose exec -T backend python -m pytest -q`
Expected: ~129 passed.

- [ ] **Step 2: Frontend completo**

Run: `npm --prefix frontend run test`
Expected: ~64 passed.

- [ ] **Step 3: Lint + build**

Run: `npm --prefix frontend run lint` (sem erros) e `npm --prefix frontend run build` (limpo).

- [ ] **Step 4: (sem commit — verificação)** Reporte os números. Se algo falhar, corrija na task correspondente.

---

## Notas para o executor

- O espelhamento só ocorre em 5→6 e só copia os campos não-nulos enviados; `os_atual` do aparelho NÃO é alterado (já é a OS, do abrir). Cancelar e demais fases não espelham.
- `ec.ult_calibragem`/`prox_calibragem` são `Date`; converta de `datetime` com `.date()` (já no helper). `data_calibracao` é setado server-side com `agora()`.
- `new Date()` é permitido no código do navegador (a restrição vale só para scripts de workflow).
- A média recalcula automaticamente ao mudar os 3 testes, exceto se o usuário editou a média manualmente (`mediaEditada`). O `eslint-disable react-hooks/set-state-in-effect` fica só na linha do `setMedia` no efeito.
- Após a Task 5, o controlador roda o E2E não-destrutivo (abrir o modal da fase Laboratório, conferir form rico + média automática + próxima calibração; sem submeter).
```
