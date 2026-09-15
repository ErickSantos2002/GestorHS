import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

const buscar = vi.fn()
vi.mock('../empresas/api', () => ({ destinatariosApi: { buscar: (...a: unknown[]) => buscar(...a) } }))

import { DestinatarioBusca } from './DestinatarioBusca'

const CLIENTE = { tipo: 'cliente', id: 5, nome: 'Rumo Matriz', documento: '08857492000148', municipio: 'Recife', estado: 'PE', matriz_id: null, matriz_nome: null }
const EMPRESA = { tipo: 'empresa', id: 9, nome: 'Rumo Filial', documento: '36312056000552', municipio: 'Curitiba', estado: 'PR', matriz_id: 5, matriz_nome: 'Rumo Matriz' }

describe('DestinatarioBusca', () => {
  beforeEach(() => buscar.mockReset())

  it('marca cada resultado como Cliente ou Empresa e escolhe', async () => {
    buscar.mockResolvedValue([CLIENTE, EMPRESA])
    const onEscolher = vi.fn()
    render(<DestinatarioBusca onEscolher={onEscolher} onCadastrarEmpresa={vi.fn()} />)
    fireEvent.change(screen.getByPlaceholderText(/Buscar cliente ou empresa/), { target: { value: 'rumo' } })
    expect(await screen.findByText('Empresa · matriz Rumo Matriz')).toBeInTheDocument()
    expect(screen.getByText('Cliente')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Rumo Filial/ }))
    expect(onEscolher).toHaveBeenCalledWith(EMPRESA)
  })

  it('documento completo sem resultado oferece cadastrar empresa', async () => {
    buscar.mockResolvedValue([])
    const onCadastrar = vi.fn()
    render(<DestinatarioBusca onEscolher={vi.fn()} onCadastrarEmpresa={onCadastrar} />)
    fireEvent.change(screen.getByPlaceholderText(/Buscar cliente ou empresa/), { target: { value: '36.312.056/0005-52' } })
    fireEvent.click(await screen.findByRole('button', { name: 'Cadastrar empresa com este documento' }))
    expect(onCadastrar).toHaveBeenCalledWith('36312056000552')
  })

  it('nome sem resultado nao oferece cadastro', async () => {
    buscar.mockResolvedValue([])
    render(<DestinatarioBusca onEscolher={vi.fn()} onCadastrarEmpresa={vi.fn()} />)
    fireEvent.change(screen.getByPlaceholderText(/Buscar cliente ou empresa/), { target: { value: 'inexistente' } })
    await waitFor(() => expect(buscar).toHaveBeenCalled())
    expect(await screen.findByText('Nenhum cliente ou empresa encontrado.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Cadastrar empresa/ })).toBeNull()
  })
})
