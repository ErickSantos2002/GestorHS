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

const ME = { id: 1, nome: 'Erick', email: 'erick@hs.com', funcao_id: 1, funcao: 'Administrador' }

function Probe() {
  const { user, loading, login, logout, entrarComTokens } = useAuth()
  return (
    <div>
      <span data-testid="loading">{String(loading)}</span>
      <span data-testid="user">{user ? user.email : 'anon'}</span>
      <button onClick={() => login('erick@hs.com', 'senha')}>entrar</button>
      <button onClick={() => entrarComTokens({ access_token: 'sso-acc', refresh_token: 'sso-ref' })}>
        entrar por token
      </button>
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
    await waitFor(() => expect(screen.getByTestId('user').textContent).toBe('erick@hs.com'))
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

    await waitFor(() => expect(screen.getByTestId('user').textContent).toBe('erick@hs.com'))
    expect(getTokens()?.access_token).toBe('a')
  })

  it('logout limpa tokens e usuário', async () => {
    setTokens({ access_token: 'a', refresh_token: 'r' })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(ME)))
    renderProbe()
    await waitFor(() => expect(screen.getByTestId('user').textContent).toBe('erick@hs.com'))

    await act(async () => {
      screen.getByText('sair').click()
    })

    expect(screen.getByTestId('user').textContent).toBe('anon')
    expect(getTokens()).toBeNull()
  })

  it('entrarComTokens persiste o par e hidrata o usuário', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(ME)))
    renderProbe()
    await waitFor(() => expect(screen.getByTestId('loading').textContent).toBe('false'))

    await act(async () => {
      screen.getByText('entrar por token').click()
    })

    await waitFor(() => expect(screen.getByTestId('user').textContent).toBe('erick@hs.com'))
    expect(getTokens()).toEqual({ access_token: 'sso-acc', refresh_token: 'sso-ref' })
  })
})

function ProbeReset() {
  const { user, login, definirSenha } = useAuth()
  return (
    <div>
      <span data-testid="user2">{user ? user.email : 'anon'}</span>
      <span data-testid="res" />
      <button onClick={async () => { const r = await login('temp', 'prov'); document.querySelector('[data-testid=res]')!.textContent = String(r.precisa_redefinir) }}>login</button>
      <button onClick={() => definirSenha('temp', 'prov', 'novasenha123')}>definir</button>
    </div>
  )
}

describe('AuthContext — reset forçado', () => {
  beforeEach(() => { localStorage.clear(); vi.restoreAllMocks() })

  it('login com precisa_redefinir não autentica', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ precisa_redefinir: true })))
    render(<AuthProvider><ProbeReset /></AuthProvider>)
    await act(async () => { screen.getByText('login').click() })
    await waitFor(() => expect(screen.getByTestId('res').textContent).toBe('true'))
    expect(screen.getByTestId('user2').textContent).toBe('anon')
  })

  it('definirSenha guarda tokens e carrega o usuário', async () => {
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(jsonResponse({ access_token: 'a', refresh_token: 'r' }))  // definir-senha
      .mockResolvedValueOnce(jsonResponse(ME)))  // /auth/me
    render(<AuthProvider><ProbeReset /></AuthProvider>)
    await act(async () => { screen.getByText('definir').click() })
    await waitFor(() => expect(screen.getByTestId('user2').textContent).toBe('erick@hs.com'))
    expect(getTokens()?.access_token).toBe('a')
  })
})
