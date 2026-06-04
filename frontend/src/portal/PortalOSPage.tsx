import { useEffect, useState } from 'react'
import { Table, TH, TD } from '../components/ui/Table'
import { Button } from '../components/ui/Button'
import { Spinner } from '../components/ui/Spinner'
import { ApiError } from '../lib/api'
import { portalApi, TIPO_LABEL, formatData, type PortalOSItem } from './api'

const LIMITE = 25

export function PortalOSPage() {
  const [emAndamento, setEmAndamento] = useState(false)
  const [offset, setOffset] = useState(0)
  const [itens, setItens] = useState<PortalOSItem[] | null>(null)
  const [total, setTotal] = useState(0)
  const [erro, setErro] = useState('')

  useEffect(() => {
    let ativo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setItens(null)
    setErro('')
    portalApi.minhasOs({ em_andamento: emAndamento, offset, limit: LIMITE })
      .then((p) => { if (!ativo) return; setItens(p.items); setTotal(p.total) })
      .catch((e) => { if (!ativo) return; setErro(e instanceof ApiError ? e.message : 'Falha ao carregar'); setItens([]) })
    return () => { ativo = false }
  }, [emAndamento, offset])

  const inicio = total === 0 ? 0 : offset + 1
  const fim = Math.min(offset + LIMITE, total)

  return (
    <div className="px-4 md:px-6 py-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-2xl font-extrabold text-slate-100">Minhas OS</h1>
        <label className="flex items-center gap-2 text-sm text-slate-300">
          <input type="checkbox" checked={emAndamento} onChange={(e) => { setOffset(0); setEmAndamento(e.target.checked) }} className="accent-primary" />
          Em andamento
        </label>
      </div>
      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      {itens === null ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhuma OS encontrada.</p>
      ) : (
        <>
          <Table head={<><TH>OS</TH><TH>Aparelho</TH><TH>Fase</TH><TH>Tipo</TH><TH>Chegada</TH></>}>
            {itens.map((o) => (
              <tr key={o.id} className="hover:bg-background-elevated transition-colors">
                <TD>#{o.id}</TD>
                <TD>{o.equipamento_descricao ?? '—'}{o.equipamento_serie ? ` · ${o.equipamento_serie}` : ''}</TD>
                <TD>{o.fase_descricao ? (
                  <span className="inline-flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full" style={{ background: `#${o.fase_cor}` }} />
                    {o.fase_descricao}
                  </span>
                ) : '—'}</TD>
                <TD>{o.tipo_servico && TIPO_LABEL[o.tipo_servico] ? TIPO_LABEL[o.tipo_servico] : '—'}</TD>
                <TD>{formatData(o.data_chegada)}</TD>
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
