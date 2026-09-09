import { useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Button } from '../../components/ui/Button'
import { ApiError } from '../../lib/api'
import { ordensApi } from './api'

/** Cancelar UMA OS (Administrador). A OS sai das contas da caixa e do card do
 * TaskHS, mas continua vinculada — o motivo vai para o log. */
export function CancelarOSModal({ osId, onClose, onConcluido }: {
  osId: number
  onClose: () => void
  onConcluido: () => void
}) {
  const [motivo, setMotivo] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function submeter(e: FormEvent) {
    e.preventDefault()
    if (!motivo.trim()) {
      setErro('Motivo é obrigatório.')
      return
    }
    setEnviando(true)
    setErro('')
    try {
      await ordensApi.cancelar(osId, { motivo: motivo.trim() })
      onConcluido()
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao cancelar a OS')
      setEnviando(false)
    }
  }

  const inputClass = 'w-full px-3 py-2 text-sm rounded-lg border border-border bg-background-elevated text-slate-300 focus:outline-none focus:ring-2 focus:ring-primary/50'

  return (
    <Modal
      open
      onClose={onClose}
      title={`Cancelar OS #${osId}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Voltar</Button>
          <Button variant="danger" type="submit" form="form-cancelar-os" disabled={enviando}>
            {enviando ? 'Cancelando…' : 'Cancelar a OS'}
          </Button>
        </>
      }
    >
      <form id="form-cancelar-os" className="space-y-4" onSubmit={submeter}>
        <p className="text-sm text-slate-400">
          A OS sai das contas da caixa — a caixa passa a avançar sem ela e o aparelho
          some do card do TaskHS. Não desfaz certificado já emitido nem calibração já
          espelhada na frota.
        </p>
        <div>
          <label htmlFor="motivo-cancelar-os" className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">Motivo</label>
          <textarea
            id="motivo-cancelar-os"
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
            rows={3}
            className={inputClass}
            placeholder="ex.: OS aberta em duplicidade"
          />
        </div>
        {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      </form>
    </Modal>
  )
}
