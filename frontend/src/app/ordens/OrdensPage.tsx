import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Table, TH, TD } from '../../components/ui/Table'
import { Badge } from '../../components/ui/Badge'
import { Spinner } from '../../components/ui/Spinner'
import { SearchBar } from '../../components/ui/SearchBar'
import { PaginationOffset } from '../../components/ui/Pagination'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { cn } from '../../lib/utils'
import { ApiError } from '../../lib/api'
import { ordensApi, TIPO_SERVICO, FASES_FILTRO, formatData, type OrdemListItem } from './api'
import { caixasApi, type QuadroCaixaColuna } from '../caixas/api'
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
        <Quadro clienteId={clienteId} onAbrir={(id) => navigate(`/app/caixas/${id}`)} />
      ) : (
        <Lista clienteId={clienteId} onAbrir={(id) => navigate(`/app/ordens/${id}`)} />
      )}
    </PageContainer>
  )
}

function Quadro({ clienteId, onAbrir }: { clienteId?: number; onAbrir: (id: number) => void }) {
  const [colunas, setColunas] = useState<QuadroCaixaColuna[] | null>(null)
  const [erro, setErro] = useState('')

  useEffect(() => {
    let ativo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setColunas(null)
    setErro('')
    caixasApi
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
    <div className="rounded-2xl bg-background-surface/40 border border-border/60 p-4">
      <div className="flex gap-4 overflow-x-auto pb-2">
        {colunas.map((col) => (
          <div key={col.fase} className="w-72 shrink-0 rounded-2xl bg-background-surface border border-border">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border">
              <span className="inline-flex items-center gap-2 text-sm font-semibold text-slate-100">
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: `#${col.cor}` }} />
                {col.descricao}
              </span>
              <span className="text-xs text-slate-500">{col.total}</span>
            </div>
            <div className="p-3 space-y-2 max-h-[70vh] overflow-y-auto">
              {col.caixas.length === 0 ? (
                <p className="text-xs text-slate-600 px-1">—</p>
              ) : (
                col.caixas.map((cx) => (
                  <button
                    key={cx.id}
                    onClick={() => onAbrir(cx.id)}
                    className="w-full text-left rounded-xl bg-background-elevated border border-border p-3 hover:border-primary/40 transition-colors"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-semibold text-slate-100">CX {cx.id}</span>
                      {col.fase === 5 && (
                        <span className={cn('text-xs px-2 py-0.5 rounded-full',
                          cx.pendentes === 0 ? 'bg-emerald-500/15 text-emerald-400' : 'bg-amber-500/15 text-amber-400')}>
                          {cx.prontos}/{cx.total_os} prontos
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-300 mt-1 truncate flex items-center gap-1.5">
                      <span className="truncate">{cx.cliente_principal_nome ?? cx.cliente_nome ?? '—'}</span>
                      {cx.outros_clientes && cx.outros_clientes > 0 ? (
                        <span className="text-xs text-slate-500 shrink-0">
                          +{cx.outros_clientes} outro{cx.outros_clientes > 1 ? 's' : ''}
                        </span>
                      ) : null}
                    </p>
                    <p className="text-xs text-slate-500">{cx.total_os} aparelho{cx.total_os !== 1 ? 's' : ''}</p>
                  </button>
                ))
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

/** Períodos prontos do filtro de chegada. Devolvem a faixa [de, até] em ISO, ou
 *  `null` quando não há faixa a aplicar (Todos) — o backend trata cada ponta como
 *  opcional, então "sem faixa" é simplesmente não enviar os parâmetros. */
const PERIODOS = [
  { valor: '', label: 'Todo o período' },
  { valor: 'hoje', label: 'Hoje' },
  { valor: '7', label: 'Últimos 7 dias' },
  { valor: '30', label: 'Últimos 30 dias' },
  { valor: 'mes', label: 'Este mês' },
  { valor: 'mes-1', label: 'Mês passado' },
  { valor: 'custom', label: 'Personalizado…' },
] as const

function iso(d: Date): string {
  // Local, não UTC: `toISOString` devolveria o dia anterior à noite no Brasil.
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function faixaDoPeriodo(valor: string): { de?: string; ate?: string } {
  const hoje = new Date()
  switch (valor) {
    case 'hoje':
      return { de: iso(hoje), ate: iso(hoje) }
    case '7':
    case '30': {
      const de = new Date(hoje)
      de.setDate(de.getDate() - (Number(valor) - 1))   // inclui hoje na contagem
      return { de: iso(de), ate: iso(hoje) }
    }
    case 'mes':
      return { de: iso(new Date(hoje.getFullYear(), hoje.getMonth(), 1)), ate: iso(hoje) }
    case 'mes-1': {
      const de = new Date(hoje.getFullYear(), hoje.getMonth() - 1, 1)
      const ate = new Date(hoje.getFullYear(), hoje.getMonth(), 0)   // dia 0 = último do mês anterior
      return { de: iso(de), ate: iso(ate) }
    }
    default:
      return {}
  }
}

function Lista({ clienteId, faseInicial, onAbrir }: { clienteId?: number; faseInicial?: string; onAbrir: (id: number) => void }) {
  const [fase, setFase] = useState(faseInicial ?? '')
  const [tipo, setTipo] = useState('')
  const [periodo, setPeriodo] = useState('')
  const [de, setDe] = useState('')
  const [ate, setAte] = useState('')
  const [termo, setTermo] = useState('')
  const [busca, setBusca] = useState('')
  const [offset, setOffset] = useState(0)
  const [itens, setItens] = useState<OrdemListItem[] | null>(null)
  const [total, setTotal] = useState(0)
  const [erro, setErro] = useState('')

  // Personalizado usa os dois campos de data; os demais derivam do período escolhido.
  const faixa = periodo === 'custom' ? { de: de || undefined, ate: ate || undefined } : faixaDoPeriodo(periodo)

  useEffect(() => {
    let ativo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setItens(null)
    setErro('')
    ordensApi
      .listar({ fase: fase ? Number(fase) : undefined, cliente: clienteId, tipo: tipo || undefined, q: busca || undefined,
                chegadaDe: faixa.de, chegadaAte: faixa.ate, offset, limit: LIMITE })
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
  }, [fase, tipo, busca, clienteId, offset, faixa.de, faixa.ate])

  function onBuscar(e: FormEvent) {
    e.preventDefault()
    setOffset(0)
    setBusca(termo.trim())
  }

  return (
    <div className="space-y-4">
      <SearchBar
        value={termo}
        onChange={setTermo}
        onSubmit={onBuscar}
        placeholder="Nº da OS, etiqueta ou cliente"
        abaixo={
          <>
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
            <div className="w-48">
              <Select id="periodo" label="Chegada" value={periodo}
                onChange={(e) => { setOffset(0); setPeriodo(e.target.value) }}>
                {PERIODOS.map((p) => <option key={p.valor} value={p.valor}>{p.label}</option>)}
              </Select>
            </div>
            {periodo === 'custom' && (
              <>
                <div className="w-40">
                  <Input id="chegada-de" label="De" type="date" value={de}
                    onChange={(e) => { setOffset(0); setDe(e.target.value) }} />
                </div>
                <div className="w-40">
                  <Input id="chegada-ate" label="Até" type="date" value={ate}
                    onChange={(e) => { setOffset(0); setAte(e.target.value) }} />
                </div>
              </>
            )}
          </>
        }
      />

      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}

      {itens === null ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhuma OS encontrada.</p>
      ) : (
        <>
          <Table
            head={<><TH>Caixa</TH><TH>OS</TH><TH>Cliente</TH><TH>Equipamento</TH><TH>Fase</TH><TH>Tipo</TH><TH>Chegada</TH><TH>Situação</TH></>}
            footer={<PaginationOffset offset={offset} limit={LIMITE} total={total} onOffsetChange={setOffset} itemLabel="OS" />}
          >
            {itens.map((o) => (
              <tr key={o.id} className="hover:bg-background-elevated transition-colors cursor-pointer" onClick={() => onAbrir(o.id)}>
                <TD>{o.caixa ? `CX ${o.caixa}` : '—'}</TD>
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
        </>
      )}
    </div>
  )
}
