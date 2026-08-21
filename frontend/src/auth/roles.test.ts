import { describe, it, expect } from 'vitest'
import {
  isAdmin,
  podeAbrirOS,
  podeRegistrarContato,
  podeAtenderSolicitacao,
  podeGerenciarPropostas,
  podeAvancarCaixa,
  podeMarcarSemConserto,
  podeEditarTipoServico,
  podeFaturarProposta,
  podeDesfaturarProposta,
  FUNCAO_RESPONSAVEL_POR_FASE,
  FUNCAO_EXPEDICAO,
  FUNCAO_LABORATORIO,
  FUNCAO_COMERCIAL,
  FUNCAO_FINANCEIRO,
} from './roles'
import { type User } from './AuthContext'

const admin: User = { id: 1, nome: null, email: 'a@hs.com', funcao_id: 1, funcao: 'Administrador' }
const comum: User = { id: 2, nome: null, email: 'b@hs.com', funcao_id: 2, funcao: 'Expedição' }

describe('isAdmin', () => {
  it('true para Administrador', () => expect(isAdmin(admin)).toBe(true))
  it('false para outra função', () => expect(isAdmin(comum)).toBe(false))
  it('false para null', () => expect(isAdmin(null)).toBe(false))
})

function u(funcao: string | null): User {
  return { id: 1, nome: 'x', email: 'x@hs.com', funcao } as User
}

describe('auth/roles — podeAbrirOS', () => {
  it('admin pode', () => expect(podeAbrirOS(u('Administrador'))).toBe(true))
  it('Expedição pode', () => expect(podeAbrirOS(u('Expedição'))).toBe(true))
  it('Laboratório não pode', () => expect(podeAbrirOS(u('Laboratório'))).toBe(false))
  it('null não pode', () => expect(podeAbrirOS(null)).toBe(false))
})

describe('auth/roles — podeRegistrarContato', () => {
  it('podeRegistrarContato: admin e Comercial sim, outros não', () => {
    expect(podeRegistrarContato(u('Administrador'))).toBe(true)
    expect(podeRegistrarContato(u('Comercial Pós-Vendas'))).toBe(true)
    expect(podeRegistrarContato(u('Laboratório'))).toBe(false)
    expect(podeRegistrarContato(null)).toBe(false)
  })
})

describe('auth/roles — podeAtenderSolicitacao', () => {
  it('podeAtenderSolicitacao: admin e Comercial sim, outros não', () => {
    expect(podeAtenderSolicitacao(u('Administrador'))).toBe(true)
    expect(podeAtenderSolicitacao(u('Comercial Pós-Vendas'))).toBe(true)
    expect(podeAtenderSolicitacao(u('Laboratório'))).toBe(false)
    expect(podeAtenderSolicitacao(null)).toBe(false)
  })
})

describe('auth/roles — podeGerenciarPropostas', () => {
  it('podeGerenciarPropostas: admin e Comercial sim, outros não', () => {
    expect(podeGerenciarPropostas(u('Administrador'))).toBe(true)
    expect(podeGerenciarPropostas(u('Comercial Pós-Vendas'))).toBe(true)
    expect(podeGerenciarPropostas(u('Laboratório'))).toBe(false)
    expect(podeGerenciarPropostas(null)).toBe(false)
  })

  it('Financeiro tambem pode gerenciar propostas', () => {
    expect(podeGerenciarPropostas(u('Financeiro'))).toBe(true)
    expect(podeGerenciarPropostas(u('Laboratório'))).toBe(false)
  })
})

describe('auth/roles — podeAvancarCaixa', () => {
  it('mapa FUNCAO_RESPONSAVEL_POR_FASE tem os valores corretos', () => {
    expect(FUNCAO_RESPONSAVEL_POR_FASE[4]).toBe(FUNCAO_EXPEDICAO)
    expect(FUNCAO_RESPONSAVEL_POR_FASE[5]).toBe(FUNCAO_LABORATORIO)
    expect(FUNCAO_RESPONSAVEL_POR_FASE[6]).toBe(FUNCAO_COMERCIAL)
    expect(FUNCAO_RESPONSAVEL_POR_FASE[7]).toBe(FUNCAO_EXPEDICAO)
    expect(FUNCAO_RESPONSAVEL_POR_FASE[10]).toBe(FUNCAO_FINANCEIRO)
    expect(FUNCAO_RESPONSAVEL_POR_FASE[6]).toBe('Comercial Pós-Vendas')
  })

  it('admin pode avançar em qualquer fase', () => {
    expect(podeAvancarCaixa(u('Administrador'), 4)).toBe(true)
    expect(podeAvancarCaixa(u('Administrador'), 5)).toBe(true)
    expect(podeAvancarCaixa(u('Administrador'), 6)).toBe(true)
    expect(podeAvancarCaixa(u('Administrador'), 7)).toBe(true)
    expect(podeAvancarCaixa(u('Administrador'), 10)).toBe(true)
  })

  it('Expedição pode avançar nas fases 4 e 7', () => {
    expect(podeAvancarCaixa(u('Expedição'), 4)).toBe(true)
    expect(podeAvancarCaixa(u('Expedição'), 7)).toBe(true)
    expect(podeAvancarCaixa(u('Expedição'), 5)).toBe(false)
    expect(podeAvancarCaixa(u('Expedição'), 6)).toBe(false)
    expect(podeAvancarCaixa(u('Expedição'), 10)).toBe(false)
  })

  it('Laboratório pode avançar na fase 5', () => {
    expect(podeAvancarCaixa(u('Laboratório'), 5)).toBe(true)
    expect(podeAvancarCaixa(u('Laboratório'), 4)).toBe(false)
    expect(podeAvancarCaixa(u('Laboratório'), 6)).toBe(false)
    expect(podeAvancarCaixa(u('Laboratório'), 7)).toBe(false)
    expect(podeAvancarCaixa(u('Laboratório'), 10)).toBe(false)
  })

  it('Comercial Pós-Vendas pode avançar na fase 6', () => {
    expect(podeAvancarCaixa(u('Comercial Pós-Vendas'), 6)).toBe(true)
    expect(podeAvancarCaixa(u('Comercial Pós-Vendas'), 4)).toBe(false)
    expect(podeAvancarCaixa(u('Comercial Pós-Vendas'), 5)).toBe(false)
    expect(podeAvancarCaixa(u('Comercial Pós-Vendas'), 7)).toBe(false)
    expect(podeAvancarCaixa(u('Comercial Pós-Vendas'), 10)).toBe(false)
  })

  it('Financeiro pode avançar na fase 10', () => {
    expect(podeAvancarCaixa(u('Financeiro'), 10)).toBe(true)
    expect(podeAvancarCaixa(u('Financeiro'), 4)).toBe(false)
    expect(podeAvancarCaixa(u('Financeiro'), 5)).toBe(false)
    expect(podeAvancarCaixa(u('Financeiro'), 6)).toBe(false)
    expect(podeAvancarCaixa(u('Financeiro'), 7)).toBe(false)
  })

  it('outra função não pode avançar em nenhuma fase', () => {
    expect(podeAvancarCaixa(u('Qualidade'), 4)).toBe(false)
    expect(podeAvancarCaixa(u('Qualidade'), 5)).toBe(false)
    expect(podeAvancarCaixa(u('Suporte'), 6)).toBe(false)
  })

  it('usuario sem sessao (null) não pode avançar', () => {
    expect(podeAvancarCaixa(null, 4)).toBe(false)
    expect(podeAvancarCaixa(null, 5)).toBe(false)
    expect(podeAvancarCaixa(null, 6)).toBe(false)
  })

  it('fase null: admin ainda passa (por isAdmin), outros não', () => {
    // Admin sempre passa, até com fase nula
    expect(podeAvancarCaixa(u('Administrador'), null)).toBe(true)
    // Não-admin com fase nula retorna false
    expect(podeAvancarCaixa(u('Laboratório'), null)).toBe(false)
    expect(podeAvancarCaixa(null, null)).toBe(false)
  })
})

describe('auth/roles — podeMarcarSemConserto', () => {
  it('admin pode marcar sem conserto', () => {
    expect(podeMarcarSemConserto(u('Administrador'))).toBe(true)
  })

  it('Laboratório pode marcar sem conserto', () => {
    expect(podeMarcarSemConserto(u('Laboratório'))).toBe(true)
  })

  it('outras funcoes não podem marcar sem conserto', () => {
    expect(podeMarcarSemConserto(u('Expedição'))).toBe(false)
    expect(podeMarcarSemConserto(u('Comercial Pós-Vendas'))).toBe(false)
    expect(podeMarcarSemConserto(u('Financeiro'))).toBe(false)
    expect(podeMarcarSemConserto(u('Qualidade'))).toBe(false)
  })

  it('usuario sem sessao (null) não pode marcar sem conserto', () => {
    expect(podeMarcarSemConserto(null)).toBe(false)
  })
})

describe('auth/roles — podeFaturarProposta', () => {
  it('Financeiro pode faturar', () => expect(podeFaturarProposta(u('Financeiro'))).toBe(true))
  it('Admin pode faturar', () => expect(podeFaturarProposta(u('Administrador'))).toBe(true))
  it('Comercial Pós-Vendas não pode faturar', () => expect(podeFaturarProposta(u('Comercial Pós-Vendas'))).toBe(false))
  it('null não pode faturar', () => expect(podeFaturarProposta(null)).toBe(false))
})

describe('auth/roles — podeDesfaturarProposta', () => {
  it('Admin pode desfaturar', () => expect(podeDesfaturarProposta(u('Administrador'))).toBe(true))
  it('Financeiro não pode desfaturar', () => expect(podeDesfaturarProposta(u('Financeiro'))).toBe(false))
  it('null não pode desfaturar', () => expect(podeDesfaturarProposta(null)).toBe(false))
})

describe('auth/roles — podeEditarTipoServico', () => {
  // So durante o laboratorio: depois dele a OS ja emitiu certificado e seguiu
  // para cobranca, e trocar o tipo mudaria o que foi cobrado e o que foi emitido.
  it('laboratório edita na fase 5', () => {
    expect(podeEditarTipoServico({ funcao: 'Laboratório' } as never, 5)).toBe(true)
  })

  it('admin também edita na fase 5', () => {
    expect(podeEditarTipoServico({ funcao: 'Administrador' } as never, 5)).toBe(true)
  })

  it('laboratório não edita fora da fase 5', () => {
    for (const fase of [4, 6, 7, 8, 9]) {
      expect(podeEditarTipoServico({ funcao: 'Laboratório' } as never, fase)).toBe(false)
    }
  })

  it('outra função não edita nem na fase 5', () => {
    expect(podeEditarTipoServico({ funcao: 'Financeiro' } as never, 5)).toBe(false)
    expect(podeEditarTipoServico(null, 5)).toBe(false)
  })

  it('fase desconhecida não libera', () => {
    expect(podeEditarTipoServico({ funcao: 'Laboratório' } as never, null)).toBe(false)
  })
})
