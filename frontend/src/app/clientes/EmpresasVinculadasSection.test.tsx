import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { EmpresasVinculadasSection } from './EmpresasVinculadasSection'
import { empresasApi, type Empresa } from '../empresas/api'

const EMPRESA = {
  id: 9, cliente: 5, matriz_nome: 'ACME', nome: 'Filial Norte', cgc: '36312056000552', cpf: null,
  municipio: 'Joao Neiva', estado: 'ES', ativo: true,
} as Empresa

describe('EmpresasVinculadasSection', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('lista as filiais do cliente', async () => {
    const listar = vi.spyOn(empresasApi, 'listar').mockResolvedValue({ items: [EMPRESA], total: 1 })
    render(<MemoryRouter><EmpresasVinculadasSection clienteId={5} /></MemoryRouter>)
    expect(await screen.findByText('Filial Norte')).toBeInTheDocument()
    expect(listar).toHaveBeenCalledWith({ cliente: 5, limit: 100 })
  })

  it('some quando nao ha filial', async () => {
    const listar = vi.spyOn(empresasApi, 'listar').mockResolvedValue({ items: [], total: 0 })
    const { container } = render(<MemoryRouter><EmpresasVinculadasSection clienteId={5} /></MemoryRouter>)
    await waitFor(() => expect(listar).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })
})
