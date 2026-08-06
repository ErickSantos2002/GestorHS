import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
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

function tela() {
  return render(<MemoryRouter><OrdensPage /></MemoryRouter>)
}

/** Último argumento com que a listagem foi chamada. */
function ultimaChamada() {
  return vi.mocked(listar).mock.calls.at(-1)![0]
}

describe('filtro de data de chegada', () => {
  beforeEach(() => {
    vi.mocked(listar).mockReset().mockResolvedValue({ items: [], total: 0 })
    vi.mocked(quadro).mockResolvedValue([])
    // 04/08/2026 — data fixa para os períodos serem determinísticos.
    // Só o Date é fingido: fingir TODOS os timers congela o que o waitFor usa.
    vi.useFakeTimers({ toFake: ['Date'] }).setSystemTime(new Date(2026, 7, 4, 10, 0, 0))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('sem período escolhido nao manda faixa de data', async () => {
    tela()
    fireEvent.click(screen.getByRole('button', { name: /lista/i }))
    await waitFor(() => expect(listar).toHaveBeenCalled())
    expect(ultimaChamada().chegadaDe).toBeUndefined()
    expect(ultimaChamada().chegadaAte).toBeUndefined()
  })

  it('"Hoje" manda o mesmo dia nas duas pontas', async () => {
    tela()
    fireEvent.click(screen.getByRole('button', { name: /lista/i }))
    await waitFor(() => expect(listar).toHaveBeenCalled())

    fireEvent.change(screen.getByLabelText(/chegada/i), { target: { value: 'hoje' } })
    await waitFor(() => expect(ultimaChamada().chegadaDe).toBe('2026-08-04'))
    expect(ultimaChamada().chegadaAte).toBe('2026-08-04')
  })

  it('"Últimos 7 dias" inclui hoje na contagem', async () => {
    tela()
    fireEvent.click(screen.getByRole('button', { name: /lista/i }))
    await waitFor(() => expect(listar).toHaveBeenCalled())

    fireEvent.change(screen.getByLabelText(/chegada/i), { target: { value: '7' } })
    // 7 dias contando hoje: 29/07 a 04/08, nao 28/07
    await waitFor(() => expect(ultimaChamada().chegadaDe).toBe('2026-07-29'))
    expect(ultimaChamada().chegadaAte).toBe('2026-08-04')
  })

  it('"Mês passado" vai do dia 1 ao último dia do mês anterior', async () => {
    tela()
    fireEvent.click(screen.getByRole('button', { name: /lista/i }))
    await waitFor(() => expect(listar).toHaveBeenCalled())

    fireEvent.change(screen.getByLabelText(/chegada/i), { target: { value: 'mes-1' } })
    await waitFor(() => expect(ultimaChamada().chegadaDe).toBe('2026-07-01'))
    expect(ultimaChamada().chegadaAte).toBe('2026-07-31')
  })

  it('"Personalizado" revela os dois campos e manda o que foi digitado', async () => {
    tela()
    fireEvent.click(screen.getByRole('button', { name: /lista/i }))
    await waitFor(() => expect(listar).toHaveBeenCalled())

    expect(screen.queryByLabelText(/^de$/i)).not.toBeInTheDocument()
    fireEvent.change(screen.getByLabelText(/chegada/i), { target: { value: 'custom' } })

    fireEvent.change(screen.getByLabelText(/^de$/i), { target: { value: '2026-01-10' } })
    fireEvent.change(screen.getByLabelText(/^at.$/i), { target: { value: '2026-02-20' } })
    await waitFor(() => expect(ultimaChamada().chegadaDe).toBe('2026-01-10'))
    expect(ultimaChamada().chegadaAte).toBe('2026-02-20')
  })

  it('trocar o periodo volta para a primeira pagina', async () => {
    tela()
    fireEvent.click(screen.getByRole('button', { name: /lista/i }))
    await waitFor(() => expect(listar).toHaveBeenCalled())

    fireEvent.change(screen.getByLabelText(/chegada/i), { target: { value: '30' } })
    await waitFor(() => expect(ultimaChamada().chegadaDe).toBe('2026-07-06'))
    expect(ultimaChamada().offset).toBe(0)
  })
})
