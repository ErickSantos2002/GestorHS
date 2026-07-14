import { describe, it, expect, beforeEach, vi } from 'vitest'
import { listarUsuarios, criarUsuario, desativarUsuario, reativarUsuario } from './api'
import { setTokens } from '../../lib/auth-storage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

const ITEM = { id: 1, nome: null, email: 'a@hs.com', funcao_id: null, funcao: null, precisa_redefinir_senha: false, ativo: true }

describe('acesso/api', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    setTokens({ access_token: 't', refresh_token: 'r' })
  })

  it('listarUsuarios faz GET em /usuarios', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse([ITEM]))
    vi.stubGlobal('fetch', f)
    const r = await listarUsuarios()
    expect(String(f.mock.calls[0][0])).toContain('/usuarios')
    expect(r[0].email).toBe('a@hs.com')
  })

  it('listarUsuarios(true) inclui incluir_inativos=true na query', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse([ITEM]))
    vi.stubGlobal('fetch', f)
    await listarUsuarios(true)
    expect(String(f.mock.calls[0][0])).toContain('/usuarios?incluir_inativos=true')
  })

  it('criarUsuario faz POST com o corpo', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse(ITEM))
    vi.stubGlobal('fetch', f)
    await criarUsuario({ email: 'novo@hs.com', senha: '12345678' })
    expect(f.mock.calls[0][1].method).toBe('POST')
    expect(String(f.mock.calls[0][1].body)).toContain('novo')
  })

  it('desativarUsuario resolve no 204 com POST', async () => {
    const f = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', f)
    await expect(desativarUsuario(5)).resolves.toBeUndefined()
    expect(f.mock.calls[0][1].method).toBe('POST')
    expect(String(f.mock.calls[0][0])).toContain('/usuarios/5/desativar')
  })

  it('desativarUsuario lança ApiError em falha', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ detail: 'não é possível desativar o próprio usuário' }, 400))
    vi.stubGlobal('fetch', f)
    await expect(desativarUsuario(5)).rejects.toMatchObject({ status: 400 })
  })

  it('reativarUsuario resolve no 204 com POST', async () => {
    const f = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', f)
    await expect(reativarUsuario(5)).resolves.toBeUndefined()
    expect(f.mock.calls[0][1].method).toBe('POST')
    expect(String(f.mock.calls[0][0])).toContain('/usuarios/5/reativar')
  })
})
