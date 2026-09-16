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
  tiny_id: null, tiny_status: null, tiny_erro: null, tiny_em: null,
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

  it('mostra o estado do Tiny de cada empresa', async () => {
    vi.spyOn(empresasApi, 'listar').mockResolvedValue({
      items: [
        { ...EMPRESA, id: 1, nome: 'Sincronizada', tiny_status: 'enviada', tiny_id: 610661344 },
        { ...EMPRESA, id: 2, nome: 'Com erro', tiny_status: 'erro', tiny_erro: 'Cidade não encontrada' },
        { ...EMPRESA, id: 3, nome: 'Na fila', tiny_status: 'pendente' },
        { ...EMPRESA, id: 4, nome: 'Fora', tiny_status: null },
      ],
      total: 4,
    })
    renderPagina()
    expect(await screen.findByText('Enviada')).toBeInTheDocument()
    expect(screen.getByText('610661344')).toBeInTheDocument()
    expect(screen.getByTitle('Cidade não encontrada')).toBeInTheDocument()
    expect(screen.getByText('Pendente')).toBeInTheDocument()
  })

  it('botao de reenviar aparece so em erro e pendente', async () => {
    vi.spyOn(empresasApi, 'listar').mockResolvedValue({
      items: [
        { ...EMPRESA, id: 1, nome: 'Enviada', tiny_status: 'enviada', tiny_id: 7 },
        { ...EMPRESA, id: 2, nome: 'Com erro', tiny_status: 'erro', tiny_erro: 'x' },
      ],
      total: 2,
    })
    renderPagina()
    await screen.findByText('Com erro')
    expect(screen.getAllByRole('button', { name: 'Reenviar ao Tiny' })).toHaveLength(1)
  })

  it('reenviar chama a api e recarrega', async () => {
    const listar = vi.spyOn(empresasApi, 'listar').mockResolvedValue({
      items: [{ ...EMPRESA, id: 2, nome: 'Com erro', tiny_status: 'erro', tiny_erro: 'x' }],
      total: 1,
    })
    const reenviar = vi.spyOn(empresasApi, 'reenviarTiny').mockResolvedValue({ ...EMPRESA, tiny_status: 'pendente' })
    renderPagina()
    await screen.findByText('Com erro')
    fireEvent.click(screen.getByRole('button', { name: 'Reenviar ao Tiny' }))
    await waitFor(() => expect(reenviar).toHaveBeenCalledWith(2))
    await waitFor(() => expect(listar).toHaveBeenCalledTimes(2))
  })

  it('segundo clique no reenviar nao dispara segunda chamada', async () => {
    vi.spyOn(empresasApi, 'listar').mockResolvedValue({
      items: [{ ...EMPRESA, id: 2, nome: 'Com erro', tiny_status: 'erro', tiny_erro: 'x' }],
      total: 1,
    })
    // Dois syncs simultaneos da mesma empresa criariam dois contatos no Tiny.
    let liberar: (e: Empresa) => void = () => {}
    const reenviar = vi.spyOn(empresasApi, 'reenviarTiny')
      .mockReturnValue(new Promise<Empresa>((res) => { liberar = res }))
    renderPagina()
    await screen.findByText('Com erro')
    const botao = screen.getByRole('button', { name: 'Reenviar ao Tiny' })
    fireEvent.click(botao)
    await waitFor(() => expect(botao).toBeDisabled())
    fireEvent.click(botao)
    expect(reenviar).toHaveBeenCalledTimes(1)
    liberar({ ...EMPRESA, id: 2, tiny_status: 'pendente' })
    await waitFor(() => expect(botao).not.toBeDisabled())
  })

  it('filtro de erro no Tiny passa o parametro', async () => {
    const listar = vi.spyOn(empresasApi, 'listar').mockResolvedValue({ items: [EMPRESA], total: 1 })
    renderPagina()
    await screen.findByText('Filial Norte')
    fireEvent.click(screen.getByLabelText('Só com erro no Tiny'))
    await waitFor(() => expect(listar).toHaveBeenLastCalledWith(expect.objectContaining({ tiny_status: 'erro' })))
  })

  it('quem nao gerencia nao ve o botao de reenviar', async () => {
    mockUser = { ...mockUser, funcao: 'Laboratório' }
    vi.spyOn(empresasApi, 'listar').mockResolvedValue({
      items: [{ ...EMPRESA, tiny_status: 'erro', tiny_erro: 'x' }], total: 1,
    })
    renderPagina()
    await screen.findByText('Filial Norte')
    expect(screen.queryByRole('button', { name: 'Reenviar ao Tiny' })).toBeNull()
  })
})
