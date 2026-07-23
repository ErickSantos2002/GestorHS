import { useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Button } from '../../components/ui/Button'
import { ApiError } from '../../lib/api'
import { caixasApi } from './api'

export function SemConsertoModal({ osId, onClose, onConcluido }: {
  osId: number
  onClose: () => void
  onConcluido: () => void
}) {
  const [obs, setObs] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function submeter(e: FormEvent) {
    e.preventDefault()
    if (!obs.trim()) {
      setErro('Justificativa é obrigatória.')
      return
    }
    setEnviando(true)
    setErro('')
    try {
      await caixasApi.desfechoLab(osId, { desfecho: 'sem_conserto', obs: obs.trim() })
      onConcluido()
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao marcar sem conserto')
      setEnviando(false)
    }
  }

  const inputClass = 'w-full px-3 py-2 text-sm rounded-lg border border-border bg-background-elevated text-slate-300 focus:outline-none focus:ring-2 focus:ring-primary/50'

  return (
    <Modal
      open
      onClose={onClose}
      title={`Sem conserto — OS #${osId}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button variant="danger" type="submit" form="form-sem-conserto" disabled={enviando}>
            {enviando ? 'Salvando…' : 'Confirmar'}
          </Button>
        </>
      }
    >
      <form id="form-sem-conserto" className="space-y-4" onSubmit={submeter}>
        <div>
          <label htmlFor="obs-sem-conserto" className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">Justificativa</label>
          <textarea id="obs-sem-conserto" value={obs} onChange={(e) => setObs(e.target.value)} rows={3} className={inputClass} required />
        </div>
        {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      </form>
    </Modal>
  )
}
