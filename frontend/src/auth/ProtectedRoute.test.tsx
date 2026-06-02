import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from './AuthContext'
import { ProtectedRoute } from './ProtectedRoute'
import { setTokens } from '../lib/auth-storage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

function renderAt(initial: string) {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={[initial]}>
        <Routes>
          <Route path="/login" element={<div>tela de login</div>} />
          <Route
            path="/app"
            element={
              <ProtectedRoute>
                <div>conteudo protegido</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  )
}

describe('ProtectedRoute', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('sem usuário redireciona para /login', async () => {
    vi.stubGlobal('fetch', vi.fn())
    renderAt('/app')
    await waitFor(() => expect(screen.getByText('tela de login')).toBeInTheDocument())
  })

  it('com usuário renderiza o conteúdo', async () => {
    setTokens({ access_token: 'a', refresh_token: 'r' })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ id: 1, nome: 'E', login: 'e', email: null, funcao_id: 1 })))
    renderAt('/app')
    await waitFor(() => expect(screen.getByText('conteudo protegido')).toBeInTheDocument())
  })

  it('durante o loading mostra o spinner', () => {
    setTokens({ access_token: 'a', refresh_token: 'r' })
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {}))) // nunca resolve → fica em loading
    renderAt('/app')
    expect(screen.getByRole('status')).toBeInTheDocument()
  })
})
