# GestorHS — Fase 5A (Portal do cliente — Auth & Shell)

**Data:** 2026-06-04
**Status:** Aprovado para implementação
**Parte de:** Fase 5 (Portal do cliente), sub-projeto 1 de 3 — **5A auth & shell** → 5B páginas informativas (frota/certificados/OS) → 5C solicitar recalibração.
**Depende de:** Backend de auth de cliente já existente (`/auth/login-portal`, `get_current_cliente` validando o claim `cliente`; `UsuarioCliente` com `(cliente, login)` único). Frontend Fase 0 (design system, `lib/api` com refresh single-flight, `auth-storage`, árvore de rotas `/portal` lazy).

---

## 1. Objetivo

Construir a fundação navegável do portal do cliente (`/portal`): login multi-tenant por documento (CNPJ/CPF), contexto de autenticação próprio, shell/layout e home com resumo. É a base sobre a qual a 5B (páginas informativas) e a 5C (solicitações) serão construídas. O isolamento de tenant é a preocupação central: um cliente nunca vê dados de outro.

## 2. Escopo

**Dentro:**
- Backend: `/auth/login-portal` passa a aceitar **documento** (CNPJ/CPF) no lugar do id numérico; `GET /portal/me` e `GET /portal/resumo` (escopados ao `cliente` do token).
- Frontend: `PortalAuthProvider`/`usePortalAuth`, `PortalProtectedRoute`, `PortalLoginPage`, `PortalLayout` (shell), `PortalHomePage` (resumo), `portal/api.ts`, rotas.

**Fora (com a fase/destino):**
- Páginas de frota/certificados/OS do portal → **5B** (nesta fase, itens de nav levam a placeholders "em breve").
- Solicitar recalibração + tabela `solicitacoes` → **5C**.
- Auto-atendimento de senha (reset/troca pelo cliente) e reset forçado no 1º login → **Fase 6**.
- Cadastro self-service de usuário-cliente (criados pela equipe interna).

## 3. Contexto do código atual

- **Backend:** `app/api/auth.py` → `login_portal` recebe `PortalLoginRequest { cliente: int, login, senha }`, filtra `UsuarioCliente` por `(cliente, login)`, usa `_autenticar` (anti-enumeração: verify contra `_DUMMY_HASH` quando não existe; 403 se `precisa_redefinir_senha`; 401 se senha errada) e emite token com claim `cliente` (`criar_access_token(sub, tipo="cliente", cliente=...)`). `app/api/deps.py` → `get_current_cliente` valida `tipo == "cliente"` e `dados["cliente"] == cli.cliente`. `Cliente` tem `cgc` (varchar14, CNPJ em dígitos) e `cpf` (varchar11). `UsuarioCliente` tem `cliente, nome, login, senha, email, precisa_redefinir_senha`.
- **Frontend:** `App.tsx` carrega duas árvores lazy (`/app` e `/portal`). `src/portal/routes.tsx` hoje é placeholder (`PortalRoutes` → `PlaceholderPage`). `src/auth/AuthContext.tsx` (`AuthProvider`/`useAuth`) é o modelo a espelhar: hidrata via `apiJson('/auth/me')` se há token, `login()` faz POST + `setTokens` + carrega me, `logout()` limpa. `lib/api` expõe `apiJson`/`apiFetch` (refresh single-flight no 401) e `setOnUnauthorized(cb)` (callback global único). `lib/auth-storage` (`getTokens`/`setTokens`/`clearTokens`). Componentes `Input`/`Button`/`Spinner`; `cn()`.

## 4. Backend

### 4.1 Login por documento
- `app/schemas/auth.py`: `PortalLoginRequest` passa a `{ documento: str, login: str, senha: str }` (remove `cliente: int`).
- `app/api/auth.py` `login_portal`:
  - `doc = "".join(c for c in dados.documento if c.isdigit())` (normaliza CNPJ/CPF).
  - `cli_empresa = db.query(Cliente).filter(or_(Cliente.cgc == doc, Cliente.cpf == doc)).first()` (quando `doc` não vazio).
  - Se `cli_empresa` é `None` → `_autenticar(None, dados.senha)` (mesmo timing/401 anti-enumeração; não revela se o documento existe).
  - Senão: `cli = db.query(UsuarioCliente).filter(UsuarioCliente.cliente == cli_empresa.id, UsuarioCliente.login == dados.login).first()`; `_autenticar(cli, dados.senha)`; emite token com `cliente=cli.cliente` (igual a hoje).
- `from sqlalchemy import or_` no topo.

### 4.2 `GET /portal/me` e `GET /portal/resumo`
Novo router `app/api/portal.py` (prefix `/portal`, tag "portal"), registrado em `main.py`. Schemas em `app/schemas/portal.py`. **Toda rota usa `get_current_cliente` e filtra pelo `cliente` do token — nunca por parâmetro.**

- `GET /portal/me` → `PortalMeOut { id, login, nome, cliente, cliente_nome }`. Carrega o `UsuarioCliente` (do token) + o nome da empresa (`Cliente.nome` via `cli.cliente`).
- `GET /portal/resumo` → `PortalResumoOut { aparelhos, vencidos, os_andamento }`:
  - `aparelhos` = `count(EquipamentoCliente)` com `cliente == token.cliente` e `ativo == True`.
  - `vencidos` = idem + `prox_calibragem < hoje`.
  - `os_andamento` = `count(Ordem)` com `cliente == token.cliente` e `fase IN (4,5,6,7)`.

### 4.3 Schemas (`app/schemas/portal.py`)
- `PortalMeOut { id: int, login: str, nome: str | None, cliente: int, cliente_nome: str | None }`.
- `PortalResumoOut { aparelhos: int, vencidos: int, os_andamento: int }`.

### 4.4 Testes (pytest)
- Fixture: um `Cliente` com `cgc="11222333000144"`; um `UsuarioCliente(cliente=<id>, login="contato", senha=hash("portal123"))`; alguns `EquipamentoCliente`/`Ordem` desse cliente (+ de outro cliente, para provar isolamento).
- Login por documento: `POST /auth/login-portal {documento:"11.222.333/0001-44", login:"contato", senha:"portal123"}` → 200 com token; documento inexistente → 401; senha errada → 401; documento certo + login errado → 401.
- `GET /portal/me` com o token do cliente → dados certos (cliente_nome). Sem token / com token de **usuário interno** (tipo "usuario") → 401.
- `GET /portal/resumo` → contagens só do cliente do token (não conta aparelhos/OS de outro cliente).

## 5. Frontend (`frontend/src/portal/`)

### 5.1 Auth context
- `PortalAuthProvider` + `usePortalAuth` (espelha `AuthContext.tsx`, independente): estado `cliente: PortalMe | null`, `loading`. Hidrata via `portalApi.me()` se há token; `login(documento, login, senha)` faz POST `/auth/login-portal` + `setTokens` + carrega `me`; `logout()` limpa. Usa `setOnUnauthorized(() => setCliente(null))` no efeito (callback global; só uma árvore — /app ou /portal — está montada por vez via lazy).
- `PortalProtectedRoute`: enquanto `loading`, `Spinner`; se `!cliente`, `<Navigate to="/portal/login">`; senão renderiza os filhos.

### 5.2 API (`portal/api.ts`)
- Tipos `PortalMe { id, login, nome, cliente, cliente_nome }`, `PortalResumo { aparelhos, vencidos, os_andamento }`.
- `portalApi.me()` (`GET /portal/me`), `portalApi.resumo()` (`GET /portal/resumo`).

### 5.3 Login (`PortalLoginPage`, `/portal/login`)
- Form: **Documento (CNPJ/CPF)**, **Login**, **Senha**; botão Entrar. Chama `usePortalAuth().login(...)`. Erros: 401 → "Credenciais inválidas."; 403 → "Conta bloqueada — contate a Health Safety."; outros → genérico. Sucesso → `navigate('/portal')`. Se já autenticado, redireciona para `/portal`.

### 5.4 Shell (`PortalLayout`)
- Topbar: marca + **nome da empresa** (`cliente.cliente_nome`) + botão **Sair**. Navegação com **Início** (`/portal`), **Minha frota** (`/portal/frota`), **Certificados** (`/portal/certificados`), **Minhas OS** (`/portal/os`) — os três últimos apontam para um `EmBrevePage` ("Disponível em breve") até a 5B. Visual do design system (emerald, dark-first), mais enxuto que o `/app`.

### 5.5 Home (`PortalHomePage`, `/portal`)
- Saudação "Olá, {empresa}"; **3 cartões**: Aparelhos, Vencidos (destaque danger se > 0), OS em andamento — de `portalApi.resumo()`. `Spinner`/erros no padrão.

### 5.6 Rotas (`portal/routes.tsx`)
- Envolve tudo em `PortalAuthProvider`. `/portal/login` (público) + rotas protegidas (`PortalProtectedRoute` + `PortalLayout`): `/portal` (home), `/portal/frota|certificados|os` (`EmBrevePage`). Fallback `*` → `/portal`.

### 5.7 Testes (Vitest)
- `portal/api.test.ts`: `me`/`resumo` nos paths certos; propaga `ApiError`.
- `PortalAuthProvider`: `login` guarda token e carrega `me`; `logout` limpa (padrão dos testes de auth do `/app`).
- Telas: `tsc -b` + `lint` + `build`.

## 6. Verificação / E2E
- pytest + `npm run test` verdes; `tsc`/`lint`/`build` limpos.
- **E2E manual:** criar um `UsuarioCliente` de teste (script `criar_usuario_cliente` ou direto no banco) ligado a um cliente com CNPJ conhecido; logar em `/portal/login` com documento+login+senha; ver a home com o nome da empresa e os contadores; navegar nos placeholders; sair. Não-destrutivo (só leitura, exceto criar o usuário-cliente de teste — claramente marcado).

## 7. Critérios de aceite
- Um cliente acessa `/portal/login`, informa CNPJ/CPF + login + senha e entra na home com o nome da empresa e os 3 contadores; navegação e logout funcionam; rotas do portal são protegidas (sem token → login).
- Login resolve o documento (com ou sem pontuação) para o cliente; documento/credenciais inválidos → 401 sem revelar o que falhou; conta marcada p/ redefinir → mensagem de conta bloqueada.
- Isolamento: `/portal/me` e `/portal/resumo` retornam só dados do cliente do token; token de usuário interno não acessa `/portal/*`.
- pytest + `npm run test` verdes; `tsc`/`lint`/`build` limpos; E2E ok.

## 8. Fora de escopo (reafirmando)
Páginas informativas (5B); solicitações (5C); auto-atendimento/reset de senha (Fase 6); cadastro self-service de usuário-cliente.
