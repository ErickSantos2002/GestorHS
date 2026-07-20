import { describe, it, expect } from 'vitest'
import { isAdmin, podeGerenciarCadastros } from './roles'

const u = (funcao: string | null) => ({ funcao }) as never

describe('podeGerenciarCadastros (cliente e aparelho)', () => {
  it('libera Administrador e Laboratorio', () => {
    expect(podeGerenciarCadastros(u('Administrador'))).toBe(true)
    expect(podeGerenciarCadastros(u('Laboratório'))).toBe(true)
  })

  it('bloqueia as demais funcoes e usuario sem sessao', () => {
    for (const f of ['Expedição', 'Comercial Pós-Vendas', 'Financeiro', 'Suporte', 'Qualidade']) {
      expect(podeGerenciarCadastros(u(f))).toBe(false)
    }
    expect(podeGerenciarCadastros(null)).toBe(false)
  })

  it('EXCLUIR nao vaza: o Laboratorio gerencia cadastros mas NAO e admin', () => {
    // Os botoes de excluir usam isAdmin(), nao este helper — se um dia alguem
    // trocar isAdmin por podeGerenciarCadastros num botao de excluir, este
    // teste nao pega, mas a distincao entre os dois fica registrada aqui.
    expect(podeGerenciarCadastros(u('Laboratório'))).toBe(true)
    expect(isAdmin(u('Laboratório'))).toBe(false)
  })
})
