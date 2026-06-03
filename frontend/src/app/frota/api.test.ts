import { describe, it, expect, beforeEach, vi } from 'vitest'
import { equipamentosClienteApi } from './api'
import { setTokens } from '../../lib/auth-storage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('frota/api', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    setTokens({ access_token: 't', refresh_token: 'r' })
  })

  it('listar monta a query string (cliente/status/q/offset/limit)', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ items: [], total: 0 }))
    vi.stubGlobal('fetch', f)
    await equipamentosClienteApi.listar({ cliente: 5, status: 'vencido', q: 'S1', offset: 25, limit: 25 })
    const url = String(f.mock.calls[0][0])
    expect(url).toContain('/equipamentos-cliente?')
    expect(url).toContain('cliente=5')
    expect(url).toContain('status=vencido')
    expect(url).toContain('q=S1')
    expect(url).toContain('offset=25')
  })

  it('historico bate no path certo', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse([]))
    vi.stubGlobal('fetch', f)
    await equipamentosClienteApi.historico(7)
    expect(String(f.mock.calls[0][0])).toContain('/equipamentos-cliente/7/historico')
  })

  it('excluir propaga ApiError', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ detail: 'registro em uso' }, 409))
    vi.stubGlobal('fetch', f)
    await expect(equipamentosClienteApi.excluir(9)).rejects.toMatchObject({ status: 409 })
  })
})
