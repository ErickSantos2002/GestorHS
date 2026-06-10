# Ficha do aparelho: OS e certificados — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Na ficha do aparelho, link rápido pro cliente + lista de OS do aparelho + lista de certificados gerados (com download de PDF, incluindo os antigos).

**Architecture:** Dois endpoints de leitura sub-recurso em `equipamentos-cliente` (`/ordens` reusando `OrdemListOut`; `/certificados` com schema novo `EquipCertItem`); frontend adiciona link do cliente e duas seções full-width na ficha do aparelho, baixando PDF via endpoint existente.

**Tech Stack:** FastAPI + SQLAlchemy (backend), React 19 + TS + Vite + Tailwind (frontend), pytest/vitest.

**Branch:** `main`. Lançamento: v1.4.2.

**Spec:** `docs/superpowers/specs/2026-06-10-aparelho-os-certificados-design.md`

---

## Task 1: Backend — endpoints `/ordens` e `/certificados` do aparelho

**Files:**
- Modify: `backend/app/schemas/frota.py`
- Modify: `backend/app/api/equipamentos_cliente.py`
- Test: `backend/tests/test_frota_os_certificados.py`

Contexto: seguir o padrão do endpoint `historico` já existente (auth `get_current_usuario`, 404 se aparelho não existe). `/ordens` reusa `OrdemListOut`; `/certificados` usa schema novo. pytest roda no container: `docker compose exec -T backend python -m pytest ...`.

- [ ] **Step 1: Escrever os testes**

Criar `backend/tests/test_frota_os_certificados.py`:

```python
def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _aparelho_com_os(db_session):
    from app.models import Cliente, Equipamento, EquipamentoCliente, Ordem, OSCertificado
    cli = Cliente(nome="ACME"); eq = Equipamento(descricao="Mark X")
    db_session.add_all([cli, eq]); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie="S1")
    outro = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie="S2")
    db_session.add_all([ec, outro]); db_session.flush()
    o1 = Ordem(cliente=cli.id, equipamento_cliente=ec.id, situacao="E", tipo_servico="C", fase=5)
    o2 = Ordem(cliente=cli.id, equipamento_cliente=ec.id, situacao="F", tipo_servico="C", fase=8)
    o_outro = Ordem(cliente=cli.id, equipamento_cliente=outro.id, situacao="E", tipo_servico="C", fase=5)
    db_session.add_all([o1, o2, o_outro]); db_session.flush()
    db_session.add(OSCertificado(os=o1.id, tipo="C", html="<p>x</p>"))
    db_session.commit()
    return ec.id, outro.id, o1.id, o2.id


def test_ordens_do_aparelho(client, usuario_admin, db_session):
    ec_id, _outro, o1, o2 = _aparelho_com_os(db_session)
    h = _headers(client, "admin", "senha123")
    r = client.get(f"/equipamentos-cliente/{ec_id}/ordens", headers=h)
    assert r.status_code == 200
    ids = [o["id"] for o in r.json()]
    assert ids == sorted(ids, reverse=True)        # desc
    assert o1 in ids and o2 in ids
    assert len(ids) == 2                            # só as OS desse aparelho


def test_certificados_do_aparelho(client, usuario_admin, db_session):
    ec_id, _outro, o1, _o2 = _aparelho_com_os(db_session)
    h = _headers(client, "admin", "senha123")
    r = client.get(f"/equipamentos-cliente/{ec_id}/certificados", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["os"] == o1 and body[0]["tipo"] == "C"
    assert "data_geracao" in body[0]


def test_ordens_aparelho_inexistente_404(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    assert client.get("/equipamentos-cliente/99999/ordens", headers=h).status_code == 404
    assert client.get("/equipamentos-cliente/99999/certificados", headers=h).status_code == 404
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `docker compose exec -T backend python -m pytest tests/test_frota_os_certificados.py -q`
Expected: FAIL (404 nas rotas inexistentes / schema ausente).

- [ ] **Step 3: Adicionar o schema `EquipCertItem`**

Em `backend/app/schemas/frota.py`, trocar a primeira linha de import de data:
`from datetime import date` → `from datetime import date, datetime`
E adicionar ao fim do arquivo:
```python
class EquipCertItem(BaseModel):
    os: int
    tipo: str
    data_geracao: datetime | None = None
    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Adicionar os endpoints**

Em `backend/app/api/equipamentos_cliente.py`:
- No import de models, acrescentar `Ordem, OSCertificado`:
  `from app.models import Usuario, EquipamentoCliente, HistoricoEquipamento, Ordem, OSCertificado`
- Acrescentar imports de schema:
  `from app.schemas.frota import (FrotaListOut, FrotaPage, EquipamentoClienteOut, EquipamentoClienteCreate, EquipamentoClienteUpdate, HistoricoOut, EquipCertItem)`
  `from app.schemas.ordens import OrdemListOut`
- Adicionar as rotas logo após o endpoint `historico`:
```python
@router.get("/{item_id}/ordens", response_model=list[OrdemListOut])
def ordens_do_aparelho(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    if db.query(EquipamentoCliente).filter(EquipamentoCliente.id == item_id).first() is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    rows = db.query(Ordem).filter(Ordem.equipamento_cliente == item_id).order_by(Ordem.id.desc()).all()
    return [OrdemListOut.model_validate(o) for o in rows]


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
    return [EquipCertItem(os=c.os, tipo=c.tipo, data_geracao=c.data_geracao) for c in rows]
```

- [ ] **Step 5: Rodar e ver passar**

Run: `docker compose exec -T backend python -m pytest tests/test_frota_os_certificados.py -q`
Expected: PASS (3 passed).

- [ ] **Step 6: Suíte backend completa**

Run: `docker compose exec -T backend python -m pytest -q`
Expected: PASS (sem regressões).

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/frota.py backend/app/api/equipamentos_cliente.py backend/tests/test_frota_os_certificados.py
git commit -m "feat(frota): endpoints OS e certificados do aparelho"
```

---

## Task 2: Frontend api — `ordens` e `certificados` do aparelho

**Files:**
- Modify: `frontend/src/app/frota/api.ts`
- Test: `frontend/src/app/frota/api.test.ts` (criar se não existir; senão acrescentar)

Contexto: a lista de OS reusa o tipo `OrdemListItem` de `../ordens/api`; certificados usam tipo novo `EquipCertItem`. Métodos usam `apiJson`.

- [ ] **Step 1: Adicionar tipos e métodos**

Em `frontend/src/app/frota/api.ts`:
- No topo, acrescentar o import de tipo:
```ts
import type { OrdemListItem } from '../ordens/api'
```
- Adicionar o tipo (perto de `Historico`):
```ts
export interface EquipCertItem {
  os: number
  tipo: 'C' | 'M'
  data_geracao: string | null
}
```
- Dentro de `equipamentosClienteApi`, após `historico`, acrescentar:
```ts
  ordens: (id: number): Promise<OrdemListItem[]> => apiJson<OrdemListItem[]>(`/equipamentos-cliente/${id}/ordens`),
  certificados: (id: number): Promise<EquipCertItem[]> => apiJson<EquipCertItem[]>(`/equipamentos-cliente/${id}/certificados`),
```

- [ ] **Step 2: Teste das URLs**

Criar/!acrescentar em `frontend/src/app/frota/api.test.ts`:
```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { equipamentosClienteApi } from './api'

describe('equipamentosClienteApi sub-recursos', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.setItem('gestorhs-access', 'tok')
  })
  it('ordens monta a URL do aparelho', async () => {
    const spy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )
    await equipamentosClienteApi.ordens(7)
    expect(spy.mock.calls[0][0]).toContain('/equipamentos-cliente/7/ordens')
  })
  it('certificados monta a URL do aparelho', async () => {
    const spy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )
    await equipamentosClienteApi.certificados(7)
    expect(spy.mock.calls[0][0]).toContain('/equipamentos-cliente/7/certificados')
  })
})
```
Nota: confira o nome da chave do token no `lib/api.ts` (ex.: `gestorhs-access`); se for outro, ajuste o `localStorage.setItem`. Se o projeto já tiver um helper de mock de fetch em outros `.test.ts` da pasta, siga o mesmo padrão.

- [ ] **Step 3: Verificar**

Run: `cd frontend && npx vitest run src/app/frota/api.test.ts && npx tsc -b --noEmit && npx eslint src/app/frota/api.ts`
Expected: testes passam; tsc/lint limpos.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/frota/api.ts frontend/src/app/frota/api.test.ts
git commit -m "feat(frota): api ordens e certificados do aparelho"
```

---

## Task 3: Frontend — ficha do aparelho (cliente link + OS + certificados)

**Files:**
- Modify: `frontend/src/app/frota/EquipamentoClienteDetailPage.tsx`

Contexto: adicionar link do cliente, carregar OS+certificados quando editando, e duas seções full-width abaixo do `DetailGrid` (antes do `{abrindoOS && ...}`). A página já importa `Table, TH, TD`, `Secao`, `formatData` não — então importar de `../ordens/api`: `ordensApi`, `formatData`, `TIPO_SERVICO`, e o tipo `OrdemListItem`. `Link` de `react-router-dom`.

- [ ] **Step 1: Imports**

Acrescentar:
```tsx
import { Link } from 'react-router-dom'
import { ordensApi, formatData, TIPO_SERVICO, type OrdemListItem } from '../ordens/api'
import type { EquipCertItem } from './api'
```
(`useNavigate`/`useParams` já vêm de `react-router-dom` — acrescentar `Link` ao import existente em vez de duplicar.)

- [ ] **Step 2: Estado e carregamento**

Adicionar estados (perto dos outros `useState`):
```tsx
  const [ordens, setOrdens] = useState<OrdemListItem[]>([])
  const [certs, setCerts] = useState<EquipCertItem[]>([])
  const [erroDownload, setErroDownload] = useState('')
```
No `useEffect` que já busca `historico` (o que depende de `[id, editando]`), acrescentar as duas buscas (dentro do mesmo effect, respeitando a flag `ativo`):
```tsx
    void equipamentosClienteApi.ordens(Number(id)).then((o) => { if (ativo) setOrdens(o) }).catch(() => {})
    void equipamentosClienteApi.certificados(Number(id)).then((c) => { if (ativo) setCerts(c) }).catch(() => {})
```

- [ ] **Step 3: Handler de download**

Adicionar (perto de `salvar`/`excluir`):
```tsx
  async function baixarPdf(os: number, tipo: 'C' | 'M') {
    setErroDownload('')
    try {
      await ordensApi.baixarCertificadoPdf(os, tipo)
    } catch {
      setErroDownload('Falha ao baixar PDF')
    }
  }
```

- [ ] **Step 4: Link do cliente**

Trocar `<p className="text-sm text-slate-400">Cliente: {nomeCliente}</p>` por:
```tsx
      <p className="text-sm text-slate-400">
        Cliente:{' '}
        {obj?.cliente
          ? <Link to={`/app/clientes/${obj.cliente}`} className="text-primary hover:underline">{nomeCliente}</Link>
          : <span>{nomeCliente}</span>}
      </p>
```

- [ ] **Step 5: Seções full-width (OS + certificados)**

Logo após o fechamento do `DetailGrid`/bloco condicional do form e ANTES de `{abrindoOS && obj && (`, inserir (só quando editando):
```tsx
      {editando && (
        <div className="rounded-2xl bg-background-surface border border-border p-5 space-y-4">
          <h2 className="text-sm font-semibold text-slate-100">Ordens de serviço</h2>
          {ordens.length === 0 ? (
            <p className="text-sm text-slate-500">Nenhuma OS.</p>
          ) : (
            <Table head={<><TH>OS</TH><TH>Chegada</TH><TH>Tipo</TH><TH>Fase</TH><TH>Situação</TH></>}>
              {ordens.map((o) => (
                <tr key={o.id} className="hover:bg-background-elevated transition-colors">
                  <TD><Link to={`/app/ordens/${o.id}`} className="font-semibold text-primary hover:underline">#{o.id}</Link></TD>
                  <TD>{formatData(o.data_chegada)}</TD>
                  <TD>{o.tipo_servico && o.tipo_servico in TIPO_SERVICO ? TIPO_SERVICO[o.tipo_servico as keyof typeof TIPO_SERVICO].label : '—'}</TD>
                  <TD>{o.fase_descricao ? (
                    <span className="inline-flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full" style={{ background: `#${o.fase_cor}` }} />
                      {o.fase_descricao}
                    </span>
                  ) : '—'}</TD>
                  <TD>{o.situacao}</TD>
                </tr>
              ))}
            </Table>
          )}
        </div>
      )}

      {editando && (
        <div className="rounded-2xl bg-background-surface border border-border p-5 space-y-4">
          <h2 className="text-sm font-semibold text-slate-100">Certificados</h2>
          {erroDownload && <p className="text-sm text-danger">{erroDownload}</p>}
          {certs.length === 0 ? (
            <p className="text-sm text-slate-500">Nenhum certificado gerado.</p>
          ) : (
            <Table head={<><TH>OS</TH><TH>Tipo</TH><TH>Gerado em</TH><TH>PDF</TH></>}>
              {certs.map((c) => (
                <tr key={`${c.os}-${c.tipo}`} className="hover:bg-background-elevated transition-colors">
                  <TD><Link to={`/app/ordens/${c.os}`} className="font-semibold text-primary hover:underline">#{c.os}</Link></TD>
                  <TD>{c.tipo === 'C' ? 'Calibração' : 'Manutenção'}</TD>
                  <TD>{formatData(c.data_geracao)}</TD>
                  <TD><button type="button" onClick={() => void baixarPdf(c.os, c.tipo)} className="text-xs font-semibold text-primary hover:underline">Baixar PDF</button></TD>
                </tr>
              ))}
            </Table>
          )}
        </div>
      )}
```

- [ ] **Step 6: Verificar**

Run: `cd frontend && npx tsc -b --noEmit && npx eslint src/app/frota/EquipamentoClienteDetailPage.tsx && npm run build`
Expected: sem erros, build verde.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app/frota/EquipamentoClienteDetailPage.tsx
git commit -m "feat(frota): ficha do aparelho com link do cliente, OS e certificados"
```

---

## Task 4: Changelog v1.4.2 + verificação final + memória

**Files:**
- Modify: `frontend/src/app/changelog/data.ts`

- [ ] **Step 1: Adicionar v1.4.2 no topo do array `CHANGELOG`**

```ts
  {
    versao: '1.4.2',
    data: '10/06/2026',
    itens: [
      { tipo: 'novidade', texto: 'Na ficha do aparelho agora aparecem as ordens de serviço do equipamento e todos os certificados de calibração já gerados, com download do PDF — facilitando o acesso a certificados antigos. O nome do cliente também virou link direto para a ficha do cliente.' },
    ],
  },
```

- [ ] **Step 2: Verificar build + suíte**

Run: `cd frontend && npm run build && npx vitest run`
Expected: build verde; testes passando.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/changelog/data.ts
git commit -m "docs(changelog): v1.4.2 — OS e certificados na ficha do aparelho"
```

- [ ] **Step 4: E2E manual (com o usuário)**

Abrir um aparelho com OS e certificados: ver o link do cliente, a lista de OS (clicável) e os certificados; baixar um PDF antigo.

- [ ] **Step 5: Atualizar memória**

Em `C:\Users\TI\.claude\projects\d--GitHub-GestorHS\memory\project_gestorhs.md`: registrar os endpoints `GET /equipamentos-cliente/{id}/ordens` e `/certificados` (+ schema `EquipCertItem`) e que a ficha do aparelho mostra OS + certificados com download (reusa `ordensApi.baixarCertificadoPdf`).

---

## Self-Review (preenchido)

**Spec coverage:** endpoints `/ordens` e `/certificados` + schema (T1); api frontend (T2); ficha do aparelho com link/OS/certificados (T3); changelog/memória/E2E (T4). Tudo coberto.

**Type consistency:** `EquipCertItem` (`os`, `tipo`, `data_geracao`) idêntico no backend (frota.py) e frontend (api.ts); `OrdemListOut`(back)/`OrdemListItem`(front) usados para a lista de OS; métodos `equipamentosClienteApi.ordens/certificados`; download via `ordensApi.baixarCertificadoPdf(os, tipo)` (assinatura já existente).

**Placeholders:** nenhum — todo passo tem código/comando. (Corrigida a linha confusa do 1º teste com a versão limpa logo abaixo dela.)
