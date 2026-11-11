# Função Consulta + Propostas para Expedição — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expedição vê Propostas em leitura; nova função `Consulta` só lê (trava na API) e ganha filtros por modelo + visão por modelo para achar "quem tem Phoebus".

**Architecture:** Trava central em `get_current_usuario` (método ≠ GET → 403 para Consulta). Filtro `equipamento` nos helpers `_query_frota`/`_query_clientes` (listagem e exportação herdam). Endpoint novo de resumo por modelo. Frontend: helpers em `roles.ts`, Sidebar, selects nas páginas.

**Tech Stack:** FastAPI · SQLAlchemy 2 · Alembic · pytest (SQLite) · React 19 · Vitest.

**Spec:** `docs/superpowers/specs/2026-11-11-funcao-consulta-design.md`

## Global Constraints

- Nome da função: `"Consulta"` (constante `FUNCAO_CONSULTA` em `backend/app/api/deps.py` e `frontend/src/auth/roles.ts`).
- Mensagem do 403: `"Função Consulta é somente leitura"`.
- Única exceção de escrita: `POST /auth/trocar-senha`.
- Estoque HS (`settings.CLIENTE_ESTOQUE_HS_ID`) **fora** do resumo por modelo e do filtro de clientes; **dentro** da lista/exportação de Equipamentos.
- Filtro de clientes e resumo contam só `EquipamentoCliente.ativo IS TRUE`.
- Commits: PT-BR sem acento, uma linha, sem trailer de co-autor (CLAUDE.md do repo prevalece).
- Baseline: há falhas pré-existentes no backend (ver memória) — comparar contra a baseline, não contra zero.

## Review Focus

1. Rota de escrita nova criada no futuro sem `require_funcao` → teste de varredura de `app.routes` pega (Task 2).
2. Usuário Consulta com `funcao_id` nulo/função apagada → `funcao_rel` None não pode estourar 500; trava só age se descrição == Consulta (Task 2, teste `test_sem_funcao_nao_quebra`).
3. Cliente com 2 aparelhos do mesmo modelo aparece uma vez no filtro de clientes e conta 1 em `clientes` do resumo (Task 3/4).
4. `?equipamento=` na URL de Clientes/Equipamentos deve aplicar o filtro ao abrir a página pelo link do resumo (Task 6).
5. Rota `/equipamentos-cliente/resumo-por-modelo` declarada antes de `/{id}` — senão 422 (Task 4, o próprio teste HTTP pega).

---

### Task 1: Expedição vê Propostas

**Files:** Modify `frontend/src/auth/roles.ts`, `frontend/src/auth/roles.test.ts`, `frontend/src/layout/Sidebar.tsx:31`, `frontend/src/layout/Sidebar.test.tsx`

**Interfaces:** Produces `podeVerPropostas(user: User | null): boolean` = `podeGerenciarPropostas(user) || user?.funcao === FUNCAO_EXPEDICAO`.

- [ ] Teste em `roles.test.ts`: `podeVerPropostas` true para Administrador, Comercial Pós-Vendas, Financeiro, Expedição; false para Laboratório e null.
- [ ] Teste em `Sidebar.test.tsx`: usuário Expedição vê link "Propostas" e **não** vê "Serviços" nem "Produtos".
- [ ] Rodar `npx vitest run src/auth/roles.test.ts src/layout/Sidebar.test.tsx` → FAIL.
- [ ] Implementar helper; linha Propostas da Sidebar usa `visivel: podeVerPropostas`.
- [ ] Rodar de novo → PASS. Commit `feat(propostas): expedicao ve propostas em modo leitura`.

### Task 2: Função Consulta + trava de escrita na API

**Files:** Create `backend/alembic/versions/0033_funcao_consulta.py`, `backend/tests/test_funcao_consulta.py`; Modify `backend/app/api/deps.py`, `backend/tests/conftest.py`

**Interfaces:** Produces `FUNCAO_CONSULTA = "Consulta"` (deps.py); fixture `client_consulta` (login de `consulta@hs.com`/`senha123`, função Consulta via `_get_or_create_funcao`, depende de `fases_seed`).

- [ ] Fixtures `usuario_consulta` e `client_consulta` em `conftest.py` no padrão de `client_exp`.
- [ ] Testes em `test_funcao_consulta.py`:
  - `test_toda_escrita_recusada`: percorre `app.routes` (`APIRoute`) com métodos ∩ {POST, PUT, PATCH, DELETE}, cujo `dependant` (recursivo em `.dependencies`) contém `get_current_usuario`, excluindo `/auth/trocar-senha`; troca `{param}` do path por `1`, envia `json={}`; assert `status_code == 403` e `detail == "Função Consulta é somente leitura"` para cada uma (acumular falhas e mostrar a lista).
  - `test_leituras_liberadas`: `GET /clientes`, `/empresas`, `/equipamentos-cliente`, `/equipamentos`, `/produtos`, `/propostas` → 200.
  - `test_trocar_senha_liberado`: `POST /auth/trocar-senha` com senha atual correta → 204.
  - `test_outras_funcoes_intactas`: `client_exp` faz `POST` que já fazia antes (ex.: criar cliente) → não 403.
  - `test_sem_funcao_nao_quebra`: usuário com `funcao_id=None` em `GET /clientes` → 200.
- [ ] Rodar `pytest tests/test_funcao_consulta.py -q` → FAIL.
- [ ] `get_current_usuario(request: Request, token=..., db=...)`: depois de validar o usuário, se `usuario.funcao_rel is not None and usuario.funcao_rel.descricao == FUNCAO_CONSULTA and request.method not in {"GET","HEAD","OPTIONS"} and request.url.path not in _ESCRITA_LIBERADA_CONSULTA` → 403. `_ESCRITA_LIBERADA_CONSULTA = frozenset({"/auth/trocar-senha"})`. Conferir com grep que nenhum chamador invoca `get_current_usuario(...)` direto (fora de `Depends`); se houver, ajustar.
- [ ] Migração `0033_funcao_consulta` (`down_revision = "0032_cliente_tiny"`): upgrade `INSERT INTO funcoes (descricao) SELECT 'Consulta' WHERE NOT EXISTS (...)`; downgrade `DELETE FROM funcoes WHERE descricao='Consulta' AND NOT EXISTS (SELECT 1 FROM usuarios WHERE funcao_id = funcoes.id)`. Atenção: `funcoes.id` pode não ter sequence se os ids vieram do legado — se o INSERT falhar por id nulo, usar `COALESCE(MAX(id),0)+1`. **Não aplicar em produção** (o Erick aplica).
- [ ] Rodar o arquivo → PASS; rodar `pytest -q` inteiro e comparar com baseline. Commit `feat(acesso): funcao consulta somente leitura`.

### Task 3: Filtro por modelo na frota e nos clientes (backend)

**Files:** Modify `backend/app/api/equipamentos_cliente.py` (`_query_frota`, `listar`, `exportar`), `backend/app/api/clientes.py` (`_query_clientes`, `listar`, `exportar`); Test `backend/tests/test_filtro_modelo.py`

**Interfaces:** Produces query param `equipamento: int | None` em `GET /equipamentos-cliente`, `/equipamentos-cliente/exportar`, `/clientes`, `/clientes/exportar`.

- [ ] Testes (dados: modelo A e B; cliente X com 2 aparelhos A ativos, cliente Y com 1 A inativo, cliente Z com B, estoque id=`CLIENTE_ESTOQUE_HS_ID` com 1 A ativo):
  - `test_frota_filtra_por_modelo`: `?equipamento=A` → 4 itens (inclui inativo e estoque), todos com `equipamento == A`.
  - `test_clientes_tem_modelo`: `?equipamento=A` → só X, `total == 1` (sem duplicar, sem Y inativo, sem estoque).
  - `test_clientes_tem_modelo_combina_com_q`: `?equipamento=A&q=<nome de Z>` → vazio.
  - `test_exportar_respeita_filtro` (frota e clientes): xlsx tem o número de linhas de dados esperado.
- [ ] Rodar → FAIL. Implementar: frota `filter(EquipamentoCliente.equipamento == equipamento)`; clientes `EXISTS` com `equipamento == X`, `ativo.is_(True)`, `Cliente.id != settings.CLIENTE_ESTOQUE_HS_ID` (aplicado só quando o filtro vem).
- [ ] PASS. Commit `feat(frota): filtro por modelo de aparelho`.

### Task 4: Resumo por modelo (backend)

**Files:** Modify `backend/app/api/equipamentos_cliente.py`, `backend/app/schemas/frota.py`; Test `backend/tests/test_filtro_modelo.py`

**Interfaces:** Produces `GET /equipamentos-cliente/resumo-por-modelo` → `list[ResumoModeloOut]`, `ResumoModeloOut{equipamento: int, descricao: str | None, aparelhos: int, clientes: int}`; ordenado por `aparelhos` desc, depois `descricao`. Só ativos, sem estoque HS, modelos com 0 omitidos. Auth: `get_current_usuario`. Declarar antes de qualquer `/{id}`.

- [ ] Teste `test_resumo_por_modelo` com os mesmos dados: `[{A, aparelhos 2, clientes 1}, {B, 1, 1}]`.
- [ ] FAIL → implementar (`group_by` + `count(distinct cliente)`, join no catálogo para `descricao`) → PASS. Commit `feat(frota): resumo de aparelhos por modelo`.

### Task 5: Frontend do Consulta

**Files:** Modify `frontend/src/auth/roles.ts`, `roles.test.ts`, `frontend/src/layout/Sidebar.tsx`, `Sidebar.test.tsx`, `frontend/src/app/catalogo/CatalogoProdutosPage.tsx` (+ test)

**Interfaces:** Produces `FUNCAO_CONSULTA = 'Consulta'`, `isConsulta(user): boolean`, `podeVerProdutos(user)` = `podeGerenciarPropostas || isConsulta`. Lista `ITENS_CONSULTA = ['/app', '/app/clientes', '/app/empresas', '/app/equipamentos', '/app/catalogo/produtos']` na Sidebar.

- [ ] Testes: `isConsulta`; Sidebar com usuário Consulta mostra exatamente Dashboard, Clientes, Empresas, Equipamentos, Produtos; `CatalogoProdutosPage` com Consulta mostra a lista e **não** mostra botão "Novo"/editar/excluir.
- [ ] FAIL → implementar: filtro da Sidebar — se `isConsulta`, item visível sse `to` ∈ `ITENS_CONSULTA` (ignora `visivel`); Produtos: acesso com `podeVerProdutos`, ações de escrita com `podeGerenciarPropostas`.
- [ ] Conferir à mão Clientes, ClienteLayout/abas, Empresas, Equipamentos e detalhe de aparelho: todo botão de escrita guardado por helper que não inclui Consulta (grep por `<Button` sem guarda). Corrigir o que faltar.
- [ ] PASS. Commit `feat(acesso): telas da funcao consulta`.

### Task 6: Filtros e resumo no frontend

**Files:** Modify `frontend/src/app/frota/api.ts`, `FrotaPage.tsx` (+ `FrotaPage.test.tsx`), `frontend/src/app/clientes/api.ts`, `ClientesPage.tsx` (+ `ClientesPage.test.tsx`); Create `frontend/src/app/frota/ResumoPorModelo.tsx` (+ test)

**Interfaces:** Consumes Task 3/4 endpoints. `FrotaParams.equipamento?: number`, `ListarParams.equipamento?: number`, `equipamentosClienteApi.resumoPorModelo(): Promise<ResumoModelo[]>`. Catálogo via `equipamentosApi.listar()` (`app/cadastros/api.ts`).

- [ ] Testes: FrotaPage aberta com `?equipamento=36` chama `listar` com `equipamento: 36` e o select mostra o modelo; mudar o select atualiza a URL e zera offset; exportar recebe `equipamento`. ClientesPage idem com select "Tem aparelho". ResumoPorModelo renderiza linhas e links `/app/equipamentos?equipamento=X` e `/app/clientes?equipamento=X`.
- [ ] FAIL → implementar (estado do filtro lido/gravado em `useSearchParams`, preservando `cliente` na frota; bloco recolhível fechado por padrão no topo da FrotaPage).
- [ ] PASS; `npm run lint && npx tsc -b --noEmit && npm run build`. Commit `feat(frota): filtro e visao por modelo na tela`.

### Task 7: Fechamento

- [ ] Entrada `1.60.0` no topo de `frontend/src/app/changelog/data.ts` (Expedição vê Propostas; função Consulta; filtro e visão por modelo).
- [ ] `pytest -q` (vs baseline) + verificação completa do frontend.
- [ ] Commit `docs(changelog): v1.60.0 — funcao consulta e visao por modelo`. Não fazer push.
