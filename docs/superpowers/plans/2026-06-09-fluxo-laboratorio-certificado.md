# Fluxo correto do laboratório (gerar → revisar → concluir) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mover os dados de calibração do "Concluir laboratório" para o passo "Gerar certificado"; o concluir-lab passa a pedir só próxima calibração + observação e é bloqueado sem certificado gerado.

**Architecture:** O endpoint de gerar certificado passa a receber os dados de calibração (salva em `ordens` + `data_calibracao` + gera o HTML). O avanço 5→6 deixa de capturar calibração/auto-gerar, exige certificado e grava só `prox_calibragem` + espelha. Frontend: novo `GerarCertificadoModal` (form de calibração) e `AvancarModal` enxuto para a fase 5.

**Tech Stack:** Backend FastAPI + SQLAlchemy + pytest (SQLite). Frontend React + TS + Vite + Vitest.

**Spec:** `docs/superpowers/specs/2026-06-09-fluxo-laboratorio-certificado-design.md`

**Contexto:** branch `feat/geracao-certificado` (não mesclada). Já existem: motor `certificado_gerar` (gerar_certificados/tipos_para/montar_contexto/preencher), `os_certificados`, endpoints `GET/POST /ordens/{id}/[gerar-]certificado(s)` (POST hoje sem corpo), `AvancarModal` com modo `pedeCalibracao`, seção "Certificados" no `OrdemDetailPage` com botão "Gerar/Regerar". `agora()` em `app.api.ordens_acoes`. Escrita cert = `require_funcao("Laboratório","Administrador")`. Fixtures: `usuario_admin`, `usuario_lab`, `usuario_comum`(Expedição), `usuario_comercial`, `os_base`, `fases_seed`.

**Escopo:** só Calibração. Sem migração de banco (reusa colunas/tabelas).

---

## Task 1: Schemas — `GerarCertificadoIn`, enxugar `AvancarIn`, expor calib no `OrdemOut`

**Files:**
- Modify: `backend/app/schemas/ordens.py`
- Test: `backend/tests/test_recebimento_schemas.py` (adicionar) — ou um novo `test_lab_schemas.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_lab_schemas.py`:

```python
def test_gerar_certificado_in():
    from app.schemas.ordens import GerarCertificadoIn
    m = GerarCertificadoIn(tipo_calibragem=2, calib_cert="C-1", calib_temp="25",
                           calib_pressao="1", calib_teste1="a", calib_teste2="b",
                           calib_teste3="c", calib_teste_media="0,20", calib_situacao="Aprovado")
    assert m.calib_cert == "C-1" and m.tipo_calibragem == 2


def test_avancar_in_sem_calib():
    from app.schemas.ordens import AvancarIn
    m = AvancarIn(obs="x")
    assert not hasattr(m, "calib_cert")
    assert not hasattr(m, "calib_teste1")
    assert not hasattr(m, "pdf_certificado")
    # mantém os usados no avanço
    assert m.obs == "x"
    m2 = AvancarIn(prox_calibragem=None, cod_retorno=None)
    assert m2.prox_calibragem is None


def test_ordem_out_expoe_calib_para_prefill(db_session):
    from app.models import Cliente, Ordem
    from app.schemas.ordens import OrdemOut
    cli = Cliente(nome="C"); db_session.add(cli); db_session.flush()
    o = Ordem(cliente=cli.id, situacao="E", tipo_calibragem=3,
              calib_teste1="a", calib_teste2="b", calib_teste3="c")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    out = OrdemOut.model_validate(o)
    assert out.tipo_calibragem == 3
    assert out.calib_teste1 == "a" and out.calib_teste2 == "b" and out.calib_teste3 == "c"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_lab_schemas.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

Em `backend/app/schemas/ordens.py`:
- Substitua a classe `AvancarIn` inteira por (mantém só o que o avanço usa):
```python
class AvancarIn(BaseModel):
    obs: str | None = None
    cod_retorno: str | None = None
    prox_calibragem: datetime | None = None
```
- Adicione, logo após `AvancarIn`, a nova classe:
```python
class GerarCertificadoIn(BaseModel):
    tipo_calibragem: int | None = None
    calib_cert: str | None = None
    calib_temp: str | None = None
    calib_pressao: str | None = None
    calib_teste1: str | None = None
    calib_teste2: str | None = None
    calib_teste3: str | None = None
    calib_teste_media: str | None = None
    calib_situacao: str | None = None
```
- Em `OrdemOut`, adicione os campos que faltam para o prefill (junto aos demais `calib_*`):
```python
    tipo_calibragem: int | None = None
    calib_teste1: str | None = None
    calib_teste2: str | None = None
    calib_teste3: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_lab_schemas.py -q` → 3 passed.

> A suíte inteira vai FALHAR agora (o endpoint `avancar` e seus testes ainda usam os campos calib do `AvancarIn`). Isso é esperado e será corrigido nas Tasks 2–3. Não rode a suíte inteira ainda; só o arquivo desta task.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/ordens.py backend/tests/test_lab_schemas.py
git commit -m "feat(lab): GerarCertificadoIn + AvancarIn sem calib + OrdemOut expõe calib p/ prefill"
```

---

## Task 2: Endpoint gerar-certificado recebe os dados de calibração

**Files:**
- Modify: `backend/app/api/certificados_os.py`
- Test: `backend/tests/test_certificado_os_api.py` (adicionar)

- [ ] **Step 1: Write the failing test**

Adicione ao final de `backend/tests/test_certificado_os_api.py`:

```python
def test_gerar_com_dados_salva_e_preenche(client, usuario_admin, db_session):
    h = _headers(client, "admin", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C",), tipo_servico="C")
    body = {
        "tipo_calibragem": None, "calib_cert": "CERT-9", "calib_temp": "25",
        "calib_pressao": "1013", "calib_teste1": "0,10", "calib_teste2": "0,20",
        "calib_teste3": "0,30", "calib_teste_media": "0,20", "calib_situacao": "Aprovado",
    }
    r = client.post(f"/ordens/{oid}/gerar-certificado", json=body, headers=h)
    assert r.status_code == 200
    # dados salvos na OS + data_calibracao setada
    from app.models import Ordem
    o = db_session.get(Ordem, oid); db_session.refresh(o)
    assert o.calib_cert == "CERT-9" and o.calib_temp == "25"
    assert o.calib_situacao == "Aprovado"
    assert o.data_calibracao is not None
    # certificado preenchido com os dados (o modelo usa [serie]; checamos que gerou)
    assert any(c["tipo"] == "C" and c["html"] for c in r.json())


def test_gerar_sem_corpo_regenera_sem_alterar(client, usuario_admin, db_session):
    h = _headers(client, "admin", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C",), tipo_servico="C")
    client.post(f"/ordens/{oid}/gerar-certificado", json={"calib_cert": "X1"}, headers=h)
    from app.models import Ordem
    # regenera sem corpo → não zera calib_cert
    r = client.post(f"/ordens/{oid}/gerar-certificado", headers=h)
    assert r.status_code == 200
    o = db_session.get(Ordem, oid); db_session.refresh(o)
    assert o.calib_cert == "X1"
```

(O helper `_os_com_modelo` já existe no arquivo — cria OS fase 5 com cliente/equip/modelo.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_certificado_os_api.py::test_gerar_com_dados_salva_e_preenche -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

Substitua o conteúdo de `backend/app/api/certificados_os.py` por:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Ordem, OSCertificado
from app.api.deps import get_current_usuario, require_funcao
from app.api.ordens_acoes import agora
from app.core.certificado_gerar import gerar_certificados, tipos_para
from app.schemas.ordens import GerarCertificadoIn
from app.schemas.certificados_modelo import OSCertificadoOut

router = APIRouter(tags=["certificados-os"])

_gerar = require_funcao("Laboratório", "Administrador")

_CAMPOS_CALIB = (
    "tipo_calibragem", "calib_cert", "calib_temp", "calib_pressao",
    "calib_teste1", "calib_teste2", "calib_teste3", "calib_teste_media", "calib_situacao",
)


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
def gerar(ordem_id: int, dados: GerarCertificadoIn | None = None, db: Session = Depends(get_db), _: Usuario = Depends(_gerar)):
    ordem = _os_ou_404(db, ordem_id)
    if dados is not None:
        for campo in _CAMPOS_CALIB:
            setattr(ordem, campo, getattr(dados, campo))
        ordem.data_calibracao = agora()
        db.flush()
    gerados = gerar_certificados(db, ordem, tipos_para(ordem))
    db.commit()
    for g in gerados:
        db.refresh(g)
    return [OSCertificadoOut.model_validate(c) for c in gerados]
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_certificado_os_api.py -q` → tudo verde (incl. os 2 novos + os antigos sem corpo).

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/certificados_os.py backend/tests/test_certificado_os_api.py
git commit -m "feat(lab): gerar-certificado recebe dados de calibração e seta data_calibracao"
```

---

## Task 3: Avanço 5→6 — exige certificado, grava só próxima calibração

**Files:**
- Modify: `backend/app/api/ordens.py` (branch `origem == 5`; imports)
- Test: `backend/tests/test_ordens_avancar.py`

- [ ] **Step 1: Write/adjust tests**

Em `backend/tests/test_ordens_avancar.py`:
- O teste `test_cadeia_feliz_completa` faz `5 -> 6` com `json={}` e espera `data_calibracao is not None`. Agora o 5→6 exige certificado e NÃO seta data_calibracao. **Ajuste** esse teste: antes do avanço 5→6, gere um certificado; e troque a asserção. Substitua o trecho do 5→6 nesse teste por:
```python
    # gera certificado (pré-requisito do concluir lab) — precisa de modelo p/ o aparelho
    from app.models import CertificadoModelo
    db_session.add(CertificadoModelo(equipamento=os_base["equipamento"], tipo="C", texto="<p>[serie]</p>"))
    db_session.commit()
    client.post(f"/ordens/{oid}/gerar-certificado", json={"calib_cert": "C-1"}, headers=hl)
    # 5 -> 6 (Laboratório) — só próxima calibração + obs
    r = client.post(f"/ordens/{oid}/avancar", json={"prox_calibragem": "2027-06-09"}, headers=hl)
    assert r.json()["fase"] == 6
```
- **Substitua** os dois testes adicionados na feature anterior (`test_avanco_5_6_gera_certificado` e `test_avanco_5_6_nao_quebra_se_geracao_falha`) por estes:
```python
def test_concluir_lab_bloqueia_sem_certificado(client, usuario_comum, usuario_lab, fases_seed, os_base):
    he = _headers(client, "comum", "senha123")
    hl = _headers(client, "lab", "senha123")
    oid = _abrir(client, he, os_base["equipamento_cliente"])["id"]
    client.post(f"/ordens/{oid}/avancar", json={}, headers=he)  # 4->5
    r = client.post(f"/ordens/{oid}/avancar", json={"prox_calibragem": "2027-06-09"}, headers=hl)  # 5->6 sem cert
    assert r.status_code == 409


def test_concluir_lab_com_certificado(client, usuario_comum, usuario_lab, fases_seed, os_base, db_session):
    from app.models import CertificadoModelo
    db_session.add(CertificadoModelo(equipamento=os_base["equipamento"], tipo="C", texto="<p>[serie]</p>"))
    db_session.commit()
    he = _headers(client, "comum", "senha123")
    hl = _headers(client, "lab", "senha123")
    oid = _abrir(client, he, os_base["equipamento_cliente"])["id"]
    client.post(f"/ordens/{oid}/avancar", json={}, headers=he)  # 4->5
    client.post(f"/ordens/{oid}/gerar-certificado", json={"calib_cert": "C-1"}, headers=hl)
    r = client.post(f"/ordens/{oid}/avancar", json={"prox_calibragem": "2027-06-09"}, headers=hl)  # 5->6
    assert r.status_code == 200 and r.json()["fase"] == 6
    assert r.json()["prox_calibragem"] is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_ordens_avancar.py -q`
Expected: FAIL (o 5→6 ainda grava calib/auto-gera e não exige cert).

- [ ] **Step 3: Implement**

Em `backend/app/api/ordens.py`:
- Garanta o import: `from app.models import ... , OSCertificado` (junte `OSCertificado` ao import existente de `app.models`).
- Remova o import no topo `from app.core.certificado_gerar import gerar_certificados, tipos_para` (não é mais usado no avançar). E o `import logging` adicionado antes pode permanecer ou sair (se não usado em outro ponto, remova para não quebrar lint).
- Substitua TODO o branch `if origem == 5:` (das linhas que setam data_calibracao/calib_*/geração) por:
```python
    if origem == 5:                       # Laboratório -> Pós-Vendas
        tem_cert = db.query(OSCertificado).filter(OSCertificado.os == ordem.id).first() is not None
        if not tem_cert:
            raise HTTPException(status_code=409, detail="gere o certificado antes de concluir o laboratório")
        if dados.prox_calibragem is not None:
            ordem.prox_calibragem = dados.prox_calibragem
        espelhar_calibracao(db, ordem)
        texto = "Laboratório concluído"
```

> `espelhar_calibracao` copia `calib_*` + `prox_calibragem` + `ult_calibragem` para o `equipamento_cliente`; como `calib_*` já foram salvos na geração e `prox_calibragem` acabou de ser setado, o espelho fica completo.

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_ordens_avancar.py -q` → verde.
Run: `cd backend && python -m pytest -q` → tudo verde (a suíte volta ao verde após Tasks 1–3).

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/ordens.py backend/tests/test_ordens_avancar.py
git commit -m "feat(lab): concluir laboratório exige certificado e grava só próxima calibração"
```

---

## Task 4: Frontend api — payloads do novo fluxo

**Files:**
- Modify: `frontend/src/app/ordens/api.ts`
- Test: `frontend/src/app/ordens/api.certificado.test.ts` (adicionar)

- [ ] **Step 1: Write/adjust tests**

Adicione ao `frontend/src/app/ordens/api.certificado.test.ts`:

```ts
  it('gerarCertificado com dados de calibração', async () => {
    await ordensApi.gerarCertificado(5, { calib_cert: 'C-1', calib_temp: '25' })
    expect(apiJson).toHaveBeenCalledWith('/ordens/5/gerar-certificado', { method: 'POST', body: JSON.stringify({ calib_cert: 'C-1', calib_temp: '25' }) })
  })
  it('gerarCertificado sem dados (regerar)', async () => {
    await ordensApi.gerarCertificado(5)
    expect(apiJson).toHaveBeenCalledWith('/ordens/5/gerar-certificado', { method: 'POST' })
  })
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/app/ordens/api.certificado.test.ts`
Expected: FAIL.

- [ ] **Step 3: Implement**

Em `frontend/src/app/ordens/api.ts`:
- `AvancarPayload`: remova os campos `tipo_calibragem` e `calib_*` (mantém `obs`, `cod_retorno`, `prox_calibragem`). Resultado:
```ts
export interface AvancarPayload {
  obs?: string | null
  cod_retorno?: string | null
  prox_calibragem?: string | null
}
```
- `OrdemDetalhe`: adicione (junto aos `calib_*` existentes) os campos de prefill:
```ts
  tipo_calibragem: number | null
  calib_teste1: string | null
  calib_teste2: string | null
  calib_teste3: string | null
```
- Novo payload + ajuste do método:
```ts
export interface GerarCertificadoPayload {
  tipo_calibragem?: number | null
  calib_cert?: string | null
  calib_temp?: string | null
  calib_pressao?: string | null
  calib_teste1?: string | null
  calib_teste2?: string | null
  calib_teste3?: string | null
  calib_teste_media?: string | null
  calib_situacao?: string | null
}
```
e substitua `gerarCertificado`:
```ts
  gerarCertificado: (id: number, payload?: GerarCertificadoPayload): Promise<OSCertificado[]> =>
    apiJson<OSCertificado[]>(`/ordens/${id}/gerar-certificado`, payload
      ? { method: 'POST', body: JSON.stringify(payload) }
      : { method: 'POST' }),
```
- `TRANSICOES`: troque a entrada da fase 5:
```ts
export const TRANSICOES: Record<number, { rotulo: string; pedeCodRetorno?: boolean; pedeProxCalibragem?: boolean }> = {
  4: { rotulo: 'Encaminhar ao laboratório' },
  5: { rotulo: 'Concluir laboratório', pedeProxCalibragem: true },
  6: { rotulo: 'Registrar aceite' },
  7: { rotulo: 'Postar retorno', pedeCodRetorno: true },
}
```

- [ ] **Step 4: Run + typecheck**

Run: `cd frontend && npx vitest run src/app/ordens/api.certificado.test.ts` → verde.
Run: `cd frontend && npx tsc -b --noEmit` — ESPERADO falhar em `AvancarModal.tsx` (usa `pedeCalibracao`/calib) e `OrdemDetailPage.tsx` (gerarCertificados) — corrigidos nas Tasks 5–6. Se houver erro em outro arquivo, conserte.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/ordens/api.ts frontend/src/app/ordens/api.certificado.test.ts
git commit -m "feat(lab): payloads do novo fluxo (gerarCertificado com dados, AvancarPayload enxuto)"
```

---

## Task 5: `AvancarModal` enxuto + `GerarCertificadoModal`

**Files:**
- Modify: `frontend/src/app/ordens/AvancarModal.tsx`
- Create: `frontend/src/app/ordens/GerarCertificadoModal.tsx`

- [ ] **Step 1: Enxugar `AvancarModal`**

Reescreva `frontend/src/app/ordens/AvancarModal.tsx` removendo o modo calibração; para a fase 5 (`pedeProxCalibragem`), mostrar só Próxima calibração (date, default +1 ano) + Observação:

```tsx
import { useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { ApiError } from '../../lib/api'
import { ordensApi, type OrdemDetalhe, type AvancarPayload } from './api'

function maisUmAno(): string {
  const d = new Date()
  d.setFullYear(d.getFullYear() + 1)
  return d.toISOString().slice(0, 10)
}

export function AvancarModal({ os, rotulo, pedeCodRetorno, pedeProxCalibragem, onClose, onConcluido }: {
  os: OrdemDetalhe
  rotulo: string
  pedeCodRetorno?: boolean
  pedeProxCalibragem?: boolean
  onClose: () => void
  onConcluido: (os: OrdemDetalhe) => void
}) {
  const [obs, setObs] = useState('')
  const [codRetorno, setCodRetorno] = useState('')
  const [prox, setProx] = useState(pedeProxCalibragem ? maisUmAno() : '')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

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
    if (pedeProxCalibragem) payload.prox_calibragem = prox || null
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
        {pedeProxCalibragem && (
          <Input id="prox" label="Próxima calibração" type="date" value={prox} onChange={(e) => setProx(e.target.value)} />
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

- [ ] **Step 2: Criar `GerarCertificadoModal`**

Create `frontend/src/app/ordens/GerarCertificadoModal.tsx` (move a lógica de calibração + média do antigo AvancarModal):

```tsx
import { useEffect, useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { ApiError } from '../../lib/api'
import { tiposCalibragemApi, type TipoCalibragem } from '../cadastros/api'
import { ordensApi, type OrdemDetalhe, type OSCertificado, type GerarCertificadoPayload } from './api'

function calcMedia(t1: string, t2: string, t3: string): string {
  const vals = [t1, t2, t3]
  if (vals.some((v) => v.trim() === '')) return ''
  const nums = vals.map((v) => Number(v.replace(',', '.')))
  if (nums.some((n) => Number.isNaN(n))) return ''
  return ((nums[0] + nums[1] + nums[2]) / 3).toFixed(2).replace('.', ',')
}

export function GerarCertificadoModal({ os, onClose, onGerado }: {
  os: OrdemDetalhe
  onClose: () => void
  onGerado: (certs: OSCertificado[]) => void
}) {
  const [tipos, setTipos] = useState<TipoCalibragem[]>([])
  const [tipoCal, setTipoCal] = useState(os.tipo_calibragem ? String(os.tipo_calibragem) : '')
  const [cert, setCert] = useState(os.calib_cert ?? '')
  const [temp, setTemp] = useState(os.calib_temp ?? '')
  const [pressao, setPressao] = useState(os.calib_pressao ?? '')
  const [t1, setT1] = useState(os.calib_teste1 ?? '')
  const [t2, setT2] = useState(os.calib_teste2 ?? '')
  const [t3, setT3] = useState(os.calib_teste3 ?? '')
  const [media, setMedia] = useState(os.calib_teste_media ?? '')
  const [mediaEditada, setMediaEditada] = useState(!!os.calib_teste_media)
  const [situacao, setSituacao] = useState(os.calib_situacao ?? '')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    let ativo = true
    void tiposCalibragemApi.listar().then((ts) => { if (ativo) setTipos(ts) }).catch(() => {})
    return () => { ativo = false }
  }, [])

  useEffect(() => {
    if (mediaEditada) return
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMedia(calcMedia(t1, t2, t3))
  }, [t1, t2, t3, mediaEditada])

  async function submeter(e: FormEvent) {
    e.preventDefault()
    setErro(''); setEnviando(true)
    const payload: GerarCertificadoPayload = {
      tipo_calibragem: tipoCal ? Number(tipoCal) : null,
      calib_cert: cert.trim() || null,
      calib_temp: temp.trim() || null,
      calib_pressao: pressao.trim() || null,
      calib_teste1: t1.trim() || null,
      calib_teste2: t2.trim() || null,
      calib_teste3: t3.trim() || null,
      calib_teste_media: media.trim() || null,
      calib_situacao: situacao.trim() || null,
    }
    try {
      const certs = await ordensApi.gerarCertificado(os.id, payload)
      onGerado(certs)
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
      title="Gerar certificado de calibração"
      footer={
        <>
          <button type="button" onClick={onClose} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">Cancelar</button>
          <button type="submit" form="form-gerar-cert" disabled={enviando} className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all">Gerar</button>
        </>
      }
    >
      <form id="form-gerar-cert" className="space-y-4" onSubmit={submeter}>
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
        <Input id="media" label="Média dos testes" value={media} onChange={(e) => { setMediaEditada(true); setMedia(e.target.value) }} />
        {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      </form>
    </Modal>
  )
}
```

- [ ] **Step 3: Typecheck/lint/build (parcial)**

Run: `cd frontend && npx tsc -b --noEmit` — ESPERADO falhar só em `OrdemDetailPage.tsx` (ainda passa `pedeCalibracao` ao AvancarModal e usa `gerarCertificados` antigo). Corrigido na Task 6.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/ordens/AvancarModal.tsx frontend/src/app/ordens/GerarCertificadoModal.tsx
git commit -m "feat(lab): AvancarModal só próxima calibração/obs + novo GerarCertificadoModal"
```

---

## Task 6: `OrdemDetailPage` — botão Gerar (form) + concluir-lab

**Files:**
- Modify: `frontend/src/app/ordens/OrdemDetailPage.tsx`

- [ ] **Step 1: Wire up**

Em `frontend/src/app/ordens/OrdemDetailPage.tsx`:
- Importe `GerarCertificadoModal` de `./GerarCertificadoModal`.
- Adicione estado `const [gerandoCert, setGerandoCert] = useState(false)`.
- A fase de laboratório é 5. Calcule `const naLab = os.fase === 5`.
- Substitua a função `gerarCertificados` (que fazia POST sem corpo) e o botão "Gerar/Regerar": agora o botão **abre o modal** quando na fase Lab; o modal faz o POST com dados.
  - `acao` da `<Secao titulo="Certificados">`:
    ```tsx
    acao={podeGerarCert && naLab && <Button variant="secondary" onClick={() => setGerandoCert(true)}>{certs.length ? 'Regerar' : 'Gerar certificado'}</Button>}
    ```
  - Remova a função `gerarCertificados` antiga (sem corpo). 
- Renderize o modal (perto do `AvancarModal`/`CancelarModal`):
  ```tsx
  {gerandoCert && (
    <GerarCertificadoModal
      os={os}
      onClose={() => setGerandoCert(false)}
      onGerado={(cs) => { setCerts(cs); setGerandoCert(false); void ordensApi.obter(osId).then(setOs).catch(() => {}) }}
    />
  )}
  ```
  (Recarrega a OS porque `calib_*`/`data_calibracao` mudaram.)
- O uso do `AvancarModal`: troque a prop `pedeCalibracao={transicao.pedeCalibracao}` por `pedeProxCalibragem={transicao.pedeProxCalibragem}`.
- O `AvancarModal` para a fase 5 trata o 409 ("gere o certificado antes de concluir") via `ApiError` → já mostra `err.message`. Garanta que a mensagem apareça (o modal já renderiza `erro`).

> Mantenha o resto da seção (lista de certificados com Imprimir) e a exibição existente. Se `certs.length === 0`, o texto pode orientar: "Gere o certificado de calibração." quando `naLab && podeGerarCert`.

- [ ] **Step 2: Verificação**

Run: `cd frontend && npx tsc -b --noEmit && npx eslint src/app/ordens && npm run build && npx vitest run` → tudo verde.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/ordens/OrdemDetailPage.tsx
git commit -m "feat(lab): OS abre form de gerar certificado e conclui lab só com próxima calibração"
```

---

## Task 7: Changelog + E2E + memória

**Files:**
- Modify: `frontend/src/app/changelog/data.ts`

- [ ] **Step 1: Ajustar a entrada v1.4.0** (ainda não foi para produção — refletir o fluxo correto). Substitua os `itens` da v1.4.0 por:
```ts
    itens: [
      { tipo: 'novidade', texto: 'Certificado de calibração no laboratório — gere o certificado informando os dados da calibração (Nº, temperatura, pressão, testes, média, situação), revise e imprima; só então conclua o laboratório informando a próxima calibração e a observação.' },
      { tipo: 'melhoria', texto: 'Modelos de certificado por aparelho com dois tipos (Calibração e Manutenção) e biblioteca de imagens.' },
    ],
```

- [ ] **Step 2: Validar + commit**

Run: `cd frontend && npx vitest run src/app/changelog/ && npx tsc -b --noEmit && npm run build` → verde.
```bash
git add frontend/src/app/changelog/data.ts
git commit -m "feat(changelog): v1.4.0 reflete o fluxo de certificado no laboratório"
```

- [ ] **Step 3: E2E manual** — backend (:8000) + front (:5173). Login admin. Abrir uma OS na fase Laboratório (avançar uma do Recebido até o Lab, ou usar uma existente): na seção Certificados, "Gerar certificado de calibração" → preencher dados → Gerar → ver/Imprimir o certificado preenchido. Tentar "Concluir laboratório" sem gerar (em outra OS) → bloqueia. Concluir com próxima calibração + obs → fase Pós-Vendas. (Não há migração nova; nada a aplicar no banco.)

- [ ] **Step 4: Memória** — atualizar `project_gestorhs.md`: o fluxo do laboratório (gerar certificado com dados → revisar/imprimir → concluir só com próxima calibração + obs; conclusão bloqueada sem certificado; data_calibracao na geração).

---

## Self-Review

**Cobertura da spec:** GerarCertificadoIn + AvancarIn enxuto + OrdemOut prefill (Task 1); endpoint gerar recebe dados + data_calibracao (Task 2); avanço 5→6 exige cert + só prox/obs + sem auto-gen (Task 3); front payloads/TRANSICOES (Task 4); AvancarModal enxuto + GerarCertificadoModal (Task 5); OrdemDetailPage form+concluir (Task 6); changelog + E2E + memória (Task 7). Só Calibração; sem migração. ✓

**Placeholders:** nenhum; trechos de UI têm código completo.

**Consistência de tipos/nomes:** backend `GerarCertificadoIn` (campos calib), `AvancarIn{obs,cod_retorno,prox_calibragem}`, endpoint `POST /ordens/{id}/gerar-certificado` (corpo opcional), 409 sem cert; front `GerarCertificadoPayload`, `ordensApi.gerarCertificado(id, payload?)`, `AvancarPayload{obs,cod_retorno,prox_calibragem}`, `TRANSICOES[5].pedeProxCalibragem`, `AvancarModal` prop `pedeProxCalibragem`, `GerarCertificadoModal`, `OrdemDetalhe` ganha `tipo_calibragem`/`calib_teste1..3`. Consistentes. ✓
- `espelhar_calibracao` permanece no 5→6 (após prox_calibragem setado). data_calibracao só na geração. ✓
