import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { apiJson, setOnUnauthorized } from '../lib/api'
import { clearTokens, getTokens, setTokens, type Tokens } from '../lib/auth-storage'

export interface User {
  id: number
  nome: string | null
  login: string
  email: string | null
  funcao_id: number | null
}

interface AuthContextValue {
  user: User | null
  loading: boolean
  login: (login: string, senha: string) => Promise<void>
  logout: () => void
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

  async function login(login: string, senha: string) {
    const tokens = await apiJson<Tokens>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ login, senha }),
    })
    setTokens(tokens)
    const me = await apiJson<User>('/auth/me')
    setUser(me)
  }

  function logout() {
    clearTokens()
    setUser(null)
  }

  return <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth deve ser usado dentro de <AuthProvider>')
  return ctx
}
