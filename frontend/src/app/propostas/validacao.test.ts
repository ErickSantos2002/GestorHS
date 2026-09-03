import { describe, it, expect } from 'vitest'
import { camposObrigatoriosFaltando, htmlTemTexto, validarProposta } from './validacao'
import type { CampoOverride } from './clienteOverride'

const RASCUNHO_OK: Partial<Record<CampoOverride, string>> = {
  nome: 'Cliente Teste',
  documento: '36312056000552',
  endereco: 'Rua X, 10',
  municipio: 'Recife',
  estado: 'PE',
  cep: '50000000',
  telefone: '8130001111',
  email: 'contato@teste.com',
  contato: 'Joana',
}

const OK = { cliente: 5, rascunho: RASCUNHO_OK, outrosItens: '<p>Calibracao</p>' }

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

describe('camposObrigatoriosFaltando', () => {
  it('nao aponta nada com todos os obrigatorios preenchidos', () => {
    expect(camposObrigatoriosFaltando(RASCUNHO_OK)).toEqual([])
  })

  it('telefone e contato tambem sao obrigatorios', () => {
    expect(camposObrigatoriosFaltando({ ...RASCUNHO_OK, telefone: '', contato: '' }))
      .toEqual(['telefone', 'contato'])
  })

  it('aponta os campos vazios na ordem do formulario', () => {
    expect(camposObrigatoriosFaltando({ ...RASCUNHO_OK, email: '', endereco: '' }))
      .toEqual(['endereco', 'email'])
  })

  it('trata so espacos e campo ausente como vazio', () => {
    expect(camposObrigatoriosFaltando({ ...RASCUNHO_OK, municipio: '   ' })).toEqual(['municipio'])
    expect(camposObrigatoriosFaltando({})).toEqual(
      ['nome', 'documento', 'endereco', 'municipio', 'estado', 'cep', 'telefone', 'email', 'contato'],
    )
  })

  it('campos de digitos so com pontuacao nao contam como preenchidos', () => {
    expect(camposObrigatoriosFaltando({ ...RASCUNHO_OK, documento: '--' })).toEqual(['documento'])
    expect(camposObrigatoriosFaltando({ ...RASCUNHO_OK, cep: '-' })).toEqual(['cep'])
  })
})

describe('validarProposta', () => {
  it('aceita proposta com cliente, dados obrigatorios e outros itens', () => {
    expect(validarProposta(OK)).toBeNull()
  })

  it('exige cliente', () => {
    expect(validarProposta({ ...OK, cliente: null })).toMatch(/selecione o cliente/i)
  })

  it('espera o carregamento do cliente antes de julgar os campos', () => {
    expect(validarProposta({ ...OK, rascunho: {}, carregandoCliente: true })).toMatch(/aguarde/i)
  })

  it('lista os campos obrigatorios que faltam, pelo rotulo', () => {
    const msg = validarProposta({ ...OK, rascunho: { ...RASCUNHO_OK, email: '', cep: '' } })
    expect(msg).toMatch(/obrigat/i)
    expect(msg).toContain('CEP')
    expect(msg).toContain('E-mail')
  })

  it('exige o bloco de outros itens preenchido', () => {
    expect(validarProposta({ ...OK, outrosItens: '<p><br></p>' })).toMatch(/Outros Itens/)
  })

  it('reporta o cliente antes dos campos quando faltam os dois', () => {
    expect(validarProposta({ cliente: null, rascunho: {}, outrosItens: null })).toMatch(/selecione o cliente/i)
  })
})
