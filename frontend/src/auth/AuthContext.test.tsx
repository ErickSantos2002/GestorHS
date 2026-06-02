import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import { AuthProvider, useAuth } from './AuthContext'
import { setTokens, getTokens } from '../lib/auth-storage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

const ME = { id: 1, nome: 'Erick', login: 'erick', email: null, funcao_id: 1, funcao: 'Administrador' }

function Probe() {
  const { user, loading, login, logout } = useAuth()
  return (
    <div>
      <span data-testid="loading">{String(loading)}</span>
      <span data-testid="user">{user ? user.login : 'anon'}</span>
      <button onClick={() => login('erick', 'senha')}>entrar</button>
      <button onClick={() => logout()}>sair</button>
    </div>
  )
}

function renderProbe() {
  return render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  )
}

describe('AuthContext', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('sem token: termina deslogado e sem loading', async () => {
    vi.stubGlobal('fetch', vi.fn())
    renderProbe()
    await waitFor(() => expect(screen.getByTestId('loading').textContent).toBe('false'))
    expect(screen.getByTestId('user').textContent).toBe('anon')
  })

  it('com token válido: hidrata o usuário via /auth/me', async () => {
    setTokens({ access_token: 'a', refresh_token: 'r' })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(ME)))
    renderProbe()
    await waitFor(() => expect(screen.getByTestId('user').textContent).toBe('erick'))
  })

  it('com token inválido: limpa e fica deslogado', async () => {
    setTokens({ access_token: 'a', refresh_token: 'r' })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ detail: 'x' }, 401)))
    renderProbe()
    await waitFor(() => expect(screen.getByTestId('loading').textContent).toBe('false'))
    expect(screen.getByTestId('user').textContent).toBe('anon')
  })

  it('login grava tokens e popula o usuário', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ access_token: 'a', refresh_token: 'r' })) // /auth/login
      .mockResolvedValueOnce(jsonResponse(ME)) // /auth/me
    vi.stubGlobal('fetch', fetchMock)
    renderProbe()
    await waitFor(() => expect(screen.getByTestId('loading').textContent).toBe('false'))

    await act(async () => {
      screen.getByText('entrar').click()
    })

    await waitFor(() => expect(screen.getByTestId('user').textContent).toBe('erick'))
    expect(getTokens()?.access_token).toBe('a')
  })

  it('logout limpa tokens e usuário', async () => {
    setTokens({ access_token: 'a', refresh_token: 'r' })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(ME)))
    renderProbe()
    await waitFor(() => expect(screen.getByTestId('user').textContent).toBe('erick'))

    await act(async () => {
      screen.getByText('sair').click()
    })

    expect(screen.getByTestId('user').textContent).toBe('anon')
    expect(getTokens()).toBeNull()
  })
})
