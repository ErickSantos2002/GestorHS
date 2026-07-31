# Pós-Vendas edita cadastros + controle de Ativo mais bonito — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Comercial Pós-Vendas passa a poder **editar** cliente e aparelho (inclusive marcar ativo/inativo), sem ganhar criar nem transferir; e o controle de Ativo vira um interruptor com o texto do estado.

**Architecture:** A permissão de cadastro, hoje uma tupla única que gateia criar/editar/transferir, se divide em duas: `GESTOR_CADASTRO` (criar, transferir) e `EDITOR_CADASTRO` (editar, = a primeira + Pós-Vendas). O frontend espelha com `podeEditarCadastros`. Em paralelo, o checkbox cru de Ativo dá lugar ao componente `Toggle` da casa, que ganha a prop `disabled` que lhe faltava.

**Tech Stack:** Backend Python 3.12 / FastAPI / pytest. Frontend React 19 / TypeScript / Tailwind v4 / Vitest + Testing Library.

**Spec:** [docs/superpowers/specs/2026-07-31-pos-vendas-edita-cadastros-design.md](../specs/2026-07-31-pos-vendas-edita-cadastros-design.md)

## Global Constraints

- **Pós-Vendas ganha SÓ editar.** Criar cliente/aparelho e transferir aparelho continuam em `GESTOR_CADASTRO`; excluir continua exclusivo do Administrador. Um `POST` ou uma transferência que passe a aceitar Pós-Vendas é defeito.
- **`EDITOR_CADASTRO` é derivada de `GESTOR_CADASTRO`** (`GESTOR_CADASTRO + ("Comercial Pós-Vendas",)`), para as duas não divergirem quando alguém mexer numa delas.
- **O nome da função é exatamente `"Comercial Pós-Vendas"`** (com acentos — é o valor gravado no banco).
- **Cliente e aparelho não são simétricos.** `ClienteDetailPage` é **só criação** (rota `clientes/novo`; seu `salvar` só chama `criar`) e **continua** com `podeGerenciarCadastros`. Quem edita cliente é `ClienteDadosTab`. Já `EquipamentoClienteDetailPage` faz os dois modos e precisa do ternário.
- **`Toggle` é usado por 4 telas** (`MainLayout`, `Topbar`, `CaixasPage`, `UsuariosPage`). A prop `disabled` nasce opcional com default `false` para não mudar nada nelas.
- **Regra de função é espelhada em dois lados** — mudou em `backend/app/api/deps.py`, muda em `frontend/src/auth/roles.ts`. Os comentários que apontam um para o outro devem continuar corretos.
- Idioma PT-BR: textos de interface com acentos; identificadores sem acentos.
- **Commits:** Conventional Commits em português **sem acentos**, assunto de **uma linha só**, sem corpo e **sem trailer de co-autor**.
- **Branch:** `feat/pos-vendas-edita-cadastros`. **Nunca `git add -A`** — listar os caminhos (há outro agente neste repo, com arquivos não rastreados em `backend/relatorios/` e PDFs em `docs/`). Conferir `git branch --show-current` antes de cada commit. **Não fazer push nem merge** sem o Erick pedir.
- **Baseline:** backend `4 failed` (2 em `tests/test_certificados_gerais.py`, 2 em `tests/test_publico_certificado_geral.py`, todas `PermissionError`); frontend `1 failed` (`ClienteEquipamentosTab.test.tsx > esconde "Novo aparelho" para não-admin`). **A Task 4 corrige essa falha do frontend** — ao final da entrega o frontend fecha com **0 falhas**. Qualquer falha além dessas é regressão.
- **Ambiente:** backend `cd backend && source .venv/bin/activate`; frontend `cd frontend`.

---

### Task 0: Preparar branch e baseline

**Files:** nenhum.

- [ ] **Step 1: Criar a branch**

```bash
cd /home/ericks/github/GestorHS
git branch --show-current          # confirme que está em main
git checkout -b feat/pos-vendas-edita-cadastros
```

- [ ] **Step 2: Registrar o baseline**

```bash
cd backend && source .venv/bin/activate && pytest -q 2>&1 | tail -3
cd ../frontend && npm test 2>&1 | tail -5
```

Esperado: backend `4 failed`, frontend `1 failed`.

---

### Task 1: `EDITOR_CADASTRO` no backend

**Files:**
- Modify: `backend/app/api/deps.py` (por volta da linha 89-95)
- Modify: `backend/app/api/clientes.py` (a função `atualizar`, linha 57)
- Modify: `backend/app/api/equipamentos_cliente.py` (a função `atualizar`, linha 181)
- Test: `backend/tests/test_frota_escrita.py` (acrescenta casos)
- Test: `backend/tests/test_clientes.py` (acrescenta casos)

**Interfaces:**
- Produces: `app.api.deps.EDITOR_CADASTRO` — tupla de nomes de função autorizados a **editar** cadastro. Consumida pelos dois routers. `GESTOR_CADASTRO` continua existindo, inalterada, para criar/transferir.

**Contexto dos testes:** os dois arquivos já têm o helper `_headers(client, email, senha)`. `test_frota_escrita.py` também tem `_base(db_session)`, que devolve `(cliente_id, equipamento_id)`. A fixture `usuario_comercial` já existe em `conftest.py:173` — email **`comercial@hs.com`**, senha `senha123`.

- [ ] **Step 1: Escrever os testes que falham**

Acrescente ao fim de `backend/tests/test_frota_escrita.py`:

```python
def test_pos_vendas_edita_aparelho_mas_nao_cria_nem_transfere(client, usuario_admin, usuario_comercial, db_session):
    """Pos-Vendas corrige cadastro (inclusive o ativo), mas nao cadastra do zero
    nem move aparelho entre clientes."""
    from app.models import Cliente
    cid, eid = _base(db_session)
    adm = _headers(client, "admin@hs.com", "senha123")
    criado = client.post("/equipamentos-cliente", json={"cliente": cid, "equipamento": eid}, headers=adm)
    assert criado.status_code == 201
    iid = criado.json()["id"]

    pv = _headers(client, "comercial@hs.com", "senha123")
    # EDITAR: pode
    r = client.patch(f"/equipamentos-cliente/{iid}", json={"ativo": False}, headers=pv)
    assert r.status_code == 200
    assert r.json()["ativo"] is False
    # CRIAR: nao pode
    assert client.post("/equipamentos-cliente", json={"cliente": cid, "equipamento": eid},
                       headers=pv).status_code == 403
    # TRANSFERIR: nao pode
    outro = Cliente(nome="Destino")
    db_session.add(outro); db_session.commit()
    assert client.post(f"/equipamentos-cliente/{iid}/transferir", json={"cliente": outro.id},
                       headers=pv).status_code == 403
    # EXCLUIR: continua so do Admin
    assert client.delete(f"/equipamentos-cliente/{iid}", headers=pv).status_code == 403
```

E acrescente ao fim de `backend/tests/test_clientes.py`:

```python
def test_pos_vendas_edita_cliente_mas_nao_cria(client, usuario_admin, usuario_comercial):
    """Pos-Vendas corrige endereco e demais dados do cliente, mas nao cadastra cliente novo."""
    adm = _headers(client, "admin@hs.com", "senha123")
    criado = client.post("/clientes", json={"nome": "ACME"}, headers=adm)
    assert criado.status_code == 201
    cid = criado.json()["id"]

    pv = _headers(client, "comercial@hs.com", "senha123")
    r = client.patch(f"/clientes/{cid}", json={"endereco": "Rua Nova", "municipio": "Campinas"}, headers=pv)
    assert r.status_code == 200
    assert r.json()["endereco"] == "Rua Nova"
    assert client.post("/clientes", json={"nome": "Outro"}, headers=pv).status_code == 403
    assert client.delete(f"/clientes/{cid}", headers=pv).status_code == 403


def test_gestores_continuam_editando_cliente(client, usuario_admin, usuario_comum):
    """Controle: quem ja editava (Expedicao) nao perdeu nada com a separacao das tuplas."""
    adm = _headers(client, "admin@hs.com", "senha123")
    cid = client.post("/clientes", json={"nome": "ACME 2"}, headers=adm).json()["id"]
    exp = _headers(client, "comum@hs.com", "senha123")
    assert client.patch(f"/clientes/{cid}", json={"bairro": "Centro"}, headers=exp).status_code == 200
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_frota_escrita.py tests/test_clientes.py -q`
Expected: FAIL — o `PATCH` do Pós-Vendas devolve 403 nos dois casos novos, porque hoje só `GESTOR_CADASTRO` edita.

- [ ] **Step 3: Criar a tupla nova**

Em `backend/app/api/deps.py`, logo depois da definição de `GESTOR_CADASTRO`, acrescente:

```python
# Quem pode ALTERAR cadastro ja existente — os gestores acima MAIS o Comercial
# Pos-Vendas, que precisa corrigir endereco/dados do cliente e marcar aparelho
# como inativo. Derivada de GESTOR_CADASTRO de proposito: as duas nao podem
# divergir quando alguem mexer na primeira.
# CRIAR e TRANSFERIR seguem em GESTOR_CADASTRO; EXCLUIR segue so com ADMIN.
EDITOR_CADASTRO = GESTOR_CADASTRO + ("Comercial Pós-Vendas",)
```

E atualize o comentário de `GESTOR_CADASTRO` acima dela, que hoje diz "CADASTRAR, ALTERAR e TRANSFERIR", para refletir que o ALTERAR saiu:

```python
# Quem pode CADASTRAR e TRANSFERIR clientes e aparelhos da frota.
# Fonte unica: usada pelos routers de clientes e de equipamentos_cliente.
# Expedicao entra porque da entrada de modulos novos no estoque (cadastro de aparelhos).
# ALTERAR e mais amplo — ver EDITOR_CADASTRO abaixo.
# EXCLUIR continua so com Administrador — e a unica acao destrutiva de verdade.
GESTOR_CADASTRO = (ADMIN, "Laboratório", "Expedição")
```

- [ ] **Step 4: Usar a tupla nova nos dois `atualizar`**

Em `backend/app/api/clientes.py`, acrescente `EDITOR_CADASTRO` ao import da linha 9:

```python
from app.api.deps import get_current_usuario, require_funcao, GESTOR_CADASTRO, EDITOR_CADASTRO
```

E troque a dependência da função `atualizar` (linha 57), deixando `criar` e `excluir` como estão:

```python
def atualizar(cliente_id: int, dados: ClienteUpdate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(*EDITOR_CADASTRO))):
```

Em `backend/app/api/equipamentos_cliente.py`, acrescente `EDITOR_CADASTRO` ao import da linha 9:

```python
from app.api.deps import get_current_usuario, require_funcao, GESTOR_CADASTRO, EDITOR_CADASTRO
```

E troque a dependência da função `atualizar` (linha 181), deixando `criar`, `excluir` e `transferir` como estão:

```python
def atualizar(item_id: int, dados: EquipamentoClienteUpdate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(*EDITOR_CADASTRO))):
```

- [ ] **Step 5: Rodar e confirmar que passam**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_frota_escrita.py tests/test_clientes.py tests/test_frota_leitura.py tests/test_frota_transferencia.py -q`
Expected: PASS

- [ ] **Step 6: Conferir que nada mais mudou de permissão**

Run: `cd backend && grep -rn "GESTOR_CADASTRO\|EDITOR_CADASTRO" app/`
Expected: `EDITOR_CADASTRO` aparece só na definição em `deps.py` e nos dois `atualizar`. `GESTOR_CADASTRO` continua nos dois `criar` e no `transferir`.

- [ ] **Step 7: Commit**

```bash
cd /home/ericks/github/GestorHS
git branch --show-current
git add backend/app/api/deps.py backend/app/api/clientes.py backend/app/api/equipamentos_cliente.py backend/tests/test_frota_escrita.py backend/tests/test_clientes.py
git commit -m "feat(acesso): pos-vendas pode editar cadastro de cliente e aparelho"
```

---

### Task 2: `podeEditarCadastros` no frontend

**Files:**
- Modify: `frontend/src/auth/roles.ts`
- Modify: `frontend/src/app/clientes/ClienteDadosTab.tsx` (linha 16)
- Modify: `frontend/src/app/frota/EquipamentoClienteDetailPage.tsx` (linha 60)
- Test: `frontend/src/auth/roles.cadastros.test.ts` (acrescenta um `describe`; o arquivo **já existe** e é dedicado a esta permissão)

**Interfaces:**
- Consumes: a regra do backend da Task 1.
- Produces: `podeEditarCadastros(user: User | null): boolean` em `auth/roles.ts`.

**Não mexer:** `ClientesPage.tsx:60`, `ClienteEquipamentosTab.tsx:41`, `FrotaPage.tsx:81`, `EquipamentoClienteDetailPage.tsx:240` e `ClienteDetailPage.tsx:22` continuam com `podeGerenciarCadastros` — são criar e transferir. **`ClienteDetailPage` é a tela de criação de cliente** (rota `clientes/novo`), não a de edição.

- [ ] **Step 1: Escrever o teste que falha**

O arquivo `frontend/src/auth/roles.cadastros.test.ts` **já existe** e já testa `podeGerenciarCadastros` (inclusive afirmando que Comercial Pós-Vendas é bloqueado — o que **continua verdade** para gerenciar). Acrescente `podeEditarCadastros` ao import do topo e um `describe` novo ao fim do arquivo:

```ts
describe('podeEditarCadastros (alterar cadastro existente)', () => {
  it('libera o Comercial Pos-Vendas, que gerenciar nao libera', () => {
    expect(podeEditarCadastros(u('Comercial Pós-Vendas'))).toBe(true)
    expect(podeGerenciarCadastros(u('Comercial Pós-Vendas'))).toBe(false)
  })

  it('quem gerencia tambem edita', () => {
    for (const f of ['Administrador', 'Laboratório', 'Expedição']) {
      expect(podeGerenciarCadastros(u(f))).toBe(true)
      expect(podeEditarCadastros(u(f))).toBe(true)
    }
  })

  it('bloqueia as demais funcoes e usuario sem sessao', () => {
    for (const f of ['Financeiro', 'Suporte', 'Qualidade']) {
      expect(podeEditarCadastros(u(f))).toBe(false)
    }
    expect(podeEditarCadastros(null)).toBe(false)
  })
})
```

O import do topo passa a ser:

```ts
import { isAdmin, podeGerenciarCadastros, podeEditarCadastros } from './roles'
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd frontend && npx vitest run src/auth/roles.cadastros.test.ts`
Expected: FAIL — `podeEditarCadastros` não existe ainda (erro de import).

- [ ] **Step 3: Criar o helper**

Em `frontend/src/auth/roles.ts`, logo depois de `podeGerenciarCadastros`, acrescente:

```ts
// Alterar cadastro JA EXISTENTE: os gestores acima mais o Comercial Pós-Vendas,
// que precisa corrigir endereço/dados do cliente e marcar aparelho como inativo.
// Criar e transferir continuam em podeGerenciarCadastros; excluir segue só com isAdmin().
// Espelha EDITOR_CADASTRO em backend/app/api/deps.py — mudou lá, mude aqui.
export function podeEditarCadastros(user: User | null): boolean {
  return podeGerenciarCadastros(user) || user?.funcao === FUNCAO_COMERCIAL
}
```

- [ ] **Step 4: Usar o helper nas duas telas de edição**

Em `frontend/src/app/clientes/ClienteDadosTab.tsx`, troque o import da linha 4 e a linha 16:

```tsx
import { isAdmin, podeEditarCadastros } from '../../auth/roles'
```

```tsx
  const podeEditar = podeEditarCadastros(user)
```

Em `frontend/src/app/frota/EquipamentoClienteDetailPage.tsx`, acrescente `podeEditarCadastros` ao import da linha 11 (mantendo `podeGerenciarCadastros`, que a linha 240 ainda usa para o botão Transferir):

```tsx
import { isAdmin, podeAbrirOS, podeEditarCadastros, podeGerenciarCadastros, podeGerarCertificadoVenda } from '../../auth/roles'
```

E troque a linha 60. Note que `editando` é declarado na linha 59, logo acima — a ordem já funciona:

```tsx
  const podeEditar = editando ? podeEditarCadastros(user) : podeGerenciarCadastros(user)
```

- [ ] **Step 5: Rodar e confirmar que passa**

Run: `cd frontend && npx vitest run src/auth/ src/app/frota/ src/app/clientes/`
Expected: os testes novos PASSAM. Continua **1 falha** — a pré-existente `ClienteEquipamentosTab.test.tsx > esconde "Novo aparelho" para não-admin`, que a Task 4 vai corrigir. Qualquer outra falha é regressão.

- [ ] **Step 6: Verificação de tipos e build**

Run: `cd frontend && npm run lint && npx tsc -b --noEmit && npm run build`
Expected: sem erro.

- [ ] **Step 7: Commit**

```bash
cd /home/ericks/github/GestorHS
git branch --show-current
git add frontend/src/auth/roles.ts frontend/src/auth/roles.test.ts frontend/src/app/clientes/ClienteDadosTab.tsx frontend/src/app/frota/EquipamentoClienteDetailPage.tsx
git commit -m "feat(acesso): pos-vendas edita cadastro tambem na interface"
```

---

### Task 3: `Toggle` com `disabled` e o controle de Ativo

**Files:**
- Modify: `frontend/src/components/ui/Toggle.tsx`
- Modify: `frontend/src/app/frota/EquipamentoClienteDetailPage.tsx` (o bloco do checkbox, linhas 196-202)
- Test: `frontend/src/components/ui/Toggle.test.tsx` (**novo**)
- Test: `frontend/src/app/frota/EquipamentoClienteDetailPage.ativo.test.tsx` (acrescenta casos)

**Interfaces:**
- Consumes: `podeEditarCadastros` da Task 2 (a tela já a usa via `podeEditar`/`ro`).
- Produces: `Toggle` aceita `disabled?: boolean` (default `false`).

**O componente hoje** (`frontend/src/components/ui/Toggle.tsx`) recebe `{ checked, onChange, label }`, renderiza um `<button role="switch">` e é usado por `MainLayout`, `Topbar`, `CaixasPage` e `UsuariosPage` — todas sem `disabled`, e que não podem mudar de comportamento.

- [ ] **Step 1: Escrever os testes que falham**

Crie `frontend/src/components/ui/Toggle.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Toggle } from './Toggle'

describe('Toggle', () => {
  it('dispara onChange com o valor invertido', async () => {
    const onChange = vi.fn()
    render(<Toggle checked={false} onChange={onChange} label="Ativo" />)
    await userEvent.click(screen.getByRole('switch'))
    expect(onChange).toHaveBeenCalledWith(true)
  })

  it('desabilitado nao dispara onChange', async () => {
    const onChange = vi.fn()
    render(<Toggle checked={false} onChange={onChange} label="Ativo" disabled />)
    const sw = screen.getByRole('switch')
    expect(sw).toBeDisabled()
    await userEvent.click(sw)
    expect(onChange).not.toHaveBeenCalled()
  })

  it('sem a prop disabled continua habilitado (default das telas que ja usam)', () => {
    render(<Toggle checked onChange={() => {}} label="Ativo" />)
    expect(screen.getByRole('switch')).not.toBeDisabled()
  })
})
```

E acrescente ao fim do `describe` em `frontend/src/app/frota/EquipamentoClienteDetailPage.ativo.test.tsx`:

```tsx
  it('mostra o estado por extenso ao lado do interruptor', async () => {
    obter.mockResolvedValue({ ...APARELHO, ativo: true })
    editar()
    expect(await screen.findByRole('switch')).toBeInTheDocument()
    expect(screen.getByText('Ativo')).toBeInTheDocument()
  })

  it('mostra Inativo quando o aparelho esta desativado', async () => {
    obter.mockResolvedValue({ ...APARELHO, ativo: false })
    editar()
    expect(await screen.findByText('Inativo')).toBeInTheDocument()
  })
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `cd frontend && npx vitest run src/components/ui/Toggle.test.tsx src/app/frota/EquipamentoClienteDetailPage.ativo.test.tsx`
Expected: FAIL — `Toggle` ignora `disabled`, e a tela ainda tem um checkbox (não há `role="switch"`).

- [ ] **Step 3: Adicionar `disabled` ao componente**

Substitua o conteúdo de `frontend/src/components/ui/Toggle.tsx` por:

```tsx
import { cn } from '../../lib/utils'

interface ToggleProps {
  checked: boolean
  onChange: (next: boolean) => void
  label?: string
  disabled?: boolean
}

export function Toggle({ checked, onChange, label, disabled = false }: ToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        'relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full p-0 transition-colors',
        checked ? 'bg-primary' : 'bg-slate-200 dark:bg-border',
        disabled && 'opacity-50 cursor-not-allowed',
      )}
    >
      <span
        className={cn(
          'inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform',
          checked ? 'translate-x-6' : 'translate-x-1',
        )}
      />
    </button>
  )
}
```

- [ ] **Step 4: Trocar o checkbox pelo interruptor**

Em `frontend/src/app/frota/EquipamentoClienteDetailPage.tsx`, importe o componente junto dos outros de UI:

```tsx
import { Toggle } from '../../components/ui/Toggle'
```

E substitua o `<label htmlFor="ec-ativo">…</label>` inteiro (o bloco do checkbox, dentro do grid do "Módulo") por:

```tsx
          <div className="flex items-center gap-3 text-sm text-slate-300 sm:self-end sm:pb-2">
            <Toggle checked={form.ativo} onChange={(v) => set('ativo', v)} label="Ativo" disabled={ro} />
            <span>{form.ativo ? 'Ativo' : 'Inativo'}</span>
          </div>
```

- [ ] **Step 5: Rodar e confirmar que passam**

Run: `cd frontend && npx vitest run src/components/ui/ src/app/frota/`
Expected: PASS.

**Sobre os dois testes que já existem em `EquipamentoClienteDetailPage.ativo.test.tsx`:** eles usam `findByLabelText('Ativo')` (linhas 45 e 54) e clicam no elemento. Isso **continua funcionando** com o interruptor, porque o `Toggle` põe `aria-label="Ativo"` no `<button role="switch">` e o clique dispara o `onChange`. Se mesmo assim algum falhar, ajuste-o para `getByRole('switch')` e registre o desvio no relatório — não mude a implementação para acomodar o teste.

**Atenção a uma ambiguidade que você mesmo cria:** depois da mudança existem dois elementos contendo "Ativo" — o botão (via `aria-label`) e o `<span>` do estado. `getByLabelText('Ativo')` pega o botão e `getByText('Ativo')` pega o span, então as duas consultas continuam sem ambiguidade. Se precisar escopar, use `getByRole('switch')` para o controle.

- [ ] **Step 6: Conferir que as outras 4 telas não mudaram**

Run: `cd frontend && npx vitest run src/app/caixas/ src/app/acesso/ && npm run lint && npx tsc -b --noEmit && npm run build`
Expected: sem erro — `disabled` é opcional e nasce `false`.

- [ ] **Step 7: Commit**

```bash
cd /home/ericks/github/GestorHS
git branch --show-current
git add frontend/src/components/ui/Toggle.tsx frontend/src/components/ui/Toggle.test.tsx frontend/src/app/frota/EquipamentoClienteDetailPage.tsx frontend/src/app/frota/EquipamentoClienteDetailPage.ativo.test.tsx
git commit -m "feat(ui): controle de ativo do aparelho vira interruptor com estado"
```

---

### Task 4: Corrigir o teste desatualizado de permissão

**Files:**
- Modify: `frontend/src/app/clientes/ClienteEquipamentosTab.test.tsx` (o teste `esconde "Novo aparelho" para não-admin`)

**O problema:** esse teste **falha desde antes desta entrega**. Ele usa `funcao: 'Expedição'` e espera que o botão "Novo aparelho" fique escondido — mas a regra permite Expedição **de propósito**, documentado em `backend/app/api/deps.py`: *"Expedicao entra porque da entrada de modulos novos no estoque"*. O teste é que está desatualizado em relação à regra; a regra não muda.

- [ ] **Step 1: Reescrever o teste para afirmar a regra real**

Em `frontend/src/app/clientes/ClienteEquipamentosTab.test.tsx`, substitua o teste `esconde "Novo aparelho" para não-admin` por estes dois:

```tsx
  it('mostra "Novo aparelho" para Expedição, que cadastra aparelho', async () => {
    mockUser = { funcao: 'Expedição' }
    listar.mockResolvedValue({ items: [], total: 0 })
    renderTab()
    await screen.findByText(/Nenhum aparelho/i)
    expect(screen.getByText('Novo aparelho')).toBeInTheDocument()
  })

  it('esconde "Novo aparelho" para quem nao gerencia cadastro', async () => {
    mockUser = { funcao: 'Financeiro' }
    listar.mockResolvedValue({ items: [], total: 0 })
    renderTab()
    await screen.findByText(/Nenhum aparelho/i)
    expect(screen.queryByText('Novo aparelho')).toBeNull()
  })
```

- [ ] **Step 2: Rodar e confirmar que passam**

Run: `cd frontend && npx vitest run src/app/clientes/ClienteEquipamentosTab.test.tsx`
Expected: **PASS, com 0 falhas** — é a primeira vez que este arquivo fecha limpo.

- [ ] **Step 3: Confirmar que Pós-Vendas também não vê o botão**

O Comercial Pós-Vendas ganhou o direito de **editar**, não de criar. Acrescente um terceiro caso, logo depois dos dois acima:

```tsx
  it('esconde "Novo aparelho" para Pós-Vendas, que so edita', async () => {
    mockUser = { funcao: 'Comercial Pós-Vendas' }
    listar.mockResolvedValue({ items: [], total: 0 })
    renderTab()
    await screen.findByText(/Nenhum aparelho/i)
    expect(screen.queryByText('Novo aparelho')).toBeNull()
  })
```

Run: `cd frontend && npx vitest run src/app/clientes/ClienteEquipamentosTab.test.tsx`
Expected: PASS (3 testes de permissão + os 2 de listagem + os 2 do selo de inativo).

- [ ] **Step 4: Commit**

```bash
cd /home/ericks/github/GestorHS
git branch --show-current
git add frontend/src/app/clientes/ClienteEquipamentosTab.test.tsx
git commit -m "test(clientes): alinha teste do botao novo aparelho com a regra real"
```

---

### Task 5: Changelog e verificação final

**Files:**
- Modify: `frontend/src/app/changelog/data.ts` (nova entrada no topo)

- [ ] **Step 1: Rodar a suíte inteira do backend**

Run: `cd backend && source .venv/bin/activate && pytest -q 2>&1 | tail -5`
Expected: `4 failed` (as pré-existentes) e nenhuma falha nova.

- [ ] **Step 2: Rodar a suíte inteira do frontend**

Run: `cd frontend && npm test 2>&1 | tail -8`
Expected: **0 failed.** A única falha que existia foi corrigida na Task 4. Se sobrar alguma, é regressão — pare e reporte.

- [ ] **Step 3: Adicionar a entrada no changelog**

Em `frontend/src/app/changelog/data.ts`, como **primeira** entrada de `CHANGELOG`:

```ts
  {
    versao: '1.35.0',
    data: '31/07/2026',
    itens: [
      { tipo: 'novidade', texto: 'O time de Pós-Vendas agora pode corrigir os dados de um cliente (endereço, contato e o resto do cadastro) e editar um aparelho, inclusive marcá-lo como ativo ou inativo. Criar cliente ou aparelho novo e transferir aparelho entre clientes continuam com Administração, Laboratório e Expedição.' },
      { tipo: 'melhoria', texto: 'O controle de ativo do aparelho virou um interruptor, com o estado escrito ao lado — "Ativo" ou "Inativo" — no lugar da antiga caixinha de marcar.' },
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
git commit -m "docs(changelog): v1.35.0 — pos-vendas edita cadastros e ativo vira interruptor"
```

- [ ] **Step 6: Resumo para o Erick**

Não faça push nem merge. Reporte: falhas antes/depois nas duas suítes (destacando que o frontend passou de 1 para 0), arquivos tocados, e confirmação de que `POST` e transferência continuam negando Pós-Vendas.

---

## Notas de execução

- **Ordem:** Task 1 → Task 2 (o frontend espelha a regra do backend). As Tasks 3 e 4 são independentes das anteriores, mas a 3 mexe no mesmo arquivo da 2 (`EquipamentoClienteDetailPage.tsx`), então rode-a depois.
- **A armadilha desta entrega é dar poder demais.** Toda vez que tocar num `require_funcao`, confira se é o `atualizar` — `criar`, `transferir` e `excluir` não mudam. O Step 6 da Task 1 existe para isso.
- **Nome da função com acento:** `"Comercial Pós-Vendas"` é o valor no banco e nos dois lados do código. Digitar sem acento faz a permissão simplesmente não valer, sem erro nenhum.
