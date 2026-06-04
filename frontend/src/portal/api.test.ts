import { describe, it, expect, beforeEach, vi } from 'vitest'
import { portalApi } from './api'
import { setTokens } from '../lib/auth-storage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('portal/api', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    setTokens({ access_token: 't', refresh_token: 'r' })
  })

  it('me bate em /portal/me', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ id: 1, login: 'x', cliente: 5 }))
    vi.stubGlobal('fetch', f)
    await portalApi.me()
    expect(String(f.mock.calls[0][0])).toContain('/portal/me')
  })

  it('resumo bate em /portal/resumo', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ aparelhos: 0, vencidos: 0, os_andamento: 0 }))
    vi.stubGlobal('fetch', f)
    await portalApi.resumo()
    expect(String(f.mock.calls[0][0])).toContain('/portal/resumo')
  })

  it('propaga ApiError', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ detail: 'x' }, 401))
    vi.stubGlobal('fetch', f)
    await expect(portalApi.me()).rejects.toMatchObject({ status: 401 })
  })

  it('minhaFrota monta a query (status/q/offset/limit)', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ items: [], total: 0 }))
    vi.stubGlobal('fetch', f)
    await portalApi.minhaFrota({ status: 'vencido', q: 'S1', offset: 25, limit: 25 })
    const url = String(f.mock.calls[0][0])
    expect(url).toContain('/portal/minha-frota?')
    expect(url).toContain('status=vencido')
    expect(url).toContain('q=S1')
  })

  it('certificados bate em /portal/certificados', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ items: [], total: 0 }))
    vi.stubGlobal('fetch', f)
    await portalApi.certificados({})
    expect(String(f.mock.calls[0][0])).toContain('/portal/certificados')
  })

  it('minhasOs inclui em_andamento só quando true', async () => {
    const f = vi.fn().mockImplementation(() => Promise.resolve(jsonResponse({ items: [], total: 0 })))
    vi.stubGlobal('fetch', f)
    await portalApi.minhasOs({ em_andamento: true })
    expect(String(f.mock.calls[0][0])).toContain('em_andamento=true')
    await portalApi.minhasOs({})
    expect(String(f.mock.calls[1][0])).not.toContain('em_andamento')
  })
})
