import { describe, it, expect, beforeEach, vi } from 'vitest'
import { funcoesApi, fasesApi } from './api'
import { setTokens } from '../../lib/auth-storage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('cadastros/api — funcoes e fases', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    setTokens({ access_token: 't', refresh_token: 'r' })
  })

  it('funcoesApi.criar faz POST /funcoes', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ id: 1, descricao: 'X' }, 201))
    vi.stubGlobal('fetch', f)
    await funcoesApi.criar({ descricao: 'X' })
    expect(String(f.mock.calls[0][0])).toContain('/funcoes')
    expect(f.mock.calls[0][1]).toMatchObject({ method: 'POST' })
  })

  it('funcoesApi.excluir propaga 409', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ detail: 'registro em uso' }, 409))
    vi.stubGlobal('fetch', f)
    await expect(funcoesApi.excluir(3)).rejects.toMatchObject({ status: 409 })
  })

  it('fasesApi.listar faz GET /fases', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse([]))
    vi.stubGlobal('fetch', f)
    await fasesApi.listar()
    expect(String(f.mock.calls[0][0])).toContain('/fases')
  })

  it('fasesApi.atualizar faz PATCH /fases/{id} com funcao_responsavel', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ id: 4, descricao: 'Recebido', cor: '3b82f6', funcao_responsavel: 2, funcao_nome: 'Expedição' }))
    vi.stubGlobal('fetch', f)
    await fasesApi.atualizar(4, { funcao_responsavel: 2 })
    expect(String(f.mock.calls[0][0])).toContain('/fases/4')
    expect(f.mock.calls[0][1]).toMatchObject({ method: 'PATCH' })
    expect(String(f.mock.calls[0][1].body)).toContain('funcao_responsavel')
  })

  it('tiposCalibragemApi.listar faz GET /tipos-calibragem', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse([]))
    vi.stubGlobal('fetch', f)
    const { tiposCalibragemApi } = await import('./api')
    await tiposCalibragemApi.listar()
    expect(String(f.mock.calls[0][0])).toContain('/tipos-calibragem')
  })
})
