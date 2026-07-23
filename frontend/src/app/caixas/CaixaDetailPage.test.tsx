import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

let mockUser = { funcao: 'Administrador' }
vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ user: mockUser })
}))

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
    mockUser = { funcao: 'Administrador' }
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
    mockUser = { funcao: 'Administrador' }
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

describe('CaixaDetailPage — gating por funcao (role-based)', () => {
  beforeEach(() => {
    mockUser = { funcao: 'Administrador' }
    obter.mockReset(); desvincularOrdem.mockReset()
  })

  it('Laboratorio ve botao Avançar em fase 5, Comercial não', async () => {
    // Caixa em fase 5 (Laboratório é responsável)
    obter.mockResolvedValue({
      id: 5, data: '2026-07-16', obs: null, total_os: 1, clientes: ['ACME'],
      fase: 5,
      ordens: [
        { id: 10, cliente: 1, cliente_nome: 'ACME', equipamento_descricao: 'Bafômetro', equipamento_serie: 'S1', fase: 5, fase_descricao: 'Laboratório', fase_cor: 'abc', desfecho_lab: 'concluido' },
      ],
    })

    // Teste 1: Laboratório pode ver e clicar em "Avançar caixa"
    mockUser = { funcao: 'Laboratório' }
    const { unmount: unmount1 } = render(
      <MemoryRouter initialEntries={['/app/caixas/5']}>
        <Routes><Route path="/app/caixas/:id" element={<CaixaDetailPage />} /></Routes>
      </MemoryRouter>,
    )
    await screen.findByText('Caixa #5')
    expect(screen.queryByRole('button', { name: /avançar caixa/i })).not.toBeNull()
    unmount1()

    // Teste 2: Comercial Pós-Vendas NÃO pode ver "Avançar caixa" em fase 5
    mockUser = { funcao: 'Comercial Pós-Vendas' }
    obter.mockResolvedValue({
      id: 5, data: '2026-07-16', obs: null, total_os: 1, clientes: ['ACME'],
      fase: 5,
      ordens: [
        { id: 10, cliente: 1, cliente_nome: 'ACME', equipamento_descricao: 'Bafômetro', equipamento_serie: 'S1', fase: 5, fase_descricao: 'Laboratório', fase_cor: 'abc', desfecho_lab: 'concluido' },
      ],
    })
    render(
      <MemoryRouter initialEntries={['/app/caixas/5']}>
        <Routes><Route path="/app/caixas/:id" element={<CaixaDetailPage />} /></Routes>
      </MemoryRouter>,
    )
    await screen.findByText('Caixa #5')
    expect(screen.queryByRole('button', { name: /avançar caixa/i })).toBeNull()
  })

  it('Comercial ve botao Avançar em fase 6, Laboratorio não', async () => {
    // Caixa em fase 6 (Comercial é responsável)
    obter.mockResolvedValue({
      id: 6, data: '2026-07-16', obs: null, total_os: 1, clientes: ['ACME'],
      fase: 6,
      ordens: [
        { id: 10, cliente: 1, cliente_nome: 'ACME', equipamento_descricao: 'Bafômetro', equipamento_serie: 'S1', fase: 6, fase_descricao: 'Pós-Vendas', fase_cor: 'abc' },
      ],
    })

    // Teste 1: Comercial pode ver "Avançar caixa" em fase 6
    mockUser = { funcao: 'Comercial Pós-Vendas' }
    const { unmount: unmount1 } = render(
      <MemoryRouter initialEntries={['/app/caixas/6']}>
        <Routes><Route path="/app/caixas/:id" element={<CaixaDetailPage />} /></Routes>
      </MemoryRouter>,
    )
    await screen.findByText('Caixa #6')
    expect(screen.queryByRole('button', { name: /avançar caixa/i })).not.toBeNull()
    unmount1()

    // Teste 2: Laboratório NÃO pode ver "Avançar caixa" em fase 6
    mockUser = { funcao: 'Laboratório' }
    obter.mockResolvedValue({
      id: 6, data: '2026-07-16', obs: null, total_os: 1, clientes: ['ACME'],
      fase: 6,
      ordens: [
        { id: 10, cliente: 1, cliente_nome: 'ACME', equipamento_descricao: 'Bafômetro', equipamento_serie: 'S1', fase: 6, fase_descricao: 'Pós-Vendas', fase_cor: 'abc' },
      ],
    })
    render(
      <MemoryRouter initialEntries={['/app/caixas/6']}>
        <Routes><Route path="/app/caixas/:id" element={<CaixaDetailPage />} /></Routes>
      </MemoryRouter>,
    )
    await screen.findByText('Caixa #6')
    expect(screen.queryByRole('button', { name: /avançar caixa/i })).toBeNull()
  })

  it('Expedicao ve botao Avançar em fase 4, Laboratorio não', async () => {
    // Caixa em fase 4 (Expedição é responsável)
    obter.mockResolvedValue({
      id: 4, data: '2026-07-16', obs: null, total_os: 1, clientes: ['ACME'],
      fase: 4,
      ordens: [
        { id: 10, cliente: 1, cliente_nome: 'ACME', equipamento_descricao: 'Bafômetro', equipamento_serie: 'S1', fase: 4, fase_descricao: 'Recebido', fase_cor: 'abc' },
      ],
    })

    // Teste 1: Expedição pode ver "Avançar caixa" em fase 4
    mockUser = { funcao: 'Expedição' }
    const { unmount: unmount1 } = render(
      <MemoryRouter initialEntries={['/app/caixas/4']}>
        <Routes><Route path="/app/caixas/:id" element={<CaixaDetailPage />} /></Routes>
      </MemoryRouter>,
    )
    await screen.findByText('Caixa #4')
    expect(screen.queryByRole('button', { name: /avançar caixa/i })).not.toBeNull()
    unmount1()

    // Teste 2: Laboratório NÃO pode ver "Avançar caixa" em fase 4
    mockUser = { funcao: 'Laboratório' }
    obter.mockResolvedValue({
      id: 4, data: '2026-07-16', obs: null, total_os: 1, clientes: ['ACME'],
      fase: 4,
      ordens: [
        { id: 10, cliente: 1, cliente_nome: 'ACME', equipamento_descricao: 'Bafômetro', equipamento_serie: 'S1', fase: 4, fase_descricao: 'Recebido', fase_cor: 'abc' },
      ],
    })
    render(
      <MemoryRouter initialEntries={['/app/caixas/4']}>
        <Routes><Route path="/app/caixas/:id" element={<CaixaDetailPage />} /></Routes>
      </MemoryRouter>,
    )
    await screen.findByText('Caixa #4')
    expect(screen.queryByRole('button', { name: /avançar caixa/i })).toBeNull()
  })

  it('Financeiro ve botao Avançar em fase 10, Laboratorio não', async () => {
    // Caixa em fase 10 (Financeiro é responsável)
    obter.mockResolvedValue({
      id: 10, data: '2026-07-16', obs: null, total_os: 1, clientes: ['ACME'],
      fase: 10,
      ordens: [
        { id: 10, cliente: 1, cliente_nome: 'ACME', equipamento_descricao: 'Bafômetro', equipamento_serie: 'S1', fase: 10, fase_descricao: 'Financeiro', fase_cor: 'abc' },
      ],
    })

    // Teste 1: Financeiro pode ver "Avançar caixa" em fase 10
    mockUser = { funcao: 'Financeiro' }
    const { unmount: unmount1 } = render(
      <MemoryRouter initialEntries={['/app/caixas/10']}>
        <Routes><Route path="/app/caixas/:id" element={<CaixaDetailPage />} /></Routes>
      </MemoryRouter>,
    )
    await screen.findByText('Caixa #10')
    expect(screen.queryByRole('button', { name: /avançar caixa/i })).not.toBeNull()
    unmount1()

    // Teste 2: Laboratório NÃO pode ver "Avançar caixa" em fase 10
    mockUser = { funcao: 'Laboratório' }
    obter.mockResolvedValue({
      id: 10, data: '2026-07-16', obs: null, total_os: 1, clientes: ['ACME'],
      fase: 10,
      ordens: [
        { id: 10, cliente: 1, cliente_nome: 'ACME', equipamento_descricao: 'Bafômetro', equipamento_serie: 'S1', fase: 10, fase_descricao: 'Financeiro', fase_cor: 'abc' },
      ],
    })
    render(
      <MemoryRouter initialEntries={['/app/caixas/10']}>
        <Routes><Route path="/app/caixas/:id" element={<CaixaDetailPage />} /></Routes>
      </MemoryRouter>,
    )
    await screen.findByText('Caixa #10')
    expect(screen.queryByRole('button', { name: /avançar caixa/i })).toBeNull()
  })

  it('Laboratorio ve botao "Sem conserto", Expedicao não', async () => {
    // Caixa em fase 5 com OS em desfecho_lab: 'pendente'
    obter.mockResolvedValue({
      id: 5, data: '2026-07-16', obs: null, total_os: 1, clientes: ['ACME'],
      fase: 5,
      ordens: [
        { id: 10, cliente: 1, cliente_nome: 'ACME', equipamento_descricao: 'Bafômetro', equipamento_serie: 'S1', fase: 5, fase_descricao: 'Laboratório', fase_cor: 'abc', desfecho_lab: 'pendente' },
      ],
    })

    // Teste 1: Laboratório pode ver botão "Sem conserto"
    mockUser = { funcao: 'Laboratório' }
    const { unmount: unmount1 } = render(
      <MemoryRouter initialEntries={['/app/caixas/5']}>
        <Routes><Route path="/app/caixas/:id" element={<CaixaDetailPage />} /></Routes>
      </MemoryRouter>,
    )
    await screen.findByText('Caixa #5')
    expect(screen.queryByRole('button', { name: 'Sem conserto' })).not.toBeNull()
    unmount1()

    // Teste 2: Expedição NÃO pode ver botão "Sem conserto"
    mockUser = { funcao: 'Expedição' }
    obter.mockResolvedValue({
      id: 5, data: '2026-07-16', obs: null, total_os: 1, clientes: ['ACME'],
      fase: 5,
      ordens: [
        { id: 10, cliente: 1, cliente_nome: 'ACME', equipamento_descricao: 'Bafômetro', equipamento_serie: 'S1', fase: 5, fase_descricao: 'Laboratório', fase_cor: 'abc', desfecho_lab: 'pendente' },
      ],
    })
    render(
      <MemoryRouter initialEntries={['/app/caixas/5']}>
        <Routes><Route path="/app/caixas/:id" element={<CaixaDetailPage />} /></Routes>
      </MemoryRouter>,
    )
    await screen.findByText('Caixa #5')
    expect(screen.queryByRole('button', { name: 'Sem conserto' })).toBeNull()
  })
})
