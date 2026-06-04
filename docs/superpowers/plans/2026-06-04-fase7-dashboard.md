# Fase 7 — Dashboard interno — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir o placeholder do `/app` por um dashboard operacional com 4 indicadores-chave, OS ativas por fase e atalhos, servido por um endpoint agregado `GET /dashboard`.

**Architecture:** Backend acrescenta um router `dashboard` (read-only, qualquer interno) que devolve contagens agregadas num único `DashboardOut`. Frontend ganha um módulo `app/dashboard/` com `api.ts` (`dashboardApi.resumo()`) e reescreve `DashboardPage` para consumir esse endpoint, reaproveitando `StatCard`, `Spinner` e `useNavigate`. Remove-se um arquivo órfão do portal.

**Tech Stack:** FastAPI, SQLAlchemy 2, Pydantic v2, pytest (SQLite in-memory); React 19, TypeScript, Vite, Vitest.

**Spec:** `docs/superpowers/specs/2026-06-04-fase7-dashboard-design.md`

**Convenções do projeto (já validadas):**
- Backend: router por arquivo em `app/api/`, registrado em `app/main.py`; auth via `Depends(get_current_usuario)`; fronteiras de status iguais à frota (vencido `prox < hoje`; vencendo `hoje <= prox <= hoje+90`); fases ativas `(4,5,6,7)`.
- Testes backend: `client` + `db_session` + fixtures (`usuario_admin`, `usuario_comum`, `fases_seed`); token via `client.post("/auth/login", json={"login","senha"})` → `Authorization: Bearer`.
- Frontend: `apiJson<T>(path)` de `../../lib/api`; páginas carregam em `useEffect` com guarda `ativo`, `Spinner` enquanto `=== null`, erro com `ApiError`; navegação com `useNavigate` para rotas `/app/...`.
- Testes frontend (Vitest): stub de `fetch` com `jsonResponse`, `setTokens(...)` no `beforeEach`, asserta a URL chamada.

---

## File Structure

**Backend:**
- Create: `backend/app/schemas/dashboard.py` — `OsPorFaseItem`, `DashboardOut`.
- Create: `backend/app/api/dashboard.py` — router `GET /dashboard`.
- Modify: `backend/app/main.py` — importar e registrar o router.
- Create: `backend/tests/test_dashboard.py` — contagens + 401.

**Frontend:**
- Create: `frontend/src/app/dashboard/api.ts` — tipos + `dashboardApi`.
- Create: `frontend/src/app/dashboard/api.test.ts` — testes do `dashboardApi`.
- Modify (reescrita): `frontend/src/app/pages/DashboardPage.tsx` — dashboard real.
- Delete: `frontend/src/portal/pages/PlaceholderPage.tsx` — órfão.

---

## Task 1: Schemas do dashboard (backend)

**Files:**
- Create: `backend/app/schemas/dashboard.py`

- [ ] **Step 1: Criar o arquivo de schemas**

```python
from pydantic import BaseModel


class OsPorFaseItem(BaseModel):
    fase: int
    descricao: str
    cor: str
    total: int


class DashboardOut(BaseModel):
    aparelhos_vencidos: int
    aparelhos_vencendo: int
    solicitacoes_pendentes: int
    clientes_a_cobrar: int
    os_por_fase: list[OsPorFaseItem]
```

- [ ] **Step 2: Conferir import**

Run: `cd backend; python -c "from app.schemas.dashboard import DashboardOut, OsPorFaseItem; print('ok')"`
Expected: imprime `ok` sem erro.

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/dashboard.py
git commit -m "feat(backend): schemas do dashboard interno"
```

---

## Task 2: Endpoint GET /dashboard (backend, TDD)

**Files:**
- Create: `backend/tests/test_dashboard.py`
- Create: `backend/app/api/dashboard.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Escrever os testes que falham**

Criar `backend/tests/test_dashboard.py`. As fronteiras seguem a frota; `fases_seed` cria as fases 4–9 (a 8/9 não contam em `os_por_fase`). O cliente C só tem aparelho em_dia → não entra em `clientes_a_cobrar`.

```python
from datetime import date, timedelta


def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _setup(db_session):
    from app.models import Cliente, Equipamento, EquipamentoCliente, Ordem, Solicitacao
    hoje = date.today()
    cliA = Cliente(nome="Alfa Ltda")
    cliB = Cliente(nome="Beta SA")
    cliC = Cliente(nome="Gama ME")
    eq = Equipamento(descricao="Bafômetro")
    db_session.add_all([cliA, cliB, cliC, eq])
    db_session.flush()

    def ec(cli, prox, ativo=True):
        return EquipamentoCliente(cliente=cli, equipamento=eq.id, prox_calibragem=prox, ativo=ativo)

    db_session.add_all([
        ec(cliA.id, hoje - timedelta(days=10)),             # vencido
        ec(cliA.id, hoje + timedelta(days=30)),             # vencendo
        ec(cliA.id, hoje + timedelta(days=200)),            # em_dia (ignorado)
        ec(cliA.id, hoje - timedelta(days=1), ativo=False), # inativo (ignorado)
        ec(cliB.id, hoje - timedelta(days=2)),              # vencido
        ec(cliC.id, hoje + timedelta(days=300)),            # em_dia só -> C fora da cobrança
    ])
    # OS: fase 4 (x2), fase 5 (x1), fase 8 (finalizada, não conta)
    db_session.add_all([
        Ordem(cliente=cliA.id, fase=4),
        Ordem(cliente=cliA.id, fase=4),
        Ordem(cliente=cliB.id, fase=5),
        Ordem(cliente=cliB.id, fase=8),
    ])
    # Solicitações: 1 pendente + 1 atendida
    db_session.add_all([
        Solicitacao(cliente=cliA.id, equipamento_cliente=1, status="pendente"),
        Solicitacao(cliente=cliB.id, equipamento_cliente=5, status="atendida"),
    ])
    db_session.commit()
    return {"A": cliA.id, "B": cliB.id, "C": cliC.id}


def test_contagens(client, usuario_comum, fases_seed, db_session):
    _setup(db_session)
    r = client.get("/dashboard", headers=_headers(client, "comum", "senha123"))
    assert r.status_code == 200
    body = r.json()
    assert body["aparelhos_vencidos"] == 2       # A + B (inativo ignorado)
    assert body["aparelhos_vencendo"] == 1        # A
    assert body["solicitacoes_pendentes"] == 1
    assert body["clientes_a_cobrar"] == 2         # A e B (C só em_dia)


def test_os_por_fase(client, usuario_comum, fases_seed, db_session):
    _setup(db_session)
    r = client.get("/dashboard", headers=_headers(client, "comum", "senha123"))
    fases = r.json()["os_por_fase"]
    assert [f["fase"] for f in fases] == [4, 5, 6, 7]   # ordem, só fases ativas
    por_fase = {f["fase"]: f["total"] for f in fases}
    assert por_fase == {4: 2, 5: 1, 6: 0, 7: 0}          # fase 8 não aparece
    assert fases[0]["descricao"] == "Recebido" and fases[0]["cor"] == "3b82f6"


def test_exige_autenticacao(client, db_session):
    assert client.get("/dashboard").status_code == 401
```

- [ ] **Step 2: Rodar os testes e ver falhar**

Run: `cd backend; python -m pytest tests/test_dashboard.py -v`
Expected: FAIL — `404` (rota inexistente) nos dois primeiros; o de 401 pode passar por acaso, ok.

- [ ] **Step 3: Implementar o router**

Criar `backend/app/api/dashboard.py`. O `os_por_fase` faz um `group_by` único e depois monta a lista iterando as `Fase` 4–7 (incluindo as de total 0).

```python
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, distinct
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, EquipamentoCliente, Solicitacao, Ordem, Fase
from app.api.deps import get_current_usuario
from app.schemas.dashboard import DashboardOut, OsPorFaseItem

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
_FASES_ATIVAS = (4, 5, 6, 7)


@router.get("", response_model=DashboardOut)
def resumo(
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_usuario),
):
    hoje = date.today()
    limite = hoje + timedelta(days=90)

    ativos = db.query(EquipamentoCliente).filter(
        EquipamentoCliente.ativo.is_(True),
        EquipamentoCliente.prox_calibragem.isnot(None),
    )
    aparelhos_vencidos = ativos.filter(EquipamentoCliente.prox_calibragem < hoje).count()
    aparelhos_vencendo = ativos.filter(
        EquipamentoCliente.prox_calibragem >= hoje,
        EquipamentoCliente.prox_calibragem <= limite,
    ).count()

    solicitacoes_pendentes = (
        db.query(Solicitacao).filter(Solicitacao.status == "pendente").count()
    )

    clientes_a_cobrar = (
        db.query(func.count(distinct(EquipamentoCliente.cliente)))
        .filter(
            EquipamentoCliente.ativo.is_(True),
            EquipamentoCliente.prox_calibragem.isnot(None),
            EquipamentoCliente.prox_calibragem <= limite,
        )
        .scalar()
    ) or 0

    contagem = dict(
        db.query(Ordem.fase, func.count(Ordem.id))
        .filter(Ordem.fase.in_(_FASES_ATIVAS))
        .group_by(Ordem.fase)
        .all()
    )
    fases = (
        db.query(Fase)
        .filter(Fase.id.in_(_FASES_ATIVAS))
        .order_by(Fase.id)
        .all()
    )
    os_por_fase = [
        OsPorFaseItem(fase=f.id, descricao=f.descricao, cor=f.cor, total=int(contagem.get(f.id, 0)))
        for f in fases
    ]

    return DashboardOut(
        aparelhos_vencidos=aparelhos_vencidos,
        aparelhos_vencendo=aparelhos_vencendo,
        solicitacoes_pendentes=solicitacoes_pendentes,
        clientes_a_cobrar=int(clientes_a_cobrar),
        os_por_fase=os_por_fase,
    )
```

- [ ] **Step 4: Registrar o router em `main.py`**

Em `backend/app/main.py`, adicionar `dashboard` à linha de import dos routers e registrar.

Import (linha 4) — acrescentar `, dashboard` ao final da lista:
```python
from app.api import auth, funcoes, usuarios, setores, marcas, grupos, categorias, equipamentos, clientes, funcionarios, equipamentos_cliente, fases, ordens, tipos_calibragem, alertas, portal, solicitacoes, usuarios_cliente, dashboard
```

Registro — acrescentar após `app.include_router(usuarios_cliente.router)`:
```python
app.include_router(dashboard.router)
```

- [ ] **Step 5: Rodar os testes e ver passar**

Run: `cd backend; python -m pytest tests/test_dashboard.py -v`
Expected: PASS (3 testes).

- [ ] **Step 6: Rodar a suíte backend inteira (sem regressões)**

Run: `cd backend; python -m pytest -q`
Expected: todos passam.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/dashboard.py backend/app/main.py backend/tests/test_dashboard.py
git commit -m "feat(backend): endpoint agregado GET /dashboard"
```

---

## Task 3: API do dashboard (frontend, TDD)

**Files:**
- Create: `frontend/src/app/dashboard/api.test.ts`
- Create: `frontend/src/app/dashboard/api.ts`

- [ ] **Step 1: Escrever o teste que falha**

Criar `frontend/src/app/dashboard/api.test.ts` (espelha `solicitacoes/api.test.ts`).

```ts
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { dashboardApi } from './api'
import { ApiError } from '../../lib/api'
import { setTokens } from '../../lib/auth-storage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('app/dashboard/api', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    setTokens({ access_token: 't', refresh_token: 'r' })
  })

  it('resumo faz GET /dashboard', async () => {
    const f = vi.fn().mockResolvedValue(
      jsonResponse({
        aparelhos_vencidos: 3, aparelhos_vencendo: 2, solicitacoes_pendentes: 1,
        clientes_a_cobrar: 2, os_por_fase: [],
      }),
    )
    vi.stubGlobal('fetch', f)
    const r = await dashboardApi.resumo()
    expect(String(f.mock.calls[0][0])).toContain('/dashboard')
    expect(r.aparelhos_vencidos).toBe(3)
  })

  it('resumo propaga ApiError', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ detail: 'erro' }, 500))
    vi.stubGlobal('fetch', f)
    await expect(dashboardApi.resumo()).rejects.toBeInstanceOf(ApiError)
  })
})
```

- [ ] **Step 2: Rodar o teste e ver falhar**

Run: `cd frontend; npx vitest run src/app/dashboard/api.test.ts`
Expected: FAIL — `Cannot find module './api'`.

- [ ] **Step 3: Implementar a api**

Criar `frontend/src/app/dashboard/api.ts`.

```ts
import { apiJson } from '../../lib/api'

export interface OsPorFaseItem {
  fase: number
  descricao: string
  cor: string
  total: number
}

export interface DashboardResumo {
  aparelhos_vencidos: number
  aparelhos_vencendo: number
  solicitacoes_pendentes: number
  clientes_a_cobrar: number
  os_por_fase: OsPorFaseItem[]
}

export const dashboardApi = {
  resumo: (): Promise<DashboardResumo> => apiJson<DashboardResumo>('/dashboard'),
}
```

- [ ] **Step 4: Rodar o teste e ver passar**

Run: `cd frontend; npx vitest run src/app/dashboard/api.test.ts`
Expected: PASS (2 testes).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/dashboard/api.ts frontend/src/app/dashboard/api.test.ts
git commit -m "feat(frontend): dashboardApi.resumo (GET /dashboard)"
```

---

## Task 4: Reescrever a DashboardPage

**Files:**
- Modify (reescrita completa): `frontend/src/app/pages/DashboardPage.tsx`

- [ ] **Step 1: Reescrever o componente**

Substituir TODO o conteúdo de `frontend/src/app/pages/DashboardPage.tsx`. Usa `StatCard` (já existe: props `label`, `value`, `icon`, `color`, `sub`), `Spinner`, `useNavigate`, `useAuth`, e os ícones disponíveis em `components/ui/icons` (`IconFrota`, `IconSolicitacoes`, `IconCobranca`, `IconOrdens`). Carrega em `useEffect` com guarda `ativo`. As cores das fases vêm como hex sem `#` (ex.: `"3b82f6"`).

```tsx
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { StatCard } from '../../components/ui/StatCard'
import { Spinner } from '../../components/ui/Spinner'
import { IconFrota, IconSolicitacoes, IconCobranca, IconOrdens } from '../../components/ui/icons'
import { ApiError } from '../../lib/api'
import { useAuth } from '../../auth/AuthContext'
import { dashboardApi, type DashboardResumo } from '../dashboard/api'

export function DashboardPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [dados, setDados] = useState<DashboardResumo | null>(null)
  const [erro, setErro] = useState('')

  useEffect(() => {
    let ativo = true
    dashboardApi
      .resumo()
      .then((d) => {
        if (ativo) setDados(d)
      })
      .catch((e) => {
        if (!ativo) return
        setErro(e instanceof ApiError ? e.message : 'Falha ao carregar o dashboard')
      })
    return () => {
      ativo = false
    }
  }, [])

  return (
    <div className="px-4 md:px-6 py-6 space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100">Olá, {user?.nome ?? user?.login} 👋</h1>
        <p className="text-sm text-slate-500 mt-1">Visão geral da operação.</p>
      </div>

      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}

      {dados === null ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <button onClick={() => navigate('/app/frota')} className="text-left">
              <StatCard
                label="Aparelhos vencidos"
                value={dados.aparelhos_vencidos}
                icon={<IconFrota className="w-6 h-6 text-danger" />}
                color="bg-danger/15"
              />
            </button>
            <button onClick={() => navigate('/app/frota')} className="text-left">
              <StatCard
                label="Vencendo (90 dias)"
                value={dados.aparelhos_vencendo}
                icon={<IconFrota className="w-6 h-6 text-warning" />}
                color="bg-warning/15"
              />
            </button>
            <button onClick={() => navigate('/app/solicitacoes')} className="text-left">
              <StatCard
                label="Solicitações pendentes"
                value={dados.solicitacoes_pendentes}
                icon={<IconSolicitacoes className="w-6 h-6 text-primary" />}
                color="bg-primary/15"
              />
            </button>
            <button onClick={() => navigate('/app/cobranca')} className="text-left">
              <StatCard
                label="Clientes a cobrar"
                value={dados.clientes_a_cobrar}
                icon={<IconCobranca className="w-6 h-6 text-primary" />}
                color="bg-primary/15"
              />
            </button>
          </div>

          <div>
            <h2 className="text-sm font-bold text-slate-300 mb-3">OS ativas por fase</h2>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {dados.os_por_fase.map((f) => (
                <button
                  key={f.fase}
                  onClick={() => navigate('/app/ordens')}
                  className="flex items-center gap-3 rounded-xl bg-background-surface border border-border px-4 py-3 text-left hover:bg-background-elevated transition-colors"
                >
                  <span className="w-3 h-3 rounded-full shrink-0" style={{ background: `#${f.cor}` }} />
                  <span className="flex-1 text-sm text-slate-300 truncate">{f.descricao}</span>
                  <span className="text-lg font-extrabold text-slate-100">{f.total}</span>
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verificar tipos**

Run: `cd frontend; npx tsc -b --noEmit`
Expected: sem erros.

- [ ] **Step 3: Lint**

Run: `cd frontend; npm run lint`
Expected: sem erros (atenção ao plugin `react-hooks` — a estrutura do `useEffect` espelha as páginas existentes).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/pages/DashboardPage.tsx
git commit -m "feat(frontend): dashboard interno (indicadores + OS por fase + atalhos)"
```

---

## Task 5: Remover o PlaceholderPage órfão

**Files:**
- Delete: `frontend/src/portal/pages/PlaceholderPage.tsx`

- [ ] **Step 1: Confirmar que nenhum import referencia o arquivo**

Run (Grep): procurar `PlaceholderPage` em `frontend/src`.
Expected: a única ocorrência é a própria definição em `portal/pages/PlaceholderPage.tsx`. Se houver qualquer import, PARAR e reportar (não apagar).

- [ ] **Step 2: Apagar o arquivo**

```bash
git rm frontend/src/portal/pages/PlaceholderPage.tsx
```

- [ ] **Step 3: Verificar build (garante que não quebrou nenhum import)**

Run: `cd frontend; npx tsc -b --noEmit; npm run build`
Expected: build conclui sem erros.

- [ ] **Step 4: Commit**

```bash
git commit -m "chore(frontend): remove PlaceholderPage órfão do portal"
```

---

## Task 6: Verificação final (suítes completas)

**Files:** nenhum (só verificação).

- [ ] **Step 1: Suíte backend**

Run: `cd backend; python -m pytest -q`
Expected: todos passam.

- [ ] **Step 2: Suíte frontend (testes + tipos + lint + build)**

Run: `cd frontend; npx vitest run; npx tsc -b --noEmit; npm run lint; npm run build`
Expected: tudo verde.

- [ ] **Step 2.5: Não há novos commits aqui** — só confirma que o working tree está limpo (`git status`).

---

## Notas para o E2E (após a execução, fora do subagente)
- Logar no `/app` (admin `admin`/`admin12345`) e ver o dashboard com indicadores reais (vencidos na casa dos milhares, OS por fase, etc.).
- Clicar em cada card → Frota / Solicitações / Cobrança; clicar numa fase → Ordens.
- Verificação não-destrutiva (só leitura). Matar dev-servers órfãos em 5173/5174/5175 ao final.

## Self-review (preenchido pelo autor do plano)
- **Cobertura da spec:** §4.1 endpoint → Task 2; §4.2 schemas → Task 1; §4.3 testes pytest → Task 2 (3 testes: contagens, os_por_fase, 401); §5.1 api → Task 3; §5.2 DashboardPage → Task 4; §5.3 limpeza → Task 5; §5.4 testes Vitest + tsc/lint/build → Tasks 3, 4 e 6. ✓
- **Placeholders:** nenhum — todo passo traz código/comando completo.
- **Consistência de tipos:** `DashboardOut`/`DashboardResumo` e `OsPorFaseItem` com os mesmos campos nos dois lados (`fase, descricao, cor, total`); `dashboardApi.resumo` usado igual no teste e na página; `StatCard` chamado com as props reais (`label, value, icon, color`); ícones existem em `icons.tsx`; rota `/dashboard` (prefixo do router) batendo com o path do front.
