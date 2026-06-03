import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ordensApi } from './api'
import { setTokens } from '../../lib/auth-storage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('ordens/api', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    setTokens({ access_token: 't', refresh_token: 'r' })
  })

  it('listar monta a query string (fase/cliente/tipo/q/offset/limit)', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ items: [], total: 0 }))
    vi.stubGlobal('fetch', f)
    await ordensApi.listar({ fase: 5, cliente: 12, tipo: 'C', q: 'abc', offset: 25, limit: 25 })
    const url = String(f.mock.calls[0][0])
    expect(url).toContain('/ordens?')
    expect(url).toContain('fase=5')
    expect(url).toContain('cliente=12')
    expect(url).toContain('tipo=C')
    expect(url).toContain('q=abc')
    expect(url).toContain('offset=25')
  })

  it('listar omite chaves ausentes mas sempre manda offset/limit', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ items: [], total: 0 }))
    vi.stubGlobal('fetch', f)
    await ordensApi.listar({})
    const url = String(f.mock.calls[0][0])
    expect(url).not.toContain('fase=')
    expect(url).not.toContain('cliente=')
    expect(url).toContain('offset=0')
    expect(url).toContain('limit=25')
  })

  it('quadro bate em /ordens/quadro (com e sem cliente)', async () => {
    const f = vi.fn()
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse([]))
    vi.stubGlobal('fetch', f)
    await ordensApi.quadro({})
    expect(String(f.mock.calls[0][0])).toContain('/ordens/quadro')
    await ordensApi.quadro({ cliente: 7 })
    expect(String(f.mock.calls[1][0])).toContain('/ordens/quadro?cliente=7')
  })

  it('obter e logs nos paths certos', async () => {
    const f = vi.fn()
      .mockResolvedValueOnce(jsonResponse({}))
      .mockResolvedValueOnce(jsonResponse([]))
    vi.stubGlobal('fetch', f)
    await ordensApi.obter(42)
    expect(String(f.mock.calls[0][0])).toContain('/ordens/42')
    await ordensApi.logs(42)
    expect(String(f.mock.calls[1][0])).toContain('/ordens/42/logs')
  })

  it('propaga ApiError em resposta não-ok', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ detail: 'x' }, 404))
    vi.stubGlobal('fetch', f)
    await expect(ordensApi.obter(99)).rejects.toMatchObject({ status: 404 })
  })
})
