import { useEffect, useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { ApiError } from '../../lib/api'
import { clientesApi, type ClienteListItem } from '../clientes/api'
import { equipamentosClienteApi } from './api'

export function TransferirModal({ equipamentoClienteId, donoAtual, onClose, onTransferida }: {
  equipamentoClienteId: number
  donoAtual: number
  onClose: () => void
  onTransferida: () => void
}) {
  const [q, setQ] = useState('')
  const [resultados, setResultados] = useState<ClienteListItem[]>([])
  const [destino, setDestino] = useState<ClienteListItem | null>(null)
  const [obs, setObs] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    let vivo = true
    if (destino || !q.trim()) {
      Promise.resolve().then(() => { if (vivo) setResultados([]) })
    } else {
      clientesApi.listar({ q: q.trim(), limit: 8 })
        .then((r) => { if (vivo) setResultados(r.items) })
        .catch(() => { if (vivo) setResultados([]) })
    }
    return () => { vivo = false }
  }, [q, destino])

  async function submeter(e: FormEvent) {
    e.preventDefault()
    if (!destino) return
    setErro(''); setEnviando(true)
    try {
      await equipamentosClienteApi.transferir(equipamentoClienteId, { cliente: destino.id, obs: obs.trim() || null })
      onTransferida()
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao transferir')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Transferir aparelho"
      size="lg"
      footer={
        <>
          <Button variant="secondary" type="button" onClick={onClose}>Cancelar</Button>
          <Button type="submit" form="form-transferir" disabled={enviando || destino == null || destino.id === donoAtual}>
            {enviando ? 'Transferindo…' : 'Transferir'}
          </Button>
        </>
      }
    >
      <form id="form-transferir" className="space-y-4" onSubmit={submeter}>
        <p className="text-sm text-slate-400">Escolha a empresa de destino. O histórico de OS antigas continua com a empresa atual.</p>

        {destino ? (
          <div className="flex items-center justify-between rounded-lg bg-primary/10 border border-primary/30 px-3 py-2">
            <span className="text-sm font-semibold text-primary">{destino.nome ?? `#${destino.id}`}</span>
            <button type="button" className="text-xs text-slate-400 hover:text-slate-200" onClick={() => setDestino(null)}>trocar</button>
          </div>
        ) : (
          <div>
            <Input id="busca-empresa" label="Empresa de destino" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar por nome" />
            {resultados.length > 0 && (
              <ul className="mt-1 rounded-lg border border-border divide-y divide-border overflow-hidden">
                {resultados.map((c) => (
                  <li key={c.id}>
                    <button type="button" onClick={() => { setDestino(c); setQ('') }}
                      className="w-full text-left px-3 py-2 text-sm hover:bg-background-elevated">
                      {c.nome ?? `#${c.id}`}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {destino && destino.id === donoAtual && (
          <p className="text-sm text-warning">Esta empresa já é a dona atual do aparelho.</p>
        )}

        <Input id="obs-transferencia" label="Observação (opcional)" value={obs} onChange={(e) => setObs(e.target.value)} placeholder="Motivo da transferência" />

        {erro && <p className="text-sm text-danger">{erro}</p>}
      </form>
    </Modal>
  )
}
