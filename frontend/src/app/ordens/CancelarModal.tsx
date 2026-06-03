import { useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { ApiError } from '../../lib/api'
import { ordensApi, type OrdemDetalhe } from './api'

export function CancelarModal({ os, onClose, onConcluido }: {
  os: OrdemDetalhe
  onClose: () => void
  onConcluido: (os: OrdemDetalhe) => void
}) {
  const [motivo, setMotivo] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function submeter(e: FormEvent) {
    e.preventDefault()
    setErro('')
    if (!motivo.trim()) {
      setErro('Motivo é obrigatório.')
      return
    }
    setEnviando(true)
    try {
      const atualizada = await ordensApi.cancelar(os.id, { motivo: motivo.trim() })
      onConcluido(atualizada)
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao cancelar')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={`Cancelar OS #${os.id}`}
      footer={
        <>
          <button type="button" onClick={onClose} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">Voltar</button>
          <button type="submit" form="form-cancelar" disabled={enviando} className="flex-1 py-2.5 rounded-lg bg-danger text-white text-sm font-semibold hover:bg-danger-600 disabled:opacity-50 transition-all">Cancelar OS</button>
        </>
      }
    >
      <form id="form-cancelar" className="space-y-4" onSubmit={submeter}>
        <div>
          <label htmlFor="motivo" className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">Motivo</label>
          <textarea id="motivo" value={motivo} onChange={(e) => setMotivo(e.target.value)} rows={3} className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-background-elevated text-slate-300 focus:outline-none focus:ring-2 focus:ring-primary/50" />
        </div>
        {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      </form>
    </Modal>
  )
}
