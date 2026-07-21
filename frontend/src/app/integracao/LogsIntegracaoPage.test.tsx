import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { LogsIntegracaoPage } from './LogsIntegracaoPage'
import { logsIntegracaoApi, podeReenviar, type LogIntegracao } from './api'

const base: LogIntegracao = {
  id: 1, criado_em: '2026-07-21T10:00:00Z', integracao: 'growthhs', tipo: 'os_card',
  external_id: '10853', referencia_os: 10853, status: 'erro', motivo: null,
  http_status: 422, resposta: 'ruim', payload: { source: 'gestorhs.os' },
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
    expect(await screen.findByText('#10853')).toBeInTheDocument()
    expect(screen.getByText(/GrowthHS: desligado/i)).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: /reenviar/i })).toBeInTheDocument()
  })
})
