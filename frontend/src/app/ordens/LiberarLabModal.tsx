import { useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Button } from '../../components/ui/Button'
import { ApiError } from '../../lib/api'
import { caixasApi } from '../caixas/api'

export function LiberarLabModal({ osId, onClose, onConcluido }: {
  osId: number
  onClose: () => void
  onConcluido: () => void
}) {
  const [motivo, setMotivo] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function submeter(e: FormEvent) {
    e.preventDefault()
    setEnviando(true)
    setErro('')
    try {
      await caixasApi.desfechoLab(osId, { desfecho: 'liberado', obs: motivo.trim() || null })
      onConcluido()
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao liberar do laboratório')
      setEnviando(false)
    }
  }

  const inputClass = 'w-full px-3 py-2 text-sm rounded-lg border border-border bg-background-elevated text-slate-300 focus:outline-none focus:ring-2 focus:ring-primary/50'

  return (
    <Modal
      open
      onClose={onClose}
      title={`Liberar do laboratório — OS #${osId}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button variant="primary" type="submit" form="form-liberar-lab" disabled={enviando}>
            {enviando ? 'Salvando…' : 'Liberar do Laboratório'}
          </Button>
        </>
      }
    >
      <form id="form-liberar-lab" className="space-y-4" onSubmit={submeter}>
        <p className="text-sm text-slate-400">
          A OS sai do laboratório sem certificado de calibração/manutenção associado.
        </p>
        <div>
          <label htmlFor="motivo-liberar-lab" className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">Motivo (opcional)</label>
          <textarea
            id="motivo-liberar-lab"
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
            rows={3}
            className={inputClass}
            placeholder="ex.: modelo de certificado de manutencao ainda nao cadastrado"
          />
        </div>
        {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      </form>
    </Modal>
  )
}
