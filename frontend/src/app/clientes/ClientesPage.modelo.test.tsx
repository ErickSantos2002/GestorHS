import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../../auth/AuthContext', () => ({ useAuth: () => ({ user: { funcao: 'Consulta' } }) }))

const { listar, listarModelos } = vi.hoisted(() => ({ listar: vi.fn(), listarModelos: vi.fn() }))
vi.mock('./api', async (orig) => {
  const real = await orig<typeof import('./api')>()
  return { ...real, clientesApi: { ...real.clientesApi, listar: (...a: unknown[]) => listar(...a) } }
})
vi.mock('../cadastros/api', () => ({ equipamentosApi: { listar: listarModelos } }))

import { ClientesPage } from './ClientesPage'

describe('ClientesPage — filtro "Tem aparelho"', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listar.mockResolvedValue({ items: [], total: 0 })
    listarModelos.mockResolvedValue([{ id: 36, descricao: 'Phoebus' }])
  })

  it('abre com ?equipamento= da URL aplicado', async () => {
    render(<MemoryRouter initialEntries={['/app/clientes?equipamento=36']}><ClientesPage /></MemoryRouter>)
    await waitFor(() => expect(listar).toHaveBeenLastCalledWith(expect.objectContaining({ equipamento: 36 })))
  })

  it('escolher o modelo filtra a lista', async () => {
    render(<MemoryRouter initialEntries={['/app/clientes']}><ClientesPage /></MemoryRouter>)
    await screen.findByRole('option', { name: 'Phoebus' })
    await userEvent.selectOptions(screen.getByLabelText('Tem aparelho'), '36')
    expect(listar).toHaveBeenLastCalledWith(expect.objectContaining({ equipamento: 36, offset: 0 }))
  })

  it('Consulta não vê "Novo cliente"', async () => {
    render(<MemoryRouter initialEntries={['/app/clientes']}><ClientesPage /></MemoryRouter>)
    await screen.findByRole('option', { name: 'Phoebus' })
    expect(screen.queryByRole('button', { name: /novo cliente/i })).toBeNull()
  })
})
