import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { PortalAuthProvider, usePortalAuth } from './PortalAuthContext'
import { getTokens } from '../lib/auth-storage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

function Sonda() {
  const { cliente, loading, login, logout } = usePortalAuth()
  return (
    <div>
      <span data-testid="estado">{loading ? 'loading' : cliente ? cliente.cliente_nome ?? 'sem-nome' : 'deslogado'}</span>
      <button onClick={() => void login('11222333000144', 'cliente1', 'portal123')}>entrar</button>
      <button onClick={() => logout()}>sair</button>
    </div>
  )
}

describe('PortalAuthProvider', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('sem token, fica deslogado', async () => {
    render(<PortalAuthProvider><Sonda /></PortalAuthProvider>)
    await waitFor(() => expect(screen.getByTestId('estado').textContent).toBe('deslogado'))
  })

  it('login guarda token e carrega o cliente; logout limpa', async () => {
    const f = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ access_token: 'a', refresh_token: 'r' }))  // login-portal
      .mockResolvedValueOnce(jsonResponse({ id: 1, login: 'cliente1', cliente: 5, cliente_nome: 'Empresa X' }))  // /portal/me
    vi.stubGlobal('fetch', f)
    const { default: userEvent } = await import('@testing-library/user-event')
    render(<PortalAuthProvider><Sonda /></PortalAuthProvider>)
    await waitFor(() => expect(screen.getByTestId('estado').textContent).toBe('deslogado'))
    await userEvent.click(screen.getByText('entrar'))
    await waitFor(() => expect(screen.getByTestId('estado').textContent).toBe('Empresa X'))
    expect(getTokens()).not.toBeNull()
    await userEvent.click(screen.getByText('sair'))
    await waitFor(() => expect(screen.getByTestId('estado').textContent).toBe('deslogado'))
    expect(getTokens()).toBeNull()
  })
})

function SondaReset() {
  const { cliente, login, definirSenha } = usePortalAuth()
  return (
    <div>
      <span data-testid="cli2">{cliente ? (cliente.cliente_nome ?? 'sem-nome') : 'deslogado'}</span>
      <span data-testid="res2" />
      <button onClick={async () => { const r = await login('11222333000144', 'cliente1', 'prov'); document.querySelector('[data-testid=res2]')!.textContent = String(r.precisa_redefinir) }}>login</button>
      <button onClick={() => definirSenha('11222333000144', 'cliente1', 'prov', 'novasenha123')}>definir</button>
    </div>
  )
}

describe('PortalAuthProvider — reset forçado', () => {
  beforeEach(() => { localStorage.clear(); vi.restoreAllMocks() })

  it('login com precisa_redefinir não autentica', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ precisa_redefinir: true })))
    const { default: userEvent } = await import('@testing-library/user-event')
    render(<PortalAuthProvider><SondaReset /></PortalAuthProvider>)
    await userEvent.click(screen.getByText('login'))
    await waitFor(() => expect(screen.getByTestId('res2').textContent).toBe('true'))
    expect(screen.getByTestId('cli2').textContent).toBe('deslogado')
  })

  it('definirSenha guarda tokens e carrega o cliente', async () => {
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(jsonResponse({ access_token: 'a', refresh_token: 'r' }))  // definir-senha-portal
      .mockResolvedValueOnce(jsonResponse({ id: 1, login: 'cliente1', cliente: 5, cliente_nome: 'Empresa X' })))  // /portal/me
    const { default: userEvent } = await import('@testing-library/user-event')
    render(<PortalAuthProvider><SondaReset /></PortalAuthProvider>)
    await userEvent.click(screen.getByText('definir'))
    await waitFor(() => expect(screen.getByTestId('cli2').textContent).toBe('Empresa X'))
  })
})
