import { describe, it, expect, beforeEach, vi } from 'vitest'
import { usuariosPortalApi } from './api'
import { setTokens } from '../../lib/auth-storage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('clientes/api — usuariosPortalApi', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    setTokens({ access_token: 't', refresh_token: 'r' })
  })

  it('listarPorCliente faz GET /clientes/{id}/usuarios-portal', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse([]))
    vi.stubGlobal('fetch', f)
    await usuariosPortalApi.listarPorCliente(7)
    expect(String(f.mock.calls[0][0])).toContain('/clientes/7/usuarios-portal')
  })

  it('criar faz POST /clientes/{id}/usuarios-portal', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ id: 1 }, 201))
    vi.stubGlobal('fetch', f)
    await usuariosPortalApi.criar(7, { login: 'a', nome: null, email: null, senha: 'temp12345' })
    expect(String(f.mock.calls[0][0])).toContain('/clientes/7/usuarios-portal')
    expect(f.mock.calls[0][1]).toMatchObject({ method: 'POST' })
  })

  it('redefinirSenha faz POST /usuarios-portal/{id}/redefinir-senha', async () => {
    const f = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', f)
    await usuariosPortalApi.redefinirSenha(3, 'nova12345')
    expect(String(f.mock.calls[0][0])).toContain('/usuarios-portal/3/redefinir-senha')
    expect(String(f.mock.calls[0][1].body)).toContain('nova_senha')
  })

  it('criar propaga ApiError 409', async () => {
    const f = vi.fn().mockResolvedValue(jsonResponse({ detail: 'login já em uso' }, 409))
    vi.stubGlobal('fetch', f)
    await expect(usuariosPortalApi.criar(7, { login: 'a', nome: null, email: null, senha: 'temp12345' })).rejects.toMatchObject({ status: 409 })
  })
})
