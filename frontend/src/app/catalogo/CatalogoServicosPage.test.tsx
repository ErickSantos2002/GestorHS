import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockUser = { id: 1, nome: 'Admin', email: 'a@a.com', funcao_id: 1, funcao: 'Administrador' }
vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ user: mockUser }),
}))

import { CatalogoServicosPage } from './CatalogoServicosPage'
import { servicosApi, type Servico } from '../propostas/api'

const servico: Servico = {
  id: 1, sku: 'SRV-1', nome: 'Calibração padrão', descricao: null,
  unidade: 'un', preco: 150, codigo_servico: 'COD-1', ativo: true,
}

describe('CatalogoServicosPage', () => {
  beforeEach(() => {
    vi.spyOn(servicosApi, 'listar').mockResolvedValue([servico])
  })

  it('lista os servicos cadastrados', async () => {
    render(<CatalogoServicosPage />)
    expect(await screen.findByText('Calibração padrão')).toBeInTheDocument()
    expect(screen.getByText('SRV-1')).toBeInTheDocument()
  })

  it('cria um servico pelo modal', async () => {
    const criar = vi.spyOn(servicosApi, 'criar').mockResolvedValue({ ...servico, id: 2, nome: 'Novo servico' })
    render(<CatalogoServicosPage />)
    await screen.findByText('Calibração padrão')

    fireEvent.click(screen.getByRole('button', { name: /novo/i }))
    fireEvent.change(screen.getByLabelText(/nome/i), { target: { value: 'Novo servico' } })
    fireEvent.click(screen.getByRole('button', { name: /salvar/i }))

    await waitFor(() => expect(criar).toHaveBeenCalledWith(expect.objectContaining({ nome: 'Novo servico' })))
  })
})
