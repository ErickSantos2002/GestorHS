import { useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { Button } from '../../components/ui/Button'

export function FecharOrdensModal({ quantidade, onClose, onConfirmar }: {
  quantidade: number
  onClose: () => void
  onConfirmar: (cod_retorno: string, obs: string | null) => Promise<void>
}) {
  const [cod, setCod] = useState('')
  const [obs, setObs] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function submeter(e: FormEvent) {
    e.preventDefault()
    if (!cod.trim()) { setErro('Código de retorno é obrigatório.'); return }
    setEnviando(true); setErro('')
    try {
      await onConfirmar(cod.trim(), obs.trim() || null)
    } catch (err) {
      setErro(err instanceof Error ? err.message : 'Falha ao fechar')
      setEnviando(false)
    }
  }

  const inputClass = 'w-full px-3 py-2 text-sm rounded-lg border border-border bg-background-elevated text-slate-300 focus:outline-none focus:ring-2 focus:ring-primary/50'

  return (
    <Modal
      open
      onClose={onClose}
      title={`Fechar ${quantidade} OS`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button type="submit" form="form-fechar-ordens" disabled={enviando}>
            {enviando ? 'Fechando…' : 'Confirmar'}
          </Button>
        </>
      }
    >
      <form id="form-fechar-ordens" className="space-y-4" onSubmit={submeter}>
        <p className="text-sm text-slate-400">
          O mesmo código de retorno será aplicado às {quantidade} OS selecionadas.
        </p>
        <Input id="cod-retorno" label="Código de retorno" value={cod} onChange={(e) => setCod(e.target.value)} required />
        <div>
          <label htmlFor="obs-fechar" className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">Observação</label>
          <textarea id="obs-fechar" value={obs} onChange={(e) => setObs(e.target.value)} rows={2} className={inputClass} />
        </div>
        {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      </form>
    </Modal>
  )
}
