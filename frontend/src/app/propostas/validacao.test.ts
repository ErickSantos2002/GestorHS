import { describe, it, expect } from 'vitest'
import { htmlTemTexto, validarProposta } from './validacao'

const OK = { cliente: 5, documento: '36312056000552', outrosItens: '<p>Calibracao</p>' }

describe('htmlTemTexto', () => {
  it('trata vazio, nulo e markup sem texto como sem texto', () => {
    expect(htmlTemTexto('')).toBe(false)
    expect(htmlTemTexto(null)).toBe(false)
    expect(htmlTemTexto('<p><br></p>')).toBe(false)
    expect(htmlTemTexto('<p>&nbsp;</p>')).toBe(false)
    expect(htmlTemTexto('   ')).toBe(false)
  })

  it('reconhece texto dentro de tags', () => {
    expect(htmlTemTexto('<p><strong>Servicos</strong></p>')).toBe(true)
    expect(htmlTemTexto('<ul><li>Calibracao</li></ul>')).toBe(true)
  })
})

describe('validarProposta', () => {
  it('aceita proposta com cliente, documento e outros itens', () => {
    expect(validarProposta(OK)).toBeNull()
  })

  it('exige cliente', () => {
    expect(validarProposta({ ...OK, cliente: null })).toMatch(/selecione o cliente/i)
  })

  it('espera o carregamento do cliente antes de julgar o documento', () => {
    expect(validarProposta({ ...OK, documento: '', carregandoCliente: true })).toMatch(/aguarde/i)
  })

  it('exige documento do cliente', () => {
    expect(validarProposta({ ...OK, documento: null })).toMatch(/CNPJ\/CPF/)
    expect(validarProposta({ ...OK, documento: '---' })).toMatch(/CNPJ\/CPF/)
  })

  it('exige o bloco de outros itens preenchido', () => {
    expect(validarProposta({ ...OK, outrosItens: '<p><br></p>' })).toMatch(/Outros Itens/)
  })

  it('reporta o cliente antes do documento quando faltam os dois', () => {
    expect(validarProposta({ cliente: null, documento: null, outrosItens: null })).toMatch(/selecione o cliente/i)
  })
})
