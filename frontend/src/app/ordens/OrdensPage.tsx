import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Spinner } from '../../components/ui/Spinner'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { cn } from '../../lib/utils'
import { ApiError } from '../../lib/api'
import { ordensApi, TIPO_SERVICO, FASES_FILTRO, formatData, type OrdemListItem, type QuadroColuna } from './api'
import { PageContainer } from '../../components/ui/Page'

const LIMITE = 25
type Vista = 'quadro' | 'lista'

function tipoBadge(tipo: string | null) {
  if (!tipo || !(tipo in TIPO_SERVICO)) return null
  const t = TIPO_SERVICO[tipo as keyof typeof TIPO_SERVICO]
  return <Badge tone={t.tone}>{t.label}</Badge>
}

export function OrdensPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const clienteParam = searchParams.get('cliente')
  const clienteId = clienteParam ? Number(clienteParam) : undefined
  const [vista, setVista] = useState<Vista>('quadro')

  return (
    <PageContainer>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-extrabold text-slate-100">Ordens de Serviço</h1>
        <div className="flex gap-2">
          {(['quadro', 'lista'] as Vista[]).map((v) => (
            <button
              key={v}
              onClick={() => setVista(v)}
              className={cn(
                'text-xs px-3 py-1.5 rounded-full font-medium transition-all',
                vista === v ? 'bg-primary/15 text-primary' : 'text-slate-500 hover:text-slate-300 hover:bg-background-elevated',
              )}
            >
              {v === 'quadro' ? 'Quadro' : 'Lista'}
            </button>
          ))}
        </div>
      </div>

      {clienteId && (
        <div className="flex items-center gap-2 text-sm">
          <span className="rounded-full bg-primary/10 text-primary px-3 py-1 font-medium">Cliente #{clienteId}</span>
          <button onClick={() => navigate('/app/ordens')} className="text-xs text-slate-400 hover:text-slate-200">limpar</button>
        </div>
      )}

      {vista === 'quadro' ? (
        <Quadro clienteId={clienteId} onAbrir={(id) => navigate(`/app/ordens/${id}`)} />
      ) : (
        <Lista clienteId={clienteId} onAbrir={(id) => navigate(`/app/ordens/${id}`)} />
      )}
    </PageContainer>
  )
}

function Quadro({ clienteId, onAbrir }: { clienteId?: number; onAbrir: (id: number) => void }) {
  const [colunas, setColunas] = useState<QuadroColuna[] | null>(null)
  const [erro, setErro] = useState('')

  useEffect(() => {
    let ativo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setColunas(null)
    setErro('')
    ordensApi
      .quadro({ cliente: clienteId })
      .then((c) => {
        if (ativo) setColunas(c)
      })
      .catch((e) => {
        if (!ativo) return
        setErro(e instanceof ApiError ? e.message : 'Falha ao carregar')
        setColunas([])
      })
    return () => {
      ativo = false
    }
  }, [clienteId])

  if (erro) return <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>
  if (colunas === null) return <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>

  return (
    <div className="flex gap-4 overflow-x-auto pb-2">
      {colunas.map((col) => (
        <div key={col.fase} className="w-72 shrink-0 rounded-2xl bg-background-surface border border-border">
          <div className="flex items-center justify-between px-4 py-3 border-b border-border">
            <span className="inline-flex items-center gap-2 text-sm font-semibold text-slate-100">
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: `#${col.cor}` }} />
              {col.descricao}
            </span>
            <span className="text-xs text-slate-500">{col.ordens.length}</span>
          </div>
          <div className="p-3 space-y-2 max-h-[70vh] overflow-y-auto">
            {col.ordens.length === 0 ? (
              <p className="text-xs text-slate-600 px-1">—</p>
            ) : (
              col.ordens.map((o) => (
                <button
                  key={o.id}
                  onClick={() => onAbrir(o.id)}
                  className="w-full text-left rounded-xl bg-background-elevated border border-border p-3 hover:border-primary/40 transition-colors"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-semibold text-slate-100">OS #{o.id}</span>
                    {tipoBadge(o.tipo_servico)}
                  </div>
                  <p className="text-xs text-slate-300 mt-1 truncate">{o.cliente_nome ?? '—'}</p>
                  <p className="text-xs text-slate-500 truncate">
                    {o.equipamento_descricao ?? '—'}
                    {o.equipamento_serie ? ` · ${o.equipamento_serie}` : ''}
                  </p>
                  <p className="text-[11px] text-slate-600 mt-1">chegou {formatData(o.data_chegada)}</p>
                </button>
              ))
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

function Lista({ clienteId, onAbrir }: { clienteId?: number; onAbrir: (id: number) => void }) {
  const [fase, setFase] = useState('')
  const [tipo, setTipo] = useState('')
  const [termo, setTermo] = useState('')
  const [busca, setBusca] = useState('')
  const [offset, setOffset] = useState(0)
  const [itens, setItens] = useState<OrdemListItem[] | null>(null)
  const [total, setTotal] = useState(0)
  const [erro, setErro] = useState('')

  useEffect(() => {
    let ativo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setItens(null)
    setErro('')
    ordensApi
      .listar({ fase: fase ? Number(fase) : undefined, cliente: clienteId, tipo: tipo || undefined, q: busca || undefined, offset, limit: LIMITE })
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
  }, [fase, tipo, busca, clienteId, offset])

  function onBuscar(e: FormEvent) {
    e.preventDefault()
    setOffset(0)
    setBusca(termo.trim())
  }

  const inicio = total === 0 ? 0 : offset + 1
  const fim = Math.min(offset + LIMITE, total)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 items-end">
        <div className="w-44">
          <Select id="fase" label="Fase" value={fase} onChange={(e) => { setOffset(0); setFase(e.target.value) }}>
            <option value="">Todas</option>
            {FASES_FILTRO.map((f) => <option key={f.id} value={f.id}>{f.label}</option>)}
          </Select>
        </div>
        <div className="w-40">
          <Select id="tipo" label="Tipo" value={tipo} onChange={(e) => { setOffset(0); setTipo(e.target.value) }}>
            <option value="">Todos</option>
            <option value="C">Calibração</option>
            <option value="M">Manutenção</option>
            <option value="A">Ambas</option>
          </Select>
        </div>
        <form onSubmit={onBuscar} className="flex gap-2 items-end flex-1 min-w-60">
          <div className="flex-1">
            <Input id="busca" label="Busca" placeholder="Nº da OS, etiqueta ou cliente" value={termo} onChange={(e) => setTermo(e.target.value)} />
          </div>
          <Button type="submit" variant="secondary">Buscar</Button>
        </form>
      </div>

      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}

      {itens === null ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhuma OS encontrada.</p>
      ) : (
        <>
          <Table head={<><TH>OS</TH><TH>Cliente</TH><TH>Equipamento</TH><TH>Fase</TH><TH>Tipo</TH><TH>Chegada</TH><TH>Situação</TH></>}>
            {itens.map((o) => (
              <tr key={o.id} className="hover:bg-background-elevated transition-colors cursor-pointer" onClick={() => onAbrir(o.id)}>
                <TD>#{o.id}</TD>
                <TD>{o.cliente_nome ?? '—'}</TD>
                <TD>{o.equipamento_descricao ?? '—'}</TD>
                <TD>
                  {o.fase_descricao ? (
                    <span className="inline-flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full" style={{ background: `#${o.fase_cor}` }} />
                      {o.fase_descricao}
                    </span>
                  ) : '—'}
                </TD>
                <TD>{tipoBadge(o.tipo_servico) ?? '—'}</TD>
                <TD>{formatData(o.data_chegada)}</TD>
                <TD>{o.situacao}</TD>
              </tr>
            ))}
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
    </div>
  )
}
