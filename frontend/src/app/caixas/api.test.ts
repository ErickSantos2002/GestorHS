import { describe, it, expect, vi, beforeEach } from 'vitest'

const apiJson = vi.fn()
vi.mock('../../lib/api', () => ({ apiJson: (...a: unknown[]) => apiJson(...a) }))

import { caixasApi } from './api'

beforeEach(() => { apiJson.mockReset(); apiJson.mockResolvedValue({}) })

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

  it('vincular e desvincular OS', async () => {
    await caixasApi.vincularOrdem(3, 7)
    expect(apiJson).toHaveBeenCalledWith('/caixas/3/ordens', { method: 'POST', body: JSON.stringify({ ordem_id: 7 }) })
    await caixasApi.desvincularOrdem(3, 7)
    expect(apiJson).toHaveBeenCalledWith('/caixas/3/ordens/7', { method: 'DELETE' })
  })
})
