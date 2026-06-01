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
