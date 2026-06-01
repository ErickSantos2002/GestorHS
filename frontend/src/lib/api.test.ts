import { describe, it, expect, beforeEach, vi } from 'vitest'
import { apiFetch, apiJson, setOnUnauthorized } from './api'
import { setTokens, getTokens } from './auth-storage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('api', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    setOnUnauthorized(null)
  })

  it('injeta o Authorization quando há token', async () => {
    setTokens({ access_token: 'tok', refresh_token: 'r' })
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    await apiFetch('/x')

    const headers = fetchMock.mock.calls[0][1].headers as Headers
    expect(headers.get('Authorization')).toBe('Bearer tok')
  })

  it('não injeta Authorization sem token', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    await apiFetch('/x')

    const headers = fetchMock.mock.calls[0][1].headers as Headers
    expect(headers.has('Authorization')).toBe(false)
  })

  it('no 401 faz refresh e repete a request com o novo token', async () => {
    setTokens({ access_token: 'velho', refresh_token: 'r' })
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ detail: 'expirado' }, 401)) // /x
      .mockResolvedValueOnce(jsonResponse({ access_token: 'novo', refresh_token: 'r2' })) // /auth/refresh
      .mockResolvedValueOnce(jsonResponse({ ok: true })) // /x repetido
    vi.stubGlobal('fetch', fetchMock)

    const res = await apiFetch('/x')

    expect(res.status).toBe(200)
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(fetchMock.mock.calls[1][0]).toContain('/auth/refresh')
    const retryHeaders = fetchMock.mock.calls[2][1].headers as Headers
    expect(retryHeaders.get('Authorization')).toBe('Bearer novo')
    expect(getTokens()?.access_token).toBe('novo')
  })

  it('faz um único refresh para requests concorrentes (single-flight)', async () => {
    setTokens({ access_token: 'velho', refresh_token: 'r' })
    const fetchMock = vi.fn((url: string) => {
      if (url.includes('/auth/refresh')) {
        return Promise.resolve(jsonResponse({ access_token: 'novo', refresh_token: 'r2' }))
      }
      const tokenAtual = getTokens()?.access_token
      return Promise.resolve(
        tokenAtual === 'novo' ? jsonResponse({ ok: true }) : jsonResponse({ detail: 'expirado' }, 401),
      )
    })
    vi.stubGlobal('fetch', fetchMock as unknown as typeof fetch)

    await Promise.all([apiFetch('/a'), apiFetch('/b')])

    const refreshCalls = fetchMock.mock.calls.filter((c) => String(c[0]).includes('/auth/refresh'))
    expect(refreshCalls.length).toBe(1)
  })

  it('refresh falho limpa tokens e chama onUnauthorized', async () => {
    setTokens({ access_token: 'velho', refresh_token: 'r' })
    const onUnauth = vi.fn()
    setOnUnauthorized(onUnauth)
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ detail: 'expirado' }, 401))
      .mockResolvedValueOnce(jsonResponse({ detail: 'invalido' }, 401)) // /auth/refresh falha
    vi.stubGlobal('fetch', fetchMock)

    const res = await apiFetch('/x')

    expect(res.status).toBe(401)
    expect(getTokens()).toBeNull()
    expect(onUnauth).toHaveBeenCalledTimes(1)
  })

  it('apiJson lança ApiError com o detail no erro', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ detail: 'Credenciais inválidas' }, 401))
    vi.stubGlobal('fetch', fetchMock)

    await expect(apiJson('/auth/login', { method: 'POST', body: '{}' })).rejects.toMatchObject({
      status: 401,
      message: 'Credenciais inválidas',
    })
  })
})
