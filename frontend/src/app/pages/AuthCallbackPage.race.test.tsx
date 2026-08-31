import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AuthProvider } from '../../auth/AuthContext'
import { AuthCallbackPage } from './AuthCallbackPage'
import { setTokens, getTokens } from '../../lib/auth-storage'

// Reproduz a corrida descrita na revisão: com um token VELHO já no
// localStorage, o efeito de hidratação do AuthProvider (pai) e o efeito de
// troca do ticket na AuthCallbackPage (filho) disparam juntos em /auth/callback.
// Sem a correção, a hidratação vê o token velho, toma 401 no /auth/me, tenta
// /auth/refresh, falha, e o clearTokens() dela chega DEPOIS que o exchange já
// gravou os tokens novos — apagando-os. Este teste afirma que, ao final do
// fluxo, o localStorage tem os tokens NOVOS: nem os velhos, nem vazio.

const ME = { id: 1, nome: 'Erick', email: 'erick@hs.com', funcao_id: 1, funcao: 'Administrador' }
const NOVOS = { access_token: 'novo-acc', refresh_token: 'novo-ref', token_type: 'bearer' }

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

function montarFetchMock() {
  return vi.fn((url: string, options?: RequestInit) => {
    const headers = new Headers(options?.headers)
    const auth = headers.get('Authorization')

    if (url.includes('/auth/sso/exchange')) {
      return Promise.resolve(jsonResponse(NOVOS))
    }
    if (url.includes('/auth/me')) {
      if (auth === `Bearer ${NOVOS.access_token}`) return Promise.resolve(jsonResponse(ME))
      // token velho (ou nenhum): a hidratação toma 401
      return Promise.resolve(jsonResponse({ detail: 'não autenticado' }, 401))
    }
    if (url.includes('/auth/refresh')) {
      // refresh do token velho falha — é o caminho que dispara o clearTokens
      // atrasado se a corrida não estiver corrigida.
      return Promise.resolve(jsonResponse({ detail: 'refresh inválido' }, 401))
    }
    throw new Error(`fetch não mockado: ${url}`)
  })
}

function montar(query: string) {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={[`/auth/callback${query}`]}>
        <AuthCallbackPage />
      </MemoryRouter>
    </AuthProvider>,
  )
}

describe('AuthCallbackPage — corrida com a hidratação do AuthProvider', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('com token velho no localStorage, termina com os tokens novos (não os velhos, não vazio)', async () => {
    setTokens({ access_token: 'velho-acc', refresh_token: 'velho-ref' })
    vi.stubGlobal('fetch', montarFetchMock())

    montar('?ticket=abc123')

    await waitFor(() => expect(getTokens()).toEqual(NOVOS))
    // Confirma que não regrediu para vazio nem ficou com o token velho depois
    // que a hidratação também terminar.
    expect(getTokens()).not.toBeNull()
    expect(getTokens()?.access_token).not.toBe('velho-acc')
  })
})
