import { useCallback, useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate, useOutletContext, useParams } from 'react-router-dom'
import { Button } from '../../components/ui/Button'
import { Spinner } from '../../components/ui/Spinner'
import { ApiError } from '../../lib/api'
import { useAuth } from '../../auth/AuthContext'
import { isAdmin } from '../../auth/roles'
import { cn } from '../../lib/utils'
import { PageContainer } from '../../components/ui/Page'
import { clientesApi, type Cliente } from './api'

export type ClienteCtx = { cliente: Cliente; recarregar: () => void }
// eslint-disable-next-line react-refresh/only-export-components
export function useCliente() { return useOutletContext<ClienteCtx>() }

const abaCls = ({ isActive }: { isActive: boolean }) =>
  cn('text-xs px-3 py-1.5 rounded-full font-medium transition-all',
    isActive ? 'bg-primary/15 text-primary' : 'text-slate-500 hover:text-slate-300 hover:bg-background-elevated')

export function ClienteLayout() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const [cliente, setCliente] = useState<Cliente | null>(null)
  const [erro, setErro] = useState('')
  const [recarga, setRecarga] = useState(0)
  const recarregar = useCallback(() => setRecarga((n) => n + 1), [])

  useEffect(() => {
    let ativo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setErro('')
    clientesApi.obter(Number(id))
      .then((c) => { if (ativo) setCliente(c) })
      .catch((e) => { if (ativo) setErro(e instanceof ApiError ? e.message : 'Falha ao carregar') })
    return () => { ativo = false }
  }, [id, recarga])

  async function excluir() {
    if (!window.confirm('Excluir este cliente?')) return
    setErro('')
    try {
      await clientesApi.excluir(Number(id))
      navigate('/app/clientes', { replace: true })
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao excluir')
    }
  }

  if (erro && !cliente) {
    return <PageContainer><div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div></PageContainer>
  }
  if (!cliente) {
    return <div className="flex justify-center py-16"><Spinner className="w-8 h-8" /></div>
  }

  return (
    <PageContainer>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-extrabold text-slate-100">{cliente.nome || 'Cliente'}</h1>
        <div className="flex gap-2">
          {isAdmin(user) && <Button variant="danger" onClick={excluir}>Excluir</Button>}
          <Button variant="secondary" onClick={() => navigate('/app/clientes')}>Voltar</Button>
        </div>
      </div>

      <div className="flex gap-2">
        <NavLink to="." end className={abaCls}>Dados</NavLink>
        <NavLink to="equipamentos" className={abaCls}>Equipamentos</NavLink>
      </div>

      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}

      <Outlet context={{ cliente, recarregar } satisfies ClienteCtx} />
    </PageContainer>
  )
}
