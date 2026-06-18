import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Spinner } from '../../components/ui/Spinner'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { ApiError } from '../../lib/api'
import { useAuth } from '../../auth/AuthContext'
import { isAdmin } from '../../auth/roles'
import { equipamentosClienteApi, STATUS_CALIBRACAO, type FrotaItem } from './api'
import { PageContainer } from '../../components/ui/Page'

const LIMITE = 25

export function FrotaPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const clienteParam = searchParams.get('cliente')
  const clienteId = clienteParam ? Number(clienteParam) : undefined

  const [statusFiltro, setStatusFiltro] = useState('')
  const [termo, setTermo] = useState('')
  const [busca, setBusca] = useState('')
  const [offset, setOffset] = useState(0)
  const [itens, setItens] = useState<FrotaItem[] | null>(null)
  const [total, setTotal] = useState(0)
  const [erro, setErro] = useState('')

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setOffset(0)
  }, [clienteId])

  useEffect(() => {
    let ativo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setItens(null)
    setErro('')
    equipamentosClienteApi
      .listar({ cliente: clienteId, status: statusFiltro || undefined, q: busca || undefined, offset, limit: LIMITE })
      .then((p) => {
        if (!ativo) return
        setItens(p.items)
        setTotal(p.total)
      })
      .catch((e) => {
        if (!ativo) return
        setErro(e instanceof ApiError ? e.message : 'Falha ao carregar')
        setItens([])
      })
    return () => {
      ativo = false
    }
  }, [clienteId, statusFiltro, busca, offset])

  function onBuscar(e: FormEvent) {
    e.preventDefault()
    setOffset(0)
    setBusca(termo.trim())
  }

  const inicio = total === 0 ? 0 : offset + 1
  const fim = Math.min(offset + LIMITE, total)
  const nomeCliente = itens?.[0]?.cliente_nome

  return (
    <PageContainer>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-extrabold text-slate-100">Equipamentos</h1>
        {isAdmin(user) && (
          <Button
            onClick={() => { if (clienteId) navigate(`/app/frota/novo?cliente=${clienteId}`) }}
            disabled={!clienteId}
            title={clienteId ? undefined : 'Filtre por um cliente para adicionar'}
          >
            Novo aparelho
          </Button>
        )}
      </div>

      {clienteId && (
        <div className="flex items-center gap-2 text-sm">
          <span className="rounded-full bg-primary/10 text-primary px-3 py-1 font-medium">
            Cliente: {nomeCliente ?? `#${clienteId}`}
          </span>
          <button onClick={() => navigate('/app/frota')} className="text-xs text-slate-400 hover:text-slate-200">limpar</button>
        </div>
      )}

      <div className="flex flex-wrap gap-2 items-end">
        <div className="w-48">
          <Select
            id="status"
            label="Status"
            value={statusFiltro}
            onChange={(e) => {
              setOffset(0)
              setStatusFiltro(e.target.value)
            }}
          >
            <option value="">Todos</option>
            <option value="em_dia">Em dia</option>
            <option value="vencendo">Vencendo</option>
            <option value="vencido">Vencido</option>
            <option value="sem_data">Sem data</option>
          </Select>
        </div>
        <form onSubmit={onBuscar} className="flex gap-2 items-end flex-1 min-w-60">
          <div className="flex-1">
            <Input id="busca" label="Busca" placeholder="Série ou patrimônio" value={termo} onChange={(e) => setTermo(e.target.value)} />
          </div>
          <Button type="submit" variant="secondary">Buscar</Button>
        </form>
      </div>

      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}

      {itens === null ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum aparelho encontrado.</p>
      ) : (
        <>
          <Table head={<><TH>Aparelho</TH><TH>Cliente</TH><TH>Série / Patrimônio</TH><TH>Próx. calibração</TH><TH>Status</TH></>}>
            {itens.map((e) => {
              const s = STATUS_CALIBRACAO[e.status_calibracao]
              return (
                <tr key={e.id} className="hover:bg-background-elevated transition-colors cursor-pointer" onClick={() => navigate(`/app/frota/${e.id}`)}>
                  <TD>{e.equipamento_descricao ?? '—'}</TD>
                  <TD>{e.cliente_nome ?? '—'}</TD>
                  <TD>{e.serie || e.patrimonio || '—'}</TD>
                  <TD>{e.prox_calibragem ?? '—'}</TD>
                  <TD><Badge tone={s.tone}>{s.label}</Badge></TD>
                </tr>
              )
            })}
          </Table>
          <div className="flex items-center justify-between text-sm text-slate-400">
            <span>{inicio}–{fim} de {total}</span>
            <div className="flex gap-2">
              <Button variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - LIMITE))}>Anterior</Button>
              <Button variant="secondary" disabled={fim >= total} onClick={() => setOffset(offset + LIMITE)}>Próxima</Button>
            </div>
          </div>
        </>
      )}
    </PageContainer>
  )
}
