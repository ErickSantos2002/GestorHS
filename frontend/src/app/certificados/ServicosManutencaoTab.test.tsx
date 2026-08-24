import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

let mockUser: { funcao: string } | null = { funcao: 'Laboratório' }
vi.mock('../../auth/AuthContext', () => ({ useAuth: () => ({ user: mockUser }) }))

const { listarServicos, criarServico, atualizarServico, excluirServico } = vi.hoisted(() => ({
  listarServicos: vi.fn(), criarServico: vi.fn(), atualizarServico: vi.fn(), excluirServico: vi.fn(),
}))
vi.mock('../ordens/manutencao', async (orig) => {
  const real = await orig<typeof import('../ordens/manutencao')>()
  return {
    ...real,
    manutencaoApi: { ...real.manutencaoApi, listarServicos, criarServico, atualizarServico, excluirServico },
  }
})

import { ServicosManutencaoTab } from './ServicosManutencaoTab'

describe('ServicosManutencaoTab', () => {
  beforeEach(() => {
    mockUser = { funcao: 'Laboratório' }
    listarServicos.mockReset(); criarServico.mockReset(); atualizarServico.mockReset(); excluirServico.mockReset()
    listarServicos.mockResolvedValue([
      { id: 1, codigo: '226', descricao: 'Troca da placa mãe', resumo_padrao: 'Placa substituída.', ativo: true },
      { id: 2, codigo: null, descricao: 'Serviço antigo', resumo_padrao: 'x.', ativo: false },
    ])
  })

  it('lista os serviços, mostrando os inativos como tal', async () => {
    render(<ServicosManutencaoTab />)
    expect(await screen.findByText('Troca da placa mãe')).toBeInTheDocument()
    expect(screen.getByText('Serviço antigo')).toBeInTheDocument()
    expect(screen.getByText('Inativo')).toBeInTheDocument()
  })

  it('laboratório cadastra um serviço novo', async () => {
    criarServico.mockResolvedValue({ id: 3, descricao: 'Troca do bocal', resumo_padrao: 'Bocal trocado.', ativo: true })
    render(<ServicosManutencaoTab />)
    await userEvent.click(await screen.findByText('Novo serviço'))
    fireEvent.change(screen.getByLabelText('Descrição'), { target: { value: 'Troca do bocal' } })
    fireEvent.change(screen.getByLabelText('Resumo padrão'), { target: { value: 'Bocal trocado.' } })
    await userEvent.click(screen.getByText('Salvar'))

    await waitFor(() => expect(criarServico).toHaveBeenCalledWith({
      codigo: null, descricao: 'Troca do bocal', resumo_padrao: 'Bocal trocado.',
    }))
  })

  it('laboratório não vê o botão de excluir', async () => {
    render(<ServicosManutencaoTab />)
    await screen.findByText('Troca da placa mãe')
    expect(screen.queryByLabelText('Excluir')).not.toBeInTheDocument()
  })

  it('administrador vê o botão de excluir', async () => {
    mockUser = { funcao: 'Administrador' }
    render(<ServicosManutencaoTab />)
    await screen.findByText('Troca da placa mãe')
    expect(screen.getAllByLabelText('Excluir').length).toBeGreaterThan(0)
  })

  it('mostra o código na lista e envia o que foi digitado', async () => {
    criarServico.mockResolvedValue({ id: 3, codigo: '294', descricao: 'Troca de pilha interna', resumo_padrao: '', ativo: true })
    render(<ServicosManutencaoTab />)
    // O código vem do catálogo comercial e aparece na coluna própria.
    expect(await screen.findByText('226')).toBeInTheDocument()

    await userEvent.click(screen.getByText('Novo serviço'))
    fireEvent.change(screen.getByLabelText('Código'), { target: { value: '294' } })
    fireEvent.change(screen.getByLabelText('Descrição'), { target: { value: 'Troca de pilha interna' } })
    await userEvent.click(screen.getByText('Salvar'))

    await waitFor(() => expect(criarServico).toHaveBeenCalledWith({
      codigo: '294', descricao: 'Troca de pilha interna', resumo_padrao: '',
    }))
  })

  it('serviço sem código mostra travessão, não vazio', async () => {
    render(<ServicosManutencaoTab />)
    await screen.findByText('Troca da placa mãe')
    expect(screen.getByText('—')).toBeInTheDocument()
  })
})
