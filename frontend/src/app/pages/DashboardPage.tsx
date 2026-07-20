import { useEffect, useState, type CSSProperties } from 'react'
import { useNavigate } from 'react-router-dom'
import { StatCard } from '../../components/ui/StatCard'
import { Spinner } from '../../components/ui/Spinner'
import { IconFrota, IconSolicitacoes, IconCobranca } from '../../components/ui/icons'
import { ApiError } from '../../lib/api'
import { useAuth } from '../../auth/AuthContext'
import { dashboardApi, type DashboardResumo } from '../dashboard/api'
import { PageContainer } from '../../components/ui/Page'

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
    <PageContainer>
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100">Olá, {user?.nome ?? user?.email} 👋</h1>
        <p className="text-sm text-slate-500 mt-1">Visão geral da operação.</p>
      </div>

      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}

      {dados === null && !erro ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : dados ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <button onClick={() => navigate('/app/equipamentos')} className="text-left">
              <StatCard
                label="Aparelhos vencidos"
                value={dados.aparelhos_vencidos}
                icon={<IconFrota className="w-8 h-8 text-danger" />}
                color="bg-danger/15"
              />
            </button>
            <button onClick={() => navigate('/app/equipamentos')} className="text-left">
              <StatCard
                label="Vencendo (90 dias)"
                value={dados.aparelhos_vencendo}
                icon={<IconFrota className="w-8 h-8 text-warning" />}
                color="bg-warning/15"
              />
            </button>
            <button onClick={() => navigate('/app/solicitacoes')} className="text-left">
              <StatCard
                label="Solicitações pendentes"
                value={dados.solicitacoes_pendentes}
                icon={<IconSolicitacoes className="w-8 h-8 text-primary" />}
                color="bg-primary/15"
              />
            </button>
            <button onClick={() => navigate('/app/cobranca')} className="text-left">
              <StatCard
                label="Clientes a cobrar"
                value={dados.clientes_a_cobrar}
                icon={<IconCobranca className="w-8 h-8 text-primary" />}
                color="bg-primary/15"
              />
            </button>
          </div>

          <div>
            <h2 className="text-sm font-bold text-slate-300 mb-3">OS ativas por fase</h2>
            {/* Uma coluna por fase: o board tem 5 fases ativas, mas o grid acompanha o total real. */}
            <div
              className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-[repeat(var(--fases),minmax(0,1fr))]"
              style={{ '--fases': dados.os_por_fase.length } as CSSProperties}
            >
              {dados.os_por_fase.map((f) => (
                <button
                  key={f.fase}
                  onClick={() => navigate('/app/ordens')}
                  className="flex items-center gap-3 rounded-2xl bg-background-surface border border-border px-5 py-5 text-left hover:bg-background-elevated transition-colors"
                >
                  <span className="w-3.5 h-3.5 rounded-full shrink-0" style={{ background: f.cor ? `#${f.cor}` : '#6b7280' }} />
                  <span className="flex-1 text-base text-slate-300 truncate">{f.descricao}</span>
                  <span className="text-2xl font-extrabold text-slate-100">{f.total}</span>
                </button>
              ))}
            </div>
          </div>
        </>
      ) : null}
    </PageContainer>
  )
}
