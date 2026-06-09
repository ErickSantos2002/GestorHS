import { useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { ApiError } from '../../lib/api'
import { ordensApi, type OrdemDetalhe, type AvancarPayload } from './api'

function maisUmAno(): string {
  const d = new Date()
  d.setFullYear(d.getFullYear() + 1)
  return d.toISOString().slice(0, 10)
}

export function AvancarModal({ os, rotulo, pedeCodRetorno, pedeProxCalibragem, onClose, onConcluido }: {
  os: OrdemDetalhe
  rotulo: string
  pedeCodRetorno?: boolean
  pedeProxCalibragem?: boolean
  onClose: () => void
  onConcluido: (os: OrdemDetalhe) => void
}) {
  const [obs, setObs] = useState('')
  const [codRetorno, setCodRetorno] = useState('')
  const [prox, setProx] = useState(pedeProxCalibragem ? maisUmAno() : '')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function submeter(e: FormEvent) {
    e.preventDefault()
    setErro('')
    if (pedeCodRetorno && !codRetorno.trim()) {
      setErro('Código de retorno é obrigatório.')
      return
    }
    const payload: AvancarPayload = {
      obs: obs.trim() || null,
      cod_retorno: pedeCodRetorno ? codRetorno.trim() : null,
    }
    if (pedeProxCalibragem) payload.prox_calibragem = prox || null
    setEnviando(true)
    try {
      const atualizada = await ordensApi.avancar(os.id, payload)
      onConcluido(atualizada)
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao avançar')
    } finally {
      setEnviando(false)
    }
  }

  const inputClass = 'w-full px-3 py-2 text-sm rounded-lg border border-border bg-background-elevated text-slate-300 focus:outline-none focus:ring-2 focus:ring-primary/50'

  return (
    <Modal
      open
      onClose={onClose}
      title={rotulo}
      footer={
        <>
          <button type="button" onClick={onClose} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">Cancelar</button>
          <button type="submit" form="form-avancar" disabled={enviando} className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all">Confirmar</button>
        </>
      }
    >
      <form id="form-avancar" className="space-y-4" onSubmit={submeter}>
        {pedeCodRetorno && (
          <Input id="cod-retorno" label="Código de retorno" value={codRetorno} onChange={(e) => setCodRetorno(e.target.value)} required />
        )}
        {pedeProxCalibragem && (
          <Input id="prox" label="Próxima calibração" type="date" value={prox} onChange={(e) => setProx(e.target.value)} />
        )}
        <div>
          <label htmlFor="obs" className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">Observação</label>
          <textarea id="obs" value={obs} onChange={(e) => setObs(e.target.value)} rows={3} className={inputClass} />
        </div>
        {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      </form>
    </Modal>
  )
}
