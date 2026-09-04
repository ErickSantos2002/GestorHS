import { describe, it, expect, vi, beforeEach } from 'vitest'

const { apiJson, apiFetch } = vi.hoisted(() => ({ apiJson: vi.fn(), apiFetch: vi.fn() }))
vi.mock('../../lib/api', () => {
  class ApiError extends Error {
    status: number
    constructor(status: number, message: string) { super(message); this.status = status }
  }
  return {
    apiJson: (...a: unknown[]) => apiJson(...a),
    apiFetch: (...a: unknown[]) => apiFetch(...a),
    ApiError,
  }
})

import { caixasApi } from './api'

beforeEach(() => {
  apiJson.mockReset(); apiJson.mockResolvedValue({})
  apiFetch.mockReset(); apiFetch.mockResolvedValue({ ok: true })
})

describe('caixasApi', () => {
  it('listar monta query string com q', async () => {
    await caixasApi.listar({ q: 'votor', offset: 25, limit: 25 })
    expect(apiJson).toHaveBeenCalledWith('/caixas?q=votor&offset=25&limit=25')
  })

  it('criar manda POST com obs', async () => {
    await caixasApi.criar({ obs: 'lote' })
    expect(apiJson).toHaveBeenCalledWith('/caixas', { method: 'POST', body: JSON.stringify({ obs: 'lote' }) })
  })

  it('vincular OS usa apiJson com POST', async () => {
    await caixasApi.vincularOrdem(3, 7)
    expect(apiJson).toHaveBeenCalledWith('/caixas/3/ordens', { method: 'POST', body: JSON.stringify({ ordem_id: 7 }) })
  })

  it('desvincular OS usa apiFetch (204 sem corpo) com DELETE', async () => {
    await caixasApi.desvincularOrdem(3, 7)
    expect(apiFetch).toHaveBeenCalledWith('/caixas/3/ordens/7', expect.objectContaining({ method: 'DELETE' }))
  })

  it('excluir caixa usa apiFetch com DELETE', async () => {
    await caixasApi.excluir(3)
    expect(apiFetch).toHaveBeenCalledWith('/caixas/3', expect.objectContaining({ method: 'DELETE' }))
  })

  it('quadro busca /caixas/quadro sem query quando sem cliente', async () => {
    await caixasApi.quadro()
    expect(apiJson).toHaveBeenCalledWith('/caixas/quadro')
  })

  it('quadro monta query com cliente', async () => {
    await caixasApi.quadro({ cliente: 5 })
    expect(apiJson).toHaveBeenCalledWith('/caixas/quadro?cliente=5')
  })

  it('avancar posta em /caixas/:id/avancar', async () => {
    await caixasApi.avancar(7, { cod_retorno: null, obs: null })
    expect(apiJson).toHaveBeenCalledWith('/caixas/7/avancar', { method: 'POST', body: JSON.stringify({ cod_retorno: null, obs: null }) })
  })

  it('cancelar posta motivo em /caixas/:id/cancelar', async () => {
    await caixasApi.cancelar(7, { motivo: 'erro' })
    expect(apiJson).toHaveBeenCalledWith('/caixas/7/cancelar', { method: 'POST', body: JSON.stringify({ motivo: 'erro' }) })
  })

  it('desfechoLab posta em /ordens/:id/desfecho-lab', async () => {
    await caixasApi.desfechoLab(9, { desfecho: 'concluido', obs: null })
    expect(apiJson).toHaveBeenCalledWith('/ordens/9/desfecho-lab', { method: 'POST', body: JSON.stringify({ desfecho: 'concluido', obs: null }) })
  })

  // A costura frontend<->backend desta rota: os tres nomes de campo do FormData
  // ('numeros', 'arquivos_pdf', 'arquivos_xml') precisam bater com os parametros
  // Form/File do endpoint em app/api/notas_fiscais.py. Sao string dos dois lados
  // — um typo passa por lint, tsc e build e so aparece como 422 em producao.
  it('enviarNotasFiscaisCaixa posta o FormData com as tres listas paralelas', async () => {
    apiFetch.mockResolvedValue({ ok: true, json: async () => ({ id: 7, notas_fiscais: [] }) })
    const pdf1 = new File([new Uint8Array([1])], 'nf1.pdf', { type: 'application/pdf' })
    const xml1 = new File([new Uint8Array([2])], 'nf1.xml', { type: 'application/xml' })
    const pdf2 = new File([new Uint8Array([3])], 'nf2.pdf', { type: 'application/pdf' })
    const xml2 = new File([new Uint8Array([4])], 'nf2.xml', { type: 'application/xml' })

    await caixasApi.enviarNotasFiscaisCaixa(7, [
      { numero: '111', pdf: pdf1, xml: xml1 },
      { numero: '222', pdf: pdf2, xml: xml2 },
    ])

    const [url, init] = apiFetch.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/caixas/7/notas-fiscais')
    expect(init.method).toBe('POST')
    const fd = init.body as FormData
    expect(fd.getAll('numeros')).toEqual(['111', '222'])
    const pdfs = fd.getAll('arquivos_pdf') as File[]
    const xmls = fd.getAll('arquivos_xml') as File[]
    expect(pdfs.map((f) => f.name)).toEqual(['nf1.pdf', 'nf2.pdf'])
    expect(xmls.map((f) => f.name)).toEqual(['nf1.xml', 'nf2.xml'])
  })

  it('avancar envia cliente_principal', async () => {
    await caixasApi.avancar(7, { cliente_principal: 3, obs: null, cod_retorno: null })
    expect(apiJson).toHaveBeenCalledWith('/caixas/7/avancar', { method: 'POST', body: JSON.stringify({ cliente_principal: 3, obs: null, cod_retorno: null }) })
  })
})
