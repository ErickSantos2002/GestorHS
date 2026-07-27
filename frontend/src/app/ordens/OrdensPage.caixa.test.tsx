import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const { listar } = vi.hoisted(() => ({ listar: vi.fn() }))
vi.mock('./api', async (orig) => {
  const real = await orig<typeof import('./api')>()
  return { ...real, ordensApi: { ...real.ordensApi, listar } }
})

const { quadro } = vi.hoisted(() => ({ quadro: vi.fn() }))
vi.mock('../caixas/api', async (orig) => {
  const real = await orig<typeof import('../caixas/api')>()
  return { ...real, caixasApi: { ...real.caixasApi, quadro } }
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

describe('quadro de ordens mostra caixas', () => {
  it('mostra progresso do lab no card da caixa', async () => {
    quadro.mockResolvedValue([
      { fase: 5, descricao: 'Laboratório', cor: 'abc', total: 1,
        caixas: [{ id: 7, cliente_nome: 'ACME', total_os: 5, prontos: 3, pendentes: 2 }] },
    ])
    tela()
    expect(await screen.findByText(/3\/5/)).toBeInTheDocument()
  })

  it('mostra caixa (numero, cliente e aparelhos) fora da coluna de laboratorio, sem badge', async () => {
    quadro.mockResolvedValue([
      { fase: 4, descricao: 'Recebido', cor: 'aabbcc', total: 1,
        caixas: [{ id: 740, cliente_nome: 'CINPAL', total_os: 2, prontos: 0, pendentes: 2 }] },
    ])
    tela()
    expect(await screen.findByText('CX 740')).toBeInTheDocument()
    expect(screen.getByText('CINPAL')).toBeInTheDocument()
    expect(screen.getByText('2 aparelhos')).toBeInTheDocument()
    expect(screen.queryByText(/prontos/)).toBeNull()
  })

  it('mostra + N outros no card da caixa multi-cliente', async () => {
    quadro.mockResolvedValue([
      { fase: 4, descricao: 'Recebido', cor: 'abc', total: 1,
        caixas: [{ id: 7, cliente_nome: 'ACME', cliente_principal_nome: 'ACME', total_os: 3, prontos: 0, pendentes: 3, outros_clientes: 1 }] },
    ])
    tela()
    expect(await screen.findByText(/\+1 outro/i)).toBeInTheDocument()
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
