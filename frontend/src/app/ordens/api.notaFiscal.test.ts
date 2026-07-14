import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ordensApi } from './api'

function okJson(body: unknown) {
  return { ok: true, status: 200, json: async () => body, headers: new Headers() } as unknown as Response
}

describe('enviarNotaFiscal', () => {
  beforeEach(() => {
    localStorage.setItem('gestorhs.tokens', JSON.stringify({ access_token: 'a', refresh_token: 'r' }))
  })

  it('envia multipart com o arquivo e o numero', async () => {
    const fetchMock = vi.fn().mockResolvedValue(okJson({ nota_fiscal: 'x.pdf', nota_fiscal_numero: '123' }))
    vi.stubGlobal('fetch', fetchMock)
    const file = new File([new Uint8Array([1])], 'nf.pdf', { type: 'application/pdf' })
    await ordensApi.enviarNotaFiscal(7, file, '123')
    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toContain('/ordens/7/nota-fiscal')
    expect((init as RequestInit).method).toBe('POST')
    const body = (init as RequestInit).body as FormData
    expect(body.get('numero')).toBe('123')
    expect(body.get('file')).toBeInstanceOf(File)
  })
})
