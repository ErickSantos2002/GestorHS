import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { apiJson, setOnUnauthorized } from '../lib/api'
import { clearTokens, getTokens, setTokens, type Tokens } from '../lib/auth-storage'

export interface User {
  id: number
  nome: string | null
  email: string
  funcao_id: number | null
  funcao: string | null
}

export interface LoginResult {
  precisa_redefinir: boolean
}

interface LoginRespBody {
  precisa_redefinir?: boolean
  access_token?: string
  refresh_token?: string
}

interface AuthContextValue {
  user: User | null
  loading: boolean
  login: (email: string, senha: string) => Promise<LoginResult>
  logout: () => void
  definirSenha: (email: string, senhaAtual: string, novaSenha: string) => Promise<void>
  entrarComTokens: (tokens: Tokens) => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setOnUnauthorized(() => setUser(null))
    return () => setOnUnauthorized(null)
  }, [])

  useEffect(() => {
    let ativo = true
    async function hidratar() {
      if (!getTokens()) {
        if (ativo) setLoading(false)
        return
      }
      try {
        const me = await apiJson<User>('/auth/me')
        if (ativo) setUser(me)
      } catch {
        clearTokens()
        if (ativo) setUser(null)
      } finally {
        if (ativo) setLoading(false)
      }
    }
    void hidratar()
    return () => {
      ativo = false
    }
  }, [])

  async function login(email: string, senha: string): Promise<LoginResult> {
    const r = await apiJson<LoginRespBody>('/auth/login', { method: 'POST', body: JSON.stringify({ email, senha }) })
    if (r.precisa_redefinir) return { precisa_redefinir: true }
    setTokens({ access_token: r.access_token as string, refresh_token: r.refresh_token as string })
    const me = await apiJson<User>('/auth/me')
    setUser(me)
    return { precisa_redefinir: false }
  }

  async function definirSenha(email: string, senhaAtual: string, novaSenha: string) {
    const tokens = await apiJson<Tokens>('/auth/definir-senha', {
      method: 'POST',
      body: JSON.stringify({ email, senha_atual: senhaAtual, nova_senha: novaSenha }),
    })
    setTokens(tokens)
    const me = await apiJson<User>('/auth/me')
    setUser(me)
  }

  function logout() {
    clearTokens()
    setUser(null)
  }

  async function entrarComTokens(tokens: Tokens) {
    setTokens(tokens)
    const me = await apiJson<User>('/auth/me')
    setUser(me)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, definirSenha, entrarComTokens }}>
      {children}
    </AuthContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth deve ser usado dentro de <AuthProvider>')
  return ctx
}
