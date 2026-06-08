import { describe, it, expect, vi, beforeEach } from 'vitest'

const { apiJson, apiFetch } = vi.hoisted(() => ({ apiJson: vi.fn(), apiFetch: vi.fn() }))
vi.mock('../../lib/api', () => {
  class ApiError extends Error {
    status: number
    constructor(status: number, message: string) { super(message); this.status = status }
  }
  return { apiJson: (...a: unknown[]) => apiJson(...a), apiFetch: (...a: unknown[]) => apiFetch(...a), ApiError }
})

import { certificadosApi, CAMPOS_CERTIFICADO } from './api'

beforeEach(() => {
  apiJson.mockReset(); apiJson.mockResolvedValue({})
  apiFetch.mockReset(); apiFetch.mockResolvedValue({ ok: true, json: async () => ({}) })
})

describe('certificadosApi', () => {
  it('listarModelos com q', async () => {
    await certificadosApi.listarModelos({ q: 'mark' })
    expect(apiJson).toHaveBeenCalledWith('/certificados-modelo?q=mark')
  })
  it('obterModelo', async () => {
    await certificadosApi.obterModelo(3)
    expect(apiJson).toHaveBeenCalledWith('/certificados-modelo/3')
  })
  it('salvarModelo manda PUT', async () => {
    await certificadosApi.salvarModelo(3, { descricao: 'd', texto: '<p>x</p>' })
    expect(apiJson).toHaveBeenCalledWith('/certificados-modelo/3', { method: 'PUT', body: JSON.stringify({ descricao: 'd', texto: '<p>x</p>' }) })
  })
  it('excluirImagem usa DELETE via apiFetch', async () => {
    await certificadosApi.excluirImagem(5)
    expect(apiFetch).toHaveBeenCalledWith('/certificado-imagens/5', expect.objectContaining({ method: 'DELETE' }))
  })
  it('tem lista de campos', () => {
    expect(CAMPOS_CERTIFICADO.length).toBeGreaterThan(3)
    expect(CAMPOS_CERTIFICADO.some((c) => c.campo === '[nomecli]')).toBe(true)
  })
})
