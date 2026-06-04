import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { StatCard } from '../../components/ui/StatCard'
import { Spinner } from '../../components/ui/Spinner'
import { IconFrota, IconSolicitacoes, IconCobranca } from '../../components/ui/icons'
import { ApiError } from '../../lib/api'
import { useAuth } from '../../auth/AuthContext'
import { dashboardApi, type DashboardResumo } from '../dashboard/api'

export function DashboardPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [dados, setDados] = useState<DashboardResumo | null>(null)
  const [erro, setErro] = useState('')

  useEffect(() => {
    let ativo = true
    dashboardApi
      .resumo()
      .then((d) => {
        if (ativo) setDados(d)
      })
      .catch((e) => {
        if (!ativo) return
        setErro(e instanceof ApiError ? e.message : 'Falha ao carregar o dashboard')
      })
    return () => {
      ativo = false
    }
  }, [])

  return (
    <div className="px-4 md:px-6 py-6 space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100">Olá, {user?.nome ?? user?.login} 👋</h1>
        <p className="text-sm text-slate-500 mt-1">Visão geral da operação.</p>
      </div>

      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}

      {dados === null ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <button onClick={() => navigate('/app/frota')} className="text-left">
              <StatCard
                label="Aparelhos vencidos"
                value={dados.aparelhos_vencidos}
                icon={<IconFrota className="w-6 h-6 text-danger" />}
                color="bg-danger/15"
              />
            </button>
            <button onClick={() => navigate('/app/frota')} className="text-left">
              <StatCard
                label="Vencendo (90 dias)"
                value={dados.aparelhos_vencendo}
                icon={<IconFrota className="w-6 h-6 text-warning" />}
                color="bg-warning/15"
              />
            </button>
            <button onClick={() => navigate('/app/solicitacoes')} className="text-left">
              <StatCard
                label="Solicitações pendentes"
                value={dados.solicitacoes_pendentes}
                icon={<IconSolicitacoes className="w-6 h-6 text-primary" />}
                color="bg-primary/15"
              />
            </button>
            <button onClick={() => navigate('/app/cobranca')} className="text-left">
              <StatCard
                label="Clientes a cobrar"
                value={dados.clientes_a_cobrar}
                icon={<IconCobranca className="w-6 h-6 text-primary" />}
                color="bg-primary/15"
              />
            </button>
          </div>

          <div>
            <h2 className="text-sm font-bold text-slate-300 mb-3">OS ativas por fase</h2>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {dados.os_por_fase.map((f) => (
                <button
                  key={f.fase}
                  onClick={() => navigate('/app/ordens')}
                  className="flex items-center gap-3 rounded-xl bg-background-surface border border-border px-4 py-3 text-left hover:bg-background-elevated transition-colors"
                >
                  <span className="w-3 h-3 rounded-full shrink-0" style={{ background: `#${f.cor}` }} />
                  <span className="flex-1 text-sm text-slate-300 truncate">{f.descricao}</span>
                  <span className="text-lg font-extrabold text-slate-100">{f.total}</span>
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
