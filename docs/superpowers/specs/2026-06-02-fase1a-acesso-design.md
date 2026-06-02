# GestorHS — Fase 1A (Acesso)

**Data:** 2026-06-02
**Status:** Aprovado para implementação
**Depende de:** Backend Fundação + Auth (pronto) · Frontend Fase 0 (pronto, na `main`)
**Parte de:** Fase 1 do roadmap (Acesso & Cadastros base), sub-projeto 1 de 2. O sub-projeto 1B (Cadastros base) vem depois e reusa os padrões estabelecidos aqui.

---

## 1. Objetivo

Entregar a gestão de **acesso interno**: o Administrador cria, edita e remove usuários internos, atribui-lhes uma função, e reseta senhas; qualquer usuário troca a própria senha; e a navegação esconde o que não é do papel do usuário. Ao fim, o sistema controla "quem entra e o que cada um vê" — a base sobre a qual os cadastros (1B) e os módulos seguintes aplicam permissão.

## 2. Escopo

**Dentro:**
- CRUD de **usuários internos** (`usuarios`).
- **Listar funções** e **atribuí-las** a usuários.
- Ciclo de senha: admin define na criação, admin **reseta**, usuário **troca a própria**.
- **Navegação/rotas gated por função** (Administrador vs. não).
- `/auth/me` passa a expor a **descrição da função** do usuário.

**Fora (deferido, com a fase de destino):**
- CRUD de funções customizadas e mapa função→fase → **Fase 3** (quando a função governa a fila de OS).
- Reset-forçado-no-1º-login e migração de credenciais legadas → **Fase 6**.
- Cadastros de domínio (clientes, catálogo, marcas, categorias, grupos, funcionários) → **Fase 1B**.
- Portal do cliente / usuários-cliente → **Fase 5**.

## 3. Contexto do código atual

- Backend FastAPI + SQLAlchemy 2 + Pydantic v2, padrão `tiny-integrador` (`app/core`, `app/models`, `app/schemas`, `app/api`). Existem os modelos `Usuario`, `Funcao`, `UsuarioCliente`; o router `auth`; e `app/api/deps.py` com `get_current_usuario`, `get_current_cliente` e `require_funcao(*descricoes)`.
- `Usuario`: `id, nome, login(unique), senha(text/hash argon2), email, funcao_id(FK funcoes), precisa_redefinir_senha(bool)`.
- `Funcao`: `id, descricao(unique)`. Quatro papéis semeados: Administrador, Expedição, Laboratório, Comercial Pós-Vendas.
- `/auth/login` retorna **403 "Senha precisa ser redefinida"** quando `precisa_redefinir_senha=true`. Não há endpoint de troca/reset de senha ainda.
- Frontend Fase 0: design system, `AuthContext`/`useAuth`, `ProtectedRoute`, cliente `api.ts` (`apiJson`, `ApiError`), shell (Sidebar/Topbar/MainLayout), componentes (Table, TH, TD, Modal, Button, Input, Select, Badge, Spinner). `User` = `{id, nome, login, email, funcao_id}`. Rotas `/app/*` (lazy, protegida) e `/portal/*`.

## 4. Backend — endpoints

Novos routers por domínio: `app/api/funcoes.py` e `app/api/usuarios.py`, registrados em `app/main.py`. Schemas em `app/schemas/acesso.py`.

| Método | Rota | Corpo | Autorização | Notas |
|---|---|---|---|---|
| GET | `/funcoes` | — | Administrador | lista `{id, descricao}` |
| GET | `/usuarios` | — | Administrador | lista `UsuarioListOut` |
| POST | `/usuarios` | `UsuarioCreate` | Administrador | hash argon2; `login` duplicado → **409** |
| GET | `/usuarios/{id}` | — | Administrador | `UsuarioListOut`; 404 se não existe |
| PATCH | `/usuarios/{id}` | `UsuarioUpdate` | Administrador | campos opcionais; **não** altera senha; `login` duplicado → 409 |
| DELETE | `/usuarios/{id}` | — | Administrador | **guardas** (ver 4.2) |
| POST | `/usuarios/{id}/redefinir-senha` | `RedefinirSenhaIn` | Administrador | grava hash; `precisa_redefinir_senha=false` |
| POST | `/auth/trocar-senha` | `TrocarSenhaIn` | usuário interno autenticado | valida a senha atual |

### 4.1 Schemas (`app/schemas/acesso.py`)
- `FuncaoOut` — `{id, descricao}`.
- `UsuarioListOut` — `{id, nome, login, email, funcao_id, funcao: str | None, precisa_redefinir_senha}`.
- `UsuarioCreate` — `{nome, login, email: str | None, senha, funcao_id: int | None}`; `senha` com **mínimo 8** caracteres.
- `UsuarioUpdate` — `{nome?, email?, funcao_id?, login?}` (todos opcionais).
- `RedefinirSenhaIn` — `{nova_senha}` (mín. 8).
- `TrocarSenhaIn` — `{senha_atual, nova_senha}` (nova mín. 8).

### 4.2 Guardas e regras
- **Login único:** colisão em criar/editar → 409 "login já em uso".
- **Não excluir a si mesmo:** `DELETE /usuarios/{id}` onde `id == usuário atual` → 400 "não é possível excluir o próprio usuário".
- **Não excluir o último Administrador:** se o alvo é o único usuário com função Administrador → 400 "não é possível excluir o último administrador". (A mesma proteção vale para *rebaixar* via PATCH: se a edição tira o último admin da função Administrador → 400.)
- **Trocar a própria senha:** `senha_atual` incorreta → 400/401 "senha atual incorreta"; grava o novo hash.
- **Senha mínima:** validação Pydantic (≥ 8) em todos os pontos que recebem senha.
- A criação deixa `precisa_redefinir_senha=false` (admin define a senha real).

### 4.3 `/auth/me` com a função
`/auth/me` passa a devolver a **descrição da função**. Adiciona-se um relationship `Usuario.funcao → Funcao` (não-quebra; o FK já existe) e o campo `funcao: str | None` ao `UsuarioOut` (em `app/schemas/auth.py`), populado a partir de `usuario.funcao.descricao`. O front deriva `isAdmin = user.funcao === "Administrador"`.

## 5. Frontend

- **AuthContext:** a interface `User` ganha `funcao: string | null`; exporta-se um helper `isAdmin(user)` (ou `user?.funcao === 'Administrador'`).
- **Módulo de API de acesso** (`src/app/acesso/api.ts`): funções tipadas sobre `apiJson` — `listarFuncoes`, `listarUsuarios`, `criarUsuario`, `obterUsuario`, `atualizarUsuario`, `excluirUsuario`, `redefinirSenha`, `trocarMinhaSenha`.
- **`UsuariosPage` (`/app/usuarios`, admin):** `Table` (nome, login, email, função via `Badge`, ações) + botão "Novo usuário" → `Modal` de criação (nome, login, email, senha, `Select` de função). Edição via `Modal` (sem senha). Ações por linha: editar, redefinir senha (`Modal`), excluir (confirmação). Erros (incl. 409) mostrados inline. Estados de loading/empty com os padrões do design system.
- **`MinhaContaPage` (`/app/conta`, todos):** form "Trocar minha senha" (senha atual, nova, confirmação) ligado em `POST /auth/trocar-senha`; sucesso/erro inline.
- **Topbar:** o avatar vira um **dropdown** (padrão da seção 6.6 do `DESIGN_SYSTEM.md`) com "Minha conta" (→ `/app/conta`) e "Sair". O ícone de logout solto sai (evita duplicação); o toggle de tema permanece.
- **Sidebar:** `NAV_ITEMS` ganha `adminOnly?: boolean`; a lista é filtrada por `isAdmin`. "Usuários" é `adminOnly`. "Dashboard" para todos.
- **Rotas (`app/routes.tsx`):** adicionar `/app/usuarios` → `UsuariosPage` e `/app/conta` → `MinhaContaPage`. A `UsuariosPage` é admin-only; se um não-admin acessar direto, a API responde 403 e a página mostra um aviso de acesso negado (esconder é só UX; a API manda).

## 6. Testes

- **Backend (pytest, junto dos atuais; SQLite):**
  - Authz: não-admin → 403 em todas as rotas de gestão (`/funcoes`, `/usuarios*`).
  - Criar usuário: hash gravado (não texto puro), `login` duplicado → 409.
  - Listar e obter; obter inexistente → 404.
  - Editar: troca de função reflete; `login` duplicado → 409.
  - Excluir: self-delete → 400; último admin → 400; exclusão normal OK.
  - Admin redefinir senha: novo hash funciona no login.
  - Trocar a própria senha: atual incorreta → erro; correta → novo hash autentica.
  - `/auth/me` retorna `funcao` (descrição) correta.
- **Frontend (Vitest + RTL, lógica como na Fase 0):**
  - Gating da nav: item "Usuários" some para não-admin e aparece para admin.
  - Módulo `acesso/api.ts`: chamadas batem nos endpoints/métodos certos e propagam `ApiError`.
  - Telas visuais (UsuariosPage, MinhaContaPage, dropdown da Topbar) verificadas por `tsc -b` + `lint` + E2E manual.

## 7. Critérios de aceite

- Admin loga → vê "Usuários" na nav → lista, cria (com função e senha), edita, reseta senha e exclui usuários; as guardas (self-delete, último admin, login duplicado) funcionam.
- Não-admin **não** vê "Usuários" e recebe 403 se forçar `/app/usuarios`.
- Qualquer usuário troca a própria senha em `/app/conta`; senha atual errada é rejeitada.
- `/auth/me` devolve a descrição da função; a nav reage ao papel.
- `npm run test` (front) e `pytest` (back) verdes; `tsc -b`, `lint` e `build` limpos.
- Verificação E2E manual no navegador contra o backend no Docker.

## 8. Fora de escopo (reafirmando)
CRUD de funções customizadas, mapa função→fase, reset-forçado-no-1º-login, cadastros de domínio, usuários-cliente/portal. Cada um na sua fase.
