import { type ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { cn } from '../lib/utils'
import { useAuth } from '../auth/AuthContext'
import { isAdmin } from '../auth/roles'
import { IconDashboard, IconUsers, IconCadastros, IconClientes } from '../components/ui/icons'

interface NavItem {
  label: string
  icon: ReactNode
  to: string
  adminOnly?: boolean
}

const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', icon: <IconDashboard />, to: '/app' },
  { label: 'Usuários', icon: <IconUsers />, to: '/app/usuarios', adminOnly: true },
  { label: 'Cadastros', icon: <IconCadastros />, to: '/app/cadastros', adminOnly: true },
  { label: 'Clientes', icon: <IconClientes />, to: '/app/clientes' },
]

export function Sidebar({ collapsed }: { collapsed: boolean }) {
  const location = useLocation()
  const { user } = useAuth()
  const itens = NAV_ITEMS.filter((item) => !item.adminOnly || isAdmin(user))

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
        {itens.map((item) => {
          const active =
            item.to === '/app'
              ? location.pathname === '/app'
              : location.pathname === item.to || location.pathname.startsWith(item.to + '/')
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
