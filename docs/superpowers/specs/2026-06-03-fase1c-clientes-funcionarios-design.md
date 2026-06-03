# GestorHS — Fase 1C (Clientes & Funcionários)

**Data:** 2026-06-03
**Status:** Aprovado para implementação
**Depende de:** Fase 1A (Acesso) e 1B (Cadastros de referência) — na `main`. Reusa `crudClient`/`useCrud`, o padrão lista+modal/form, o gating por função e o helper `excluir_protegido`.
**Parte de:** Épico 1.4 do roadmap (Cadastros base), sub-projeto 2 de 2 (encerra o 1.4).

---

## 1. Objetivo

Gerir a base de **clientes** (1.833 registros) e os **funcionários** de cada cliente. Clientes é dado operacional consultado por todas as funções; sua edição e a gestão de funcionários ficam com o Administrador. Entrega lista com busca/paginação, página de detalhe/edição e a sub-gestão de funcionários — encerrando os cadastros base da Fase 1.

## 2. Escopo

**Dentro:** CRUD de `clientes` (lista paginada com busca + página de detalhe/edição com form em seções) e `funcionarios` (geridos dentro do detalhe do cliente).

**Decisões:**
- **Permissão:** leitura (`GET`) para qualquer usuário interno autenticado; escrita (`POST`/`PATCH`/`DELETE`) só Administrador. O item de nav "Clientes" é visível a todos os internos (sem `adminOnly`).
- **Não-admin vê o detalhe em modo leitura** (campos desabilitados, sem botões de salvar/excluir) em vez de ser bloqueado — combina com "ler = qualquer interno". A API impõe 403 na escrita de qualquer forma.
- **Busca + paginação server-side:** `GET /clientes` aceita `q` (casa `nome`/`cgc`/`cpf`/`municipio` via `ilike`), `offset` e `limit` (padrão 25); devolve `{ items, total }`. A lista usa um schema enxuto (`ClienteListOut`).
- **Página de detalhe** (`/app/clientes/:id`) serve edição; `/app/clientes/novo` serve criação. Funcionários só aparecem quando o cliente já existe (precisa do id).
- **Guarda de exclusão:** excluir um cliente com funcionário (ou referenciado por OS/frota — FKs no banco real) → **409 "registro em uso"** (helper `excluir_protegido`).
- **Imagem do cliente adiada** (`clientes.imagem` não editada — coerente com a Fase 1B).

**Fora (com a fase de destino):**
- Importação em massa de clientes; upload de imagem/mídia.
- Vínculos com `equipamentos_cliente` (frota), OS, certificados → Fases 2–3.
- Refino de permissões por função (ex.: Comercial editar clientes) → Fase 3.

## 3. Contexto do código atual

- Backend FastAPI + SQLAlchemy 2 + Pydantic v2. `app/api/deps.py` → `get_current_usuario` (qualquer interno; 401 sem token) e `require_funcao("Administrador")` (retorna o Usuario; 403 se função não bate). `app/api/cadastros_common.py` → `excluir_protegido(db, obj)` (delete; IntegrityError → 409 "registro em uso"). Modelos existentes incluem `Setor`, `Grupo` (FKs que o cliente/funcionário usam). Routers registrados em `app/main.py`. Schemas por domínio. Teste: SQLite in-memory com `PRAGMA foreign_keys=ON` (conftest), fixtures `client`, `db_session`, `usuario_admin` (admin/senha123), `usuario_comum` (Expedição, comum/senha123).
- Frontend React 19 + Vite 8 + Tailwind v4. Reusa: `Table/TH/TD`, `Modal`, `Button`, `Input`, `Select`, `Badge`, `Spinner`; `apiJson`/`apiFetch`/`ApiError` (`lib/api.ts`); `useAuth`/`isAdmin`; `crudClient`/`useCrud` (`app/cadastros/`). `Sidebar` filtra itens por `adminOnly` (itens sem a flag aparecem a todos). `react-router-dom` v7 com árvore `/app/*`.

### Tabelas (já existentes no banco)

```
clientes(id bigserial, grupo→grupos, nome, cgc(14), cpf(11), endereco, numero bigint,
         complemento, bairro, municipio, estado char(2), cep char(8), contato, email,
         telefones, celular, whatsapp, whatsapp1, whatsapp2, insc_mun, insc_est,
         datcad date, obs text, imagem, ativo bool)
funcionarios(id, cliente→clientes NOT NULL, setor→setores, matricula, centro, nome,
             email, cargo, admissao date, idade int, sexo char(1), estado(2), cidade, ativo bool)
```

## 4. Backend

Modelos novos `Cliente` e `Funcionario` (um arquivo por modelo). Schemas em `app/schemas/clientes.py`. Routers `app/api/clientes.py` e `app/api/funcionarios.py`, registrados em `app/main.py`.

### 4.1 Rotas

| Método | Rota | Autorização | Notas |
|---|---|---|---|
| GET | `/clientes?q=&offset=&limit=` | qualquer interno | `{ items: ClienteListOut[], total: int }`; `q` ilike em nome/cgc/cpf/municipio; `limit` padrão 25, máx. 100 |
| GET | `/clientes/{id}` | qualquer interno | `ClienteOut` (completo); 404 |
| POST | `/clientes` | Administrador | `ClienteOut`; 201 |
| PATCH | `/clientes/{id}` | Administrador | parcial (`exclude_unset`); 404 |
| DELETE | `/clientes/{id}` | Administrador | `excluir_protegido` → 409 se em uso; 404 |
| GET | `/clientes/{cliente_id}/funcionarios` | qualquer interno | lista os funcionários do cliente; 404 se cliente não existe |
| POST | `/clientes/{cliente_id}/funcionarios` | Administrador | cria com `cliente` do path; 404 se cliente não existe |
| PATCH | `/funcionarios/{id}` | Administrador | parcial; 404 |
| DELETE | `/funcionarios/{id}` | Administrador | 404 |

### 4.2 Schemas

- **`ClienteListOut`** (lista enxuta): `id, nome, cgc, cpf, municipio, estado, ativo`.
- **`ClientesPage`**: `{ items: list[ClienteListOut], total: int }`.
- **`ClienteOut`** (completo): todos os campos exceto `imagem` (id, grupo, nome, cgc, cpf, endereco, numero, complemento, bairro, municipio, estado, cep, contato, email, telefones, celular, whatsapp, whatsapp1, whatsapp2, insc_mun, insc_est, datcad, obs, ativo).
- **`ClienteCreate`**: `nome` obrigatório (min_length=1); demais opcionais; `ativo` default true. (`imagem`/`datcad` não recebidos.)
- **`ClienteUpdate`**: todos opcionais.
- **`FuncionarioOut`**: `id, cliente, setor, matricula, centro, nome, email, cargo, admissao, idade, sexo, estado, cidade, ativo`.
- **`FuncionarioCreate`**: `nome` obrigatório; demais opcionais; `ativo` default true. (`cliente` vem do path, não do corpo.)
- **`FuncionarioUpdate`**: todos opcionais (não inclui `cliente`).

`*Out` com `from_attributes=True`. Sem validação de FK no app além do que o banco impõe.

### 4.3 Busca e paginação

`listar` aplica filtro `q` (se presente) com `or_(Cliente.nome.ilike(f"%{q}%"), Cliente.cgc.ilike(...), Cliente.cpf.ilike(...), Cliente.municipio.ilike(...))`, conta o total filtrado, e devolve `items` com `offset`/`limit` (ordenados por `nome`). `limit` é limitado a no máximo 100.

## 5. Frontend

- **Nav:** item **"Clientes"** (sem `adminOnly`) → `/app/clientes`. Ícone novo `IconClientes`.
- **`ClientesPage`** (`/app/clientes`): campo de busca (dispara a consulta), `Table` (Nome, CNPJ/CPF, Município/UF, `Badge` ativo), controles de paginação ("Anterior"/"Próxima" + "X–Y de N"). Clique na linha → `/app/clientes/:id`. Botão "Novo cliente" só para admin (`isAdmin`) → `/app/clientes/novo`. Estado: termo de busca, página atual.
- **`ClienteDetailPage`** (`/app/clientes/:id` e `/app/clientes/novo`): carrega o cliente por id (ou vazio para "novo"); form em seções (Identificação, Endereço, Contatos, Observações), com `Select` de grupo. Salvar/voltar. **Não-admin: campos desabilitados e sem botões de escrita** (modo leitura). Em "novo", após salvar, navega para o detalhe do cliente criado.
- **Funcionários** (componente dentro do detalhe, só quando o cliente já existe): sub-`Table` + modal de criar/editar (matrícula, nome, cargo, `Select` de setor, e-mail, admissão, ativo), excluir. Admin escreve; não-admin só vê.
- **API** `app/clientes/api.ts`: `clientesApi` (`listar({q,offset,limit})`, `obter`, `criar`, `atualizar`, `excluir`) e `funcionariosApi` (`listarPorCliente(clienteId)`, `criar(clienteId, payload)`, `atualizar(id, payload)`, `excluir(id)`). Reusa `apiJson` e um `apiVoid` local; a `listar` monta a query string.
- Erros (incl. 409 "em uso") inline; exclusão confirmada via `window.confirm`.

## 6. Testes

- **Backend (pytest, SQLite, junto dos atuais):**
  - Lista: `q` filtra (casa nome/cgc/cidade); paginação respeita `offset`/`limit` e `total` reflete o filtro.
  - Permissão: GET liberado a `usuario_comum` (200); POST/PATCH/DELETE negados a não-admin (403).
  - CRUD de cliente; 404 em id inexistente; delete-cliente-em-uso (com funcionário) → 409.
  - Funcionários: criar via `/clientes/{id}/funcionarios` (cliente do path); listar por cliente; cliente inexistente → 404; editar/excluir por id; criar/editar/excluir negado a não-admin (403).
- **Frontend (Vitest+RTL, lógica):** `clientes/api.ts` — `listar` monta a query string (`q`/`offset`/`limit`) corretamente e parseia `{items,total}`; `funcionariosApi.criar` posta no path do cliente; propagação de `ApiError`. Telas visuais por `tsc -b` + `lint` + E2E manual.

## 7. Critérios de aceite

- Qualquer interno vê "Clientes", busca por nome/CNPJ, pagina e abre o detalhe (somente leitura se não-admin).
- Admin cria/edita/exclui cliente e gere funcionários no detalhe; excluir cliente com funcionário mostra **409 "registro em uso"**.
- A busca filtra server-side e a paginação navega corretamente (total e fatias certos).
- Funcionário criado fica vinculado ao cliente do path; criar para cliente inexistente → 404.
- `pytest` e `npm run test` verdes; `tsc -b`, `lint`, `build` limpos; verificação E2E manual no navegador.

## 8. Fora de escopo (reafirmando)
Importação em massa; imagem/mídia do cliente; vínculos com frota/OS/certificados; refino de permissões por função; paginação por cursor (usamos offset/limit).
