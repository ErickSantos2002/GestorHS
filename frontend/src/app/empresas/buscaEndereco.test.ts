import { describe, it, expect } from 'vitest'
import { ApiError } from '../../lib/api'
import { dadosVazios } from './dadosEmpresa'
import { aplicarResultadoCep, aplicarResultadoCnpj, mensagemErroBusca } from './buscaEndereco'

const CEP = { cep: '50030230', endereco: 'Cais do Apolo', bairro: 'Boa Vista', municipio: 'Recife', estado: 'PE' }
const CNPJ = {
  documento: '36312056000552', nome: 'Acme Ltda', endereco: 'Rua X', numero: '10', complemento: 'Sala 2',
  bairro: 'Centro', municipio: 'Recife', estado: 'PE', cep: '50030230', situacao: 'ATIVA',
}

describe('aplicarResultadoCep', () => {
  it('preenche cep, endereco, bairro, municipio e estado', () => {
    const { dados, preenchidos } = aplicarResultadoCep(dadosVazios(), CEP)
    expect(dados).toEqual({
      ...dadosVazios(), cep: CEP.cep, endereco: CEP.endereco, bairro: CEP.bairro, municipio: CEP.municipio, estado: CEP.estado,
    })
    expect(preenchidos).toEqual(['cep', 'endereco', 'bairro', 'municipio', 'estado'])
  })

  it('nao toca em nome, documento, numero, complemento, telefone nem email', () => {
    const antes = {
      ...dadosVazios(), nome: 'Filial', documento: '111', numero: '10', complemento: 'Sala 2',
      telefone: '81999', email: 'a@b.c',
    }
    const { dados } = aplicarResultadoCep(antes, CEP)
    expect(dados.nome).toBe('Filial')
    expect(dados.documento).toBe('111')
    expect(dados.numero).toBe('10')
    expect(dados.complemento).toBe('Sala 2')
    expect(dados.telefone).toBe('81999')
    expect(dados.email).toBe('a@b.c')
  })

  it('sobrescreve valor ja preenchido', () => {
    const { dados } = aplicarResultadoCep({ ...dadosVazios(), municipio: 'Olinda' }, CEP)
    expect(dados.municipio).toBe('Recife')
  })

  it('campo vazio na resposta nao apaga o que ja existe', () => {
    const { dados, preenchidos } = aplicarResultadoCep({ ...dadosVazios(), municipio: 'Olinda' }, { ...CEP, municipio: '' })
    expect(dados.municipio).toBe('Olinda')
    expect(preenchidos).not.toContain('municipio')
  })
})

describe('aplicarResultadoCnpj', () => {
  it('preenche razao social, endereco, numero, complemento, bairro, municipio, estado e cep', () => {
    const { dados, preenchidos } = aplicarResultadoCnpj(dadosVazios(), CNPJ)
    expect(dados).toEqual({
      ...dadosVazios(), nome: CNPJ.nome, cep: CNPJ.cep, endereco: CNPJ.endereco, numero: CNPJ.numero,
      complemento: CNPJ.complemento, bairro: CNPJ.bairro, municipio: CNPJ.municipio, estado: CNPJ.estado,
    })
    expect(preenchidos).toEqual(['nome', 'cep', 'endereco', 'numero', 'complemento', 'bairro', 'municipio', 'estado'])
  })

  it('nao sobrescreve telefone nem email (dados da Receita sao velhos)', () => {
    const antes = { ...dadosVazios(), telefone: '8130001111', email: 'bom@cliente.com' }
    const { dados } = aplicarResultadoCnpj(antes, CNPJ)
    expect(dados.telefone).toBe('8130001111')
    expect(dados.email).toBe('bom@cliente.com')
  })

  it('nao altera o dados original (funcao pura)', () => {
    const antes = { ...dadosVazios(), municipio: 'Olinda' }
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

  it('cota estourada (429) manda esperar, nao diz que o servico caiu', () => {
    const msg = mensagemErroBusca(new ApiError(429, 'x'), 'CNPJ')
    expect(msg).toMatch(/espere alguns segundos/i)
    expect(msg).not.toMatch(/indisponível/i)
  })

  it('erro desconhecido vira mensagem generica com o tipo', () => {
    expect(mensagemErroBusca(new Error('boom'), 'CEP')).toMatch(/Falha ao consultar o CEP/)
  })
})
