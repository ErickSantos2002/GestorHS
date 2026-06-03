import { describe, it, expect, beforeEach, vi } from 'vitest'
import { clientesApi, funcionariosApi } from './api'
import { setTokens } from '../../lib/auth-storage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('clientes/api', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    setTokens({ access_token: 't', refresh_token: 'r' })
  })

  it('listar monta a query string (q/offset/limit)', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ items: [], total: 0 }))
    vi.stubGlobal('fetch', f)
    await clientesApi.listar({ q: 'acme', offset: 25, limit: 25 })
    const url = String(f.mock.calls[0][0])
    expect(url).toContain('/clientes?')
    expect(url).toContain('q=acme')
    expect(url).toContain('offset=25')
    expect(url).toContain('limit=25')
  })

  it('criar faz POST com corpo', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ id: 1, nome: 'ACME', ativo: true }))
    vi.stubGlobal('fetch', f)
    await clientesApi.criar({ nome: 'ACME' } as never)
    expect(f.mock.calls[0][1].method).toBe('POST')
    expect(String(f.mock.calls[0][1].body)).toContain('ACME')
  })

  it('funcionariosApi.criar posta no path do cliente', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ id: 9, cliente: 3, ativo: true }))
    vi.stubGlobal('fetch', f)
    await funcionariosApi.criar(3, { nome: 'Maria' } as never)
    expect(String(f.mock.calls[0][0])).toContain('/clientes/3/funcionarios')
    expect(f.mock.calls[0][1].method).toBe('POST')
  })

  it('excluir propaga ApiError', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ detail: 'registro em uso' }, 409))
    vi.stubGlobal('fetch', f)
    await expect(clientesApi.excluir(5)).rejects.toMatchObject({ status: 409 })
  })
})
