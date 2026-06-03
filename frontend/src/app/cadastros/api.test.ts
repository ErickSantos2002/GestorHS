import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setoresApi, equipamentosApi } from './api'
import { setTokens } from '../../lib/auth-storage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('cadastros/api (crudClient)', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    setTokens({ access_token: 't', refresh_token: 'r' })
  })

  it('listar faz GET no recurso', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse([{ id: 1, descricao: 'A' }]))
    vi.stubGlobal('fetch', f)
    const r = await setoresApi.listar()
    expect(String(f.mock.calls[0][0])).toContain('/setores')
    expect(r[0].descricao).toBe('A')
  })

  it('criar faz POST com corpo', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ id: 2, descricao: 'Novo' }))
    vi.stubGlobal('fetch', f)
    await setoresApi.criar({ descricao: 'Novo' })
    expect(f.mock.calls[0][1].method).toBe('POST')
    expect(String(f.mock.calls[0][1].body)).toContain('Novo')
  })

  it('excluir resolve no 204 e propaga 409', async () => {
    const ok = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', ok)
    await expect(equipamentosApi.excluir(5)).resolves.toBeUndefined()
    expect(ok.mock.calls[0][1].method).toBe('DELETE')

    const fail = vi.fn().mockResolvedValue(jsonResponse({ detail: 'registro em uso' }, 409))
    vi.stubGlobal('fetch', fail)
    await expect(equipamentosApi.excluir(5)).rejects.toMatchObject({ status: 409 })
  })
})
