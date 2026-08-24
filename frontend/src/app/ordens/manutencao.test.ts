import { describe, it, expect, beforeEach, vi } from 'vitest'
import { comporResumo, manutencaoApi } from './manutencao'
import { setTokens } from '../../lib/auth-storage'

// Espelha compor_resumo do backend (app/core/manutencao.py): o modal precisa
// mostrar o resumo composto ANTES de salvar, sem ida ao servidor.
describe('comporResumo', () => {
  it('junta as frases na ordem, com ponto entre elas', () => {
    expect(comporResumo(['Primeira frase', 'Segunda frase'])).toBe('Primeira frase. Segunda frase.')
  })

  it('nao duplica o ponto que ja existe', () => {
    expect(comporResumo(['Primeira frase.', 'Segunda frase.'])).toBe('Primeira frase. Segunda frase.')
  })

  it('ignora frases vazias', () => {
    expect(comporResumo(['', '  ', 'Única.'])).toBe('Única.')
  })

  it('sem frases devolve vazio', () => {
    expect(comporResumo([])).toBe('')
  })
})

describe('manutencaoApi.excluirServico', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    setTokens({ access_token: 't', refresh_token: 'r' })
  })

  // DELETE /manutencao-servicos/{id} responde 204 sem corpo. Se excluirServico
  // usasse apiJson (que sempre faz res.json() no sucesso), isso lançaria
  // SyntaxError mesmo com a exclusão bem-sucedida no servidor.
  it('resolve sem lançar quando a resposta é 204 sem corpo', async () => {
    const f = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', f)
    await expect(manutencaoApi.excluirServico(5)).resolves.toBeUndefined()
    expect(f.mock.calls[0][1].method).toBe('DELETE')
  })
})
