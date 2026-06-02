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
