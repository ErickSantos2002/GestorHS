# Aparelho: um único controle de ativo/inativo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remover o Select "Situação" (`status` A/I/M) da tela do aparelho, deixando o checkbox "Ativo" como único controle de ativo/inativo.

**Architecture:** O campo `status` é morto — nenhuma regra de negócio o lê, e ele só existe num Select que enganava o usuário. A remoção é em duas camadas independentes: os quatro schemas Pydantic que o expõem (`backend/app/schemas/frota.py`) e a tela + tipos do frontend. A coluna do banco fica intacta, sem migração.

**Tech Stack:** Backend Python 3.12 / FastAPI / Pydantic v2 / pytest. Frontend React 19 / TypeScript / Vite / Vitest + Testing Library.

**Spec:** [docs/superpowers/specs/2026-07-30-aparelho-ativo-unico-controle-design.md](../specs/2026-07-30-aparelho-ativo-unico-controle-design.md)

## Global Constraints

- **`status_calibracao` NÃO é o alvo.** Nos schemas e nos tipos, `status` e `status_calibracao` aparecem em linhas **vizinhas**. Só o `status` (A/I/M) sai; `status_calibracao` (`vencido`/`vencendo`/`em_dia`/`sem_data`) **fica**. Apagar o errado quebra a tela da frota inteira.
- **O parâmetro `status` da listagem também fica.** `GET /equipamentos-cliente?status=vencido` é o filtro de calibração, não este campo. Não confundir.
- **Nenhuma migração.** A coluna `equipamentos_cliente.status` permanece no banco com os dados de hoje. O modelo já tem `default="A"`, então aparelho novo continua nascendo com `'A'` sem ninguém informar.
- **Nenhuma mudança de comportamento em produção.** As cinco regras que leem `ativo` (portal, dashboard, alertas, e as duas cargas do GrowthHS) não são tocadas.
- **Nada a corrigir nos dados.** O aparelho 7939 (Cofco, Módulo PHOEBUS F000472) fica **ativo** — decisão explícita do Erick.
- Idioma do domínio é PT-BR; identificadores sem acentos.
- **Commits:** Conventional Commits em português **sem acentos**, assunto de **uma linha só**, sem corpo e **sem trailer de co-autor**.
- **Branch:** todo o trabalho vai em `feat/aparelho-ativo-unico-controle`. **Nunca `git add -A`** — sempre listar os caminhos (há outro agente trabalhando neste repo, com arquivos não rastreados em `backend/relatorios/` e PDFs em `docs/`). Confira `git branch --show-current` antes de cada commit. **Não fazer push nem merge** sem o Erick pedir.
- **Baseline de testes nesta máquina:** backend `4 failed` (2 em `tests/test_certificados_gerais.py`, 2 em `tests/test_publico_certificado_geral.py`, todas `PermissionError`); frontend `1 failed` (`src/app/clientes/ClienteEquipamentosTab.test.tsx > esconde "Novo aparelho" para nao-admin`). O número de `failed` é o que importa; o de `passed` sobe. Qualquer falha **além** dessas é regressão.
- **Ambiente:** backend `cd backend && source .venv/bin/activate`; frontend `cd frontend`.

---

### Task 0: Preparar branch e baseline

**Files:** nenhum.

- [ ] **Step 1: Criar a branch**

```bash
cd /home/ericks/github/GestorHS
git branch --show-current          # confirme que está em main
git checkout -b feat/aparelho-ativo-unico-controle
```

- [ ] **Step 2: Registrar o baseline**

```bash
cd backend && source .venv/bin/activate && pytest -q 2>&1 | tail -3
cd ../frontend && npm test 2>&1 | tail -5
```

Anote as linhas finais. Esperado: backend `4 failed`, frontend `1 failed`.

---

### Task 1: Remover `status` dos schemas da frota

**Files:**
- Modify: `backend/app/schemas/frota.py` (linhas 16, 56, 83, 95 — e o import da linha 2)
- Test: `backend/tests/test_frota_leitura.py` (acrescenta casos)
- Test: `backend/tests/test_frota_escrita.py` (acrescenta caso; limpa um payload)

**Interfaces:**
- Produces: a API de frota deixa de aceitar e de devolver o campo `status`. `EquipamentoClienteCreate`, `EquipamentoClienteUpdate`, `FrotaListOut` e `EquipamentoClienteOut` perdem o campo. Nada mais no backend referencia `EquipamentoCliente.status`.

**Nota sobre Pydantic v2:** `EquipamentoClienteCreate`/`Update` não declaram `model_config`, então o default `extra="ignore"` vale — um cliente antigo que ainda mande `"status": "A"` no corpo **não** toma 422, o campo é simplesmente ignorado. É o comportamento desejado (compatibilidade), e um dos testes abaixo trava isso.

- [ ] **Step 1: Escrever os testes que falham**

Acrescente ao fim de `backend/tests/test_frota_leitura.py`:

```python
def test_frota_nao_expoe_mais_o_campo_status(client, usuario_admin, db_session):
    """O campo `status` (A/I/M) era morto — nenhuma regra o lia — e saiu da API.
    `status_calibracao`, que e' outra coisa, continua."""
    from app.models import Cliente, Equipamento, EquipamentoCliente
    cli = Cliente(nome="Cliente Status")
    eq = Equipamento(descricao="Bafometro")
    db_session.add_all([cli, eq]); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie="S-ST")
    db_session.add(ec); db_session.commit(); db_session.refresh(ec)
    tok = client.post("/auth/login", json={"email": "admin@hs.com", "senha": "senha123"}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}

    lista = client.get("/equipamentos-cliente", headers=h)
    assert lista.status_code == 200
    item = lista.json()["items"][0]
    assert "status" not in item
    assert "status_calibracao" in item

    detalhe = client.get(f"/equipamentos-cliente/{ec.id}", headers=h)
    assert detalhe.status_code == 200
    assert "status" not in detalhe.json()
    assert "status_calibracao" in detalhe.json()
```

Acrescente ao fim de `backend/tests/test_frota_escrita.py`:

```python
def test_criar_e_editar_aparelho_sem_status(client, usuario_admin, db_session):
    """Criar/editar sem `status` funciona, e a coluna do banco mantem o default 'A'
    (ela continua existindo — nao houve migracao)."""
    from app.models import Cliente, Equipamento, EquipamentoCliente
    cli = Cliente(nome="Cliente Sem Status")
    eq = Equipamento(descricao="Bafometro")
    db_session.add_all([cli, eq]); db_session.flush(); db_session.commit()
    tok = client.post("/auth/login", json={"email": "admin@hs.com", "senha": "senha123"}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}

    criado = client.post("/equipamentos-cliente",
                         json={"cliente": cli.id, "equipamento": eq.id, "serie": "S-NS"}, headers=h)
    assert criado.status_code == 201
    iid = criado.json()["id"]
    assert db_session.get(EquipamentoCliente, iid).status == "A"

    assert client.patch(f"/equipamentos-cliente/{iid}",
                        json={"ativo": False}, headers=h).status_code == 200
    db_session.expire_all()
    obj = db_session.get(EquipamentoCliente, iid)
    assert obj.ativo is False
    assert obj.status == "A"   # a coluna nao e' mexida por ninguem


def test_status_enviado_por_cliente_antigo_e_ignorado_sem_erro(client, usuario_admin, db_session):
    """Compatibilidade: quem ainda mandar `status` no corpo nao toma 422 — o campo
    e' ignorado (Pydantic v2, extra='ignore')."""
    from app.models import Cliente, Equipamento, EquipamentoCliente
    cli = Cliente(nome="Cliente Legado")
    eq = Equipamento(descricao="Bafometro")
    db_session.add_all([cli, eq]); db_session.flush(); db_session.commit()
    tok = client.post("/auth/login", json={"email": "admin@hs.com", "senha": "senha123"}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    criado = client.post("/equipamentos-cliente",
                         json={"cliente": cli.id, "equipamento": eq.id, "serie": "S-LEG",
                               "status": "I"}, headers=h)
    assert criado.status_code == 201
    assert db_session.get(EquipamentoCliente, criado.json()["id"]).status == "A"
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_frota_leitura.py tests/test_frota_escrita.py -q`
Expected: FAIL — os testes novos falham porque `status` ainda vem nas respostas e porque o `"status": "I"` do último ainda é aceito e gravado.

- [ ] **Step 3: Remover o campo dos quatro schemas**

Em `backend/app/schemas/frota.py`, apague **apenas** estas quatro linhas (a linha `status_calibracao` logo abaixo de duas delas **fica**):

- `FrotaListOut` (linha 16): `    status: str`
- `EquipamentoClienteOut` (linha 56): `    status: str`
- `EquipamentoClienteCreate` (linha 83): `    status: Literal["A", "I", "M"] = "A"`
- `EquipamentoClienteUpdate` (linha 95): `    status: Optional[Literal["A", "I", "M"]] = None`

Depois disso `Literal` fica sem uso no arquivo — ajuste o import da linha 2:

```python
from typing import Optional
```

(era `from typing import Optional, Literal`)

- [ ] **Step 4: Limpar o payload legado de um teste existente**

Em `backend/tests/test_frota_escrita.py`, linha 33, o POST manda `"status": "A"` sem necessidade. Remova só esse par do JSON, deixando o resto igual:

```python
    criado = client.post("/equipamentos-cliente", json={"cliente": cid, "equipamento": eid, "serie": "S1"}, headers=h)
```

- [ ] **Step 5: Rodar e confirmar que passam**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_frota_leitura.py tests/test_frota_escrita.py tests/test_frota_os_certificados.py tests/test_frota_transferencia.py -q`
Expected: PASS

- [ ] **Step 6: Confirmar que ninguém mais lê o campo**

Run: `cd backend && grep -rn "EquipamentoCliente.status\|\"status\"" app/schemas/frota.py app/api/equipamentos_cliente.py | grep -v status_calibracao`
Expected: nenhuma linha referente ao campo A/I/M. (Ocorrências de `status` como filtro de calibração em `equipamentos_cliente.py` são esperadas e devem continuar.)

- [ ] **Step 7: Commit**

```bash
cd /home/ericks/github/GestorHS
git branch --show-current
git add backend/app/schemas/frota.py backend/tests/test_frota_leitura.py backend/tests/test_frota_escrita.py
git commit -m "refactor(frota): remove o campo status a/i/m dos schemas"
```

---

### Task 2: Remover o Select "Situação" da tela do aparelho

**Files:**
- Modify: `frontend/src/app/frota/api.ts` (linhas 23, 60, 86)
- Modify: `frontend/src/app/frota/EquipamentoClienteDetailPage.tsx` (linha 23 do `VAZIO`, linha 99 do carregamento, linhas 196-207 do formulário)
- Test: `frontend/src/app/frota/EquipamentoClienteDetailPage.ativo.test.tsx` (novo)

**Interfaces:**
- Consumes: a API da Task 1, que não devolve nem aceita mais `status`.
- Produces: `EquipamentoClientePayload`, `FrotaItem` e `EquipamentoCliente` sem o campo `status`. A tela do aparelho passa a ter só o checkbox "Ativo".

- [ ] **Step 1: Escrever o teste que falha**

Crie `frontend/src/app/frota/EquipamentoClienteDetailPage.ativo.test.tsx`:

```tsx
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

vi.mock('../../auth/AuthContext', () => ({ useAuth: () => ({ user: { funcao: 'Administrador' } }) }))
const { obter, atualizar } = vi.hoisted(() => ({ obter: vi.fn(), atualizar: vi.fn() }))
vi.mock('./api', async (orig) => {
  const real = await orig<typeof import('./api')>()
  return { ...real, equipamentosClienteApi: {
    obter, atualizar,
    historico: () => Promise.resolve([]), ordens: () => Promise.resolve([]),
    certificados: () => Promise.resolve([]), transferencias: () => Promise.resolve([]),
  } }
})
vi.mock('../cadastros/api', () => ({ equipamentosApi: { listar: () => Promise.resolve([]) } }))

import { EquipamentoClienteDetailPage } from './EquipamentoClienteDetailPage'

const APARELHO = {
  id: 7, cliente: 5, cliente_nome: 'ACME', equipamento: 1, equipamento_descricao: 'Bafometro',
  modulo: 0, serie: 'S1', patrimonio: null, datacompra: null, ult_calibragem: null,
  prox_calibragem: null, ativo: true, status_calibracao: 'sem_data' as const, os_atual: null,
  calib_cert: null, calib_temp: null, calib_pressao: null, calib_teste1: null, calib_teste2: null,
  calib_teste3: null, calib_teste_media: null, calib_situacao: null,
  modulo_instalado: null, instalado_em: null, em_estoque: false,
}

function editar() {
  return render(
    <MemoryRouter initialEntries={['/app/equipamentos/7']}>
      <Routes>
        <Route path="/app/equipamentos/:aparelhoId" element={<EquipamentoClienteDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

afterEach(() => { vi.clearAllMocks() })

describe('controle unico de ativo', () => {
  it('nao renderiza mais o select de Situacao', async () => {
    obter.mockResolvedValue(APARELHO)
    editar()
    expect(await screen.findByLabelText('Ativo')).toBeInTheDocument()
    expect(screen.queryByLabelText('Situação')).not.toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'Manutenção' })).not.toBeInTheDocument()
  })

  it('desmarcar o checkbox salva ativo=false e nao manda status', async () => {
    obter.mockResolvedValue(APARELHO)
    atualizar.mockResolvedValue({ ...APARELHO, ativo: false })
    editar()
    const check = await screen.findByLabelText('Ativo')
    await userEvent.click(check)
    await userEvent.click(screen.getByRole('button', { name: /salvar/i }))
    expect(atualizar).toHaveBeenCalledTimes(1)
    const [, payload] = atualizar.mock.calls[0]
    expect(payload.ativo).toBe(false)
    expect(payload).not.toHaveProperty('status')
  })
})
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd frontend && npx vitest run src/app/frota/EquipamentoClienteDetailPage.ativo.test.tsx`
Expected: FAIL — o Select "Situação" ainda está na tela e o payload ainda leva `status`.

- [ ] **Step 3: Remover `status` dos tipos**

Em `frontend/src/app/frota/api.ts`, apague **apenas** estas três linhas (a linha `status_calibracao` logo abaixo de duas delas **fica**):

- `FrotaItem` (linha 23): `  status: string`
- `EquipamentoCliente` (linha 60): `  status: string`
- `EquipamentoClientePayload` (linha 86): `  status: 'A' | 'I' | 'M'`

- [ ] **Step 4: Tirar `status` do estado da tela**

Em `frontend/src/app/frota/EquipamentoClienteDetailPage.tsx`:

O valor inicial (linha 22-24) perde o `status`:

```tsx
const VAZIO: EquipamentoClientePayload = {
  cliente: 0, equipamento: 0, modulo: 0, serie: null, patrimonio: null,
  datacompra: null, ult_calibragem: null, prox_calibragem: null, ativo: true,
}
```

O carregamento do aparelho (por volta da linha 96-100) perde o campo:

```tsx
        setForm({
          cliente: e.cliente, equipamento: e.equipamento, modulo: e.modulo, serie: e.serie, patrimonio: e.patrimonio,
          datacompra: e.datacompra, ult_calibragem: e.ult_calibragem, prox_calibragem: e.prox_calibragem,
          ativo: e.ativo,
        })
```

- [ ] **Step 5: Trocar o Select pelo checkbox no formulário**

Em `frontend/src/app/frota/EquipamentoClienteDetailPage.tsx`, substitua o bloco das linhas 196-207 (o `grid` com Módulo + Select, seguido do `label` solto do checkbox) por um `grid` só, com o checkbox ocupando a coluna que era do Select:

```tsx
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Input id="ec-modulo" label="Módulo" type="number" value={String(form.modulo)} onChange={(e) => set('modulo', Number(e.target.value) || 0)} disabled={ro} />
          <label htmlFor="ec-ativo" className="flex items-center gap-2 text-sm text-slate-300 sm:self-end sm:pb-2">
            <input id="ec-ativo" type="checkbox" checked={form.ativo} onChange={(e) => set('ativo', e.target.checked)} disabled={ro} className="accent-primary" />
            Ativo
          </label>
        </div>
```

O `id`/`htmlFor` são necessários para o `getByLabelText('Ativo')` do teste encontrar o checkbox.

- [ ] **Step 6: Verificar se o import de `Select` ainda é usado**

Run: `cd frontend && grep -n "<Select" src/app/frota/EquipamentoClienteDetailPage.tsx`
Se **não** houver mais nenhum `<Select`, remova `Select` do import da linha 5 (`import { Select } from '../../components/ui/Select'`). Se ainda houver (o campo "Equipamento" usa um), **mantenha** o import.

- [ ] **Step 7: Rodar e confirmar que passa**

Run: `cd frontend && npx vitest run src/app/frota/`
Expected: PASS — o teste novo e os três já existentes (`.datas`, `.embutido`, `elo`, `CertificadoVenda`).

- [ ] **Step 8: Verificação de tipos e build**

Run: `cd frontend && npm run lint && npx tsc -b --noEmit && npm run build`
Expected: sem erro. Se `tsc` reclamar de `status` em algum lugar que o plano não previu, é um consumidor que ninguém mapeou — corrija removendo o uso, e registre no relatório.

- [ ] **Step 9: Commit**

```bash
cd /home/ericks/github/GestorHS
git branch --show-current
git add frontend/src/app/frota/api.ts frontend/src/app/frota/EquipamentoClienteDetailPage.tsx frontend/src/app/frota/EquipamentoClienteDetailPage.ativo.test.tsx
git commit -m "refactor(frota): tela do aparelho com um unico controle de ativo"
```

---

### Task 3: Changelog e verificação final

**Files:**
- Modify: `frontend/src/app/changelog/data.ts` (nova entrada no topo)

- [ ] **Step 1: Rodar a suíte inteira do backend**

Run: `cd backend && source .venv/bin/activate && pytest -q 2>&1 | tail -5`
Expected: `4 failed` (as pré-existentes) e nenhuma falha nova.

- [ ] **Step 2: Rodar a suíte inteira do frontend**

Run: `cd frontend && npm test 2>&1 | tail -8`
Expected: `1 failed` (a pré-existente em `ClienteEquipamentosTab.test.tsx`) e nenhuma falha nova.

- [ ] **Step 3: Adicionar a entrada no changelog**

Em `frontend/src/app/changelog/data.ts`, como **primeira** entrada de `CHANGELOG` (antes da `1.33.0`):

```ts
  {
    versao: '1.33.1',
    data: '30/07/2026',
    itens: [
      { tipo: 'melhoria', texto: 'A tela do aparelho tinha dois jeitos de dizer se ele está ativo — o campo "Situação" e a caixinha "Ativo" — e só a caixinha valia de verdade. O campo "Situação" foi removido: agora é a caixinha "Ativo" que controla se o aparelho aparece no portal do cliente, no painel, nos alertas e nas cargas de cobrança.' },
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
git commit -m "docs(changelog): v1.33.1 — aparelho com um unico controle de ativo"
```

- [ ] **Step 6: Resumo para o Erick**

Não faça push nem merge. Reporte: falhas antes/depois nas duas suítes, arquivos tocados, e confirmação de que a coluna `equipamentos_cliente.status` não foi tocada (nenhuma migração criada).

---

## Notas de execução

- **Ordem importa pouco, mas a Task 1 vem antes da 2:** o teste do frontend monta o objeto do aparelho **sem** `status`, o que só é coerente depois da API parar de devolvê-lo.
- **O risco desta entrega é apagar a linha errada.** Em `schemas/frota.py` e em `frota/api.ts`, `status` e `status_calibracao` são linhas vizinhas. Depois de cada remoção, confira que `status_calibracao` continua lá.
- **Se `tsc` acusar um consumidor de `status` fora dos arquivos previstos**, não invente: remova o uso, rode a suíte do frontend inteira, e registre o achado no relatório — significa que a spec subestimou o alcance.
