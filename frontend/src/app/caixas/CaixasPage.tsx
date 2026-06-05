import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Spinner } from '../../components/ui/Spinner'
import { Modal } from '../../components/ui/Modal'
import { useAuth } from '../../auth/AuthContext'
import { podeAbrirOS } from '../../auth/roles'
import { ApiError } from '../../lib/api'
import { caixasApi, formatData, STATUS_CAIXA, type CaixaListItem } from './api'

const PAGE = 25

export function CaixasPage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const podeEscrever = podeAbrirOS(user)
  const [status, setStatus] = useState('')
  const [q, setQ] = useState('')
  const [busca, setBusca] = useState('')
  const [offset, setOffset] = useState(0)
  const [dados, setDados] = useState<{ items: CaixaListItem[]; total: number } | null>(null)
  const [erro, setErro] = useState('')
  const [novaAberta, setNovaAberta] = useState(false)
  const [novaObs, setNovaObs] = useState('')
  const [salvando, setSalvando] = useState(false)
  const [erroModal, setErroModal] = useState('')

  useEffect(() => {
    let vivo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDados(null)
    setErro('')
    caixasApi
      .listar({ status: status || undefined, q: busca || undefined, offset, limit: PAGE })
      .then((r) => { if (vivo) setDados(r) })
      .catch((e) => { if (vivo) { setErro(e instanceof ApiError ? e.message : 'Falha ao carregar'); setDados({ items: [], total: 0 }) } })
    return () => { vivo = false }
  }, [status, busca, offset])

  async function criar(e: FormEvent) {
    e.preventDefault()
    setSalvando(true)
    setErroModal('')
    try {
      const c = await caixasApi.criar({ obs: novaObs.trim() || null })
      navigate(`/app/caixas/${c.id}`)
    } catch (err) {
      setErroModal(err instanceof ApiError ? err.message : 'Falha ao criar caixa')
    } finally {
      setSalvando(false)
    }
  }

  function onBuscar(e: FormEvent) {
    e.preventDefault()
    setOffset(0)
    setBusca(q.trim())
  }

  const inicio = dados && dados.total > 0 ? offset + 1 : 0
  const fim = dados ? Math.min(offset + PAGE, dados.total) : 0

  return (
    <div className="px-4 md:px-6 py-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100">Caixas</h1>
          <p className="text-sm text-slate-500 mt-0.5">Agrupamento físico de ordens de serviço.</p>
        </div>
        {podeEscrever && (
          <Button
            onClick={() => { setNovaObs(''); setErroModal(''); setNovaAberta(true) }}
          >
            Nova caixa
          </Button>
        )}
      </div>

      <div className="flex flex-wrap gap-2 items-end">
        <div>
          <label htmlFor="filtro-status" className="block text-xs font-semibold text-slate-500 mb-1 uppercase tracking-wide">Status</label>
          <select
            id="filtro-status"
            value={status}
            onChange={(e) => { setOffset(0); setStatus(e.target.value) }}
            className="px-3 py-2 text-sm rounded-lg border border-border bg-background-elevated text-slate-300 focus:outline-none focus:ring-2 focus:ring-primary/50"
          >
            <option value="">Todos os status</option>
            <option value="P">Pendente</option>
            <option value="A">Aberta</option>
            <option value="F">Finalizada</option>
          </select>
        </div>
        <form onSubmit={onBuscar} className="flex gap-2 items-end">
          <div>
            <label htmlFor="filtro-busca" className="block text-xs font-semibold text-slate-500 mb-1 uppercase tracking-wide">Busca</label>
            <input
              id="filtro-busca"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Nº ou descrição"
              className="px-3 py-2 text-sm rounded-lg border border-border bg-background-elevated text-slate-300 focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
          </div>
          <Button type="submit" variant="secondary">Buscar</Button>
        </form>
      </div>

      {erro && (
        <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>
      )}

      {dados === null ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : dados.items.length === 0 && !erro ? (
        <p className="text-sm text-slate-500">Nenhuma caixa.</p>
      ) : dados.items.length > 0 ? (
        <>
          <Table head={
            <>
              <TH>Caixa</TH>
              <TH>Data</TH>
              <TH>Status</TH>
              <TH>OS</TH>
              <TH>Clientes</TH>
              <TH>Descrição</TH>
            </>
          }>
            {dados.items.map((c) => (
              <tr
                key={c.id}
                className="hover:bg-background-elevated transition-colors cursor-pointer"
                onClick={() => navigate(`/app/caixas/${c.id}`)}
              >
                <TD><span className="font-semibold text-slate-200">#{c.id}</span></TD>
                <TD>{formatData(c.data)}</TD>
                <TD>
                  <Badge tone={STATUS_CAIXA[c.status]?.tone}>
                    {STATUS_CAIXA[c.status]?.label ?? c.status}
                  </Badge>
                </TD>
                <TD>{c.total_os}</TD>
                <TD>
                  {c.clientes.length === 0
                    ? '—'
                    : c.clientes.length === 1
                      ? c.clientes[0]
                      : `${c.clientes.length} clientes`}
                </TD>
                <TD>
                  <span className="truncate max-w-xs block">{c.obs ?? '—'}</span>
                </TD>
              </tr>
            ))}
          </Table>

          <div className="flex items-center justify-between text-sm text-slate-400">
            <span>{inicio}–{fim} de {dados.total}</span>
            <div className="flex gap-2">
              <Button variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>Anterior</Button>
              <Button variant="secondary" disabled={fim >= dados.total} onClick={() => setOffset(offset + PAGE)}>Próxima</Button>
            </div>
          </div>
        </>
      ) : null}

      {novaAberta && (
        <Modal
          open
          onClose={() => setNovaAberta(false)}
          title="Nova caixa"
          footer={
            <>
              <button
                type="button"
                onClick={() => setNovaAberta(false)}
                className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated"
              >
                Cancelar
              </button>
              <button
                type="submit"
                form="form-nova-caixa"
                disabled={salvando}
                className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50"
              >
                Criar
              </button>
            </>
          }
        >
          <form id="form-nova-caixa" onSubmit={criar} className="space-y-4">
            <div>
              <label htmlFor="obs" className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">
                Descrição / origem (opcional)
              </label>
              <input
                id="obs"
                value={novaObs}
                onChange={(e) => setNovaObs(e.target.value)}
                placeholder="Ex.: Lote Cuiabá"
                className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-background-elevated text-slate-300 focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
            </div>
            {erroModal && <p className="text-sm text-danger">{erroModal}</p>}
          </form>
        </Modal>
      )}
    </div>
  )
}
