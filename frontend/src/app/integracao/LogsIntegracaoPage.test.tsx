import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { LogsIntegracaoPage } from './LogsIntegracaoPage'
import { logsIntegracaoApi, podeReenviar, type LogIntegracao } from './api'

const base: LogIntegracao = {
  id: 1, criado_em: '2026-07-21T10:00:00Z', integracao: 'growthhs', tipo: 'os_card',
  external_id: '10853', referencia_os: 10853, referencia_tipo: 'os', status: 'erro',
  motivo: null, http_status: 422, resposta: 'ruim', payload: { source: 'gestorhs.os' },
}

describe('podeReenviar', () => {
  it('so quando ha payload e nao foi sucesso', () => {
    expect(podeReenviar(base)).toBe(true)
    expect(podeReenviar({ ...base, status: 'sucesso' })).toBe(false)
    expect(podeReenviar({ ...base, payload: null })).toBe(false)
  })
})

describe('LogsIntegracaoPage', () => {
  beforeEach(() => {
    vi.spyOn(logsIntegracaoApi, 'listar').mockResolvedValue({
      items: [base], total: 1, estado: { taskhs_ativo: true, growthhs_ativo: false },
    })
  })

  it('mostra a linha, o estado desligado e o botao reenviar', async () => {
    render(<MemoryRouter><LogsIntegracaoPage /></MemoryRouter>)
    expect(await screen.findByText('OS #10853')).toBeInTheDocument()
    expect(screen.getByText(/GrowthHS: desligado/i)).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: /reenviar/i })).toBeInTheDocument()
  })

  it('referencia de OS linka para a OS', async () => {
    render(<MemoryRouter><LogsIntegracaoPage /></MemoryRouter>)
    const link = await screen.findByRole('link', { name: 'OS #10853' })
    expect(link).toHaveAttribute('href', '/app/ordens/10853')
  })

  it('referencia de caixa linka para a caixa, nao para a OS de mesmo numero', async () => {
    vi.spyOn(logsIntegracaoApi, 'listar').mockResolvedValue({
      items: [{ ...base, referencia_os: 916, referencia_tipo: 'caixa' }],
      total: 1, estado: { taskhs_ativo: true, growthhs_ativo: false },
    })
    render(<MemoryRouter><LogsIntegracaoPage /></MemoryRouter>)
    const link = await screen.findByRole('link', { name: 'CX 916' })
    expect(link).toHaveAttribute('href', '/app/caixas/916')
  })
})
