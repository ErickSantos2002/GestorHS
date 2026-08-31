import { StrictMode } from 'react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const entrarComTokens = vi.fn()
const navigate = vi.fn()
const apiJson = vi.fn()

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ entrarComTokens }),
}))

vi.mock('../../lib/api', async () => {
  const real = await vi.importActual<typeof import('../../lib/api')>('../../lib/api')
  return { ...real, apiJson: (...args: unknown[]) => apiJson(...args) }
})

vi.mock('react-router-dom', async () => {
  const real = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...real, useNavigate: () => navigate }
})

import { AuthCallbackPage } from './AuthCallbackPage'
import { ApiError } from '../../lib/api'

function montar(query: string) {
  return render(
    <MemoryRouter initialEntries={[`/auth/callback${query}`]}>
      <AuthCallbackPage />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  entrarComTokens.mockResolvedValue(undefined)
})

describe('AuthCallbackPage', () => {
  it('troca o ticket, entra e vai para /app', async () => {
    apiJson.mockResolvedValue({ access_token: 'acc', refresh_token: 'ref' })
    montar('?ticket=abc123')

    await waitFor(() =>
      expect(apiJson).toHaveBeenCalledWith('/auth/sso/exchange', {
        method: 'POST',
        body: JSON.stringify({ ticket: 'abc123' }),
      }),
    )
    await waitFor(() => expect(entrarComTokens).toHaveBeenCalledWith({ access_token: 'acc', refresh_token: 'ref' }))
    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/app', { replace: true }))
  })

  it('mostra a mensagem do backend quando o ticket ja foi usado', async () => {
    apiJson.mockRejectedValue(new ApiError(400, 'Link de acesso inválido ou expirado. Entre de novo.'))
    montar('?ticket=usado')

    expect(await screen.findByText(/Link de acesso inválido ou expirado/)).toBeInTheDocument()
    expect(screen.getByText('Voltar para o login')).toBeInTheDocument()
    expect(navigate).not.toHaveBeenCalled()
  })

  it('reclama quando volta sem ticket', async () => {
    montar('')
    expect(await screen.findByText(/Link de retorno inválido/)).toBeInTheDocument()
    expect(apiJson).not.toHaveBeenCalled()
  })

  it('troca o ticket uma vez so mesmo com o StrictMode invocando o efeito duas vezes', async () => {
    // O ticket e' de uso unico e o StrictMode roda o efeito duas vezes em dev:
    // a segunda chamada tomaria 400 e derrubaria um login que deu certo.
    apiJson.mockResolvedValue({ access_token: 'acc', refresh_token: 'ref' })
    render(
      <StrictMode>
        <MemoryRouter initialEntries={['/auth/callback?ticket=abc123']}>
          <AuthCallbackPage />
        </MemoryRouter>
      </StrictMode>,
    )
    await waitFor(() => expect(entrarComTokens).toHaveBeenCalled())
    expect(apiJson).toHaveBeenCalledTimes(1)
  })
})
