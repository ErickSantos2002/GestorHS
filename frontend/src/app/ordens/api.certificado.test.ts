import { describe, it, expect, vi, beforeEach } from 'vitest'
const { apiJson } = vi.hoisted(() => ({ apiJson: vi.fn() }))
vi.mock('../../lib/api', () => ({ apiJson: (...a: unknown[]) => apiJson(...a), apiFetch: vi.fn(), ApiError: class extends Error {} }))
import { ordensApi } from './api'
beforeEach(() => { apiJson.mockReset(); apiJson.mockResolvedValue([]) })
describe('ordensApi certificados', () => {
  it('lista', async () => { await ordensApi.certificados(5); expect(apiJson).toHaveBeenCalledWith('/ordens/5/certificados') })
  it('gera', async () => { await ordensApi.gerarCertificado(5); expect(apiJson).toHaveBeenCalledWith('/ordens/5/gerar-certificado', { method: 'POST' }) })
})
