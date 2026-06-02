import { useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { ApiError } from '../../lib/api'
import { criarUsuario, atualizarUsuario, type UsuarioItem, type Funcao } from './api'

interface Props {
  funcoes: Funcao[]
  usuario: UsuarioItem | null
  onClose: () => void
  onSalvo: () => void
}

export function UsuarioFormModal({ funcoes, usuario, onClose, onSalvo }: Props) {
  const editando = usuario !== null
  const [nome, setNome] = useState(usuario?.nome ?? '')
  const [login, setLogin] = useState(usuario?.login ?? '')
  const [email, setEmail] = useState(usuario?.email ?? '')
  const [senha, setSenha] = useState('')
  const [funcaoId, setFuncaoId] = useState(usuario?.funcao_id ? String(usuario.funcao_id) : '')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setErro('')
    setEnviando(true)
    try {
      const funcao_id = funcaoId ? Number(funcaoId) : null
      if (usuario) {
        await atualizarUsuario(usuario.id, { nome, email, funcao_id, login })
      } else {
        await criarUsuario({ nome, login, email, senha, funcao_id })
      }
      onSalvo()
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao salvar')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={editando ? 'Editar usuário' : 'Novo usuário'}
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
            form="form-usuario"
            disabled={enviando}
            className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all"
          >
            Salvar
          </button>
        </>
      }
    >
      <form id="form-usuario" className="space-y-4" onSubmit={onSubmit}>
        <Input id="nome" label="Nome" value={nome} onChange={(e) => setNome(e.target.value)} />
        <Input id="login" label="Login" value={login} onChange={(e) => setLogin(e.target.value)} required maxLength={20} />
        <Input id="email" label="E-mail" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        {!editando && (
          <Input
            id="senha"
            label="Senha (mín. 8)"
            type="password"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            required
            minLength={8}
          />
        )}
        <Select id="funcao" label="Função" value={funcaoId} onChange={(e) => setFuncaoId(e.target.value)}>
          <option value="">— sem função —</option>
          {funcoes.map((f) => (
            <option key={f.id} value={f.id}>
              {f.descricao}
            </option>
          ))}
        </Select>
        {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      </form>
    </Modal>
  )
}
