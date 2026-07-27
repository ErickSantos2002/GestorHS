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
  it('listar monta query string com q', async () => {
    await caixasApi.listar({ q: 'votor', offset: 25, limit: 25 })
    expect(apiJson).toHaveBeenCalledWith('/caixas?q=votor&offset=25&limit=25')
  })

  it('criar manda POST com obs', async () => {
    await caixasApi.criar({ obs: 'lote' })
    expect(apiJson).toHaveBeenCalledWith('/caixas', { method: 'POST', body: JSON.stringify({ obs: 'lote' }) })
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

  it('quadro busca /caixas/quadro sem query quando sem cliente', async () => {
    await caixasApi.quadro()
    expect(apiJson).toHaveBeenCalledWith('/caixas/quadro')
  })

  it('quadro monta query com cliente', async () => {
    await caixasApi.quadro({ cliente: 5 })
    expect(apiJson).toHaveBeenCalledWith('/caixas/quadro?cliente=5')
  })

  it('avancar posta em /caixas/:id/avancar', async () => {
    await caixasApi.avancar(7, { cod_retorno: null, obs: null })
    expect(apiJson).toHaveBeenCalledWith('/caixas/7/avancar', { method: 'POST', body: JSON.stringify({ cod_retorno: null, obs: null }) })
  })

  it('cancelar posta motivo em /caixas/:id/cancelar', async () => {
    await caixasApi.cancelar(7, { motivo: 'erro' })
    expect(apiJson).toHaveBeenCalledWith('/caixas/7/cancelar', { method: 'POST', body: JSON.stringify({ motivo: 'erro' }) })
  })

  it('desfechoLab posta em /ordens/:id/desfecho-lab', async () => {
    await caixasApi.desfechoLab(9, { desfecho: 'concluido', obs: null })
    expect(apiJson).toHaveBeenCalledWith('/ordens/9/desfecho-lab', { method: 'POST', body: JSON.stringify({ desfecho: 'concluido', obs: null }) })
  })

  it('avancar envia cliente_principal', async () => {
    await caixasApi.avancar(7, { cliente_principal: 3, obs: null, cod_retorno: null })
    expect(apiJson).toHaveBeenCalledWith('/caixas/7/avancar', { method: 'POST', body: JSON.stringify({ cliente_principal: 3, obs: null, cod_retorno: null }) })
  })
})
