import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ordensApi } from './api'

function okJson(body: unknown) {
  return { ok: true, status: 200, json: async () => body, headers: new Headers() } as unknown as Response
}

describe('enviarNotaFiscal', () => {
  beforeEach(() => {
    localStorage.setItem('gestorhs.tokens', JSON.stringify({ access_token: 'a', refresh_token: 'r' }))
  })

  it('envia multipart com o PAR de arquivos e o numero', async () => {
    const fetchMock = vi.fn().mockResolvedValue(okJson({ nota_fiscal: 'x.pdf', nota_fiscal_xml: 'x.xml', nota_fiscal_numero: '123' }))
    vi.stubGlobal('fetch', fetchMock)
    const pdf = new File([new Uint8Array([1])], 'nf.pdf', { type: 'application/pdf' })
    const xml = new File([new Uint8Array([2])], 'nf.xml', { type: 'application/xml' })
    await ordensApi.enviarNotaFiscal(7, pdf, xml, '123')
    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toContain('/ordens/7/nota-fiscal')
    expect((init as RequestInit).method).toBe('POST')
    const body = (init as RequestInit).body as FormData
    expect(body.get('numero')).toBe('123')
    expect(body.get('arquivo_pdf')).toBeInstanceOf(File)
    expect(body.get('arquivo_xml')).toBeInstanceOf(File)
  })
})

describe('baixarNotaFiscal', () => {
  beforeEach(() => {
    localStorage.setItem('gestorhs.tokens', JSON.stringify({ access_token: 'a', refresh_token: 'r' }))
  })

  it('busca o XML numa rota propria, sem mexer na do PDF', async () => {
    const resp = { ok: true, status: 200, blob: async () => new Blob(['<x/>']), headers: new Headers() } as unknown as Response
    const fetchMock = vi.fn().mockResolvedValue(resp)
    vi.stubGlobal('fetch', fetchMock)
    vi.stubGlobal('URL', { ...URL, createObjectURL: () => 'blob:x', revokeObjectURL: () => {} })

    await ordensApi.baixarNotaFiscal(7, 'nf.pdf')
    expect(String(fetchMock.mock.calls[0][0])).toContain('/ordens/7/nota-fiscal')
    expect(String(fetchMock.mock.calls[0][0])).not.toContain('/xml')

    await ordensApi.baixarNotaFiscal(7, 'nf.xml', 'xml')
    expect(String(fetchMock.mock.calls[1][0])).toContain('/ordens/7/nota-fiscal/xml')
  })
})
