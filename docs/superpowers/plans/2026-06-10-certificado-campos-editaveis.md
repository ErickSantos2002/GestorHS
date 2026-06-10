# Modal de certificado com campos editáveis — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Na modal de gerar/regerar certificado, permitir editar todos os campos (Cliente, Aparelho, Calibração) pré-preenchidos, sobrescrevendo valores só naquele certificado/OS sem alterar o cadastro.

**Architecture:** Overrides de identidade (cliente/aparelho) guardados num JSON `ordens.cert_overrides`; `montar_contexto` sobrepõe esses overrides aos valores derivados; um endpoint devolve os campos efetivos para pré-preencher a modal; a modal cresce em seções e envia tudo no gerar.

**Tech Stack:** FastAPI + SQLAlchemy + Alembic (backend), React 19 + TS + Vite + Tailwind (frontend), pytest/vitest.

**Branch:** `main`. Lançamento: v1.5.0.

**Spec:** `docs/superpowers/specs/2026-06-10-certificado-campos-editaveis-design.md`

**Chaves de override (8):** `nomecli, cnpj, endcli, modelo, marca, serie, patrimonio, datacompra`.

---

## Task 1: Coluna `cert_overrides` (migração + modelo)

**Files:**
- Create: `backend/alembic/versions/0008_cert_overrides.py`
- Modify: `backend/app/models/ordem.py`

Contexto: nova coluna JSON nullable em `ordens`. Os testes criam tabelas via `Base.metadata.create_all` (do modelo), então a coluna do modelo já vale na suíte; a migração é para o Postgres real (aplicada no fim).

- [ ] **Step 1: Criar a migração**

```python
# backend/alembic/versions/0008_cert_overrides.py
"""ordens.cert_overrides (JSON) — sobrescritas de identidade do certificado

Revision ID: 0008_cert_overrides
Revises: 0007_os_certificados
Create Date: 2026-06-10
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_cert_overrides"
down_revision = "0007_os_certificados"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ordens", sa.Column("cert_overrides", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("ordens", "cert_overrides")
```

- [ ] **Step 2: Adicionar a coluna ao modelo**

Em `backend/app/models/ordem.py`:
- No import do topo, acrescentar `JSON`: `from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime, Numeric, JSON`
- Logo após a linha `certificado = Column(Text, nullable=True)`, adicionar:
```python
    cert_overrides = Column(JSON, nullable=True)
```

- [ ] **Step 3: Verificar import do modelo (sanidade)**

Run: `docker compose exec -T backend python -c "from app.models import Ordem; print('cert_overrides' in Ordem.__table__.columns)"`
Expected: `True`

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/0008_cert_overrides.py backend/app/models/ordem.py
git commit -m "feat(cert): coluna ordens.cert_overrides (JSON) + migracao 0008"
```

---

## Task 2: `montar_contexto` aplica overrides

**Files:**
- Modify: `backend/app/core/certificado_gerar.py`
- Test: `backend/tests/test_certificado_gerar.py`

Contexto: após montar o contexto derivado, sobrepor os overrides salvos (só valores não-vazios).

- [ ] **Step 1: Escrever o teste (acrescentar ao fim de `backend/tests/test_certificado_gerar.py`)**

```python
def test_montar_contexto_aplica_overrides(db_session):
    from app.models import Cliente, Ordem
    from app.core.certificado_gerar import montar_contexto
    cli = Cliente(nome="ACME LTDA", cgc="111"); db_session.add(cli); db_session.flush()
    o = Ordem(cliente=cli.id, situacao="E", cert_overrides={"nomecli": "NOME ESPECIAL", "cnpj": "999"})
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    ctx = montar_contexto(db_session, o)
    assert ctx["nomecli"] == "NOME ESPECIAL"   # override vence
    assert ctx["cnpj"] == "999"


def test_montar_contexto_override_vazio_mantem_derivado(db_session):
    from app.models import Cliente, Ordem
    from app.core.certificado_gerar import montar_contexto
    cli = Cliente(nome="ACME LTDA"); db_session.add(cli); db_session.flush()
    o = Ordem(cliente=cli.id, situacao="E", cert_overrides={"nomecli": ""})
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    ctx = montar_contexto(db_session, o)
    assert ctx["nomecli"] == "ACME LTDA"        # vazio não sobrescreve
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_certificado_gerar.py -q -k override`
Expected: FAIL (override ainda não aplicado).

- [ ] **Step 3: Implementar o overlay**

Em `backend/app/core/certificado_gerar.py`, na função `montar_contexto`, trocar o `return { ... }` final por atribuir a um dict e sobrepor antes de retornar. Ou seja, onde hoje está:
```python
    return {
        "nomecli": (cli.nome if cli else "") or "",
        ...
        "datacli": hoje,
    }
```
trocar para:
```python
    ctx = {
        "nomecli": (cli.nome if cli else "") or "",
        ...
        "datacli": hoje,
    }
    for chave, valor in (ordem.cert_overrides or {}).items():
        if valor:
            ctx[chave] = valor
    return ctx
```
(manter exatamente o conteúdo do dict existente; só renomear para `ctx` e aplicar o overlay antes do `return ctx`.)

- [ ] **Step 4: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_certificado_gerar.py -q`
Expected: PASS (todos do arquivo).

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/certificado_gerar.py backend/tests/test_certificado_gerar.py
git commit -m "feat(cert): montar_contexto sobrepoe cert_overrides"
```

---

## Task 3: Schema + endpoints (campos efetivos + gravar overrides)

**Files:**
- Modify: `backend/app/schemas/ordens.py`
- Modify: `backend/app/api/certificados_os.py`
- Test: `backend/tests/test_certificado_os_api.py`

Contexto: `GerarCertificadoIn` ganha os 8 campos de identidade; novo `CertificadoCamposOut`; endpoint GET dos campos efetivos; o gerar grava `cert_overrides`.

- [ ] **Step 1: Escrever os testes (acrescentar ao fim de `backend/tests/test_certificado_os_api.py`)**

```python
def test_certificado_campos_deriva_e_aplica_override(client, usuario_admin, db_session):
    h = _headers(client, "admin", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C",), tipo_servico="C")
    # sem override: deriva do cliente (ACME) e do aparelho (Mark X / série S1)
    r = client.get(f"/ordens/{oid}/certificado-campos", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["nomecli"] == "ACME"
    assert body["serie"] == "S1"
    # grava override e confere que o GET reflete
    client.post(f"/ordens/{oid}/gerar-certificado", json={"nomecli": "NOME ESPECIAL"}, headers=h)
    body2 = client.get(f"/ordens/{oid}/certificado-campos", headers=h).json()
    assert body2["nomecli"] == "NOME ESPECIAL"


def test_gerar_grava_overrides_sem_alterar_cliente(client, usuario_admin, db_session):
    h = _headers(client, "admin", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C",), tipo_servico="C")
    r = client.post(f"/ordens/{oid}/gerar-certificado", json={"nomecli": "OUTRO NOME", "cnpj": "123"}, headers=h)
    assert r.status_code == 200
    from app.models import Ordem, Cliente
    o = db_session.get(Ordem, oid); db_session.refresh(o)
    assert o.cert_overrides == {"nomecli": "OUTRO NOME", "cnpj": "123"}
    # o HTML do certificado reflete o override
    assert "OUTRO NOME" in r.json()[0]["html"]
    # cadastro do cliente intacto
    cli = db_session.get(Cliente, o.cliente)
    assert cli.nome == "ACME"


def test_certificado_campos_404(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    assert client.get("/ordens/99999/certificado-campos", headers=h).status_code == 404
```
Nota: o template de teste em `_os_com_modelo` é `<p>[nomecli]-[serie]-{t}</p>`, então o HTML conterá o `nomecli` (com override "OUTRO NOME").

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_certificado_os_api.py -q -k "campos or overrides"`
Expected: FAIL (404 na rota / campo ausente).

- [ ] **Step 3: Schema**

Em `backend/app/schemas/ordens.py`:
- Em `GerarCertificadoIn`, adicionar os 8 campos de identidade (após `data_calibracao`, antes dos `calib_*`):
```python
    nomecli: str | None = None
    cnpj: str | None = None
    endcli: str | None = None
    modelo: str | None = None
    marca: str | None = None
    serie: str | None = None
    patrimonio: str | None = None
    datacompra: str | None = None
```
- Adicionar a classe (perto de `GerarCertificadoIn`):
```python
class CertificadoCamposOut(BaseModel):
    nomecli: str = ""
    cnpj: str = ""
    endcli: str = ""
    modelo: str = ""
    marca: str = ""
    serie: str = ""
    patrimonio: str = ""
    datacompra: str = ""
    calib_cert: str | None = None
    calib_temp: str | None = None
    calib_pressao: str | None = None
    calib_teste1: str | None = None
    calib_teste2: str | None = None
    calib_teste3: str | None = None
    calib_teste_media: str | None = None
    calib_situacao: str | None = None
    data_calibracao: date | None = None
```

- [ ] **Step 4: Endpoints**

Em `backend/app/api/certificados_os.py`:
- No import do core, acrescentar `montar_contexto`: `from app.core.certificado_gerar import gerar_certificados, tipos_para, montar_contexto`
- No import de schemas, acrescentar `CertificadoCamposOut`: `from app.schemas.ordens import GerarCertificadoIn, CertificadoCamposOut`
- Adicionar a constante (perto de `_CAMPOS_CALIB`):
```python
_CAMPOS_OVERRIDE = ("nomecli", "cnpj", "endcli", "modelo", "marca", "serie", "patrimonio", "datacompra")
```
- No corpo do `gerar`, dentro do `if dados is not None:` (após gravar `calib_*` e `data_calibracao`), adicionar antes do `db.flush()`:
```python
        overrides = {k: getattr(dados, k) for k in _CAMPOS_OVERRIDE if getattr(dados, k)}
        ordem.cert_overrides = overrides or None
```
- Adicionar o endpoint GET (após `listar_os_certificados`):
```python
@router.get("/ordens/{ordem_id}/certificado-campos", response_model=CertificadoCamposOut)
def certificado_campos(ordem_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    ordem = _os_ou_404(db, ordem_id)
    ctx = montar_contexto(db, ordem)
    return CertificadoCamposOut(
        nomecli=ctx.get("nomecli", ""), cnpj=ctx.get("cnpj", ""), endcli=ctx.get("endcli", ""),
        modelo=ctx.get("modelo", ""), marca=ctx.get("marca", ""), serie=ctx.get("serie", ""),
        patrimonio=ctx.get("patrimonio", ""), datacompra=ctx.get("datacompra", ""),
        calib_cert=ordem.calib_cert, calib_temp=ordem.calib_temp, calib_pressao=ordem.calib_pressao,
        calib_teste1=ordem.calib_teste1, calib_teste2=ordem.calib_teste2, calib_teste3=ordem.calib_teste3,
        calib_teste_media=ordem.calib_teste_media, calib_situacao=ordem.calib_situacao,
        data_calibracao=ordem.data_calibracao.date() if ordem.data_calibracao else None,
    )
```

- [ ] **Step 5: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_certificado_os_api.py -q`
Expected: PASS (todos, incl. os 3 novos).

- [ ] **Step 6: Suíte completa**

Run: `docker compose exec -T backend python -m pytest -q`
Expected: PASS sem regressões.

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/ordens.py backend/app/api/certificados_os.py backend/tests/test_certificado_os_api.py
git commit -m "feat(cert): endpoint certificado-campos + gravar overrides no gerar"
```

---

## Task 4: Frontend api — campos + payload

**Files:**
- Modify: `frontend/src/app/ordens/api.ts`

- [ ] **Step 1: Tipo + payload + método**

Em `frontend/src/app/ordens/api.ts`:
- Na interface `GerarCertificadoPayload`, adicionar (após `data_calibracao`):
```ts
  nomecli?: string | null
  cnpj?: string | null
  endcli?: string | null
  modelo?: string | null
  marca?: string | null
  serie?: string | null
  patrimonio?: string | null
  datacompra?: string | null
```
- Adicionar a interface (perto de `GerarCertificadoPayload`):
```ts
export interface CertificadoCampos {
  nomecli: string
  cnpj: string
  endcli: string
  modelo: string
  marca: string
  serie: string
  patrimonio: string
  datacompra: string
  calib_cert: string | null
  calib_temp: string | null
  calib_pressao: string | null
  calib_teste1: string | null
  calib_teste2: string | null
  calib_teste3: string | null
  calib_teste_media: string | null
  calib_situacao: string | null
  data_calibracao: string | null
}
```
- Dentro de `ordensApi`, após `gerarCertificado`, adicionar:
```ts
  certificadoCampos: (id: number): Promise<CertificadoCampos> => apiJson<CertificadoCampos>(`/ordens/${id}/certificado-campos`),
```

- [ ] **Step 2: Verificar**

Run: `cd frontend && npx tsc -b --noEmit && npx eslint src/app/ordens/api.ts`
Expected: limpo.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/ordens/api.ts
git commit -m "feat(cert): tipo CertificadoCampos + payload de identidade + certificadoCampos"
```

---

## Task 5: Modal com todos os campos (Cliente / Aparelho / Calibração)

**Files:**
- Modify: `frontend/src/app/ordens/GerarCertificadoModal.tsx`

Contexto: a modal passa a buscar os campos efetivos no endpoint e pré-preencher todos. Reescrita completa do arquivo abaixo.

- [ ] **Step 1: Substituir o conteúdo de `GerarCertificadoModal.tsx`**

```tsx
import { useEffect, useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Spinner } from '../../components/ui/Spinner'
import { ApiError } from '../../lib/api'
import { ordensApi, type OrdemDetalhe, type OSCertificado, type GerarCertificadoPayload } from './api'

function calcMedia(t1: string, t2: string, t3: string): string {
  const vals = [t1, t2, t3]
  if (vals.some((v) => v.trim() === '')) return ''
  const nums = vals.map((v) => Number(v.replace(',', '.')))
  if (nums.some((n) => Number.isNaN(n))) return ''
  return ((nums[0] + nums[1] + nums[2]) / 3).toFixed(2).replace('.', ',')
}

function hojeISO(): string {
  return new Date().toISOString().slice(0, 10)
}

export function GerarCertificadoModal({ os, onClose, onGerado }: {
  os: OrdemDetalhe
  onClose: () => void
  onGerado: (certs: OSCertificado[]) => void
}) {
  const [carregando, setCarregando] = useState(true)
  // identidade
  const [nomecli, setNomecli] = useState('')
  const [cnpj, setCnpj] = useState('')
  const [endcli, setEndcli] = useState('')
  const [modelo, setModelo] = useState('')
  const [marca, setMarca] = useState('')
  const [serie, setSerie] = useState('')
  const [patrimonio, setPatrimonio] = useState('')
  const [datacompra, setDatacompra] = useState('')
  // calibração
  const [dataCalib, setDataCalib] = useState(hojeISO())
  const [cert, setCert] = useState('')
  const [situacao, setSituacao] = useState('')
  const [temp, setTemp] = useState('')
  const [pressao, setPressao] = useState('')
  const [t1, setT1] = useState('')
  const [t2, setT2] = useState('')
  const [t3, setT3] = useState('')
  const [media, setMedia] = useState('')
  const [mediaEditada, setMediaEditada] = useState(false)
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    let ativo = true
    ordensApi.certificadoCampos(os.id)
      .then((c) => {
        if (!ativo) return
        setNomecli(c.nomecli ?? ''); setCnpj(c.cnpj ?? ''); setEndcli(c.endcli ?? '')
        setModelo(c.modelo ?? ''); setMarca(c.marca ?? ''); setSerie(c.serie ?? '')
        setPatrimonio(c.patrimonio ?? ''); setDatacompra(c.datacompra ?? '')
        setCert(c.calib_cert ?? ''); setSituacao(c.calib_situacao ?? '')
        setTemp(c.calib_temp ?? ''); setPressao(c.calib_pressao ?? '')
        setT1(c.calib_teste1 ?? ''); setT2(c.calib_teste2 ?? ''); setT3(c.calib_teste3 ?? '')
        setMedia(c.calib_teste_media ?? '')
        // preserva a média manual só quando ela existe e os testes não estão completos
        setMediaEditada(!!c.calib_teste_media && !(c.calib_teste1 && c.calib_teste2 && c.calib_teste3))
        setDataCalib(c.data_calibracao ? c.data_calibracao.slice(0, 10) : hojeISO())
        setCarregando(false)
      })
      .catch(() => { if (ativo) { setErro('Falha ao carregar os campos do certificado'); setCarregando(false) } })
    return () => { ativo = false }
  }, [os.id])

  useEffect(() => {
    if (mediaEditada) return
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMedia(calcMedia(t1, t2, t3))
  }, [t1, t2, t3, mediaEditada])

  async function submeter(e: FormEvent) {
    e.preventDefault()
    setErro(''); setEnviando(true)
    const payload: GerarCertificadoPayload = {
      data_calibracao: dataCalib || null,
      nomecli: nomecli.trim() || null,
      cnpj: cnpj.trim() || null,
      endcli: endcli.trim() || null,
      modelo: modelo.trim() || null,
      marca: marca.trim() || null,
      serie: serie.trim() || null,
      patrimonio: patrimonio.trim() || null,
      datacompra: datacompra.trim() || null,
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

  const secao = 'text-xs font-semibold text-slate-500 uppercase tracking-wide'

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
          <div className="space-y-3">
            <p className={secao}>Cliente</p>
            <Input id="nomecli" label="Nome" value={nomecli} onChange={(e) => setNomecli(e.target.value)} />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Input id="cnpj" label="CNPJ/CPF" value={cnpj} onChange={(e) => setCnpj(e.target.value)} />
              <Input id="endcli" label="Endereço" value={endcli} onChange={(e) => setEndcli(e.target.value)} />
            </div>
          </div>

          <div className="space-y-3">
            <p className={secao}>Aparelho</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Input id="modelo" label="Modelo" value={modelo} onChange={(e) => setModelo(e.target.value)} />
              <Input id="marca" label="Marca" value={marca} onChange={(e) => setMarca(e.target.value)} />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <Input id="serie" label="Série" value={serie} onChange={(e) => setSerie(e.target.value)} />
              <Input id="patrimonio" label="Patrimônio" value={patrimonio} onChange={(e) => setPatrimonio(e.target.value)} />
              <Input id="datacompra" label="Data de compra" value={datacompra} onChange={(e) => setDatacompra(e.target.value)} />
            </div>
          </div>

          <div className="space-y-3">
            <p className={secao}>Calibração</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Input id="data-calib" label="Data de calibração" type="date" value={dataCalib} onChange={(e) => setDataCalib(e.target.value)} />
              <Input id="cert" label="Nº do certificado" value={cert} onChange={(e) => setCert(e.target.value)} />
            </div>
            <Select id="situacao" label="Situação" value={situacao} onChange={(e) => setSituacao(e.target.value)}>
              <option value="">— selecione —</option>
              <option value="Aparelho subsequente">Aparelho subsequente</option>
              <option value="Aparelho inicial">Aparelho inicial</option>
            </Select>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Input id="temp" label="Temperatura" value={temp} onChange={(e) => setTemp(e.target.value)} />
              <Input id="pressao" label="Pressão" value={pressao} onChange={(e) => setPressao(e.target.value)} />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <Input id="t1" label="Teste 1" value={t1} onChange={(e) => setT1(e.target.value)} />
              <Input id="t2" label="Teste 2" value={t2} onChange={(e) => setT2(e.target.value)} />
              <Input id="t3" label="Teste 3" value={t3} onChange={(e) => setT3(e.target.value)} />
            </div>
            <Input id="media" label="Média dos testes" value={media} onChange={(e) => { setMediaEditada(true); setMedia(e.target.value) }} />
          </div>

          {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
        </form>
      )}
    </Modal>
  )
}
```

- [ ] **Step 2: Verificar**

Run: `cd frontend && npx tsc -b --noEmit && npx eslint src/app/ordens/GerarCertificadoModal.tsx && npm run build`
Expected: sem erros, build verde. (Se `Modal` não aceitar `size`, conferir a prop em `components/ui/Modal.tsx` — ela existe; usar o valor suportado.)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/ordens/GerarCertificadoModal.tsx
git commit -m "feat(cert): modal com Cliente/Aparelho/Calibracao pre-preenchidos e editaveis"
```

---

## Task 6: Migração no banco real + changelog v1.5.0 + verificação + memória

**Files:**
- Modify: `frontend/src/app/changelog/data.ts`

- [ ] **Step 1: Aplicar a migração no banco real (9998)**

Run: `docker compose exec -T backend alembic upgrade head`
Expected: aplica `0008_cert_overrides` sem erro. Conferir: `docker compose exec -T backend alembic current` mostra `0008_cert_overrides`.

- [ ] **Step 2: Changelog v1.5.0 (topo do array `CHANGELOG`)**

```ts
  {
    versao: '1.5.0',
    data: '10/06/2026',
    itens: [
      { tipo: 'novidade', texto: 'A tela de gerar/regerar certificado agora mostra todos os campos (dados do cliente, do aparelho e da calibração) já preenchidos automaticamente. Dá para ajustar qualquer informação apenas naquele certificado — por exemplo, corrigir o nome ou endereço que sai impresso — sem alterar o cadastro do cliente ou do aparelho. O ajuste fica salvo na OS e vale para as próximas regerações.' },
    ],
  },
```

- [ ] **Step 3: Verificar build + suítes**

Run: `cd frontend && npm run build && npx vitest run`
Expected: build verde; testes passando.
Run: `docker compose exec -T backend python -m pytest -q`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/changelog/data.ts
git commit -m "docs(changelog): v1.5.0 — certificado com campos editaveis por OS"
```

- [ ] **Step 5: E2E manual (com o usuário)**

Gerar certificado → ver Cliente/Aparelho pré-preenchidos → alterar só o Nome → gerar → baixar PDF (nome alterado) → conferir ficha do cliente intacta → reabrir a modal e ver o override mantido.

- [ ] **Step 6: Atualizar memória**

Em `C:\Users\TI\.claude\projects\d--GitHub-GestorHS\memory\project_gestorhs.md`: registrar `ordens.cert_overrides` (JSON, migração 0008), o overlay em `montar_contexto`, o endpoint `GET /ordens/{id}/certificado-campos`, e a modal de certificado em seções (Cliente/Aparelho/Calibração) com override por OS sem tocar no cadastro.

---

## Self-Review (preenchido)

**Spec coverage:** coluna+migração (T1); overlay no motor (T2); schema/endpoints/gravação (T3); api front (T4); modal (T5); migração real+changelog+memória (T6). Tudo coberto.

**Type consistency:** chaves de override idênticas em `_CAMPOS_OVERRIDE` (back), `GerarCertificadoIn`/`CertificadoCamposOut` (back), `GerarCertificadoPayload`/`CertificadoCampos` (front), e nos `set*` do modal. `data_calibracao` `date`(back)/`string`(front, YYYY-MM-DD). `montar_contexto` produz as chaves `nomecli/cnpj/endcli/modelo/marca/serie/patrimonio/datacompra` que o overlay e o GET consomem.

**Placeholders:** nenhum — código completo em cada passo (incl. a reescrita integral do modal).
