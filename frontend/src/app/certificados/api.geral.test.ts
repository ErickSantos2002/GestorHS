import { describe, it, expect, vi, beforeEach } from 'vitest'
import { certificadosApi } from './api'
import { setTokens } from '../../lib/auth-storage'

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('certificadosApi (gerais)', () => {
  beforeEach(() => { localStorage.clear(); vi.restoreAllMocks(); setTokens({ access_token: 't', refresh_token: 'r' }) })

  it('listarGerais bate no path certo', async () => {
    const f = vi.fn().mockResolvedValue(json([]))
    vi.stubGlobal('fetch', f)
    await certificadosApi.listarGerais()
    expect(String(f.mock.calls[0][0])).toContain('/certificados-gerais')
  })

  it('enviarGeral manda multipart com nome e arquivo', async () => {
    const f = vi.fn().mockResolvedValue(json({ id: 1, nome: 'Gas', data_upload: null, usuario_nome: null, link: null }))
    vi.stubGlobal('fetch', f)
    await certificadosApi.enviarGeral('Gas', new File([new Blob(['x'])], 'g.pdf', { type: 'application/pdf' }))
    const init = f.mock.calls[0][1] as RequestInit
    expect(init.method).toBe('POST')
    expect(init.body).toBeInstanceOf(FormData)
  })

  it('excluirGeral usa DELETE', async () => {
    const f = vi.fn().mockResolvedValue(json({ ok: true }))
    vi.stubGlobal('fetch', f)
    await certificadosApi.excluirGeral(3)
    const init = f.mock.calls[0][1] as RequestInit
    expect(String(f.mock.calls[0][0])).toContain('/certificados-gerais/3')
    expect(init.method).toBe('DELETE')
  })
})
