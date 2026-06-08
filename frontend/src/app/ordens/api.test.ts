import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ordensApi } from './api'
import { setTokens } from '../../lib/auth-storage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('ordens/api', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    setTokens({ access_token: 't', refresh_token: 'r' })
  })

  it('listar monta a query string (fase/cliente/tipo/q/offset/limit)', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ items: [], total: 0 }))
    vi.stubGlobal('fetch', f)
    await ordensApi.listar({ fase: 5, cliente: 12, tipo: 'C', q: 'abc', offset: 25, limit: 25 })
    const url = String(f.mock.calls[0][0])
    expect(url).toContain('/ordens?')
    expect(url).toContain('fase=5')
    expect(url).toContain('cliente=12')
    expect(url).toContain('tipo=C')
    expect(url).toContain('q=abc')
    expect(url).toContain('offset=25')
  })

  it('listar omite chaves ausentes mas sempre manda offset/limit', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ items: [], total: 0 }))
    vi.stubGlobal('fetch', f)
    await ordensApi.listar({})
    const url = String(f.mock.calls[0][0])
    expect(url).not.toContain('fase=')
    expect(url).not.toContain('cliente=')
    expect(url).toContain('offset=0')
    expect(url).toContain('limit=25')
  })

  it('quadro bate em /ordens/quadro (com e sem cliente)', async () => {
    const f = vi.fn()
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse([]))
    vi.stubGlobal('fetch', f)
    await ordensApi.quadro({})
    expect(String(f.mock.calls[0][0])).toContain('/ordens/quadro')
    await ordensApi.quadro({ cliente: 7 })
    expect(String(f.mock.calls[1][0])).toContain('/ordens/quadro?cliente=7')
  })

  it('obter e logs nos paths certos', async () => {
    const f = vi.fn()
      .mockResolvedValueOnce(jsonResponse({}))
      .mockResolvedValueOnce(jsonResponse([]))
    vi.stubGlobal('fetch', f)
    await ordensApi.obter(42)
    expect(String(f.mock.calls[0][0])).toContain('/ordens/42')
    await ordensApi.logs(42)
    expect(String(f.mock.calls[1][0])).toContain('/ordens/42/logs')
  })

  it('propaga ApiError em resposta não-ok', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ detail: 'x' }, 404))
    vi.stubGlobal('fetch', f)
    await expect(ordensApi.obter(99)).rejects.toMatchObject({ status: 404 })
  })

  it('abrir faz POST /ordens com o corpo certo', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ id: 1 }, 201))
    vi.stubGlobal('fetch', f)
    await ordensApi.abrir({ equipamento_cliente: 7, tipo_servico: 'C', condicao_chegada: 'ok' })
    expect(String(f.mock.calls[0][0])).toContain('/ordens')
    expect(f.mock.calls[0][1]).toMatchObject({ method: 'POST' })
    const body = String(f.mock.calls[0][1].body)
    expect(body).toContain('equipamento_cliente')
    expect(body).toContain('tipo_servico')
  })

  it('avancar faz POST /ordens/{id}/avancar com obs/cod_retorno', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ id: 1 }))
    vi.stubGlobal('fetch', f)
    await ordensApi.avancar(5, { obs: 'x', cod_retorno: 'BR9' })
    expect(String(f.mock.calls[0][0])).toContain('/ordens/5/avancar')
    expect(f.mock.calls[0][1]).toMatchObject({ method: 'POST' })
    expect(String(f.mock.calls[0][1].body)).toContain('cod_retorno')
  })

  it('cancelar faz POST /ordens/{id}/cancelar com motivo', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ id: 1 }))
    vi.stubGlobal('fetch', f)
    await ordensApi.cancelar(9, { motivo: 'desistência' })
    expect(String(f.mock.calls[0][0])).toContain('/ordens/9/cancelar')
    expect(String(f.mock.calls[0][1].body)).toContain('motivo')
  })

  it('abrir propaga ApiError 409', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ detail: 'aparelho já possui OS ativa' }, 409))
    vi.stubGlobal('fetch', f)
    await expect(ordensApi.abrir({ equipamento_cliente: 7, tipo_servico: 'C' })).rejects.toMatchObject({ status: 409 })
  })

  it('avancar inclui campos de calibração no corpo', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ id: 1 }))
    vi.stubGlobal('fetch', f)
    await ordensApi.avancar(5, { calib_cert: 'HF1', calib_teste_media: '0,1', prox_calibragem: '2027-06-03' })
    const body = String(f.mock.calls[0][1].body)
    expect(body).toContain('calib_cert')
    expect(body).toContain('prox_calibragem')
  })
})
