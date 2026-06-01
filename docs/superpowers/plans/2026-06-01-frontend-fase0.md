# Frontend Fase 0 (Fundação) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Montar a fundação do frontend do GestorHS — design system portado do TaskHS, roteamento em duas árvores lazy (`/app` equipe, `/portal` cliente) e login real da equipe contra o backend — deixando um shell navegável após o login.

**Architecture:** SPA React 19 + TypeScript + Vite 8. Tailwind v4 via `@tailwindcss/vite` (CSS-first `@theme`, dark-first). `react-router-dom@7` com árvores lazy. Autenticação por JWT em localStorage, com um fetch wrapper central que injeta o `Bearer` e faz refresh single-flight no 401. Lógica de auth coberta por testes (Vitest + RTL); componentes visuais portados literalmente do `DESIGN_SYSTEM.md`.

**Tech Stack:** React 19.2, TypeScript 6, Vite 8, Tailwind CSS v4, react-router-dom 7, clsx + tailwind-merge, Vitest 3 + React Testing Library + jsdom.

**Referências:**
- Spec: `docs/superpowers/specs/2026-06-01-frontend-fase0-design.md`
- Design system: `DESIGN_SYSTEM.md`
- Backend (já no ar via `docker compose up -d`, em `http://localhost:8000`): `POST /auth/login {login,senha}` → `{access_token,refresh_token,token_type}`; `GET /auth/me` → `{id,nome,login,email,funcao_id}`; `POST /auth/refresh {refresh_token}` → `Token`.

**Convenções de TS no projeto (do `tsconfig.app.json`):** `verbatimModuleSyntax` (use `import type` ou `{ type X }` para tipos), `noUnusedLocals`/`noUnusedParameters` (nada sem uso), `erasableSyntaxOnly` (sem enums/namespaces). `jsx: react-jsx` (não precisa importar React para JSX).

**Trabalho na branch:** todo este plano roda numa branch dedicada `feat/frontend-fase0`. Crie-a antes da Task 1:
```bash
git checkout -b feat/frontend-fase0
```

---

### Task 1: Tooling, tema e configuração de testes

Instala dependências, liga o Tailwind v4, porta o `@theme`/base do design system, configura o Vitest e prova que o ambiente de teste roda.

**Files:**
- Modify: `frontend/package.json` (deps + scripts)
- Modify: `frontend/vite.config.ts`
- Modify: `frontend/tsconfig.app.json`
- Modify: `frontend/index.html`
- Create: `frontend/.env.example`
- Replace: `frontend/src/index.css`
- Create: `frontend/src/test/setup.ts`
- Create: `frontend/src/test/sanity.test.ts`
- Delete: `frontend/src/App.css` (template default não usado)

- [ ] **Step 1: Instalar dependências**

Run (no diretório `frontend/`):
```bash
npm install react-router-dom@^7 clsx tailwind-merge
npm install -D tailwindcss@^4 @tailwindcss/vite@^4 vitest@^3 jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event
```
Expected: instala sem erro de peer (React 19 é compatível).

- [ ] **Step 2: Adicionar scripts de teste ao `package.json`**

No bloco `"scripts"`, adicione:
```json
    "test": "vitest run",
    "test:watch": "vitest"
```

- [ ] **Step 3: Configurar Vite + Vitest** (`frontend/vite.config.ts`, substitua o conteúdo)

```ts
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
  },
})
```

- [ ] **Step 4: Tipos globais de teste** (`frontend/tsconfig.app.json`)

Troque a linha `"types": ["vite/client"],` por:
```json
    "types": ["vite/client", "vitest/globals"],
```

- [ ] **Step 5: Setup de teste** (`frontend/src/test/setup.ts`)

```ts
import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

afterEach(() => {
  cleanup()
})
```

- [ ] **Step 6: Portar `index.css`** (`frontend/src/index.css`, substitua TODO o conteúdo)

```css
@import url("https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;0,9..40,800;1,9..40,400&display=swap");
@import "tailwindcss";

@theme {
  /* Font */
  --font-sans: "DM Sans", ui-sans-serif, system-ui, sans-serif;

  /* Primary — Emerald */
  --color-primary:     #10b981;
  --color-primary-50:  #ecfdf5;
  --color-primary-100: #d1fae5;
  --color-primary-200: #a7f3d0;
  --color-primary-300: #6ee7b7;
  --color-primary-400: #34d399;
  --color-primary-500: #10b981;
  --color-primary-600: #059669;
  --color-primary-700: #047857;
  --color-primary-800: #065f46;
  --color-primary-900: #064e3b;

  /* Success */
  --color-success:     #10b981;
  --color-success-50:  #ecfdf5;
  --color-success-100: #d1fae5;
  --color-success-400: #34d399;
  --color-success-500: #10b981;
  --color-success-600: #059669;
  --color-success-700: #047857;

  /* Danger */
  --color-danger:     #ef4444;
  --color-danger-50:  #fef2f2;
  --color-danger-100: #fee2e2;
  --color-danger-400: #f87171;
  --color-danger-500: #ef4444;
  --color-danger-600: #dc2626;
  --color-danger-700: #b91c1c;

  /* Warning */
  --color-warning:     #f59e0b;
  --color-warning-50:  #fffbeb;
  --color-warning-100: #fef3c7;
  --color-warning-400: #fbbf24;
  --color-warning-500: #f59e0b;
  --color-warning-600: #d97706;
  --color-warning-700: #b45309;

  /* Info */
  --color-info:     #3b82f6;
  --color-info-50:  #eff6ff;
  --color-info-100: #dbeafe;
  --color-info-400: #60a5fa;
  --color-info-500: #3b82f6;
  --color-info-600: #2563eb;
  --color-info-700: #1d4ed8;

  /* Backgrounds (light) */
  --color-background:          #f0f7f5;
  --color-background-surface:  #ffffff;
  --color-background-elevated: #e8f4f0;
  --color-background-sidebar:  #f5faf8;

  /* Borders (light) */
  --color-border:       #ddeee8;
  --color-border-muted: #eef7f4;
}

/* Dark overrides (tema padrão) */
.dark {
  --color-background:          #0c1629;
  --color-background-surface:  #111f35;
  --color-background-elevated: #182a42;
  --color-background-sidebar:  #08111f;
  --color-border:              #192c44;
  --color-border-muted:        #111f35;
}

/* Base */
body {
  background-color: var(--color-background);
  font-family: var(--font-sans);
  -webkit-font-smoothing: antialiased;
  font-feature-settings: "cv02", "cv03", "cv04", "cv11";
  color: rgb(15 23 42);
}
.dark body { color: rgb(235 240 250); }

/* Inversão de texto no light mode */
html:not(.dark) .text-slate-100 { color: rgb(15 23 42); }
html:not(.dark) .text-slate-200 { color: rgb(30 41 59); }
html:not(.dark) .text-slate-300 { color: rgb(51 65 85); }
html:not(.dark) .text-slate-400 { color: rgb(71 85 105); }
html:not(.dark) .text-slate-500 { color: rgb(100 116 139); }
html:not(.dark) .text-slate-600 { color: rgb(148 163 184); }

/* Scrollbar custom */
::-webkit-scrollbar       { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--color-border); border-radius: 9999px; }
::-webkit-scrollbar-thumb:hover { background: var(--color-primary-300); }

/* Glow utilitário */
.glow-primary { box-shadow: 0 0 20px -4px color-mix(in srgb, #10b981 40%, transparent); }

#root { width: 100%; height: 100vh; }
```

- [ ] **Step 7: `index.html`** (`frontend/index.html`, substitua o conteúdo)

```html
<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>GestorHS</title>
    <script>
      var t = localStorage.getItem("gestorhs-theme");
      if (t !== "light") document.documentElement.classList.add("dark");
    </script>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 8: `.env.example`** (`frontend/.env.example`)

```
VITE_API_URL=http://localhost:8000
```

- [ ] **Step 9: Remover CSS template** 

Run: `git rm frontend/src/App.css` (será substituído; `App.tsx` é reescrito na Task 11).
Se `App.tsx` ainda importa `./App.css`, isso quebra o build — mas `App.tsx` só é reescrito na Task 11. Para manter o build verde agora, edite `frontend/src/App.tsx` removendo a linha `import './App.css'` (deixe o resto como está por ora).

- [ ] **Step 10: Teste de sanidade** (`frontend/src/test/sanity.test.ts`)

```ts
import { describe, it, expect } from 'vitest'

describe('ambiente de teste', () => {
  it('roda o vitest', () => {
    expect(1 + 1).toBe(2)
  })
})
```

- [ ] **Step 11: Rodar testes**

Run: `npm run test`
Expected: 1 arquivo, 1 teste, PASS.

- [ ] **Step 12: Verificar build**

Run: `npm run build`
Expected: build conclui sem erro de TypeScript.

- [ ] **Step 13: Commit**

```bash
git add -A
git commit -m "chore(frontend): tooling, tema (Tailwind v4) e Vitest"
```

---

### Task 2: Helper `cn()`

**Files:**
- Create: `frontend/src/lib/utils.ts`
- Test: `frontend/src/lib/utils.test.ts`

- [ ] **Step 1: Teste que falha** (`frontend/src/lib/utils.test.ts`)

```ts
import { describe, it, expect } from 'vitest'
import { cn } from './utils'

describe('cn', () => {
  it('junta classes', () => {
    expect(cn('a', 'b')).toBe('a b')
  })
  it('aplica classes condicionais', () => {
    expect(cn('a', false && 'b', 'c')).toBe('a c')
  })
  it('faz dedupe de conflitos do tailwind (last wins)', () => {
    expect(cn('px-2', 'px-4')).toBe('px-4')
  })
})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm run test -- utils`
Expected: FAIL (`cn` não existe / módulo não encontrado).

- [ ] **Step 3: Implementar** (`frontend/src/lib/utils.ts`)

```ts
import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `npm run test -- utils`
Expected: PASS (3 testes).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/utils.ts frontend/src/lib/utils.test.ts
git commit -m "feat(frontend): helper cn() (clsx + tailwind-merge)"
```

---

### Task 3: Armazenamento de tokens

**Files:**
- Create: `frontend/src/lib/auth-storage.ts`
- Test: `frontend/src/lib/auth-storage.test.ts`

- [ ] **Step 1: Teste que falha** (`frontend/src/lib/auth-storage.test.ts`)

```ts
import { describe, it, expect, beforeEach } from 'vitest'
import { getTokens, setTokens, clearTokens } from './auth-storage'

describe('auth-storage', () => {
  beforeEach(() => localStorage.clear())

  it('retorna null quando não há tokens', () => {
    expect(getTokens()).toBeNull()
  })

  it('grava e lê tokens', () => {
    setTokens({ access_token: 'a', refresh_token: 'r', token_type: 'bearer' })
    expect(getTokens()).toEqual({ access_token: 'a', refresh_token: 'r', token_type: 'bearer' })
  })

  it('limpa tokens', () => {
    setTokens({ access_token: 'a', refresh_token: 'r' })
    clearTokens()
    expect(getTokens()).toBeNull()
  })

  it('retorna null quando o valor está corrompido', () => {
    localStorage.setItem('gestorhs-tokens', '{not json')
    expect(getTokens()).toBeNull()
  })
})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm run test -- auth-storage`
Expected: FAIL (módulo não encontrado).

- [ ] **Step 3: Implementar** (`frontend/src/lib/auth-storage.ts`)

```ts
const KEY = 'gestorhs-tokens'

export interface Tokens {
  access_token: string
  refresh_token: string
  token_type?: string
}

export function getTokens(): Tokens | null {
  const raw = localStorage.getItem(KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as Tokens
  } catch {
    return null
  }
}

export function setTokens(tokens: Tokens): void {
  localStorage.setItem(KEY, JSON.stringify(tokens))
}

export function clearTokens(): void {
  localStorage.removeItem(KEY)
}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `npm run test -- auth-storage`
Expected: PASS (4 testes).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/auth-storage.ts frontend/src/lib/auth-storage.test.ts
git commit -m "feat(frontend): armazenamento de tokens em localStorage"
```

---

### Task 4: Cliente de API (fetch wrapper com refresh-no-401)

A peça mais sensível. Injeta o `Bearer`, e no 401 faz **um** refresh (single-flight) e repete; se o refresh falhar, limpa tokens e chama o handler de "não autorizado".

**Files:**
- Create: `frontend/src/lib/api.ts`
- Test: `frontend/src/lib/api.test.ts`

- [ ] **Step 1: Teste que falha** (`frontend/src/lib/api.test.ts`)

```ts
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { apiFetch, apiJson, setOnUnauthorized } from './api'
import { setTokens, getTokens } from './auth-storage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('api', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    setOnUnauthorized(null)
  })

  it('injeta o Authorization quando há token', async () => {
    setTokens({ access_token: 'tok', refresh_token: 'r' })
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    await apiFetch('/x')

    const headers = fetchMock.mock.calls[0][1].headers as Headers
    expect(headers.get('Authorization')).toBe('Bearer tok')
  })

  it('não injeta Authorization sem token', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    await apiFetch('/x')

    const headers = fetchMock.mock.calls[0][1].headers as Headers
    expect(headers.has('Authorization')).toBe(false)
  })

  it('no 401 faz refresh e repete a request com o novo token', async () => {
    setTokens({ access_token: 'velho', refresh_token: 'r' })
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ detail: 'expirado' }, 401)) // /x
      .mockResolvedValueOnce(jsonResponse({ access_token: 'novo', refresh_token: 'r2' })) // /auth/refresh
      .mockResolvedValueOnce(jsonResponse({ ok: true })) // /x repetido
    vi.stubGlobal('fetch', fetchMock)

    const res = await apiFetch('/x')

    expect(res.status).toBe(200)
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(fetchMock.mock.calls[1][0]).toContain('/auth/refresh')
    const retryHeaders = fetchMock.mock.calls[2][1].headers as Headers
    expect(retryHeaders.get('Authorization')).toBe('Bearer novo')
    expect(getTokens()?.access_token).toBe('novo')
  })

  it('faz um único refresh para requests concorrentes (single-flight)', async () => {
    setTokens({ access_token: 'velho', refresh_token: 'r' })
    const fetchMock = vi.fn((url: string) => {
      if (url.includes('/auth/refresh')) {
        return Promise.resolve(jsonResponse({ access_token: 'novo', refresh_token: 'r2' }))
      }
      // primeira leva: 401; após refresh, o token muda — devolve ok
      const tokenAtual = getTokens()?.access_token
      return Promise.resolve(
        tokenAtual === 'novo' ? jsonResponse({ ok: true }) : jsonResponse({ detail: 'expirado' }, 401),
      )
    })
    vi.stubGlobal('fetch', fetchMock as unknown as typeof fetch)

    await Promise.all([apiFetch('/a'), apiFetch('/b')])

    const refreshCalls = fetchMock.mock.calls.filter((c) => String(c[0]).includes('/auth/refresh'))
    expect(refreshCalls.length).toBe(1)
  })

  it('refresh falho limpa tokens e chama onUnauthorized', async () => {
    setTokens({ access_token: 'velho', refresh_token: 'r' })
    const onUnauth = vi.fn()
    setOnUnauthorized(onUnauth)
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ detail: 'expirado' }, 401))
      .mockResolvedValueOnce(jsonResponse({ detail: 'invalido' }, 401)) // /auth/refresh falha
    vi.stubGlobal('fetch', fetchMock)

    const res = await apiFetch('/x')

    expect(res.status).toBe(401)
    expect(getTokens()).toBeNull()
    expect(onUnauth).toHaveBeenCalledTimes(1)
  })

  it('apiJson lança ApiError com o detail no erro', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ detail: 'Credenciais inválidas' }, 401))
    vi.stubGlobal('fetch', fetchMock)

    await expect(apiJson('/auth/login', { method: 'POST', body: '{}' })).rejects.toMatchObject({
      status: 401,
      message: 'Credenciais inválidas',
    })
  })
})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm run test -- api`
Expected: FAIL (módulo não encontrado).

- [ ] **Step 3: Implementar** (`frontend/src/lib/api.ts`)

```ts
import { getTokens, setTokens, clearTokens, type Tokens } from './auth-storage'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

let onUnauthorized: (() => void) | null = null
export function setOnUnauthorized(cb: (() => void) | null) {
  onUnauthorized = cb
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

let refreshPromise: Promise<boolean> | null = null

async function doRefresh(): Promise<boolean> {
  const tokens = getTokens()
  if (!tokens?.refresh_token) return false
  const res = await fetch(`${BASE_URL}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: tokens.refresh_token }),
  })
  if (!res.ok) return false
  const data = (await res.json()) as Tokens
  setTokens(data)
  return true
}

function refreshOnce(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = doRefresh().finally(() => {
      refreshPromise = null
    })
  }
  return refreshPromise
}

export async function apiFetch(path: string, options: RequestInit = {}, retry = true): Promise<Response> {
  const tokens = getTokens()
  const headers = new Headers(options.headers)
  if (tokens?.access_token) headers.set('Authorization', `Bearer ${tokens.access_token}`)

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers })

  if (res.status === 401 && retry && tokens?.refresh_token) {
    const ok = await refreshOnce()
    if (ok) return apiFetch(path, options, false)
    clearTokens()
    onUnauthorized?.()
  }
  return res
}

export async function apiJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await apiFetch(path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers as Record<string, string>) },
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = (await res.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      // sem corpo JSON — mantém o statusText
    }
    throw new ApiError(res.status, detail)
  }
  return (await res.json()) as T
}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `npm run test -- api`
Expected: PASS (6 testes).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/lib/api.test.ts
git commit -m "feat(frontend): cliente de API com refresh single-flight no 401"
```

---

### Task 5: AuthContext (AuthProvider + useAuth)

**Files:**
- Create: `frontend/src/auth/AuthContext.tsx`
- Test: `frontend/src/auth/AuthContext.test.tsx`

- [ ] **Step 1: Teste que falha** (`frontend/src/auth/AuthContext.test.tsx`)

```tsx
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import { AuthProvider, useAuth } from './AuthContext'
import { setTokens, getTokens } from '../lib/auth-storage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

const ME = { id: 1, nome: 'Erick', login: 'erick', email: null, funcao_id: 1 }

function Probe() {
  const { user, loading, login, logout } = useAuth()
  return (
    <div>
      <span data-testid="loading">{String(loading)}</span>
      <span data-testid="user">{user ? user.login : 'anon'}</span>
      <button onClick={() => login('erick', 'senha')}>entrar</button>
      <button onClick={() => logout()}>sair</button>
    </div>
  )
}

function renderProbe() {
  return render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  )
}

describe('AuthContext', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('sem token: termina deslogado e sem loading', async () => {
    vi.stubGlobal('fetch', vi.fn())
    renderProbe()
    await waitFor(() => expect(screen.getByTestId('loading').textContent).toBe('false'))
    expect(screen.getByTestId('user').textContent).toBe('anon')
  })

  it('com token válido: hidrata o usuário via /auth/me', async () => {
    setTokens({ access_token: 'a', refresh_token: 'r' })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(ME)))
    renderProbe()
    await waitFor(() => expect(screen.getByTestId('user').textContent).toBe('erick'))
  })

  it('com token inválido: limpa e fica deslogado', async () => {
    setTokens({ access_token: 'a', refresh_token: 'r' })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ detail: 'x' }, 401)))
    renderProbe()
    await waitFor(() => expect(screen.getByTestId('loading').textContent).toBe('false'))
    expect(screen.getByTestId('user').textContent).toBe('anon')
  })

  it('login grava tokens e popula o usuário', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ access_token: 'a', refresh_token: 'r' })) // /auth/login
      .mockResolvedValueOnce(jsonResponse(ME)) // /auth/me
    vi.stubGlobal('fetch', fetchMock)
    renderProbe()
    await waitFor(() => expect(screen.getByTestId('loading').textContent).toBe('false'))

    await act(async () => {
      screen.getByText('entrar').click()
    })

    await waitFor(() => expect(screen.getByTestId('user').textContent).toBe('erick'))
    expect(getTokens()?.access_token).toBe('a')
  })

  it('logout limpa tokens e usuário', async () => {
    setTokens({ access_token: 'a', refresh_token: 'r' })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(ME)))
    renderProbe()
    await waitFor(() => expect(screen.getByTestId('user').textContent).toBe('erick'))

    await act(async () => {
      screen.getByText('sair').click()
    })

    expect(screen.getByTestId('user').textContent).toBe('anon')
    expect(getTokens()).toBeNull()
  })
})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm run test -- AuthContext`
Expected: FAIL (módulo não encontrado).

- [ ] **Step 3: Implementar** (`frontend/src/auth/AuthContext.tsx`)

```tsx
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { apiJson, setOnUnauthorized } from '../lib/api'
import { clearTokens, getTokens, setTokens, type Tokens } from '../lib/auth-storage'

export interface User {
  id: number
  nome: string | null
  login: string
  email: string | null
  funcao_id: number | null
}

interface AuthContextValue {
  user: User | null
  loading: boolean
  login: (login: string, senha: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setOnUnauthorized(() => setUser(null))
    return () => setOnUnauthorized(null)
  }, [])

  useEffect(() => {
    let ativo = true
    async function hidratar() {
      if (!getTokens()) {
        if (ativo) setLoading(false)
        return
      }
      try {
        const me = await apiJson<User>('/auth/me')
        if (ativo) setUser(me)
      } catch {
        clearTokens()
        if (ativo) setUser(null)
      } finally {
        if (ativo) setLoading(false)
      }
    }
    void hidratar()
    return () => {
      ativo = false
    }
  }, [])

  async function login(login: string, senha: string) {
    const tokens = await apiJson<Tokens>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ login, senha }),
    })
    setTokens(tokens)
    const me = await apiJson<User>('/auth/me')
    setUser(me)
  }

  function logout() {
    clearTokens()
    setUser(null)
  }

  return <AuthContext value={{ user, loading, login, logout }}>{children}</AuthContext>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth deve ser usado dentro de <AuthProvider>')
  return ctx
}
```

> Nota: React 19 permite `<AuthContext value=...>` (sem `.Provider`). Se o lint reclamar, use `<AuthContext.Provider value=...>`.

- [ ] **Step 4: Rodar e ver passar**

Run: `npm run test -- AuthContext`
Expected: PASS (5 testes).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/auth/AuthContext.tsx frontend/src/auth/AuthContext.test.tsx
git commit -m "feat(frontend): AuthProvider + useAuth (login, logout, hidratação)"
```

---

### Task 6: ProtectedRoute

**Files:**
- Create: `frontend/src/components/ui/Spinner.tsx` (dependência visual mínima do ProtectedRoute)
- Create: `frontend/src/auth/ProtectedRoute.tsx`
- Test: `frontend/src/auth/ProtectedRoute.test.tsx`

- [ ] **Step 1: Criar o Spinner** (`frontend/src/components/ui/Spinner.tsx`)

```tsx
import { cn } from '../../lib/utils'

export function Spinner({ className }: { className?: string }) {
  return (
    <svg
      className={cn('w-5 h-5 animate-spin text-primary', className)}
      fill="none"
      viewBox="0 0 24 24"
      role="status"
      aria-label="Carregando"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  )
}
```

- [ ] **Step 2: Teste que falha** (`frontend/src/auth/ProtectedRoute.test.tsx`)

```tsx
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from './AuthContext'
import { ProtectedRoute } from './ProtectedRoute'
import { setTokens } from '../lib/auth-storage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

function renderAt(initial: string) {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={[initial]}>
        <Routes>
          <Route path="/login" element={<div>tela de login</div>} />
          <Route
            path="/app"
            element={
              <ProtectedRoute>
                <div>conteudo protegido</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  )
}

describe('ProtectedRoute', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('sem usuário redireciona para /login', async () => {
    vi.stubGlobal('fetch', vi.fn())
    renderAt('/app')
    await waitFor(() => expect(screen.getByText('tela de login')).toBeInTheDocument())
  })

  it('com usuário renderiza o conteúdo', async () => {
    setTokens({ access_token: 'a', refresh_token: 'r' })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ id: 1, nome: 'E', login: 'e', email: null, funcao_id: 1 })))
    renderAt('/app')
    await waitFor(() => expect(screen.getByText('conteudo protegido')).toBeInTheDocument())
  })
})
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `npm run test -- ProtectedRoute`
Expected: FAIL (módulo não encontrado).

- [ ] **Step 4: Implementar** (`frontend/src/auth/ProtectedRoute.tsx`)

```tsx
import { type ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from './AuthContext'
import { Spinner } from '../components/ui/Spinner'

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <Spinner className="w-8 h-8" />
      </div>
    )
  }

  if (!user) return <Navigate to="/login" replace />

  return <>{children}</>
}
```

- [ ] **Step 5: Rodar e ver passar**

Run: `npm run test -- ProtectedRoute`
Expected: PASS (2 testes).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/auth/ProtectedRoute.tsx frontend/src/components/ui/Spinner.tsx frontend/src/auth/ProtectedRoute.test.tsx
git commit -m "feat(frontend): ProtectedRoute + Spinner"
```

---

### Task 7: Ícones + primitivos de formulário (Button, Input, Select)

Sem testes (visual). Porte do `DESIGN_SYSTEM.md` seções 6.1, 6.5, 10. Verificação = type-check + lint.

**Files:**
- Create: `frontend/src/components/ui/icons.tsx`
- Create: `frontend/src/components/ui/Button.tsx`
- Create: `frontend/src/components/ui/Input.tsx`
- Create: `frontend/src/components/ui/Select.tsx`

- [ ] **Step 1: Ícones** (`frontend/src/components/ui/icons.tsx`)

```tsx
interface IconProps {
  className?: string
}

function base(className?: string) {
  return className ?? 'w-5 h-5 shrink-0'
}

export function IconMenu({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
    </svg>
  )
}

export function IconSun({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2m0 14v2m9-9h-2M5 12H3m15.36 6.36-1.42-1.42M6.34 6.34 4.93 4.93m12.73 0-1.42 1.42M6.34 17.66l-1.41 1.41M12 8a4 4 0 100 8 4 4 0 000-8z" />
    </svg>
  )
}

export function IconMoon({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" />
    </svg>
  )
}

export function IconLogout({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H9m4 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
    </svg>
  )
}

export function IconDashboard({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l9-9 9 9M5 10v10a1 1 0 001 1h3v-6h6v6h3a1 1 0 001-1V10" />
    </svg>
  )
}

export function IconChevronDown({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 9l6 6 6-6" />
    </svg>
  )
}

export function IconAlertCircle({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  )
}

export function IconX({ className }: IconProps) {
  return (
    <svg className={base(className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
    </svg>
  )
}
```

- [ ] **Step 2: Button** (`frontend/src/components/ui/Button.tsx`)

```tsx
import { type ButtonHTMLAttributes } from 'react'
import { cn } from '../../lib/utils'

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost'

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-primary text-white hover:bg-primary-600',
  secondary: 'border border-border text-slate-300 hover:bg-background-elevated',
  danger: 'bg-danger text-white hover:bg-danger-600',
  ghost: 'text-slate-400 hover:text-slate-100 hover:bg-background-elevated',
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
}

export function Button({ variant = 'primary', className, ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        'flex items-center justify-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg',
        'active:scale-95 transition-all duration-150',
        'disabled:opacity-60 disabled:cursor-not-allowed',
        VARIANTS[variant],
        className,
      )}
      {...props}
    />
  )
}
```

- [ ] **Step 3: Input** (`frontend/src/components/ui/Input.tsx`)

```tsx
import { type InputHTMLAttributes } from 'react'
import { cn } from '../../lib/utils'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
}

export function Input({ label, id, className, ...props }: InputProps) {
  return (
    <div>
      {label && (
        <label htmlFor={id} className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">
          {label}
        </label>
      )}
      <input
        id={id}
        className={cn(
          'w-full px-3 py-2.5 text-sm rounded-lg border border-border bg-background-elevated',
          'text-slate-100 placeholder-slate-500',
          'focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-colors',
          className,
        )}
        {...props}
      />
    </div>
  )
}
```

- [ ] **Step 4: Select** (`frontend/src/components/ui/Select.tsx`)

```tsx
import { type SelectHTMLAttributes } from 'react'
import { cn } from '../../lib/utils'
import { IconChevronDown } from './icons'

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string
}

export function Select({ label, id, className, children, ...props }: SelectProps) {
  return (
    <div>
      {label && (
        <label htmlFor={id} className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">
          {label}
        </label>
      )}
      <div className="relative">
        <select
          id={id}
          className={cn(
            'appearance-none w-full pl-3 pr-8 py-2 text-sm rounded-lg border border-border bg-background-elevated',
            'text-slate-300 focus:outline-none focus:ring-2 focus:ring-primary/50 cursor-pointer transition-colors',
            className,
          )}
          {...props}
        >
          {children}
        </select>
        <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none">
          <IconChevronDown className="w-4 h-4" />
        </span>
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Verificar type-check e lint**

Run: `npx tsc -b && npm run lint`
Expected: sem erros.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ui/icons.tsx frontend/src/components/ui/Button.tsx frontend/src/components/ui/Input.tsx frontend/src/components/ui/Select.tsx
git commit -m "feat(frontend): ícones + Button, Input, Select"
```

---

### Task 8: Badge, Toggle, Modal, Drawer, Table, StatCard

Sem testes (visual). Porte do `DESIGN_SYSTEM.md` seções 6.2, 6.3, 6.9, 6.10, 8, 9.

**Files:**
- Create: `frontend/src/components/ui/Badge.tsx`
- Create: `frontend/src/components/ui/Toggle.tsx`
- Create: `frontend/src/components/ui/Modal.tsx`
- Create: `frontend/src/components/ui/Drawer.tsx`
- Create: `frontend/src/components/ui/Table.tsx`
- Create: `frontend/src/components/ui/StatCard.tsx`

- [ ] **Step 1: Badge** (`frontend/src/components/ui/Badge.tsx`)

```tsx
import { type ReactNode } from 'react'
import { cn } from '../../lib/utils'

type Tone = 'primary' | 'danger' | 'warning' | 'info' | 'neutral'

const TONES: Record<Tone, string> = {
  primary: 'bg-primary/10 text-primary',
  danger: 'bg-danger/10 text-danger',
  warning: 'bg-warning/10 text-warning',
  info: 'bg-info/10 text-info',
  neutral: 'bg-slate-100 dark:bg-background-elevated text-slate-500',
}

export function Badge({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span className={cn('inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full', TONES[tone])}>
      {children}
    </span>
  )
}
```

- [ ] **Step 2: Toggle** (`frontend/src/components/ui/Toggle.tsx`)

```tsx
import { cn } from '../../lib/utils'

interface ToggleProps {
  checked: boolean
  onChange: (next: boolean) => void
  label?: string
}

export function Toggle({ checked, onChange, label }: ToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={cn('w-10 h-6 rounded-full transition-colors relative shrink-0', checked ? 'bg-primary' : 'bg-slate-200 dark:bg-border')}
    >
      <span className={cn('absolute top-1 w-4 h-4 rounded-full bg-white shadow transition-transform', checked ? 'translate-x-5' : 'translate-x-1')} />
    </button>
  )
}
```

- [ ] **Step 3: Modal** (`frontend/src/components/ui/Modal.tsx`)

```tsx
import { type ReactNode } from 'react'
import { IconX } from './icons'

interface ModalProps {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
  footer?: ReactNode
}

export function Modal({ open, onClose, title, children, footer }: ModalProps) {
  if (!open) return null
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="w-full max-w-md rounded-2xl bg-background-surface border border-border shadow-2xl">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h2 className="text-base font-bold text-slate-100">{title}</h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-200 hover:bg-background-elevated transition-colors"
            aria-label="Fechar"
          >
            <IconX className="w-4 h-4" />
          </button>
        </div>
        <div className="p-6 space-y-4">{children}</div>
        {footer && <div className="flex gap-2 px-6 pb-6 pt-1">{footer}</div>}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Drawer** (`frontend/src/components/ui/Drawer.tsx`)

```tsx
import { type ReactNode } from 'react'
import { IconX } from './icons'

interface DrawerProps {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
}

export function Drawer({ open, onClose, title, children }: DrawerProps) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="flex-1 bg-black/40" onClick={onClose} />
      <div className="w-[380px] bg-background-surface border-l border-border flex flex-col h-full shadow-2xl">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border shrink-0">
          <h2 className="text-sm font-semibold text-slate-200">{title}</h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-200 hover:bg-background-elevated transition-colors"
            aria-label="Fechar"
          >
            <IconX className="w-4 h-4" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-5 space-y-4">{children}</div>
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Table** (`frontend/src/components/ui/Table.tsx`)

```tsx
import { type ReactNode } from 'react'

interface TableProps {
  head: ReactNode
  children: ReactNode
}

export function Table({ head, children }: TableProps) {
  return (
    <div className="rounded-2xl border border-border bg-background-surface overflow-hidden shadow-sm">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-background-elevated">{head}</tr>
        </thead>
        <tbody className="divide-y divide-border">{children}</tbody>
      </table>
    </div>
  )
}

export function TH({ children }: { children: ReactNode }) {
  return <th className="text-left px-5 py-3 text-xs font-semibold uppercase tracking-wider text-slate-400">{children}</th>
}

export function TD({ children }: { children: ReactNode }) {
  return <td className="px-5 py-4">{children}</td>
}
```

- [ ] **Step 6: StatCard** (`frontend/src/components/ui/StatCard.tsx`)

```tsx
import { type ReactNode } from 'react'
import { cn } from '../../lib/utils'

interface StatCardProps {
  label: string
  value: ReactNode
  icon: ReactNode
  color: string
  sub?: string
}

export function StatCard({ label, value, icon, color, sub }: StatCardProps) {
  return (
    <div className="rounded-xl bg-background-surface border border-border p-5 flex items-center gap-4">
      <div className={cn('w-12 h-12 rounded-xl flex items-center justify-center shrink-0', color)}>{icon}</div>
      <div className="min-w-0">
        <p className="text-2xl font-extrabold text-slate-100 leading-none">{value}</p>
        <p className="text-xs text-slate-500 mt-1 font-medium">{label}</p>
        {sub && <p className="text-[11px] text-slate-600 mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}
```

- [ ] **Step 7: Verificar type-check e lint**

Run: `npx tsc -b && npm run lint`
Expected: sem erros.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/ui/Badge.tsx frontend/src/components/ui/Toggle.tsx frontend/src/components/ui/Modal.tsx frontend/src/components/ui/Drawer.tsx frontend/src/components/ui/Table.tsx frontend/src/components/ui/StatCard.tsx
git commit -m "feat(frontend): Badge, Toggle, Modal, Drawer, Table, StatCard"
```

---

### Task 9: App Shell (Sidebar, Topbar, MainLayout)

Sem testes (visual). Porte do `DESIGN_SYSTEM.md` seção 5. O toggle de tema vive no `MainLayout`.

**Files:**
- Create: `frontend/src/layout/Sidebar.tsx`
- Create: `frontend/src/layout/Topbar.tsx`
- Create: `frontend/src/layout/MainLayout.tsx`

- [ ] **Step 1: Sidebar** (`frontend/src/layout/Sidebar.tsx`)

```tsx
import { type ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { cn } from '../lib/utils'
import { IconDashboard } from '../components/ui/icons'

interface NavItem {
  label: string
  icon: ReactNode
  to: string
}

const NAV_ITEMS: NavItem[] = [{ label: 'Dashboard', icon: <IconDashboard />, to: '/app' }]

export function Sidebar({ collapsed }: { collapsed: boolean }) {
  const location = useLocation()

  return (
    <aside
      className={cn(
        'flex flex-col shrink-0 bg-background-sidebar border-r border-border',
        'transition-[width] duration-300 ease-in-out overflow-hidden',
        collapsed ? 'w-18' : 'w-64',
      )}
    >
      <div className={cn('flex h-16 shrink-0 items-center border-b border-border', collapsed ? 'justify-center px-0' : 'px-5')}>
        {collapsed ? (
          <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-primary/15">
            <span className="text-sm font-bold text-primary">G</span>
          </div>
        ) : (
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-primary/15 flex items-center justify-center shrink-0">
              <span className="text-sm font-bold text-primary">G</span>
            </div>
            <span className="font-bold text-slate-100 text-base tracking-tight">GestorHS</span>
          </div>
        )}
      </div>

      <nav className="flex-1 px-2 py-4 space-y-1">
        {NAV_ITEMS.map((item) => {
          const active = location.pathname === item.to || location.pathname.startsWith(item.to + '/')
          return (
            <Link
              key={item.to}
              to={item.to}
              title={collapsed ? item.label : undefined}
              className={cn(
                'relative group flex items-center w-full rounded-lg text-sm font-medium transition-all duration-200',
                collapsed ? 'justify-center px-0 py-2.5 mx-1' : 'gap-3 px-3 py-2',
                active
                  ? cn('bg-primary/10 text-primary font-semibold', !collapsed && 'shadow-[inset_2px_0_0_#10b981] pl-2.5')
                  : cn(!collapsed && 'pl-2.5', 'text-slate-400 dark:text-slate-500 hover:bg-background-elevated hover:text-slate-100'),
              )}
            >
              {item.icon}
              {!collapsed && <span className="truncate">{item.label}</span>}
              {collapsed && (
                <span className="pointer-events-none absolute left-full ml-3 z-50 whitespace-nowrap rounded-lg bg-background-surface border border-border px-2.5 py-1.5 text-xs font-medium text-slate-200 shadow-lg opacity-0 group-hover:opacity-100 transition-opacity duration-150">
                  {item.label}
                </span>
              )}
            </Link>
          )
        })}
      </nav>
    </aside>
  )
}
```

- [ ] **Step 2: Topbar** (`frontend/src/layout/Topbar.tsx`)

```tsx
import { cn } from '../lib/utils'
import { useAuth } from '../auth/AuthContext'
import { IconMenu, IconSun, IconMoon, IconLogout } from '../components/ui/icons'

function iniciais(nome: string | null, login: string): string {
  const base = (nome ?? login).trim()
  const partes = base.split(/\s+/)
  if (partes.length >= 2) return (partes[0][0] + partes[1][0]).toUpperCase()
  return base.slice(0, 2).toUpperCase()
}

interface TopbarProps {
  dark: boolean
  onToggleTheme: () => void
  onToggleSidebar: () => void
}

const iconBtn = 'rounded-lg p-2 text-slate-400 hover:bg-background-elevated hover:text-slate-100 transition-colors duration-200'

export function Topbar({ dark, onToggleTheme, onToggleSidebar }: TopbarProps) {
  const { user, logout } = useAuth()

  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-border bg-background-sidebar px-4 md:px-6">
      <button className={iconBtn} onClick={onToggleSidebar} aria-label="Alternar menu">
        <IconMenu />
      </button>

      <div className="flex items-center gap-2">
        <button className={iconBtn} onClick={onToggleTheme} aria-label="Alternar tema">
          {dark ? <IconSun /> : <IconMoon />}
        </button>
        <button className={cn(iconBtn, 'hover:text-danger-400')} onClick={logout} aria-label="Sair">
          <IconLogout />
        </button>
        {user && (
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary-400 to-primary-700 flex items-center justify-center text-white text-xs font-bold shadow-sm">
            {iniciais(user.nome, user.login)}
          </div>
        )}
      </div>
    </header>
  )
}
```

- [ ] **Step 3: MainLayout** (`frontend/src/layout/MainLayout.tsx`)

```tsx
import { type ReactNode, useState } from 'react'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'

export function MainLayout({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false)
  const [dark, setDark] = useState(() => localStorage.getItem('gestorhs-theme') !== 'light')

  function toggleTheme() {
    const next = !dark
    setDark(next)
    localStorage.setItem('gestorhs-theme', next ? 'dark' : 'light')
    document.documentElement.classList.toggle('dark', next)
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar collapsed={collapsed} />
      <div className="flex flex-col flex-1 overflow-hidden min-w-0">
        <Topbar dark={dark} onToggleTheme={toggleTheme} onToggleSidebar={() => setCollapsed((c) => !c)} />
        <main className="flex flex-col flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Verificar type-check e lint**

Run: `npx tsc -b && npm run lint`
Expected: sem erros.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/layout/Sidebar.tsx frontend/src/layout/Topbar.tsx frontend/src/layout/MainLayout.tsx
git commit -m "feat(frontend): app shell (Sidebar, Topbar, MainLayout) com toggle de tema"
```

---

### Task 10: Páginas (LoginPage, DashboardPage, PlaceholderPage do portal)

Sem testes (visual). LoginPage liga em `useAuth().login`. Porte do `DESIGN_SYSTEM.md` seção 11.

**Files:**
- Create: `frontend/src/app/pages/LoginPage.tsx`
- Create: `frontend/src/app/pages/DashboardPage.tsx`
- Create: `frontend/src/portal/pages/PlaceholderPage.tsx`

- [ ] **Step 1: LoginPage** (`frontend/src/app/pages/LoginPage.tsx`)

```tsx
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { ApiError } from '../../lib/api'
import { Input } from '../../components/ui/Input'
import { Spinner } from '../../components/ui/Spinner'
import { IconAlertCircle } from '../../components/ui/icons'

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [usuario, setUsuario] = useState('')
  const [senha, setSenha] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setErro('')
    setEnviando(true)
    try {
      await login(usuario, senha)
      navigate('/app', { replace: true })
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao entrar. Tente novamente.')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-primary/15 flex items-center justify-center mb-3 shadow-sm">
            <span className="text-xl font-extrabold text-primary">G</span>
          </div>
          <h1 className="text-2xl font-extrabold text-slate-100 tracking-tight">GestorHS</h1>
          <p className="text-sm text-slate-500 mt-1">Faça login para continuar</p>
        </div>

        <div className="rounded-2xl bg-background-surface border border-border shadow-sm p-6">
          <form className="space-y-4" onSubmit={onSubmit}>
            <Input id="login" label="Usuário" value={usuario} onChange={(e) => setUsuario(e.target.value)} autoComplete="username" autoFocus />
            <Input id="senha" label="Senha" type="password" value={senha} onChange={(e) => setSenha(e.target.value)} autoComplete="current-password" />

            {erro && (
              <div className="flex items-center gap-2 rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">
                <IconAlertCircle className="w-4 h-4 shrink-0" />
                {erro}
              </div>
            )}

            <button
              type="submit"
              disabled={enviando}
              className="w-full py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
            >
              {enviando && <Spinner className="w-4 h-4 text-white" />}
              Entrar
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-slate-400 mt-6">GestorHS · Health Safety</p>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: DashboardPage** (`frontend/src/app/pages/DashboardPage.tsx`)

```tsx
import { useAuth } from '../../auth/AuthContext'

export function DashboardPage() {
  const { user } = useAuth()
  return (
    <div className="px-4 md:px-6 py-6">
      <h1 className="text-xl font-extrabold text-slate-100">Bem-vindo, {user?.nome ?? user?.login} 👋</h1>
      <p className="text-sm text-slate-500 mt-1">A fundação está no ar. Os módulos chegam na Fase 1.</p>
    </div>
  )
}
```

- [ ] **Step 3: PlaceholderPage** (`frontend/src/portal/pages/PlaceholderPage.tsx`)

```tsx
export function PlaceholderPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="text-center">
        <h1 className="text-2xl font-extrabold text-slate-100">Portal do Cliente</h1>
        <p className="text-sm text-slate-500 mt-2">Em construção — disponível na Fase 5.</p>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Verificar type-check e lint**

Run: `npx tsc -b && npm run lint`
Expected: sem erros.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/pages/LoginPage.tsx frontend/src/app/pages/DashboardPage.tsx frontend/src/portal/pages/PlaceholderPage.tsx
git commit -m "feat(frontend): páginas de login, dashboard e placeholder do portal"
```

---

### Task 11: Roteamento e integração final

Liga tudo: árvores lazy, `AuthProvider`, e remove o template do scaffold. Fecha com verificação manual contra o backend.

**Files:**
- Create: `frontend/src/app/routes.tsx`
- Create: `frontend/src/portal/routes.tsx`
- Replace: `frontend/src/App.tsx`
- Verify: `frontend/src/main.tsx` (deve permanecer montando `<App/>`)

- [ ] **Step 1: Rotas internas** (`frontend/src/app/routes.tsx`)

```tsx
import { Routes, Route, Navigate } from 'react-router-dom'
import { MainLayout } from '../layout/MainLayout'
import { DashboardPage } from './pages/DashboardPage'

export default function AppRoutes() {
  return (
    <MainLayout>
      <Routes>
        <Route index element={<DashboardPage />} />
        <Route path="*" element={<Navigate to="/app" replace />} />
      </Routes>
    </MainLayout>
  )
}
```

- [ ] **Step 2: Rotas do portal** (`frontend/src/portal/routes.tsx`)

```tsx
import { Routes, Route } from 'react-router-dom'
import { PlaceholderPage } from './pages/PlaceholderPage'

export default function PortalRoutes() {
  return (
    <Routes>
      <Route path="*" element={<PlaceholderPage />} />
    </Routes>
  )
}
```

- [ ] **Step 3: App.tsx** (`frontend/src/App.tsx`, substitua TODO o conteúdo)

```tsx
import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { LoginPage } from './app/pages/LoginPage'
import { Spinner } from './components/ui/Spinner'

const AppRoutes = lazy(() => import('./app/routes'))
const PortalRoutes = lazy(() => import('./portal/routes'))

function FullScreenSpinner() {
  return (
    <div className="flex h-screen items-center justify-center bg-background">
      <Spinner className="w-8 h-8" />
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Suspense fallback={<FullScreenSpinner />}>
          <Routes>
            <Route path="/" element={<Navigate to="/app" replace />} />
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/app/*"
              element={
                <ProtectedRoute>
                  <AppRoutes />
                </ProtectedRoute>
              }
            />
            <Route path="/portal/*" element={<PortalRoutes />} />
            <Route path="*" element={<Navigate to="/app" replace />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </AuthProvider>
  )
}
```

- [ ] **Step 4: Conferir `main.tsx`**

Abra `frontend/src/main.tsx`. Deve estar assim (sem `App.css`):
```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```
Se houver qualquer import de `./App.css`, remova.

- [ ] **Step 5: Suíte completa de testes**

Run: `npm run test`
Expected: todos os arquivos PASS (utils, auth-storage, api, AuthContext, ProtectedRoute, sanity).

- [ ] **Step 6: Build + lint**

Run: `npm run build && npm run lint`
Expected: build gera chunks separados para `app/routes` e `portal/routes` (lazy); lint sem erros.

- [ ] **Step 7: Verificação manual contra o backend**

Garanta o backend no ar: `docker compose up -d` (na raiz do repo). Crie `frontend/.env` com `VITE_API_URL=http://localhost:8000` (copie de `.env.example`).
Run: `npm run dev` e abra a URL do Vite.
Verifique:
1. Acessar `/` redireciona para `/login` (via `/app` → ProtectedRoute).
2. Login com o admin de bootstrap entra e cai no shell em `/app` com a saudação.
3. Reload mantém a sessão (hidratação via `/auth/me`).
4. Botão de logout volta para `/login`.
5. Toggle de tema alterna dark/light e persiste após reload (sem flash).
6. Acessar `/portal` mostra o placeholder (e o Network mostra um chunk separado carregado).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/app/routes.tsx frontend/src/portal/routes.tsx frontend/src/App.tsx frontend/src/main.tsx
git commit -m "feat(frontend): roteamento /app + /portal lazy com AuthProvider"
```

---

## Notas para o executor

- **Ordem importa para os imports:** o `Spinner` é criado na Task 6 (antes do ProtectedRoute, que o usa). Os demais componentes de `ui/` (Task 7–8) não são importados por nada até as páginas/shell (Task 9–10), então o build permanece verde entre tasks.
- **`verbatimModuleSyntax`:** sempre `import { type X }` ou `import type` para tipos. Os exemplos já seguem isso.
- **Backend:** precisa estar no ar (`docker compose up -d`) só para a verificação manual da Task 11; os testes usam `fetch` mockado e não tocam a rede.
- **`.env` real vs `.env.example`:** o `.gitignore` do projeto deve ignorar `.env`. Confirme que `frontend/.env` não é commitado (se o `.gitignore` da raiz não cobrir `frontend/.env`, adicione `frontend/.env`).
```
