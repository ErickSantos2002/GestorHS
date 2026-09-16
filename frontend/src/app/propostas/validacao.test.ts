import { describe, it, expect } from 'vitest'
import { htmlTemTexto, validarProposta, camposObrigatoriosFaltando } from './validacao'
import { dadosVazios } from '../empresas/dadosEmpresa'
import type { Cliente } from '../clientes/api'

const COMPLETO = {
  ...dadosVazios('08857492000148'), nome: 'ACME', cep: '50000000', endereco: 'Rua X',
  municipio: 'Recife', estado: 'PE', email: 'a@a.com', telefone: '81999990000',
}
const SELECAO = { tipo: 'cliente' as const, cliente: { id: 5 } as Cliente }

describe('validacao', () => {
  it('htmlTemTexto ignora markup vazio do editor', () => {
    expect(htmlTemTexto('<p><br></p>')).toBe(false)
    expect(htmlTemTexto('<p>&nbsp;</p>')).toBe(false)
    expect(htmlTemTexto('<p>ok</p>')).toBe(true)
  })

  it('exige destinatario', () => {
    expect(validarProposta({ selecao: null, dados: COMPLETO, contato: 'Maria', outrosItens: '<p>x</p>' }))
      .toBe('Escolha o destinatário antes de salvar a proposta.')
  })

  it('espera o carregamento', () => {
    expect(validarProposta({ selecao: SELECAO, dados: COMPLETO, contato: 'Maria', outrosItens: '<p>x</p>', carregando: true }))
      .toBe('Aguarde o carregamento dos dados do destinatário.')
  })

  it('lista os obrigatorios faltando, incluindo o contato', () => {
    const dados = { ...COMPLETO, email: '', telefone: ' ' }
    expect(camposObrigatoriosFaltando(dados, '', true)).toEqual(['Telefone', 'E-mail', 'Contato (aos cuidados de)'])
    expect(validarProposta({ selecao: SELECAO, dados, contato: '', outrosItens: '<p>x</p>' }))
      .toBe('Preencha os campos obrigatórios: Telefone, E-mail, Contato (aos cuidados de).')
  })

  it('exige outros itens', () => {
    expect(validarProposta({ selecao: SELECAO, dados: COMPLETO, contato: 'Maria', outrosItens: '<p><br></p>' }))
      .toBe('Preencha "Outros Itens ou Serviços" — use o botao Aplicar modelo.')
  })

  it('documento so e obrigatorio para empresa nova', () => {
    const semDoc = { ...COMPLETO, documento: '' }
    expect(validarProposta({ selecao: SELECAO, dados: semDoc, contato: 'Maria', outrosItens: '<p>x</p>' })).toBeNull()
    expect(validarProposta({ selecao: { tipo: 'nova_empresa', matriz: null }, dados: semDoc, contato: 'Maria', outrosItens: '<p>x</p>' }))
      .toBe('Preencha os campos obrigatórios: CNPJ / CPF.')
  })

  it('ok', () => {
    expect(validarProposta({ selecao: SELECAO, dados: COMPLETO, contato: 'Maria', outrosItens: '<p>x</p>' })).toBeNull()
  })
})
