import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

interface FakeUser {
  funcao: string | null
}
let mockUser: FakeUser | null = null
vi.mock('../auth/AuthContext', () => ({ useAuth: () => ({ user: mockUser }) }))

import { Sidebar } from './Sidebar'

describe('Sidebar (gating por função)', () => {
  beforeEach(() => {
    mockUser = null
  })

  it('esconde "Usuários" para não-admin', () => {
    mockUser = { funcao: 'Expedição' }
    render(
      <MemoryRouter>
        <Sidebar collapsed={false} />
      </MemoryRouter>,
    )
    expect(screen.queryByText('Usuários')).toBeNull()
    expect(screen.getByText('Dashboard')).toBeInTheDocument()
  })

  it('mostra "Usuários" para Administrador', () => {
    mockUser = { funcao: 'Administrador' }
    render(
      <MemoryRouter>
        <Sidebar collapsed={false} />
      </MemoryRouter>,
    )
    expect(screen.getByText('Usuários')).toBeInTheDocument()
  })

  it('esconde "Logs de Integração" para não-admin', () => {
    mockUser = { funcao: 'Expedição' }
    render(
      <MemoryRouter>
        <Sidebar collapsed={false} />
      </MemoryRouter>,
    )
    expect(screen.queryByText('Logs de Integração')).toBeNull()
  })

  it('mostra "Logs de Integração" para Administrador', () => {
    mockUser = { funcao: 'Administrador' }
    render(
      <MemoryRouter>
        <Sidebar collapsed={false} />
      </MemoryRouter>,
    )
    expect(screen.getByText('Logs de Integração')).toBeInTheDocument()
  })

  it('Expedição vê "Propostas" mas não "Serviços" nem "Produtos"', () => {
    mockUser = { funcao: 'Expedição' }
    render(
      <MemoryRouter>
        <Sidebar collapsed={false} />
      </MemoryRouter>,
    )
    expect(screen.getByText('Propostas')).toBeInTheDocument()
    expect(screen.queryByText('Serviços')).toBeNull()
    expect(screen.queryByText('Produtos')).toBeNull()
  })

  it('Consulta vê só Dashboard, Clientes, Empresas, Equipamentos e Produtos', () => {
    mockUser = { funcao: 'Consulta' }
    render(
      <MemoryRouter>
        <Sidebar collapsed={false} />
      </MemoryRouter>,
    )
    const rotulos = screen.getAllByRole('link').map((a) => a.textContent?.trim()).filter(Boolean)
    expect(rotulos).toEqual(['Dashboard', 'Clientes', 'Empresas', 'Equipamentos', 'Produtos'])
  })
})
