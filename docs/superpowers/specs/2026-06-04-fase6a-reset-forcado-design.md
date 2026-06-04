# GestorHS — Fase 6A (Reset forçado de senha no 1º login)

**Data:** 2026-06-04
**Status:** Aprovado para implementação
**Parte de:** Fase 6 (Migração de credenciais), sub-projeto 1 de 2 — **6A reset forçado** → 6B gestão de usuários do portal pelo admin.
**Depende de:** Auth existente (`/auth/login`, `/auth/login-portal`, `_autenticar`, `precisa_redefinir_senha`); 1A (`/usuarios/{id}/redefinir-senha`); 5A (`PortalAuthContext`, login por documento). Migração 0001 deixou as contas legadas com `senha=''` e `precisa_redefinir_senha=true`.

---

## 1. Objetivo

Tornar operável a migração das credenciais: quando uma conta tem `precisa_redefinir_senha=true`, o login deixa de retornar 403 e passa a um fluxo "defina sua nova senha" (internos e portal). O admin entrega senhas **temporárias** e o usuário define a sua no primeiro acesso. É o mecanismo; a gestão de usuários do portal pelo admin vem na 6B.

## 2. Escopo

**Dentro:**
- Backend: login (equipe e portal) sinaliza "precisa redefinir" após verificar a senha; `POST /auth/definir-senha` e `/auth/definir-senha-portal`; `redefinir-senha` (admin) passa a gravar senha temporária.
- Frontend: passo "Defina sua nova senha" no login do `/app` e do `/portal`; métodos `definirSenha` nos contextos de auth.

**Fora (com a fase/destino):**
- Gestão de usuários do portal pelo admin (criar/listar/resetar `usuarios_cliente`) → **6B**.
- "Esqueci minha senha" / recuperação por e-mail (sem envio de e-mail no v1).
- Expiração de senha temporária; política de complexidade além do mínimo de 8.

## 3. Contexto do código atual

- **Backend:** `app/api/auth.py` → `_autenticar(registro, senha)`: se `registro is None` faz dummy-verify + 401; **se `precisa_redefinir_senha` → 403 (antes de verificar a senha)**; se senha errada → 401. `login`/`login_portal` retornam `Token`. `login_portal` resolve `documento`→`Cliente` (5A). `app/api/usuarios.py` → `redefinir_senha` grava `hash_senha(nova)` e seta `precisa_redefinir_senha=False`. `app/core/security.py` → `hash_senha`/`verificar_senha` (argon2; hash vazio `''` → verify retorna False). Schemas em `app/schemas/auth.py` (`Token`, `PortalLoginRequest{documento,login,senha}`, `TrocarSenhaIn{senha_atual, nova_senha(min 8)}`). `get_current_usuario`/`get_current_cliente`.
- **Frontend:** `auth/AuthContext.tsx` (`login(login,senha)` → POST /auth/login + setTokens + carrega `/auth/me`); `app/pages/LoginPage.tsx`. `portal/PortalAuthContext.tsx` (`login(documento,login,senha)` → /auth/login-portal); `portal/PortalLoginPage.tsx`. `lib/api` (`apiJson`), `lib/auth-storage` (`setTokens`). Testes Vitest de auth no padrão mock-fetch.

## 4. Backend

### 4.1 Login sinaliza "precisa redefinir" (`app/api/auth.py`)
- Novo schema `LoginOut`: `{ precisa_redefinir: bool = False, access_token: str | None = None, refresh_token: str | None = None, token_type: str = "bearer" }`.
- Refatorar a autenticação: helper `_verificar_credenciais(registro, senha)` → se `registro is None`: dummy-verify + 401; se `not verificar_senha(senha, registro.senha)`: 401. (Remove o 403 daqui — a flag deixa de bloquear o login.)
- `POST /auth/login` (`response_model=LoginOut`): acha o usuário; `_verificar_credenciais`; se `usuario.precisa_redefinir_senha` → `LoginOut(precisa_redefinir=True)`; senão → `LoginOut(access_token=..., refresh_token=...)`.
- `POST /auth/login-portal` (`response_model=LoginOut`): resolve documento→cliente→`(cliente,login)`; `_verificar_credenciais`; mesma lógica (token de cliente com claim `cliente`).

> `LoginOut` com tokens opcionais cobre os dois casos; o frontend distingue por `precisa_redefinir`.

### 4.2 Definir senha (`POST /auth/definir-senha`, `POST /auth/definir-senha-portal`)
- Schemas: `DefinirSenhaIn { login: str, senha_atual: str, nova_senha: str (min 8) }`; `DefinirSenhaPortalIn { documento: str, login: str, senha_atual: str, nova_senha: str (min 8) }`.
- `definir-senha` (equipe, `response_model=Token`): acha o usuário por `login`; `_verificar_credenciais(usuario, senha_atual)` (401 se inválido); se **não** `precisa_redefinir_senha` → 400 "conta não requer redefinição"; grava `senha=hash_senha(nova_senha)`, `precisa_redefinir_senha=False`; retorna `Token` (login automático).
- `definir-senha-portal` (portal, `response_model=Token`): resolve documento→cliente→`(cliente,login)`; idem; token de cliente.

### 4.3 `redefinir-senha` do admin (`app/api/usuarios.py`)
- Passa a gravar `senha=hash_senha(nova_senha)` e `precisa_redefinir_senha=True` (temporária — força a troca no próximo login).

### 4.4 Testes (pytest)
- Login: usuário com `precisa_redefinir_senha=true` + senha correta → 200 `{precisa_redefinir:true}` sem tokens; senha errada → 401; usuário normal → tokens (`precisa_redefinir` ausente/false). Idem portal (com documento).
- `definir-senha`: define a nova, limpa o flag, retorna tokens; login normal subsequente funciona; `senha_atual` errada → 401; login inexistente → 401; conta sem flag → 400. Idem `definir-senha-portal`.
- `redefinir-senha` (admin): após o reset, `precisa_redefinir_senha` fica `True` e o login passa a sinalizar `precisa_redefinir` (atualizar o teste 1A que assumia o flag limpo).
- Ajustar quaisquer testes de login/login-portal que esperavam `Token` direto (agora `LoginOut`) ou o 403 antigo.

## 5. Frontend

### 5.1 `/app` (`auth/AuthContext.tsx`, `app/pages/LoginPage.tsx`)
- `AuthContext`: `login(login, senha)` passa a retornar `LoginResult` = `{ precisa_redefinir: true }` ou `{ precisa_redefinir: false }` (com user já carregado, como hoje). Novo `definirSenha(login, senhaAtual, novaSenha)`: POST `/auth/definir-senha` → `setTokens` → carrega `/auth/me` → seta `user`.
- `LoginPage`: estado `etapa: 'login' | 'definir'`. No submit do login, se o resultado tem `precisa_redefinir` → guarda `login`/`senha` digitados e vai para a etapa "definir". A etapa "Defina sua nova senha" pede **nova senha** + **confirmação** (valida ≥8 e iguais) → `definirSenha(loginGuardado, senhaGuardada, novaSenha)` → `navigate('/app')`. Erros (401/400) inline; botão "voltar ao login".

### 5.2 `/portal` (`portal/PortalAuthContext.tsx`, `portal/PortalLoginPage.tsx`)
- `PortalAuthContext`: `login(documento, login, senha)` retorna `LoginResult`; novo `definirSenha(documento, login, senhaAtual, novaSenha)` → `/auth/definir-senha-portal`.
- `PortalLoginPage`: mesmo passo "Defina sua nova senha" (mantém documento + login + senha temporária).

### 5.3 Testes (Vitest)
- `AuthContext`: `login` que recebe `{precisa_redefinir:true}` NÃO autentica (user permanece null); `definirSenha` guarda token e carrega o me (user setado). `PortalAuthContext`: idem com cliente.
- Telas: `tsc -b` + `lint` + `build`.

## 6. Verificação / E2E
- pytest + `npm run test` verdes; `tsc`/`lint`/`build` limpos.
- **E2E:** (interno) admin cria um usuário de teste e usa `redefinir-senha` para dar uma senha temporária; logar com ela → cair em "Defina sua nova senha" → definir → entrar; o 2º login com a nova senha é normal. (Portal) criar um `usuarios_cliente` de teste com `precisa_redefinir_senha=true` + senha temporária; mesmo fluxo no `/portal`. O controlador avisa antes de mexer no banco real e **remove os usuários de teste ao fim**.

## 7. Critérios de aceite
- Conta com senha temporária (interno ou portal) loga, é levada a definir uma nova senha (com confirmação, ≥8) e entra autenticada; o flag é limpo; o próximo login é normal.
- Login inexistente/senha errada → 401 (sem vazar existência); conta sem flag → 400 no `definir-senha`.
- `redefinir-senha` do admin deixa a conta em estado temporário (força a troca).
- pytest + `npm run test` verdes; `tsc`/`lint`/`build` limpos; E2E ok.

## 8. Fora de escopo (reafirmando)
Gestão de usuários do portal pelo admin (6B); recuperação por e-mail; expiração de temporária; política de complexidade.
