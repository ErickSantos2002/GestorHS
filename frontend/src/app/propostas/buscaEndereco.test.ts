import { describe, it, expect } from 'vitest'
import { ApiError } from '../../lib/api'
import { aplicarResultadoCep, aplicarResultadoCnpj, mensagemErroBusca } from './buscaEndereco'

const CEP = { cep: '50030230', endereco: 'Cais do Apolo', municipio: 'Recife', estado: 'PE' }
const CNPJ = {
  documento: '36312056000552', nome: 'Acme Ltda', endereco: 'Rua X, 10',
  municipio: 'Recife', estado: 'PE', cep: '50030230', situacao: 'ATIVA',
}

describe('aplicarResultadoCep', () => {
  it('preenche endereco, municipio e estado', () => {
    const { draft, preenchidos } = aplicarResultadoCep({}, CEP)
    expect(draft).toEqual({ endereco: 'Cais do Apolo', municipio: 'Recife', estado: 'PE' })
    expect(preenchidos).toEqual(['endereco', 'municipio', 'estado'])
  })

  it('nao toca em nome, documento, telefone, email nem contato', () => {
    const antes = { nome: 'Filial', documento: '111', telefone: '81999', email: 'a@b.c', contato: 'Ana' }
    const { draft } = aplicarResultadoCep(antes, CEP)
    expect(draft.nome).toBe('Filial')
    expect(draft.documento).toBe('111')
    expect(draft.telefone).toBe('81999')
    expect(draft.email).toBe('a@b.c')
    expect(draft.contato).toBe('Ana')
  })

  it('sobrescreve valor ja preenchido', () => {
    const { draft } = aplicarResultadoCep({ municipio: 'Olinda' }, CEP)
    expect(draft.municipio).toBe('Recife')
  })

  it('campo vazio na resposta nao apaga o que ja existe', () => {
    const { draft, preenchidos } = aplicarResultadoCep({ municipio: 'Olinda' }, { ...CEP, municipio: '' })
    expect(draft.municipio).toBe('Olinda')
    expect(preenchidos).not.toContain('municipio')
  })
})

describe('aplicarResultadoCnpj', () => {
  it('preenche razao social, endereco, municipio, estado e cep', () => {
    const { draft, preenchidos } = aplicarResultadoCnpj({}, CNPJ)
    expect(draft).toEqual({
      nome: 'Acme Ltda', endereco: 'Rua X, 10', municipio: 'Recife', estado: 'PE', cep: '50030230',
    })
    expect(preenchidos).toEqual(['nome', 'endereco', 'municipio', 'estado', 'cep'])
  })

  it('nao sobrescreve telefone, email nem contato (dados da Receita sao velhos)', () => {
    const antes = { telefone: '8130001111', email: 'bom@cliente.com', contato: 'Ana' }
    const { draft } = aplicarResultadoCnpj(antes, CNPJ)
    expect(draft.telefone).toBe('8130001111')
    expect(draft.email).toBe('bom@cliente.com')
    expect(draft.contato).toBe('Ana')
  })

  it('nao altera o draft original (funcao pura)', () => {
    const antes = { municipio: 'Olinda' }
    aplicarResultadoCnpj(antes, CNPJ)
    expect(antes.municipio).toBe('Olinda')
  })
})

describe('mensagemErroBusca', () => {
  it('traduz os status conhecidos', () => {
    expect(mensagemErroBusca(new ApiError(404, 'x'), 'CNPJ')).toMatch(/não encontrado/i)
    expect(mensagemErroBusca(new ApiError(400, 'x'), 'CEP')).toMatch(/inválido/i)
    expect(mensagemErroBusca(new ApiError(502, 'x'), 'CEP')).toMatch(/indisponível/i)
  })

  it('erro desconhecido vira mensagem generica com o tipo', () => {
    expect(mensagemErroBusca(new Error('boom'), 'CEP')).toMatch(/Falha ao consultar o CEP/)
  })
})
