# Equipamentos como aba na página do cliente — Design

**Data:** 2026-07-15
**Área:** frontend (`app/clientes`, `app/frota`, rotas)

## Problema

Hoje, na tela de detalhe do cliente, o botão **Equipamentos** faz
`navigate('/app/equipamentos?cliente=:id')` — ou seja, **sai** da página do cliente e leva
para a lista global de equipamentos filtrada por aquele cliente. Para voltar ao cliente, o
usuário depende do link "limpar" ou do voltar do navegador, perdendo o contexto. A equipe
relatou que esse vai-e-vem entre "dados do cliente" e "equipamentos do cliente" ficou
complicado.

## Objetivo

Transformar a página do cliente num container com abas **Dados | Equipamentos**, permitindo
transitar entre os dados do cliente, a lista de equipamentos dele e o detalhe de um aparelho
**sem sair da página**, reaproveitando a tela de detalhe de aparelho que já existe (com OS,
transferência, certificados etc.).

## Não-objetivos

- Não mexer na página global **Equipamentos** (`/app/equipamentos`) do menu lateral — ela
  continua listando todos os aparelhos.
- Não duplicar a tela de detalhe de aparelho. Ela é reusada, não copiada.
- Não adicionar busca/filtro/paginação na lista dentro da aba (decisão: lista simples).

## Arquitetura (Abordagem A — rotas aninhadas reusando a tela de detalhe)

A rota `clientes/:id` deixa de ser folha e passa a ser um **layout com abas**. O endereço
reflete onde o usuário está (favoritável, voltar do navegador funciona):

```
clientes/novo                 → ClienteDetailPage (novo; SEM abas — não há equipamentos ainda)
clientes/:id                  → ClienteLayout (título do cliente + abas [Dados|Equipamentos] + <Outlet/>)
   ├─ (index)                 → ClienteDadosTab        (o formulário do cliente de hoje)
   ├─ equipamentos            → ClienteEquipamentosTab (lista simples só daquele cliente)
   ├─ equipamentos/novo       → EquipamentoClienteDetailPage (reusada, modo embutido)
   └─ equipamentos/:aparelho  → EquipamentoClienteDetailPage (reusada, modo embutido)
```

### Componentes

- **`ClienteLayout`** (novo) — busca o cliente uma vez (para o título e para alimentar a aba
  Dados via `useOutletContext`), renderiza o cabeçalho (nome + botões Excluir/Voltar), a barra
  de abas e um `<Outlet/>`. As abas são `NavLink`s para `.` (Dados) e `equipamentos`.
- **`ClienteDadosTab`** (extraído do atual `ClienteDetailPage`) — o formulário do cliente.
  Recebe o cliente já carregado via `useOutletContext` (evita segunda busca). Mantém salvar /
  permissões / seções Funcionários e Usuários do portal (aside) como hoje.
- **`ClienteEquipamentosTab`** (novo) — lista simples dos aparelhos do cliente
  (`equipamentosClienteApi.listar({ cliente })`): colunas **Aparelho · Série/Patrimônio ·
  Próxima calibração · Status** (badge colorido, reusando `STATUS_CALIBRACAO`). Botão **Novo
  aparelho** (admin) → `equipamentos/novo`. Clique na linha → `equipamentos/:aparelho`.
- **`EquipamentoClienteDetailPage`** (adaptada) — ganha um modo "embutido" acionado quando
  aberta sob a rota do cliente. No modo embutido: "Voltar" vai para
  `/app/clientes/:id/equipamentos` (a aba), e o "Novo aparelho" pega o cliente do **path**
  (`:id`) em vez de `?cliente=`. Fora do cliente (rotas globais) o comportamento é o de hoje.

### Colisão de parâmetros de rota

A tela de detalhe hoje lê o id do aparelho de `useParams().id`. Sob a rota aninhada,
`:id` é o **cliente**. Para não colidir, a rota aninhada do aparelho usa `:aparelho`:

- Global: `equipamentos/:id` → aparelho = `params.id`, cliente = `?cliente=` (query).
- Aninhada: `clientes/:id/equipamentos/:aparelho` → cliente = `params.id`, aparelho = `params.aparelho`.

O modo embutido é passado **explicitamente via prop** no `element` da rota
(`<EquipamentoClienteDetailPage embutido />`), o que torna a intenção óbvia e dispensa
adivinhação. Com isso a resolução é sem ambiguidade:

- `embutido`: aparelho = `params.aparelho` (na rota `.../novo` é `undefined` → `editando=false`);
  cliente = `params.id`.
- global (hoje): aparelho = `params.id`; cliente = `?cliente=` (query).

Ou seja, **qual param carrega o aparelho depende do modo** — nunca um fallback de um para o
outro, para não confundir o id do cliente com o do aparelho na rota `.../novo`.

### Fluxo de dados

- `ClienteLayout` busca o cliente (`clientesApi.obter`) uma vez; passa via contexto do Outlet.
- `ClienteDadosTab` consome o cliente do contexto; ainda faz `atualizar` no salvar.
- `ClienteEquipamentosTab` busca a lista do cliente ao montar.
- Detalhe do aparelho busca o próprio aparelho + histórico/OS/certificados/transferências, igual hoje.

### Navegação e "breadcrumb"

Nos três níveis, o cabeçalho do cliente e as abas ficam fixos (fazem parte do `ClienteLayout`).
No detalhe do aparelho, a aba **Equipamentos** permanece ativa e um caminho
`‹Cliente› › Equipamentos › ‹Aparelho›` aparece; clicar em "Equipamentos" volta para a lista.

## Tratamento de erros e permissões

- Sem mudança de regra: **Novo aparelho**, **Excluir**, **Transferir** seguem `isAdmin`;
  **Abrir OS** segue `podeAbrirOS`. Edição de campos permanece read-only para não-admin.
- Erros de carregamento reusam o box de erro vermelho existente.
- Cliente inexistente (`404` em `clientesApi.obter`) → mensagem de erro no layout, sem abas.

## Testes

- **`ClienteEquipamentosTab`**: renderiza a lista do cliente; mostra "Nenhum aparelho" quando
  vazio; botão "Novo aparelho" só para admin; clicar numa linha navega para
  `equipamentos/:aparelho`.
- **Rotas do cliente**: `/app/clientes/:id` mostra a aba Dados (form); `.../equipamentos`
  mostra a lista; a aba ativa acompanha a URL.
- **Modo embutido do detalhe**: sob o cliente, "Voltar" aponta para
  `/app/clientes/:id/equipamentos`; fora do cliente, para `/app/equipamentos` (regressão).
- Reaproveitar mocks de `frota/api.test.ts` e o padrão de render com `MemoryRouter`.

## Riscos

- **Refator do `ClienteDetailPage`**: extrair o formulário para `ClienteDadosTab` sem regredir
  salvar/permissões/aside. Mitigado por manter o form idêntico, só mudando de onde vem o cliente.
- **Duplo contexto da tela de detalhe** (global vs. embutido): mitigado pela prop explícita
  `embutido` e pela resolução única de `aparelhoId`/`clienteId`.
