import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { apiJson, ApiError } from '../../lib/api'
import { Spinner } from '../../components/ui/Spinner'
import { IconAlertCircle } from '../../components/ui/icons'
import { clearTokens, type Tokens } from '../../lib/auth-storage'
import logo from '../../assets/logo.png'

export function AuthCallbackPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const { entrarComTokens } = useAuth()
  const ticket = params.get('ticket')
  // Sem ticket não há nada a trocar — o erro já nasce definido, sem passar
  // pelo efeito (setState síncrono no corpo do efeito é anti-padrão).
  const [erro, setErro] = useState(() => (ticket ? '' : 'Link de retorno inválido. Entre novamente.'))
  const jaTrocou = useRef(false)

  useEffect(() => {
    if (!ticket) return
    // O ticket é de uso único e o StrictMode roda este efeito duas vezes em
    // dev — a segunda chamada tomaria 400 e derrubaria um login que deu certo.
    // A trava também importa aqui: `entrarComTokens` (das deps abaixo) muda
    // de identidade a cada render do AuthProvider, então o próprio login bem
    // sucedido (setUser -> re-render) faria este efeito rodar de novo — sem
    // a trava, o clearTokens() logo abaixo apagaria os tokens que acabaram
    // de ser gravados.
    if (jaTrocou.current) return
    jaTrocou.current = true

    // Chegar aqui é começar uma sessão nova: limpa qualquer token velho ANTES
    // da troca, e antes da IIFE async. Efeito de filho roda antes do efeito
    // de hidratação do AuthProvider (pai) — sem isso, a hidratação acha um
    // token velho, toma 401 no /auth/me, tenta /auth/refresh, falha, e o
    // clearTokens() dela chega atrasado: apaga os tokens novos que acabaram
    // de ser gravados aqui e zera o usuário, jogando quem acabou de logar de
    // volta pro /login sem mensagem nenhuma.
    clearTokens()

    void (async () => {
      try {
        const tokens = await apiJson<Tokens>('/auth/sso/exchange', {
          method: 'POST',
          body: JSON.stringify({ ticket }),
        })
        await entrarComTokens(tokens)
        navigate('/app', { replace: true })
      } catch (err) {
        setErro(
          err instanceof ApiError ? err.message : 'Não foi possível concluir o login. Tente novamente.',
        )
      }
    })()
  }, [ticket, navigate, entrarComTokens])

  if (!erro) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-3 bg-background">
        <Spinner className="w-8 h-8" />
        <p className="text-sm text-slate-400">Entrando…</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <img src={logo} alt="Health Safety" className="h-16 w-auto mb-3" />
          <h1 className="text-2xl font-extrabold text-slate-100 tracking-tight">GestorHS</h1>
        </div>
        <div className="rounded-2xl bg-background-surface border border-border shadow-sm p-6 space-y-4">
          <div className="flex items-center gap-2 rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">
            <IconAlertCircle className="w-4 h-4 shrink-0" />
            {erro}
          </div>
          <Link
            to="/login"
            className="block w-full py-2.5 rounded-lg bg-primary text-white text-sm font-semibold text-center hover:bg-primary-600 transition-all"
          >
            Voltar para o login
          </Link>
        </div>
      </div>
    </div>
  )
}
