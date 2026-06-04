import { describe, it, expect, beforeEach, vi } from 'vitest'
import { dashboardApi } from './api'
import { ApiError } from '../../lib/api'
import { setTokens } from '../../lib/auth-storage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('app/dashboard/api', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    setTokens({ access_token: 't', refresh_token: 'r' })
  })

  it('resumo faz GET /dashboard', async () => {
    const f = vi.fn().mockResolvedValue(
      jsonResponse({
        aparelhos_vencidos: 3, aparelhos_vencendo: 2, solicitacoes_pendentes: 1,
        clientes_a_cobrar: 2, os_por_fase: [],
      }),
    )
    vi.stubGlobal('fetch', f)
    const r = await dashboardApi.resumo()
    expect(String(f.mock.calls[0][0])).toContain('/dashboard')
    expect(r.aparelhos_vencidos).toBe(3)
  })

  it('resumo propaga ApiError', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ detail: 'erro' }, 500))
    vi.stubGlobal('fetch', f)
    await expect(dashboardApi.resumo()).rejects.toBeInstanceOf(ApiError)
  })
})
