import { describe, it, expect, vi, beforeEach } from 'vitest'

const { apiJson, apiFetch } = vi.hoisted(() => ({ apiJson: vi.fn(), apiFetch: vi.fn() }))
vi.mock('../../lib/api', () => {
  class ApiError extends Error {
    status: number
    constructor(status: number, message: string) { super(message); this.status = status }
  }
  return {
    apiJson: (...a: unknown[]) => apiJson(...a),
    apiFetch: (...a: unknown[]) => apiFetch(...a),
    ApiError,
  }
})

import { caixasApi } from './api'

beforeEach(() => {
  apiJson.mockReset(); apiJson.mockResolvedValue({})
  apiFetch.mockReset(); apiFetch.mockResolvedValue({ ok: true })
})

describe('caixasApi', () => {
  it('listar monta query string com status e q', async () => {
    await caixasApi.listar({ status: 'P', q: 'votor', offset: 25, limit: 25 })
    expect(apiJson).toHaveBeenCalledWith('/caixas?status=P&q=votor&offset=25&limit=25')
  })

  it('criar manda POST com obs', async () => {
    await caixasApi.criar({ obs: 'lote' })
    expect(apiJson).toHaveBeenCalledWith('/caixas', { method: 'POST', body: JSON.stringify({ obs: 'lote' }) })
  })

  it('abrir e finalizar usam POST nas rotas certas', async () => {
    await caixasApi.abrir(3)
    expect(apiJson).toHaveBeenCalledWith('/caixas/3/abrir', { method: 'POST' })
    await caixasApi.finalizar(3)
    expect(apiJson).toHaveBeenCalledWith('/caixas/3/finalizar', { method: 'POST' })
  })

  it('vincular OS usa apiJson com POST', async () => {
    await caixasApi.vincularOrdem(3, 7)
    expect(apiJson).toHaveBeenCalledWith('/caixas/3/ordens', { method: 'POST', body: JSON.stringify({ ordem_id: 7 }) })
  })

  it('desvincular OS usa apiFetch (204 sem corpo) com DELETE', async () => {
    await caixasApi.desvincularOrdem(3, 7)
    expect(apiFetch).toHaveBeenCalledWith('/caixas/3/ordens/7', expect.objectContaining({ method: 'DELETE' }))
  })

  it('excluir caixa usa apiFetch com DELETE', async () => {
    await caixasApi.excluir(3)
    expect(apiFetch).toHaveBeenCalledWith('/caixas/3', expect.objectContaining({ method: 'DELETE' }))
  })
})
