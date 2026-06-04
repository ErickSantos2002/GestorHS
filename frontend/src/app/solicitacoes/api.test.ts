import { describe, it, expect, beforeEach, vi } from 'vitest'
import { solicitacoesApi } from './api'
import { setTokens } from '../../lib/auth-storage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('app/solicitacoes/api', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    setTokens({ access_token: 't', refresh_token: 'r' })
  })

  it('listar monta a query (status/offset/limit)', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ items: [], total: 0 }))
    vi.stubGlobal('fetch', f)
    await solicitacoesApi.listar({ status: 'pendente', offset: 25, limit: 25 })
    const url = String(f.mock.calls[0][0])
    expect(url).toContain('/solicitacoes?')
    expect(url).toContain('status=pendente')
  })

  it('atender faz POST /solicitacoes/{id}/atender', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ id: 1, status: 'atendida' }))
    vi.stubGlobal('fetch', f)
    await solicitacoesApi.atender(1)
    expect(String(f.mock.calls[0][0])).toContain('/solicitacoes/1/atender')
    expect(f.mock.calls[0][1]).toMatchObject({ method: 'POST' })
  })
})
