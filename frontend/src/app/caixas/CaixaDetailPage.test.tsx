import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

vi.mock('../../auth/AuthContext', () => ({ useAuth: () => ({ user: { funcao: 'Administrador' } }) }))

const { obter, avancar, desvincularOrdem } = vi.hoisted(() => ({ obter: vi.fn(), avancar: vi.fn(), desvincularOrdem: vi.fn() }))
vi.mock('./api', async (orig) => {
  const real = await orig<typeof import('./api')>()
  return { ...real, caixasApi: { ...real.caixasApi, obter, desvincularOrdem } }
})
vi.mock('../ordens/api', async (orig) => {
  const real = await orig<typeof import('../ordens/api')>()
  return { ...real, ordensApi: { ...real.ordensApi, avancar } }
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

describe('CaixaDetailPage — fechar OS por seleção', () => {
  beforeEach(() => {
    obter.mockReset(); avancar.mockReset(); desvincularOrdem.mockReset()
    obter.mockResolvedValue({ ...CAIXA }); avancar.mockResolvedValue({}); desvincularOrdem.mockResolvedValue({})
  })

  it('removeu o botão "Vincular OS existente"', async () => {
    tela()
    await screen.findByText('Caixa #3')
    expect(screen.queryByText('Vincular OS existente')).toBeNull()
  })

  it('só a OS em Preparando Retorno tem checkbox; fechar chama avancar com o código', async () => {
    tela()
    await screen.findByText('Caixa #3')
    const checks = screen.getAllByRole('checkbox')
    // 1 no cabeçalho (marcar todas) + 1 na linha elegível (OS #10). A OS #11 (fase 5) não tem.
    const daLinha = checks.filter((c) => (c as HTMLInputElement).dataset.os === '10')
    expect(daLinha).toHaveLength(1)
    fireEvent.click(daLinha[0])

    fireEvent.click(screen.getByText(/Fechar OS selecionadas \(1\)/))
    fireEvent.change(screen.getByLabelText('Código de retorno'), { target: { value: 'BR777' } })
    fireEvent.click(screen.getByRole('button', { name: /Confirmar/ }))

    await waitFor(() => expect(avancar).toHaveBeenCalledWith(10, { cod_retorno: 'BR777', obs: null }))
    expect(avancar).toHaveBeenCalledTimes(1)
  })

  it('recarregar a caixa (sem fechar) limpa a seleção', async () => {
    tela()
    await screen.findByText('Caixa #3')
    const checks = screen.getAllByRole('checkbox')
    const daLinha = checks.filter((c) => (c as HTMLInputElement).dataset.os === '10')
    fireEvent.click(daLinha[0])
    await screen.findByText(/Fechar OS selecionadas \(1\)/)

    // Aciona um reload por outro caminho (remover a OS #11), sem fechar nada.
    const botoesRemover = screen.getAllByRole('button', { name: 'Remover' })
    fireEvent.click(botoesRemover[1])

    await waitFor(() => expect(desvincularOrdem).toHaveBeenCalledWith(3, 11))
    await waitFor(() => expect(screen.getByText(/Fechar OS selecionadas \(0\)/)).toBeInTheDocument())
  })
})

describe('CaixaDetailPage — avançar/cancelar caixa e sem conserto', () => {
  beforeEach(() => {
    obter.mockReset(); avancar.mockReset(); desvincularOrdem.mockReset()
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
