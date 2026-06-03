# GestorHS — Fase 3C (Frontend de OS — visualização + config admin)

**Data:** 2026-06-03
**Status:** Aprovado para implementação
**Parte de:** Fase 3 (Ordens de Serviço), sub-projeto 3 de 5 (3A schema ✅ → 3B backend ✅ → **3C kanban/lista/detalhe + config** → 3D formulários-portão → 3E calibração/certificado).
**Depende de:** Backend da OS (3B) na `main`: `GET /ordens` (paginado, filtros fase/cliente/tipo/q), `GET /ordens/quadro` (ativas agrupadas), `GET /ordens/{id}`, `GET /ordens/{id}/logs`, `GET/PATCH /fases`, CRUD `/funcoes`. Frontend Fase 0–2 (design system, `apiJson`/`crudClient`, layout, auth/roles).

---

## 1. Objetivo

Entregar a interface só-leitura do módulo de Ordens de Serviço — o **quadro kanban** das OS ativas (a visão operacional central), uma **lista** paginada para o histórico, e a **página de detalhe** com a timeline de eventos — além da **tela admin de configuração** do mapa função→fase e do CRUD de funções (endpoints prontos desde a 3B, ainda sem UI). Nenhuma ação de escrita de OS: abrir/avançar/cancelar (formulários-portão) são a Fase 3D.

## 2. Escopo

**Dentro:**
- Módulo `frontend/src/app/ordens/` (api + páginas).
- `/app/ordens` com toggle **Quadro | Lista**; `/app/ordens/:id` detalhe.
- Item de nav "Ordens" (visível a todos os internos).
- Abas **Funções** e **Fases** na página Cadastros (admin).

**Fora (com a fase/destino):**
- Abrir/avançar/cancelar e formulários-portão → **3D**.
- Resultados ricos de calibração/certificado/espelhamento → **3E** (exibidos no detalhe se já existirem, nunca editados aqui).
- Drag-and-drop no kanban (o avanço é por formulário, não por arrastar).
- Portal do cliente → Fase 5.
- Decisão de `os_atual` ao encerrar a OS → follow-up da 3E.

## 3. Contexto do código atual

- React 19 + Vite 8 + Tailwind v4. Componentes `Table/TH/TD`, `Button`, `Badge` (tones primary/warning/danger/neutral), `Spinner`, `Input`, `Select`, `Modal`. `apiJson`/`apiFetch`/`ApiError` em `lib/api`; `cn()` em `lib/utils`. `useAuth`/`isAdmin` em `auth/`. Rotas em `app/routes.tsx`; nav em `layout/Sidebar.tsx` (`NAV_ITEMS` com `adminOnly`). Ícones SVG inline em `components/ui/icons`.
- Padrão de módulo de domínio (ver `app/frota/`): `api.ts` com tipos + objeto-cliente usando `apiJson`/`apiVoid`; página de lista com `useEffect` (guarda `ativo`), busca via form, paginação `offset`/`limit` 25, leitura de `?cliente=` por `useSearchParams`, navegação por `useNavigate`, linha clicável → detalhe.
- Padrão de cadastro (ver `app/cadastros/`): `crudClient<TOut,TCreate,TUpdate>(base)` genérico em `cadastros/api.ts`; `CadastroSimples<T>` (lista + criar/editar/excluir com `Modal`, trata 409 inline); `CadastrosPage` com abas (estado local `aba`, pills). `funcoesApi`/`fasesApi` serão adicionados seguindo esse padrão.
- Backend relevante: `GET /ordens/quadro` → `[{fase, descricao, cor, ordens: OrdemListOut[]}]`; `OrdemListOut` = `{id, cliente, cliente_nome, equipamento_cliente, equipamento_descricao, equipamento_serie, fase, fase_descricao, fase_cor, tipo_servico, data_chegada, prox_calibragem, situacao}`; `GET /ordens` → `{items, total}`; `OrdemOut` (detalhe) inclui condicao_chegada/acessorios/aceite/cod_retorno/datas + calib_* só-leitura; `LogOut` = `{id, os, usuario, autor, datalog, texto}`; `GET /funcoes` (admin) → `{id, descricao}`; `GET /fases` → `{id, descricao, cor, funcao_responsavel, funcao_nome}`; `PATCH /fases/{id}` `{funcao_responsavel}`.

## 4. Nav e rotas

- **Sidebar:** novo `NAV_ITEM` **"Ordens"** (sem `adminOnly`) → `/app/ordens`, com um ícone novo (`IconOrdens`) em `components/ui/icons`.
- **Rotas** (`app/routes.tsx`):
  - `/app/ordens` → `OrdensPage` (quadro/lista).
  - `/app/ordens/:id` → `OrdemDetailPage`.

## 5. Módulo `app/ordens/`

### 5.1 `api.ts`
- Tipos: `OrdemListItem` (campos de `OrdemListOut`), `OrdemPage {items, total}`, `QuadroColuna {fase, descricao, cor, ordens: OrdemListItem[]}`, `OrdemDetalhe` (campos de `OrdemOut`), `LogOS {id, os, usuario, autor, datalog, texto}`.
- `TIPO_SERVICO: Record<'C'|'M'|'A', {label, tone}>` → C "Calibração" (primary), M "Manutenção" (warning), A "Ambas" (neutral). `null` → "—".
- `ordensApi`:
  - `listar({fase?, cliente?, tipo?, q?, offset?, limit?}) → OrdemPage` (monta query string; só inclui chaves presentes; `offset` default 0, `limit` default 25).
  - `quadro({cliente?}) → QuadroColuna[]` (`/ordens/quadro`, inclui `cliente` se houver).
  - `obter(id) → OrdemDetalhe` (`/ordens/{id}`).
  - `logs(id) → LogOS[]` (`/ordens/{id}/logs`).

### 5.2 `OrdensPage` (`/app/ordens`)
- Estado `vista: 'quadro' | 'lista'` (default `'quadro'`), toggle de pills no topo (padrão visual das abas de Cadastros). Lê `?cliente=ID` (chip "Cliente: nome — limpar" como na Frota); o filtro de cliente vale para as duas vistas.
- **Quadro:** carrega `ordensApi.quadro({cliente})`. Renderiza 4 colunas lado a lado (flex, scroll horizontal se faltar largura; cada coluna com scroll vertical). Cabeçalho da coluna: faixa com `fase_cor` (estilo `style={{ background: '#'+cor }}` ou borda), `descricao` e contagem `(n)`. Lista de **cartões**: `OS #id`, `cliente_nome`, `equipamento_descricao` + série, `Badge` de tipo de serviço (via `TIPO_SERVICO`), `data_chegada` formatada. Cartão clicável → `/app/ordens/:id`. Coluna vazia → texto "—".
- **Lista:** carrega `ordensApi.listar({fase, cliente, tipo, q, offset, limit:25})`. Filtros: `Select` de **fase** (Recebido/Laboratório/Pós-Vendas/Preparando Retorno/Finalizada/Cancelada, com os ids 4–9), `Select` de **tipo** (C/M/A), e form de **busca** `q` (placeholder "Nº da OS, etiqueta ou cliente"). Tabela: OS #, Cliente, Equipamento, Fase (`Badge` com `fase_cor`), Tipo, Chegada, Situação. Paginação 25/pág ("X–Y de N", Anterior/Próxima). Linha → detalhe.
- Erros via `ApiError` inline; `Spinner` no carregamento.

### 5.3 `OrdemDetailPage` (`/app/ordens/:id`)
- Carrega `ordensApi.obter(id)` e `ordensApi.logs(id)`. 404 → mensagem "OS não encontrada" + voltar.
- **Cabeçalho:** `OS #id`, `Badge` da fase (cor `fase_cor`), `cliente_nome`, `equipamento_descricao` + série, situação. Botão "Voltar".
- **Recebimento:** tipo de serviço (label), condição de chegada, acessórios, data de chegada.
- **Datas:** data de calibração, data de aceite, data de retorno (postagem), próxima calibração — "—" quando nulas.
- **Resultados da calibração:** bloco só-leitura com `calib_cert/calib_temp/calib_pressao/calib_teste_media/calib_situacao/pdf_certificado` **se houver algum preenchido**; senão, nota "Sem resultados de calibração ainda." (preenchido na 3E).
- **Histórico:** timeline dos `logs` (mais recente primeiro ou por id), cada item com data (`datalog`) e `texto`. Vazio → "Sem eventos."
- **Sem botões de ação** (abrir/avançar/cancelar = 3D).

## 6. Config admin (abas em Cadastros)

`CadastrosPage` ganha duas abas novas no array `ABAS`: **"Funções"** e **"Fases"**.

### 6.1 Aba Funções
- Reusa `CadastroSimples<Funcao>` com um `funcoesApi` (CRUD) — `Funcao = {id, descricao}`. Criar/editar pede só `descricao`. Excluir função em uso → **409** "registro em uso" tratado inline (o `CadastroSimples` já trata `ApiError`).
- `funcoesApi = crudClient<Funcao, {descricao:string}, {descricao?:string}>('/funcoes')` em `cadastros/api.ts` (ou em `acesso/api.ts`, onde já há tipos de função; **decisão de implementação:** colocar junto do `crudClient` em `cadastros/api.ts` para reuso direto).

### 6.2 Aba Fases
- `FasesPanel` (componente próprio): carrega `fasesApi.listar()` (as 6 fases) e `funcoesApi.listar()` (para o Select). Tabela: Fase (descrição + bolinha da cor), `Select` de responsável (opções = funções + "— sem responsável —" para `null`). Ao mudar o Select, chama `fasesApi.atualizar(id, {funcao_responsavel})` e atualiza a linha; erro inline. Finalizada/Cancelada normalmente sem responsável (mas editáveis).
- `fasesApi` em `cadastros/api.ts`: `listar() → Fase[]` (`/fases`), `atualizar(id, {funcao_responsavel:number|null}) → Fase` (`PATCH /fases/{id}`). `Fase = {id, descricao, cor, funcao_responsavel, funcao_nome}`.

## 7. Testes

- **Vitest + RTL** (`app/ordens/api.test.ts`): `ordensApi.listar` monta a query string correta com cada combinação de filtros (fase/cliente/tipo/q/offset/limit) e omite chaves ausentes; `quadro` usa `/ordens/quadro` (com/sem cliente); `obter`/`logs` nos paths certos; propaga `ApiError` em resposta não-ok. Para `fasesApi`/`funcoesApi`: paths e métodos corretos (`PATCH /fases/{id}`, CRUD `/funcoes`). Mockar `apiJson`/`apiFetch` como nos testes de `frota/api.test.ts`.
- **Telas:** validadas por `tsc -b` + `npm run lint` + `npm run build` limpos, e **E2E manual** no navegador contra o banco real.

## 8. Critérios de aceite

- Qualquer interno abre "Ordens", vê o kanban das OS ativas distribuídas em 4 colunas (com as cores das fases e contagens), alterna para a Lista, filtra por fase/tipo, busca por nº/cliente, e abre o detalhe de uma OS com a timeline de logs.
- O filtro `?cliente=ID` (ex.: vindo de outro módulo no futuro) filtra ambas as vistas.
- Admin, nas abas de Cadastros, edita o responsável de cada fase (PATCH /fases) e cria/edita/exclui funções (409 em uso tratado).
- `npm run test` verde; `tsc -b`, `lint`, `build` limpos; E2E manual ok (379 OS ativas no quadro; histórico de 10.168 na lista com busca).

## 9. Fora de escopo (reafirmando)
Formulários-portão e ações de escrita de OS (3D); resultados ricos/certificado/espelhamento (3E); drag-and-drop; portal (Fase 5); limpeza de `os_atual` ao encerrar (3E).
