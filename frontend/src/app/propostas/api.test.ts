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

import { propostasApi, servicosApi, produtosApi, frotaDoCliente, type PropostaCreate } from './api'

beforeEach(() => {
  apiJson.mockReset(); apiJson.mockResolvedValue({})
  apiFetch.mockReset(); apiFetch.mockResolvedValue({ ok: true })
})

const payload: PropostaCreate = {
  cliente: 5,
  contato: 'Fulano',
  vendedor: 'Ciclano',
  data: '2026-07-24',
  intro: null,
  outros_itens: null,
  desconto: 0,
  frete: 0,
  forma_envio: null,
  forma_frete: null,
  transportador: null,
  condicao_pagamento: null,
  validade_dias: null,
  data_entrega: null,
  descricao_entrega: null,
  endereco_entrega_diferente: false,
  endereco_entrega: null,
  cliente_override: null,
  observacoes: null,
  assinatura: null,
  itens: [],
  aparelhos: [],
}

describe('propostasApi', () => {
  it('listar busca /propostas com paginacao', async () => {
    await propostasApi.listar({ page: 2, page_size: 25, q: 'votor' })
    expect(apiJson).toHaveBeenCalledWith('/propostas?page=2&page_size=25&q=votor')
  })

  it('listar sem params usa so o path base', async () => {
    await propostasApi.listar()
    expect(apiJson).toHaveBeenCalledWith('/propostas')
  })

  it('obter busca /propostas/:id', async () => {
    await propostasApi.obter(9)
    expect(apiJson).toHaveBeenCalledWith('/propostas/9')
  })

  it('criar posta em /propostas', async () => {
    await propostasApi.criar(payload)
    expect(apiJson).toHaveBeenCalledWith('/propostas', { method: 'POST', body: JSON.stringify(payload) })
  })

  it('atualizar da PUT em /propostas/:id', async () => {
    await propostasApi.atualizar(9, payload)
    expect(apiJson).toHaveBeenCalledWith('/propostas/9', { method: 'PUT', body: JSON.stringify(payload) })
  })

  it('excluir usa apiFetch com DELETE', async () => {
    await propostasApi.excluir(9)
    expect(apiFetch).toHaveBeenCalledWith('/propostas/9', expect.objectContaining({ method: 'DELETE' }))
  })

  it('duplicar posta em /propostas/:id/duplicar', async () => {
    await propostasApi.duplicar(9)
    expect(apiJson).toHaveBeenCalledWith('/propostas/9/duplicar', { method: 'POST' })
  })

  it('listarVersoes busca /propostas/:id/versoes', async () => {
    await propostasApi.listarVersoes(9)
    expect(apiJson).toHaveBeenCalledWith('/propostas/9/versoes')
  })

  it('pdfUrl monta a url absoluta com base da api', () => {
    const url = propostasApi.pdfUrl(9)
    expect(url).toMatch(/\/propostas\/9\/pdf$/)
  })

  it('pdfUrl com download=true acrescenta query', () => {
    const url = propostasApi.pdfUrl(9, true)
    expect(url).toMatch(/\/propostas\/9\/pdf\?download=1$/)
  })

  it('versaoPdfUrl monta a url da versao', () => {
    const url = propostasApi.versaoPdfUrl(9, 3)
    expect(url).toMatch(/\/propostas\/9\/versoes\/3\/pdf$/)
  })
})

describe('frotaDoCliente', () => {
  it('busca equipamentos-cliente filtrando por cliente', async () => {
    apiJson.mockResolvedValue({ items: [], total: 0 })
    await frotaDoCliente(5)
    expect(apiJson).toHaveBeenCalledWith('/equipamentos-cliente?cliente=5&limit=100')
  })
})

describe('servicosApi / produtosApi', () => {
  it('servicosApi.listar busca /servicos', async () => {
    await servicosApi.listar()
    expect(apiJson).toHaveBeenCalledWith('/servicos')
  })

  it('produtosApi.criar posta em /produtos', async () => {
    const body = { nome: 'Produto X', preco: 10 }
    await produtosApi.criar(body)
    expect(apiJson).toHaveBeenCalledWith('/produtos', { method: 'POST', body: JSON.stringify(body) })
  })
})
