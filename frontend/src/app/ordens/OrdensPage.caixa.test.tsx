import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const { quadro, listar } = vi.hoisted(() => ({ quadro: vi.fn(), listar: vi.fn() }))
vi.mock('./api', async (orig) => {
  const real = await orig<typeof import('./api')>()
  return { ...real, ordensApi: { quadro, listar } }
})

import { OrdensPage } from './OrdensPage'

function os(over: Record<string, unknown> = {}) {
  return {
    id: 10839, cliente: 1, cliente_nome: 'CINPAL', equipamento_cliente: 1,
    equipamento_descricao: 'IBLOW10D', equipamento_serie: 'SN-1', fase: 4,
    fase_descricao: 'Recebido', fase_cor: 'aabbcc', tipo_servico: 'C',
    data_chegada: null, prox_calibragem: null, situacao: 'A', caixa: 740, ...over,
  }
}

function tela() {
  return render(<MemoryRouter><OrdensPage /></MemoryRouter>)
}

describe('numero da caixa nas ordens', () => {
  it('aparece no card do quadro, antes do numero da OS', async () => {
    quadro.mockResolvedValue([{ fase: 4, descricao: 'Recebido', cor: 'aabbcc', total: 1, ordens: [os()] }])
    tela()
    expect(await screen.findByText(/CX 740/)).toBeInTheDocument()
    expect(screen.getByText(/OS #10839/)).toBeInTheDocument()
  })

  it('nao mostra caixa no card quando a OS nao tem', async () => {
    quadro.mockResolvedValue([{ fase: 4, descricao: 'Recebido', cor: 'aabbcc', total: 1, ordens: [os({ caixa: null })] }])
    tela()
    expect(await screen.findByText(/OS #10839/)).toBeInTheDocument()
    expect(screen.queryByText(/CX/)).toBeNull()
  })

  it('tem coluna Caixa na vista de lista', async () => {
    quadro.mockResolvedValue([])
    listar.mockResolvedValue({ items: [os()], total: 1 })
    tela()
    fireEvent.click(screen.getByText('Lista'))
    expect(await screen.findByText('Caixa')).toBeInTheDocument()
    expect(screen.getByText('CX 740')).toBeInTheDocument()
  })
})
