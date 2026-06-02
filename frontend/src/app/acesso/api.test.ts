import { describe, it, expect, beforeEach, vi } from 'vitest'
import { listarUsuarios, criarUsuario, excluirUsuario } from './api'
import { setTokens } from '../../lib/auth-storage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

const ITEM = { id: 1, nome: null, login: 'a', email: null, funcao_id: null, funcao: null, precisa_redefinir_senha: false }

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
    expect(r[0].login).toBe('a')
  })

  it('criarUsuario faz POST com o corpo', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse(ITEM))
    vi.stubGlobal('fetch', f)
    await criarUsuario({ login: 'novo', senha: '12345678' })
    expect(f.mock.calls[0][1].method).toBe('POST')
    expect(String(f.mock.calls[0][1].body)).toContain('novo')
  })

  it('excluirUsuario resolve no 204 com DELETE', async () => {
    const f = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', f)
    await expect(excluirUsuario(5)).resolves.toBeUndefined()
    expect(f.mock.calls[0][1].method).toBe('DELETE')
  })

  it('excluirUsuario lança ApiError em falha', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ detail: 'não é possível excluir o próprio usuário' }, 400))
    vi.stubGlobal('fetch', f)
    await expect(excluirUsuario(5)).rejects.toMatchObject({ status: 400 })
  })
})
