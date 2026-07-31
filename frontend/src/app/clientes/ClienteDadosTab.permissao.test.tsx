import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

let mockUser: { funcao: string | null } | null = { funcao: 'Administrador' }
vi.mock('../../auth/AuthContext', () => ({ useAuth: () => ({ user: mockUser }) }))

const { clienteCtx } = vi.hoisted(() => ({
  clienteCtx: { cliente: { id: 5, nome: 'ACME', ativo: true }, recarregar: () => {} },
}))
vi.mock('./ClienteLayout', () => ({ useCliente: () => clienteCtx }))

vi.mock('../cadastros/api', () => ({ gruposApi: { listar: () => Promise.resolve([]) } }))
vi.mock('./FuncionariosSection', () => ({ FuncionariosSection: () => <div>funcionarios</div> }))
vi.mock('./UsuariosPortalSection', () => ({ UsuariosPortalSection: () => <div>portal</div> }))

import { ClienteDadosTab } from './ClienteDadosTab'

describe('ClienteDadosTab (permissao para editar cadastro)', () => {
  beforeEach(() => {
    mockUser = { funcao: 'Administrador' }
  })

  it('Comercial Pós-Vendas edita os dados do cliente (campo habilitado)', async () => {
    mockUser = { funcao: 'Comercial Pós-Vendas' }
    render(<ClienteDadosTab />)
    const campoNome = await screen.findByLabelText('Nome')
    expect(campoNome).not.toBeDisabled()
  })

  it('Financeiro não edita cadastro (campo desabilitado)', async () => {
    mockUser = { funcao: 'Financeiro' }
    render(<ClienteDadosTab />)
    const campoNome = await screen.findByLabelText('Nome')
    expect(campoNome).toBeDisabled()
  })
})
