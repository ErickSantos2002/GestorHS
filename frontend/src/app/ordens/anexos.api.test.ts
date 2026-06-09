import { describe, it, expect, beforeEach, vi } from 'vitest'
import { fotosApi } from './api'
import { setTokens } from '../../lib/auth-storage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('app/ordens anexos api', () => {
  beforeEach(() => { localStorage.clear(); vi.restoreAllMocks(); setTokens({ access_token: 't', refresh_token: 'r' }) })

  it('fotosApi.listar faz GET /ordens/:id/fotos', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse([]))
    vi.stubGlobal('fetch', f)
    await fotosApi.listar(7)
    expect(String(f.mock.calls[0][0])).toContain('/ordens/7/fotos')
  })

  it('fotosApi.enviar faz POST multipart sem Content-Type manual', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ id: 1, os: 7, arquivo: 'a.jpg', legenda: null, url: '/x' }, 201))
    vi.stubGlobal('fetch', f)
    await fotosApi.enviar(7, new File([new Uint8Array([1])], 'a.jpg', { type: 'image/jpeg' }), 'frente')
    const init = f.mock.calls[0][1]
    expect(init.method).toBe('POST')
    expect(init.body).toBeInstanceOf(FormData)
    const headers = new Headers(init.headers)
    expect(headers.get('Content-Type')).toBeNull()
  })
})
