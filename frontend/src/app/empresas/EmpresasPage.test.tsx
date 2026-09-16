import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

let mockUser = { id: 1, nome: 'Com', email: 'c@c.com', funcao_id: 1, funcao: 'Comercial Pós-Vendas' }
vi.mock('../../auth/AuthContext', () => ({ useAuth: () => ({ user: mockUser }) }))

import { EmpresasPage } from './EmpresasPage'
import { empresasApi, type Empresa } from './api'
import { clientesApi } from '../clientes/api'
import { ApiError } from '../../lib/api'

const EMPRESA: Empresa = {
  id: 9, cliente: 5, matriz_nome: 'ACME', nome: 'Filial Norte', cgc: '36312056000552', cpf: null, cep: '29680000',
  endereco: 'BR 101', numero: 'S/N', complemento: null, bairro: null, municipio: 'Joao Neiva', estado: 'ES',
  email: 'f@acme.com', telefone: '2733330000', insc_est: null, ativo: true, created_at: null, updated_at: null,
}

const renderPagina = () => render(<MemoryRouter><EmpresasPage /></MemoryRouter>)

describe('EmpresasPage', () => {
  beforeEach(() => {
    mockUser = { id: 1, nome: 'Com', email: 'c@c.com', funcao_id: 1, funcao: 'Comercial Pós-Vendas' }
    vi.restoreAllMocks()
    vi.spyOn(empresasApi, 'listar').mockResolvedValue({ items: [EMPRESA], total: 1 })
    vi.spyOn(clientesApi, 'listar').mockResolvedValue({ items: [], total: 0 })
  })

  it('lista empresas com a matriz', async () => {
    renderPagina()
    expect(await screen.findByText('Filial Norte')).toBeInTheDocument()
    expect(screen.getByText('ACME')).toBeInTheDocument()
    expect(screen.getByText('36.312.056/0005-52')).toBeInTheDocument()
  })

  it('cria empresa pelo modal', async () => {
    const criar = vi.spyOn(empresasApi, 'criar').mockResolvedValue({ ...EMPRESA, id: 10 })
    renderPagina()
    await screen.findByText('Filial Norte')
    fireEvent.click(screen.getByRole('button', { name: 'Nova empresa' }))
    fireEvent.change(screen.getByLabelText(/Razão social/), { target: { value: 'Filial Sul' } })
    fireEvent.change(screen.getByLabelText(/CNPJ \/ CPF/), { target: { value: '11.222.333/0001-81' } })
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }))
    await waitFor(() => expect(criar).toHaveBeenCalledWith(expect.objectContaining({
      nome: 'Filial Sul', documento: '11222333000181', cliente: null, email: null,
    })))
  })

  it('mostra o 409 de documento duplicado', async () => {
    vi.spyOn(empresasApi, 'criar').mockRejectedValue(new ApiError(409, 'Documento já cadastrado como Cliente: ACME'))
    renderPagina()
    await screen.findByText('Filial Norte')
    fireEvent.click(screen.getByRole('button', { name: 'Nova empresa' }))
    fireEvent.change(screen.getByLabelText(/Razão social/), { target: { value: 'X' } })
    fireEvent.change(screen.getByLabelText(/CNPJ \/ CPF/), { target: { value: '08857492000148' } })
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(await screen.findByText('Documento já cadastrado como Cliente: ACME')).toBeInTheDocument()
  })

  it('quem nao gerencia so visualiza', async () => {
    mockUser = { ...mockUser, funcao: 'Laboratório' }
    renderPagina()
    await screen.findByText('Filial Norte')
    expect(screen.queryByRole('button', { name: 'Nova empresa' })).toBeNull()
  })
})
