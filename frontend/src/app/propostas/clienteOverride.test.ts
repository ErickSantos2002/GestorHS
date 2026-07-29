import { describe, it, expect } from 'vitest'
import { camposAlterados, temOverride, valorDoCadastro } from './clienteOverride'
import type { Cliente } from '../clientes/api'

const CLIENTE = {
  id: 5, grupo: null, nome: 'Cliente Teste', cgc: '36312056000552', cpf: null, endereco: 'Rua X, 10',
  numero: null, complemento: null, bairro: null, municipio: 'Recife', estado: 'PE', cep: null, contato: 'Ana',
  email: 'cliente@teste.com', telefones: '8130001111', celular: null, whatsapp: null, whatsapp1: null, whatsapp2: null,
  insc_mun: null, insc_est: null, datcad: null, obs: null, ativo: true,
} as Cliente

describe('temOverride', () => {
  it('so considera override quando ha algum valor de fato', () => {
    expect(temOverride(null)).toBe(false)
    expect(temOverride({})).toBe(false)
    expect(temOverride({ nome: '' })).toBe(false)
    expect(temOverride({ nome: '   ' })).toBe(false)
    expect(temOverride({ nome: 'Outro' })).toBe(true)
  })
})

describe('valorDoCadastro', () => {
  it('documento cai no CPF quando nao ha CNPJ', () => {
    expect(valorDoCadastro('documento', CLIENTE)).toBe('36312056000552')
    expect(valorDoCadastro('documento', { ...CLIENTE, cgc: null, cpf: '12345678909' })).toBe('12345678909')
  })

  it('telefone prefere celular, depois whatsapp, depois telefones', () => {
    expect(valorDoCadastro('telefone', CLIENTE)).toBe('8130001111')
    expect(valorDoCadastro('telefone', { ...CLIENTE, celular: '81999998888' })).toBe('81999998888')
  })

  it('sem cliente devolve vazio', () => {
    expect(valorDoCadastro('nome', null)).toBe('')
  })
})

describe('camposAlterados', () => {
  it('sem override nao lista nada', () => {
    expect(camposAlterados(null, CLIENTE)).toEqual([])
    expect(camposAlterados({}, CLIENTE)).toEqual([])
  })

  it('lista so os campos preenchidos, com o valor do cadastro ao lado', () => {
    const r = camposAlterados({ nome: 'Filial Recife', email: '' }, CLIENTE)
    expect(r).toHaveLength(1)
    expect(r[0]).toMatchObject({ campo: 'nome', rotulo: 'Razão social / Nome', cadastro: 'Cliente Teste', proposta: 'Filial Recife', mudou: true })
  })

  it('formata o documento dos dois lados', () => {
    const [d] = camposAlterados({ documento: '12345678909' }, CLIENTE)
    expect(d.cadastro).toBe('36.312.056/0005-52')
    expect(d.proposta).toBe('123.456.789-09')
    expect(d.mudou).toBe(true)
  })

  it('marca mudou=false quando o override repete o cadastro', () => {
    const [d] = camposAlterados({ documento: '36.312.056/0005-52' }, CLIENTE)
    expect(d.mudou).toBe(false)
    const [n] = camposAlterados({ nome: '  Cliente Teste  ' }, CLIENTE)
    expect(n.mudou).toBe(false)
  })

  it('sem o cadastro carregado ainda mostra o valor da proposta', () => {
    const [n] = camposAlterados({ nome: 'Filial Recife' }, null)
    expect(n.cadastro).toBe('')
    expect(n.proposta).toBe('Filial Recife')
    expect(n.mudou).toBe(true)
  })

  it('mantem a ordem canonica dos campos', () => {
    const r = camposAlterados({ contato: 'Joao', nome: 'X', documento: '111' }, CLIENTE)
    expect(r.map((c) => c.campo)).toEqual(['nome', 'documento', 'contato'])
  })
})
