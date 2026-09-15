import { describe, it, expect } from 'vitest'
import { clienteDaFrota, descreverSelecao, montarDestinatario, type Selecao } from './destinatario'
import { dadosVazios } from '../empresas/dadosEmpresa'
import type { Cliente } from '../clientes/api'
import type { Empresa } from '../empresas/api'

const CLIENTE = { id: 5, nome: 'ACME' } as Cliente
const EMPRESA = { id: 9, nome: 'Filial', cliente: 5, matriz_nome: 'ACME' } as Empresa
const EMPRESA_SOLTA = { ...EMPRESA, cliente: null, matriz_nome: null } as Empresa

const DADOS = {
  ...dadosVazios('36.312.056/0005-52'), nome: ' Filial ', cep: '29680-000', endereco: 'BR 101',
  numero: 'S/N', municipio: 'Joao Neiva', estado: 'ES', email: 'f@acme.com', telefone: '2733330000',
}

describe('destinatario', () => {
  it('cliente da frota por tipo', () => {
    expect(clienteDaFrota(null)).toBeNull()
    expect(clienteDaFrota({ tipo: 'cliente', cliente: CLIENTE })).toBe(5)
    expect(clienteDaFrota({ tipo: 'empresa', empresa: EMPRESA })).toBe(5)
    expect(clienteDaFrota({ tipo: 'empresa', empresa: EMPRESA_SOLTA })).toBeNull()
    expect(clienteDaFrota({ tipo: 'nova_empresa', matriz: { id: 7, nome: 'M' } })).toBe(7)
    expect(clienteDaFrota({ tipo: 'nova_empresa', matriz: null })).toBeNull()
  })

  it('payload de cliente nao leva documento', () => {
    const p = montarDestinatario({ tipo: 'cliente', cliente: CLIENTE }, DADOS)
    expect(p).toMatchObject({ tipo: 'cliente', id: 5, matriz: null, documento: null, nome: 'Filial', cep: '29680000', bairro: null })
  })

  it('payload de nova empresa leva documento em digitos e a matriz', () => {
    const s: Selecao = { tipo: 'nova_empresa', matriz: { id: 7, nome: 'M' } }
    expect(montarDestinatario(s, DADOS)).toMatchObject({ tipo: 'nova_empresa', id: null, matriz: 7, documento: '36312056000552' })
  })

  it('descricao', () => {
    expect(descreverSelecao({ tipo: 'empresa', empresa: EMPRESA })).toBe('Empresa · matriz ACME')
    expect(descreverSelecao({ tipo: 'empresa', empresa: EMPRESA_SOLTA })).toBe('Empresa · sem matriz')
    expect(descreverSelecao({ tipo: 'cliente', cliente: CLIENTE })).toBe('Cliente')
    expect(descreverSelecao({ tipo: 'nova_empresa', matriz: null })).toBe('Nova empresa · sem matriz')
  })
})
