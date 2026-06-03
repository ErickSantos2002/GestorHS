import { describe, it, expect, beforeEach, vi } from 'vitest'
import { alertasApi } from './api'
import { setTokens } from '../../lib/auth-storage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('alertas/api', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    setTokens({ access_token: 't', refresh_token: 'r' })
  })

  it('listar monta a query (q/ocultar_recentes/offset/limit)', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ items: [], total: 0 }))
    vi.stubGlobal('fetch', f)
    await alertasApi.listar({ q: 'beta', ocultar_recentes: true, offset: 25, limit: 25 })
    const url = String(f.mock.calls[0][0])
    expect(url).toContain('/alertas?')
    expect(url).toContain('q=beta')
    expect(url).toContain('ocultar_recentes=true')
    expect(url).toContain('offset=25')
  })

  it('listar omite ocultar_recentes quando false', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ items: [], total: 0 }))
    vi.stubGlobal('fetch', f)
    await alertasApi.listar({})
    expect(String(f.mock.calls[0][0])).not.toContain('ocultar_recentes')
  })

  it('registrarContato faz POST /alertas/{id}/contato', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ cliente: 5, atualizados: 2, ult_contato: null }))
    vi.stubGlobal('fetch', f)
    await alertasApi.registrarContato(5)
    expect(String(f.mock.calls[0][0])).toContain('/alertas/5/contato')
    expect(f.mock.calls[0][1]).toMatchObject({ method: 'POST' })
  })

  it('propaga ApiError', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ detail: 'x' }, 403))
    vi.stubGlobal('fetch', f)
    await expect(alertasApi.registrarContato(5)).rejects.toMatchObject({ status: 403 })
  })
})
