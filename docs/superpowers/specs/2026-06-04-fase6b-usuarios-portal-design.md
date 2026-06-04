# GestorHS — Fase 6B (Gestão de usuários do portal)

**Data:** 2026-06-04
**Status:** Aprovado para implementação
**Parte de:** Fase 6 (Migração de credenciais), sub-projeto 2 de 2 — 6A reset forçado ✅ → **6B gestão de usuários do portal**. Encerra a Fase 6 e o roadmap principal.
**Depende de:** 1C (`ClienteDetailPage`, `FuncionariosSection`, padrão de seção aninhada + router aninhado `funcionarios.py`), 6A (senha temporária / reset forçado), `UsuarioCliente` (UNIQUE `(cliente, login)`), `hash_senha`.

---

## 1. Objetivo

Dar ao admin a gestão dos logins do portal (`usuarios_cliente`): criar, editar, redefinir senha (temporária) e excluir — no detalhe do cliente. É o que falta para **provisionar e desbloquear** os clientes (legados e novos) no portal; com a 6A, o cliente troca a senha temporária no 1º acesso.

## 2. Escopo

**Dentro:**
- Backend: CRUD aninhado de `usuarios_cliente` (`/clientes/{id}/usuarios-portal` + `/usuarios-portal/{id}`), admin-only, senha sempre temporária; senha nunca exposta.
- Frontend: `UsuariosPortalSection` no detalhe do cliente (admin-only) + `usuariosPortalApi`.

**Fora (com a fase/destino):**
- Auto-cadastro pelo cliente; recuperação de senha por e-mail.
- Papéis/permissões dentro do portal (todo usuário-cliente vê tudo do seu cliente).
- Gestão em massa / importação.

## 3. Contexto do código atual

- **Backend:** `app/api/funcionarios.py` é o padrão a espelhar — router **sem prefixo**, rotas `/clientes/{cliente_id}/funcionarios` (aninhada) e `/funcionarios/{id}`, `_exige_cliente`, `get_current_usuario` (read) / `require_funcao("Administrador")` (write), registrado em `main.py`. `UsuarioCliente` (`app/models/usuario_cliente.py`): `id, cliente (BigInteger), nome, login, senha (text), email, precisa_redefinir_senha`; UNIQUE `(cliente, login)` (`uq_usuarios_cliente_login`). `hash_senha` em `app/core/security.py`. `Cliente` em models. Testes pytest/SQLite; fixtures `usuario_admin`, `usuario_comum` (Expedição), `db_session`, `client`.
- **Frontend:** `clientes/ClienteDetailPage.tsx` renderiza `FuncionariosSection` no modo edição; `FuncionariosSection.tsx` é o padrão (carrega via api, tabela, modal criar/editar, excluir com confirm). `clientes/api.ts` (`apiJson`/`apiVoid`, `funcionariosApi`). `useAuth`/`isAdmin`. Componentes `Table/Badge/Button/Spinner/Modal/Input`.

## 4. Backend

### 4.1 Schemas (`app/schemas/usuarios_cliente.py`)
- `UsuarioPortalOut { id: int, cliente: int, login: str, nome: str | None, email: str | None, precisa_redefinir_senha: bool }` (`from_attributes`). **Sem `senha`.**
- `UsuarioPortalCreate { login: str, nome: str | None = None, email: str | None = None, senha: str (min_length=8) }`.
- `UsuarioPortalUpdate { login: str | None = None, nome: str | None = None, email: str | None = None }`.
- `RedefinirSenhaClienteIn { nova_senha: str (min_length=8) }`.

### 4.2 Endpoints (`app/api/usuarios_cliente.py`, router sem prefixo, registrado em `main.py`)
`ADMIN = "Administrador"`. Helper `_exige_cliente(db, cliente_id)` (404).
- **`GET /clientes/{cliente_id}/usuarios-portal`** (`require_funcao(ADMIN)`) → 404 cliente; lista `UsuarioCliente` com `cliente == cliente_id`, `order_by id`. Retorna `list[UsuarioPortalOut]`.
- **`POST /clientes/{cliente_id}/usuarios-portal`** (`require_funcao(ADMIN)`) `UsuarioPortalCreate` → 404 cliente; se já existe `UsuarioCliente(cliente=cliente_id, login=dados.login)` → **409** "login já em uso para este cliente"; cria com `senha=hash_senha(dados.senha)`, `precisa_redefinir_senha=True`. 201 `UsuarioPortalOut`.
- **`PATCH /usuarios-portal/{item_id}`** (`require_funcao(ADMIN)`) `UsuarioPortalUpdate` → 404; se `login` muda, valida unicidade `(cliente, login)` (excluindo o próprio) → 409; aplica `nome`/`email`/`login`. `UsuarioPortalOut`.
- **`POST /usuarios-portal/{item_id}/redefinir-senha`** (`require_funcao(ADMIN)`) `RedefinirSenhaClienteIn` → 404; `senha=hash_senha(nova_senha)`, `precisa_redefinir_senha=True`. 204.
- **`DELETE /usuarios-portal/{item_id}`** (`require_funcao(ADMIN)`) → 404; remove. 204.

### 4.3 Testes (pytest)
- Criar: 201, `precisa_redefinir_senha=True` no retorno, **sem campo `senha`**; a senha gravada autentica via `/auth/login-portal` (que então sinaliza `precisa_redefinir`).
- 409: mesmo `(cliente, login)` duas vezes; mesmo `login` em outro cliente → ok (201).
- Listar por cliente (só os do cliente; 404 cliente inexistente).
- Patch: muda nome/email; trocar login para um já usado no mesmo cliente → 409.
- Redefinir-senha: 204 e `precisa_redefinir_senha` volta a `True` (criar com flag, redefinir mantém true).
- Delete: 204; depois some da lista.
- 403: `usuario_comum` (não-admin) em GET/POST/PATCH/redefinir/DELETE.

## 5. Frontend

### 5.1 API (`clientes/api.ts` — estender)
- `UsuarioPortal { id, cliente, login, nome, email, precisa_redefinir_senha }`; `UsuarioPortalPayload { login, nome, email, senha }`.
- `usuariosPortalApi`: `listarPorCliente(clienteId)` (`GET /clientes/{id}/usuarios-portal`), `criar(clienteId, payload)` (`POST` mesmo path), `atualizar(id, {login?,nome?,email?})` (`PATCH /usuarios-portal/{id}`), `redefinirSenha(id, novaSenha)` (`POST /usuarios-portal/{id}/redefinir-senha`, body `{nova_senha}`), `excluir(id)` (`DELETE /usuarios-portal/{id}`).

### 5.2 `UsuariosPortalSection` (`clientes/UsuariosPortalSection.tsx`)
Espelha `FuncionariosSection`. Props `{ clienteId: number }` (só renderizada para admin). Carrega `listarPorCliente`. Tabela: **Login, Nome, E-mail, Status** (`Badge` warning "Senha temporária" se `precisa_redefinir_senha`, senão `Badge` neutral/primary "Ativa") + Ações (Editar, Redefinir senha, Excluir).
- **Criar** (modal): login, nome, e-mail, senha (≥8). 409 inline ("login já em uso para este cliente").
- **Editar** (modal): login, nome, e-mail (sem senha).
- **Redefinir senha** (modal): só `nova_senha` (≥8) → `redefinirSenha`.
- **Excluir**: `window.confirm`.

### 5.3 `ClienteDetailPage`
Renderiza `<UsuariosPortalSection clienteId={Number(id)} />` **apenas quando `isAdmin(user)`** e no modo edição (cliente existente), logo após a seção de Funcionários.

### 5.4 Testes (Vitest)
- `clientes/api.test.ts` (estender, ou novo `usuarios-portal.api.test.ts`): `usuariosPortalApi` — paths/métodos de listar/criar/atualizar/redefinirSenha/excluir; propaga `ApiError` (409).
- Telas: `tsc -b` + `lint` + `build`.

## 6. Verificação / E2E
- pytest + `npm run test` verdes; `tsc`/`lint`/`build` limpos.
- **E2E:** abrir o detalhe de um cliente (como admin), criar um usuário do portal com senha temporária; logar no `/portal` com ele → cair no "Defina sua nova senha" (integração 6A) → entrar; voltar ao detalhe e excluir o usuário de teste. O controlador avisa antes de escrever no banco real e **remove o usuário de teste ao fim**.

## 7. Critérios de aceite
- No detalhe do cliente, o admin cria/edita/exclui usuários do portal e redefine senha; login duplicado no mesmo cliente → 409; a senha é sempre temporária; a senha nunca volta na resposta.
- Não-admin não vê a seção nem acessa os endpoints (403).
- O usuário criado loga no portal e passa pelo reset forçado (6A).
- pytest + `npm run test` verdes; `tsc`/`lint`/`build` limpos; E2E ok. **Fase 6 e roadmap completos.**

## 8. Fora de escopo (reafirmando)
Auto-cadastro/recuperação por e-mail; papéis dentro do portal; gestão em massa.
