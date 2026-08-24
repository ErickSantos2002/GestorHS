import { describe, it, expect, beforeEach, vi } from 'vitest'
import { comporResumo, manutencaoApi } from './manutencao'
import { setTokens } from '../../lib/auth-storage'

// Espelha compor_resumo do backend (app/core/manutencao.py): o modal precisa
// mostrar o resumo composto ANTES de salvar, sem ida ao servidor.
// Espelho de compor_resumo do backend (app/core/manutencao.py) — os mesmos
// casos estao cobertos la, em tests/test_manutencao_core.py.
describe('comporResumo', () => {
  const S = (codigo: string | null, descricao: string) => ({ codigo, descricao })

  it('um serviço: aparelho, conformidade e o serviço', () => {
    expect(comporResumo('Mercury', '10301681', [S('214', 'Troca de solenoide/bomba')])).toBe(
      'Foi realizada a manutenção no equipamento Mercury / nº de série 10301681, '
      + 'em conformidade com os procedimentos técnicos da Health & Safety, '
      + 'referente ao serviço: 214 – Troca de solenoide/bomba.',
    )
  })

  it('vários serviços: lista todos sem repetir aparelho nem conformidade', () => {
    const texto = comporResumo('Mercury', '10301681', [
      S('214', 'Troca de solenoide/bomba'),
      S('315', 'Troca do Bluetooth - Mercury'),
      S('70', 'Troca do botão ON/OFF'),
    ])
    expect(texto).toContain('referente aos serviços: 214 – Troca de solenoide/bomba; '
      + '315 – Troca do Bluetooth - Mercury; 70 – Troca do botão ON/OFF.')
    expect(texto.match(/em conformidade/g)).toHaveLength(1)
    expect(texto.match(/nº de série/g)).toHaveLength(1)
  })

  it('singular e plural conforme a quantidade', () => {
    expect(comporResumo('X', '1', [S('1', 'A')])).toContain('referente ao serviço:')
    expect(comporResumo('X', '1', [S('1', 'A'), S('2', 'B')])).toContain('referente aos serviços:')
  })

  it('serviço sem código mostra só a descrição', () => {
    expect(comporResumo('X', '1', [S(null, 'Sem código')])).toContain('referente ao serviço: Sem código.')
  })

  it('sem serviço devolve vazio', () => {
    expect(comporResumo('Mercury', '10301681', [])).toBe('')
  })

  it('aguenta aparelho sem modelo ou sem série', () => {
    expect(comporResumo('', '10301681', [S('1', 'A')])).toContain('no equipamento nº de série 10301681,')
    expect(comporResumo('Mercury', '', [S('1', 'A')])).toContain('no equipamento Mercury,')
    expect(comporResumo('', '', [S('1', 'A')])).toContain('no equipamento não identificado,')
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
