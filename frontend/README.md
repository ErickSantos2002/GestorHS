# GestorHS — Frontend

SPA em React 19 + TypeScript + Vite + Tailwind v4 que serve os dois apps do GestorHS: o painel interno (`/app`) e o portal do cliente (`/portal`).

Para a visão geral do projeto, arquitetura e setup do backend, veja o [README na raiz](../README.md).

## Desenvolvimento

```bash
npm install
cp .env.example .env     # VITE_API_URL=http://localhost:8000 (URL da API)
npm run dev              # http://localhost:5173
```

## Scripts

| Comando | O que faz |
|---------|-----------|
| `npm run dev` | servidor de desenvolvimento (HMR) |
| `npm run build` | type-check (`tsc -b`) + build de produção |
| `npm run preview` | serve o build de produção localmente |
| `npm run lint` | ESLint |
| `npm test` | testes (Vitest) |
| `npm run test:watch` | testes em watch mode |

## Estrutura

```
src/
├── app/            módulos internos (acesso, cadastros, clientes, frota,
│                     ordens, alertas, solicitacoes, dashboard)
├── portal/         portal do cliente (auth próprio + páginas)
├── auth/           AuthContext, ProtectedRoute, roles
├── components/ui/  design system
├── layout/         MainLayout, Sidebar, Topbar
└── lib/            cliente de API (refresh single-flight), storage, utils
```

A camada de API (`src/lib/api.ts`) anexa o Bearer token automaticamente e renova no 401 (refresh *single-flight*). Cada módulo tem seu `api.ts`. Os dois apps têm **providers de autenticação independentes** (`AuthContext` para `/app`, `PortalAuthContext` para `/portal`).
