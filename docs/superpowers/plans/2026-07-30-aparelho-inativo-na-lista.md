# Aparelho inativo visível na lista — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mostrar na lista de aparelhos quais estão inativos (selo + linha esmaecida) e permitir filtrar por ativo/inativo na página da Frota.

**Architecture:** Três camadas independentes. O backend ganha um parâmetro `ativo` opcional na listagem; o cliente HTTP do frontend repassa esse parâmetro; e as duas telas que renderizam a mesma tabela (Frota e aba Equipamentos do cliente) ganham o selo "Inativo" e a linha esmaecida. Nenhuma migração, nenhum campo novo — `ativo` já existe e já é lido pelas regras de negócio.

**Tech Stack:** Backend Python 3.12 / FastAPI / SQLAlchemy 2 / pytest. Frontend React 19 / TypeScript / Tailwind v4 / Vitest + Testing Library.

**Spec:** [docs/superpowers/specs/2026-07-30-aparelho-inativo-na-lista-design.md](../specs/2026-07-30-aparelho-inativo-na-lista-design.md)

## Global Constraints

- **A palavra "Status" já está ocupada** pela coluna e pelo filtro de **calibração** (`Em dia`/`Vencendo`/`Vencido`/`Sem data`). O filtro novo chama-se **"Aparelhos"** (opções *Todos* / *Ativos* / *Inativos*). **Nunca** usar "Situação" — é o campo morto A/I/M aposentado na v1.33.1; reusar a palavra ressuscita a confusão que aquela entrega desfez.
- **Aparelho ativo não ganha selo nenhum.** O indicador só aparece nos inativos (~20% da base). Nada de coluna nova.
- **A lista continua abrindo com todos** — o filtro nasce em *Todos*. Esconder inativo por padrão foi considerado e descartado.
- **Esmaecido = `opacity-60` no `<tr>`**, somado às classes que já existem lá. Não tocar no componente `Table`.
- **Badge de calibração de aparelho inativo vai para o tom `neutral`**, mantendo o texto ("Vencido" continua escrito, só perde o vermelho).
- Nenhuma migração; nenhum schema novo; o portal do cliente não muda (já filtra `ativo = true` no backend).
- Idioma PT-BR: textos de interface com acentos; identificadores sem acentos.
- **Commits:** Conventional Commits em português **sem acentos**, assunto de **uma linha só**, sem corpo e **sem trailer de co-autor**.
- **Branch:** `feat/aparelho-inativo-na-lista`. **Nunca `git add -A`** — listar os caminhos (há outro agente neste repo, com arquivos não rastreados em `backend/relatorios/` e PDFs em `docs/`). Conferir `git branch --show-current` antes de cada commit. **Não fazer push nem merge** sem o Erick pedir.
- **Baseline:** backend `4 failed` (2 em `tests/test_certificados_gerais.py`, 2 em `tests/test_publico_certificado_geral.py`, todas `PermissionError`); frontend `1 failed` — **`ClienteEquipamentosTab.test.tsx > esconde "Novo aparelho" para não-admin`**, que é um dos arquivos desta entrega. Ela **já falhava antes** (o teste está desatualizado: `podeGerenciarCadastros` em `auth/roles.ts:54` hoje inclui Expedição, então o botão aparece mesmo). **Não corrija esse teste** — está fora do escopo e é decisão de produto. O número de `failed` é o que importa; qualquer falha **além** dessas é regressão.
- **Ambiente:** backend `cd backend && source .venv/bin/activate`; frontend `cd frontend`.

---

### Task 0: Preparar branch e baseline

**Files:** nenhum.

- [ ] **Step 1: Criar a branch**

```bash
cd /home/ericks/github/GestorHS
git branch --show-current          # confirme que está em main
git checkout -b feat/aparelho-inativo-na-lista
```

- [ ] **Step 2: Registrar o baseline**

```bash
cd backend && source .venv/bin/activate && pytest -q 2>&1 | tail -3
cd ../frontend && npm test 2>&1 | tail -5
```

Esperado: backend `4 failed`, frontend `1 failed`.

---

### Task 1: Filtro `ativo` na listagem (backend)

**Files:**
- Modify: `backend/app/api/equipamentos_cliente.py` (função `listar`, por volta das linhas 76-100)
- Test: `backend/tests/test_frota_leitura.py` (acrescenta casos)

**Interfaces:**
- Produces: `GET /equipamentos-cliente?ativo=true|false`. Omitido = todos (comportamento de hoje). Consumido pela Task 2, que passa o parâmetro pelo cliente HTTP.

- [ ] **Step 1: Escrever os testes que falham**

Acrescente ao fim de `backend/tests/test_frota_leitura.py`:

```python
def _dois_aparelhos(db):
    """Um ativo e um inativo, do mesmo cliente."""
    from app.models import Cliente, Equipamento, EquipamentoCliente
    cli = Cliente(nome="Cliente Ativo/Inativo")
    eq = Equipamento(descricao="Bafometro")
    db.add_all([cli, eq]); db.flush()
    ativo = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie="S-ATIVO", ativo=True)
    inativo = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie="S-INATIVO", ativo=False)
    db.add_all([ativo, inativo]); db.commit()
    return cli.id


def test_frota_filtro_ativo_true(client, usuario_admin, db_session):
    _dois_aparelhos(db_session)
    tok = client.post("/auth/login", json={"email": "admin@hs.com", "senha": "senha123"}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    r = client.get("/equipamentos-cliente?ativo=true", headers=h)
    assert r.status_code == 200
    series = [i["serie"] for i in r.json()["items"]]
    assert series == ["S-ATIVO"]


def test_frota_filtro_ativo_false(client, usuario_admin, db_session):
    _dois_aparelhos(db_session)
    tok = client.post("/auth/login", json={"email": "admin@hs.com", "senha": "senha123"}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    r = client.get("/equipamentos-cliente?ativo=false", headers=h)
    assert r.status_code == 200
    series = [i["serie"] for i in r.json()["items"]]
    assert series == ["S-INATIVO"]


def test_frota_sem_filtro_ativo_devolve_os_dois(client, usuario_admin, db_session):
    """Compatibilidade: sem o parametro a lista continua trazendo tudo, como antes."""
    _dois_aparelhos(db_session)
    tok = client.post("/auth/login", json={"email": "admin@hs.com", "senha": "senha123"}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    r = client.get("/equipamentos-cliente", headers=h)
    assert r.status_code == 200
    assert r.json()["total"] == 2


def test_frota_filtro_ativo_combina_com_filtro_de_calibracao(client, usuario_admin, db_session):
    """Os dois filtros sao independentes e se somam."""
    from datetime import date, timedelta
    from app.models import Cliente, Equipamento, EquipamentoCliente
    cli = Cliente(nome="Cliente Combinado")
    eq = Equipamento(descricao="Bafometro")
    db_session.add_all([cli, eq]); db_session.flush()
    ontem = date.today() - timedelta(days=1)
    db_session.add_all([
        EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie="S-AT-VENC",
                           ativo=True, prox_calibragem=ontem),
        EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie="S-IN-VENC",
                           ativo=False, prox_calibragem=ontem),
    ])
    db_session.commit()
    tok = client.post("/auth/login", json={"email": "admin@hs.com", "senha": "senha123"}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    r = client.get("/equipamentos-cliente?ativo=true&status=vencido", headers=h)
    assert r.status_code == 200
    assert [i["serie"] for i in r.json()["items"]] == ["S-AT-VENC"]
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_frota_leitura.py -q`
Expected: FAIL — sem o parâmetro no endpoint, `?ativo=true` é ignorado e as listas voltam com os dois aparelhos.

- [ ] **Step 3: Adicionar o parâmetro no endpoint**

Em `backend/app/api/equipamentos_cliente.py`, na assinatura da função `listar`, acrescente `ativo` logo depois de `status`:

```python
def listar(
    cliente: int | None = None,
    status: str | None = None,
    ativo: bool | None = None,
    q: str | None = None,
    offset: int = 0,
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_usuario),
):
```

E no corpo, logo depois do bloco `if cliente is not None:` e antes do `if status:`:

```python
    if ativo is not None:
        # Filtro opcional: omitido devolve ativos E inativos, como sempre foi.
        query = query.filter(EquipamentoCliente.ativo.is_(ativo))
```

- [ ] **Step 4: Rodar e confirmar que passam**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_frota_leitura.py tests/test_frota_escrita.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /home/ericks/github/GestorHS
git branch --show-current
git add backend/app/api/equipamentos_cliente.py backend/tests/test_frota_leitura.py
git commit -m "feat(frota): filtro de ativo na listagem de aparelhos"
```

---

### Task 2: Frota — filtro "Aparelhos", selo e linha esmaecida

**Files:**
- Modify: `frontend/src/app/frota/api.ts` (interface `FrotaParams` e a função `listar`, por volta das linhas 174-190)
- Modify: `frontend/src/app/frota/FrotaPage.tsx`
- Test: `frontend/src/app/frota/FrotaPage.test.tsx` (**novo** — não existe hoje)

**Interfaces:**
- Consumes: `GET /equipamentos-cliente?ativo=true|false` da Task 1.
- Produces: `FrotaParams.ativo?: boolean` no cliente HTTP — reusado pela Task 3? **Não**: a aba do cliente não ganha filtro. Nada além desta task depende do que ela produz.

- [ ] **Step 1: Escrever o teste que falha**

Crie `frontend/src/app/frota/FrotaPage.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../../auth/AuthContext', () => ({ useAuth: () => ({ user: { funcao: 'Administrador' } }) }))

const { listar } = vi.hoisted(() => ({ listar: vi.fn() }))
vi.mock('./api', () => ({
  equipamentosClienteApi: { listar },
  STATUS_CALIBRACAO: {
    em_dia: { label: 'Em dia', tone: 'primary' as const },
    vencendo: { label: 'Vencendo', tone: 'warning' as const },
    vencido: { label: 'Vencido', tone: 'danger' as const },
    sem_data: { label: 'Sem data', tone: 'neutral' as const },
  },
}))

import { FrotaPage } from './FrotaPage'

function item(over: Partial<Record<string, unknown>> = {}) {
  return {
    id: 1, cliente: 5, cliente_nome: 'ACME', equipamento: 9,
    equipamento_descricao: 'Bafômetro X', serie: 'SN-1', patrimonio: null,
    prox_calibragem: '2026-08-01', ativo: true, status_calibracao: 'em_dia',
    ...over,
  }
}

function renderPage() {
  return render(<MemoryRouter initialEntries={['/app/equipamentos']}><FrotaPage /></MemoryRouter>)
}

describe('FrotaPage — aparelho inativo', () => {
  beforeEach(() => { listar.mockReset() })

  it('marca a linha do inativo com selo e esmaecido', async () => {
    listar.mockResolvedValue({ items: [
      item({ id: 1, equipamento_descricao: 'Bafômetro Ativo', ativo: true }),
      item({ id: 2, equipamento_descricao: 'Bafômetro Inativo', ativo: false, serie: 'SN-2' }),
    ], total: 2 })
    renderPage()

    const linhaInativa = (await screen.findByText('Bafômetro Inativo')).closest('tr')
    expect(linhaInativa).not.toBeNull()
    expect(linhaInativa!.className).toContain('opacity-60')
    expect(linhaInativa!.textContent).toContain('Inativo')

    const linhaAtiva = screen.getByText('Bafômetro Ativo').closest('tr')
    expect(linhaAtiva!.className).not.toContain('opacity-60')
    expect(linhaAtiva!.textContent).not.toContain('Inativo')
  })

  it('nao pinta de alarme a calibracao de um aparelho inativo', async () => {
    listar.mockResolvedValue({ items: [
      item({ id: 3, equipamento_descricao: 'Vencido Inativo', ativo: false, status_calibracao: 'vencido' }),
    ], total: 1 })
    renderPage()
    const badge = await screen.findByText('Vencido')
    // tom neutral em vez de danger — o aparelho saiu de uso, nao e' fila de trabalho
    expect(badge.className).not.toContain('text-danger')
  })

  it('o filtro Aparelhos manda o parametro ativo na chamada', async () => {
    listar.mockResolvedValue({ items: [], total: 0 })
    renderPage()
    await screen.findByText(/Nenhum aparelho/i)
    expect(listar).toHaveBeenLastCalledWith(expect.objectContaining({ ativo: undefined }))

    await userEvent.selectOptions(screen.getByLabelText('Aparelhos'), 'true')
    expect(listar).toHaveBeenLastCalledWith(expect.objectContaining({ ativo: true }))

    await userEvent.selectOptions(screen.getByLabelText('Aparelhos'), 'false')
    expect(listar).toHaveBeenLastCalledWith(expect.objectContaining({ ativo: false }))

    await userEvent.selectOptions(screen.getByLabelText('Aparelhos'), '')
    expect(listar).toHaveBeenLastCalledWith(expect.objectContaining({ ativo: undefined }))
  })
})
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd frontend && npx vitest run src/app/frota/FrotaPage.test.tsx`
Expected: FAIL — não há selo, nem `opacity-60`, nem filtro "Aparelhos".

- [ ] **Step 3: Passar o parâmetro no cliente HTTP**

Em `frontend/src/app/frota/api.ts`, na interface `FrotaParams`, acrescente `ativo` logo depois de `status`:

```ts
  status?: string
  ativo?: boolean
```

E dentro de `listar`, logo depois da linha do `status`:

```ts
    if (params.ativo !== undefined) sp.set('ativo', String(params.ativo))
```

(`!== undefined` e não `if (params.ativo)`, senão `false` nunca seria enviado.)

- [ ] **Step 4: Adicionar o estado e o filtro na página**

Em `frontend/src/app/frota/FrotaPage.tsx`:

Importe o utilitário de classes junto dos outros imports:

```tsx
import { cn } from '../../lib/utils'
```

Acrescente o estado ao lado de `statusFiltro`:

```tsx
  const [ativoFiltro, setAtivoFiltro] = useState('')
```

Na chamada dentro do `useEffect`, acrescente o parâmetro:

```tsx
      .listar({
        cliente: clienteId,
        status: statusFiltro || undefined,
        ativo: ativoFiltro === '' ? undefined : ativoFiltro === 'true',
        q: busca || undefined,
        offset,
        limit: LIMITE,
      })
```

E acrescente `ativoFiltro` ao array de dependências do mesmo `useEffect`:

```tsx
  }, [clienteId, statusFiltro, ativoFiltro, busca, offset])
```

- [ ] **Step 5: Adicionar o Select "Aparelhos" na barra de busca**

Ainda em `FrotaPage.tsx`, o `SearchBar` hoje recebe um `antes` com um único `<div className="w-48">` envolvendo o Select de Status. Substitua o bloco `antes={...}` inteiro por este, que envolve os dois Selects num flex para ficarem lado a lado:

```tsx
        antes={
          <div className="flex gap-3">
            <div className="w-48">
              <Select
                id="status"
                label="Status"
                value={statusFiltro}
                onChange={(e) => {
                  setOffset(0)
                  setStatusFiltro(e.target.value)
                }}
              >
                <option value="">Todos</option>
                <option value="em_dia">Em dia</option>
                <option value="vencendo">Vencendo</option>
                <option value="vencido">Vencido</option>
                <option value="sem_data">Sem data</option>
              </Select>
            </div>
            <div className="w-48">
              <Select
                id="ativo"
                label="Aparelhos"
                value={ativoFiltro}
                onChange={(e) => {
                  setOffset(0)
                  setAtivoFiltro(e.target.value)
                }}
              >
                <option value="">Todos</option>
                <option value="true">Ativos</option>
                <option value="false">Inativos</option>
              </Select>
            </div>
          </div>
        }
```

O Select de Status é reproduzido acima **sem nenhuma alteração** — ele só mudou de lugar, para dentro do novo flex. Confira que as opções continuam idênticas às de antes.

- [ ] **Step 6: Marcar a linha do inativo**

Ainda em `FrotaPage.tsx`, no `itens.map(...)`, troque o `<tr>` e as duas `<TD>` afetadas:

```tsx
                <tr
                  key={e.id}
                  className={cn('hover:bg-background-elevated transition-colors cursor-pointer', !e.ativo && 'opacity-60')}
                  onClick={() => navigate(`/app/equipamentos/${e.id}`)}
                >
                  <TD>
                    <span className="inline-flex items-center gap-2">
                      {e.equipamento_descricao ?? '—'}
                      {!e.ativo && <Badge tone="neutral">Inativo</Badge>}
                    </span>
                  </TD>
                  <TD>{e.cliente_nome ?? '—'}</TD>
                  <TD>{e.serie || e.patrimonio || '—'}</TD>
                  <TD>{e.prox_calibragem ?? '—'}</TD>
                  <TD><Badge tone={e.ativo ? s.tone : 'neutral'}>{s.label}</Badge></TD>
                </tr>
```

- [ ] **Step 7: Rodar e confirmar que passa**

Run: `cd frontend && npx vitest run src/app/frota/`
Expected: PASS — o arquivo novo e os que já existiam na pasta.

- [ ] **Step 8: Verificação de tipos e build**

Run: `cd frontend && npm run lint && npx tsc -b --noEmit && npm run build`
Expected: sem erro.

- [ ] **Step 9: Commit**

```bash
cd /home/ericks/github/GestorHS
git branch --show-current
git add frontend/src/app/frota/api.ts frontend/src/app/frota/FrotaPage.tsx frontend/src/app/frota/FrotaPage.test.tsx
git commit -m "feat(frota): selo de inativo e filtro de aparelhos na lista"
```

---

### Task 3: Aba Equipamentos do cliente — selo e linha esmaecida

**Files:**
- Modify: `frontend/src/app/clientes/ClienteEquipamentosTab.tsx`
- Test: `frontend/src/app/clientes/ClienteEquipamentosTab.test.tsx` (acrescenta casos)

**Interfaces:**
- Consumes: nada de tasks anteriores — a aba usa `equipamentosClienteApi.listar({ cliente })` sem filtro novo.
- Produces: nada.

**Escopo:** esta aba recebe **só** o selo e o esmaecido. **Não** ganha filtro — ela não tem barra de filtros hoje, e criar uma só para isso é mais tela do que o problema pede.

- [ ] **Step 1: Escrever o teste que falha**

Acrescente dentro do `describe('ClienteEquipamentosTab', ...)` em `frontend/src/app/clientes/ClienteEquipamentosTab.test.tsx`, ao lado dos testes já existentes:

```tsx
  it('marca a linha do aparelho inativo com selo e esmaecido', async () => {
    listar.mockResolvedValue({ items: [
      { id: 1, cliente: 5, cliente_nome: 'ACME', equipamento: 9, equipamento_descricao: 'Bafômetro Ativo',
        serie: 'SN-1', patrimonio: null, prox_calibragem: '2026-08-01', ativo: true, status_calibracao: 'em_dia' },
      { id: 2, cliente: 5, cliente_nome: 'ACME', equipamento: 9, equipamento_descricao: 'Bafômetro Inativo',
        serie: 'SN-2', patrimonio: null, prox_calibragem: '2026-08-01', ativo: false, status_calibracao: 'vencido' },
    ], total: 2 })
    renderTab()

    const linhaInativa = (await screen.findByText('Bafômetro Inativo')).closest('tr')
    expect(linhaInativa).not.toBeNull()
    expect(linhaInativa!.className).toContain('opacity-60')
    expect(linhaInativa!.textContent).toContain('Inativo')

    const linhaAtiva = screen.getByText('Bafômetro Ativo').closest('tr')
    expect(linhaAtiva!.className).not.toContain('opacity-60')
    expect(linhaAtiva!.textContent).not.toContain('Inativo')
  })

  it('nao pinta de alarme a calibracao de um aparelho inativo', async () => {
    listar.mockResolvedValue({ items: [
      { id: 3, cliente: 5, cliente_nome: 'ACME', equipamento: 9, equipamento_descricao: 'Vencido Inativo',
        serie: 'SN-3', patrimonio: null, prox_calibragem: '2026-01-01', ativo: false, status_calibracao: 'vencido' },
    ], total: 1 })
    renderTab()
    const badge = await screen.findByText('Vencido')
    expect(badge.className).not.toContain('text-danger')
  })
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd frontend && npx vitest run src/app/clientes/ClienteEquipamentosTab.test.tsx`
Expected: FAIL nos dois testes novos. **O teste `esconde "Novo aparelho" para não-admin` também falha — isso é a falha pré-existente do baseline, não sua.** Não a corrija.

- [ ] **Step 3: Marcar a linha do inativo**

Em `frontend/src/app/clientes/ClienteEquipamentosTab.tsx`, importe o utilitário de classes junto dos outros imports:

```tsx
import { cn } from '../../lib/utils'
```

E no `itens.map(...)`, troque o `<tr>` e as duas `<TD>` afetadas:

```tsx
              <tr
                key={e.id}
                className={cn('hover:bg-background-elevated transition-colors cursor-pointer', !e.ativo && 'opacity-60')}
                onClick={() => navigate(String(e.id))}
              >
                <TD>
                  <span className="inline-flex items-center gap-2">
                    {e.equipamento_descricao ?? '—'}
                    {!e.ativo && <Badge tone="neutral">Inativo</Badge>}
                  </span>
                </TD>
                <TD>{e.serie || e.patrimonio || '—'}</TD>
                <TD>{e.prox_calibragem ?? '—'}</TD>
                <TD><Badge tone={e.ativo ? s.tone : 'neutral'}>{s.label}</Badge></TD>
              </tr>
```

- [ ] **Step 4: Limpar um resquício no teste existente**

No mesmo arquivo de teste, o primeiro caso (`lista os aparelhos do cliente`) monta o item com `status: 'A'` — campo que **não existe mais** (foi removido na v1.33.1). Apague só esse par do objeto, deixando o resto igual.

- [ ] **Step 5: Rodar e confirmar que passa**

Run: `cd frontend && npx vitest run src/app/clientes/ClienteEquipamentosTab.test.tsx`
Expected: os dois testes novos PASSAM; continua **1 falha** — a pré-existente `esconde "Novo aparelho" para não-admin`. Se aparecer qualquer outra, é regressão sua.

- [ ] **Step 6: Verificação de tipos e build**

Run: `cd frontend && npm run lint && npx tsc -b --noEmit && npm run build`
Expected: sem erro.

- [ ] **Step 7: Commit**

```bash
cd /home/ericks/github/GestorHS
git branch --show-current
git add frontend/src/app/clientes/ClienteEquipamentosTab.tsx frontend/src/app/clientes/ClienteEquipamentosTab.test.tsx
git commit -m "feat(frota): selo de inativo na aba de equipamentos do cliente"
```

---

### Task 4: Changelog e verificação final

**Files:**
- Modify: `frontend/src/app/changelog/data.ts` (nova entrada no topo)

- [ ] **Step 1: Rodar a suíte inteira do backend**

Run: `cd backend && source .venv/bin/activate && pytest -q 2>&1 | tail -5`
Expected: `4 failed` (as pré-existentes) e nenhuma falha nova.

- [ ] **Step 2: Rodar a suíte inteira do frontend**

Run: `cd frontend && npm test 2>&1 | tail -8`
Expected: `1 failed` (`ClienteEquipamentosTab.test.tsx > esconde "Novo aparelho" para não-admin`, pré-existente) e nenhuma falha nova.

- [ ] **Step 3: Adicionar a entrada no changelog**

Em `frontend/src/app/changelog/data.ts`, como **primeira** entrada de `CHANGELOG`:

```ts
  {
    versao: '1.34.0',
    data: '30/07/2026',
    itens: [
      { tipo: 'novidade', texto: 'A lista de aparelhos agora mostra quais estão inativos: a linha aparece esmaecida e com o selo "Inativo" ao lado do nome. Vale na página de Equipamentos e na aba Equipamentos dentro do cliente.' },
      { tipo: 'novidade', texto: 'Novo filtro "Aparelhos" na página de Equipamentos, para ver só os ativos, só os inativos ou todos. Ele começa em "Todos", então a lista abre como sempre abriu.' },
      { tipo: 'melhoria', texto: 'Aparelho inativo com calibração vencida não aparece mais em vermelho na lista — ele saiu de uso, então não é trabalho pendente. O texto continua lá para consulta.' },
    ],
  },
```

- [ ] **Step 4: Verificar o frontend de novo**

Run: `cd frontend && npm run lint && npx tsc -b --noEmit && npm run build`
Expected: sem erro.

- [ ] **Step 5: Commit**

```bash
cd /home/ericks/github/GestorHS
git branch --show-current
git add frontend/src/app/changelog/data.ts
git commit -m "docs(changelog): v1.34.0 — aparelho inativo visivel na lista"
```

- [ ] **Step 6: Resumo para o Erick**

Não faça push nem merge. Reporte: falhas antes/depois nas duas suítes, arquivos tocados, e confirmação de que nenhuma migração foi criada.

---

## Notas de execução

- **A Task 1 vem antes da 2** (o filtro do frontend depende do parâmetro no backend). As Tasks 2 e 3 são independentes entre si.
- **A falha pré-existente é no arquivo que a Task 3 edita.** Ela vai aparecer em toda rodada daquele arquivo. O diagnóstico já está feito: `podeGerenciarCadastros` (`frontend/src/auth/roles.ts:54`) hoje inclui Expedição, então o botão "Novo aparelho" aparece e o teste que espera o contrário está desatualizado. **Corrigir isso é decisão de produto e está fora do escopo desta entrega** — se o implementador "consertar", vai estar mudando o significado de um teste sem autorização.
- **Se `getByLabelText('Aparelhos')` não achar o Select**, confira como o componente `Select` (em `components/ui/Select.tsx`) liga `label` e `id` — o filtro de calibração ao lado usa o mesmo padrão e serve de referência.
