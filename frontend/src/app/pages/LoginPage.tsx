import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { ApiError } from '../../lib/api'
import { Input } from '../../components/ui/Input'
import { Spinner } from '../../components/ui/Spinner'
import { IconAlertCircle } from '../../components/ui/icons'

export function LoginPage() {
  const { login, definirSenha, user, loading } = useAuth()
  const navigate = useNavigate()
  const [usuario, setUsuario] = useState('')
  const [senha, setSenha] = useState('')
  const [etapa, setEtapa] = useState<'login' | 'definir'>('login')
  const [novaSenha, setNovaSenha] = useState('')
  const [confirma, setConfirma] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  if (loading) {
    return <div className="flex h-screen items-center justify-center bg-background"><Spinner className="w-8 h-8" /></div>
  }
  if (user) return <Navigate to="/app" replace />

  async function onLogin(e: FormEvent) {
    e.preventDefault()
    setErro(''); setEnviando(true)
    try {
      const r = await login(usuario, senha)
      if (r.precisa_redefinir) { setNovaSenha(''); setConfirma(''); setEtapa('definir') }
      else navigate('/app', { replace: true })
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao entrar. Tente novamente.')
    } finally { setEnviando(false) }
  }

  async function onDefinir(e: FormEvent) {
    e.preventDefault()
    setErro('')
    if (novaSenha.length < 8) { setErro('A nova senha deve ter ao menos 8 caracteres.'); return }
    if (novaSenha !== confirma) { setErro('As senhas não conferem.'); return }
    setEnviando(true)
    try {
      await definirSenha(usuario, senha, novaSenha)
      navigate('/app', { replace: true })
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao definir a senha.')
    } finally { setEnviando(false) }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-primary/15 flex items-center justify-center mb-3 shadow-sm">
            <span className="text-xl font-extrabold text-primary">G</span>
          </div>
          <h1 className="text-2xl font-extrabold text-slate-100 tracking-tight">GestorHS</h1>
          <p className="text-sm text-slate-500 mt-1">{etapa === 'login' ? 'Faça login para continuar' : 'Defina sua nova senha'}</p>
        </div>
        <div className="rounded-2xl bg-background-surface border border-border shadow-sm p-6">
          {etapa === 'login' ? (
            <form className="space-y-4" onSubmit={onLogin}>
              <Input id="login" label="Usuário" value={usuario} onChange={(e) => setUsuario(e.target.value)} autoComplete="username" autoFocus />
              <Input id="senha" label="Senha" type="password" value={senha} onChange={(e) => setSenha(e.target.value)} autoComplete="current-password" />
              {erro && (
                <div className="flex items-center gap-2 rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">
                  <IconAlertCircle className="w-4 h-4 shrink-0" />{erro}
                </div>
              )}
              <button type="submit" disabled={enviando} className="w-full py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2">
                {enviando && <Spinner className="w-4 h-4 text-white" />}Entrar
              </button>
            </form>
          ) : (
            <form className="space-y-4" onSubmit={onDefinir}>
              <p className="text-sm text-slate-400">Sua senha é temporária. Defina uma nova para continuar.</p>
              <Input id="nova" label="Nova senha" type="password" value={novaSenha} onChange={(e) => setNovaSenha(e.target.value)} autoComplete="new-password" autoFocus />
              <Input id="confirma" label="Confirmar nova senha" type="password" value={confirma} onChange={(e) => setConfirma(e.target.value)} autoComplete="new-password" />
              {erro && (
                <div className="flex items-center gap-2 rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">
                  <IconAlertCircle className="w-4 h-4 shrink-0" />{erro}
                </div>
              )}
              <button type="submit" disabled={enviando} className="w-full py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2">
                {enviando && <Spinner className="w-4 h-4 text-white" />}Definir senha
              </button>
              <button type="button" onClick={() => { setEtapa('login'); setErro('') }} className="w-full text-xs text-slate-400 hover:text-slate-200">voltar ao login</button>
            </form>
          )}
        </div>
        <p className="text-center text-xs text-slate-400 mt-6">GestorHS · Health Safety</p>
      </div>
    </div>
  )
}
