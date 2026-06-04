import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { apiJson, setOnUnauthorized } from '../lib/api'
import { clearTokens, getTokens, setTokens, type Tokens } from '../lib/auth-storage'
import { portalApi, type PortalMe } from './api'

interface PortalAuthValue {
  cliente: PortalMe | null
  loading: boolean
  login: (documento: string, login: string, senha: string) => Promise<void>
  logout: () => void
}

const PortalAuthContext = createContext<PortalAuthValue | null>(null)

export function PortalAuthProvider({ children }: { children: ReactNode }) {
  const [cliente, setCliente] = useState<PortalMe | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setOnUnauthorized(() => setCliente(null))
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
        const me = await portalApi.me()
        if (ativo) setCliente(me)
      } catch {
        clearTokens()
        if (ativo) setCliente(null)
      } finally {
        if (ativo) setLoading(false)
      }
    }
    void hidratar()
    return () => {
      ativo = false
    }
  }, [])

  async function login(documento: string, loginCliente: string, senha: string) {
    const tokens = await apiJson<Tokens>('/auth/login-portal', {
      method: 'POST',
      body: JSON.stringify({ documento, login: loginCliente, senha }),
    })
    setTokens(tokens)
    const me = await portalApi.me()
    setCliente(me)
  }

  function logout() {
    clearTokens()
    setCliente(null)
  }

  return <PortalAuthContext.Provider value={{ cliente, loading, login, logout }}>{children}</PortalAuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function usePortalAuth(): PortalAuthValue {
  const ctx = useContext(PortalAuthContext)
  if (!ctx) throw new Error('usePortalAuth deve ser usado dentro de <PortalAuthProvider>')
  return ctx
}
