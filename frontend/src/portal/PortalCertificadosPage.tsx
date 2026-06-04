import { useEffect, useState } from 'react'
import { Table, TH, TD } from '../components/ui/Table'
import { Button } from '../components/ui/Button'
import { Spinner } from '../components/ui/Spinner'
import { ApiError } from '../lib/api'
import { portalApi, formatData, type PortalCertItem } from './api'

const LIMITE = 25

export function PortalCertificadosPage() {
  const [offset, setOffset] = useState(0)
  const [itens, setItens] = useState<PortalCertItem[] | null>(null)
  const [total, setTotal] = useState(0)
  const [erro, setErro] = useState('')

  useEffect(() => {
    let ativo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setItens(null)
    setErro('')
    portalApi.certificados({ offset, limit: LIMITE })
      .then((p) => { if (!ativo) return; setItens(p.items); setTotal(p.total) })
      .catch((e) => { if (!ativo) return; setErro(e instanceof ApiError ? e.message : 'Falha ao carregar'); setItens([]) })
    return () => { ativo = false }
  }, [offset])

  const inicio = total === 0 ? 0 : offset + 1
  const fim = Math.min(offset + LIMITE, total)

  return (
    <div className="px-4 md:px-6 py-6 space-y-6">
      <h1 className="text-2xl font-extrabold text-slate-100">Certificados</h1>
      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      {itens === null ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum certificado disponível.</p>
      ) : (
        <>
          <Table head={<><TH>Aparelho</TH><TH>Série</TH><TH>Certificado</TH><TH>Última calibração</TH><TH>Próxima calibração</TH><TH>PDF</TH></>}>
            {itens.map((c) => (
              <tr key={c.equipamento_cliente} className="hover:bg-background-elevated transition-colors">
                <TD>{c.equipamento_descricao ?? '—'}</TD>
                <TD>{c.serie ?? '—'}</TD>
                <TD>{c.calib_cert ?? '—'}</TD>
                <TD>{formatData(c.ult_calibragem)}</TD>
                <TD>{formatData(c.prox_calibragem)}</TD>
                <TD>{c.os != null
                  ? <button type="button" className="text-primary hover:underline text-sm" onClick={() => { portalApi.baixarCertificado(c.os!).catch(() => setErro('Certificado indisponível')) }}>Baixar</button>
                  : '—'}</TD>
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
