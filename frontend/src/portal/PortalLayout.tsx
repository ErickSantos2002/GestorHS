import { type ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { cn } from '../lib/utils'
import { usePortalAuth } from './PortalAuthContext'

const NAV = [
  { label: 'Início', to: '/portal' },
  { label: 'Minha frota', to: '/portal/frota' },
  { label: 'Certificados', to: '/portal/certificados' },
  { label: 'Minhas OS', to: '/portal/os' },
  { label: 'Solicitações', to: '/portal/solicitacoes' },
]

export function PortalLayout({ children }: { children: ReactNode }) {
  const { cliente, logout } = usePortalAuth()
  const location = useLocation()
  return (
    <div className="min-h-screen bg-background">
      <header className="h-16 border-b border-border bg-background-sidebar flex items-center justify-between px-4 md:px-6">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-primary/15 flex items-center justify-center shrink-0">
            <span className="text-sm font-bold text-primary">G</span>
          </div>
          <span className="font-bold text-slate-100 tracking-tight truncate max-w-[40vw]">{cliente?.cliente_nome ?? 'Portal'}</span>
        </div>
        <button onClick={logout} className="text-sm text-slate-400 hover:text-slate-100 transition-colors">Sair</button>
      </header>
      <nav className="border-b border-border bg-background-surface px-2 md:px-6 flex gap-1 overflow-x-auto">
        {NAV.map((item) => {
          const active = item.to === '/portal' ? location.pathname === '/portal' : location.pathname.startsWith(item.to)
          return (
            <Link key={item.to} to={item.to} className={cn('px-3 py-3 text-sm font-medium whitespace-nowrap border-b-2 transition-colors',
              active ? 'border-primary text-primary' : 'border-transparent text-slate-400 hover:text-slate-200')}>
              {item.label}
            </Link>
          )
        })}
      </nav>
      <main>{children}</main>
    </div>
  )
}
