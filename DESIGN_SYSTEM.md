# TaskHS — Design System

> Documento de referência do design system do **TaskHS** (gestão de SST, marca **Talenths**).
> Extraído do frontend real (`frontend/src`). Use este arquivo para replicar o mesmo visual/UX em outro projeto.

**Stack:** React 19 + TypeScript + Vite 8 + **Tailwind CSS v4** (config CSS-first via `@theme`, sem `tailwind.config.js`).
**Fonte:** DM Sans. **Cor de marca:** Emerald `#10b981`. **Tema:** dark por padrão, com light mode via classe `.dark`.
**Sem biblioteca de UI** (nada de shadcn/Radix/Headless UI) e **sem lib de animação** (só transições CSS). Ícones são SVG inline. Drag & drop via `@dnd-kit`.

---

## 0. Como portar para outro projeto (ordem obrigatória)

Para que qualquer snippet deste doc compile no projeto destino, copie **nesta ordem**:

1. **Bloco `@theme`** (tokens de cor + fonte) — Seção 1.
2. **Overrides de base** no `index.css`: inversão de `text-slate-*` no light mode, scrollbar custom, `.glow-primary`, `body`, `#root` — Seção 1.4.
3. **Helper `cn()`** (clsx + tailwind-merge) — Seção 2.
4. **Script anti-FOUC** de tema no `index.html` + convenção `localStorage["taskhs-theme"]` — Seção 1.3.

Sem esses três primeiros itens, as classes `bg-primary`, `bg-background-surface`, `text-slate-100` etc. **não funcionam** ou renderizam errado no light mode.

### Dependências relevantes (package.json)

| Pacote | Versão | Papel |
|---|---|---|
| `react` / `react-dom` | `^19.2.6` | Framework |
| `react-router-dom` | `^7.15.1` | Rotas |
| `@dnd-kit/core` · `/sortable` · `/utilities` | `^6.3.1` · `^10.0.0` · `^3.2.2` | Drag & drop |
| `clsx` | `^2.1.1` | classNames condicionais (`cn`) |
| `tailwind-merge` | `^3.6.0` | dedupe de classes (`cn`) |
| `@tailwindcss/vite` (dev) | `^4.3.0` | Engine Tailwind v4 |
| `vite` (dev) | `^8.0.12` | Build |
| `@vitejs/plugin-react` (dev) | `^6.0.1` | Fast Refresh |

`vite.config.ts`:
```ts
import tailwindcss from '@tailwindcss/vite'
export default defineConfig({ plugins: [react(), tailwindcss()] })
```

---

## 1. Tokens (Tailwind v4 `@theme`)

No Tailwind v4 toda variável `--color-*` declarada em `@theme` vira utilitário automaticamente (`bg-`, `text-`, `border-`, `ring-`, `divide-`, com modificadores de opacidade tipo `bg-primary/10`). Idem `--font-sans` → `font-sans`.

### 1.1 Bloco `@theme` completo (cole no topo do `index.css`)

```css
@import url("https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;0,9..40,800;1,9..40,400&display=swap");
@import "tailwindcss";

@theme {
  /* Font */
  --font-sans: "DM Sans", ui-sans-serif, system-ui, sans-serif;

  /* Primary — Emerald (marca Talenths) */
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

  /* Success (espelha o emerald) */
  --color-success:     #10b981;
  --color-success-50:  #ecfdf5;
  --color-success-100: #d1fae5;
  --color-success-400: #34d399;
  --color-success-500: #10b981;
  --color-success-600: #059669;
  --color-success-700: #047857;

  /* Danger (red) */
  --color-danger:     #ef4444;
  --color-danger-50:  #fef2f2;
  --color-danger-100: #fee2e2;
  --color-danger-400: #f87171;
  --color-danger-500: #ef4444;
  --color-danger-600: #dc2626;
  --color-danger-700: #b91c1c;

  /* Warning (amber) */
  --color-warning:     #f59e0b;
  --color-warning-50:  #fffbeb;
  --color-warning-100: #fef3c7;
  --color-warning-400: #fbbf24;
  --color-warning-500: #f59e0b;
  --color-warning-600: #d97706;
  --color-warning-700: #b45309;

  /* Info (blue) */
  --color-info:     #3b82f6;
  --color-info-50:  #eff6ff;
  --color-info-100: #dbeafe;
  --color-info-400: #60a5fa;
  --color-info-500: #3b82f6;
  --color-info-600: #2563eb;
  --color-info-700: #1d4ed8;

  /* Backgrounds (light — tom verde sutil) */
  --color-background:          #f0f7f5;
  --color-background-surface:  #ffffff;
  --color-background-elevated: #e8f4f0;
  --color-background-sidebar:  #f5faf8;

  /* Borders (light) */
  --color-border:       #ddeee8;
  --color-border-muted: #eef7f4;
}
```

> Nota: as escalas semânticas (success/danger/warning/info) são **parciais** de propósito (só 50/100/400/500/600/700 — sem 200/300/800/900). Só `primary` tem a escala completa 50→900.

### 1.2 Paleta resumida

| Token | Light | Dark | Uso |
|---|---|---|---|
| `bg-background` | `#f0f7f5` | `#0c1629` | Canvas do app (root) |
| `bg-background-surface` | `#ffffff` | `#111f35` | Cards, modais, popovers |
| `bg-background-elevated` | `#e8f4f0` | `#182a42` | Inputs, hover de botões/linhas |
| `bg-background-sidebar` | `#f5faf8` | `#08111f` | Sidebar + topbar (uma moldura só) |
| `border-border` | `#ddeee8` | `#192c44` | Bordas/divisores estruturais |
| `border-border-muted` | `#eef7f4` | `#111f35` | Bordas sutis |
| `primary` (emerald) | `#10b981` (escala 50–900) | igual | Acento/marca |
| `danger` / `warning` / `info` / `success` | red / amber / blue / emerald | igual | Semânticos |

### 1.3 Dark mode (padrão LIGADO)

Estratégia: classe `.dark` em `<html>`. Só os tokens de background/border mudam — as escalas de cor (primary/danger/...) permanecem iguais, então os componentes **nunca** ramificam por tema nas superfícies.

```css
/* index.css — overrides dark */
.dark {
  --color-background:          #0c1629;
  --color-background-surface:  #111f35;
  --color-background-elevated: #182a42;
  --color-background-sidebar:  #08111f;
  --color-border:              #192c44;
  --color-border-muted:        #111f35;
}
```

**Anti-FOUC** — rode antes do React montar (em `index.html`, dentro do `<head>`):
```html
<script>
  var t = localStorage.getItem("taskhs-theme");
  if (t !== "light") document.documentElement.classList.add("dark");
</script>
```

**Toggle** (vive no `MainLayout`, não no AuthContext):
```ts
const [dark, setDark] = useState(() => localStorage.getItem("taskhs-theme") !== "light");
function toggleTheme() {
  const next = !dark;
  setDark(next);
  localStorage.setItem("taskhs-theme", next ? "dark" : "light");
  document.documentElement.classList.toggle("dark", next);
}
```
Chave de persistência: `localStorage["taskhs-theme"]` ∈ `"dark" | "light"`.

### 1.4 Estilos base + inversão de texto (CRÍTICO)

O app é escrito **dark-first**: os componentes usam `text-slate-100/200/.../600` assumindo fundo escuro. No light mode esses valores são **invertidos** via CSS para continuarem legíveis. Sem este bloco, texto `text-slate-100` fica invisível no claro.

```css
/* ── Base ── */
body {
  background-color: var(--color-background);
  font-family: var(--font-sans);
  -webkit-font-smoothing: antialiased;
  font-feature-settings: "cv02", "cv03", "cv04", "cv11"; /* variantes glíficas DM Sans */
  color: rgb(15 23 42);          /* slate-900 no light */
}
.dark body { color: rgb(235 240 250); }

/* ── Inversão de texto no light mode ── */
html:not(.dark) .text-slate-100 { color: rgb(15 23 42);    } /* → slate-900 (mais escuro) */
html:not(.dark) .text-slate-200 { color: rgb(30 41 59);    } /* → slate-800 */
html:not(.dark) .text-slate-300 { color: rgb(51 65 85);    } /* → slate-700 */
html:not(.dark) .text-slate-400 { color: rgb(71 85 105);   } /* → slate-600 */
html:not(.dark) .text-slate-500 { color: rgb(100 116 139); } /* → slate-500 */
html:not(.dark) .text-slate-600 { color: rgb(148 163 184); } /* → slate-400 (mais claro) */

/* ── Scrollbar custom (6px) ── */
::-webkit-scrollbar       { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--color-border); border-radius: 9999px; }
::-webkit-scrollbar-thumb:hover { background: var(--color-primary-300); }

/* ── Glow utilitário ── */
.glow-primary { box-shadow: 0 0 20px -4px color-mix(in srgb, #10b981 40%, transparent); }

#root { width: 100%; height: 100vh; }
```

**Mapa mental do `text-slate-*`** (vale para os dois temas): `100` = título / `200`-`300` = corpo / `400`-`500` = mutado / `600` = fraquíssimo.

---

## 2. Helper `cn()`

Todo snippet depende disto (`src/lib/utils.ts`):
```ts
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

---

## 3. Tipografia

**Família:** DM Sans (Google Fonts), pesos **300/400/500/600/700/800** + itálico 400, eixo óptico `opsz 9..40`. Antialiasing + `font-feature-settings: "cv02","cv03","cv04","cv11"`.

### Escala (todas as combinações reais em uso)

| Papel | Classes |
|---|---|
| Título de página | `text-2xl font-extrabold text-slate-100` (auth: `+ tracking-tight`) |
| Valor de StatCard | `text-2xl font-extrabold text-slate-100 leading-none` |
| Saudação dashboard | `text-xl font-extrabold text-slate-100` |
| Título de modal | `text-base font-bold text-slate-100` |
| Título de card | `text-sm font-semibold text-slate-100` (hover `group-hover:text-primary`, `truncate`) |
| Nome em linha/tabela | `font-semibold text-slate-800 dark:text-slate-100` |
| Label de botão | `text-sm font-semibold` |
| Corpo / subtítulo | `text-sm text-slate-500` |
| Label de campo (form) | `text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5` |
| Eyebrow de seção | `text-xs font-semibold text-slate-500 uppercase tracking-wider` |
| `<th>` de tabela | `text-xs font-semibold uppercase tracking-wider text-slate-400` |
| Label de StatCard | `text-xs text-slate-500 mt-1 font-medium` |
| Texto de badge | `text-xs font-semibold` |
| Legenda / fraco | `text-[11px] text-slate-600` |
| Micro-tag | `text-[10px] font-medium` |

**Ladder de peso:** `font-extrabold` (títulos/valores) → `font-bold` (título de modal, %) → `font-semibold` (labels, botões, nomes, badges) → `font-medium` (label de stat, switch).
**Ladder de tamanho:** `text-2xl` → `text-xl` → `text-base` → `text-sm` → `text-xs` → `text-[11px]` → `text-[10px]`.

---

## 4. Convenções transversais

### Raio (radius ladder)
- `rounded-2xl` → modais, painéis-card, banner de boas-vindas, canvas do board, chip de logo.
- `rounded-xl` → cards de board, colunas kanban, menus/popovers, stat cards, containers de ícone.
- `rounded-lg` → botões, inputs, cards kanban, itens de menu.
- `rounded-md` / `rounded` → inputs compactos, botões de ícone.
- `rounded-full` → pills, badges, avatares, swatches, dots, trilho de progresso, toggle.

### Sombra (shadow ladder)
- `shadow-sm` → chips/cards estáticos.
- `shadow-md` → hover de card.
- `shadow-lg` → tooltip, hover de card clicável (`hover:shadow-lg hover:shadow-primary/5`).
- `shadow-2xl` → overlays flutuantes (modais, dropdowns, painéis).
- `shadow-[inset_2px_0_0_#10b981]` → barra de acento da nav ativa (sem deslocar layout).

### Transições
- `transition-colors duration-200` → hover de botões/links (padrão).
- `transition-all duration-150` → botões/cards interativos.
- `transition-all duration-200` → hover de cards, itens de nav.
- `transition-[width] duration-300 ease-in-out` → colapso da sidebar.
- `transition-all duration-700` → barra de progresso (preenchimento).
- Feedback de clique: **`active:scale-95`** (botões) / `active:scale-[0.98]` (botão full-width de auth).

### Espaçamento
- Ritmo vertical: `space-y-6` (seções) · `space-y-4` (campos de form) · `space-y-2`/`space-y-3` (blocos).
- Padding de página: `px-4 md:px-6 py-6`.
- Padding de card: StatCard `p-5` · card de board `p-4` · modal/login `p-6`.
- Containers: auth `max-w-sm` · modal `max-w-md`/`max-w-lg` · página de tabela `max-w-4xl mx-auto` · dashboard full-width.
- Idiom de scroll: **`flex flex-col flex-1 min-h-0 overflow-y-auto`**.

### Padrões de comportamento
- **Hover-reveal:** pai recebe `group` (ou nomeado `group/card`); filhos usam `opacity-0 group-hover:opacity-100` (handles de drag, estrela, ícones de editar/excluir).
- **Tinted-by-data:** cores dinâmicas (cor do board/lista/label) entram via `style={{ backgroundColor: \`${color}20\` }}` (sufixos hex-alpha: `18`, `20`, `25`, `28`, `30`) com classes Tailwind neutras na estrutura.
- **z-index:** modais/painéis `z-50` · popovers/menus `z-20` · handle de drag de card `z-10`.
- **Focus ring:** sempre `focus:outline-none` + `focus:ring-2 focus:ring-primary` (forte) / `focus:ring-primary/40` ou `/50` (suave) / `focus:ring-1 focus:ring-primary/50` (compacto).

---

## 5. App Shell (layout + navegação)

Sidebar fixa à esquerda + coluna principal (topbar + conteúdo). A página inteira **não rola** — o scroll é delegado às regiões internas. Colapso é manual (não viewport-driven), via transição de largura + tooltips (não é off-canvas).

```jsx
<div className="flex h-screen overflow-hidden bg-background">
  <aside className={cn(
    "flex flex-col shrink-0 bg-background-sidebar border-r border-border",
    "transition-[width] duration-300 ease-in-out overflow-hidden",
    collapsed ? "w-18" : "w-64",
  )}>
    {/* header do logo (h-16) · nav (flex-1) · footer */}
  </aside>

  <div className="flex flex-col flex-1 overflow-hidden min-w-0"> {/* min-w-0 impede overflow do conteúdo */}
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-border bg-background-sidebar px-4 md:px-6">
      {/* topbar */}
    </header>
    <main className="flex flex-col flex-1 overflow-hidden">{children}</main>
  </div>
</div>
```

Regras-chave: sidebar `w-64` (aberta) / `w-18` (rail) · header do logo e topbar ambos `h-16` (alinham) · `min-w-0` na coluna principal é o que impede o conteúdo largo (boards) de estourar o layout.

### 5.1 Nav item (com estados ativo/inativo + tooltip no modo colapsado)

```jsx
const NAV_ITEMS = [
  { label: "Dashboard", icon: <IconDashboard />, to: "/",        adminOnly: false },
  { label: "Boards",    icon: <IconBoards />,    to: "/boards",  adminOnly: false },
  { label: "Usuários",  icon: <IconUsers />,     to: "/usuarios", adminOnly: true  },
];
// .filter(item => !item.adminOnly || user?.is_admin)

const active = to === "/"
  ? location.pathname === "/" || location.pathname === "/dashboard"
  : location.pathname.startsWith(to); // startsWith mantém "Boards" ativo em /boards/:id

<Link to={to} title={collapsed ? label : undefined} className={cn(
  "relative group flex items-center w-full rounded-lg text-sm font-medium transition-all duration-200",
  collapsed ? "justify-center px-0 py-2.5 mx-1" : "gap-3 px-3 py-2",
  active
    ? ["bg-primary/10 text-primary font-semibold", !collapsed && "shadow-[inset_2px_0_0_#10b981] pl-2.5"]
    : [!collapsed && "pl-2.5", "text-slate-400 dark:text-slate-500", "hover:bg-background-elevated hover:text-slate-100"],
)}>
  {icon}
  {!collapsed && <span className="truncate">{label}</span>}
  {collapsed && (
    <span className="pointer-events-none absolute left-full ml-3 z-50 whitespace-nowrap rounded-lg bg-background-surface border border-border px-2.5 py-1.5 text-xs font-medium text-slate-200 shadow-lg opacity-0 group-hover:opacity-100 transition-opacity duration-150">
      {label}
    </span>
  )}
</Link>
```

### 5.2 Logo (chip `rounded-xl bg-primary/15`)
```jsx
<div className={cn("flex h-16 shrink-0 items-center border-b border-border", collapsed ? "justify-center px-0" : "px-5")}>
  {collapsed ? (
    <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-primary/15"><span className="text-sm font-bold text-primary">T</span></div>
  ) : (
    <div className="flex items-center gap-2.5">
      <div className="w-8 h-8 rounded-xl bg-primary/15 flex items-center justify-center shrink-0">
        <img src={logo} alt="" className="w-5 h-5 object-contain" onError={e => { (e.target as HTMLImageElement).style.display = "none" }} />
      </div>
      <span className="font-bold text-slate-100 text-base tracking-tight">TaskHS</span>
    </div>
  )}
</div>
```

### 5.3 Topbar — botão de ícone + avatar + dropdown de notificações
```jsx
{/* Botão de ícone (hamburger, tema, sino, logout) */}
className="rounded-lg p-2 text-slate-400 hover:bg-background-elevated hover:text-slate-100 transition-colors duration-200"
{/* variante logout: hover:text-danger-400 */}

{/* Avatar de iniciais — gradiente emerald */}
<div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary-400 to-primary-700 flex items-center justify-center text-white text-xs font-bold shadow-sm">
  {user?.initials ?? "?"}
</div>

{/* Dropdown ancorado (click-outside via ref + listener de mousedown) */}
<div className="absolute right-0 top-full mt-2 w-80 rounded-xl bg-background-surface border border-border shadow-2xl z-50 flex flex-col overflow-hidden">…</div>
```

### 5.4 Rotas (`App.tsx`)
```jsx
<AuthProvider><BrowserRouter><Routes>
  <Route path="/login" element={<LoginPage />} />
  <Route path="/*" element={
    <ProtectedRoute><MainLayout><Routes>
      <Route index element={<DashboardPage />} />
      <Route path="dashboard" element={<DashboardPage />} />
      <Route path="boards" element={<BoardsPage />} />
      <Route path="boards/:id" element={<BoardPage />} />
      <Route path="usuarios" element={<UsersPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes></MainLayout></ProtectedRoute>
  } />
</Routes></BrowserRouter></AuthProvider>

// ProtectedRoute: if (!user) return <Navigate to="/login" replace />; return <>{children}</>;
```

---

## 6. Componentes

### 6.1 Botões

| Variante | Classes |
|---|---|
| **Primary** | `flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg bg-primary text-white hover:bg-primary-600 active:scale-95 transition-all duration-150` |
| **Primary full-width** | `w-full py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed transition-all` |
| **Secondary (outline)** | `flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg border border-border text-slate-300 hover:bg-background-elevated active:scale-95 transition-all duration-150` |
| **Danger (solid)** | `text-xs px-3 py-1.5 rounded-lg bg-red-500 text-white hover:bg-red-600 disabled:opacity-50 transition-colors font-semibold` |
| **Danger (outline)** | `w-full py-2.5 rounded-lg border border-red-500/40 text-red-400 text-sm font-semibold hover:bg-red-500/10 transition-colors flex items-center justify-center gap-2` |
| **Ghost / texto** | `flex items-center gap-2 text-xs text-slate-500 hover:text-primary transition-colors` |
| **Icon-only** | `p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-background-elevated transition-colors` |
| **Pill toggle** | base `text-xs px-2.5 py-1 rounded-full font-medium transition-all`; ativo `bg-primary/15 text-primary`; inativo `text-slate-500 hover:text-slate-300 hover:bg-background-elevated` |
| **Dashed "add"** | `rounded-xl border-2 border-dashed border-border hover:border-primary/40 hover:text-primary text-slate-600 text-sm font-medium flex flex-col items-center justify-center gap-2 p-8 transition-all duration-150` |

### 6.2 Modal / Dialog
```jsx
{/* Overlay: black + blur */}
<div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
     onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
  {/* Container */}
  <div className="w-full max-w-md rounded-2xl bg-background-surface border border-border shadow-2xl">
    {/* Header */}
    <div className="flex items-center justify-between px-5 py-4 border-b border-border">
      <h2 className="text-base font-bold text-slate-100">Título</h2>
      <button className="p-1.5 rounded-lg text-slate-500 hover:text-slate-200 hover:bg-background-elevated transition-colors"><IX /></button>
    </div>
    {/* Body */}
    <form className="p-6 space-y-4">…</form>
    {/* Footer: dois botões iguais */}
    <div className="flex gap-2 pt-1">
      <button className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">Cancelar</button>
      <button className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all">Confirmar</button>
    </div>
  </div>
</div>
```
Variantes de container: `max-w-lg` (import), `max-w-[900px] ... flex flex-col` (detalhe de card, com barra de acento `<div className="h-1.5 shrink-0" style={{backgroundColor}}/>` como primeiro filho). Modais **não** têm animação de entrada/saída — montam/desmontam condicionalmente.

### 6.3 Painel slide-in (drawer à direita)
```jsx
<div className="fixed inset-0 z-50 flex">
  <div className="flex-1 bg-black/40" onClick={onClose} />          {/* backdrop sem blur */}
  <div className="w-[380px] bg-background-surface border-l border-border flex flex-col h-full shadow-2xl">
    <div className="flex items-center justify-between px-5 py-4 border-b border-border shrink-0">
      <div className="flex items-center gap-2"><IGear /><h2 className="text-sm font-semibold text-slate-200">Configurações</h2></div>
      <button className="p-1.5 rounded-lg text-slate-500 hover:text-slate-200 hover:bg-background-elevated transition-colors"><IX /></button>
    </div>
    <div className="flex-1 overflow-y-auto p-5 space-y-4">{/* corpo */}</div>
    <div className="border-t border-border p-5 shrink-0">       {/* zona de perigo */}
      <p className="text-xs font-semibold text-slate-400 mb-3">Zona de perigo</p>
      <button className="w-full py-2.5 rounded-lg border border-red-500/40 text-red-400 text-sm font-semibold hover:bg-red-500/10 transition-colors flex items-center justify-center gap-2"><ITrash />Excluir</button>
    </div>
  </div>
</div>
```
Larguras: `w-[380px]` (config/labels), `w-[420px]` (arquivados).

### 6.4 Card (board) — acento de cor + hover-lift
```jsx
<div className="group cursor-pointer text-left rounded-xl bg-background-surface border border-border hover:border-primary/40 hover:shadow-lg hover:shadow-primary/5 transition-all duration-200 overflow-hidden">
  <div className="h-2" style={{ backgroundColor: board.color }} />            {/* barra de acento no topo */}
  <div className="p-4">
    <div className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0 text-white/80" style={{ backgroundColor: `${board.color}30` }}><IBoard /></div>
    <p className="font-semibold text-slate-100 group-hover:text-primary transition-colors leading-snug mb-1">{board.title}</p>
    <p className="text-xs text-slate-500 line-clamp-2 leading-relaxed">{board.description}</p>
    <p className="text-[11px] text-slate-600 mt-3">{date}</p>
  </div>
</div>
```

### 6.5 Inputs de formulário
```jsx
{/* Label (uppercase) */}
<label className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">E-mail</label>

{/* Text input (ring forte, borda some no focus) */}
<input className="w-full px-3 py-2.5 text-sm rounded-lg border border-border bg-background-elevated text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-colors" />

{/* Search (ícone à esquerda) */}
<div className="relative flex-1 min-w-45">
  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none"><ISearch /></span>
  <input className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-border bg-background-elevated text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-colors" />
</div>

{/* Textarea */}
<textarea className="w-full text-sm text-slate-200 bg-background-elevated border border-border rounded-lg px-3 py-2.5 resize-none focus:outline-none focus:ring-2 focus:ring-primary/40 placeholder-slate-500 leading-relaxed" />

{/* Select (chevron custom) */}
<div className="relative">
  <select className="appearance-none pl-3 pr-8 py-2 text-sm rounded-lg border border-border bg-background-elevated text-slate-300 focus:outline-none focus:ring-2 focus:ring-primary/50 cursor-pointer transition-colors">…</select>
  <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none"><IChevron /></span>
</div>
```

### 6.6 Dropdown menu / popover
```jsx
<div className="relative" ref={menuRef}>  {/* click-outside via listener de mousedown */}
  <div className="absolute right-0 top-full mt-1 z-20 w-44 rounded-xl bg-background-surface border border-border shadow-xl overflow-hidden">
    <button className="w-full flex items-center gap-2.5 px-3 py-2.5 text-sm text-slate-300 hover:bg-background-elevated transition-colors text-left">Item</button>
    {/* item danger (divisor = border-t no próximo item) */}
    <button className="w-full flex items-center gap-2.5 px-3 py-2.5 text-sm text-red-400 hover:bg-red-500/10 transition-colors text-left border-t border-border">Excluir</button>
  </div>
</div>
```

### 6.7 Color pickers (paletas preset)
```js
// Cores de board:
const COLORS = ["#0ea5e9","#6366f1","#10b981","#f59e0b","#ef4444","#8b5cf6","#ec4899","#14b8a6"];
// Cores de label/lista:
const LABEL_COLORS = ["#ef4444","#f97316","#f59e0b","#22c55e","#0ea5e9","#8b5cf6","#ec4899","#64748b"];
```
```jsx
{/* Swatch com ring no selecionado */}
<button type="button" onClick={() => setColor(c)}
  className={cn("w-7 h-7 rounded-full transition-all duration-150",
    color === c ? "ring-2 ring-offset-2 ring-offset-background-surface scale-110" : "opacity-70 hover:opacity-100")}
  style={{ backgroundColor: c }} />

{/* Variante border-grow */}
className={cn("w-7 h-7 rounded-full border-2 transition-transform", color === c ? "scale-125 border-white/80" : "border-transparent")}
```

### 6.8 Spinner + barra de progresso
```jsx
{/* Spinner */}
<svg className="w-5 h-5 animate-spin text-primary" fill="none" viewBox="0 0 24 24">
  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
</svg>

{/* Barra de progresso (verde a 100%, indigo abaixo) */}
<div className="h-2 rounded-full bg-background-elevated overflow-hidden">
  <div className="h-full rounded-full transition-all duration-700" style={{ width: `${pct}%`, backgroundColor: pct === 100 ? "#10b981" : "#818cf8" }} />
</div>
{/* Variante dashboard: bg-gradient-to-r from-primary to-emerald-400 */}
```

### 6.9 Badges, tags, avatares, empty state
```jsx
{/* Badge de contagem (tinted-by-data) */}
<span className="text-xs font-bold px-2 py-0.5 rounded-full" style={{ backgroundColor: `${color}20`, color }}>{n}</span>

{/* Role badge (admin = primary, membro = cinza) */}
<span className={cn("inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full",
  isAdmin ? "bg-primary/10 text-primary" : "bg-slate-100 dark:bg-background-elevated text-slate-500")}>…</span>

{/* Tag/label (hex-alpha 25%) */}
<span className="text-[10px] font-semibold px-2 py-0.5 rounded-full" style={{ backgroundColor: `${l.color}25`, color: l.color }}>{l.label}</span>

{/* Avatar de iniciais */}
<div className="w-6 h-6 rounded-full bg-gradient-to-br from-primary-400 to-primary-700 flex items-center justify-center shrink-0">
  <span className="text-[9px] font-bold text-white leading-none">{initials}</span>
</div>

{/* Empty state */}
<div className="rounded-xl border-2 border-dashed border-border flex flex-col items-center justify-center py-12 text-center gap-3">
  <div className="w-12 h-12 rounded-xl bg-background-elevated flex items-center justify-center text-slate-500"><IBoard /></div>
  <p className="text-sm font-semibold text-slate-400">Nenhum item ainda</p>
  <button className="text-sm text-primary hover:underline">Criar primeiro</button>
</div>
```

### 6.10 Toggle switch (custom, sem checkbox nativo)
```jsx
<div onClick={() => set(!on)} className={cn("w-10 h-6 rounded-full transition-colors relative shrink-0", on ? "bg-primary" : "bg-slate-200 dark:bg-border")}>
  <span className={cn("absolute top-1 w-4 h-4 rounded-full bg-white shadow transition-transform", on ? "translate-x-5" : "translate-x-1")} />
</div>
```

### 6.11 Segmented control (toggle de view)
```jsx
<div className="flex items-center rounded-lg border border-border bg-background-elevated overflow-hidden">
  <button className={cn("p-2 transition-colors duration-150", active ? "bg-primary/15 text-primary" : "text-slate-500 hover:text-slate-300")}><IGrid /></button>
  <button className={cn("p-2 transition-colors duration-150", active ? "bg-primary/15 text-primary" : "text-slate-500 hover:text-slate-300")}><IList /></button>
</div>
```

---

## 7. Kanban (específico do produto)

- **Largura de coluna padrão:** `w-[272px] shrink-0`.
- **Coluna:** `flex flex-col w-[272px] shrink-0 rounded-xl overflow-hidden` + `style={{ backgroundColor: "rgba(13, 22, 36, 0.85)" }}`.
- **Card kanban:** acento via `border-l-4` por prioridade (`border-l-red-500` crítica · `border-l-amber-500` alta · `border-l-indigo-400` média · `border-l-slate-600` baixa); dragging = `shadow-2xl rotate-1 opacity-95 scale-105`.
- **Área de drop (highlight ao arrastar):** `... min-h-[60px] rounded-lg transition-colors duration-150` + `isOver && "bg-primary/5"`.
- **Canvas do board:** fundo em gradiente com a cor do board:
  ```jsx
  style={{ background: `linear-gradient(160deg, ${hexToRgba(board.color, 0.14)} 0%, ${hexToRgba(board.color, 0.04)} 35%, #0a1525 70%)` }}
  ```
- **DragOverlay:** `<div className="w-[272px] rotate-2 shadow-2xl">`.

---

## 8. StatCard (dashboard)
```jsx
function StatCard({ label, value, icon, color, sub }) {
  return (
    <div className="rounded-xl bg-background-surface border border-border p-5 flex items-center gap-4">
      <div className={cn("w-12 h-12 rounded-xl flex items-center justify-center shrink-0", color)}>{icon}</div>
      <div className="min-w-0">
        <p className="text-2xl font-extrabold text-slate-100 leading-none">
          {value === undefined ? <span className="w-8 h-6 rounded bg-background-elevated animate-pulse inline-block" /> : value}
        </p>
        <p className="text-xs text-slate-500 mt-1 font-medium">{label}</p>
        {sub && <p className="text-[11px] text-slate-600 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}
// color (tint convention): "bg-primary/15 text-primary" | "bg-indigo-500/15 text-indigo-400"
//   | (valor>0 ? "bg-red-500/15 text-red-400" : "bg-slate-700/40 text-slate-500")  ← inativo = cinza
// grid: grid grid-cols-2 lg:grid-cols-4 gap-4
```

---

## 9. Tabela de dados
```jsx
<div className="rounded-2xl border border-border bg-background-surface overflow-hidden shadow-sm">
  <table className="w-full text-sm">
    <thead>
      <tr className="border-b border-border bg-background-elevated">
        <th className="text-left px-5 py-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Coluna</th>
      </tr>
    </thead>
    <tbody className="divide-y divide-border">
      <tr className="hover:bg-background-elevated transition-colors">
        <td className="px-5 py-4">…</td>
      </tr>
    </tbody>
  </table>
</div>
```
Paddings: head `px-5 py-3`, body `px-5 py-4`. Avatar em tabela: `w-9 h-9 rounded-full bg-primary/10 border border-primary/20` com iniciais `text-xs font-bold text-primary`.

---

## 10. Ícones

**Convenção:** SVG inline como componentes `I*` / `Icon*`. Todos: `fill="none" viewBox="0 0 24 24" stroke="currentColor"` + `strokeLinecap="round" strokeLinejoin="round"` nos paths. A cor segue o `text-*` ao redor (`currentColor`).

| Contexto | Tamanho | strokeWidth |
|---|---|---|
| Ícones de nav / decorativos / stat | `w-5 h-5` (`shrink-0` na nav) | `1.75` |
| Ícones de ação / botão | `w-4 h-4` | `2` |
| `IPlus` / `ICheck` (add/confirma) | `w-4 h-4` | `2.5` |
| Spinner | `w-4 h-4` ou `w-5 h-5` `animate-spin text-primary` | circle `4` |
| `IStar` | `w-4 h-4` | `2` (único com `fill` toggling: `fill={filled ? "currentColor" : "none"}`) |

Template:
```jsx
function IconExample() {
  return (
    <svg className="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
      <path strokeLinecap="round" strokeLinejoin="round" d="…" />
    </svg>
  );
}
```

---

## 11. Tela de login (referência completa)
```jsx
<div className="min-h-screen flex items-center justify-center bg-background px-4">
  <div className="w-full max-w-sm">
    <div className="flex flex-col items-center mb-8">
      <div className="w-14 h-14 rounded-2xl bg-primary/10 dark:bg-primary/15 flex items-center justify-center mb-3 shadow-sm">
        <img src={logo} alt="" className="w-9 h-9 object-contain" onError={e => { (e.target as HTMLImageElement).style.display = "none" }} />
      </div>
      <h1 className="text-2xl font-extrabold text-slate-900 dark:text-slate-100 tracking-tight">TaskHS</h1>
      <p className="text-sm text-slate-500 mt-1">Gestão de SST — faça login para continuar</p>
    </div>
    <div className="rounded-2xl bg-white dark:bg-background-surface border border-slate-200 dark:border-border shadow-sm p-6">
      <form className="space-y-4">
        {/* labels + inputs (6.5), erro (abaixo), submit com spinner */}
        {error && (
          <div className="flex items-center gap-2 rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">
            <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
            {error}
          </div>
        )}
      </form>
    </div>
    <p className="text-center text-xs text-slate-400 mt-6">TaskHS · Health & Safety Tech · v0.1.0</p>
  </div>
</div>
```

---

## Resumo dos princípios (cole no topo do prompt de outra IA)

1. **Dark-first**, light via classe `.dark` (só backgrounds/borders mudam). Texto escrito como `text-slate-100→600` e invertido no light via CSS.
2. **Marca = emerald `#10b981`** (`primary`). Acentos sempre em `primary` com opacidade (`/5 /10 /15`).
3. **Superfícies:** `background` (canvas) → `background-surface` (cards/modais) → `background-elevated` (inputs/hover). Bordas sempre `border-border`.
4. **Raio:** `2xl` superfícies grandes → `xl` cards/menus → `lg` botões/inputs → `full` pills/avatares.
5. **Tudo anima:** `transition-colors`/`transition-all`; clique = `active:scale-95`.
6. **Cores dinâmicas** (board/lista/label) via `style` inline com hex-alpha; estrutura em classes neutras.
7. **Ícones:** SVG inline, `viewBox 0 0 24 24`, `currentColor`, stroke `1.75` (nav) / `2` (ação).
8. **Sem libs de UI/animação.** `cn()` (clsx + tailwind-merge) é o único utilitário.
