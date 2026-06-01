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
