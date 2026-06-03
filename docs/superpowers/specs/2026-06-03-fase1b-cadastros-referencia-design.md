# GestorHS — Fase 1B (Cadastros de referência)

**Data:** 2026-06-03
**Status:** Aprovado para implementação
**Depende de:** Fase 1A (Acesso) — na `main`. Reusa o padrão lista+modal, o gating por função e o módulo de API tipado.
**Parte de:** Épico 1.4 do roadmap (Cadastros base), sub-projeto 1 de 2. O sub-projeto seguinte (1C — Clientes & Funcionários) virá em spec próprio.

---

## 1. Objetivo

Entregar a gestão dos **dados-mestre de referência** do sistema: setores, marcas, grupos, categorias e o catálogo de equipamentos. São a fundação que clientes, frota e Ordens de Serviço referenciam. O Administrador cadastra e edita; qualquer usuário interno pode ler as listas (para popular selects de formulários futuros).

## 2. Escopo

**Dentro:** CRUD de `setores`, `marcas`, `grupos`, `categorias` e `equipamentos` (catálogo), numa página única "Cadastros" com abas.

**Decisões:**
- **Permissão:** leitura (`GET`) liberada para qualquer usuário interno autenticado; escrita (`POST`/`PATCH`/`DELETE`) só Administrador.
- **Imagem adiada:** os campos `marcas.imagem` e `equipamentos.imagem` **não** são editados nesta fase (upload/storage de mídia é questão em aberto do design — fase futura). Valores existentes são preservados.
- **Sem unicidade de `descricao`:** o schema legado não exige; duplicatas são permitidas (não validamos).
- **Guarda de exclusão:** excluir um registro referenciado por outro (FK) devolve **409 "registro em uso"**.

**Fora (com a fase de destino):**
- Clientes e funcionários do cliente → **Fase 1C**.
- Upload/armazenamento de imagens → fase de mídia.
- `equipamentos_cliente` (frota física), OS, calibração → Fases 2–3.

## 3. Contexto do código atual

- Backend FastAPI + SQLAlchemy 2 + Pydantic v2. `app/api/deps.py`: `get_current_usuario` (qualquer interno autenticado) e `require_funcao("Administrador")` (retorna o usuário; 403 se a função não bate). Routers existentes: `auth`, `funcoes`, `usuarios`. Schemas agrupados por domínio (`app/schemas/auth.py`, `acesso.py`). Modelos um por arquivo (`app/models/usuario.py`, `funcao.py`).
- Teste backend: SQLite in-memory (`tests/conftest.py`), fixtures `client`, `db_session`, `usuario_admin` (Administrador, `admin`/`senha123`), `usuario_comum` (Expedição, `comum`/`senha123`). Roda no container: `docker compose exec -T backend python -m pytest`.
- Frontend React 19 + Vite 8 + Tailwind v4. Reusa: `Table/TH/TD`, `Modal`, `Button`, `Input`, `Select`, `Badge`, `Spinner`; `apiJson`/`apiFetch`/`ApiError` (`lib/api.ts`); `useAuth`/`isAdmin`; padrão lista+modal de `app/acesso/UsuariosPage.tsx`. Sidebar com `adminOnly`. Segmented control descrito na seção 6.11 do `DESIGN_SYSTEM.md`.

### Tabelas (já existentes no banco)

```
setores(id, descricao)
marcas(id, descricao, imagem)
grupos(id, descricao, texto)
categorias(id, setor→setores, posicao, descricao)
equipamentos(id, categoria→categorias, marca→marcas, descricao, detalhes, especificacao,
             preco_cod, preco_por, custo, peso_calibragem, peso, imagem,
             estoque, estoque_min, ativo, destaque, datacad)
```

## 4. Backend

Modelos SQLAlchemy novos (mapeiam tabelas existentes): `Setor`, `Marca`, `Grupo`, `Categoria`, `Equipamento` (um arquivo por modelo em `app/models/`). Schemas em `app/schemas/cadastros.py`. Um router explícito por entidade em `app/api/` (`setores.py`, `marcas.py`, `grupos.py`, `categorias.py`, `equipamentos.py`), registrados em `app/main.py`.

### 4.1 Rotas (padrão por entidade)

Para cada recurso `<r>` ∈ {`setores`, `marcas`, `grupos`, `categorias`, `equipamentos`}:

| Método | Rota | Autorização |
|---|---|---|
| GET | `/<r>` | qualquer interno (`get_current_usuario`) |
| GET | `/<r>/{id}` | qualquer interno |
| POST | `/<r>` | Administrador |
| PATCH | `/<r>/{id}` | Administrador |
| DELETE | `/<r>/{id}` | Administrador |

- GET de id inexistente → 404.
- DELETE de registro em uso (viola FK) → **409 "registro em uso"** (capturar `IntegrityError`, `db.rollback()`, levantar 409).
- PATCH usa `model_dump(exclude_unset=True)` (atualização parcial).

### 4.2 Campos por entidade (schemas Pydantic)

- **Setor:** `descricao` (obrigatório).
- **Marca:** `descricao` (obrigatório). *(imagem não editada)*
- **Grupo:** `descricao` (obrigatório), `texto` (opcional).
- **Categoria:** `descricao` (obrigatório), `setor` (FK opcional → setores.id), `posicao` (int, default 0).
- **Equipamento:** `descricao`, `categoria` (FK opcional), `marca` (FK opcional), `detalhes` (opcional), `especificacao` (opcional), `preco_cod`/`preco_por`/`custo` (numérico, default 0), `peso_calibragem`/`peso` (numérico, default 0), `estoque`/`estoque_min` (int, default 0), `ativo` (bool, default false), `destaque` (bool, default false). *(imagem e datacad não editados; datacad pode ser deixado pelo banco/None)*

Schemas `*Out` com `from_attributes=True`. Não há validação de FK explícita no app além do que o banco impõe (FK inválida → o banco rejeita; tratar como 400/409 se ocorrer — caso raro pela UI, que usa selects).

## 5. Frontend

- **Nav:** item **"Cadastros"** na Sidebar, `adminOnly: true` → rota `/app/cadastros`.
- **Página `CadastrosPage`** (`/app/cadastros`, admin): um **segmented control** (abas) — Setores · Marcas · Grupos · Categorias · Equipamentos — alternando entre painéis. Estado de aba local.
- **Reúso — hook `useCrud<T>`** (`src/app/cadastros/useCrud.ts`): encapsula `itens`, `loading`, `erro`, `recarregar()`, e helpers para excluir com tratamento de erro — a orquestração hoje duplicada em `UsuariosPage`. Cada painel usa o hook e renderiza sua própria tabela + modal.
- **Painéis** (`src/app/cadastros/`):
  - `SetoresPanel`, `MarcasPanel` — tabela (descrição) + modal de um campo.
  - `GruposPanel` — descrição + textarea (texto).
  - `CategoriasPanel` — descrição + `Select` de setor + posição; consome a lista de setores.
  - `EquipamentosPanel` — form com os campos da 4.2; consome listas de categorias e marcas (selects); badges para ativo/destaque na tabela.
- **Módulo de API** `src/app/cadastros/api.ts`: funções tipadas por entidade sobre `apiJson` (e `apiVoid` para o DELETE 204), espelhando o `acesso/api.ts`.
- Erros (incl. 409 "em uso") inline; exclusão confirmada via `window.confirm`.

## 6. Testes

- **Backend (pytest, SQLite, junto dos atuais):** por entidade —
  - leitura liberada a não-admin (`usuario_comum` → GET 200);
  - escrita negada a não-admin (POST/PATCH/DELETE → 403);
  - criar, obter (404 se inexistente), editar (partial);
  - excluir normal (204) e **excluir em uso → 409** (ex.: setor referenciado por categoria; marca/categoria por equipamento).
  - Cobertura mais densa em setores, categorias e equipamentos (FK/guarda); marcas e grupos com o essencial.
- **Frontend (Vitest+RTL, lógica como nas fases anteriores):**
  - `useCrud` — carrega itens, expõe erro em falha, `recarregar()` após ação.
  - `cadastros/api.ts` — chamadas batem nos endpoints/métodos certos e propagam `ApiError`.
  - Painéis visuais e a `CadastrosPage` (abas) verificados por `tsc -b` + `lint` + E2E manual.

## 7. Critérios de aceite

- Admin vê "Cadastros", alterna entre as abas e faz CRUD em cada entidade.
- Categoria liga a um setor; equipamento liga a categoria + marca (selects populados via API).
- Excluir um registro referenciado mostra **409 "registro em uso"**; o registro permanece.
- Um usuário não-admin **não** vê "Cadastros" e recebe 403 ao tentar escrever, mas consegue **ler** as listas via API (GET 200).
- `pytest` (back) e `npm run test` (front) verdes; `tsc -b`, `lint` e `build` limpos.
- Verificação E2E manual no navegador contra o backend no Docker.

## 8. Fora de escopo (reafirmando)
Clientes, funcionários do cliente (1C); upload/armazenamento de imagens; `equipamentos_cliente`/OS/calibração; unicidade de `descricao`; ordenação drag-and-drop de categorias.
