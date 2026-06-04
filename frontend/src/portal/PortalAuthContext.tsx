import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { apiJson, setOnUnauthorized } from '../lib/api'
import { clearTokens, getTokens, setTokens, type Tokens } from '../lib/auth-storage'
import { portalApi, type PortalMe } from './api'

export interface LoginResult {
  precisa_redefinir: boolean
}

interface LoginRespBody {
  precisa_redefinir?: boolean
  access_token?: string
  refresh_token?: string
}

interface PortalAuthValue {
  cliente: PortalMe | null
  loading: boolean
  login: (documento: string, login: string, senha: string) => Promise<LoginResult>
  definirSenha: (documento: string, login: string, senhaAtual: string, novaSenha: string) => Promise<void>
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

  async function login(documento: string, loginCliente: string, senha: string): Promise<LoginResult> {
    const r = await apiJson<LoginRespBody>('/auth/login-portal', {
      method: 'POST',
      body: JSON.stringify({ documento, login: loginCliente, senha }),
    })
    if (r.precisa_redefinir) return { precisa_redefinir: true }
    setTokens({ access_token: r.access_token as string, refresh_token: r.refresh_token as string })
    const me = await portalApi.me()
    setCliente(me)
    return { precisa_redefinir: false }
  }

  async function definirSenha(documento: string, loginCliente: string, senhaAtual: string, novaSenha: string) {
    const tokens = await apiJson<Tokens>('/auth/definir-senha-portal', {
      method: 'POST',
      body: JSON.stringify({ documento, login: loginCliente, senha_atual: senhaAtual, nova_senha: novaSenha }),
    })
    setTokens(tokens)
    const me = await portalApi.me()
    setCliente(me)
  }

  function logout() {
    clearTokens()
    setCliente(null)
  }

  return <PortalAuthContext.Provider value={{ cliente, loading, login, definirSenha, logout }}>{children}</PortalAuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function usePortalAuth(): PortalAuthValue {
  const ctx = useContext(PortalAuthContext)
  if (!ctx) throw new Error('usePortalAuth deve ser usado dentro de <PortalAuthProvider>')
  return ctx
}
