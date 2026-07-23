import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

vi.mock('../../auth/AuthContext', () => ({ useAuth: () => ({ user: { funcao: 'Administrador' } }) }))

const { obter, desvincularOrdem } = vi.hoisted(() => ({ obter: vi.fn(), desvincularOrdem: vi.fn() }))
vi.mock('./api', async (orig) => {
  const real = await orig<typeof import('./api')>()
  return { ...real, caixasApi: { ...real.caixasApi, obter, desvincularOrdem } }
})

import { CaixaDetailPage } from './CaixaDetailPage'

const CAIXA = {
  id: 3, data: '2026-07-16', obs: null, total_os: 2, clientes: ['ACME'],
  ordens: [
    { id: 10, cliente: 1, cliente_nome: 'ACME', equipamento_descricao: 'Bafômetro', equipamento_serie: 'S1', fase: 7, fase_descricao: 'Preparando Retorno', fase_cor: 'abc' },
    { id: 11, cliente: 1, cliente_nome: 'ACME', equipamento_descricao: 'Bafômetro', equipamento_serie: 'S2', fase: 5, fase_descricao: 'Laboratório', fase_cor: 'def' },
  ],
}

function tela() {
  return render(
    <MemoryRouter initialEntries={['/app/caixas/3']}>
      <Routes><Route path="/app/caixas/:id" element={<CaixaDetailPage />} /></Routes>
    </MemoryRouter>,
  )
}

describe('CaixaDetailPage', () => {
  beforeEach(() => {
    obter.mockReset(); desvincularOrdem.mockReset()
    obter.mockResolvedValue({ ...CAIXA }); desvincularOrdem.mockResolvedValue({})
  })

  it('removeu o botão "Vincular OS existente"', async () => {
    tela()
    await screen.findByText('Caixa #3')
    expect(screen.queryByText('Vincular OS existente')).toBeNull()
  })

  it('removeu o fechar OS em lote (a caixa avança como um todo)', async () => {
    tela()
    await screen.findByText('Caixa #3')
    expect(screen.queryAllByRole('checkbox')).toHaveLength(0)
    expect(screen.queryByText(/Fechar OS selecionadas/)).toBeNull()
  })
})

describe('CaixaDetailPage — avançar/cancelar caixa e sem conserto', () => {
  beforeEach(() => {
    obter.mockReset(); desvincularOrdem.mockReset()
  })

  it('bloqueia avancar caixa com aparelho pendente no lab', async () => {
    obter.mockResolvedValue({
      id: 7, fase: 5, ordens: [
        { id: 1, desfecho_lab: 'concluido', fase: 5 },
        { id: 2, desfecho_lab: 'pendente', fase: 5 }],
    })
    render(<MemoryRouter initialEntries={['/app/caixas/7']}><Routes><Route path="/app/caixas/:id" element={<CaixaDetailPage />} /></Routes></MemoryRouter>)
    const btn = await screen.findByRole('button', { name: /avançar caixa/i })
    expect(btn).toBeDisabled()
  })
})
