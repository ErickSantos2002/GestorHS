# Pós-Vendas edita cadastros + controle de Ativo mais bonito — Design

**Data:** 2026-07-31
**Área:** backend (`api/deps.py`, `api/clientes.py`, `api/equipamentos_cliente.py`) + frontend (`auth/roles.ts`, `components/ui/Toggle.tsx`, telas de cliente e de aparelho) + testes.
**Tipo:** mudança de autorização + melhoria de UI. Sem migração.

## Problema

Duas coisas, que se resolvem no mesmo lugar:

1. **O controle de ativo do aparelho é um checkbox cru.** Depois que a v1.33.1 removeu o campo "Situação" duplicado, sobrou um `<input type="checkbox">` com o rótulo "Ativo" — funcional, mas destoante do resto do sistema, que já tem um componente `Toggle` (interruptor) usado em Usuários, Caixas e no layout.

2. **Pós-Vendas não consegue corrigir cadastro.** Quando o endereço de um cliente está errado, ou um aparelho precisa ser marcado como inativo, o time de Comercial Pós-Vendas depende de outra pessoa. Hoje só Admin, Laboratório e Expedição podem.

O nó é que a permissão de editar não existe separada: uma tupla única gateia **criar, editar e transferir** de uma vez.

```python
# backend/app/api/deps.py:95 — fonte única, usada pelos routers de clientes e de equipamentos
GESTOR_CADASTRO = (ADMIN, "Laboratório", "Expedição")
```

Adicionar Pós-Vendas ali resolveria os dois pedidos com uma linha, mas entregaria junto **criar cadastro do zero** e **transferir aparelho entre clientes** — poder que ninguém pediu, sendo a transferência uma ação com consequência real na frota.

## Design

### 1. Separar "gerenciar" de "editar"

`deps.py` passa a ter duas tuplas:

| tupla | quem | o que gateia |
|---|---|---|
| `GESTOR_CADASTRO` (existente) | Admin, Laboratório, Expedição | **criar** cliente/aparelho, **transferir** aparelho |
| `EDITOR_CADASTRO` (novo) | os três acima **+ `"Comercial Pós-Vendas"`** | **editar** cliente e aparelho |

`EDITOR_CADASTRO` é derivada de `GESTOR_CADASTRO` (`GESTOR_CADASTRO + ("Comercial Pós-Vendas",)`), para as duas não divergirem quando alguém mexer numa delas.

**Backend:**

| endpoint | antes | depois |
|---|---|---|
| `PATCH /clientes/{id}` | `GESTOR_CADASTRO` | **`EDITOR_CADASTRO`** |
| `PATCH /equipamentos-cliente/{id}` | `GESTOR_CADASTRO` | **`EDITOR_CADASTRO`** |
| `POST /clientes` | `GESTOR_CADASTRO` | inalterado |
| `POST /equipamentos-cliente` | `GESTOR_CADASTRO` | inalterado |
| transferência de aparelho | `GESTOR_CADASTRO` | inalterado |
| `DELETE` (ambos) | `ADMIN` | inalterado |

**Frontend:** `auth/roles.ts` ganha `podeEditarCadastros`, espelhando `EDITOR_CADASTRO`. Os 8 pontos que hoje chamam `podeGerenciarCadastros` se dividem:

- **Continuam com `podeGerenciarCadastros`** (criar e transferir): `ClientesPage.tsx:60` ("Novo cliente"), `ClienteEquipamentosTab.tsx:41` ("Novo aparelho"), `FrotaPage.tsx:81` ("Novo aparelho"), `EquipamentoClienteDetailPage.tsx:240` ("Transferir"), e **`ClienteDetailPage.tsx:22`** — ver abaixo.
- **Passam a `podeEditarCadastros`** (habilitar formulário de edição): `ClienteDadosTab.tsx:16` e `EquipamentoClienteDetailPage.tsx:60`.

### 2. Cliente e aparelho não são simétricos

As duas telas de cliente **não** são a mesma coisa:

- `ClienteDetailPage` é **só criação** — rota `clientes/novo`, e seu `salvar` chama apenas `clientesApi.criar`. Portanto ela **continua** com `podeGerenciarCadastros`; Pós-Vendas não cria cliente.
- `ClienteDadosTab` é a aba de **edição** do cliente existente (dentro de `clientes/:id`). É ela que passa a `podeEditarCadastros`.

Já `EquipamentoClienteDetailPage` serve **aos dois modos** (`const editando = aparelhoId !== undefined`, linha 59). Trocar seu flag por `podeEditarCadastros` sem mais nada deixaria o Pós-Vendas abrir `/equipamentos/novo` pela URL, preencher o formulário inteiro e só tomar 403 ao salvar. Nela o flag passa a ser:

```tsx
const podeEditar = editando ? podeEditarCadastros(user) : podeGerenciarCadastros(user)
```

O backend continua sendo o gate real (o `POST` recusa de qualquer jeito); isto evita o beco sem saída na interface.

### 3. O controle de Ativo

Na tela do aparelho, o `<input type="checkbox">` dá lugar ao componente `Toggle` da casa, com o **texto do estado ao lado** — "Ativo" quando ligado, "Inativo" quando desligado. O rótulo passa a dizer o estado atual em vez de só nomear o campo. Fica na mesma posição de hoje, na segunda coluna da linha do "Módulo".

**O `Toggle` não aceita `disabled` hoje.** A tela desabilita todos os campos para quem não pode editar, e o checkbox atual respeita isso; o `Toggle`, não. Então `components/ui/Toggle.tsx` ganha uma prop `disabled?: boolean` (default `false`), que passa `disabled` para o `<button>` e acrescenta `opacity-50 cursor-not-allowed` às classes quando ligada. O default preserva o comportamento nas 4 telas que já usam o componente.

### 4. O teste vermelho no caminho

`ClienteEquipamentosTab.test.tsx > esconde "Novo aparelho" para não-admin` **falha desde antes desta entrega** e testa exatamente a função que estamos dividindo. Ele afirma que **Expedição** não vê o botão "Novo aparelho", mas a regra permite Expedição **de propósito** — documentado em [deps.py:93](../../../backend/app/api/deps.py): *"Expedicao entra porque da entrada de modulos novos no estoque"*. O teste é que está desatualizado em relação à regra.

Ele é corrigido para afirmar a regra real: **Expedição vê** o botão; um papel que de fato não gerencia cadastro (**Financeiro**) não vê. Isso limpa a única falha permanente da suíte do frontend, que hoje atrapalha enxergar regressão de verdade.

Depois desta entrega o baseline do frontend passa a ser **0 falhas**.

## Fora do escopo

- **Pós-Vendas não ganha criar nem transferir** — decisão explícita.
- **Excluir continua exclusivo do Administrador**, nos dois cadastros.
- **Nenhuma migração**, nenhum campo novo.
- **A regra que permite Expedição gerenciar cadastro não muda** — só o teste que a descrevia errado.

## Testes

**Backend** — permissões de aparelho em `tests/test_frota_escrita.py` (que já tem os casos por função) e de cliente em `tests/test_clientes.py`: Comercial Pós-Vendas consegue `PATCH` de cliente e de aparelho (200); **não** consegue `POST` de nenhum dos dois nem transferir (403); Laboratório e Expedição continuam podendo tudo que podiam; `DELETE` continua 403 para todos menos Admin.

A fixture do papel já existe (`usuario_comercial` em `tests/conftest.py:173`, função `"Comercial Pós-Vendas"`) — não é preciso criar.

**Frontend:** `podeEditarCadastros` inclui Comercial Pós-Vendas e `podeGerenciarCadastros` não; na tela do aparelho em modo **edição** o formulário fica habilitado para Pós-Vendas, e em modo **criação** fica desabilitado; a aba de dados do cliente fica editável para Pós-Vendas; o `Toggle` com `disabled` não dispara `onChange` ao ser clicado; o controle mostra "Ativo"/"Inativo" conforme o estado.

**Baseline:** backend 4 falhas pré-existentes (`PermissionError` em `test_certificados_gerais.py` e `test_publico_certificado_geral.py`). Frontend: 1 falha pré-existente que **esta entrega corrige** — ao final, o frontend deve fechar com **0 falhas**.

## Arquivos

Backend: `app/api/deps.py`, `app/api/clientes.py`, `app/api/equipamentos_cliente.py` + testes. Frontend: `src/auth/roles.ts`, `src/components/ui/Toggle.tsx`, `src/app/frota/EquipamentoClienteDetailPage.tsx`, `src/app/clientes/ClienteDetailPage.tsx`, `src/app/clientes/ClienteDadosTab.tsx`, `src/app/clientes/ClienteEquipamentosTab.test.tsx` + testes. Changelog: entrada de release ao fechar.
