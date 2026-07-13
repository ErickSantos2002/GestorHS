import { useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { ApiError } from '../../lib/api'
import { redefinirSenha, type UsuarioItem } from './api'

interface Props {
  usuario: UsuarioItem
  onClose: () => void
  onSalvo: () => void
}

export function RedefinirSenhaModal({ usuario, onClose, onSalvo }: Props) {
  const [nova, setNova] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setErro('')
    setEnviando(true)
    try {
      await redefinirSenha(usuario.id, nova)
      onSalvo()
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao redefinir')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={`Redefinir senha — ${usuario.nome ?? usuario.email}`}
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors"
          >
            Cancelar
          </button>
          <button
            type="submit"
            form="form-senha"
            disabled={enviando}
            className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all"
          >
            Salvar
          </button>
        </>
      }
    >
      <form id="form-senha" className="space-y-4" onSubmit={onSubmit}>
        <Input
          id="nova-senha"
          label="Nova senha (mín. 8)"
          type="password"
          value={nova}
          onChange={(e) => setNova(e.target.value)}
          required
          minLength={8}
        />
        {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      </form>
    </Modal>
  )
}
