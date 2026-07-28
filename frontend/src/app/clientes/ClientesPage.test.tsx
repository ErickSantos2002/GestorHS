import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ user: { id: 1, nome: 'Erick', email: 'e@hs.com', funcao_id: 1, funcao: 'Administrador' } }),
}))

const listar = vi.fn()

vi.mock('./api', async (orig) => {
  const real = await orig<typeof import('./api')>()
  return {
    ...real,
    clientesApi: { ...real.clientesApi, listar: (...a: unknown[]) => listar(...a) },
  }
})

import { ClientesPage } from './ClientesPage'

const CLIENTE = {
  id: 1, nome: 'Cliente Teste', cgc: '36312056000552', cpf: null, municipio: 'Recife', estado: 'PE', ativo: true,
}

beforeEach(() => {
  vi.clearAllMocks()
  listar.mockResolvedValue({ items: [CLIENTE], total: 1 })
})

describe('ClientesPage', () => {
  it('exibe o CNPJ formatado na lista', async () => {
    render(
      <MemoryRouter>
        <ClientesPage />
      </MemoryRouter>,
    )
    expect(await screen.findByText('36.312.056/0005-52')).toBeInTheDocument()
    expect(screen.queryByText('36312056000552')).not.toBeInTheDocument()
  })
})
