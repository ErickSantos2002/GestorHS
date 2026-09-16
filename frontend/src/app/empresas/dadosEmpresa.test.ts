import { describe, it, expect } from 'vitest'
import {
  camposFaltando, dadosDeCliente, dadosDeEmpresa, dadosVazios, OBRIGATORIOS_PROPOSTA,
  sugestoesDeCliente, sugestoesDeEmpresa,
} from './dadosEmpresa'
import type { Cliente } from '../clientes/api'
import type { Empresa } from './api'

const CLIENTE = {
  id: 5, grupo: null, nome: 'ACME', cgc: '08857492000148', cpf: null, endereco: 'Rua X', numero: 10,
  complemento: null, bairro: 'Centro', municipio: 'Recife', estado: 'PE', cep: '50000000', contato: null,
  email: 'a@acme.com', telefones: null, celular: '81999990000', whatsapp: null, whatsapp1: null, whatsapp2: null,
  insc_mun: null, insc_est: null, datcad: null, obs: null, ativo: true,
} as Cliente

const EMPRESA: Empresa = {
  id: 9, cliente: 5, matriz_nome: 'ACME', nome: 'Filial', cgc: '36312056000552', cpf: null, cep: '29680000',
  endereco: 'BR 101', numero: 'S/N', complemento: null, bairro: 'Zona Rural', municipio: 'Joao Neiva',
  estado: 'ES', email: 'f@acme.com', telefone: '2733330000', insc_est: null, ativo: true,
  created_at: null, updated_at: null,
}

describe('dadosEmpresa', () => {
  it('dados do cliente abrem com e-mail e telefone vazios', () => {
    const d = dadosDeCliente(CLIENTE)
    expect(d).toMatchObject({ nome: 'ACME', documento: '08857492000148', numero: '10', bairro: 'Centro' })
    expect(d.email).toBe('')
    expect(d.telefone).toBe('')
  })

  it('com comContato, e-mail e telefone vem do cadastro', () => {
    expect(dadosDeEmpresa(EMPRESA, { comContato: true })).toMatchObject({ email: 'f@acme.com', telefone: '2733330000' })
  })

  it('sugestao de telefone do cliente prefere telefones e cai no celular', () => {
    expect(sugestoesDeCliente(CLIENTE)).toEqual({ email: 'a@acme.com', telefone: '81999990000' })
    expect(sugestoesDeCliente({ ...CLIENTE, telefones: '8130001111' }).telefone).toBe('8130001111')
    expect(sugestoesDeEmpresa(EMPRESA)).toEqual({ email: 'f@acme.com', telefone: '2733330000' })
  })

  it('camposFaltando ignora pontuacao em documento e cep', () => {
    const d = { ...dadosVazios('...'), nome: 'X', cep: '-' }
    expect(camposFaltando(d, OBRIGATORIOS_PROPOSTA)).toEqual(
      ['documento', 'cep', 'endereco', 'municipio', 'estado', 'telefone', 'email'],
    )
  })
})
