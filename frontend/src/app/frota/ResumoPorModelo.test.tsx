import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

const { resumoPorModelo } = vi.hoisted(() => ({ resumoPorModelo: vi.fn() }))
vi.mock('./api', () => ({ equipamentosClienteApi: { resumoPorModelo } }))

import { ResumoPorModelo } from './ResumoPorModelo'

describe('ResumoPorModelo', () => {
  beforeEach(() => {
    resumoPorModelo.mockReset()
    resumoPorModelo.mockResolvedValue([
      { equipamento: 36, descricao: 'Phoebus', aparelhos: 120, clientes: 45 },
    ])
  })

  it('nasce fechado e só busca ao abrir', async () => {
    render(<MemoryRouter><ResumoPorModelo /></MemoryRouter>)
    expect(resumoPorModelo).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: /por modelo/i }))
    expect(await screen.findByText('Phoebus')).toBeInTheDocument()
    expect(screen.getByText('120')).toBeInTheDocument()
    expect(screen.getByText('45')).toBeInTheDocument()
  })

  it('cada linha leva aos aparelhos e aos clientes daquele modelo', async () => {
    render(<MemoryRouter><ResumoPorModelo /></MemoryRouter>)
    await userEvent.click(screen.getByRole('button', { name: /por modelo/i }))
    await screen.findByText('Phoebus')
    expect(screen.getByRole('link', { name: /ver aparelhos/i })).toHaveAttribute('href', '/app/equipamentos?equipamento=36')
    expect(screen.getByRole('link', { name: /ver clientes/i })).toHaveAttribute('href', '/app/clientes?equipamento=36')
  })

  it('diz o critério da contagem, que difere da lista de aparelhos', async () => {
    render(<MemoryRouter><ResumoPorModelo /></MemoryRouter>)
    await userEvent.click(screen.getByRole('button', { name: /por modelo/i }))
    await screen.findByText('Phoebus')
    expect(screen.getByText('Aparelhos ativos')).toBeInTheDocument()
    expect(screen.getByText(/sem o estoque da HS/i)).toBeInTheDocument()
  })
})
