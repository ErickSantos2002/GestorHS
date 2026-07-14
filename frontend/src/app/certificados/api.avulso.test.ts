import { describe, it, expect, vi, beforeEach } from 'vitest'
import { certificadosApi } from './api'

function okJson(body: unknown) {
  return { ok: true, status: 200, json: async () => body, headers: new Headers() } as unknown as Response
}

describe('certificados avulsos', () => {
  beforeEach(() => {
    localStorage.setItem('gestorhs.tokens', JSON.stringify({ access_token: 'a', refresh_token: 'r' }))
  })

  it('gera o avulso enviando o template e os campos', async () => {
    const fetchMock = vi.fn().mockResolvedValue(okJson({ id: 1, tipo: 'C' }))
    vi.stubGlobal('fetch', fetchMock)
    await certificadosApi.gerarAvulso({ equipamento: 5, tipo: 'C', nomecli: 'POC', os: 'XXXX' })
    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toContain('/certificados-avulsos')
    expect((init as RequestInit).method).toBe('POST')
    expect(JSON.parse((init as RequestInit).body as string)).toMatchObject({ equipamento: 5, tipo: 'C', os: 'XXXX' })
  })

  it('lista os avulsos', async () => {
    const fetchMock = vi.fn().mockResolvedValue(okJson([{ id: 2 }]))
    vi.stubGlobal('fetch', fetchMock)
    const r = await certificadosApi.listarAvulsos()
    expect(String(fetchMock.mock.calls[0][0])).toContain('/certificados-avulsos')
    expect(r[0].id).toBe(2)
  })
})
