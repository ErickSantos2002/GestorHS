import { useEffect, useState } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Spinner } from '../../components/ui/Spinner'
import { clientesApi, type Cliente } from '../clientes/api'
import { camposAlterados, type CampoAlterado } from './clienteOverride'

/**
 * Comparativo cadastro x proposta dos campos editados só nesta proposta.
 * Fica sem o lado do cadastro enquanto o cliente não carregou (ou se falhar) —
 * o que a proposta usa continua visível, que é o dado mais importante aqui.
 */
export function TabelaOverride({ campos, carregando }: { campos: CampoAlterado[]; carregando?: boolean }) {
  if (campos.length === 0) {
    return <p className="text-sm text-slate-500">Nenhum dado editado nesta proposta.</p>
  }
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-background-elevated text-left">
            <th className="px-3 py-2 font-medium text-slate-400">Campo</th>
            <th className="px-3 py-2 font-medium text-slate-400">No cadastro do cliente</th>
            <th className="px-3 py-2 font-medium text-slate-400">Nesta proposta</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {campos.map((c) => (
            <tr key={c.campo}>
              <td className="px-3 py-2 font-medium text-slate-300">{c.rotulo}</td>
              <td className="px-3 py-2 text-slate-500">
                {carregando ? '…' : (c.cadastro || <span className="italic text-slate-600">em branco</span>)}
              </td>
              <td className={`px-3 py-2 ${c.mudou ? 'font-semibold text-warning' : 'text-slate-400'}`}>
                {c.proposta}
                {!c.mudou && <span className="ml-2 text-xs font-normal text-slate-500">(igual ao cadastro)</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Modal aberta pelo selo "Dados editados" da listagem. */
export function OverrideDetalheModal({ propostaNumero, clienteId, override, onClose }: {
  propostaNumero: number
  clienteId: number | null
  override: Record<string, unknown> | null
  onClose: () => void
}) {
  const [cliente, setCliente] = useState<Cliente | null>(null)
  const [carregando, setCarregando] = useState(clienteId != null)

  useEffect(() => {
    if (clienteId == null) return
    let vivo = true
    clientesApi.obter(clienteId)
      .then((c) => { if (vivo) setCliente(c) })
      .catch(() => { if (vivo) setCliente(null) })
      .finally(() => { if (vivo) setCarregando(false) })
    return () => { vivo = false }
  }, [clienteId])

  const campos = camposAlterados(override, cliente)

  return (
    <Modal open onClose={onClose} title={`Dados editados — Proposta #${propostaNumero}`} size="3xl">
      <p className="text-sm text-slate-500">
        Estes dados valem só nesta proposta e <strong className="text-slate-400">não alteram o cadastro do cliente</strong>.
        Campos não listados vêm do cadastro normalmente.
      </p>
      {carregando && campos.length === 0 ? (
        <div className="flex justify-center py-8"><Spinner className="w-6 h-6" /></div>
      ) : (
        <TabelaOverride campos={campos} carregando={carregando} />
      )}
    </Modal>
  )
}
