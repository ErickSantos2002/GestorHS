import { useEffect, useState, type FormEvent } from 'react'
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { ApiError, apiJson, apiUrl } from '../../lib/api'
import { Input } from '../../components/ui/Input'
import { Spinner } from '../../components/ui/Spinner'
import { IconAlertCircle } from '../../components/ui/icons'
import logo from '../../assets/logo.png'

const MENSAGENS_SSO: Record<string, string> = {
  usuario_nao_encontrado: 'Nenhuma conta GestorHS para este e-mail Microsoft. Fale com o administrador.',
  usuario_inativo: 'Usuário desativado. Fale com o administrador.',
  falha_microsoft: 'Falha na autenticação com a Microsoft. Tente novamente.',
}

export function LoginPage() {
  const { login, definirSenha, user, loading } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [etapa, setEtapa] = useState<'login' | 'definir'>('login')
  const [novaSenha, setNovaSenha] = useState('')
  const [confirma, setConfirma] = useState('')
  const [erro, setErro] = useState(MENSAGENS_SSO[params.get('erro') ?? ''] ?? '')
  const [enviando, setEnviando] = useState(false)
  const [ssoAtivo, setSsoAtivo] = useState(false)

  useEffect(() => {
    // O backend e' a fonte unica: um VITE_SSO_ATIVO no build duplicaria a
    // configuracao em duas pontas que podem discordar. Falhou, esconde.
    void apiJson<{ ativo: boolean }>('/auth/sso/status')
      .then((r) => setSsoAtivo(r.ativo))
      .catch(() => setSsoAtivo(false))
  }, [])

  if (loading) {
    return <div className="flex h-screen items-center justify-center bg-background"><Spinner className="w-8 h-8" /></div>
  }
  if (user) return <Navigate to="/app" replace />

  async function onLogin(e: FormEvent) {
    e.preventDefault()
    setErro(''); setEnviando(true)
    try {
      const r = await login(email, senha)
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
      await definirSenha(email, senha, novaSenha)
      navigate('/app', { replace: true })
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao definir a senha.')
    } finally { setEnviando(false) }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <img src={logo} alt="Health Safety" className="h-16 w-auto mb-3" />
          <h1 className="text-2xl font-extrabold text-slate-100 tracking-tight">GestorHS</h1>
          <p className="text-sm text-slate-500 mt-1">{etapa === 'login' ? 'Faça login para continuar' : 'Defina sua nova senha'}</p>
        </div>
        <div className="rounded-2xl bg-background-surface border border-border shadow-sm p-6">
          {etapa === 'login' ? (
            <form className="space-y-4" onSubmit={onLogin}>
              <Input id="email" label="E-mail" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" autoFocus />
              <Input id="senha" label="Senha" type="password" value={senha} onChange={(e) => setSenha(e.target.value)} autoComplete="current-password" />
              {erro && (
                <div className="flex items-center gap-2 rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">
                  <IconAlertCircle className="w-4 h-4 shrink-0" />{erro}
                </div>
              )}
              <button type="submit" disabled={enviando} className="w-full py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2">
                {enviando && <Spinner className="w-4 h-4 text-white" />}Entrar
              </button>
              {ssoAtivo && (
                <>
                  <div className="flex items-center gap-3 pt-2">
                    <span className="h-px flex-1 bg-border" />
                    <span className="text-xs text-slate-500">ou</span>
                    <span className="h-px flex-1 bg-border" />
                  </div>
                  <a
                    href={apiUrl('/auth/microsoft')}
                    className="w-full py-2.5 rounded-lg bg-background-surface border border-border text-sm font-semibold text-slate-200 hover:bg-white/5 active:scale-[0.98] transition-all flex items-center justify-center gap-2"
                  >
                    <svg className="w-4 h-4" viewBox="0 0 21 21" aria-hidden="true">
                      <rect x="1" y="1" width="9" height="9" fill="#f25022" />
                      <rect x="11" y="1" width="9" height="9" fill="#7fba00" />
                      <rect x="1" y="11" width="9" height="9" fill="#00a4ef" />
                      <rect x="11" y="11" width="9" height="9" fill="#ffb900" />
                    </svg>
                    Entrar com Microsoft
                  </a>
                </>
              )}
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
