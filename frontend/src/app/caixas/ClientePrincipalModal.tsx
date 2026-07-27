import { useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Select } from '../../components/ui/Select'
import { Button } from '../../components/ui/Button'

export function ClientePrincipalModal({ clientes, onConfirmar, onClose }: {
  clientes: { id: number; nome: string }[]
  onConfirmar: (clienteId: number) => void | Promise<void>
  onClose: () => void
}) {
  const [clienteId, setClienteId] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function submeter(e: FormEvent) {
    e.preventDefault()
    if (!clienteId) return
    setEnviando(true)
    try {
      await onConfirmar(Number(clienteId))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Cliente principal"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button type="submit" form="form-cliente-principal" disabled={!clienteId || enviando}>
            {enviando ? 'Avançando…' : 'Confirmar'}
          </Button>
        </>
      }
    >
      <form id="form-cliente-principal" className="space-y-4" onSubmit={submeter}>
        <Select
          id="cliente-principal"
          label="Cliente"
          value={clienteId}
          onChange={(e) => setClienteId(e.target.value)}
          required
        >
          <option value="">Selecione…</option>
          {clientes.map((c) => (
            <option key={c.id} value={c.id}>{c.nome}</option>
          ))}
        </Select>
      </form>
    </Modal>
  )
}
