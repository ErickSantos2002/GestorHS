# GestorHS — Frontend Fase 0 (Fundação)

**Data:** 2026-06-01
**Status:** Aprovado para implementação
**Depende de:** Backend Fundação + Auth (pronto, na `main`) · Design system do TaskHS (`DESIGN_SYSTEM.md`)

---

## 1. Objetivo

Montar a fundação técnica do frontend do GestorHS: portar o design system do TaskHS, configurar o roteamento em duas árvores (`/app` da equipe e `/portal` do cliente, lazy), e entregar a autenticação da equipe ligada no backend real. Ao fim da fase, um funcionário faz login de verdade e cai num shell navegável; o `/portal` existe como esqueleto lazy.

Nada de feature de domínio aqui (cadastros, OS, etc.) — só a casca sobre a qual a Fase 1 será construída.

## 2. Contexto

- `frontend/` hoje é o scaffold limpo do Vite: **React 19.2 + TypeScript 6 + Vite 8**, sem Tailwind, sem router, sem auth. `App.tsx`/`index.css` ainda são o template default.
- O backend roda em **`http://localhost:8000`** (Docker Desktop, `docker compose up -d`), conectado ao Postgres remoto (9998). CORS já libera `localhost:5173/5174`.
- O design system está documentado em `DESIGN_SYSTEM.md` (Tailwind v4 `@theme`, DM Sans, emerald `#10b981`, dark-first, shell sidebar+topbar, `cn()`, sem lib de UI). O porte é quase literal.

### Contrato de auth do backend (confirmado no código)

| Rota | Corpo | Resposta |
|---|---|---|
| `POST /auth/login` | `{login, senha}` | `{access_token, refresh_token, token_type}` |
| `POST /auth/login-portal` | `{cliente:int, login, senha}` | mesmo `Token` |
| `GET /auth/me` | — (Bearer) | `{id, nome, login, email, funcao_id}` |
| `POST /auth/refresh` | `{refresh_token}` | novo `Token` |

## 3. Decisões (travadas no brainstorming)

1. **Token + refresh:** `access` e `refresh` em **localStorage**; um fetch wrapper central injeta o `Bearer` e, ao receber **401**, dispara **um** `/auth/refresh` (single-flight) e repete a request. Falha no refresh → limpa tokens e redireciona para `/login`.
2. **Componentes base:** construir a **biblioteca completa** dos 10 componentes do Épico 0.1 agora, em `components/ui/`.
3. **Testes:** **Vitest + React Testing Library**, com **TDD na lógica de auth** (api client, AuthContext, ProtectedRoute, auth-storage). Componentes puramente visuais não são testados nesta fase.
4. **`/portal`:** só o **esqueleto lazy + placeholder**. Login/shell do portal e a UX do tenant ficam para a Fase 5.

## 4. Dependências a adicionar

- **Runtime:** `react-router-dom@^7`, `clsx`, `tailwind-merge`
- **Build (dev):** `tailwindcss@^4`, `@tailwindcss/vite@^4`
- **Teste (dev):** `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`

`@dnd-kit` **não** entra agora — o kanban é Fase 3 (YAGNI).

## 5. Estrutura de arquivos

```
frontend/
  index.html               # anti-FOUC, lang="pt-BR", title GestorHS
  vite.config.ts           # + plugin tailwindcss; config de teste (vitest)
  .env.example             # VITE_API_URL=http://localhost:8000
  src/
    index.css              # @theme + overrides dark + base/scrollbar/glow (Seção 1 do DS)
    main.tsx               # monta <App/>
    App.tsx                # Router: árvores /app e /portal lazy + Suspense
    lib/
      utils.ts             # cn() (clsx + tailwind-merge)
      auth-storage.ts      # get/set/clear de tokens no localStorage
      api.ts               # fetch wrapper: baseURL + Bearer + refresh-no-401 (single-flight)
    auth/
      AuthContext.tsx      # AuthProvider + useAuth (user, login, logout, loading)
      ProtectedRoute.tsx   # sem user → <Navigate to="/login">
    components/ui/
      Button.tsx Input.tsx Select.tsx Modal.tsx Drawer.tsx Table.tsx
      StatCard.tsx Badge.tsx Toggle.tsx Spinner.tsx
      icons.tsx            # SVGs inline (I*), convenção do DS
    layout/
      MainLayout.tsx       # shell: <Sidebar/> + <Topbar/>, toggle de tema
      Sidebar.tsx          # colapsável (w-64/w-18), nav com tooltip
      Topbar.tsx           # botões de ícone + avatar + (sino placeholder)
    app/
      routes.tsx           # rotas internas (equipe)
      pages/LoginPage.tsx  # ligada em POST /auth/login
      pages/DashboardPage.tsx   # placeholder ("Bem-vindo, {nome}")
    portal/
      routes.tsx           # lazy
      pages/PlaceholderPage.tsx # "Portal em construção"
    test/
      setup.ts             # jest-dom + cleanup
```

## 6. Roteamento (duas árvores, lazy)

- `/` → `<Navigate to="/app" replace>`
- `/login` → `LoginPage` (equipe) — topo, não-lazy
- `/app/*` → **chunk lazy** `AppRoutes`, envolto em `ProtectedRoute` → `MainLayout`
  - `/app` (index) → `DashboardPage` (placeholder)
  - `*` → `<Navigate to="/app" replace>`
- `/portal/*` → **chunk lazy** `PortalRoutes` → `PlaceholderPage`
- `<Suspense fallback={<Spinner/>}>` envolve as árvores lazy. O cliente baixa só o bundle do portal.

## 7. Fluxo de autenticação

- **Boot:** `AuthProvider` lê o token do localStorage; se houver, chama `GET /auth/me` para hidratar `user` (estado `loading` mostra spinner full-screen); 401 → limpa e trata como deslogado.
- **Login:** `POST /auth/login {login, senha}` → grava `access`+`refresh`, busca `/auth/me`, redireciona para `/app`. Erro → mensagem inline (padrão de erro da Seção 11 do DS).
- **`api.ts`:** injeta `Authorization: Bearer`; em **401**, dispara **um** `/auth/refresh` (promise single-flight compartilhada entre requests concorrentes); sucesso → regrava tokens e repete a request original; falha → limpa tokens e sinaliza logout (redirect para `/login`). O endpoint `/auth/login` em si não tenta refresh.
- **baseURL:** `import.meta.env.VITE_API_URL`, default `http://localhost:8000`. `.env.example` documenta.
- **Logout:** limpa tokens e `user`, navega para `/login`.

## 8. Tema (dark-first)

Porte literal do DS: bloco `@theme` (tokens + DM Sans), overrides `.dark`, inversão de `text-slate-*` no light, scrollbar custom, `.glow-primary`, base do `body`/`#root`. Script anti-FOUC no `<head>` do `index.html`. **Chave de storage:** `gestorhs-theme` (não `taskhs-theme`). O toggle vive no `MainLayout` e alterna a classe `.dark` no `<html>`.

## 9. Marca e textos

Logo "T" → **"GestorHS"** (chip `rounded-xl bg-primary/15`). `index.html` com `lang="pt-BR"` e `<title>GestorHS</title>`. Rodapé do login: "GestorHS · Health Safety". Mesmo emerald, mesma DM Sans. Itens de nav placeholder (ex.: Dashboard) — a nav real por função vem na Fase 1.

## 10. Testes (TDD na lógica)

Vitest + RTL, ambiente jsdom. Cobre as peças com lógica, com `fetch` mockado:

- **`auth-storage`** — get/set/clear; ausência de token retorna `null`.
- **`api`** — sucesso passa o Bearer; 401 dispara refresh e repete; refresh concorrente é single-flight (um só `/auth/refresh`); refresh falho limpa tokens e propaga o erro.
- **`AuthContext`** — `login` grava tokens e popula `user`; `logout` limpa; boot com token válido hidrata via `/me`; boot com token inválido (401) cai para deslogado.
- **`ProtectedRoute`** — sem `user` redireciona para `/login`; com `user` renderiza os filhos; durante `loading` mostra spinner.

Componentes puramente visuais (`components/ui/*`, shell) não são testados nesta fase.

## 11. Critérios de aceite

- `npm run dev` sobe o front; `npm run build` e `npm run lint` passam.
- `npm run test` verde (cobertura da lógica de auth acima).
- Com o backend no Docker (`:8000`), um funcionário faz **login real** e chega ao shell em `/app`; reload mantém a sessão; logout volta pra `/login`.
- Tema dark por padrão, toggle persiste em `localStorage["gestorhs-theme"]`, sem flash no reload.
- `/portal` carrega como chunk separado (placeholder), provando o code-splitting.
- 401 numa request protegida aciona refresh transparente; refresh expirado desloga.

## 12. Fora de escopo da Fase 0

- Login e shell do **portal** (Fase 5) e a UX do tenant.
- Qualquer feature de domínio (cadastros, frota, OS, alertas).
- Nav por função / permissões na UI (Fase 1).
- Kanban / `@dnd-kit` (Fase 3).
- Testes de componentes visuais e E2E de navegador.
