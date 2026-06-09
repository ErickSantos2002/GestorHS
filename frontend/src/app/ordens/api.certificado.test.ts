import { describe, it, expect, vi, beforeEach } from 'vitest'
const { apiJson } = vi.hoisted(() => ({ apiJson: vi.fn() }))
vi.mock('../../lib/api', () => ({ apiJson: (...a: unknown[]) => apiJson(...a), apiFetch: vi.fn(), ApiError: class extends Error {} }))
import { ordensApi } from './api'
beforeEach(() => { apiJson.mockReset(); apiJson.mockResolvedValue([]) })
describe('ordensApi certificados', () => {
  it('lista', async () => { await ordensApi.certificados(5); expect(apiJson).toHaveBeenCalledWith('/ordens/5/certificados') })
  it('gera', async () => { await ordensApi.gerarCertificado(5); expect(apiJson).toHaveBeenCalledWith('/ordens/5/gerar-certificado', { method: 'POST' }) })
  it('gerarCertificado com dados de calibração', async () => {
    await ordensApi.gerarCertificado(5, { calib_cert: 'C-1', calib_temp: '25' })
    expect(apiJson).toHaveBeenCalledWith('/ordens/5/gerar-certificado', { method: 'POST', body: JSON.stringify({ calib_cert: 'C-1', calib_temp: '25' }) })
  })
  it('gerarCertificado sem dados (regerar)', async () => {
    await ordensApi.gerarCertificado(5)
    expect(apiJson).toHaveBeenCalledWith('/ordens/5/gerar-certificado', { method: 'POST' })
  })
})
