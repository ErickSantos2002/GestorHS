import { useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { Button } from '../../components/ui/Button'
import { ApiError } from '../../lib/api'
import { caixasApi } from './api'

export function AvancarCaixaModal({ id, rotulo, onClose, onConcluido }: {
  id: number
  rotulo: string
  onClose: () => void
  onConcluido: () => void
}) {
  const [codRetorno, setCodRetorno] = useState('')
  const [obs, setObs] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function submeter(e: FormEvent) {
    e.preventDefault()
    if (!codRetorno.trim()) {
      setErro('Código de retorno é obrigatório.')
      return
    }
    setEnviando(true)
    setErro('')
    try {
      await caixasApi.avancar(id, { cod_retorno: codRetorno.trim(), obs: obs.trim() || null })
      onConcluido()
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao avançar')
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
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button type="submit" form="form-avancar-caixa" disabled={enviando}>
            {enviando ? 'Avançando…' : 'Confirmar'}
          </Button>
        </>
      }
    >
      <form id="form-avancar-caixa" className="space-y-4" onSubmit={submeter}>
        <Input
          id="cod-retorno-caixa"
          label="Código de retorno"
          value={codRetorno}
          onChange={(e) => setCodRetorno(e.target.value)}
          required
        />
        <div>
          <label htmlFor="obs-avancar-caixa" className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">Observação</label>
          <textarea id="obs-avancar-caixa" value={obs} onChange={(e) => setObs(e.target.value)} rows={3} className={inputClass} />
        </div>
        {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      </form>
    </Modal>
  )
}
