import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Spinner } from '../../components/ui/Spinner'
import { SearchBar } from '../../components/ui/SearchBar'
import { PaginationOffset } from '../../components/ui/Pagination'
import { Select } from '../../components/ui/Select'
import { ApiError } from '../../lib/api'
import { useAuth } from '../../auth/AuthContext'
import { podeGerenciarCadastros } from '../../auth/roles'
import { equipamentosClienteApi, STATUS_CALIBRACAO, type FrotaItem } from './api'
import { PageContainer } from '../../components/ui/Page'
import { cn } from '../../lib/utils'
import { BotaoExportar } from '../../components/ui/BotaoExportar'

const LIMITE = 25

export function FrotaPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const clienteParam = searchParams.get('cliente')
  const clienteId = clienteParam ? Number(clienteParam) : undefined

  const [statusFiltro, setStatusFiltro] = useState('')
  const [ativoFiltro, setAtivoFiltro] = useState('')
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
      .listar({
        cliente: clienteId,
        status: statusFiltro || undefined,
        ativo: ativoFiltro === '' ? undefined : ativoFiltro === 'true',
        q: busca || undefined,
        offset,
        limit: LIMITE,
      })
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
  }, [clienteId, statusFiltro, ativoFiltro, busca, offset])

  function onBuscar(e: FormEvent) {
    e.preventDefault()
    setOffset(0)
    setBusca(termo.trim())
  }

  const nomeCliente = itens?.[0]?.cliente_nome

  return (
    <PageContainer>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-extrabold text-slate-100">Equipamentos</h1>
        <div className="flex items-start gap-2">
          <BotaoExportar
            caminho="/equipamentos-cliente/exportar"
            params={{ cliente: clienteId, status: statusFiltro, ativo: ativoFiltro, q: busca }}
            nome="equipamentos"
          />
          {podeGerenciarCadastros(user) && (
            <Button
              onClick={() => { if (clienteId) navigate(`/app/equipamentos/novo?cliente=${clienteId}`) }}
              disabled={!clienteId}
              title={clienteId ? undefined : 'Filtre por um cliente para adicionar'}
            >
              Novo aparelho
            </Button>
          )}
        </div>
      </div>

      {clienteId && (
        <div className="flex items-center gap-2 text-sm">
          <span className="rounded-full bg-primary/10 text-primary px-3 py-1 font-medium">
            Cliente: {nomeCliente ?? `#${clienteId}`}
          </span>
          <button onClick={() => navigate('/app/equipamentos')} className="text-xs text-slate-400 hover:text-slate-200">limpar</button>
        </div>
      )}

      <SearchBar
        value={termo}
        onChange={setTermo}
        onSubmit={onBuscar}
        placeholder="Série ou patrimônio"
        antes={
          <div className="flex gap-3">
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
            <div className="w-48">
              <Select
                id="ativo"
                label="Aparelhos"
                value={ativoFiltro}
                onChange={(e) => {
                  setOffset(0)
                  setAtivoFiltro(e.target.value)
                }}
              >
                <option value="">Todos</option>
                <option value="true">Ativos</option>
                <option value="false">Inativos</option>
              </Select>
            </div>
          </div>
        }
      />

      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}

      {itens === null ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum aparelho encontrado.</p>
      ) : (
        <>
          <Table
            head={<><TH>Aparelho</TH><TH>Cliente</TH><TH>Série / Patrimônio</TH><TH>Próx. calibração</TH><TH>Status</TH></>}
            footer={<PaginationOffset offset={offset} limit={LIMITE} total={total} onOffsetChange={setOffset} itemLabel="aparelhos" />}
          >
            {itens.map((e) => {
              const s = STATUS_CALIBRACAO[e.status_calibracao]
              return (
                <tr
                  key={e.id}
                  className={cn('hover:bg-background-elevated transition-colors cursor-pointer', !e.ativo && 'opacity-60')}
                  onClick={() => navigate(`/app/equipamentos/${e.id}`)}
                >
                  <TD>
                    <span className="inline-flex items-center gap-2">
                      {e.equipamento_descricao ?? '—'}
                      {!e.ativo && <Badge tone="neutral">Inativo</Badge>}
                    </span>
                  </TD>
                  <TD>{e.cliente_nome ?? '—'}</TD>
                  <TD>{e.serie || e.patrimonio || '—'}</TD>
                  <TD>{e.prox_calibragem ?? '—'}</TD>
                  <TD><Badge tone={e.ativo ? s.tone : 'neutral'}>{s.label}</Badge></TD>
                </tr>
              )
            })}
          </Table>
        </>
      )}
    </PageContainer>
  )
}
