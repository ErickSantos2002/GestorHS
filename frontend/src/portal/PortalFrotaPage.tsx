import { useEffect, useState, type FormEvent } from 'react'
import { Table, TH, TD } from '../components/ui/Table'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { Spinner } from '../components/ui/Spinner'
import { Input } from '../components/ui/Input'
import { Select } from '../components/ui/Select'
import { ApiError } from '../lib/api'
import { portalApi, STATUS_CALIB, formatData, type PortalFrotaItem } from './api'

const LIMITE = 25

export function PortalFrotaPage() {
  const [status, setStatus] = useState('')
  const [termo, setTermo] = useState('')
  const [busca, setBusca] = useState('')
  const [offset, setOffset] = useState(0)
  const [itens, setItens] = useState<PortalFrotaItem[] | null>(null)
  const [total, setTotal] = useState(0)
  const [erro, setErro] = useState('')
  const [aviso, setAviso] = useState('')

  useEffect(() => {
    let ativo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setItens(null)
    setErro('')
    portalApi.minhaFrota({ status: status || undefined, q: busca || undefined, offset, limit: LIMITE })
      .then((p) => { if (!ativo) return; setItens(p.items); setTotal(p.total) })
      .catch((e) => { if (!ativo) return; setErro(e instanceof ApiError ? e.message : 'Falha ao carregar'); setItens([]) })
    return () => { ativo = false }
  }, [status, busca, offset])

  function onBuscar(e: FormEvent) { e.preventDefault(); setOffset(0); setBusca(termo.trim()) }

  async function solicitar(item: PortalFrotaItem) {
    if (!window.confirm('Solicitar recalibração deste aparelho?')) return
    setAviso(''); setErro('')
    try {
      await portalApi.solicitar({ equipamento_cliente: item.id })
      setAviso(`Solicitação enviada para ${item.equipamento_descricao ?? 'o aparelho'}.`)
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao solicitar')
    }
  }

  const inicio = total === 0 ? 0 : offset + 1
  const fim = Math.min(offset + LIMITE, total)

  return (
    <div className="px-4 md:px-6 py-6 space-y-6">
      <h1 className="text-2xl font-extrabold text-slate-100">Minha frota</h1>
      <div className="flex flex-wrap gap-2 items-end">
        <div className="w-48">
          <Select id="status" label="Status" value={status} onChange={(e) => { setOffset(0); setStatus(e.target.value) }}>
            <option value="">Todos</option>
            <option value="em_dia">Em dia</option>
            <option value="vencendo">Vencendo</option>
            <option value="vencido">Vencido</option>
            <option value="sem_data">Sem data</option>
          </Select>
        </div>
        <form onSubmit={onBuscar} className="flex gap-2 items-end flex-1 min-w-60">
          <div className="flex-1"><Input id="busca" label="Busca" placeholder="Série ou patrimônio" value={termo} onChange={(e) => setTermo(e.target.value)} /></div>
          <Button type="submit" variant="secondary">Buscar</Button>
        </form>
      </div>
      {aviso && <div className="rounded-lg bg-primary/10 border border-primary/20 px-3 py-2.5 text-sm text-primary">{aviso}</div>}
      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      {itens === null ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum aparelho encontrado.</p>
      ) : (
        <>
          <Table head={<><TH>Aparelho</TH><TH>Série / Patrimônio</TH><TH>Próx. calibração</TH><TH>Status</TH><TH>Ações</TH></>}>
            {itens.map((e) => {
              const s = STATUS_CALIB[e.status_calibracao] ?? STATUS_CALIB.sem_data
              return (
                <tr key={e.id} className="hover:bg-background-elevated transition-colors">
                  <TD>{e.equipamento_descricao ?? '—'}</TD>
                  <TD>{e.serie || e.patrimonio || '—'}</TD>
                  <TD>{formatData(e.prox_calibragem)}</TD>
                  <TD><Badge tone={s.tone}>{s.label}</Badge></TD>
                  <TD><button onClick={() => solicitar(e)} className="text-xs text-primary hover:underline">Solicitar recalibração</button></TD>
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
    </div>
  )
}
