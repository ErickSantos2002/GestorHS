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
})
