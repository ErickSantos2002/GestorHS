import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockUser = { id: 1, nome: 'Admin', email: 'a@a.com', funcao_id: 1, funcao: 'Administrador' }
vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ user: mockUser }),
}))

import { CatalogoProdutosPage } from './CatalogoProdutosPage'
import { produtosApi, type Produto } from '../propostas/api'

const produto: Produto = {
  id: 1, sku: 'PRD-1', nome: 'Bocal descartável', descricao: null,
  unidade: 'un', preco: 5, ncm: '1234.56.78', ativo: true,
}

describe('CatalogoProdutosPage', () => {
  beforeEach(() => {
    vi.spyOn(produtosApi, 'listar').mockResolvedValue([produto])
  })

  it('lista os produtos cadastrados', async () => {
    render(<CatalogoProdutosPage />)
    expect(await screen.findByText('Bocal descartável')).toBeInTheDocument()
    expect(screen.getByText('PRD-1')).toBeInTheDocument()
  })

  it('cria um produto pelo modal', async () => {
    const criar = vi.spyOn(produtosApi, 'criar').mockResolvedValue({ ...produto, id: 2, nome: 'Novo produto' })
    render(<CatalogoProdutosPage />)
    await screen.findByText('Bocal descartável')

    fireEvent.click(screen.getByRole('button', { name: /novo/i }))
    fireEvent.change(screen.getByLabelText(/nome/i), { target: { value: 'Novo produto' } })
    fireEvent.click(screen.getByRole('button', { name: /salvar/i }))

    await waitFor(() => expect(criar).toHaveBeenCalledWith(expect.objectContaining({ nome: 'Novo produto' })))
  })
})
