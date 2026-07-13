import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { cn } from '../lib/utils'
import { useAuth } from '../auth/AuthContext'
import { IconMenu, IconSun, IconMoon, IconLogout, IconUser } from '../components/ui/icons'

function iniciais(nome: string | null, email: string): string {
  const base = (nome ?? email).trim()
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
  const [aberto, setAberto] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setAberto(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-border bg-background-sidebar px-4 md:px-6">
      <button className={iconBtn} onClick={onToggleSidebar} aria-label="Alternar menu">
        <IconMenu />
      </button>

      <div className="flex items-center gap-2">
        <button className={iconBtn} onClick={onToggleTheme} aria-label="Alternar tema">
          {dark ? <IconSun /> : <IconMoon />}
        </button>

        <div className="relative" ref={ref}>
          <button
            onClick={() => setAberto((o) => !o)}
            aria-label="Menu do usuário"
            className="w-8 h-8 rounded-full bg-linear-to-br from-primary-400 to-primary-700 flex items-center justify-center text-white text-xs font-bold shadow-sm"
          >
            {user ? iniciais(user.nome, user.email ?? '') : '?'}
          </button>
          {aberto && (
            <div className="absolute right-0 top-full mt-2 w-48 rounded-xl bg-background-surface border border-border shadow-2xl z-50 overflow-hidden">
              <Link
                to="/app/conta"
                onClick={() => setAberto(false)}
                className="flex items-center gap-2.5 px-3 py-2.5 text-sm text-slate-300 hover:bg-background-elevated transition-colors"
              >
                <IconUser className="w-4 h-4" />
                Minha conta
              </Link>
              <button
                onClick={() => {
                  setAberto(false)
                  logout()
                }}
                className={cn(
                  'w-full flex items-center gap-2.5 px-3 py-2.5 text-sm text-danger hover:bg-danger/10 transition-colors text-left border-t border-border',
                )}
              >
                <IconLogout className="w-4 h-4" />
                Sair
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
