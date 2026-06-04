import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { usePortalAuth } from './PortalAuthContext'
import { ApiError } from '../lib/api'
import { Input } from '../components/ui/Input'
import { Spinner } from '../components/ui/Spinner'
import { IconAlertCircle } from '../components/ui/icons'

export function PortalLoginPage() {
  const { login, cliente, loading } = usePortalAuth()
  const navigate = useNavigate()
  const [documento, setDocumento] = useState('')
  const [usuario, setUsuario] = useState('')
  const [senha, setSenha] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  if (loading) {
    return <div className="flex h-screen items-center justify-center bg-background"><Spinner className="w-8 h-8" /></div>
  }
  if (cliente) return <Navigate to="/portal" replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setErro('')
    setEnviando(true)
    try {
      await login(documento, usuario, senha)
      navigate('/portal', { replace: true })
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) setErro('Conta bloqueada — contate a Health Safety.')
      else if (err instanceof ApiError && err.status === 401) setErro('Credenciais inválidas.')
      else setErro('Falha ao entrar. Tente novamente.')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-primary/15 flex items-center justify-center mb-3 shadow-sm">
            <span className="text-xl font-extrabold text-primary">G</span>
          </div>
          <h1 className="text-2xl font-extrabold text-slate-100 tracking-tight">Portal do Cliente</h1>
          <p className="text-sm text-slate-500 mt-1">Health Safety</p>
        </div>
        <div className="rounded-2xl bg-background-surface border border-border shadow-sm p-6">
          <form className="space-y-4" onSubmit={onSubmit}>
            <Input id="documento" label="CNPJ ou CPF" value={documento} onChange={(e) => setDocumento(e.target.value)} autoFocus />
            <Input id="login" label="Login" value={usuario} onChange={(e) => setUsuario(e.target.value)} autoComplete="username" />
            <Input id="senha" label="Senha" type="password" value={senha} onChange={(e) => setSenha(e.target.value)} autoComplete="current-password" />
            {erro && (
              <div className="flex items-center gap-2 rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">
                <IconAlertCircle className="w-4 h-4 shrink-0" />
                {erro}
              </div>
            )}
            <button type="submit" disabled={enviando} className="w-full py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2">
              {enviando && <Spinner className="w-4 h-4 text-white" />}
              Entrar
            </button>
          </form>
        </div>
        <p className="text-center text-xs text-slate-400 mt-6">GestorHS · Health Safety</p>
      </div>
    </div>
  )
}
